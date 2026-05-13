// Mockup Preview Prompt - Background Script
// Opens the side panel when the extension icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((error) => console.error(error));

// Handle CDP native click requests from content script
// Uses Chrome DevTools Protocol to dispatch trusted mouse events
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
    const prefix = message.prefix || 'Mockup_Preview';
    const batchIndex = message.batchIndex || 0;
    const promptWords = (message.promptWords || '').replace(/[<>:"/\\|?*]/g, '_');

    const date = new Date();
    const dateStr = date.toISOString().replace(/[:.]/g, '-').split('T')[0];
    const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '-');

    let filename = `${prefix}_prompt${promptIndex + 1}_batch${batchIndex + 1}_${dateStr}_${timeStr}${promptWords ? '_' + promptWords : ''}.${extension}`;
    filename = filename.replace(/[<>:"/\\|?*]/g, '_');

    chrome.downloads.download({
      url: url,
      filename: filename,
      saveAs: false
    }).then((downloadId) => {
      console.log('[MPP] Download started:', downloadId, '→', filename);
      const response = {
        ok: true,
        downloadId: downloadId,
        filename: filename,
        promptIndex: promptIndex,
        batchIndex: batchIndex
      };
      sendResponse(response);
      // Notify sidepanel about download
      chrome.runtime.sendMessage({
        action: 'DOWNLOAD_STARTED',
        downloadId: downloadId,
        filename: filename,
        promptIndex: promptIndex,
        batchIndex: batchIndex
      }).catch(() => {});
    }).catch((err) => {
      console.error('[MPP] Download failed:', err);
      const response = {
        ok: false,
        error: err.message || String(err),
        url: url,
        promptIndex: promptIndex,
        batchIndex: batchIndex
      };
      sendResponse(response);
      chrome.runtime.sendMessage({
        action: 'DOWNLOAD_FAILED',
        error: response.error,
        promptIndex: promptIndex,
        batchIndex: batchIndex
      }).catch(() => {});
    });
    return true;
  }
});
