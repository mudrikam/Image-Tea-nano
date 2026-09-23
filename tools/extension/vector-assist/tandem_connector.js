// Vector Assist - Tandem Connector
// Bridges Vector Assist with Image-Tea Prompt Generator Tandem Server
// Listens for EXECUTE_FILES (batch or single), injects files into Vector Assist queue,
// and broadcasts download completion and batch finish back to Image-Tea.

(function () {
  const TANDEM_WS_URL = 'ws://127.0.0.1:48200/ws';
  let _ws = null;
  let _reconnectTimer = null;
  let _isConnected = false;

  let _keepaliveInterval = null;

  function log(msg) {
    console.log('[Vector-Tandem]', msg);
  }

  function broadcastTandemStatus(connected) {
    _isConnected = connected;
    chrome.runtime.sendMessage({
      action: 'TANDEM_STATUS_CHANGED',
      connected: connected
    }).catch(() => {});
  }

  function connectTandem() {
    if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      _ws = new WebSocket(TANDEM_WS_URL);
    } catch (_) {
      scheduleReconnect();
      return;
    }

    _ws.onopen = () => {
      broadcastTandemStatus(true);
      log('Connected to Image-Tea Tandem Server ✓');

      // Periodic heartbeat keepalive to prevent Chrome MV3 service worker termination
      if (_keepaliveInterval) clearInterval(_keepaliveInterval);
      _keepaliveInterval = setInterval(() => {
        if (_ws && _ws.readyState === WebSocket.OPEN) {
          sendPayload({ type: 'PING', client: 'vector_assist' });
        }
      }, 12000);

      sendPayload({
        type: 'REGISTER',
        client: 'vector_assist',
        version: chrome.runtime.getManifest().version
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
      if (_keepaliveInterval) {
        clearInterval(_keepaliveInterval);
        _keepaliveInterval = null;
      }
      if (_isConnected) {
        log('Disconnected from Image-Tea Tandem Server');
      }
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

  // Fetch local file from Image-Tea local bridge server and convert to DataURL
  async function fetchFileAsDataUrl(filepath) {
    const fileFetchUrl = `http://127.0.0.1:48200/file?path=${encodeURIComponent(filepath)}`;
    const resp = await fetch(fileFetchUrl);
    if (!resp.ok) {
      throw new Error(`Failed to fetch file from local server (HTTP ${resp.status}): ${filepath}`);
    }
    const blob = await resp.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve({
        name: filepath.split(/[\\/]/).pop(),
        type: blob.type || 'image/jpeg',
        size: blob.size,
        dataUrl: reader.result
      });
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  // Handle incoming commands from Prompt Generator Tandem Server
  async function handleServerMessage(msg) {
    if (!msg || !msg.action) return;

    // Handles both EXECUTE_FILES (batch list) and EXECUTE_FILE (single)
    if (msg.action === 'EXECUTE_FILES' || msg.action === 'EXECUTE_FILE') {
      const filepaths = msg.filepaths || (msg.filepath ? [msg.filepath] : []);
      const jobId = msg.job_id || Date.now();
      log(`Received vector job [${jobId}] with ${filepaths.length} file(s)`);

      if (!filepaths.length) {
        sendPayload({
          event: 'JOB_ERROR',
          client: 'vector_assist',
          job_id: jobId,
          error: 'No files provided'
        });
        return;
      }

      try {
        // Fetch all files concurrently from local bridge server
        const loadedFiles = await Promise.all(filepaths.map(fetchFileAsDataUrl));

        // Dispatch into sidepanel runner
        chrome.runtime.sendMessage({
          action: 'TANDEM_ADD_FILES_AND_START',
          files: loadedFiles,
          job_id: jobId
        }).catch((err) => {
          log('Sidepanel message delivery error: ' + err.message);
        });

        sendPayload({
          event: 'JOB_ACCEPTED',
          client: 'vector_assist',
          job_id: jobId,
          fileCount: loadedFiles.length
        });
      } catch (err) {
        log(`Error fetching vector files: ${err.message}`);
        sendPayload({
          event: 'JOB_ERROR',
          client: 'vector_assist',
          job_id: jobId,
          error: err.message
        });
      }
    }

    if (msg.action === 'PING') {
      sendPayload({ event: 'PONG', client: 'vector_assist' });
    }
  }

  // Direct export to background service worker for instant download notification
  self.broadcastVectorTandemDownload = function (filename, fileSize) {
    log(`Broadcasting vector download to Tandem Server: ${filename} (${fileSize} bytes)`);
    sendPayload({
      event: 'FILE_DOWNLOADED',
      source: 'vector_assist',
      filename: filename,
      fileSize: fileSize,
      timestamp: Date.now()
    });
  };

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

  // Broadcast each individual file download completed from Vectorizer to Image-Tea
  chrome.runtime.onMessage.addListener((message) => {
    if (message && message.type === 'VECTOR_ASSIST_DOWNLOAD_COMPLETE') {
      sendPayload({
        event: 'FILE_DOWNLOADED',
        source: 'vector_assist',
        filename: message.filename,
        fileSize: message.totalBytes || 0,
        timestamp: message.ts || Date.now()
      });
    }

    // Broadcast entire batch completed from Vectorizer to Image-Tea
    if (message && message.type === 'VECTOR_ASSIST_BATCH_COMPLETED') {
      log(`Vector batch completed (${message.count} files). Reporting to Tandem Server...`);
      sendPayload({
        event: 'BATCH_COMPLETED',
        source: 'vector_assist',
        count: message.count,
        durationSeconds: message.durationSeconds || 0,
        timestamp: Date.now()
      });
    }
  });

  // Start background auto-connection
  connectTandem();
})();
