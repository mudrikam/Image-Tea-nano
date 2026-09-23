(function () {
  if (window.__VECTOR_ASSIST_CONTENT__) return;
  window.__VECTOR_ASSIST_CONTENT__ = true;

  window.__VA_RUNTIME_CONFIG__ = null;

  try {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(["ciora_runtime_config"], function (data) {
        if (data && data.ciora_runtime_config) {
          window.__VA_RUNTIME_CONFIG__ = data.ciora_runtime_config;
        }
      });
    }
  } catch (_) {}

  // Our setting key -> page input name.
  var KEY_NAME = {
    format: "file_format",
    svgVersion: "ui.svg_version_mode",
    svgFixedSize: "svg.fixed_size",
    dxfCompat: "dxf.compatibility_level",
    outputSize: "ui.size_mode",
    drawStyle: "draw_style",
    stacking: "shape_stacking",
    groupBy: "group_by",
    simpleShapes: "parameterized_shapes.flatten",
    curveLines: "curves.allowed.lines",
    curveQuad: "curves.allowed.quadratic_bezier",
    curveCubic: "curves.allowed.cubic_bezier",
    curveCirc: "curves.allowed.circular_arc",
    curveEllip: "curves.allowed.elliptical_arc",
    lineFit: "curves.line_fit_tolerance",
    gapFill: "gap_filler.enabled",
    gapClip: "gap_filler.clip",
    gapConstant: "gap_filler.non_scaling_stroke",
    gapWidth: "gap_filler.stroke_width",
    strokeConstant: "strokes.non_scaling_stroke",
    strokeWidth: "strokes.stroke_width",
    strokeOneColor: "strokes.use_override_color",
    strokeColor: "strokes.override_color",
    outWidth: "size.width",
    outHeight: "size.height",
    outUnit: "size.unit",
    outFit: "ui.fit_mode",
    outH: "size.align_x",
    outV: "size.align_y",
    outDpi: "size.output_dpi",
    widthAuto: "ui.width_auto",
    heightAuto: "ui.height_auto"
  };

  // page (inverted for simpleShapes).
  var INVERTED = { simpleShapes: true };

  // Our value -> page value.
  function pageValueFor(key, ourValue) {
    switch (key) {
      case "format": return ourValue;
      case "svgVersion":
        if (ourValue === "tiny") return "svg_tiny_1_2";
        if (ourValue === "adobe") return "adobe";
        return "svg_1_1";
      case "dxfCompat":
        if (ourValue === "lines") return "lines_only";
        if (ourValue === "arcs") return "lines_and_arcs";
        if (ourValue === "splines") return "lines_arcs_and_splines";
        return ourValue;
      case "outputSize":
        if (ourValue === "unchanged") return "automatic";
        if (ourValue === "scaled") return "scale";
        return "custom";
      case "drawStyle":
        if (ourValue === "filled") return "fill_shapes";
        if (ourValue === "strokedOutline") return "stroke_shapes";
        if (ourValue === "strokedEdge") return "stroke_edges";
        return ourValue;
      case "stacking": return ourValue;
      case "groupBy": return ourValue;
      case "outUnit": return ourValue;
      case "outFit":
        if (ourValue === "fit") return "fit_inside";
        if (ourValue === "crop") return "fill_box";
        if (ourValue === "stretch") return "stretch";
        return ourValue;
      case "lineFit":
        if (ourValue === "coarse") return "0.3";
        if (ourValue === "medium") return "0.1";
        if (ourValue === "fine") return "0.03";
        if (ourValue === "superfine") return "0.01";
        return ourValue;
      default: return ourValue;
    }
  }

  function ourValueFor(key, pageValue) {
    switch (key) {
      case "svgVersion":
        if (pageValue === "svg_tiny_1_2") return "tiny";
        if (pageValue === "adobe") return "adobe";
        return "1.1";
      case "dxfCompat":
        if (pageValue === "lines_only") return "lines";
        if (pageValue === "lines_and_arcs") return "arcs";
        if (pageValue === "lines_arcs_and_splines") return "splines";
        return pageValue;
      case "outputSize":
        if (pageValue === "automatic") return "unchanged";
        if (pageValue === "scale") return "scaled";
        return "custom";
      case "drawStyle":
        if (pageValue === "fill_shapes") return "filled";
        if (pageValue === "stroke_shapes") return "strokedOutline";
        if (pageValue === "stroke_edges") return "strokedEdge";
        return pageValue;
      case "outFit":
        if (pageValue === "fit_inside") return "fit";
        if (pageValue === "fill_box") return "crop";
        if (pageValue === "stretch") return "stretch";
        return pageValue;
      case "lineFit":
        if (pageValue === "0.3") return "coarse";
        if (pageValue === "0.1") return "medium";
        if (pageValue === "0.03") return "fine";
        if (pageValue === "0.01") return "superfine";
        return pageValue;
      default: return pageValue;
    }
  }

  function getInputs(pageName) {
    var all = document.querySelectorAll('[name="' + pageName + '"]');
    var visible = [];
    for (var i = 0; i < all.length; i++) {
      if (all[i].type !== "hidden") visible.push(all[i]);
    }
    return visible;
  }

  // Click the wrapping <label>, which is what a human would click.
  // The browser then forwards one click to the input, and the SPA
  // handler attached to (or delegated from) the label runs.
  function clickLabel(el) {
    if (!el) return;
    var label = el.closest("label");
    var target = (label && label !== el) ? label : el;
    try { target.click(); } catch (e) {}
  }

  function isChecked(el) {
    return el.type === "checkbox" || el.type === "radio" ? el.checked : !!el.checked;
  }

  function setRadio(pageName, pageValue) {
    var els = getInputs(pageName);
    els.forEach(function (el) {
      if (el.type === "radio" && el.value === pageValue && !el.checked) clickLabel(el);
    });
    // Also sync any companion hidden field (e.g., size.mode tracks ui.size_mode).
    // The page's SPA reads both to determine state.
    if (pageName === "ui.size_mode") {
      var hidden = document.getElementById("Options-SizeModeField");
      if (hidden && hidden.value !== pageValue) {
        hidden.value = pageValue;
        hidden.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
    // When clicking svgVersion, also sync the hidden svg.version field.
    if (pageName === "ui.svg_version_mode") {
      var svgVer = document.getElementById("Options-SvgVersionField");
      var target = (pageValue === "adobe") ? "svg_1_1" : pageValue;
      if (svgVer && svgVer.value !== target) {
        svgVer.value = target;
        svgVer.dispatchEvent(new Event("change", { bubbles: true }));
      }
      var adobeField = document.getElementById("Options-AdobeCompatibilityField");
      var isAdobe = (pageValue === "adobe");
      if (adobeField && adobeField.value !== String(isAdobe)) {
        adobeField.value = String(isAdobe);
        adobeField.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
  }

  function setCheckbox(pageName, targetChecked) {
    var els = getInputs(pageName);
    els.forEach(function (el) {
      if (el.type === "checkbox" && el.checked !== targetChecked) clickLabel(el);
    });
  }

  // Number / text / color: set .value + dispatch, since no label click
  // handles text input. This also fires the SPA's change handler.
  function setTextField(pageName, value) {
    var els = getInputs(pageName);
    els.forEach(function (el) {
      var str = (value === undefined || value === null || value === "") ? "" : String(value);
      if (el.value !== str) {
        el.value = str;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  }

  // Scale: click the matching quick-button (1x/2x/4x/8x) once.
  function setScale(percent) {
    var pct = parseInt(percent, 10);
    if (isNaN(pct)) return;
    var btns = document.querySelectorAll("button.Options-scale_quick");
    for (var i = 0; i < btns.length; i++) {
      if (parseInt(btns[i].getAttribute("data-scale-percent"), 10) === pct) {
        try { btns[i].click(); } catch (e) {}
      }
    }
  }

  function readPageSettings() {
    var data = {};
    Object.keys(KEY_NAME).forEach(function (key) {
      // Special-case simpleShapes: visible checkbox has no name.
      if (key === "simpleShapes") {
        var visible = document.getElementById("Options-SimpleShapesField");
        if (visible && visible.type === "checkbox") {
          // Direct mapping: extension's simpleShapes=true == visible.checked=true
          data[key] = !!visible.checked;
        }
        return;
      }
      var pageName = KEY_NAME[key];
      var els = getInputs(pageName);
      if (!els.length) return;
      var first = els[0];
      if (first.type === "checkbox") {
        var val = isChecked(first);
        if (INVERTED[key]) val = !val;
        data[key] = val;
      } else if (first.type === "radio") {
        var checkedOne = null;
        els.forEach(function (el) { if (el.checked) checkedOne = el; });
        if (checkedOne) data[key] = ourValueFor(key, checkedOne.value);
      } else {
        data[key] = first.value;
      }
    });
    // Scale: read the active quick-button's data-scale-percent, or the hidden field.
    var activeScale = document.querySelector("button.Options-scale_quick.is-active, button.Options-scale_quick.active");
    if (activeScale && activeScale.getAttribute("data-scale-percent")) {
      data.scalePercent = activeScale.getAttribute("data-scale-percent");
    }
    return data;
  }

  function applyToPage(settings) {
    if (!settings) return;
    expandAdvanced();

    // Apply format first to reveal dependent sections.
    if (settings.format !== undefined) setRadio(KEY_NAME.format, pageValueFor("format", settings.format));

    // Apply all other keys synchronously, in order. No per-field delay —
    // the page's own change handlers run on each click, and they handle
    // their own reactive updates immediately.
    var keys = Object.keys(settings).filter(function (k) {
      return k !== "format" && k !== "scalePercent" && k !== "delayMs" && k !== "delayJitterMs";
    });
    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];
      var ourValue = settings[key];
      if (key === "simpleShapes") {
        var visible = document.getElementById("Options-SimpleShapesField");
        if (visible && visible.type === "checkbox") {
          var wantChecked = ourValue;
          if (visible.checked !== wantChecked) clickLabel(visible);
        }
        continue;
      }
      var pageName = KEY_NAME[key];
      var els = getInputs(pageName);
      if (!els.length) continue;
      var first = els[0];
      if (first.type === "checkbox") {
        var checked = ourValue;
        if (INVERTED[key]) checked = !checked;
        setCheckbox(pageName, !!checked);
      } else if (first.type === "radio") {
        setRadio(pageName, pageValueFor(key, ourValue));
      } else {
        setTextField(pageName, ourValue);
      }
    }

    // After all keys, apply scale last so it doesn't get overridden by
    // the outputSize radio change above.
    var targetMode = pageValueFor("outputSize", settings.outputSize);
    if (settings.scalePercent !== undefined && targetMode === "scale") setScale(settings.scalePercent);
  }

  function expandAdvanced() {
    var details = document.getElementById("Options-AdvancedDetails");
    if (details && !details.open) {
      details.open = true;
      details.dispatchEvent(new Event("toggle", { bubbles: true }));
    }
  }

  function notifyPageChanged() {
    var data = readPageSettings();
    try { chrome.runtime.sendMessage({ type: "VECTOR_ASSIST_PAGE_CHANGED", settings: data }); } catch (e) {}
  }

  function startWatching() {
    var last = "";
    setInterval(function () {
      var data = readPageSettings();
      var sig = JSON.stringify(data);
      if (sig !== last) { last = sig; notifyPageChanged(); }
    }, 500);
    document.addEventListener("change", function () { setTimeout(notifyPageChanged, 0); }, true);
    document.addEventListener("click", function () { setTimeout(notifyPageChanged, 0); }, true);
  }

  // Convert data URL (e.g. "data:image/png;base64,AAAA") into a File with a name.
  function dataUrlToFile(dataUrl, name) {
    var parts = dataUrl.split(",");
    var mime = "image/png";
    var m = parts[0].match(/data:([^;]+)/);
    if (m) mime = m[1];
    var bin = atob(parts[1] || "");
    var u8 = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new File([u8], name, { type: mime });
  }

  // Inject a File into the page's <input type="file"> and trigger a change.
  function injectFileIntoInput(input, file) {
    if (!input || !file) return false;
    try {
      var dt;
      try { dt = new DataTransfer(); dt.items.add(file); }
      catch (e) {
        // Older Chrome fallback: set files via __proto__ setter bypass.
        try {
          Object.defineProperty(input, "files", { value: [file], writable: true });
        } catch (e2) { return false; }
        input.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
      input.files = dt.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    } catch (e) { return false; }
  }

  function uploadFile(dataUrl, name, config) {
    if (config && config.selectors) {
      window.__VA_RUNTIME_CONFIG__ = config;
    }
    var file = dataUrlToFile(dataUrl, name || "image.png");
    var cfg = window.__VA_RUNTIME_CONFIG__;
    var selector = (cfg && cfg.selectors && cfg.selectors.fileInput) || null;
    if (!selector) {
      return { ok: false, error: "CIORA Authentication required: Missing dynamic runtime configuration" };
    }
    var input = document.querySelector(selector);
    if (!input) return { ok: false, error: "No file input found on this page" };
    var ok = injectFileIntoInput(input, file);
    return { ok: ok, fileName: file.name, fileSize: file.size, fileType: file.type };
  }

  // Read the three phase bars (0..100). Returns null if pane not in DOM yet.
  function readProgress() {
    var cfg = window.__VA_RUNTIME_CONFIG__;
    var bars = (cfg && cfg.progressBars) || null;
    if (!bars) return null;
    function pct(id) {
      var el = document.getElementById(id);
      if (!el) return null;
      var w = el.style.width || (el.getAttribute("style") || "");
      var m = ("" + w).match(/(\d+(?:\.\d+)?)\s*%/);
      if (m) return Math.max(0, Math.min(100, parseFloat(m[1])));
      return el.offsetWidth > 0 ? 100 : 0;
    }
    var u = pct(bars.upload);
    var p = pct(bars.process);
    var f = pct(bars.download);
    if (u == null && p == null && f == null) return null;
    return { upload: u || 0, process: p || 0, fetch: f || 0 };
  }

  // Detect captcha prompt
  function isCaptchaRequired() {
    var cfg = window.__VA_RUNTIME_CONFIG__;
    var capSel = (cfg && cfg.selectors && cfg.selectors.captchaContainer) || null;
    if (capSel && document.querySelector(capSel)) return true;
    var sigs = (cfg && cfg.captchaSignatures) || ["recaptcha", "hcaptcha", "turnstile"];
    var frames = document.querySelectorAll("iframe");
    for (var i = 0; i < frames.length; i++) {
      var src = (frames[i].src || "").toLowerCase();
      for (var s = 0; s < sigs.length; s++) {
        if (src.indexOf(sigs[s]) >= 0) {
          var r = frames[i].getBoundingClientRect();
          if (r.width > 50 && r.height > 50) return true;
        }
      }
    }
    return false;
  }

  function getCurrentImageId() {
    var m = location.pathname.match(/\/images\/([0-9a-f-]+)/i);
    return m ? m[1] : null;
  }

  function clickDownloadLink() {
    var cfg = window.__VA_RUNTIME_CONFIG__;
    var selector = (cfg && cfg.selectors && cfg.selectors.downloadLinks) || null;
    if (!selector) {
      return { ok: false, error: "CIORA Authentication required: Missing dynamic runtime configuration" };
    }
    var a = document.querySelector(selector);
    var resumeToken = (window.ResumeImage && window.ResumeImage.token) || null;
    if (a) {
      var visible = a.offsetParent !== null && a.getClientRects().length > 0;
      if (visible) {
        a.click();
        return { ok: true, via: "App-downloadLink.click" };
      }
      log("debug", "App-downloadLink present but hidden, falling back to direct nav");
    }
    var m = location.pathname.match(/\/images\/([^/]+)/);
    var token = resumeToken || (m && m[1]);
    if (token) {
      location.href = "/images/" + token;
      return { ok: true, via: "direct-nav", token: token };
    }
    return { ok: false, error: "No download link and no image token found" };
  }

  function submitDownload() {
    var cfg = window.__VA_RUNTIME_CONFIG__;
    if (!cfg || !cfg.selectors) {
      return { ok: false, error: "CIORA Authentication required: Missing dynamic runtime configuration" };
    }
    var topSel = cfg.selectors.submitTop;
    var botSel = cfg.selectors.submitBottom;
    var top = topSel ? document.querySelector(topSel) : null;
    if (top) {
      try { top.click(); return { ok: true, via: "Options-SubmitTop" }; } catch (e) {}
    }
    var sub = botSel ? document.querySelector(botSel) : null;
    if (sub) {
      try { sub.click(); return { ok: true, via: "Options-Submit" }; } catch (e) {}
    }
    return { ok: false, error: "No submit/download button found" };
  }

  function getPageInfo() {
    return {
      url: location.href,
      pathname: location.pathname,
      imageId: getCurrentImageId(),
      progress: readProgress(),
      captcha: isCaptchaRequired(),
      hasDownloadLink: !!document.querySelector("a.App-downloadLink"),
      hasOptionsForm: !!document.getElementById("Options-Form"),
      errorDialog: hasErrorDialog()
    };
  }

  function hasErrorDialog() {
    var cfg = window.__VA_RUNTIME_CONFIG__;
    var retrySel = (cfg && cfg.selectors && cfg.selectors.retryButton) || null;
    var modalSel = (cfg && cfg.selectors && cfg.selectors.modalContent) || null;
    var sigs = (cfg && cfg.errorSignatures) || ["too many rapid-fire", "slow down"];
    try {
      if (retrySel) {
        var btn = document.querySelector(retrySel);
        if (btn && btn.offsetParent !== null) {
          var modal = modalSel ? btn.closest(modalSel) : null;
          if (modal) return true;
        }
      }
      var modalEl = modalSel ? document.querySelector(modalSel) : null;
      if (!modalEl || modalEl.offsetParent === null) return false;
      var txt = (modalEl.textContent || "").trim().toLowerCase();
      return sigs.some(function (sig) { return txt.indexOf(sig) >= 0; });
    } catch (e) { return false; }
  }

  function hasPrecropDialog() {
    var cfg = window.__VA_RUNTIME_CONFIG__;
    var cropSel = (cfg && cfg.selectors && cfg.selectors.preCropButton) || null;
    try {
      var app = document.getElementById("PreCrop-App");
      if (!app) return false;
      var style = (app.getAttribute("style") || "").replace(/\s/g, "").toLowerCase();
      if (style.indexOf("display:block") === -1) return false;
      var cropBtn = cropSel ? document.querySelector(cropSel) : null;
      return !!cropBtn;
    } catch (e) { return false; }
  }

  function clickPrecropOk() {
    var cfg = window.__VA_RUNTIME_CONFIG__;
    var cropSel = (cfg && cfg.selectors && cfg.selectors.preCropButton) || null;
    try {
      var btn = cropSel ? document.querySelector(cropSel) : null;
      if (btn) {
        btn.click();
        return { ok: true };
      }
      return { ok: false, error: "No pre-crop button" };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }

  chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
    if (!msg || !msg.type) return;
    if (msg.config && msg.config.selectors) {
      window.__VA_RUNTIME_CONFIG__ = msg.config;
    }
    if (msg.type === "INITIALIZE_RUNTIME_CONFIG") {
      if (msg.config && msg.config.protocol && msg.config.selectors) {
        window.__VA_RUNTIME_CONFIG__ = msg.config;
        console.log('[Vector Assist] Dynamic Runtime config loaded (' + msg.config.protocol + ') ✓');
        sendResponse({ ok: true, status: "ok" });
      } else {
        sendResponse({ ok: false, status: "failed", message: "Invalid config signature" });
      }
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_GET_SETTINGS") {
      var data = readPageSettings();
      sendResponse({ settings: data });
      notifyPageChanged();
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_APPLY_SETTINGS") {
      applyToPage(msg.settings);
      notifyPageChanged();
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_UPLOAD_FILE") {
      sendResponse(uploadFile(msg.dataUrl, msg.name, msg.config));
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_GET_PROGRESS") {
      sendResponse({ progress: readProgress(), captcha: isCaptchaRequired(), imageId: getCurrentImageId(), url: location.href, errorDialog: hasErrorDialog(), precropDialog: hasPrecropDialog() });
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_GET_PAGE_INFO") {
      sendResponse(getPageInfo());
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_CLICK_DOWNLOAD_LINK") {
      sendResponse(clickDownloadLink());
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_NAVIGATE") {
      location.href = msg && msg.url ? msg.url : location.href;
      sendResponse({ ok: true });
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_SUBMIT_DOWNLOAD") {
      sendResponse(submitDownload());
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_HAS_SELECTOR") {
      sendResponse({ found: !!document.getElementById(msg.id) });
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_CLICK_RETRY") {
      var btn = document.getElementById("App-Error-RetryButton");
      if (btn) { try { btn.click(); } catch (e) {} sendResponse({ ok: true }); return true; }
      sendResponse({ ok: false, error: "No retry button" });
      return true;
    }
    if (msg.type === "VECTOR_ASSIST_CLICK_PRECROP_OK") {
      sendResponse(clickPrecropOk());
      return true;
    }
  });

  try { chrome.runtime.sendMessage({ type: "VECTOR_ASSIST_CONTENT_READY" }); } catch (e) {}
  expandAdvanced();
  startWatching();
})();

(function () {
  // Page-phase beacon: lets background.js know the latest pathname + ready state.
  function beacon() {
    try {
      chrome.runtime.sendMessage({
        type: "VECTOR_ASSIST_PAGE_PHASE",
        pathname: location.pathname,
        ready: !!document.getElementById("FileInput-Field") ||
              !!document.getElementById("Options-Form") ||
              !!document.querySelector("a.App-downloadLink"),
        ts: Date.now()
      });
    } catch (e) {}
  }
  // Fire on initial load, on history changes, and a few times in case the SPA
  // mutates after document_idle (e.g. viewer SPA mounts later).
  beacon();
  document.addEventListener("DOMContentLoaded", beacon);
  window.addEventListener("load", beacon);
  setTimeout(beacon, 500);
  setTimeout(beacon, 1500);
  setTimeout(beacon, 3000);
  var _pushState = history.pushState;
  history.pushState = function () { var r = _pushState.apply(this, arguments); beacon(); return r; };
  var _replaceState = history.replaceState;
  history.replaceState = function () { var r = _replaceState.apply(this, arguments); beacon(); return r; };
  window.addEventListener("popstate", beacon);
})();
