var SITE_PATTERN = /:\/\/([^/]+\.)?vectorizer\.ai(\/|$)/i;
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch(function (error) { console.error(error); });

chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
  if (changeInfo.status !== "complete" || !tab.url) return;
  if (SITE_PATTERN.test(tab.url)) {
    chrome.sidePanel.open({ tabId: tabId }).catch(function () {});
  }
});

var siteTabId = null;

function findActiveSiteTab(callback) {
  chrome.tabs.query({ url: "*://*.vectorizer.ai/*", active: true, currentWindow: true }, function (tabs) {
    if (tabs && tabs.length) { callback(tabs[0].id); return; }
    chrome.tabs.query({ url: "*://vectorizer.ai/*" }, function (bare) {
      if (bare && bare.length) { callback(bare[0].id); return; }
      chrome.tabs.query({ url: "*://*.vectorizer.ai/*" }, function (all) {
        callback(all && all.length ? all[0].id : (siteTabId || null));
      });
    });
  });
}

// Wrapper that silences the "Could not establish connection" error that
// surfaces in DevTools whenever a sendMessage fires before the content
// script has loaded on the target tab (common during navigation, page
// reloads, or before the user has opened vectorizer.ai at all). The
// caller still receives a clean { ok: false } response.
function sendTabMessage(tabId, msg, callback) {
  try {
    chrome.tabs.sendMessage(tabId, msg, function (resp) {
      // Touch lastError so Chrome doesn't log it as an unchecked error.
      void (chrome.runtime && chrome.runtime.lastError);
      callback(resp);
    });
  } catch (e) {
    callback(null);
  }
}

// ---------------------------------------------------------------------------
// Download tracking
//
// Vectorizer emits the result file via a programmatic <a> download (blob or
// href) triggered by Options-SubmitTop. The page's App-Progress-Download-Bar
// may stay at 0% even though the file has already landed in chrome.downloads.
// We use the downloads API as the source of truth instead.
//
// Flow:
//   1. sidepanel sends VECTOR_ASSIST_SUBMIT_DOWNLOAD -> we stamp lastSubmitTs.
//   2. chrome.downloads.onChanged fires when a download completes. If its
//      startTime >= lastSubmitTs, we forward DOWNLOAD_COMPLETE to the
//      sidepanel.
//   3. sidepanel awaits that event instead of polling the progress bar.
// ---------------------------------------------------------------------------
var lastSubmitTs = 0;

if (chrome.downloads && chrome.downloads.onChanged) {
  chrome.downloads.onChanged.addListener(function (delta) {
    if (!delta || !delta.state || !delta.state.current) return;
    if (delta.state.current !== "complete") return;
    chrome.downloads.search({ id: delta.id }, function (items) {
      var item = items && items[0];
      if (!item) return;
      var startedAt = Date.parse(item.startTime || "") || 0;
      if (startedAt + 1500 < lastSubmitTs) return;
      chrome.runtime.sendMessage({
        type: "VECTOR_ASSIST_DOWNLOAD_COMPLETE",
        id: delta.id,
        filename: item.filename || (item.suggestedFilename || ""),
        url: item.url || item.finalUrl || "",
        finalUrl: item.finalUrl || item.url || "",
        bytesReceived: item.bytesReceived || 0,
        totalBytes: item.totalBytes || 0,
        ts: Date.now()
      }, function () {});
    });
  });
}

if (chrome.downloads && chrome.downloads.onCreated) {
  chrome.downloads.onCreated.addListener(function (item) {
    if (!item) return;
    chrome.runtime.sendMessage({
      type: "VECTOR_ASSIST_DOWNLOAD_STARTED",
      id: item.id,
      url: item.url || "",
      filename: item.filename || item.suggestedFilename || "",
      ts: Date.now()
    }, function () {});
  });
}

chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (!msg || !msg.type) return;

  if (msg.type === "VECTOR_ASSIST_CONTENT_READY") {
    if (sender.tab && sender.tab.id) siteTabId = sender.tab.id;
    return;
  }

  if (msg.type === "VECTOR_ASSIST_PAGE_PHASE") {
    chrome.runtime.sendMessage({
      type: "VECTOR_ASSIST_PAGE_PHASE",
      pathname: msg.pathname,
      ready: msg.ready,
      tabId: sender.tab && sender.tab.id,
      ts: msg.ts
    }, function () {});
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
        sendTabMessage(tabId, { type: "VECTOR_ASSIST_GET_SETTINGS" }, function (resp) {
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
        sendTabMessage(tabId, {
          type: "VECTOR_ASSIST_APPLY_SETTINGS",
          settings: msg.settings
        }, function () {});
      }
    });
    return;
  }

  if (msg.type === "VECTOR_ASSIST_SUBMIT_DOWNLOAD") {
    lastSubmitTs = Date.now();
  }

  var FORWARD_TYPES = {
    VECTOR_ASSIST_UPLOAD_FILE: true,
    VECTOR_ASSIST_GET_PROGRESS: true,
    VECTOR_ASSIST_GET_PAGE_INFO: true,
    VECTOR_ASSIST_CLICK_DOWNLOAD_LINK: true,
    VECTOR_ASSIST_SUBMIT_DOWNLOAD: true,
    VECTOR_ASSIST_NAVIGATE: true
  };
  if (FORWARD_TYPES[msg.type]) {
    findActiveSiteTab(function (tabId) {
      if (tabId == null) { sendResponse({ ok: false, error: "No vectorizer.ai tab" }); return; }
      sendTabMessage(tabId, msg, function (resp) {
        sendResponse(resp || { ok: false, error: "No response" });
      });
    });
    return true;
  }

  // Make sure a Vectorizer tab exists; if not, open one to the home page
  // so the runner has somewhere to talk to.
  if (msg.type === "VECTOR_ASSIST_ENSURE_SITE") {
    findActiveSiteTab(function (tabId) {
      if (tabId != null) {
        sendResponse({ ok: true, tabId: tabId, alreadyOpen: true });
        return;
      }
      chrome.tabs.create({ url: "https://vectorizer.ai/" }, function (tab) {
        sendResponse({ ok: true, tabId: tab && tab.id, alreadyOpen: false });
      });
    });
    return true;
  }
});
