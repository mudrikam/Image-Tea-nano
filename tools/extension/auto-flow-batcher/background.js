// Auto Flow Batcher - Background Script
// Opens the side panel when the extension icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((error) => console.error(error));

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
