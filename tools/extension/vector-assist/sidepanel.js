// Vector Assist - Side Panel (UI only)
(function () {
  var SITE_URL = "https://vectorizer.ai/";
  var SITE_PATTERN = /:\/\/([^/]+\.)?vectorizer\.ai(\/|$)/i;

  var landingPage, mainInterface, btnOpenSite;
  var dndZone, fileInput, folderInput, btnSelectFiles, btnSelectFolder;
  var btnStartProcess, btnStopProcess;
  var isRunning = false;

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
      // GUI only — file handling to be implemented later.
    });

    fileInput.addEventListener("change", function () {
      // GUI only — file handling to be implemented later.
    });
    folderInput.addEventListener("change", function () {
      // GUI only — file handling to be implemented later.
    });
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
    setupTabMonitoring();
    initView();
  });
})();
