(() => {
  const portInput = document.getElementById('port');
  const connect = document.getElementById('connect');
  const status = document.getElementById('status');
  const log = document.getElementById('log');
  const stateKey = 'eemt_connection';
  let connectionId = null;
  let connected = false;

  const write = (message, kind = '') => {
    status.textContent = message;
    status.className = `status ${kind}`;
    log.textContent += `${new Date().toLocaleTimeString()} ${message}\n`;
    log.scrollTop = log.scrollHeight;
  };

  const setReadyState = (message, ready) => {
    status.textContent = message;
    status.className = `status ${ready ? 'success' : ''}`;
    document.body.classList.toggle('bridge-ready', ready);
  };

  async function connectToApp() {
    const port = Number(portInput.value);
    if (!Number.isInteger(port) || port < 1024 || port > 65535) {
      write('Port must be between 1024 and 65535.', 'error');
      return;
    }
    connectionId = crypto.randomUUID();
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.storage.local.set({ [stateKey]: {
      port,
      connectionId,
      url: tab?.url || '',
      tabId: tab?.id || null
    } });
    write('Waiting for Image Tea...', '');
    connected = true;
    connect.textContent = 'Disconnect';
    connect.classList.add('button-danger');
    portInput.disabled = true;
    await chrome.runtime.sendMessage({
      type: 'EEMT_CONNECT',
      connection: { port, connectionId, url: tab?.url || '', tabId: tab?.id || null }
    });
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === 'EEMT_LOG') write(message.message);
    if (message?.type === 'EEMT_STATUS') setReadyState(message.message, message.ready);
  });

  async function disconnectFromApp() {
    if (!connectionId) return;
    const port = Number(portInput.value);
    try {
      await fetch(`http://127.0.0.1:${port}/disconnect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ connection_id: connectionId })
      });
    } catch (_) {}
    await chrome.runtime.sendMessage({ type: 'EEMT_DISCONNECT' });
    await chrome.storage.local.remove(stateKey);
    connectionId = null;
    connected = false;
    connect.textContent = 'Connect';
    connect.classList.remove('button-danger');
    connect.disabled = false;
    portInput.disabled = false;
    write('Not ready. Click Connect to receive data.');
  }

  connect.addEventListener('click', () => {
    const action = connected ? disconnectFromApp() : connectToApp();
    action.catch((error) => write(error.message, 'error'));
  });
  chrome.storage.local.get(stateKey, (result) => {
    const saved = result[stateKey];
    if (saved?.port) {
      portInput.value = saved.port;
      connectionId = saved.connectionId;
      connected = true;
      connect.textContent = 'Disconnect';
      connect.classList.add('button-danger');
      portInput.disabled = true;
      write('Waiting for Image Tea...', '');
    }
  });
})();
