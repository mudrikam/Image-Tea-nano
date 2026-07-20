// Vector Assist - Side Panel (UI only)
(function () {
  var SITE_URL = "https://vectorizer.ai/";
  var SITE_PATTERN = /:\/\/([^/]+\.)?vectorizer\.ai(\/|$)/i;

  var landingPage, mainInterface, btnOpenSite;
  var dndZone, fileInput, folderInput, btnSelectFiles, btnSelectFolder;
  var btnStartProcess, btnStopProcess, btnClearAll, btnResetApp;
  var fileTableBody, emptyState;
  var statLoaded, statPending, statFinished, statFailed;
  var isRunning = false;

  // Realtime two-way mirror state.
  var applyingFromPage = false;   // true while we reflect page -> extension
  var applyingToPage = false;     // true while we push extension -> page

  // In-memory file list. Each item:
  // { name, type, size, dataUrl, status: "pending"|"processing"|"done"|"failed" }
  var files = [];
  var selectedName = null;

  // --------------------------------------------------------------------------
  // Logger: ring-buffered activity log for the Logs tab.
  //   - Max lines (cap FIFO once exceeded).
  //   - Entries older than LOG_TTL_MS are pruned on add() and on focus.
  //   - Levels: debug | info | warn | error | mirror | page | preset.
  // --------------------------------------------------------------------------
  var LOG_MAX = 500;        // ~ newest 500 lines
  var LOG_TTL_MS = 24 * 60 * 60 * 1000; // 24h
  var logEntries = [];
  var logFilterText = "";
  var logAutoscroll = true;
  var logListEl, logEmptyEl, logFilterEl, logAutoscrollEl, btnLogClear;

  function log(level, msg) {
    var entry = { ts: Date.now(), level: level || "info", msg: String(msg == null ? "" : msg) };
    logEntries.push(entry);
    if (logEntries.length > LOG_MAX) {
      logEntries.splice(0, logEntries.length - LOG_MAX);
    }
    var cutoff = Date.now() - LOG_TTL_MS;
    while (logEntries.length && logEntries[0].ts < cutoff) {
      logEntries.shift();
    }
    appendLogLine(entry);
    updateLogEmptyState();
  }
  function logDebug(m) { log("debug", m); }
  function logInfo(m)  { log("info",  m); }
  function logWarn(m)  { log("warn",  m); }
  function logError(m) { log("error", m); }

  function formatLogTime(ts) {
    var d = new Date(ts);
    function p(n) { return n < 10 ? "0" + n : "" + n; }
    return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function appendLogLine(entry) {
    if (!logListEl) return;
    if (!matchesLogFilter(entry)) return; // filtered out -> skip render
    var li = document.createElement("li");
    li.className = "log-" + entry.level;
    li.dataset.time = String(entry.ts);
    li.innerHTML =
      '<span class="log-time">' + escapeHtml(formatLogTime(entry.ts)) + '</span>' +
      '<span class="log-level">' + escapeHtml(entry.level) + '</span>' +
      escapeHtml(entry.msg);
    logListEl.appendChild(li);
    applyLogFilter();
    if (logAutoscroll) {
      try { logListEl.parentElement && logListEl.parentElement.scrollTop; } catch (e) {}
      // Scroll the log list's scroll container (.tab-panels contains it).
      var panel = logListEl.closest(".tab-panel");
      if (panel) panel.scrollTop = panel.scrollHeight;
    }
  }

  function updateLogEmptyState() {
    if (!logEmptyEl || !logListEl) return;
    var hasVisible = logListEl.querySelectorAll("li:not(.hidden-by-filter)").length > 0;
    logEmptyEl.classList.toggle("hidden", hasVisible || logEntries.length === 0);
    if (logEntries.length === 0) {
      logEmptyEl.textContent = "No log entries yet.";
    } else if (!hasVisible) {
      logEmptyEl.textContent = "No entries match the filter.";
    } else {
      logEmptyEl.textContent = "";
    }
  }

  function matchesLogFilter(entry) {
    if (!logFilterText) return true;
    var f = logFilterText.toLowerCase();
    return entry.msg.toLowerCase().indexOf(f) >= 0 || entry.level.toLowerCase().indexOf(f) >= 0;
  }

  function applyLogFilter() {
    if (!logListEl) return;
    var f = (logFilterText || "").toLowerCase();
    var nodes = logListEl.querySelectorAll("li");
    for (var i = 0; i < nodes.length; i++) {
      var li = nodes[i];
      var t = li.textContent.toLowerCase();
      li.classList.toggle("hidden-by-filter", f && t.indexOf(f) < 0);
    }
    updateLogEmptyState();
  }

  function rebuildLogList() {
    if (!logListEl) return;
    logListEl.innerHTML = "";
    for (var i = 0; i < logEntries.length; i++) appendLogLine(logEntries[i]);
    updateLogEmptyState();
  }

  function pruneExpiredLogs() {
    var cutoff = Date.now() - LOG_TTL_MS;
    var before = logEntries.length;
    logEntries = logEntries.filter(function (e) { return e.ts >= cutoff; });
    if (logEntries.length !== before) {
      rebuildLogList();
    }
  }

  function setupLogs() {
    logListEl = document.getElementById("logList");
    logEmptyEl = document.getElementById("logEmpty");
    logFilterEl = document.getElementById("logFilter");
    logAutoscrollEl = document.getElementById("logAutoscroll");
    btnLogClear = document.getElementById("btnLogClear");
    if (!logListEl) return;

    if (logFilterEl) {
      logFilterEl.addEventListener("input", function () {
        logFilterText = logFilterEl.value || "";
        applyLogFilter();
      });
    }
    if (logAutoscrollEl) {
      logAutoscrollEl.checked = logAutoscroll;
      logAutoscrollEl.addEventListener("change", function () {
        logAutoscroll = !!logAutoscrollEl.checked;
      });
    }
    if (btnLogClear) {
      btnLogClear.onclick = function () {
        logEntries = [];
        rebuildLogList();
        logInfo("Logs cleared");
      };
    }
    // Prune on focus (sidebar reopened) + every minute.
    pruneExpiredLogs();
    setInterval(pruneExpiredLogs, 60 * 1000);
    window.addEventListener("focus", pruneExpiredLogs);
  }

  var DB_NAME = "VectorAssist";
  var STORE_NAME = "files";
  var DB_VERSION = 1;
  var db = null;

  function openDB() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        var database = e.target.result;
        if (!database.objectStoreNames.contains(STORE_NAME)) {
          database.createObjectStore(STORE_NAME, { keyPath: "name" });
        }
      };
      req.onsuccess = function (e) { db = e.target.result; resolve(db); };
      req.onerror = function (e) { reject(e.target.error); };
    });
  }

  function ensureDB() {
    return db ? Promise.resolve(db) : openDB();
  }

  function dbGetAll() {
    return ensureDB().then(function () {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction([STORE_NAME], "readonly");
        var req = tx.objectStore(STORE_NAME).getAll();
        req.onsuccess = function (e) { resolve(e.target.result || []); };
        req.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function dbPut(record) {
    return ensureDB().then(function () {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction([STORE_NAME], "readwrite");
        tx.objectStore(STORE_NAME).put(record);
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function dbDelete(name) {
    return ensureDB().then(function () {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction([STORE_NAME], "readwrite");
        tx.objectStore(STORE_NAME).delete(name);
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function dbClear() {
    return ensureDB().then(function () {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction([STORE_NAME], "readwrite");
        tx.objectStore(STORE_NAME).clear();
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  var IMAGE_EXT = /\.(png|jpe?g|webp|gif|bmp)$/i;

  function isImageFile(file) {
    return (file.type && /^image\//.test(file.type)) || IMAGE_EXT.test(file.name);
  }

  function readFileAsDataURL(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function (e) { resolve(e.target.result); };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function truncName(name) {
    if (name.length <= 28) return name;
    var dot = name.lastIndexOf(".");
    if (dot > 0) {
      return name.substring(0, 18) + "..." + name.substring(dot);
    }
    return name.substring(0, 25) + "...";
  }

  function checkCurrentTab() {
    return new Promise(function (resolve) {
      chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        if (!tabs || !tabs[0] || !tabs[0].url) { resolve(false); return; }
        resolve(SITE_PATTERN.test(tabs[0].url));
      });
    });
  }

  function initView() {
    return checkCurrentTab().then(function (onSite) {
      if (onSite) {
        landingPage.classList.add("hidden");
        mainInterface.classList.remove("hidden");
        log("page", "On vectorizer.ai — main interface shown");
        // Push saved settings to page so extension always overrides the web.
        var root = document.querySelector(".settings");
        if (root) pushSettingsToPage(root);
      } else {
        mainInterface.classList.add("hidden");
        landingPage.classList.remove("hidden");
        log("page", "Not on vectorizer.ai — landing page shown");
      }
    });
  }

  function openSite() {
    chrome.tabs.query({ url: "*://*.vectorizer.ai/*" }, function (tabs) {
      if (tabs && tabs.length > 0) {
        chrome.tabs.update(tabs[0].id, { active: true });
        if (chrome.windows) chrome.windows.update(tabs[0].windowId, { focused: true });
      } else {
        chrome.tabs.create({ url: SITE_URL });
      }
    });
  }

  function setupDnD() {
    if (!dndZone) return;

    btnSelectFiles.onclick = function () { fileInput.value = ""; fileInput.click(); };
    btnSelectFolder.onclick = function () { folderInput.value = ""; folderInput.click(); };

    dndZone.onclick = function (e) {
      if (e.target === dndZone || e.target.closest(".dnd-icon") || e.target.closest(".dnd-text") || e.target.closest(".dnd-hint")) {
        fileInput.value = ""; fileInput.click();
      }
    };
    dndZone.addEventListener("dragover", function (e) { e.preventDefault(); dndZone.classList.add("drag-over"); });
    dndZone.addEventListener("dragleave", function (e) { e.preventDefault(); dndZone.classList.remove("drag-over"); });
    dndZone.addEventListener("drop", function (e) {
      e.preventDefault();
      dndZone.classList.remove("drag-over");

      var items = e.dataTransfer && e.dataTransfer.items;
      if (items && items.length && items[0].webkitGetAsEntry) {
        // Supports dropping folders (recursively).
        var collected = [];
        var walks = [];
        for (var i = 0; i < items.length; i++) {
          var entry = items[i].webkitGetAsEntry();
          if (entry) walks.push(walkEntry(entry, collected));
        }
        Promise.all(walks).then(function () { addNewFiles(collected); });
      } else {
        addNewFiles(Array.prototype.slice.call(e.dataTransfer.files));
      }
    });

    fileInput.addEventListener("change", function () {
      addNewFiles(Array.prototype.slice.call(fileInput.files));
    });
    folderInput.addEventListener("change", function () {
      addNewFiles(Array.prototype.slice.call(folderInput.files));
    });
  }

  function walkEntry(entry, out) {
    if (entry.isFile) {
      return new Promise(function (resolve) {
        entry.file(function (f) { out.push(f); resolve(); }, function () { resolve(); });
      });
    }
    if (entry.isDirectory) {
      var reader = entry.createReader();
      return new Promise(function (resolve) {
        function readBatch() {
          reader.readEntries(function (entries) {
            if (!entries.length) { resolve(); return; }
            var jobs = [];
            for (var i = 0; i < entries.length; i++) jobs.push(walkEntry(entries[i], out));
            Promise.all(jobs).then(readBatch);
          }, function () { resolve(); });
        }
        readBatch();
      });
    }
    return Promise.resolve();
  }

  function addNewFiles(rawFiles) {
    if (!rawFiles || !rawFiles.length) return;

    var images = rawFiles.filter(isImageFile);
    if (!images.length) return;

    var existing = {};
    files.forEach(function (f) { existing[f.name] = true; });

    var fresh = images.filter(function (f) { return !existing[f.name]; });
    if (!fresh.length) return;

    log("info", "Loading " + fresh.length + " file(s)...");

    var jobs = fresh.map(function (f) {
      return readFileAsDataURL(f).then(function (dataUrl) {
        var record = {
          name: f.name,
          type: f.type || "image/png",
          size: f.size,
          dataUrl: dataUrl,
          status: "pending"
        };
        files.push(record);
        logDebug("Loaded file '" + f.name + "' (" + f.size + " bytes)");
        return dbPut(record).catch(function () {});
      }).catch(function (e) {
        logError("Failed to read '" + f.name + "': " + e);
      });
    });

    Promise.all(jobs).then(function () {
      renderFileList();
      log("info", "File list now has " + files.length + " item(s)");
    });
  }

  function renderFileList() {
    if (!fileTableBody) return;
    fileTableBody.innerHTML = "";

    if (!files.length) {
      if (emptyState) emptyState.classList.remove("hidden");
      updateStats();
      return;
    }
    if (emptyState) emptyState.classList.add("hidden");

    files.forEach(function (file, index) {
      var row = document.createElement("tr");
      if (selectedName === file.name) row.classList.add("selected");
      row.onclick = function () {
        selectedName = file.name;
        renderFileList();
      };

      var numCell = document.createElement("td");
      numCell.className = "file-num";
      numCell.textContent = index + 1;
      row.appendChild(numCell);

      var fileCell = document.createElement("td");
      var cellWrap = document.createElement("div");
      cellWrap.className = "file-name-cell";
      var thumb = document.createElement("img");
      thumb.className = "file-thumb";
      thumb.src = file.dataUrl;
      thumb.alt = "";
      var nameEl = document.createElement("span");
      nameEl.className = "file-name";
      nameEl.textContent = truncName(file.name);
      nameEl.title = file.name;
      cellWrap.appendChild(thumb);
      cellWrap.appendChild(nameEl);
      fileCell.appendChild(cellWrap);
      row.appendChild(fileCell);

      var statusCell = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "status-badge status-" + file.status;
      badge.textContent = file.statusLabel ||
        (file.status.charAt(0).toUpperCase() + file.status.slice(1));
      statusCell.appendChild(badge);
      if (file === runnerCurrent || (file.status === "processing" && runnerCurrent === file.name) ||
          file.status === "downloading" || file.status === "submitting" ||
          file.status === "uploading" || file.status === "applying" ||
          file.status === "delaying" || file.status === "redirecting" ||
          file.status === "waiting-vectorize") {
        var remaining = 0;
        if (runnerCountdownTarget && runnerCountdownTarget > Date.now()) {
          remaining = Math.ceil((runnerCountdownTarget - Date.now()) / 1000);
        }
        var t = document.createElement("span");
        t.className = "file-row-timer";
        if (remaining > 0) {
          t.textContent = "waiting " + remaining + "s…";
        } else if (runnerFileStartTs) {
          var elapsed = Math.max(0, Math.floor((Date.now() - runnerFileStartTs) / 1000));
          t.textContent = formatHMS(elapsed) + " elapsed";
        }
        statusCell.appendChild(t);
      }
      row.appendChild(statusCell);
      row.dataset.name = file.name;

      var actionsCell = document.createElement("td");
      var actions = document.createElement("div");
      actions.className = "file-actions";
      actions.appendChild(makeActionBtn(file, "act-run", "Run this file",
        '<svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>'));
      // Skip: jump past a stuck file without aborting the whole batch.
      if (runnerState !== "idle" && file.status !== "done" && file.status !== "pending") {
        actions.appendChild(makeActionBtn(file, "act-skip", "Skip this file",
          '<svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg>'));
      }
      actions.appendChild(makeActionBtn(file, "act-delete", "Delete",
        '<svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'));
      actionsCell.appendChild(actions);
      row.appendChild(actionsCell);

      fileTableBody.appendChild(row);
    });

    updateStats();
  }

  function makeActionBtn(file, cls, title, svg) {
    var btn = document.createElement("button");
    btn.className = "btn-row " + cls;
    btn.title = title;
    btn.innerHTML = svg;
    btn.onclick = function (e) {
      e.stopPropagation();
      if (cls === "act-delete") {
        deleteFile(file.name);
      } else if (cls === "act-run") {
        startOne(file.name);
      } else if (cls === "act-skip") {
        skipFile(file.name);
      }
    };
    return btn;
  }

  function deleteFile(name) {
    files = files.filter(function (f) { return f.name !== name; });
    if (selectedName === name) selectedName = null;
    dbDelete(name).catch(function () {});
    renderFileList();
    log("info", "Deleted file '" + name + "'");
  }

  function updateStats() {
    var counts = { pending: 0, processing: 0, done: 0, failed: 0 };
    files.forEach(function (f) {
      if (counts[f.status] !== undefined) counts[f.status]++;
    });
    if (statLoaded) statLoaded.textContent = files.length;
    if (statPending) statPending.textContent = counts.pending + counts.processing;
    if (statFinished) statFinished.textContent = counts.done;
    if (statFailed) statFailed.textContent = counts.failed;
  }

  function updateControlUI() {
    if (!btnStartProcess) return;
    var iconStart = btnStartProcess.querySelector(".icon-start");
    var iconPause = btnStartProcess.querySelector(".icon-pause");
    var label = btnStartProcess.querySelector(".control-start-label");

    var s = runnerState;
    btnStartProcess.classList.remove("running", "paused");

    if (s === "running") {
      btnStartProcess.classList.add("running");
      if (iconStart) iconStart.classList.add("hidden");
      if (iconPause) iconPause.classList.remove("hidden");
      if (label) label.textContent = "Pause";
      btnStartProcess.disabled = false;
    } else if (s === "paused" || s === "captcha") {
      btnStartProcess.classList.add("paused");
      if (iconStart) iconStart.classList.add("hidden");
      if (iconPause) iconPause.classList.remove("hidden");
      if (label) label.textContent = "Resume";
      btnStartProcess.disabled = false;
    } else {
      if (iconStart) iconStart.classList.remove("hidden");
      if (iconPause) iconPause.classList.add("hidden");
      if (label) label.textContent = "Start Process";
      btnStartProcess.disabled = false;
    }

    if (btnStopProcess) btnStopProcess.disabled = (s === "idle");
  }

function formatHMS(totalSec) {
    var h = Math.floor(totalSec / 3600);
    var m = Math.floor((totalSec % 3600) / 60);
    var s = totalSec % 60;
    function p(n) { return n < 10 ? "0" + n : "" + n; }
    return h > 0 ? (h + ":" + p(m) + ":" + p(s)) : (m + ":" + p(s));
  }

function startOne(name) {
  var file = files.filter(function (f) { return f.name === name; })[0];
  if (!file) return;

  // Manual single-file run: honors the click immediately. If a batch is
  // running, it interrupts the batch and starts this file alone (no cooldown
  // between manual runs — that only applies to batch mode).
  if (runnerState !== "idle" || runnerAbortCtrl) {
    log("info", "Run " + name + ": interrupting current batch");
    if (runnerAbortCtrl && !runnerAbortSignal && typeof runnerAbortCtrl.abort === "function") {
      runnerAbortCtrl.abort();
    }
    runnerAbortSignal = true;
    runnerPauseRequested = false;
    runnerCaptchaPause = false;
    runnerQueue = [];
    runnerCurrent = null;
    runnerSetState("idle");
    // Mark non-target in-flight files skipped (target file will start fresh).
    files.forEach(function (f) {
      if (f.name !== name && f.status !== "done" && f.status !== "pending") {
        f.status = "pending";
        f.statusLabel = "Skipped";
      }
    });
    renderFileList();
    // Give the abort a tick to propagate before starting the new batch.
    setTimeout(function () {
      try { runnerStart([name], { single: true }); }
      catch (e) { logError("startOne failed: " + e); }
    }, 80);
    return;
  }
  runnerStart([name], { single: true });
}

function skipFile(name) {
  // Skip aborts the in-flight file's awaits (via runnerAbortSignal), drains
  // it from the queue, then re-pumps for the remaining items.
  if (!runnerAbortCtrl || runnerAbortSignal) {
    logWarn("Skip ignored: nothing running");
    return;
  }
  log("info", "Skipping " + name);
  if (typeof runnerAbortCtrl.abort === "function") runnerAbortCtrl.abort();
  runnerAbortSignal = true;
  runnerPauseRequested = false;
  runnerCaptchaPause = false;
  var f = files.filter(function (x) { return x.name === name; })[0];
  if (f) {
    f.status = "pending";
    f.statusLabel = "Skipped";
    renderFileList();
  }
  runnerQueue = runnerQueue.filter(function (n) { return n !== name; });
  runnerCurrent = null;
  if (runnerQueue.length) {
    runnerSetState("running");
    runnerAbortCtrl = new (typeof AbortController !== "undefined" ? AbortController : function () {
      this.signal = { aborted: false }; var self = this;
      this.abort = function () { self.signal.aborted = true; };
    })();
    runnerAbortSignal = false;
    runnerPump();
  } else {
    runnerSetState("idle");
  }
}

function startBatch(names) {
    if (!names || !names.length) {
      names = files.filter(function (f) { return f.status !== "done"; }).map(function (f) { return f.name; });
    }
    runnerStart(names);
  }

function clearAllFiles() {
    if (runnerState !== "idle") {
      logWarn("Cannot clear while runner is " + runnerState);
      return;
    }
    var names = files.map(function (f) { return f.name; });
    names.forEach(function (n) { dbDelete(n).catch(function () {}); });
    files = [];
    selectedName = null;
    renderFileList();
    log("info", "Cleared all files");
  }

  // Reset runner + UI state without removing files from the list.
 function resetAppState() {
   // Real reset: abort any running batch, clear logs, reset stats and file
   // statuses to pending, drop preset selection back to Unsaved. Files PERSIST.
   if (runnerAbortCtrl && !runnerAbortSignal) {
    if (typeof runnerAbortCtrl.abort === "function") runnerAbortCtrl.abort();
    runnerAbortSignal = true;
    logWarn("Reset: runner aborted");
  }
  runnerQueue = [];
  runnerCurrent = null;
  runnerBatchStartTs = 0;
  runnerFileStartTs = 0;
  runnerFileDurations = [];
  runnerPauseRequested = false;
  runnerCaptchaPause = false;
  files.forEach(function (f) {
    f.status = "pending";
    f.startedAt = 0;
    f.durationMs = 0;
    f.error = null;
  });
  renderFileList();
  runnerSetState("idle");
  if (presetSelect) {
    currentPresetName = "";
    presetSelect.value = "";
    setPresetState("idle");
  }
  if (typeof logs !== "undefined") {
    logs.length = 0;
  }
  if (typeof renderLogs === "function") renderLogs();
  updateRunnerUI();
  updateReadyLine();
  log("info", "App reset (files kept, logs cleared, runner cleared)");
}

function doReset() {
  // Alias kept so older callers still work; just delegates.
  resetAppState();
}

  function setupControls() {
    if (btnStartProcess) {
      btnStartProcess.onclick = function () {
        var s = runnerState;
        if (s === "running") { runnerPause(); return; }
        if (s === "paused" || s === "captcha") { runnerResume(); return; }
        var names = files.filter(function (f) { return f.status !== "done"; }).map(function (f) { return f.name; });
        if (!names.length) {
          logWarn("Start ignored: no files in queue");
          return;
        }
        log("info", "Starting batch: " + names.length + " file(s)");
        startBatch(names);
      };
    }
    if (btnStopProcess) {
      btnStopProcess.onclick = function () {
        if (btnStopProcess.disabled) return;
        runnerStop();
      };
    }
    if (btnClearAll) {
      btnClearAll.onclick = function () { clearAllFiles(); };
    }
    if (btnResetApp) {
      btnResetApp.onclick = function () { resetAppState(); };
    }
    updateControlUI();
    setInterval(function () {
      if (runnerState === "running" || runnerState === "paused" || runnerState === "captcha") {
        renderFileList();
      }
    }, 1000);
  }

  function setupTabs() {
    var tabs = document.querySelectorAll(".tab");
    var panels = document.querySelectorAll(".tab-panel");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var name = tab.getAttribute("data-tab");
        tabs.forEach(function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
        panels.forEach(function (p) {
          p.classList.toggle("active", p.getAttribute("data-panel") === name);
        });
      });
    });
  }

  // --------------------------------------------------------------------------
  // Realtime two-way mirror with the vectorizer.ai result page
  // --------------------------------------------------------------------------
  function pushSettingsToPage(root) {
    var data = collectSettings(root);
    // delayMs / delayJitterMs are runner-internal timing controls, not
    // page settings. Strip them so the page doesn't see fields it doesn't
    // know about.
    delete data.delayMs;
    delete data.delayJitterMs;
    log("mirror", "ext -> page push (" + Object.keys(data).length + " fields)");
    try {
      chrome.runtime.sendMessage({ type: "VECTOR_ASSIST_APPLY_SETTINGS", settings: data }, function () {
        if (chrome.runtime && chrome.runtime.lastError) {}
      });
    } catch (e) {
      logError("pushSettingsToPage: sendMessage failed — " + e);
    }
  }

  function reflectPageToExtension(root, pageSettings) {
    if (!pageSettings) return;
    applyingFromPage = true;
    Object.keys(pageSettings).forEach(function (name) {
      var val = pageSettings[name];
      var els = root.querySelectorAll('[name="' + name + '"]');
      els.forEach(function (el) {
        if (el.type === "radio") {
          if (el.value === val) el.checked = true;
        } else if (el.type === "checkbox") {
          el.checked = !!val;
        } else {
          el.value = val;
        }
      });
    });
    if (pageSettings.scalePercent) setScalePercent(root, pageSettings.scalePercent);
    applySettingsRules(root);
    saveSettings(root);
    setTimeout(function () {
      applyingFromPage = false;
      // Only re-evaluate preset status if this reflection is NOT an echo of
      // our own push. setupMirror already filters PAGE_CHANGED while
      // applyingToPage is true, but a few may slip through; this guard
      // prevents a freshly-loaded preset from immediately dropping to Unsaved.
      if (!applyingToPage) {
        updatePresetStatus();
      }
    }, 200);
  }

  function pullPageSettings() {
    log("mirror", "Requesting settings from page");
    try {
      chrome.runtime.sendMessage({ type: "VECTOR_ASSIST_GET_SETTINGS" }, function (resp) {
        if (chrome.runtime && chrome.runtime.lastError) { return; }
        if (resp && resp.settings) {
          log("mirror", "Page settings received (" + Object.keys(resp.settings).length + " fields)");
          reflectPageToExtension(document.querySelector(".settings"), resp.settings);
        } else {
          log("mirror", "No settings returned by page");
        }
      });
    } catch (e) {
      logError("pullPageSettings: " + e);
    }
  }

  // One-way mirror: extension edits push to page, page edits are NOT mirrored
  // back to the extension. The user is free to tweak settings on the web
  // directly; the runner re-applies the saved preset from the extension
  // state right before clicking Submit, so the page is always in sync with
  // the picked preset at the moment of download.
  function setupMirror() {
    // PAGE_CHANGED events from the page are intentionally ignored now
    // (one-way). We don't need a listener at all, but keep the function
    // for symmetry with other setup steps.
  }

  // --------------------------------------------------------------------------
  // Settings tab (GUI clone of Vectorizer.AI output options)
  // --------------------------------------------------------------------------
  function setupSettings() {
    var settingsRoot = document.querySelector(".settings");
    if (!settingsRoot) return;

    // Scale quick-buttons (1:1 with page's literal buttons, not a dropdown).
    var scaleWrap = settingsRoot.querySelector('[data-opt="scalePercent"]');
    if (scaleWrap) {
      var scaleBtns = scaleWrap.querySelectorAll(".set-scale-btn");
      scaleBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
          if (applyingFromPage) return;
          scaleBtns.forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
          settingsRoot.dataset.scalePercent = btn.getAttribute("data-scale");
          applySettingsRules(settingsRoot);
          saveSettings(settingsRoot);
          pushSettingsToPage(settingsRoot);
        });
      });
    }

    settingsRoot.addEventListener("change", function () {
      if (applyingFromPage) return; // don't echo page-originated updates
      applySettingsRules(settingsRoot);
      saveSettings(settingsRoot);
      pushSettingsToPage(settingsRoot);
      updateReadyLine();
    });

    var delayEl = settingsRoot.querySelector('[name="delayMs"]');
    var jitterEl = settingsRoot.querySelector('[name="delayJitterMs"]');
    if (delayEl) delayEl.addEventListener("input", updateReadyLine);
    if (jitterEl) jitterEl.addEventListener("input", updateReadyLine);

    if (!settingsRoot.dataset.scalePercent) settingsRoot.dataset.scalePercent = "400";

    loadSettings(settingsRoot).then(function () {
      applySettingsRules(settingsRoot);
    });
  }

  function getScalePercent(root) {
    return root.dataset.scalePercent || null;
  }

  function setScalePercent(root, percent) {
    var wrap = root.querySelector('[data-opt="scalePercent"]');
    if (!wrap) return;
    var btns = wrap.querySelectorAll(".set-scale-btn");
    var matched = null;
    btns.forEach(function (b) {
      if (b.getAttribute("data-scale") === String(percent)) matched = b;
    });
    btns.forEach(function (b) { b.classList.remove("active"); });
    if (matched) matched.classList.add("active");
    root.dataset.scalePercent = matched ? String(percent) : (percent || "");
  }

  // Mirror Vectorizer.AI: enable/disable + show/hide options per selected format,
  // draw style, and output size.
  function applySettingsRules(root) {
    var format = getRadioValue(root, "format") || "svg";
    var drawStyle = getRadioValue(root, "drawStyle") || "filled";
    var outputSize = getRadioValue(root, "outputSize") || "unchanged";

    // Format-specific groups (SVG version / DXF compat).
    root.querySelectorAll("[data-show]").forEach(function (el) {
      el.hidden = el.getAttribute("data-show") !== format;
    });

    // Output-size dependent field grids (custom / scaled).
    root.querySelectorAll("[data-show-size]").forEach(function (el) {
      el.hidden = el.getAttribute("data-show-size") !== outputSize;
    });

    // "If shapes differ / H / V / DPI" only show in Custom mode when at
    // least one dimension is NOT Auto (matches the page's literal Auto toggle).
    var aw = root.querySelector('[name="widthAuto"]');
    var ah = root.querySelector('[name="heightAuto"]');
    var autoW = aw ? aw.checked : true;
    var autoH = ah ? ah.checked : true;
    root.querySelectorAll("[data-show-no-auto]").forEach(function (el) {
      el.hidden = outputSize !== "custom" || (autoW && autoH);
    });

    // --- Group By ---
    // SVG: full. DXF: layers (all allowed). EPS/PDF: no grouping. PNG: raster.
    // Stroked edges: Group By is meaningless (edges are stroked once).
    // Preserve value when disabled; page doesn't render Group By in disabled modes.
    var groupSupported = (format === "svg" || format === "dxf") && drawStyle !== "strokedEdge";
    setGroupEnabled(root, "groupBy", groupSupported);

// --- Simple Shapes ---
     // Disabled when draw style is stroked edges. Preserve checkbox value
     // (don't force uncheck) so it round-trips when switching back.
     setCheckEnabled(root, "simpleShapes", drawStyle !== "strokedEdge");
 
     // --- Gap Filler ---
     // Disabled when draw style is stroked outlines (lines only, no shapes to fill).
     setGroupEnabled(root, "gapFiller", drawStyle !== "strokedOutline");

    // --- Shape Stacking ---
    // The page disables Shape Stacking when draw style is stroked edges
    // because edge-stroking renders stacking meaningless (every edge is
    // stroked exactly once regardless of stacking mode).
    var stackingEnabled = (drawStyle !== "strokedEdge");
    setGroupEnabled(root, "stacking", stackingEnabled);
    if (!stackingEnabled) forceRadio(root, "stacking", "cutouts");

    // --- Allowed Curve Types ---
    // EPS/PDF: only Cubic Bézier (+ implicit Lines). SVG/DXF/PNG: all types.
    // (The page has no explicit "Lines" toggle, so we omit it to stay 1:1.)
    var restrictedCurves = (format === "eps" || format === "pdf");
    setCheckEnabled(root, "curveCubic", true);   // supported by all formats
    setCheckEnabled(root, "curveQuad", !restrictedCurves);
    setCheckEnabled(root, "curveCirc", !restrictedCurves);
    setCheckEnabled(root, "curveEllip", !restrictedCurves);
    if (restrictedCurves) {
      forceCheck(root, "curveQuad", false);
      forceCheck(root, "curveCirc", false);
      forceCheck(root, "curveEllip", false);
    }

    // --- Stroke Style ---
    // The page keeps Stroke Style always visible (with a note that it only
    // applies when the draw style strokes outlines/edges). Mirror that 1:1:
    // always enabled, do not disable.
    setGroupEnabled(root, "strokeStyle", true);
  }

  function setGroupEnabled(root, groupName, enabled) {
    var group = root.querySelector('[data-group="' + groupName + '"]');
    if (!group) return;
    group.classList.toggle("disabled", !enabled);
    group.querySelectorAll("input, select").forEach(function (el) {
      el.disabled = !enabled;
    });
    group.querySelectorAll(".set-opt, .set-check, .set-field").forEach(function (el) {
      el.classList.toggle("disabled", !enabled);
    });
  }

  function setCheckEnabled(root, name, enabled) {
    var el = root.querySelector('input[name="' + name + '"]');
    if (!el) return;
    el.disabled = !enabled;
    var label = el.closest(".set-check");
    if (label) label.classList.toggle("disabled", !enabled);
  }

  function forceRadio(root, name, value) {
    var el = root.querySelector('input[name="' + name + '"][value="' + value + '"]');
    if (el && !el.checked) el.checked = true;
  }

  function forceCheck(root, name, checked) {
    var el = root.querySelector('input[name="' + name + '"]');
    if (el) el.checked = checked;
  }

  function getRadioValue(root, name) {
    var checked = root.querySelector('input[name="' + name + '"]:checked');
    return checked ? checked.value : null;
  }

  function collectSettings(root) {
    var data = {};
    var inputs = root.querySelectorAll("input, select");
    inputs.forEach(function (el) {
      if (!el.name) return;
      if (el.type === "radio") {
        if (el.checked) data[el.name] = el.value;
      } else if (el.type === "checkbox") {
        data[el.name] = el.checked;
      } else {
        data[el.name] = el.value;
      }
    });
    var sp = getScalePercent(root);
    if (sp) data.scalePercent = sp;
    return data;
  }

  function saveSettings(root) {
    try {
      var data = collectSettings(root);
      if (chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ vectorAssistSettings: data });
      }
    } catch (e) {}
  }

  function loadSettings(root) {
    return new Promise(function (resolve) {
      try {
        if (!chrome.storage || !chrome.storage.local) { resolve(); return; }
        chrome.storage.local.get(["vectorAssistSettings"], function (res) {
          var data = res && res.vectorAssistSettings;
          if (!data) { resolve(); return; }
          log("info", "Restored " + Object.keys(data).length + " saved settings");
          if (data.scalePercent) setScalePercent(root, data.scalePercent);
          Object.keys(data).forEach(function (name) {
            var val = data[name];
            var els = root.querySelectorAll('[name="' + name + '"]');
            els.forEach(function (el) {
              if (el.type === "radio") {
                el.checked = (el.value === val);
              } else if (el.type === "checkbox") {
                el.checked = !!val;
              } else {
                el.value = val;
              }
            });
          });
          resolve();
        });
      } catch (e) { resolve(); }
    });
  }

  function setupTabMonitoring() {
    chrome.tabs.onActivated.addListener(function () { initView(); });
    chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
      if (changeInfo.status === "complete" || changeInfo.url) { if (tab && tab.active) initView(); }
    });
    if (chrome.windows && chrome.windows.onFocusChanged) {
      chrome.windows.onFocusChanged.addListener(function () { initView(); });
    }
  }

  // --------------------------------------------------------------------------
  // Runner UI helpers
  // --------------------------------------------------------------------------
  var rsElapsed, rsEta, rsDone, rsNow, rsCaptcha;
  var fileProgressPercentEl, fileProgressFillEl, overallProgressPercentEl, overallProgressFillEl;
  var fileCountdownEl;
  var fileProgressPhaseEls = {};
  function setupRunner() {
    rsElapsed = document.getElementById("rsElapsed");
    rsEta = document.getElementById("rsEta");
    rsDone = document.getElementById("rsDone");
    rsNow = document.getElementById("rsNow");
    rsCaptcha = document.getElementById("rsCaptcha");
    fileProgressPercentEl = document.getElementById("fileProgressPercent");
    fileProgressFillEl = document.getElementById("fileProgressFill");
    overallProgressPercentEl = document.getElementById("overallProgressPercent");
    overallProgressFillEl = document.getElementById("overallProgressFill");
    var phases = document.querySelectorAll("#fileProgressPhases .phase");
    phases.forEach(function (el) {
      fileProgressPhaseEls[el.getAttribute("data-phase")] = el;
    });
    startRunnerProgressPolling();
    setInterval(function () {
      if (runnerState === "idle") return;
      var done = files.filter(function (f) { return f.status === "done"; }).length;
      var total = files.length;
      if (rsDone) rsDone.textContent = done + "/" + total;
      if (rsNow) {
        var label = runnerState.charAt(0).toUpperCase() + runnerState.slice(1);
        if (runnerCurrent) label += " — " + runnerCurrent;
        rsNow.textContent = label;
      }
      if (rsElapsed) {
        var startTs = runnerCurrent ? runnerFileStartTs : runnerBatchStartTs;
        if (startTs) {
          var sec = Math.max(0, Math.floor((Date.now() - startTs) / 1000));
          rsElapsed.textContent = formatHMS(sec);
        }
      }
      if (rsEta) {
        rsEta.textContent = computeETA();
      }
      if (rsCaptcha) rsCaptcha.classList.toggle("hidden", runnerState !== "captcha");
    }, 500);
  }

  function computeETA() {
    if (!runnerFileDurations.length) return "—";
    var avg = runnerFileDurations.reduce(function (a, b) { return a + b; }, 0) / runnerFileDurations.length;
    var remaining = runnerQueue.length + (runnerCurrent ? 1 : 0);
    if (!remaining) return "done";
    var sec = Math.round((avg * remaining) / 1000);
    return formatHMS(sec);
  }

  function updateRunnerUI() {
    if (typeof updateControlUI === "function") updateControlUI();
  }

  function updateRunnerProgressUI(p) {
    if (!p) return;
    var pg = p.progress || {};
    var u = pg.upload || 0, pr = pg.process || 0, f = pg.fetch || 0;
    var overall = Math.round((u + pr + f) / 3);
    if (fileProgressFillEl) fileProgressFillEl.style.width = overall + "%";
    if (fileProgressPercentEl) fileProgressPercentEl.textContent = overall + "%";
    if (overallProgressFillEl) {
      var total = files.length || 1;
      var done = files.filter(function (f) { return f.status === "done"; }).length;
      var pct = Math.round((done / total) * 100);
      overallProgressFillEl.style.width = pct + "%";
      if (overallProgressPercentEl) overallProgressPercentEl.textContent = pct + "%";
    }
    Object.keys(fileProgressPhaseEls).forEach(function (k) {
      var el = fileProgressPhaseEls[k];
      if (!el) return;
      var v = pg[k] || 0;
      el.querySelector("em").textContent = Math.round(v) + "%";
      el.classList.toggle("done", v >= 100);
      el.classList.toggle("active", v > 0 && v < 100);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    landingPage = document.getElementById("landingPage");
    mainInterface = document.getElementById("mainInterface");
    btnOpenSite = document.getElementById("btnOpenSite");
    btnStartProcess = document.getElementById("btnStartProcess");
    btnStopProcess = document.getElementById("btnStopProcess");
    btnClearAll = document.getElementById("btnClearAll");
    btnResetApp = document.getElementById("btnResetApp");
    dndZone = document.getElementById("dndZone");
    fileInput = document.getElementById("fileInput");
    folderInput = document.getElementById("folderInput");
    btnSelectFiles = document.getElementById("btnSelectFiles");
    btnSelectFolder = document.getElementById("btnSelectFolder");
    fileTableBody = document.getElementById("fileTableBody");
    emptyState = document.getElementById("emptyState");
    fileCountdownEl = document.getElementById("fileCountdown");
    statLoaded = document.getElementById("statLoaded");
    statPending = document.getElementById("statPending");
    statFinished = document.getElementById("statFinished");
    statFailed = document.getElementById("statFailed");

    try {
      fetch("manifest.json").then(function (r) {
        if (r.ok) r.json().then(function (m) {
          var v = document.getElementById("extensionVersion");
          if (v && m.version) v.textContent = "v" + m.version;
          var lv = document.getElementById("landingVersion");
          if (lv && m.version) lv.textContent = "v" + m.version;
        });
      }).catch(function () {});
    } catch (e) {}

    if (btnOpenSite) btnOpenSite.onclick = openSite;

    var btnHelp = document.getElementById("btnHelp");
    var helpModal = document.getElementById("helpModal");
    var btnCloseHelp = document.getElementById("btnCloseHelp");
    if (btnHelp && helpModal) {
      btnHelp.onclick = function () { helpModal.classList.remove("hidden"); };
      if (btnCloseHelp) btnCloseHelp.onclick = function () { helpModal.classList.add("hidden"); };
      helpModal.addEventListener("click", function (e) {
        if (e.target === helpModal) helpModal.classList.add("hidden");
      });
    }

    setupControls();
    setupTabs();
    setupDnD();
    setupLogs();
    setupSettings();
    setupPresets();
    setupMirror();
    setupRunner();
    setupPagePhaseListener();
    setupDownloadListener();
    renderFileList();
    updateReadyLine();
    setupTabMonitoring();
    initView();

    logInfo("Vector Assist initialized");

    // Push saved settings to page so extension always overrides the web.
    var root = document.querySelector(".settings");
    if (root) pushSettingsToPage(root);

    dbGetAll().then(function (records) {
      if (records && records.length) {
        files = records;
        renderFileList();
        log("info", "Restored " + records.length + " file(s) from IndexedDB");
      }
    }).catch(function (e) {
      logError("Failed to read IndexedDB: " + e);
    });
  });

// --------------------------------------------------------------------------
// Runner: batch/single file automation against vectorizer.ai.
//
// State machine per file:
//   queued -> uploading -> (progress) -> processing -> awaiting-captcha?
//     -> applying-preset -> ready-to-download -> downloading -> done | failed
//
// Pause / resume are honored at step boundaries (between delay waits).
// Captcha pauses until user clicks Resume; runner does not auto-solve.
// --------------------------------------------------------------------------
var runnerState = "idle";  // "idle" | "running" | "paused" | "captcha"
var runnerPauseRequested = false;
var runnerCaptchaPause = false;
var runnerQueue = [];      // array of file names in order
var runnerCurrent = null;  // file currently being processed (name)
var runnerBatchStartTs = 0;
var runnerFileStartTs = 0;
// Live countdown target (ms epoch). While this is in the future, the file
// row shows "waiting Ns…" instead of "elapsed".
var runnerCountdownTarget = 0;
var runnerFileDurations = []; // ms duration of completed files (for ETA)
var runnerProgressTick = null;
var runnerStepWait = null;   // {id, resolve, reject} for current wait; cancel on pause.

function runnerSetState(s) {
  runnerState = s;
  if (typeof updateRunnerUI === "function") updateRunnerUI();
}

function runnerCancelWait(reason) {
  // Clear the current wait, if any. If a Promise is stored, resolve it
  // with a "paused" marker so the awaiting code can fall through into
  // runnerGate (which will then block until the user resumes).
  if (runnerStepWait) {
    if (runnerStepWait.id) clearTimeout(runnerStepWait.id);
    if (typeof runnerStepWait.resolve === "function") {
      runnerStepWait.resolve(reason || "cancelled");
    }
    runnerStepWait = null;
  }
  // Drop the live countdown so the tick doesn't keep rendering a stale
  // target. The tick will fall back to the current phase label.
  runnerCountdownTarget = 0;
}

// Wait with delay+jitter. Promise resolves when wait completes, or rejects if cancelled.
function runnerSleep(baseMs, jitterMs, label) {
  return new Promise(function (resolve, reject) {
    if (runnerAbortSignal) { reject(new Error("STOPPED")); return; }
    var b = parseInt(baseMs, 10); if (!isFinite(b) || b < 0) b = 0;
    var j = parseInt(jitterMs, 10); if (!isFinite(j) || j < 0) j = 0;
    var wait = b + (j > 0 ? Math.floor(Math.random() * j) : 0);
    // If user wants zero delay, resolve immediately so we don't block.
    if (wait <= 0) { resolve(); return; }
    runnerCountdownTarget = Date.now() + wait;
    runnerCountdownLabel = label || "Waiting";
    ensureRunnerTick();
    var cancelled = false;
    var id = setTimeout(function () {
      if (runnerStepWait && runnerStepWait.id === id) runnerStepWait = null;
      if (runnerAbortSignal && !cancelled) { reject(new Error("STOPPED")); return; }
      resolve();
    }, wait);
    runnerStepWait = { id: id, resolve: function (reason) {
      cancelled = true;
      clearTimeout(id);
      if (runnerStepWait && runnerStepWait.id === id) runnerStepWait = null;
      // Resume path: the next runnerGate() will block until pause lifts.
      resolve(reason);
    }, reject: reject };
  });
}

// Live tick: every 250ms update the compact status line + file rows.
var runnerTickHandle = null;
var runnerCountdownLabel = "";
// When there's no active countdown, fall back to this label so the user
// always sees something meaningful (e.g. "Uploading", "Vectorizing").
var runnerPhaseLabel = "";
function ensureRunnerTick() {
  if (runnerTickHandle) return;
  runnerTickHandle = setInterval(function () {
    if (runnerState !== "running" && runnerState !== "paused" && runnerState !== "captcha") {
      clearInterval(runnerTickHandle);
      runnerTickHandle = null;
      runnerCountdownTarget = 0;
      runnerCountdownLabel = "";
      runnerPhaseLabel = "";
      updateReadyLine();
      renderFileList();
      return;
    }
    // Update the compact status line (label stays, value updates).
    if (fileCountdownEl) {
      if (runnerCountdownTarget && runnerCountdownTarget > Date.now()) {
        var remaining = Math.max(0, Math.ceil((runnerCountdownTarget - Date.now()) / 1000));
        fileCountdownEl.classList.add("waiting");
        fileCountdownEl.innerHTML = runnerCountdownLabel +
          ' <span class="cd-time">' + remaining + 's</span>';
      } else if (runnerCountdownTarget) {
        fileCountdownEl.classList.add("waiting");
        fileCountdownEl.innerHTML = runnerCountdownLabel +
          ' <span class="cd-time">…</span>';
      } else if (runnerPhaseLabel) {
        fileCountdownEl.classList.remove("waiting");
        fileCountdownEl.textContent = runnerPhaseLabel;
      } else {
        fileCountdownEl.classList.remove("waiting");
        fileCountdownEl.textContent = "Running";
      }
    }
    if (typeof renderFileList === "function") renderFileList();
  }, 250);
}

function runnerIsPauseRequested() {
  return runnerPauseRequested || runnerCaptchaPause;
}

async function runnerGate() {
  // Awaits while pause / captcha is in effect. Throws on stop.
  while (runnerPauseRequested && !runnerAbortSignal) {
    runnerSetState("paused");
    await new Promise(function (r) { setTimeout(r, 200); });
  }
  if (runnerAbortSignal) throw new Error("STOPPED");
  while (runnerCaptchaPause) {
    runnerSetState("captcha");
    await new Promise(function (r) { setTimeout(r, 300); });
  }
  if (runnerAbortSignal) throw new Error("STOPPED");
}

function updateReadyLine() {
  // Render the compact status line in idle mode. Show what's actually
  // armed: selected preset name, per-field delay, and per-file cooldown.
  if (!fileCountdownEl) return;
  var t = runnerGetTiming();
  var presetName = (presetSelect && presetSelect.value) || "";
  var delay = (t.delay || 0) + "+" + (t.jitter || 0);
  var parts = [];
  if (presetName) parts.push("preset: " + presetName);
  else parts.push("preset: none");
  parts.push("delay: " + delay + "ms");
  fileCountdownEl.classList.remove("waiting");
  fileCountdownEl.textContent = "Ready · " + parts.join(" · ");
}

function runnerGetTiming() {
  var root = document.querySelector(".settings");
  var base = parseInt(root && root.querySelector('[name="delayMs"]') && root.querySelector('[name="delayMs"]').value, 10);
  var jit  = parseInt(root && root.querySelector('[name="delayJitterMs"]') && root.querySelector('[name="delayJitterMs"]').value, 10);
  if (!isFinite(base) || base < 0) base = 0;
  if (!isFinite(jit) || jit < 0) jit = 0;
  return { delay: base, jitter: jit };
}

function runnerGetPreset(name) {
  return new Promise(function (resolve) {
    if (!name) { resolve(null); return; }
    getPresets().then(function (list) {
      var p = list.filter(function (x) { return x.name === name; })[0];
      resolve(p || null);
    });
  });
}

// Push a preset to the page and resolve immediately. No artificial wait —
// applyToPage in content.js is synchronous-per-field (literal clicks); the
// runner clicks Submit right after this returns, which is what a human
// would do. We don't poll, don't countdown, don't block.
function runnerApplyPreset(preset, timing) {
  return new Promise(function (resolve, reject) {
    if (!preset) { resolve(); return; }
    var settings = Object.assign({}, preset.settings || {});
    // delayMs / delayJitterMs are runner-internal timing controls.
    delete settings.delayMs;
    delete settings.delayJitterMs;
    chrome.runtime.sendMessage(
      { type: "VECTOR_ASSIST_APPLY_SETTINGS", settings: settings },
      function () { if (chrome.runtime && chrome.runtime.lastError) {} }
    );
    log("preset", "Applied preset '" + preset.name + "' (" + Object.keys(settings).length + " fields)");
    resolve();
  });
}

// --------------------------------------------------------------------------
// Page phase beacon: content.js on the active tab reports its URL + readiness.
// We track the most recent phase so the runner can wait for a fresh content
// script to come online after a navigation.
// --------------------------------------------------------------------------
// Download-complete coordination. background.js uses chrome.downloads to
// detect when a file has actually been written to disk (which is what we
// really care about — not the page's progress bar). The runner awaits a
// DOWNLOAD_COMPLETE event after it has clicked Submit.
// --------------------------------------------------------------------------
var downloadCompleteWaiters = [];

function setupDownloadListener() {
  if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.onMessage) return;
  chrome.runtime.onMessage.addListener(function (msg) {
    if (!msg) return;
    if (msg.type === "VECTOR_ASSIST_DOWNLOAD_STARTED") {
      log("info", "  download started (" + (msg.filename || msg.url || "?") + ")");
      return;
    }
    if (msg.type === "VECTOR_ASSIST_DOWNLOAD_COMPLETE") {
      var payload = msg;
      log("info", "  download complete: " + (payload.filename || "?") +
        " (" + (payload.bytesReceived || 0) + " bytes)");
      var stale = downloadCompleteWaiters;
      downloadCompleteWaiters = [];
      stale.forEach(function (fn) { try { fn(payload); } catch (e) {} });
    }
  });
}

function whenDownloadComplete(timeoutMs) {
  return new Promise(function (resolve) {
    var done = false;
    function finish(payload) {
      if (done) return;
      done = true;
      clearTimeout(timer);
      downloadCompleteWaiters = downloadCompleteWaiters.filter(function (fn) { return fn !== listener; });
      resolve(payload || null);
    }
    var listener = function (payload) { finish(payload); };
    downloadCompleteWaiters.push(listener);
    var timer = setTimeout(function () { finish(null); }, timeoutMs);
  });
}

var lastPagePhase = { pathname: "", ready: false, ts: 0, tabId: null };
var pagePhaseListeners = [];

function setupPagePhaseListener() {
  if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.onMessage) return;
  chrome.runtime.onMessage.addListener(function (msg) {
    if (!msg || msg.type !== "VECTOR_ASSIST_PAGE_PHASE") return;
    lastPagePhase = {
      pathname: msg.pathname || "",
      ready: !!msg.ready,
      ts: msg.ts || Date.now(),
      tabId: msg.tabId
    };
    var stale = pagePhaseListeners;
    pagePhaseListeners = [];
    stale.forEach(function (fn) { try { fn(lastPagePhase); } catch (e) {} });
  });
}

function whenPagePhaseMatches(predicate, timeoutMs) {
  // Resolves with the phase payload if predicate(pathname|ready) becomes true
  // within timeoutMs; resolves with null on timeout.
  return new Promise(function (resolve) {
    if (predicate(lastPagePhase)) { resolve(lastPagePhase); return; }
    var timer = setTimeout(function () {
      // pop ourselves out of listeners
      pagePhaseListeners = pagePhaseListeners.filter(function (fn) { return fn !== listener; });
      resolve(null);
    }, timeoutMs);
    var listener = function (p) {
      if (predicate(p)) {
        clearTimeout(timer);
        pagePhaseListeners = pagePhaseListeners.filter(function (fn) { return fn !== listener; });
        resolve(p);
      }
    };
    pagePhaseListeners.push(listener);
  });
}

function runnerSend(type, payload) {
  return new Promise(function (resolve) {
    var tries = 0;
    function attempt() {
      if (runnerAbortSignal) { resolve({ ok: false, error: "stopped" }); return; }
      tries++;
      try {
        chrome.runtime.sendMessage(Object.assign({ type: type }, payload || {}), function (resp) {
          var err = chrome.runtime && chrome.runtime.lastError;
          if (err) {
            resolve({ ok: false, error: err.message || "send failed" });
            return;
          }
          resolve(resp || { ok: false, error: "No response" });
        });
      } catch (e) { resolve({ ok: false, error: String(e) }); }
    }
    attempt();
  });
}

async function runnerProcessFile(name) {
  var file = files.filter(function (f) { return f.name === name; })[0];
  if (!file) throw new Error("File not found: " + name);

  runnerFileStartTs = Date.now();
  runnerCurrent = name;
  file.status = "pending";
  renderFileList();
  log("info", "▶ " + name + ": starting");
  updateRunnerUI();

  // Helper: set status + log + render.
  function setStatus(status, label) {
    file.status = status;
    file.statusLabel = label;
    // Mirror phase to the global status line so the tick has a label even
    // when no countdown is active.
    runnerPhaseLabel = label || status;
    ensureRunnerTick();
    renderFileList();
  }

  var ensured = await new Promise(function (resolve) {
    try {
      chrome.runtime.sendMessage({ type: "VECTOR_ASSIST_ENSURE_SITE" }, function (resp) {
        if (chrome.runtime && chrome.runtime.lastError) { resolve({ ok: false }); return; }
        resolve(resp || { ok: false });
      });
    } catch (e) { resolve({ ok: false }); }
  });
  if (!ensured || !ensured.ok) {
    setStatus("failed", "Failed: no site");
    logError(name + ": cannot open vectorizer.ai");
    throw new Error("No vectorizer tab and cannot open one");
  }
  if (!ensured.alreadyOpen) {
    log("info", name + ": opened https://vectorizer.ai/ (waiting for it to load)");
    var ready = false;
    var readyStart = Date.now();
    while (Date.now() - readyStart < 30000) {
      if (runnerAbortSignal) throw new Error("STOPPED");
      var info = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
      if (info && info.pathname === "/") { ready = true; break; }
      await new Promise(function (r) { setTimeout(r, 400); });
    }
    if (!ready) {
      logWarn(name + ": home page didn't fully load yet, proceeding anyway");
    }
  }

  var timing = runnerGetTiming();

  // 1) Always start from the home page. If the previous run left us on
  //    /images/{id} or /edit, the page would still hold that id and our
  //    upload would either be ignored or overwrite the wrong session.
  //    Navigate to /, then proceed to upload.
  setStatus("redirecting", "Opening home");
  var reImagesAny = /^\/images\//;
  var initialInfo = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
  if (initialInfo && initialInfo.pathname && reImagesAny.test(initialInfo.pathname)) {
    log("info", name + ": previous run left us on " + initialInfo.pathname + " → going home");
    await runnerSend("VECTOR_ASSIST_NAVIGATE", { url: "https://vectorizer.ai/" });
    var navStart = Date.now();
    while (Date.now() - navStart < 30000) {
      if (runnerAbortSignal) throw new Error("STOPPED");
      var i = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
      if (i && i.pathname === "/") break;
      await new Promise(function (r) { setTimeout(r, 350); });
    }
  }

  // 2) UPLOAD
  var pageInfo = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
  log("info", name + ": on " + (pageInfo.pathname || "/"));

  if (!pageInfo.imageId) {
    setStatus("uploading", "Uploading");
    var up = await runnerSend("VECTOR_ASSIST_UPLOAD_FILE", { dataUrl: file.dataUrl, name: file.name });
    if (!up || !up.ok) {
      logWarn(name + ": upload failed — " + (up && up.error) + ", reloading page");
      for (var retry = 0; retry < 3; retry++) {
        setStatus("redirecting", "Reloading (" + (retry + 1) + "/3)");
        await runnerSend("VECTOR_ASSIST_NAVIGATE", { url: "https://vectorizer.ai/" });
        var reloadStart = Date.now();
        while (Date.now() - reloadStart < 30000) {
          if (runnerAbortSignal) throw new Error("STOPPED");
          var ri = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
          if (ri && ri.pathname === "/") break;
          await new Promise(function (r) { setTimeout(r, 400); });
        }
        up = await runnerSend("VECTOR_ASSIST_UPLOAD_FILE", { dataUrl: file.dataUrl, name: file.name });
        if (up && up.ok) break;
        logWarn(name + ": retry " + (retry + 1) + " failed — " + (up && up.error));
      }
    }
    if (!up || !up.ok) {
      setStatus("failed", "Failed: upload");
      logError(name + ": upload failed after retries");
      throw new Error("Upload failed: " + (up && up.error));
    }
    log("info", name + ": upload injected (" + up.fileSize + " bytes)");

    // Wait for image id (URL moves to /processing then /edit).
    setStatus("waiting-vectorize", "Vectorizing");
    log("info", name + ": waiting for image id...");
    var gotId = await runnerWaitForImageId(360000);
    if (!gotId) {
      setStatus("failed", "Failed: timeout");
      logError(name + ": timed out waiting for image id");
      throw new Error("Image id timeout");
    }
    log("info", name + ": image id = " + gotId);
    // No extra delay here — go straight to the redirect step below.
  }

  // 2) Redirect: drop /edit, go to /images/{id} (the options page).
  var reShow = /^\/images\/[^/]+\/?$/;
  var reEdit = /\/edit\/?$/;
  var currentInfo = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
  var pathNow = currentInfo.pathname || "";
  var m = pathNow.match(/\/images\/([^/]+)/);
  var imageId = currentInfo.imageId || (m && m[1]);
  if (imageId && reEdit.test(pathNow)) {
    setStatus("redirecting", "Redirecting");
    var target = "/images/" + imageId;
    log("info", name + ": → " + target);
    await runnerSend("VECTOR_ASSIST_NAVIGATE", { url: target });
    var pollStart = Date.now();
    while (Date.now() - pollStart < 30000) {
      if (runnerAbortSignal) throw new Error("STOPPED");
      await runnerGate();
      var info = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
      if (info && info.pathname && reShow.test(info.pathname)) {
        log("info", name + ": download page ready");
        break;
      }
      await new Promise(function (r) { setTimeout(r, 350); });
    }
  } else if (reShow.test(pathNow)) {
    log("info", name + ": already on download page");
  }

  // 3) APPLY PRESET. Push the preset to the page (fire-and-forget); the
  //    page-side applyToPage runs synchronously and updates all fields.
  var pickedName = (presetSelect && presetSelect.value) || "";
  if (pickedName) {
    var preset = await runnerGetPreset(pickedName);
    if (preset) {
      setStatus("applying", "Applying preset");
      log("preset", name + ": applying preset '" + preset.name + "'");
      await runnerApplyPreset(preset, timing);
      await runnerGate();
    }
  }

  // 3b) PRE-SUBMIT DELAY. Give the page time to settle on the new settings
  //     before clicking Submit. Uses the "Delay (ms)" + "Extra random delay
  //     (ms)" fields from the Settings tab. Live countdown is rendered on
  //     the compact status line. Honoured: abort -> throw STOPPED, pause
  //     -> runnerGate blocks via the existing cancel mechanism.
  var preDelay = (timing && timing.delay > 0) || (timing && timing.jitter > 0);
  if (preDelay) {
    setStatus("delaying", "Delay before submit");
    log("info", name + ": waiting " + (timing.delay || 0) + "+" + (timing.jitter || 0) + "ms before submit");
    try {
      await runnerSleep(timing.delay, timing.jitter, "Pre-submit delay");
    } catch (e) {
      throw e;
    }
    await runnerGate();
  }

  // 4) Click Download. Just click and wait for chrome.downloads to fire.
  setStatus("submitting", "Submitting");
  log("info", name + ": clicking submit...");
  var sub = await runnerSend("VECTOR_ASSIST_SUBMIT_DOWNLOAD");
  if (!sub || !sub.ok) {
    setStatus("failed", "Failed: submit");
    logError(name + ": submit failed — " + (sub && sub.error));
    throw new Error("Submit failed");
  }

  // Wait for the file to actually land in chrome.downloads.
  setStatus("downloading", "Downloading");
  log("info", name + ": waiting for download...");
  var dlPromise = whenDownloadComplete(180000);
  var dlPayload = null;
  while (!dlPayload) {
    if (runnerAbortSignal) throw new Error("STOPPED");
    var dl = await Promise.race([
      dlPromise,
      new Promise(function (r) { setTimeout(function () { r("__tick__"); }, 6000); })
    ]);
    if (dl && dl !== "__tick__") { dlPayload = dl; break; }
    var pinfo = await runnerSend("VECTOR_ASSIST_GET_PROGRESS");
    if (pinfo && pinfo.captcha) {
      logWarn(name + ": captcha detected — pausing");
      runnerCaptchaPause = true;
      runnerSetState("captcha");
      while (runnerCaptchaPause) {
        if (runnerAbortSignal) throw new Error("STOPPED");
        await new Promise(function (r) { setTimeout(r, 300); });
      }
      log("info", name + ": resumed after captcha");
    } else {
      var prog = pinfo && pinfo.progress;
      log("info", "  fetching... bar=" + (prog && prog.fetch) + ", url=" + (pinfo && pinfo.url ? pinfo.url : "?"));
    }
  }
  log("info", name + ": file saved: " + (dlPayload.filename || dlPayload.finalUrl || "?"));

  // 6) DONE.
  setStatus("done", "Done");
  runnerFileDurations.push(Date.now() - runnerFileStartTs);
  runnerCurrent = null; // stop the per-file timer for this file.
  renderFileList();
  updateRunnerUI();
  log("info", "✓ " + name + ": done in " + ((Date.now() - runnerFileStartTs) / 1000).toFixed(1) + "s");
  await runnerSleep(timing.delay, timing.jitter);
}

// Wait until content.js reports the Options-Form element exists (or its absence is acceptable).
async function runnerWaitForOptionsForm(timeoutMs) {
  var start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (runnerAbortSignal) return false;
    var p = await runnerSend("VECTOR_ASSIST_HAS_SELECTOR", { id: "Options-Form" });
    if (p && p.found) return true;
    await new Promise(function (r) { setTimeout(r, 400); });
  }
  return false;
}

async function runnerWaitForFetchComplete(timeoutMs) {
  var start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (runnerAbortSignal) return false;
    var p = await runnerSend("VECTOR_ASSIST_GET_PROGRESS");
    if (p && p.progress && p.progress.fetch >= 100) return true;
    await new Promise(function (r) { setTimeout(r, 400); });
  }
  return false;
}

async function runnerWaitForImageId(timeoutMs) {
  var start = Date.now();
  var lastLog = 0;
  while (Date.now() - start < timeoutMs) {
    if (runnerAbortSignal) return null;
    var p = await runnerSend("VECTOR_ASSIST_GET_PROGRESS");
    if (p && p.imageId) return p.imageId;
    if (p && p.errorDialog) {
      logWarn("error dialog detected, marking file failed");
      return null; // Let the caller handle the failure.
    }
    if (!p || !p.ok) {
      await new Promise(function (r) { setTimeout(r, 600); });
      continue;
    }
    if (Date.now() - lastLog > 6000) {
      log("info", "  waiting... url=" + (p && p.url ? p.url : "?") +
        " progress=" + JSON.stringify(p && p.progress));
      lastLog = Date.now();
    }
    await new Promise(function (r) { setTimeout(r, 500); });
  }
  return null;
}

async function runnerWaitForPath(re, timeoutMs) {
  var start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (runnerAbortSignal) return false;
    var p = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
    if (p && p.pathname && re.test(p.pathname)) return true;
    await new Promise(function (r) { setTimeout(r, 300); });
  }
  return false;
}

// Wait until a phase bar reaches `target` (or stays at target if it already passed).
// Resolves to true if reached, false on timeout / captcha / stop.
async function runnerWaitForProgress(phase, target, timeoutMs) {
  var start = Date.now();
  var sawPane = false;
  var lastLog = 0;
  while (Date.now() - start < timeoutMs) {
    if (runnerAbortSignal) return false;
    var p = await runnerSend("VECTOR_ASSIST_GET_PROGRESS");
    if (p && p.captcha) return false;
    if (p && p.progress && p.progress[phase] != null) {
      sawPane = true;
      if (p.progress[phase] >= target) return true;
    }
    if (Date.now() - lastLog > 6000) {
      log("info", "  waiting for " + phase + "=" + target +
        "%, now=" + (p && p.progress && p.progress[phase]) + ", url=" + (p && p.url ? p.url : "?"));
      lastLog = Date.now();
    }
    await new Promise(function (r) { setTimeout(r, 350); });
  }
  // If pane never appeared and we're already past the target path, treat as ok.
  return sawPane ? false : true;
}

async function runnerWaitForPathProgressCombo(re, phase, target, timeoutMs) {
  // Wait for path AND progress to reach target. Useful when /images/processing
  // shows the upload/process bars before redirecting to /images/{id}/edit.
  // Exit early if the URL already moved to /images/{id} (with or without /edit)
  // — the bars belong to /processing and disappear once navigation happens.
  var start = Date.now();
  var reImageId = /^\/images\/[^/]+/;
  while (Date.now() - start < timeoutMs) {
    if (runnerAbortSignal) return false;
    var p = await runnerSend("VECTOR_ASSIST_GET_PAGE_INFO");
    var pathOk = p && p.pathname && re.test(p.pathname);
    // Early bail-out: once we have an image id (regardless of /edit suffix),
    // /processing bars are gone — treat target as reached.
    if (p && p.imageId && reImageId.test(p.pathname || "")) return true;
    if (pathOk) {
      var g = await runnerSend("VECTOR_ASSIST_GET_PROGRESS");
      if (g && g.progress && g.progress[phase] != null && g.progress[phase] >= target) return true;
    }
    await new Promise(function (r) { setTimeout(r, 350); });
  }
  return false;
}

// Duplicate declaration of runnerWaitForProgress removed below — the version
// above (with sawPane + captcha short-circuit) is the canonical one.
var runnerAbortSignal = false;

function runnerStart(names, options) {
  options = options || {};
  if (!names || !names.length) {
    logWarn("Start ignored: no files selected");
    return;
  }
  if (runnerAbortCtrl && !runnerAbortCtrl.signal.aborted) {
    logWarn("Start ignored: runner already active");
    return;
  }
  runnerAbortCtrl = new (typeof AbortController !== "undefined" ? AbortController : function () {
    this.signal = { aborted: false }; var self = this;
    this.abort = function () { self.signal.aborted = true; };
  })();
  runnerAbortSignal = false;
  runnerPauseRequested = false;
  runnerCaptchaPause = false;
  runnerQueue = names.slice();
  runnerBatchStartTs = Date.now();
  runnerFileDurations = [];
  runnerSetState("running");
  runnerPump();
}

async function runnerPump() {
  while (runnerQueue.length) {
    if (runnerAbortSignal) break;
    var name = runnerQueue[0];
    try {
      await runnerGate();
      await runnerProcessFile(name);
    } catch (e) {
      if (String(e && e.message) === "STOPPED") break;
    }
    // Inter-file cooldown: ONLY for batch runs (queue > 1). Single-file /
    // manual runs skip this — user shouldn't have to wait between manual
    // clicks. Cooldown is short anyway (0–3s) when it does apply.
    var isBatch = runnerQueue.length > 1;
    if (!runnerAbortSignal && isBatch) {
      log("info", name + ": ✓ done. Cooling 0–3s before next...");
      try {
        await runnerSleep(1500, 1500, "Next file in"); // 1.5s ± 1.5s
      } catch (e) { break; }
    }
    runnerQueue.shift();
    runnerCurrent = null;
    updateRunnerUI();
  }
  runnerCurrent = null;
  runnerAbortSignal = false;
  runnerAbortCtrl = null;
  runnerSetState("idle");
  updateRunnerUI();
  updateReadyLine();
  if (!runnerAbortSignal && runnerFileDurations.length) {
    log("info", "Batch finished. " + runnerFileDurations.length + " files in " + ((Date.now() - runnerBatchStartTs) / 1000).toFixed(1) + "s");
  }
}

function runnerPause() {
  if (runnerState === "running") {
    runnerPauseRequested = true;
    runnerSetState("paused");
    // Cancel any blocking pre-submit (or inter-file) wait so pause is
    // instant — runnerGate will block subsequent code from advancing.
    if (typeof runnerCancelWait === "function") {
      try { runnerCancelWait(); } catch (e) {}
    }
    log("info", "Runner paused");
  }
}

function runnerResume() {
  if (runnerState === "paused") {
    runnerPauseRequested = false;
    runnerSetState("running");
    log("info", "Runner resumed");
  } else if (runnerState === "captcha") {
    runnerCaptchaPause = false;
    runnerSetState("running");
    log("info", "Runner resumed after captcha");
  }
}

// AbortController-style runner stop. The runner is a long-running loop;
// user clicks Stop -> we abort the entire thing immediately. All waits
// (page phase, download, sleep, gate) check this flag.
var runnerAbortCtrl = null;
// Convenience boolean readable from anywhere: was runnerAbortCtrl aborted?
// Updated by runnerStop().
var runnerAbortSignal = false;

function runnerStop() {
  // Idempotent: clicking Stop while idle is a no-op (with a short log).
  if (!runnerAbortCtrl || runnerAbortSignal) {
    logWarn("Runner stop: nothing running");
    return;
  }
  logWarn("Runner stopped by user");
  if (typeof runnerAbortCtrl.abort === "function") runnerAbortCtrl.abort();
  runnerAbortSignal = true;
  // Also clear any active pause/captcha wait so the runner exits its gate.
  runnerPauseRequested = false;
  runnerCaptchaPause = false;
  // Cancel any blocking wait that ignores abort signal — best effort.
  if (typeof runnerCancelWait === "function") {
    try { runnerCancelWait(); } catch (e) {}
  }
  // Tell the operator: button flips to "Start" right away.
  runnerSetState("idle");
  // Flush remaining queue so any in-flight per-file work throws on next gate.
  runnerQueue = [];
  runnerAbortCtrl = null;
}

// Poll the live progress of the current file for UI bars (throttled).
function startRunnerProgressPolling() {
  if (runnerProgressTick) return;
  runnerProgressTick = setInterval(async function () {
    if (runnerState !== "running" && runnerState !== "paused" && runnerState !== "captcha") return;
    var p = await runnerSend("VECTOR_ASSIST_GET_PROGRESS");
    if (p && typeof updateRunnerProgressUI === "function") updateRunnerProgressUI(p);
  }, 500);
}

// --------------------------------------------------------------------------
// Presets: CRUD, saved/unsaved, easy switching. Extension is source of
  // truth -> applying a preset pushes all settings to the page via literal
  // clicks. The page can still change the extension (two-way), but a preset
  // is what drives the page, never the other way around.
  // --------------------------------------------------------------------------
  var presetSelect, presetStatus, currentPresetName = "";

  function getPresets() {
    return new Promise(function (resolve) {
      try {
        if (!chrome.storage || !chrome.storage.local) { resolve([]); return; }
        chrome.storage.local.get(["vectorAssistPresets"], function (res) {
          resolve((res && res.vectorAssistPresets) || []);
        });
      } catch (e) { resolve([]); }
    });
  }

  function setPresets(list) {
    try {
      if (chrome.storage && chrome.storage.local) {
        return new Promise(function (resolve) {
          chrome.storage.local.set({ vectorAssistPresets: list }, function () { resolve(list); });
        });
      }
    } catch (e) {}
    return Promise.resolve(list);
  }

  function settingsEqual(a, b) {
    return JSON.stringify(a || {}) === JSON.stringify(b || {});
  }

  function refreshPresetList(list) {
    if (!presetSelect) return;
    var data = list;
    if (!data) {
      getPresets().then(function (l) { refreshPresetList(l); });
      return;
    }
    var selected = currentPresetName;
    presetSelect.innerHTML = '<option value="">Unsaved</option>';
    data.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = p.name;
      if (p.name === selected) opt.selected = true;
      presetSelect.appendChild(opt);
    });
    // Make sure the select actually shows the current selection
    // (innerHTML rebuild can leave the wrong option selected in some browsers).
    if (selected && data.some(function (p) { return p.name === selected; })) {
      presetSelect.value = selected;
    } else {
      presetSelect.value = "";
    }
    updatePresetStatus();
    syncPresetButtons();
  }

  function currentSettingsSnapshot() {
    var root = document.querySelector(".settings");
    var data = collectSettings(root);
    var sp = getScalePercent(root);
    if (sp) data.scalePercent = sp;
    return data;
  }

  // Preset state machine: "idle" | "loaded" | "dirty" | "editing"
  var presetState = "idle";
  // Cache of the preset's original settings while in edit mode (for Cancel).
  var editingOriginal = null;

  function setStatusText(text, kind) {
    if (!presetStatus) return;
    presetStatus.textContent = text || "";
    presetStatus.classList.remove("unsaved", "editing", "saved");
    if (kind) presetStatus.classList.add(kind);
  }

  function syncPresetButtons() {
    var hasPreset = !!currentPresetName;
    if (btnPresetEdit) btnPresetEdit.hidden = !hasPreset || presetState === "editing";
    if (btnPresetDelete) btnPresetDelete.disabled = !hasPreset;
  }

  function setPresetState(newState, opts) {
    presetState = newState;
    opts = opts || {};
    if (presetSelect) {
      presetSelect.value = (newState === "idle" || newState === "dirty") ? "" : currentPresetName;
    }
    if (newState === "editing") {
      editingOriginal = opts.original ? JSON.parse(JSON.stringify(opts.original)) : null;
    } else if (newState !== "editing") {
      editingOriginal = null;
    }
    renderStatus();
    syncPresetButtons();
  }

  function renderStatus() {
    if (!presetStatus) return;
    if (presetState === "idle") { setStatusText(""); return; }
    if (presetState === "loaded") { setStatusText("Saved: " + currentPresetName, "saved"); return; }
    if (presetState === "dirty") { setStatusText("Unsaved", "unsaved"); return; }
    if (presetState === "editing") {
      setStatusText("Editing: " + currentPresetName, "editing");
    }
  }

  function updatePresetStatus() {
    // No-op: the preset name persists in the combo until the user
    // explicitly picks a different preset (or "Unsaved"). Editing a
    // field is just an override that gets pushed to the page; it does
    // not silently demote the combo to "Unsaved".
  }

  function applyPresetToUI(preset) {
    var root = document.querySelector(".settings");
    if (!root || !preset) return;
    applyingFromPage = true;
    var data = preset.settings || {};
    Object.keys(data).forEach(function (name) {
      var val = data[name];
      if (name === "scalePercent") return;
      var els = root.querySelectorAll('[name="' + name + '"]');
      els.forEach(function (el) {
        if (el.type === "radio") {
          if (el.value === val) el.checked = true;
        } else if (el.type === "checkbox") {
          el.checked = !!val;
        } else {
          el.value = val;
        }
      });
    });
    if (data.scalePercent) setScalePercent(root, data.scalePercent);
    applySettingsRules(root);
    saveSettings(root);
    pushSettingsToPage(root);
    applyingFromPage = false;
  }

  var btnPresetNew, btnPresetEdit, btnPresetSave, btnPresetCancel, btnPresetRename, btnPresetDelete;
  function setupPresets() {
    presetSelect = document.getElementById("presetSelect");
    presetStatus = document.getElementById("presetStatus");
    btnPresetNew = document.getElementById("btnPresetNew");
    btnPresetEdit = document.getElementById("btnPresetEdit");
    btnPresetSave = document.getElementById("btnPresetSave");
    btnPresetDelete = document.getElementById("btnPresetDelete");
    if (!presetSelect) return;

    // Load preset (read-only dropdown -> applies to UI + page).
    presetSelect.addEventListener("change", function () {
      var name = presetSelect.value;
      updateReadyLine();
      if (!name) { setPresetState("idle"); return; }
      currentPresetName = name;
      getPresets().then(function (list) {
        var preset = list.filter(function (p) { return p.name === name; })[0];
        if (preset) {
          applyPresetToUI(preset);
          setPresetState("loaded");
          log("preset", "Loaded preset '" + name + "' (" + Object.keys(preset.settings || {}).length + " fields)");
        } else {
          setPresetState("idle");
          logWarn("Preset '" + name + "' not found after selection");
        }
      });
    });

        if (btnPresetNew) btnPresetNew.onclick = function () {
      var name = prompt("New preset name:", "My Preset");
      if (!name) return;
      name = name.trim();
      if (!name) return;
      getPresets().then(function (list) {
        if (list.some(function (p) { return p.name === name; })) {
          alert("A preset named \"" + name + "\" already exists.");
          logWarn("Preset create blocked: '" + name + "' already exists");
          return;
        }
        list.push({ name: name, settings: currentSettingsSnapshot() });
        setPresets(list).then(function (savedList) {
          currentPresetName = name;
          refreshPresetList(savedList);
          setPresetState("loaded");
          log("preset", "Created preset '" + name + "' (" + savedList.length + " total)");
        });
      });
    };

    if (btnPresetEdit) btnPresetEdit.onclick = function () {
      if (!currentPresetName) return;
      getPresets().then(function (list) {
        var preset = list.filter(function (p) { return p.name === currentPresetName; })[0];
        if (!preset) return;
        setPresetState("editing", { original: preset.settings });
        log("preset", "Editing preset '" + currentPresetName + "'");
      });
    };

    if (btnPresetSave) btnPresetSave.onclick = function () {
      var doSave = function (name) {
        if (!name) return;
        name = name.trim();
        if (!name) return;
        currentPresetName = name;
        getPresets().then(function (list) {
          var snap = currentSettingsSnapshot();
          var existing = list.filter(function (p) { return p.name === currentPresetName; })[0];
          if (existing) {
            existing.settings = snap;
            log("preset", "Overwrote preset '" + name + "'");
          } else {
            list.push({ name: currentPresetName, settings: snap });
            log("preset", "Saved new preset '" + name + "'");
          }
          setPresets(list).then(function (savedList) {
            refreshPresetList(savedList);
            setPresetState("loaded");
          });
        });
      };
      if (presetState === "editing" && currentPresetName) {
        // Edit mode: directly overwrite the active preset.
        doSave(currentPresetName);
      } else {
        // Idle/dirty/loaded: prompt for a name. Same name as existing = overwrite;
        // different name = create new.
        var name = prompt("Save preset as:", currentPresetName || "My Preset");
        doSave(name);
      }
    };

    if (btnPresetDelete) btnPresetDelete.onclick = function () {
      if (!currentPresetName) { alert("Select a preset to delete first."); return; }
      if (!confirm("Delete preset \"" + currentPresetName + "\"?")) return;
      var deletedName = currentPresetName;
      getPresets().then(function (list) {
        list = list.filter(function (p) { return p.name !== currentPresetName; });
        setPresets(list).then(function (savedList) {
          currentPresetName = "";
          setPresetState("idle");
          refreshPresetList(savedList);
          log("preset", "Deleted preset '" + deletedName + "' (" + savedList.length + " remain)");
        });
      });
    };

    var root = document.querySelector(".settings");
    if (root) {
      root.addEventListener("change", function () {
        if (applyingFromPage) return;
        updatePresetStatus();
      });
    }
    var scaleWrap = root && root.querySelector('[data-opt="scalePercent"]');
    if (scaleWrap) {
      scaleWrap.addEventListener("click", function () {
        if (applyingFromPage) return;
        updatePresetStatus();
      });
    }

    refreshPresetList();
    setPresetState("idle");
  }
})();
