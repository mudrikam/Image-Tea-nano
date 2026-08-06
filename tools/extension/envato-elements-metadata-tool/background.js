const ITEM_URL = /^https:\/\/elements-contributors\.envato\.com\/item-submissions\/[0-9a-f-]+(?:[/?#]|$)/i;
let bridgeConnection = null;
let reconnectTimer = null;
let wasConnected = false;

function startReconnectLoop() {
  if (reconnectTimer) return;
  reconnect();
  reconnectTimer = setInterval(reconnect, 2000);
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
    if (response.ok && !wasConnected) {
      wasConnected = true;
      await sendEvent('status', 'Extension otomatis terhubung ke Image Tea.');
    }
  } catch (_) {}
}

async function processCommand(command) {
  if (!command || command.type !== 'EEMT_FILL') return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !ITEM_URL.test(tab.url || '')) {
    await sendEvent('error', 'Buka halaman edit item Envato terlebih dahulu. URL harus berbentuk /item-submissions/<id>.');
    return;
  }
  await sendEvent('status', 'Halaman item valid, memulai pengisian metadata.');
  try {
    let response;
    try {
      response = await chrome.tabs.sendMessage(tab.id, command);
    } catch (_) {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
      response = await chrome.tabs.sendMessage(tab.id, command);
    }
    if (!response?.ok) throw new Error(response?.error || 'Pengisian metadata gagal.');
  } catch (error) {
    await sendEvent('error', error.message);
  }
}

async function pollBridge() {
  if (!bridgeConnection) return;
  try {
    const response = await fetch(`http://127.0.0.1:${bridgeConnection.port}/next-command`, {
      headers: { 'X-EEMT-Connection': bridgeConnection.connectionId }
    });
    const data = await response.json();
    if (data.command) await processCommand(data.command);
  } catch (_) {}
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === 'EEMT_CONNECT') {
    bridgeConnection = message.connection;
    chrome.storage.local.set({ eemt_connection: bridgeConnection });
    startReconnectLoop();
    wasConnected = true;
    sendEvent('status', 'Extension connected dan siap menerima metadata.');
  }
  if (message?.type === 'EEMT_DISCONNECT') {
    wasConnected = false;
    bridgeConnection = null;
    chrome.storage.local.remove('eemt_connection');
  }
  if (message?.type === 'EEMT_LOG') {
    sendEvent(message.message?.startsWith('ERROR:') ? 'error' : 'log', message.message);
  }
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
