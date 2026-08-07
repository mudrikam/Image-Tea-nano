const ITEM_URL = /^https:\/\/elements-contributors\.envato\.com\/item-submissions\/[0-9a-f-]+(?:[/?#]|$)/i;
let bridgeConnection = null;
let reconnectTimer = null;
let wasConnected = false;
let processingCommand = false;
let activeCommandId = null;

function notifyStatus(message, ready) {
  chrome.runtime.sendMessage({ type: 'EEMT_STATUS', message, ready }).catch(() => {});
}

function startReconnectLoop() {
  if (reconnectTimer) return;
  reconnect();
  reconnectTimer = setInterval(reconnect, 2000);
  chrome.alarms.create('eemt-reconnect', { periodInMinutes: 0.5 });
}

async function sendEvent(type, message, extra = {}) {
  if (!bridgeConnection) return;
  chrome.runtime.sendMessage({ type: 'EEMT_LOG', message }).catch(() => {});
  try {
    await fetch(`http://127.0.0.1:${bridgeConnection.port}/extension-event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-EEMT-Connection': bridgeConnection.connectionId },
      body: JSON.stringify({ type, message, ...extra })
    });
  } catch (_) {}
}

async function reconnect() {
  if (!bridgeConnection) return;
  try {
    const response = await fetch(`http://127.0.0.1:${bridgeConnection.port}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        connection_id: bridgeConnection.connectionId,
        url: bridgeConnection.url || '',
        tab_id: bridgeConnection.tabId || null,
        reconnect: true
      })
    });
    if (response.ok) {
      const becameReady = !wasConnected;
      wasConnected = true;
      notifyStatus('Ready to receive data from Image Tea.', true);
      if (becameReady) await sendEvent('ready', 'Extension is ready to receive metadata.');
    }
  } catch (_) {
    if (wasConnected) notifyStatus('Waiting for Image Tea...', false);
    wasConnected = false;
  }
}

async function processCommand(command) {
  if (!command || command.type !== 'EEMT_FILL') return;
  if (activeCommandId === command.command_id) return;
  if (processingCommand) {
    return;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !ITEM_URL.test(tab.url || '')) {
    await sendEvent('error', 'Open an Envato item editing page first. The URL must match /item-submissions/<id>.');
    await sendEvent('command_failed', 'Metadata delivery requires an Envato item editing page.', {
      command_id: command.command_id
    });
    return;
  }
  processingCommand = true;
  activeCommandId = command.command_id;
  try {
    const reloadAndWaitForForm = async () => {
      await sendEvent('status', 'Refreshing the Envato page before metadata fill.');
      await chrome.tabs.reload(tab.id);
      for (let attempt = 0; attempt < 30; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 250));
        const current = await chrome.tabs.get(tab.id);
        if (current.status !== 'complete') continue;
        const result = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => Boolean(document.querySelector(
            '[data-test-selector="item-submission-title"] input'
          ))
        });
        if (result?.[0]?.result) return;
      }
      throw new Error('Envato title field did not become ready after page refresh.');
    };
    await reloadAndWaitForForm();
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
    const response = await chrome.tabs.sendMessage(tab.id, command);
    if (!response?.ok) throw new Error(response?.error || 'Metadata fill failed after page refresh.');
    await sendEvent('command_received', 'Metadata delivered to the Envato page.', {
      command_id: command.command_id
    });
    await sendEvent('status', 'Metadata successfully sent to Envato.');
  } catch (error) {
    await sendEvent('command_failed', `Metadata delivery failed: ${error.message}`, {
      command_id: command.command_id
    });
    await sendEvent('error', error.message);
  } finally {
    processingCommand = false;
    activeCommandId = null;
  }
}

async function pollBridge() {
  if (!bridgeConnection) return;
  try {
    const response = await fetch(`http://127.0.0.1:${bridgeConnection.port}/next-command`, {
      headers: { 'X-EEMT-Connection': bridgeConnection.connectionId }
    });
    const data = await response.json();
    if (data.command) {
      if (activeCommandId !== data.command.command_id) await processCommand(data.command);
    }
  } catch (_) {}
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === 'EEMT_CONNECT') {
    bridgeConnection = message.connection;
    chrome.storage.local.set({ eemt_connection: bridgeConnection });
    startReconnectLoop();
    notifyStatus('Waiting for Image Tea...', false);
  }
  if (message?.type === 'EEMT_DISCONNECT') {
    wasConnected = false;
    bridgeConnection = null;
    chrome.storage.local.remove('eemt_connection');
    notifyStatus('Not ready. Click Connect to receive data.', false);
  }
  if (message?.type === 'EEMT_LOG') {
    sendEvent(message.message?.startsWith('ERROR:') ? 'error' : 'log', message.message);
  }
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'eemt-reconnect') reconnect();
});

chrome.storage.local.get('eemt_connection', (result) => {
  bridgeConnection = result.eemt_connection || null;
  if (bridgeConnection) startReconnectLoop();
});

setInterval(pollBridge, 300);

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});

chrome.runtime.onStartup.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
