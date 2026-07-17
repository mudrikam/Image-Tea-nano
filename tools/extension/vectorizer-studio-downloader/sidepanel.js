(function () {
  var DB_NAME = "VeesDownloader";
  var STORE_NAME = "files";
  var DB_VERSION = 1;
  var db = null;

  function openDB() {
    return new Promise(function (resolve, reject) {
      var request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = function (event) {
        var database = event.target.result;
        if (!database.objectStoreNames.contains(STORE_NAME)) {
          database.createObjectStore(STORE_NAME, { keyPath: "fileName" });
        }
      };
      request.onsuccess = function (event) { db = event.target.result; resolve(db); };
      request.onerror = function (event) { reject(event.target.error); };
    });
  }

  function ensureDB() {
    if (db) return Promise.resolve(db);
    return openDB();
  }

  function readFileAsDataURL(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function (e) { resolve(e.target.result); };
      reader.onerror = function (e) { reject(e); };
      reader.readAsDataURL(file);
    });
  }

  function addFiles(files) {
    if (!files || files.length === 0) return Promise.resolve(0);
    var records = [];
    var idx = 0;
    function readNext() {
      if (idx >= files.length) {
        return ensureDB().then(function () {
          return new Promise(function (resolve, reject) {
            var tx = db.transaction([STORE_NAME], "readwrite");
            var store = tx.objectStore(STORE_NAME);
            for (var j = 0; j < records.length; j++) { store.put(records[j]); }
            tx.oncomplete = function () { resolve(records.length); };
            tx.onerror = function (event) { reject(event.target.error); };
          });
        });
      }
      var f = files[idx];
      return readFileAsDataURL(f).then(function (dataUrl) {
        records.push({
          fileName: f.name, originalData: dataUrl, fileType: f.type || "image/png",
          originalSize: f.size, status: "pending", vectorizedData: null, blobUrl: null,
          timestamp: new Date().toISOString(), error: null
        });
        idx++;
        return readNext();
      });
    }
    return readNext();
  }

  function getAllFiles() {
    return ensureDB().then(function () {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction([STORE_NAME], "readonly");
        tx.objectStore(STORE_NAME).getAll().onsuccess = function (e) { resolve(e.target.result); };
        tx.objectStore(STORE_NAME).getAll().onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function updateFileStatus(fileName, status, vectorizedData, blobUrl, error) {
    return ensureDB().then(function () {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction([STORE_NAME], "readwrite");
        var store = tx.objectStore(STORE_NAME);
        var getReq = store.get(fileName);
        getReq.onsuccess = function (e) {
          var file = e.target.result;
          if (file) {
            file.status = status;
            if (vectorizedData !== undefined) file.vectorizedData = vectorizedData;
            if (blobUrl !== undefined) file.blobUrl = blobUrl;
            if (error !== undefined) file.error = error;
            file.timestamp = new Date().toISOString();
            store.put(file);
          }
          resolve(file);
        };
        getReq.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function deleteFile(fileName) {
    return ensureDB().then(function () {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction([STORE_NAME], "readwrite");
        tx.objectStore(STORE_NAME).delete(fileName).onsuccess = function () { resolve(); };
      });
    });
  }

  function clearAllFiles() {
    return ensureDB().then(function () {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction([STORE_NAME], "readwrite");
        tx.objectStore(STORE_NAME).clear().onsuccess = function () { resolve(); };
      });
    });
  }

  var LOG_MAX = 200;
  function addLog(msg, type) {
    type = type || "info";
    var lb = document.getElementById("logsBody");
    if (!lb) return;
    var ts = new Date().toTimeString().split(" ")[0];
    var entry = document.createElement("div");
    entry.className = "log-entry " + type;
    entry.innerHTML = "<span class=\"ts\">" + ts + "</span>" + msg;
    lb.appendChild(entry);
    while (lb.children.length > LOG_MAX) lb.removeChild(lb.firstChild);
    lb.scrollTop = lb.scrollHeight;
  }

  // Truncate filename for display (~42 chars at 360px)
  function truncFileName(name) {
    if (name.length <= 28) return name;
    var ext = name.lastIndexOf(".");
    if (ext > 0) {
      var base = name.substring(0, ext);
      var suffix = name.substring(ext);
      return base.substring(0, 20) + "..." + suffix.substring(0, 8);
    }
    return name.substring(0, 25) + "...";
  }

  var allFiles = [];
  var selectedFile = null;
  var isProcessing = false;
  var isOnSite = false;
  var SITE_URL = "https://vectorizer.studio/";
  var SITE_PATTERN = /:\/\/([^/]+\.)?vectorizer\.studio(\/|$)/i;

  var batchRunning = false;
  var batchQueue = [];
  var batchCooldown = 30;
  var batchTotal = 0;
  var batchDone = 0;
  var batchFailed = 0;
  var countdownTimer = null;
  var cooldownRemaining = 0;

  var landingPage, mainInterface, btnOpenSite;
  var dndZone, fileInput, folderInput, btnSelectFiles, btnSelectFolder;
  var previewPlaceholder, previewImage;
  var fileTableBody, emptyState, fileCount;
  var btnClearAll, btnBatchStart, btnBatchStop, btnDownloadAll;
  var batchBar, cooldownInput, countdownText, batchStats;
  var logsToggle, logsBody, logsChevron;

  function cacheDOM() {
    landingPage = document.getElementById("landingPage");
    mainInterface = document.getElementById("mainInterface");
    btnOpenSite = document.getElementById("btnOpenSite");
    dndZone = document.getElementById("dndZone");
    fileInput = document.getElementById("fileInput");
    folderInput = document.getElementById("folderInput");
    btnSelectFiles = document.getElementById("btnSelectFiles");
    btnSelectFolder = document.getElementById("btnSelectFolder");
    previewPlaceholder = document.getElementById("previewPlaceholder");
    previewImage = document.getElementById("previewImage");
    fileTableBody = document.getElementById("fileTableBody");
    emptyState = document.getElementById("emptyState");
    fileCount = document.getElementById("fileCount");
    btnClearAll = document.getElementById("btnClearAll");
    btnBatchStart = document.getElementById("btnBatchStart");
    btnBatchStop = document.getElementById("btnBatchStop");
    btnDownloadAll = document.getElementById("btnDownloadAll");
    batchBar = document.getElementById("batchBar");
    cooldownInput = document.getElementById("cooldownInput");
    countdownText = document.getElementById("countdownText");
    batchStats = document.getElementById("batchStats");
    logsToggle = document.getElementById("logsToggle");
    logsBody = document.getElementById("logsBody");
    logsChevron = document.getElementById("logsChevron");
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
      isOnSite = onSite;
      if (onSite) { landingPage.classList.add("hidden"); mainInterface.classList.remove("hidden"); }
      else { mainInterface.classList.add("hidden"); landingPage.classList.remove("hidden"); }
    });
  }

  function showPreview(file) {
    selectedFile = file;
    if (file && file.originalData) {
      previewImage.src = file.originalData;
      previewImage.classList.remove("hidden");
      previewPlaceholder.classList.add("hidden");
    } else {
      previewImage.classList.add("hidden");
      previewPlaceholder.classList.remove("hidden");
    }
  }

  function renderFileList() {
    getAllFiles().then(function (files) {
      allFiles = files;
      fileTableBody.innerHTML = "";

      if (files.length === 0) {
        emptyState.classList.remove("hidden");
        fileCount.textContent = "0 files";
        showPreview(null);
      } else {
        emptyState.classList.add("hidden");
        fileCount.textContent = files.length + " file" + (files.length > 1 ? "s" : "");

        for (var i = 0; i < files.length; i++) {
          (function (file) {
            var row = document.createElement("tr");
            row.className = "status-" + file.status;
            if (selectedFile && selectedFile.fileName === file.fileName) row.classList.add("selected");

            var nc = document.createElement("td");
            var fc = document.createElement("div"); fc.className = "file-name-cell";
            if (file.originalData) { var th = document.createElement("img"); th.className = "file-thumb"; th.src = file.originalData; fc.appendChild(th); }
            var ns = document.createElement("span"); ns.className = "file-name"; ns.textContent = truncFileName(file.fileName); ns.title = file.fileName; fc.appendChild(ns);
            nc.appendChild(fc);
            row.appendChild(nc);

            var sc = document.createElement("td");
            var badge = document.createElement("span"); badge.className = "status-badge";
            if (file.status === "pending") { badge.className += " status-pending"; badge.textContent = "Pending"; }
            else if (file.status === "processing") { badge.className += " status-processing"; badge.innerHTML = "<span class=\"spinner\"></span> Processing"; }
            else if (file.status === "done") { badge.className += " status-done"; badge.textContent = "Done"; }
            else if (file.status === "failed") { badge.className += " status-failed"; badge.textContent = "Failed"; }
            else { badge.className += " status-pending"; badge.textContent = file.status; }
            sc.appendChild(badge); row.appendChild(sc);

            var ac = document.createElement("td"); ac.className = "file-actions";

            var procBtn = document.createElement("button"); procBtn.className = "btn-icon"; procBtn.title = "Vectorize";
            procBtn.innerHTML = "<svg width=\"12\" height=\"12\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" viewBox=\"0 0 24 24\"><polygon points=\"13 2 3 14 12 14 11 22 21 10 12 10 13 2\"/></svg>";
            procBtn.onclick = function (e) { e.stopPropagation(); processSingleFile(file); };

            var dlBtn = document.createElement("button"); dlBtn.className = "btn-icon download"; dlBtn.title = "Download SVG";
            dlBtn.innerHTML = "<svg width=\"12\" height=\"12\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" viewBox=\"0 0 24 24\"><path d=\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\"/><polyline points=\"7 10 12 15 17 10\"/><line x1=\"12\" y1=\"15\" x2=\"12\" y2=\"3\"/></svg>";
            if (file.status !== "done") { dlBtn.style.opacity = "0.25"; dlBtn.style.pointerEvents = "none"; }
            dlBtn.onclick = function (e) { e.stopPropagation(); if (file.status === "done" && file.vectorizedData) downloadSVG(file); };

            var delBtn = document.createElement("button"); delBtn.className = "btn-icon delete"; delBtn.title = "Delete";
            delBtn.innerHTML = "<svg width=\"12\" height=\"12\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" viewBox=\"0 0 24 24\"><polyline points=\"3 6 5 6 21 6\"/><path d=\"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\"/></svg>";
            delBtn.onclick = function (e) { e.stopPropagation(); deleteFile(file.fileName).then(function () { if (selectedFile && selectedFile.fileName === file.fileName) showPreview(null); addLog("Deleted: " + file.fileName); renderFileList(); }); };

            ac.appendChild(procBtn); ac.appendChild(dlBtn); ac.appendChild(delBtn);
            row.appendChild(ac);
            row.onclick = function () { showPreview(file); renderFileList(); };
            fileTableBody.appendChild(row);
          })(files[i]);
        }
        if (selectedFile && !files.some(function (f) { return f.fileName === selectedFile.fileName; })) showPreview(null);
      }
    }).catch(function (err) { addLog("Render error: " + err.message, "error"); });
  }

  function processSingleFile(file) {
    if (isProcessing) { addLog("Busy, wait.", "warn"); return; }
    if (file.status === "done") { addLog("Already vectorized.", "warn"); return; }
    isProcessing = true;
    updateFileStatus(file.fileName, "processing").then(function () {
      renderFileList();
      addLog("Processing: " + file.fileName);
      chrome.runtime.sendMessage({ type: "PROCESS_FILE", file: file }, function (resp) {
        if (chrome.runtime.lastError) {
          addLog("Error: " + chrome.runtime.lastError.message, "error");
          updateFileStatus(file.fileName, "failed", null, null, chrome.runtime.lastError.message).then(function () { isProcessing = false; renderFileList(); });
        } else if (!resp || !resp.received) {
          addLog("Send failed: " + file.fileName + (resp && resp.error ? " (" + resp.error + ")" : ""), "error");
          updateFileStatus(file.fileName, "failed", null, null, (resp && resp.error) || "Send failed").then(function () { isProcessing = false; renderFileList(); });
        }
      });
    });
  }

  function downloadSVG(file) {
    addLog("Download: " + file.fileName.replace(/\.[^.]+$/, "") + ".svg");
    chrome.runtime.sendMessage({ type: "DOWNLOAD_SVG", svgData: file.vectorizedData, fileName: file.fileName }, function (resp) {
      if (resp && resp.success) addLog("OK: " + file.fileName.replace(/\.[^.]+$/, "") + ".svg", "success");
      else addLog("DL fail: " + (resp ? resp.error : "unknown"), "error");
    });
  }

  function downloadAllDone() {
    getAllFiles().then(function (files) {
      var doneFiles = files.filter(function (f) { return f.status === "done" && f.vectorizedData; });
      if (doneFiles.length === 0) { addLog("No vectorized files.", "warn"); return; }
      addLog("Downloading " + doneFiles.length + " SVGs...");
      for (var i = 0; i < doneFiles.length; i++) { downloadSVG(doneFiles[i]); }
    });
  }

  chrome.runtime.onMessage.addListener(function (msg) {
    if (msg.type === "BLOB_CAPTURED_SIDEPANEL") {
      addLog("Vectorized: " + msg.fileName, "success");
      updateFileStatus(msg.fileName, "done", msg.vectorizedData, msg.blobUrl).then(function () {
        isProcessing = false;
        renderFileList();
        if (batchRunning) advanceBatch();
      });
    }
    if (msg.type === "PROCESS_FAILED_SIDEPANEL") {
      addLog("Failed: " + msg.fileName + " (" + msg.reason + ")", "error");
      updateFileStatus(msg.fileName, "failed", null, null, msg.reason).then(function () {
        isProcessing = false;
        renderFileList();
        if (batchRunning) advanceBatch();
      });
    }
  });

  function advanceBatch() {
    if (!batchRunning) return;
    batchQueue.shift();
    if (batchQueue.length === 0) { finishBatch(); return; }
    batchCooldown = parseInt(cooldownInput.value, 10) || 30;
    cooldownRemaining = batchCooldown;
    updateBatchStats();
    countdownTimer = setInterval(function () {
      cooldownRemaining--;
      if (cooldownRemaining <= 0) {
        clearInterval(countdownTimer);
        countdownText.textContent = "";
        var next = batchQueue[0];
        if (next) processSingleFile(next);
      } else {
        countdownText.textContent = cooldownRemaining + "s";
      }
    }, 1000);
  }

  function updateBatchStats() {
    batchStats.textContent = batchDone + "/" + batchTotal + (batchFailed > 0 ? " err " + batchFailed : "");
  }

  function finishBatch() {
    batchRunning = false;
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    countdownText.textContent = "";
    isProcessing = false;
    addLog("Batch complete: " + batchDone + " done, " + batchFailed + " failed.", "success");
    renderFileList();
  }

  function startBatch() {
    getAllFiles().then(function (files) {
      var pending = files.filter(function (f) { return f.status === "pending" || f.status === "failed"; });
      if (pending.length === 0) { addLog("No pending files.", "warn"); return; }
      batchRunning = true;
      batchQueue = pending.slice();
      batchTotal = pending.length;
      batchDone = 0;
      batchFailed = 0;
      addLog("Batch: " + batchTotal + " files, cooldown " + (parseInt(cooldownInput.value, 10) || 30) + "s");
      var first = batchQueue[0];
      if (first) processSingleFile(first);
      updateBatchStats();
    });
  }

  function stopBatch() {
    batchRunning = false;
    batchQueue = [];
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    countdownText.textContent = "";
    isProcessing = false;
    addLog("Batch stopped.", "warn");
    renderFileList();
  }

  function setupDnD() {
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
      e.preventDefault(); dndZone.classList.remove("drag-over");
      var items = e.dataTransfer.items;
      var files = [];
      function addFileEntry(entry) {
        if (entry.isFile) return new Promise(function (r) { entry.file(function (f) { files.push(f); r(); }); });
        if (entry.isDirectory) {
          var reader = entry.createReader();
          return new Promise(function (r) {
            function readEntries() {
              reader.readEntries(function (entries) {
                if (entries.length === 0) { r(); return; }
                var ps = []; for (var k = 0; k < entries.length; k++) ps.push(addFileEntry(entries[k]));
                Promise.all(ps).then(readEntries);
              });
            }
            readEntries();
          });
        }
        return Promise.resolve();
      }
      if (items && items.length > 0 && items[0].webkitGetAsEntry) {
        var ps = []; for (var i = 0; i < items.length; i++) { var entry = items[i].webkitGetAsEntry(); if (entry) ps.push(addFileEntry(entry)); }
        Promise.all(ps).then(function () { handleNewFiles(files); });
      } else { handleNewFiles(Array.from(e.dataTransfer.files)); }
    });
    fileInput.addEventListener("change", function () { handleNewFiles(Array.from(fileInput.files)); });
    folderInput.addEventListener("change", function () { handleNewFiles(Array.from(folderInput.files)); });
    document.addEventListener("paste", function (e) {
      if (!isOnSite) return;
      var items = e.clipboardData && e.clipboardData.items; if (!items) return;
      var files = []; for (var i = 0; i < items.length; i++) { if (items[i].kind === "file") files.push(items[i].getAsFile()); }
      if (files.length > 0) { e.preventDefault(); handleNewFiles(files); }
    });
  }

  function handleNewFiles(files) {
    if (!files || files.length === 0) return;
    var imageFiles = [];
    for (var i = 0; i < files.length; i++) {
      if (files[i].type.match(/^image\//) || /\.(png|jpg|jpeg|webp|gif|bmp)$/i.test(files[i].name)) imageFiles.push(files[i]);
    }
    if (imageFiles.length === 0) { addLog("No valid images.", "warn"); return; }
    getAllFiles().then(function (existing) {
      var existingNames = new Set(existing.map(function (f) { return f.fileName; }));
      var newFiles = imageFiles.filter(function (f) { return !existingNames.has(f.name); });
      if (newFiles.length === 0) { addLog("All already loaded.", "warn"); return; }
      addLog("Loading " + newFiles.length + " file" + (newFiles.length > 1 ? "s" : "") + "...");
      addFiles(newFiles).then(function (count) {
        addLog("Loaded " + count + " file" + (count > 1 ? "s" : ""), "success");
        renderFileList();
      }).catch(function (err) { addLog("Load error: " + err.message, "error"); });
    });
  }

  function setupButtons() {
    btnClearAll.onclick = function () {
      clearAllFiles().then(function () {
        isProcessing = false; selectedFile = null; showPreview(null);
        batchDone = 0; batchFailed = 0; batchTotal = 0;
        updateBatchStats();
        addLog("Cleared.", "info"); renderFileList();
      });
    };
    btnBatchStart.onclick = function () { startBatch(); };
    btnBatchStop.onclick = function () { stopBatch(); };
    btnDownloadAll.onclick = function () { downloadAllDone(); };

    var btnHelp = document.getElementById("btnHelp");
    var helpModal = document.getElementById("helpModal");
    var btnCloseHelp = document.getElementById("btnCloseHelp");
    btnHelp.onclick = function () { helpModal.classList.remove("hidden"); };
    btnCloseHelp.onclick = function () { helpModal.classList.add("hidden"); };
    helpModal.addEventListener("click", function (e) { if (e.target === helpModal) helpModal.classList.add("hidden"); });
  }

  function setupLogsToggle() {
    var collapsed = false;
    logsToggle.onclick = function () {
      collapsed = !collapsed;
      if (collapsed) { logsBody.classList.add("collapsed"); logsChevron.style.transform = "rotate(-90deg)"; }
      else { logsBody.classList.remove("collapsed"); logsChevron.style.transform = ""; }
    };
  }

  function setupTabMonitoring() {
    chrome.tabs.onActivated.addListener(function () { initView(); });
    chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
      if (changeInfo.status === "complete" || changeInfo.url) { if (tab && tab.active) initView(); }
    });
    if (chrome.windows && chrome.windows.onFocusChanged) chrome.windows.onFocusChanged.addListener(function () { initView(); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    cacheDOM();
    try {
      fetch("manifest.json").then(function (r) {
        if (r.ok) r.json().then(function (m) {
          var v = document.getElementById("extensionVersion"); if (v && m.version) v.textContent = "v" + m.version;
          var lv = document.getElementById("landingVersion"); if (lv && m.version) lv.textContent = "v" + m.version;
        });
      }).catch(function () {});
    } catch (e) {}
    btnOpenSite.onclick = function () {
      chrome.tabs.query({ url: '*://*.vectorizer.studio/*' }, function (tabs) {
        if (tabs && tabs.length > 0) {
          chrome.tabs.update(tabs[0].id, { active: true });
          chrome.windows.update(tabs[0].windowId, { focused: true }).catch(function () {});
        } else {
          chrome.tabs.create({ url: SITE_URL });
        }
      });
    };
    openDB().then(function () { addLog("DB ready."); }).catch(function (err) { addLog("DB error: " + err.message, "error"); });
    setupDnD();
    setupButtons();
    setupLogsToggle();
    setupTabMonitoring();
    updateBatchStats();
    initView().then(function () { renderFileList(); });
  });
})();
