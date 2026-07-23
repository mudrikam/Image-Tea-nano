// 3D Web Downloader — background service worker
const TWD = (() => {
  // ---- utilities ----
  function sanitizeFilename(name) {
    if (!name) return "model.glb";
    const cleaned = String(name).replace(/[\\/:*?"<>|]/g, "_").replace(/^\.+|\.+$/g, "").trim();
    return cleaned || "model.glb";
  }

  function inferExtension(url) {
    try {
      const u = new URL(url);
      const m = (u.pathname + (u.search || "")).toLowerCase().match(/\.(glb|gltf|usdz)(?=$|\?|#)/);
      if (m) return m[1];
    } catch {}
    return "glb";
  }

  // In-memory folder cache, primed on startup and updated by setFolderCache() / storage changes.
  let currentFolder = "3D-Web-Downloader";

  function folderCache() {
    return new Promise((resolve) => chrome.storage.local.get({ twdFolder: currentFolder }, (v) => {
      currentFolder = v.twdFolder || currentFolder;
      resolve(currentFolder);
    }));
  }

  function setFolderCache(name) {
    const clean = sanitizeFilename(name) || "3D-Web-Downloader";
    currentFolder = clean;
    chrome.storage.local.set({ twdFolder: clean });
  }

  // Prime folder cache at startup.
  folderCache();

  // Refresh folder cache when storage changes from another surface
  // (side panel, settings UI). Vector Assist uses the same pattern.
  if (chrome.storage?.onChanged) {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === "local" && changes.twdFolder) {
        currentFolder = sanitizeFilename(changes.twdFolder.newValue) || "3D-Web-Downloader";
        folderCache();
      }
    });
  }

  // ---- background fetch (avoids CORS for in-extension preview) ----
  async function fetchAsBlob(url) {
    const res = await fetch(url, { credentials: "omit" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const buffer = await blob.arrayBuffer();
    return { mime: blob.type || "model/gltf-binary", buffer: new Uint8Array(buffer) };
  }

  // Ask the active tab's content script to fetch the URL from page context
  // (page origin, so same-origin requests work and many cross-origin CDNs
  // that allow CORS will work too). Falls back to extension fetch.
  async function fetchViaPageThenProxy(url) {
    try {
      const tabs = await new Promise((resolve) =>
        chrome.tabs.query({ active: true, currentWindow: true }, (t) => resolve(t))
      );
      const tab = tabs?.[0];
      if (tab) {
        try {
          const r = await chrome.tabs.sendMessage(tab.id, { type: "TWD_FETCH_IN_PAGE", url });
          if (r?.ok && r.buffer) return { mime: r.mime || "model/gltf-binary", buffer: new Uint8Array(r.buffer) };
        } catch {}
      }
    } catch {}
    return await fetchAsBlob(url);
  }

  // ---- download lifecycle wiring ----
  function buildFilename(asset) {
    const ext = asset.ext || inferExtension(asset.url);
    const base = (asset.filename || "model").replace(/\.(glb|gltf|usdz)$/i, "");
    return sanitizeFilename(`${base}.${ext}`);
  }

  function triggerDownload(asset) {
    const filename = buildFilename(asset);
    // Side panel only passes the basename — the subfolder is injected by the
    // onDeterminingFilename listener below, mirroring Vector Assist's pattern.
    chrome.downloads.download(
      {
        url: asset.url,
        filename,
        saveAs: false,
        conflictAction: "uniquify",
      },
      (downloadId) => {
        const err = chrome.runtime.lastError;
        if (err || !downloadId) {
          broadcast({ type: "TWD_DOWNLOAD_FAILED", assetId: asset.id, error: err?.message || "Unknown error" });
        } else {
          // Folder prefix here is informational only — actual final path is
          // decided once onDeterminingFilename fires. Side panel still sees
          // folder/filename so it can show progress.
          const folder = currentFolder;
          broadcast({ type: "TWD_DOWNLOAD_STARTED", assetId: asset.id, downloadId, folder, filename: `${folder}/${filename}` });
        }
      }
    );
  }

  // Inject the configured subfolder into the final path. Vector Assist uses
  // the same approach: download is created with a basename, this listener
  // renames it to "<folder>/<basename>". Chrome routes conflicting names
  // through conflictAction we set during download().
  if (chrome.downloads?.onDeterminingFilename) {
    chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
      try {
        if (!item) return suggest();
        const folder = currentFolder || "3D-Web-Downloader";
        // Strip any leading subfolders Chrome may already have set so we don't
        // double-prefix (e.g. "folder/model.glb" already becomes folder/model.glb
        // again). Keep the basename only.
        const raw = item.filename || item.suggestedFilename || "model.glb";
        const base = String(raw).replace(/^.*[\\/]/, "");
        const cleanBase = sanitizeFilename(base) || "model.glb";
        suggest({ filename: `${folder}/${cleanBase}`, conflictAction: "uniquify" });
      } catch {
        try { suggest(); } catch {}
      }
    });
  }

  chrome.downloads.onChanged.addListener((delta) => {
    if (!delta || delta.state?.current !== "complete") return;
    chrome.downloads.search({ id: delta.id }, (items) => {
      const it = items?.[0];
      if (!it) return;
      broadcast({
        type: "TWD_DOWNLOAD_COMPLETE",
        downloadId: delta.id,
        url: it.url,
        filename: it.filename,
      });
    });
  });

  // ---- side panel messaging ----
  function broadcast(msg) {
    chrome.runtime.sendMessage(msg).catch(() => {});
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || typeof msg !== "object") return false;

    if (msg.type === "TWD_DOWNLOAD") {
      triggerDownload(msg.asset);
      sendResponse({ ok: true });
      return false;
    }
    if (msg.type === "TWD_DOWNLOAD_BATCH") {
      (msg.assets || []).forEach(triggerDownload);
      sendResponse({ ok: true });
      return false;
    }
    if (msg.type === "TWD_SET_FOLDER") {
      setFolderCache(msg.folder);
      sendResponse({ ok: true });
      return false;
    }
    if (msg.type === "TWD_GET_FOLDER") {
      folderCache().then((f) => sendResponse({ folder: f }));
      return true;
    }
    if (msg.type === "TWD_GET_ACTIVE_TAB") {
      // Report current tab URL to side panel so it can sync state on open.
      if (typeof activeTabId === "number" && tabSessions.has(activeTabId)) {
        const sess = tabSessions.get(activeTabId);
        sendResponse({ tabId: activeTabId, url: sess.url });
      } else {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          const t = tabs?.[0];
          if (t) {
            const sess = { url: t.url, key: sessionKey(t.id, t.url) };
            tabSessions.set(t.id, sess);
            activeTabId = t.id;
          }
          sendResponse({ tabId: t?.id, url: t?.url });
        });
        return true;
      }
      return false;
    }
    if (msg.type === "TWD_RESCAN_TAB") {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs?.[0];
        if (!tab) { sendResponse({ ok: false }); return; }
        chrome.tabs.sendMessage(tab.id, { type: "TWD_RESCAN" }, () => {
          sendResponse({ ok: true });
          void chrome.runtime.lastError;
        });
      });
      return true;
    }
    if (msg.type === "TWD_FETCH_AS_BLOB") {
      // Try fetching from the page (origin = page host, bypasses most CORS),
      // then fall back to extension-origin fetch.
      fetchViaPageThenProxy(msg.url)
        .then((result) => sendResponse({ ok: true, ...result }))
        .catch((err) => sendResponse({ ok: false, error: err?.message || String(err) }));
      return true;
    }
    return false;
  });

  // Open side panel on icon click (default behavior is configured via manifest + setPanelBehavior).
  chrome.sidePanel?.setPanelBehavior?.({ openPanelOnActionClick: true }).catch(() => {});
  // Some builds still call onClicked; ensure it gracefully opens the panel.
  chrome.action.onClicked?.addListener?.((tab) => {
    chrome.sidePanel.open({ tabId: tab.id }).catch(() => {});
  });

  // Track the active tab "session" so any reload or navigation triggers a
// refresh on the side panel, even when the URL is unchanged.
  const tabSessions = new Map(); // tabId -> { url, key }
  let activeTabId = null;

  function sessionKey(tabId, url) {
    return `${tabId}::${url}::${Math.random().toString(36).slice(2, 8)}`;
  }

  function broadcastTab(tabId, url, opts = {}) {
    activeTabId = tabId;
    broadcast({
      type: "TWD_TAB_CHANGED",
      tabId,
      url,
      reason: opts.reason || "change",
    });
  }

  chrome.tabs.onActivated?.addListener?.(({ tabId }) => {
    chrome.tabs.get(tabId, (t) => {
      const url = t?.url;
      const sess = { url, key: sessionKey(tabId, url) };
      tabSessions.set(tabId, sess);
      broadcastTab(tabId, url, { reason: "activated" });
    });
  });

  chrome.tabs.onUpdated?.addListener?.((tabId, change, tab) => {
    const url = tab?.url || change.url;
    if (!url) return;
    const prev = tabSessions.get(tabId);

    // Reload / status transitions (loading → complete) signal a fresh page.
    if (change.status === "loading" && tab?.active) {
      const sess = { url, key: sessionKey(tabId, url) };
      tabSessions.set(tabId, sess);
      broadcastTab(tabId, url, { reason: "loading" });
      return;
    }
    if (change.status === "complete" && tab?.active && prev && prev.url === url) {
      // Same URL completed after a loading phase — treat as reload/nav commit.
      const sess = { url, key: sessionKey(tabId, url) };
      tabSessions.set(tabId, sess);
      broadcastTab(tabId, url, { reason: "complete" });
      return;
    }
    // URL change (navigation to a different page).
    if (url && (!prev || prev.url !== url)) {
      const sess = { url, key: sessionKey(tabId, url) };
      tabSessions.set(tabId, sess);
      if (tab?.active) broadcastTab(tabId, url, { reason: "navigate" });
    }
  });

  chrome.tabs.onRemoved?.addListener?.((tabId) => {
    tabSessions.delete(tabId);
    if (activeTabId === tabId) {
      activeTabId = null;
      broadcast({ type: "TWD_TAB_CHANGED", tabId: null, url: null, reason: "closed" });
    }
  });

  return { TWD_VERSION: "1.0.0" };
})();