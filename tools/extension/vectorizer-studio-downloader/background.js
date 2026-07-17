// Vees Downloader - Background Script
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(function (error) { console.error(error); });

var SITE_URL = 'https://vectorizer.studio/';
var vectorizerTabId = null;

function log(msg) { console.log('[Vees BG]', msg); }

chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
  if (message.type === 'GET_OR_CREATE_TAB') {
    getOrCreateVectorizerTab().then(function (tabId) {
      sendResponse({ tabId: tabId });
    });
    return true;
  }

  if (message.type === 'PROCESS_FILE') {
    log('PROCESS_FILE received for: ' + message.file.fileName);
    getOrCreateVectorizerTab().then(function (tabId) {
      log('Sending PROCESS_FILE to tab ' + tabId);
      chrome.tabs.sendMessage(tabId, message, function (response) {
        if (chrome.runtime.lastError) {
          log('sendMessage failed: ' + chrome.runtime.lastError.message);
          sendResponse({ received: false, error: chrome.runtime.lastError.message });
        } else {
          sendResponse(response || { received: false });
        }
      });
    }).catch(function (err) {
      log('getOrCreateVectorizerTab failed: ' + err.message);
      sendResponse({ received: false, error: err.message });
    });
    return true;
  }

  if (message.type === 'BLOB_CAPTURED') {
    log('Blob captured for: ' + message.fileName);
    chrome.runtime.sendMessage({
      type: 'BLOB_CAPTURED_SIDEPANEL',
      fileName: message.fileName,
      vectorizedData: message.vectorizedData,
      blobUrl: message.blobUrl
    }).catch(function () {});
    sendResponse({ received: true });
    return true;
  }

  if (message.type === 'PROCESS_FAILED') {
    log('Process failed for: ' + message.fileName + ' - ' + message.reason);
    chrome.runtime.sendMessage({
      type: 'PROCESS_FAILED_SIDEPANEL',
      fileName: message.fileName,
      reason: message.reason
    }).catch(function () {});
    sendResponse({ received: true });
    return true;
  }

  if (message.type === 'LOG') { console.log(message.message); return; }

  if (message.type === 'STOP_PROCESSING') {
    if (vectorizerTabId) {
      chrome.tabs.sendMessage(vectorizerTabId, { type: 'STOP_PROCESSING' }).catch(function () {});
    }
    sendResponse({ stopped: true });
    return true;
  }

  if (message.type === 'DOWNLOAD_SVG') {
    var svgData = message.svgData;
    var fileName = message.fileName.replace(/\.[^.]+$/, '') + '.svg';
    var dataUrl = svgData.startsWith('data:') ? svgData : 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
    chrome.downloads.download({ url: dataUrl, filename: fileName, saveAs: false }, function (downloadId) {
      if (chrome.runtime.lastError) {
        sendResponse({ success: false, error: chrome.runtime.lastError.message });
      } else {
        sendResponse({ success: true, downloadId: downloadId });
      }
    });
    return true;
  }
});

async function getOrCreateVectorizerTab() {
  if (vectorizerTabId) {
    try {
      var tab = await chrome.tabs.get(vectorizerTabId);
      if (tab && tab.url && tab.url.includes('vectorizer.studio')) {
        await ensureContentScript(tab.id);
        return vectorizerTabId;
      }
    } catch (e) { vectorizerTabId = null; }
  }

  var tabs = await chrome.tabs.query({ url: '*://*.vectorizer.studio/*' });
  if (tabs.length > 0) {
    vectorizerTabId = tabs[0].id;
    await ensureContentScript(vectorizerTabId);
    return vectorizerTabId;
  }

  var newTab = await chrome.tabs.create({ url: SITE_URL, active: true });
  vectorizerTabId = newTab.id;

  await new Promise(function (resolve) {
    var listener = function (tabId, info) {
      if (tabId === vectorizerTabId && info.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 2000);
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(function () { chrome.tabs.onUpdated.removeListener(listener); resolve(); }, 20000);
  });

  await ensureContentScript(vectorizerTabId);
  return vectorizerTabId;
}

async function ensureContentScript(tabId) {
  try {
    var results = await chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: function () { return !!window.__VEES_CONTENT_LOADED__; }
    });
    var loaded = results && results[0] && results[0].result;
    if (!loaded) {
      log('Content script not loaded, injecting...');
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ['content.js']
      });
      await new Promise(function (r) { setTimeout(r, 500); });
    }
  } catch (e) {
    log('ensureContentScript error: ' + e.message);
  }
}

chrome.tabs.onRemoved.addListener(function (tabId) {
  if (tabId === vectorizerTabId) vectorizerTabId = null;
});