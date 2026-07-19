(function () {
  if (window.__VECTOR_ASSIST_CONTENT__) return;
  window.__VECTOR_ASSIST_CONTENT__ = true;

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

  // Set a radio group by clicking  Once, via the label.
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

  // Set a checkbox by clicking  Once, via the label. Let the SPA handle
  // any hidden companion inputs or model updates.
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
          // Inverted: extension's simpleShapes=true == visible.checked
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

    var baseDelay = parseInt(settings.delayMs, 10);
    if (!isFinite(baseDelay) || baseDelay < 0) baseDelay = 0;
    var jitter = parseInt(settings.delayJitterMs, 10);
    if (!isFinite(jitter) || jitter < 0) jitter = 0;
    function stepDelay() { return baseDelay + (jitter > 0 ? Math.floor(Math.random() * jitter) : 0); }

    // Collect the keys we will apply (skip format here; apply first separately).
    var keys = Object.keys(settings).filter(function (k) {
      return k !== "format" && k !== "scalePercent" && k !== "delayMs" && k !== "delayJitterMs";
    });

    function applyKey(key, cb) {
      var ourValue = settings[key];
      if (key === "simpleShapes") {
        var visible = document.getElementById("Options-SimpleShapesField");
        if (visible && visible.type === "checkbox") {
          var wantChecked = !ourValue; // inverted: represent shapes = !flatten
          if (visible.checked !== wantChecked) clickLabel(visible);
        }
        cb && cb();
        return;
      }
      var pageName = KEY_NAME[key];
      var els = getInputs(pageName);
      if (!els.length) { cb && cb(); return; }
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
      cb && cb();
    }

    function runSequential(i) {
      if (i >= keys.length) {
        // After all keys, apply scale if needed (last so it doesn't override).
        var targetMode = pageValueFor("outputSize", settings.outputSize);
        if (settings.scalePercent !== undefined && targetMode === "scale") setScale(settings.scalePercent);
        return;
      }
      applyKey(keys[i], function () {
        var wait = stepDelay();
        if (wait <= 0) runSequential(i + 1);
        else setTimeout(function () { runSequential(i + 1); }, wait);
      });
    }

    // Apply format first to reveal dependent sections, then the rest sequentially.
    if (settings.format !== undefined) setRadio(KEY_NAME.format, pageValueFor("format", settings.format));
    setTimeout(function () { runSequential(0); }, Math.max(150, baseDelay));
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

  chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
    if (!msg || !msg.type) return;
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
  });

  try { chrome.runtime.sendMessage({ type: "VECTOR_ASSIST_CONTENT_READY" }); } catch (e) {}
  expandAdvanced();
  startWatching();
})();
