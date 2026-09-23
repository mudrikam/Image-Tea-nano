// Auto Flow Batcher - Background Script
// Opens the side panel when the extension icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((error) => console.error(error));

// ─── Auto-Update Checker ───────────────────────────────────────────────────────
const UPDATE_CHECK_INTERVAL_MS = 60 * 60 * 1000; // Check every 1 hour
const REMOTE_MANIFEST_URL = 'https://raw.githubusercontent.com/mudrikam/Image-Tea-nano/main/tools/extension/auto-flow-batcher/manifest.json';
const DOWNLOAD_ZIP_URL = 'https://github.com/mudrikam/Image-Tea-nano/archive/refs/heads/main.zip';

async function checkForExtensionUpdate() {
  try {
    const response = await fetch(REMOTE_MANIFEST_URL, { cache: 'no-store' });
    if (!response.ok) return;
    const remoteManifest = await response.json();
    const remoteVersion = remoteManifest.version;
    const localVersion = chrome.runtime.getManifest().version;

    if (!remoteVersion || !localVersion) return;

    if (compareVersions(remoteVersion, localVersion) > 0) {
      // Notify sidepanel about available update
      chrome.runtime.sendMessage({
        action: 'UPDATE_AVAILABLE',
        remoteVersion: remoteVersion,
        localVersion: localVersion,
        downloadUrl: DOWNLOAD_ZIP_URL
      }).catch(() => {});

      // Store update info so sidepanel can check on load
      chrome.storage.local.set({
        updateAvailable: true,
        remoteVersion: remoteVersion,
        localVersion: localVersion,
        downloadUrl: DOWNLOAD_ZIP_URL
      });

      console.log(`[AFB] Update available: ${localVersion} → ${remoteVersion}`);
    } else {
      chrome.storage.local.set({ updateAvailable: false });
    }
  } catch (err) {
    console.warn('[AFB] Update check failed:', err.message);
  }
}

// Compare semantic versions: returns >0 if a > b, 0 if equal, <0 if a < b
function compareVersions(a, b) {
  const partsA = a.split('.').map(Number);
  const partsB = b.split('.').map(Number);
  const len = Math.max(partsA.length, partsB.length);
  for (let i = 0; i < len; i++) {
    const numA = partsA[i] || 0;
    const numB = partsB[i] || 0;
    if (numA > numB) return 1;
    if (numA < numB) return -1;
  }
  return 0;
}

// Check on install/update
chrome.runtime.onInstalled.addListener(() => {
  checkForExtensionUpdate();
});

// Check on startup
chrome.runtime.onStartup.addListener(() => {
  checkForExtensionUpdate();
});

// Periodic check
setInterval(checkForExtensionUpdate, UPDATE_CHECK_INTERVAL_MS);

// Also check when sidepanel requests it
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'CHECK_FOR_UPDATE') {
    checkForExtensionUpdate().then(() => sendResponse({ ok: true })).catch(() => sendResponse({ ok: false }));
    return true; // async response
  }
});

// ─── Chrome Downloads Tracker (Vector-Assist True Source of Truth) ────────────
if (chrome.downloads && chrome.downloads.onChanged) {
  chrome.downloads.onChanged.addListener((delta) => {
    if (!delta || !delta.state || !delta.state.current) return;
    if (delta.state.current !== 'complete') return;

    chrome.downloads.search({ id: delta.id }, (items) => {
      const item = items && items[0];
      if (!item) return;

      console.log('[AFB-Download] Real file download confirmed complete:', item.filename, `(${item.fileSize || item.totalBytes || 0} bytes)`);

      const payload = {
        action: 'REAL_DOWNLOAD_COMPLETED',
        type: 'REAL_DOWNLOAD_COMPLETED',
        id: delta.id,
        filename: item.filename,
        url: item.url,
        fileSize: item.fileSize || item.totalBytes || 0,
        timestamp: Date.now()
      };

      // Direct notify to Tandem Server connector if active (only Flow downloads, ignore vectorizer.ai)
      const isFromVectorizer = (item.url || '').toLowerCase().includes('vectorizer.ai');
      if (!isFromVectorizer && typeof self.broadcastTandemDownload === 'function') {
        try { self.broadcastTandemDownload(item.filename, item.fileSize || item.totalBytes || 0); } catch (_) {}
      }

      // Broadcast to both sidepanel, background internal listeners, and all tabs
      try { chrome.runtime.sendMessage(payload); } catch (_) {}
      try {
        chrome.tabs.query({}, (tabs) => {
          if (tabs && tabs.length > 0) {
            tabs.forEach(t => {
              if (t.id) {
                chrome.tabs.sendMessage(t.id, payload).catch(() => {});
              }
            });
          }
        });
      } catch (_) {}
    });
  });
}

// Handle download requests from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'DOWNLOAD_CONTENT') {
    lastDownloadRequestTs = Date.now();
    const url = message.url;
    const promptIndex = message.promptIndex || 0;
    const extension = message.extension || 'jpg';
    const prefix = message.prefix || 'Flow_Image';
    const promptWords = message.promptWords || '';
    const batchIndex = message.batchIndex || 0;

    // Build filename: Flow_Image_prompt1_batch1_2024-12-07_123456.jpg
    const date = new Date();
    const dateStr = date.toISOString().replace(/[:.]/g, '-').split('T')[0];
    const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '-');

    let filename = `${prefix}_prompt${promptIndex + 1}_batch${batchIndex + 1}_${dateStr}_${timeStr}.${extension}`;
    filename = filename.replace(/[<>:"/\\|?*]/g, '_');

    chrome.downloads.download({
      url: url,
      filename: filename,
      saveAs: false
    }).then((downloadId) => {
      console.log('[AFB] Download started:', downloadId, '→', filename);
      sendResponse({ ok: true, downloadId });
    }).catch((err) => {
      console.error('[AFB] Download failed:', err);
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (message.type === 'STAMP_DOWNLOAD_START') {
    lastDownloadRequestTs = Date.now();
    sendResponse({ ok: true, ts: lastDownloadRequestTs });
    return true;
  }

  // ─── CDP Trusted Hardware Click via Chrome Debugger (Ultra-Fast Instant Detach) ─────
  if (message.type === 'TRIGGER_CDP_CLICK') {
    const tabId = sender?.tab?.id || message.tabId;
    const x = Math.round(message.x || 0);
    const y = Math.round(message.y || 0);

    if (!tabId || !x || !y) {
      sendResponse({ ok: false, error: 'Invalid CDP click coordinates or tabId' });
      return true;
    }

    const debuggee = { tabId };

    (async () => {
      try {
        // 1. Attach debugger
        await new Promise((resolve) => {
          chrome.debugger.attach(debuggee, '1.3', () => resolve());
        });

        // 2. Dispatch mousePressed immediately
        await new Promise((resolve) => {
          chrome.debugger.sendCommand(debuggee, 'Input.dispatchMouseEvent', {
            type: 'mousePressed',
            x: x,
            y: y,
            button: 'left',
            clickCount: 1
          }, () => resolve());
        });

        // 3. Ultra-short hold (15ms)
        await new Promise(r => setTimeout(r, 15));

        // 4. Dispatch mouseReleased
        await new Promise((resolve) => {
          chrome.debugger.sendCommand(debuggee, 'Input.dispatchMouseEvent', {
            type: 'mouseReleased',
            x: x,
            y: y,
            button: 'left',
            clickCount: 1
          }, () => resolve());
        });

        // 5. Immediate Detach — hides the banner instantly
        chrome.debugger.detach(debuggee, () => {});

        console.log(`[AFB-CDP] Ultra-fast trusted click dispatched at (${x}, ${y})`);
        sendResponse({ ok: true });
      } catch (err) {
        try { chrome.debugger.detach(debuggee, () => {}); } catch (_) {}
        console.error('[AFB-CDP] Error dispatching CDP click:', err);
        sendResponse({ ok: false, error: err.message });
      }
    })();

    return true; // async response
  }
});

// ─── Tandem Connector Bridge ──────────────────────────────────────────────────
try {
  importScripts('tandem_connector.js');
} catch (e) {
  console.warn('[AFB] Tandem connector script import:', e);
}
