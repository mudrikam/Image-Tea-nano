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

// Handle CDP native click requests from content script
// Uses Chrome DevTools Protocol to dispatch trusted mouse events
// that React's event system will properly handle (isTrusted: true)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'CDP_CLICK') {
    const tabId = message.tabId || sender?.tab?.id;
    if (!tabId) {
      sendResponse({ ok: false, error: 'No tab ID' });
      return true;
    }
    const { x, y } = message;
    const debuggee = { tabId };

    (async () => {
      try {
        await chrome.debugger.attach(debuggee, '1.3');
        await chrome.debugger.sendCommand(debuggee, 'Input.dispatchMouseEvent', {
          type: 'mousePressed', x, y, button: 'left', clickCount: 1
        });
        await new Promise(r => setTimeout(r, 50));
        await chrome.debugger.sendCommand(debuggee, 'Input.dispatchMouseEvent', {
          type: 'mouseReleased', x, y, button: 'left', clickCount: 1
        });
        await new Promise(r => setTimeout(r, 50));
        await chrome.debugger.detach(debuggee);
        sendResponse({ ok: true });
      } catch (err) {
        try { await chrome.debugger.detach(debuggee); } catch (_) {}
        sendResponse({ ok: false, error: err.message });
      }
    })();
    return true;
  }
});

// Handle download requests from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'DOWNLOAD_CONTENT') {
    const url = message.url;
    const promptIndex = message.promptIndex || 0;
    const extension = message.extension || 'jpg';
    const prefix = message.prefix || 'Flow_Image';
    const promptWords = message.promptWords || '';
    const batchIndex = message.batchIndex || 0;
    const timestamp = Date.now();

    // Build filename: Flow_Image_prompt1_batch1_2024-12-07_123456.jpg
    const date = new Date();
    const dateStr = date.toISOString().replace(/[:.]/g, '-').split('T')[0];
    const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '-');

    let filename;
    if (promptWords) {
      filename = `${prefix}_prompt${promptIndex + 1}_batch${batchIndex + 1}_${dateStr}_${timeStr}.${extension}`;
    } else {
      filename = `${prefix}_prompt${promptIndex + 1}_batch${batchIndex + 1}_${dateStr}_${timeStr}.${extension}`;
    }

    filename = filename.replace(/[<>:"/\\|?*]/g, '_');

    chrome.downloads.download({
      url: url,
      filename: filename,
      saveAs: false
    }).then((downloadId) => {
      console.log('[AFB] Download started:', downloadId, '→', filename);
    }).catch((err) => {
      console.error('[AFB] Download failed:', err);
    });
  }

  if (message.type === 'DOWNLOAD_DONE') {
    const count = message.count || 0;
    const sessionId = message.sessionId || '';
    console.log(`[AFB] Download batch complete: ${count} media items, session ${sessionId}`);
  }
});
