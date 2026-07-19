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

  // Realtime two-way mirror state.
  var applyingFromPage = false;   // true while we reflect page -> extension
  var applyingToPage = false;     // true while we push extension -> page

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
        // The result page exposes the export options; mirror them in.
        pullPageSettings();
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

  // --------------------------------------------------------------------------
  // Realtime two-way mirror with the vectorizer.ai result page
  // --------------------------------------------------------------------------
  function pushSettingsToPage(root) {
    var data = collectSettings(root);
    applyingToPage = true;
    try {
      chrome.runtime.sendMessage({ type: "VECTOR_ASSIST_APPLY_SETTINGS", settings: data });
    } catch (e) {}
    // Long enough to cover delayMs + delayJitterMs + page reaction time.
    // During this window, reflected PAGE_CHANGED is treated as our own echo.
    setTimeout(function () { applyingToPage = false; }, 2500);
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
    try {
      chrome.runtime.sendMessage({ type: "VECTOR_ASSIST_GET_SETTINGS" }, function (resp) {
        if (resp && resp.settings) reflectPageToExtension(document.querySelector(".settings"), resp.settings);
      });
    } catch (e) {}
  }

  function setupMirror() {
    chrome.runtime.onMessage.addListener(function (msg) {
      if (!msg || msg.type !== "VECTOR_ASSIST_PAGE_CHANGED") return;
      if (applyingToPage) return; // ignore echo of our own push
      console.log("[VectorAssist] page -> extension", JSON.stringify(msg.settings));
      var root = document.querySelector(".settings");
      if (root) reflectPageToExtension(root, msg.settings);
    });
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

    // React to any change -> re-apply enable/disable rules + persist + push to page
    settingsRoot.addEventListener("change", function () {
      if (applyingFromPage) return; // don't echo page-originated updates
      applySettingsRules(settingsRoot);
      saveSettings(settingsRoot);
      pushSettingsToPage(settingsRoot);
    });

    // Default scale to 4x if nothing restored yet.
    if (!settingsRoot.dataset.scalePercent) settingsRoot.dataset.scalePercent = "400";

    // Restore saved values, then apply rules.
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

  // ---- helpers for enable/disable ----
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
    setupSettings();
    setupPresets();
    setupMirror();
    renderFileList();
    setupTabMonitoring();
    initView();

    // Pull any settings the result page already exposes.
    pullPageSettings();

    // Restore previously loaded files from IndexedDB.
    dbGetAll().then(function (records) {
      if (records && records.length) {
        files = records;
        renderFileList();
      }
    }).catch(function () {});
  });

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
    // Called on every settings edit.
    if (presetState === "loaded" || presetState === "dirty") {
      // Drop out of preset: snapshot no longer matches -> dirty/idle.
      currentPresetName = "";
      setPresetState("dirty");
    } else if (presetState === "editing") {
      renderStatus();
    }
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
    setTimeout(function () { applyingFromPage = false; }, 200);
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
      if (!name) { setPresetState("idle"); return; }
      currentPresetName = name;
      getPresets().then(function (list) {
        var preset = list.filter(function (p) { return p.name === name; })[0];
        if (preset) {
          applyPresetToUI(preset);
          setPresetState("loaded");
        } else {
          setPresetState("idle");
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
          return;
        }
        list.push({ name: name, settings: currentSettingsSnapshot() });
        setPresets(list).then(function (savedList) {
          currentPresetName = name;
          refreshPresetList(savedList);
          setPresetState("loaded");
        });
      });
    };

    if (btnPresetEdit) btnPresetEdit.onclick = function () {
      if (!currentPresetName) return;
      getPresets().then(function (list) {
        var preset = list.filter(function (p) { return p.name === currentPresetName; })[0];
        if (!preset) return;
        setPresetState("editing", { original: preset.settings });
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
          if (existing) existing.settings = snap;
          else list.push({ name: currentPresetName, settings: snap });
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
      getPresets().then(function (list) {
        list = list.filter(function (p) { return p.name !== currentPresetName; });
        setPresets(list).then(function (savedList) {
          currentPresetName = "";
          setPresetState("idle");
          refreshPresetList(savedList);
        });
      });
    };

    // Mark unsaved whenever the user edits settings.
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
