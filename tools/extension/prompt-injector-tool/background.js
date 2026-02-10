chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error(error));

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const relayTypes = [
    'ELEMENT_PICKED',
    'AUTOMATION_PROGRESS',
    'AUTOMATION_FINISHED',
    'AUTOMATION_STATUS',
    'AUTOMATION_ERROR',
    'DOWNLOAD_COUNTDOWN',
    'DOWNLOAD_SCANNING',
    'DOWNLOAD_DONE'
  ];
  
  if (relayTypes.includes(message.type)) {
    chrome.runtime.sendMessage(message).catch(() => {});
  }
  
  if (message.type === 'DOWNLOAD_CONTENT') {
    const url = message.url;
    const promptIndex = message.promptIndex || 0;
    const extension = message.extension || 'jpg';
    const prefix = message.prefix || 'Generated_Content';
    const promptWords = message.promptWords || '';
    const timestamp = Date.now();
    
    let filename;
    if (promptWords) {
      filename = `${prefix}_${promptWords}_${timestamp}.${extension}`;
    } else {
      filename = `${prefix}_prompt${promptIndex + 1}_${timestamp}.${extension}`;
    }
    
    filename = filename.replace(/[<>:"/\\|?*]/g, '_');
    
    chrome.downloads.download({
      url: url,
      filename: filename,
      saveAs: false
    }).then((downloadId) => {
      console.log('[Prompt Injector] Download started:', downloadId);
    }).catch((err) => {
      console.error('[Prompt Injector] Download failed:', err);
    });
  }
  
  if (message.type === 'RELOAD_PAGE') {
    chrome.tabs.query({ active: true, lastFocusedWindow: true }).then(([tab]) => {
      if (tab && tab.id) {
        console.log('[Prompt Injector] Reloading page due to crash detection');
        chrome.tabs.reload(tab.id);
      }
    }).catch((err) => {
      console.error('[Prompt Injector] Failed to reload page:', err);
    });
  }
  
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  console.log('[Prompt Injector] Extension installed');
});

console.log('[Prompt Injector] Background service worker loaded');
