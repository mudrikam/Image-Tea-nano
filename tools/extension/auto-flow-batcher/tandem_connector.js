// Auto Flow Batcher - Tandem Connector
// Bridges Auto Flow Batcher with Image-Tea Prompt Generator Tandem Server
// Listens for EXECUTE_PROMPT, dispatches to Flow tab, reports settings, and broadcasts download events.

(function () {
  const TANDEM_WS_URL = 'ws://127.0.0.1:48200/ws';
  let _ws = null;
  let _reconnectTimer = null;
  let _isConnected = false;

  let _currentJobDownloadedFiles = [];

  let _keepaliveInterval = null;

  function log(msg) {
    console.log('[AFB-Tandem]', msg);
  }

  function getActiveSettings() {
    return new Promise((resolve) => {
      chrome.storage.local.get(['afb_saved_settings'], (data) => {
        resolve(data?.afb_saved_settings || { type: 'image', batch: '1', ratio: '16:9' });
      });
    });
  }

  function broadcastTandemStatus(connected) {
    _isConnected = connected;
    chrome.runtime.sendMessage({
      action: 'TANDEM_STATUS_CHANGED',
      connected: connected
    }).catch(() => {});
  }

  async function connectTandem() {
    if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      _ws = new WebSocket(TANDEM_WS_URL);
    } catch (_) {
      scheduleReconnect();
      return;
    }

    _ws.onopen = async () => {
      broadcastTandemStatus(true);
      log('Connected to Image-Tea Tandem Server ✓');

      // Periodic heartbeat keepalive to prevent Chrome MV3 service worker termination
      if (_keepaliveInterval) clearInterval(_keepaliveInterval);
      _keepaliveInterval = setInterval(() => {
        if (_ws && _ws.readyState === WebSocket.OPEN) {
          sendPayload({ type: 'PING', client: 'auto_flow' });
        }
      }, 12000);

      const settings = await getActiveSettings();
      sendPayload({
        type: 'REGISTER',
        client: 'auto_flow',
        version: chrome.runtime.getManifest().version,
        settings: settings
      });
    };

    _ws.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
      } catch (err) {
        log('Error parsing incoming message: ' + err.message);
      }
    };

    _ws.onclose = () => {
      // Reconnect automatically if closed
      broadcastTandemStatus(false);
      _ws = null;
      scheduleReconnect();
    };

    _ws.onerror = () => {
      if (_ws) _ws.close();
    };
  }

  function scheduleReconnect() {
    if (_reconnectTimer) return;
    _reconnectTimer = setTimeout(() => {
      _reconnectTimer = null;
      connectTandem();
    }, 2000);
  }

  function sendPayload(payload) {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify(payload));
    }
  }

  // Handle incoming commands from Prompt Generator Tandem Server
  async function handleServerMessage(msg) {
    if (!msg || !msg.action) return;

    if (msg.action === 'EXECUTE_PROMPT') {
      const promptText = msg.prompt;
      const jobId = msg.job_id || Date.now();
      _currentJobDownloadedFiles = [];
      log(`Received prompt job [${jobId}]: "${promptText}"`);

      // Route through sidepanel orchestrator for full UI synchronization & automatic mode normalization
      try {
        chrome.runtime.sendMessage({
          action: 'TANDEM_EXECUTE_PROMPT',
          prompt: promptText,
          jobId: jobId
        }, (res) => {
          if (chrome.runtime.lastError) {
            log('Sidepanel notice: ' + chrome.runtime.lastError.message);
          }
        });

        sendPayload({
          event: 'JOB_ACCEPTED',
          client: 'auto_flow',
          job_id: jobId,
          prompt: promptText
        });
        log(`Prompt [${jobId}] forwarded to Auto Flow Batcher runner ✓`);
      } catch (err) {
        log('Error dispatching to runner: ' + err.message);
        sendPayload({
          event: 'JOB_ERROR',
          client: 'auto_flow',
          job_id: jobId,
          error: err.message
        });
      }
    }

    if (msg.action === 'PING') {
      const settings = await getActiveSettings();
      sendPayload({
        event: 'PONG',
        client: 'auto_flow',
        settings: settings
      });
    }
  }

  // Watch for settings changes in storage and inform server immediately
  if (chrome.storage && chrome.storage.onChanged) {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === 'local' && changes.afb_saved_settings && _isConnected) {
        log('Settings updated in extension, notifying server...');
        sendPayload({
          type: 'SETTINGS_UPDATE',
          client: 'auto_flow',
          settings: changes.afb_saved_settings.newValue
        });
      }
    });
  }

  // Handle sidepanel status & reconnect request
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message && message.type === 'GET_TANDEM_STATUS') {
      sendResponse({ connected: _isConnected });
      return true;
    }
    if (message && (message.type === 'RECONNECT_TANDEM' || message.action === 'RECONNECT_TANDEM')) {
      if (_ws) {
        try { _ws.close(); } catch (_) {}
        _ws = null;
      }
      connectTandem();
      sendResponse({ status: 'reconnecting' });
      return true;
    }
  });

  // Direct export to service worker global scope for instant download notification
  self.broadcastTandemDownload = function (filename, fileSize) {
    log(`Broadcasting file download to Tandem Server: ${filename} (${fileSize} bytes)`);
    if (filename && !_currentJobDownloadedFiles.includes(filename)) {
      _currentJobDownloadedFiles.push(filename);
    }
    sendPayload({
      event: 'FILE_DOWNLOADED',
      source: 'auto_flow',
      filename: filename,
      fileSize: fileSize || 0,
      timestamp: Date.now()
    });
  };

  // Broadcast real file downloads & batch completion to Image-Tea
  chrome.runtime.onMessage.addListener((message) => {
    if (message && (message.action === 'REAL_DOWNLOAD_COMPLETED' || message.type === 'REAL_DOWNLOAD_COMPLETED')) {
      self.broadcastTandemDownload(message.filename, message.fileSize);
    }

    if (message && (message.action === 'AFB_PROMPT_ALL_DOWNLOADS_FINISHED' || message.action === 'AFB_BATCH_FILES_COMPLETED')) {
      const filesToSend = [..._currentJobDownloadedFiles];
      _currentJobDownloadedFiles = [];
      log(`Prompt batch completed: ${filesToSend.length} files. Broadcasting to Tandem Server...`);
      sendPayload({
        event: 'BATCH_COMPLETED',
        source: 'auto_flow',
        prompt: message.prompt || '',
        batchCount: filesToSend.length,
        downloadedCount: filesToSend.length,
        filenames: filesToSend,
        timestamp: Date.now()
      });
    }
  });

  // Start background auto-connection
  connectTandem();
})();
