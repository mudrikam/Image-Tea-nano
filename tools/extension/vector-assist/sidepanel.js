// Vector Assist - Side Panel (UI only)
(function () {
  var SITE_URL = "https://vectorizer.ai/";
  var SITE_PATTERN = /:\/\/([^/]+\.)?vectorizer\.ai(\/|$)/i;

  var landingPage, mainInterface, btnOpenSite;
  var dndZone, fileInput, folderInput, btnSelectFiles, btnSelectFolder;
  var btnStartProcess, btnStopProcess;
  var fileTableBody, emptyState;
  var statLoaded, statPending, statFinished, statFailed;
  var isRunning = false;

  // In-memory file list. Each item:
  // { name, type, size, dataUrl, status: "pending"|"processing"|"done"|"failed" }
  var files = [];
  var selectedName = null;

  // --------------------------------------------------------------------------
  // IndexedDB persistence
  // --------------------------------------------------------------------------
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
      } else {
        mainInterface.classList.add("hidden");
        landingPage.classList.remove("hidden");
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

  // Recursively read a dropped file/directory entry.
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
        return dbPut(record).catch(function () {});
      }).catch(function () {});
    });

    Promise.all(jobs).then(function () {
      renderFileList();
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

      // # column
      var numCell = document.createElement("td");
      numCell.className = "file-num";
      numCell.textContent = index + 1;
      row.appendChild(numCell);

      // File column (thumb + name)
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

      // Status column
      var statusCell = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "status-badge status-" + file.status;
      badge.textContent = file.status.charAt(0).toUpperCase() + file.status.slice(1);
      statusCell.appendChild(badge);
      row.appendChild(statusCell);

      // Actions column (no functionality yet)
      var actionsCell = document.createElement("td");
      var actions = document.createElement("div");
      actions.className = "file-actions";
      actions.appendChild(makeActionBtn(file, "act-run", "Process",
        '<svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>'));
      actions.appendChild(makeActionBtn(file, "act-download", "Download",
        '<svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'));
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
      }
      // Process / Download: no functionality yet.
    };
    return btn;
  }

  function deleteFile(name) {
    files = files.filter(function (f) { return f.name !== name; });
    if (selectedName === name) selectedName = null;
    dbDelete(name).catch(function () {});
    renderFileList();
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

    if (isRunning) {
      btnStartProcess.classList.add("running");
      if (iconStart) iconStart.classList.add("hidden");
      if (iconPause) iconPause.classList.remove("hidden");
      if (label) label.textContent = "Pause";
      if (btnStopProcess) btnStopProcess.disabled = false;
    } else {
      btnStartProcess.classList.remove("running");
      if (iconStart) iconStart.classList.remove("hidden");
      if (iconPause) iconPause.classList.add("hidden");
      if (label) label.textContent = "Start Process";
      if (btnStopProcess) btnStopProcess.disabled = true;
    }
  }

  function setupControls() {
    if (btnStartProcess) {
      btnStartProcess.onclick = function () {
        // Basic switching only — no program yet.
        isRunning = !isRunning;
        updateControlUI();
      };
    }
    if (btnStopProcess) {
      btnStopProcess.onclick = function () {
        if (btnStopProcess.disabled) return;
        // Basic switching only — no program yet.
        isRunning = false;
        updateControlUI();
      };
    }
    updateControlUI();
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

  function setupTabMonitoring() {
    chrome.tabs.onActivated.addListener(function () { initView(); });
    chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
      if (changeInfo.status === "complete" || changeInfo.url) { if (tab && tab.active) initView(); }
    });
    if (chrome.windows && chrome.windows.onFocusChanged) {
      chrome.windows.onFocusChanged.addListener(function () { initView(); });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    landingPage = document.getElementById("landingPage");
    mainInterface = document.getElementById("mainInterface");
    btnOpenSite = document.getElementById("btnOpenSite");
    btnStartProcess = document.getElementById("btnStartProcess");
    btnStopProcess = document.getElementById("btnStopProcess");
    dndZone = document.getElementById("dndZone");
    fileInput = document.getElementById("fileInput");
    folderInput = document.getElementById("folderInput");
    btnSelectFiles = document.getElementById("btnSelectFiles");
    btnSelectFolder = document.getElementById("btnSelectFolder");
    fileTableBody = document.getElementById("fileTableBody");
    emptyState = document.getElementById("emptyState");
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
    renderFileList();
    setupTabMonitoring();
    initView();

    // Restore previously loaded files from IndexedDB.
    dbGetAll().then(function (records) {
      if (records && records.length) {
        files = records;
        renderFileList();
      }
    }).catch(function () {});
  });
})();
