(() => {
  const $ = (id) => document.getElementById(id);
  const metadata = $('metadata');
  const status = $('status');
  const log = $('log');
  const paste = $('paste');
  const fill = $('fill');
  const clear = $('clear');
  const STORAGE_KEY = 'eemt_state';

  function setStatus(text, kind = '') {
    status.textContent = text;
    status.className = `status ${kind}`;
  }

  function renderState(state) {
    if (!state) return;
    if (state.metadata && !metadata.value) metadata.value = JSON.stringify(state.metadata, null, 2);
    if (Array.isArray(state.logs)) log.textContent = state.logs.join('\n') + (state.logs.length ? '\n' : '');
    if (state.status) setStatus(state.status, state.kind || '');
    log.scrollTop = log.scrollHeight;
  }

  metadata.addEventListener('input', () => {
    const current = parseMetadata(metadata.value);
    if (current) {
      chrome.storage.local.set({ [STORAGE_KEY]: { metadata: current, status: status.textContent, kind: status.className.replace('status', '').trim(), logs: log.textContent.trim().split('\n').filter(Boolean) } });
    }
  });

  chrome.storage.local.get(STORAGE_KEY, (result) => renderState(result[STORAGE_KEY]));

  paste.addEventListener('click', async () => {
    try {
      metadata.value = await navigator.clipboard.readText();
      chrome.storage.local.set({ [STORAGE_KEY]: { metadata: parseMetadata(metadata.value), status: 'JSON pasted from clipboard.', kind: 'success', logs: [] } });
      setStatus('JSON pasted from clipboard.', 'success');
    } catch (_) {
      setStatus('Clipboard access failed. Use Ctrl+V in the JSON box.', 'error');
      metadata.focus();
    }
  });

  clear.addEventListener('click', async () => {
    metadata.value = '';
    log.textContent = '';
    setStatus('Extension state cleared.');
    await chrome.storage.local.remove(STORAGE_KEY);
    metadata.focus();
  });

  fill.addEventListener('click', async () => {
    let data;
    try {
      data = JSON.parse(metadata.value);
    } catch (_) {
      setStatus('Invalid JSON.', 'error');
      return;
    }
    fill.disabled = true;
    log.textContent = '';
    setStatus('Starting form filling...');
    chrome.storage.local.set({ [STORAGE_KEY]: { metadata: data, status: 'Starting form filling...', kind: '', logs: [] } });
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || !/^https:\/\/elements(?:-contributors)?\.envato\.com\//.test(tab.url || '')) {
        throw new Error('The active tab is not an Envato Elements contributor page.');
      }
      let response;
      try {
        response = await chrome.tabs.sendMessage(tab.id, { type: 'EEMT_FILL', metadata: data });
      } catch (_) {
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
        response = await chrome.tabs.sendMessage(tab.id, { type: 'EEMT_FILL', metadata: data });
      }
      if (!response?.ok) throw new Error(response?.error || 'Automation could not start.');
      setStatus('Form filling completed.', 'success');
      chrome.storage.local.set({ [STORAGE_KEY]: { metadata: data, status: 'Form filling completed.', kind: 'success', logs: log.textContent.trim().split('\n').filter(Boolean) } });
    } catch (error) {
      setStatus(error.message, 'error');
      chrome.storage.local.set({ [STORAGE_KEY]: { metadata: data, status: error.message, kind: 'error', logs: log.textContent.trim().split('\n').filter(Boolean) } });
    } finally {
      fill.disabled = false;
    }
  });

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type !== 'EEMT_LOG') return;
    log.textContent += `${message.message}\n`;
    log.scrollTop = log.scrollHeight;
  });

  function parseMetadata(value) {
    try { return JSON.parse(value); } catch (_) { return null; }
  }
})();
