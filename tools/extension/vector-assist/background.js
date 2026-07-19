// Vector Assist - Background Script
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch(function (error) { console.error(error); });

var siteTabId = null;

function findActiveSiteTab(callback) {
  chrome.tabs.query({ url: "*://*.vectorizer.ai/*", active: true, currentWindow: true }, function (tabs) {
    if (tabs && tabs.length) { callback(tabs[0].id); return; }
    chrome.tabs.query({ url: "*://*.vectorizer.ai/*" }, function (all) {
      callback(all && all.length ? all[0].id : (siteTabId || null));
    });
  });
}

chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (!msg || !msg.type) return;

  if (msg.type === "VECTOR_ASSIST_CONTENT_READY") {
    if (sender.tab && sender.tab.id) siteTabId = sender.tab.id;
    return;
  }

  if (msg.type === "VECTOR_ASSIST_PAGE_CHANGED") {
    chrome.runtime.sendMessage(
      { type: "VECTOR_ASSIST_PAGE_CHANGED", settings: msg.settings },
      function () {}
    );
    return;
  }

  if (msg.type === "VECTOR_ASSIST_GET_SETTINGS") {
    findActiveSiteTab(function (tabId) {
      if (tabId != null) {
        chrome.tabs.sendMessage(tabId, { type: "VECTOR_ASSIST_GET_SETTINGS" }, function (resp) {
          sendResponse(resp || { settings: {} });
        });
      } else {
        sendResponse({ settings: {} });
      }
    });
    return true;
  }

  if (msg.type === "VECTOR_ASSIST_APPLY_SETTINGS") {
    findActiveSiteTab(function (tabId) {
      if (tabId != null) {
        chrome.tabs.sendMessage(tabId, {
          type: "VECTOR_ASSIST_APPLY_SETTINGS",
          settings: msg.settings
        }, function () {});
      }
    });
    return;
  }
});
