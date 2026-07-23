// 3D Web Downloader — sidepanel controller (bundled with Three.js preview engine).
// Robust init, defensive wiring, ensure modal can always be closed.

import * as THREE from "./vendor/three.module.js";
import { GLTFLoader } from "./vendor/GLTFLoader.js";
import { OrbitControls } from "./vendor/OrbitControls.js";
import { RoomEnvironment } from "./vendor/RoomEnvironment.js";
import { DRACOLoader } from "./vendor/DRACOLoader.js";

const STORAGE_KEYS = {
  folder: "twdFolder",
  autoPreview: "twdAutoPreview",
  filters: "twdFilters",
};

const state = {
  assets: new Map(),
  downloaded: new Set(),
  filter: "",
  logBuffer: [],
  maxLogs: 500,
  booted: false,
  preview: { ready: false, init: null, render: null, reset: null },
};

const el = {};
const $ = (id) => document.getElementById(id);

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function log(level, message) {
  state.logBuffer.push({ time: new Date(), level, message });
  if (state.logBuffer.length > state.maxLogs) state.logBuffer.shift();
  renderLogs();
}

function renderLogs() {
  if (!el.logs) return;
  const q = (el.logFilter?.value || "").toLowerCase();
  el.logs.innerHTML = "";
  for (const l of state.logBuffer) {
    if (q && !l.message.toLowerCase().includes(q)) continue;
    const row = document.createElement("div");
    row.className = "twd-log-entry";
    const t = l.time.toTimeString().slice(0, 8);
    row.innerHTML = `<span class="twd-log-time">${t}</span><span class="twd-log-level ${l.level}">${l.level.toUpperCase()}</span><span>${escapeHtml(l.message)}</span>`;
    el.logs.appendChild(row);
  }
  if (el.logAutoscroll?.checked) el.logs.scrollTop = el.logs.scrollHeight;
}

function isDetected(asset) {
  if (!el.detGlb) return true;
  if (asset.ext === "glb") return el.detGlb.checked;
  if (asset.ext === "gltf") return el.detGltf.checked;
  if (asset.ext === "usdz") return el.detUsdz.checked;
  return true;
}

function upsertAsset(asset) {
  if (!asset) return;
  if (!isDetected(asset)) return;
  const existing = state.assets.get(asset.id);
  state.assets.set(asset.id, { ...existing, ...asset });
  log("info", `Detected ${asset.label}: ${asset.filename}`);
  renderList();
  updateStats();
  refreshPreviewOptions();
}

function renderList() {
  if (!el.list || !el.empty) return;
  const q = state.filter.toLowerCase();
  const items = [...state.assets.values()]
    .filter((a) =>
      !q ||
      a.filename.toLowerCase().includes(q) ||
      (a.origin || "").toLowerCase().includes(q) ||
      a.label.toLowerCase().includes(q) ||
      (a.source || "").toLowerCase().includes(q)
    )
    .sort((a, b) => (b.foundAt || 0) - (a.foundAt || 0));

  el.list.innerHTML = "";
  el.empty.hidden = items.length > 0;
  if (el.count) el.count.textContent = `${state.assets.size} found`;

  for (const asset of items) {
    const node = el.template.content.firstElementChild.cloneNode(true);
    node.dataset.id = asset.id;
    node.dataset.format = asset.ext;
    const fmtIcon = asset.ext === "glb" ? "▣" : asset.ext === "gltf" ? "◈" : asset.ext === "usdz" ? "◆" : "▤";
    const fmtLabel = asset.label || (asset.ext || "?").toUpperCase();
    node.querySelector(".twd-thumb-icon").textContent = fmtIcon;
    node.querySelector(".twd-thumb-fmt").textContent = fmtLabel;
    node.querySelector(".twd-item-name").textContent = asset.filename;
    node.querySelector(".twd-item-name").title = asset.filename;
    node.querySelector(".twd-item-badge").textContent = fmtLabel;
    node.querySelector(".twd-meta-ext").textContent = `.${asset.ext}`;
    node.querySelector(".twd-meta-host").textContent = asset.origin || "unknown";
    node.querySelector(".twd-meta-source").textContent = `via ${asset.source || "scan"}`;
    node.querySelector(".twd-item-url").textContent = asset.url;
    if (state.downloaded.has(asset.url)) node.classList.add("is-downloaded");

    const previewBtn = node.querySelector('[data-action="preview"]');
    const dlBtn = node.querySelector('[data-action="download"]');
    previewBtn.disabled = !asset.previewable;
    previewBtn.title = asset.previewable ? "Preview in 3D viewer" : "USDZ previews are not supported in Chrome";
    previewBtn.addEventListener("click", () => {
      openTab("preview");
      el.previewPicker.value = asset.id;
      if (state.preview.render) state.preview.render(asset);
    });
    dlBtn.addEventListener("click", () => downloadAsset(asset));
    el.list.appendChild(node);
  }
}

function updateStats() {
  const all = [...state.assets.values()];
  if (el.statTotal) el.statTotal.textContent = all.length;
  if (el.statGlb) el.statGlb.textContent = all.filter((a) => a.ext === "glb").length;
  if (el.statGltf) el.statGltf.textContent = all.filter((a) => a.ext === "gltf").length;
  if (el.statUsdz) el.statUsdz.textContent = all.filter((a) => a.ext === "usdz").length;
  if (el.statDone) el.statDone.textContent = state.downloaded.size;
}

function refreshPreviewOptions() {
  if (!el.previewPicker) return;
  const previewable = [...state.assets.values()].filter((a) => a.previewable);
  const current = el.previewPicker.value;
  el.previewPicker.innerHTML = "";
  if (previewable.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "No previewable assets yet";
    opt.disabled = true;
    el.previewPicker.appendChild(opt);
    return;
  }
  for (const a of previewable) {
    const opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = `${a.filename}  ·  ${a.origin}`;
    el.previewPicker.appendChild(opt);
  }
  if ([...el.previewPicker.options].some((o) => o.value === current)) {
    el.previewPicker.value = current;
  } else {
    el.previewPicker.selectedIndex = 0;
  }
}

function downloadAsset(asset) {
  // The configured subfolder is stored in chrome.storage.local and injected
  // by the background's onDeterminingFilename listener — Vector Assist's
  // pattern. We don't pass folder here.
  chrome.runtime.sendMessage({ type: "TWD_DOWNLOAD", asset }, () => void chrome.runtime.lastError);
  log("info", `Queued download for ${asset.filename}`);
}

function downloadAll() {
  const assets = [...state.assets.values()]
    .filter((a) => !state.downloaded.has(a.url));
  if (!assets.length) { log("warn", "Nothing to download"); return; }
  chrome.runtime.sendMessage({ type: "TWD_DOWNLOAD_BATCH", assets }, () => void chrome.runtime.lastError);
  log("info", `Queued ${assets.length} downloads`);
}

function openTab(name) {
  if (!el.tabs) return;
  el.tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  el.panes.forEach((p) => p.classList.toggle("active", p.dataset.pane === name));
  if (name === "preview") {
    refreshPreviewOptions();
    if (!el.previewPicker.value && el.previewPicker.options.length) {
      el.previewPicker.selectedIndex = 0;
    }
    const asset = state.assets.get(el.previewPicker.value);
    if (asset && state.preview.render) state.preview.render(asset);
  }
}

function showHelp(show) {
  if (!el.helpModal) return;
  el.helpModal.hidden = !show;
}

function fatal(message, err) {
  console.error("[3D Web Downloader]", message, err);
  let banner = $("twd-fatal");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "twd-fatal";
    banner.style.cssText = "background:var(--error);color:#fff;padding:10px 14px;font-size:12px;font-weight:600;text-align:center;white-space:pre-wrap;cursor:pointer;";
    banner.title = "Click to dismiss";
    banner.addEventListener("click", () => banner.remove());
    document.body.prepend(banner);
  }
  banner.textContent = `${message}: ${err?.message || err || "unknown"}`;
}

window.addEventListener("error", (e) => fatal("Runtime error", e.error || e.message));
window.addEventListener("unhandledrejection", (e) => fatal("Unhandled rejection", e.reason));

chrome.runtime.onMessage.addListener((msg) => {
  if (!msg) return;
  if (msg.type === "TWD_ASSET_FOUND" && msg.asset) {
    upsertAsset(msg.asset);
  } else if (msg.type === "TWD_DOWNLOAD_STARTED") {
    log("info", `Download started (id ${msg.downloadId})`);
  } else if (msg.type === "TWD_DOWNLOAD_COMPLETE") {
    state.downloaded.add(msg.url);
    log("success", `Downloaded ${msg.filename || msg.url}`);
    renderList();
    updateStats();
  } else if (msg.type === "TWD_DOWNLOAD_FAILED") {
    log("error", `Download failed: ${msg.error}`);
  } else if (msg.type === "TWD_TAB_CHANGED") {
    // Auto-clear and rescan on tab switch / navigation.
    handleTabChanged(msg.url, msg.reason);
  }
});

let lastTabUrl = null;
function handleTabChanged(url, reason = "change") {
  const skipReasons = ["activated"]; // tab focus alone shouldn't wipe the list
  const isSameUrl = url === lastTabUrl;
  lastTabUrl = url;

  // Always clear on these reasons even if the URL is unchanged.
  const forceClear = ["loading", "complete", "navigate", "closed"].includes(reason);

  if (isSameUrl && !forceClear) return;

  // Clear current list (assets are page-scoped).
  state.assets.clear();
  state.downloaded.clear();
  renderList();
  updateStats();
  refreshPreviewOptions();
  if (!url || /^chrome:|^about:|^edge:/.test(url)) {
    log("info", "Active tab has no scannable content");
    return;
  }
  log("info", `Tab ${reason} → rescan (${new URL(url).host})`);
  chrome.runtime.sendMessage({ type: "TWD_RESCAN_TAB" });
}

function loadSettings() {
  chrome.storage.local.get(
    {
      [STORAGE_KEYS.folder]: "3D-Web-Downloader",
      [STORAGE_KEYS.autoPreview]: true,
      [STORAGE_KEYS.filters]: { glb: true, gltf: true, usdz: true },
    },
    (v) => {
      if (el.folder) el.folder.value = v[STORAGE_KEYS.folder] || "3D-Web-Downloader";
      if (el.autoPreview) el.autoPreview.checked = !!v[STORAGE_KEYS.autoPreview];
      if (el.detGlb) el.detGlb.checked = v[STORAGE_KEYS.filters].glb !== false;
      if (el.detGltf) el.detGltf.checked = v[STORAGE_KEYS.filters].gltf !== false;
      if (el.detUsdz) el.detUsdz.checked = v[STORAGE_KEYS.filters].usdz !== false;
    }
  );
}

function saveSettings() {
  chrome.storage.local.set({
    [STORAGE_KEYS.folder]: el.folder?.value || "3D-Web-Downloader",
    [STORAGE_KEYS.autoPreview]: !!el.autoPreview?.checked,
    [STORAGE_KEYS.filters]: {
      glb: el.detGlb?.checked,
      gltf: el.detGltf?.checked,
      usdz: el.detUsdz?.checked,
    },
  });
}

// ============================================================
// Three.js preview engine (bundled)
// ============================================================
const previewModule = (() => {
  let renderer, scene, camera, controls, currentModel;
  let onInfo = () => {};
  const canvas = $("twd-preview-canvas");
  const placeholder = $("twd-preview-placeholder");
  const hint = $("twd-preview-hint");

  // Shared GLTFLoader instance with DRACO support for compressed meshes.
  const gltfLoader = new GLTFLoader();
  try {
    const draco = new DRACOLoader();
    draco.setDecoderPath(chrome.runtime.getURL("vendor/draco/"));
    draco.setDecoderConfig({ type: "wasm" });
    gltfLoader.setDRACOLoader(draco);
  } catch (err) {
    log("warn", `DRACOLoader unavailable: ${err?.message || err}`);
  }

  function emit(level, message) {
    log(level, message);
  }

  function init({ onInfo: cb } = {}) {
    onInfo = cb || (() => {});
    if (!canvas) { emit("error", "Preview canvas not found"); return; }

    // WebGL availability check.
    let supported = true;
    try {
      const probe = document.createElement("canvas");
      const gl = probe.getContext("webgl2") || probe.getContext("webgl");
      if (!gl) supported = false;
    } catch { supported = false; }
    if (!supported) {
      emit("error", "WebGL not available in this browser — preview disabled.");
      if (placeholder) placeholder.hidden = false;
      if (canvas) canvas.hidden = true;
      if (hint) hint.hidden = true;
      return;
    }

    try {
      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
      camera.position.set(2.5, 2, 3.5);

      renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.0;

      try {
        const pmrem = new THREE.PMREMGenerator(renderer);
        scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
      } catch { scene.environment = null; }

      scene.add(new THREE.AmbientLight(0xffffff, 0.55));

      // Three-point lighting so the model is well-lit from all sides.
      const key = new THREE.DirectionalLight(0xffffff, 1.4);
      key.position.set(3, 4, 5);
      scene.add(key);

      const fill = new THREE.DirectionalLight(0xb8d4ff, 0.6);
      fill.position.set(-4, 2, -3);
      scene.add(fill);

      const rim = new THREE.DirectionalLight(0xffffff, 0.5);
      rim.position.set(0, -3, -5);
      scene.add(rim);

      controls = new OrbitControls(camera, canvas);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.minDistance = 0.4;
      controls.maxDistance = 30;
    } catch (err) {
      emit("error", `3D engine init failed: ${err?.message || err}`);
      return;
    }

    function resize() {
      if (!renderer || !camera || !canvas) return;
      const parent = canvas.parentElement;
      if (!parent) return;
      const w = Math.max(1, parent.clientWidth);
      const h = Math.max(1, parent.clientHeight);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    window.addEventListener("resize", resize);
    if (window.ResizeObserver) {
      try { new ResizeObserver(resize).observe(canvas.parentElement); } catch {}
    }
    resize();
    animate();

    placeholder.hidden = false;
    canvas.hidden = true;
    hint.hidden = true;
    emit("success", "3D engine ready");
  }

  function animate() {
    requestAnimationFrame(animate);
    if (controls) controls.update();
    if (renderer && scene && camera) renderer.render(scene, camera);
  }

  function clearModel() {
    if (!scene) return;
    while (scene.children.length) {
      const obj = scene.children[0];
      scene.remove(obj);
      obj.traverse?.((n) => {
        if (n.isMesh) {
          n.geometry?.dispose();
          if (Array.isArray(n.material)) n.material.forEach((m) => m.dispose());
          else n.material?.dispose();
        }
      });
    }
  }

  function frameObject(object) {
    // Ensure all geometry has computed bounding boxes / spheres first.
    object.traverse?.((n) => {
      if (n.isMesh && n.geometry) {
        if (!n.geometry.boundingBox) n.geometry.computeBoundingBox();
        if (!n.geometry.boundingSphere) n.geometry.computeBoundingSphere();
      }
    });

    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    // Guard against zero-size / NaN / degenerate bounding boxes.
    const dims = [size.x, size.y, size.z].map((v) => (Number.isFinite(v) && v > 0 ? v : 1));
    const maxDim = Math.max(...dims);
    const minDim = Math.min(...dims);

    // Pick a stable frame distance that works for both tiny and huge models.
    const dist = Math.max(maxDim * 2.0, minDim * 8.0, 0.5);

    // Place camera at a 30-degree elevation for a flattering angle.
    camera.position.set(dist * 0.7, dist * 0.5, dist);
    camera.lookAt(center);

    // Adapt near/far to the model scale so close or huge models still render correctly.
    const near = Math.max(dist / 1000, 0.001);
    const far = Math.max(dist * 50, 100);
    camera.near = near;
    camera.far = far;
    camera.updateProjectionMatrix();

    controls.target.copy(center);
    controls.minDistance = Math.max(dist * 0.05, 0.01);
    controls.maxDistance = dist * 20;
    controls.update();
  }

  async function renderAsset(asset) {
    if (!asset) return;

    if (asset.ext === "usdz") {
      canvas.hidden = true;
      hint.hidden = true;
      placeholder.hidden = false;
      if (placeholder) placeholder.querySelector("div:last-child").textContent = "USDZ cannot be previewed in Chrome — use Download.";
      onInfo(`<b>${escapeHtml(asset.filename)}</b> · USDZ · ${escapeHtml(asset.origin || "")}<br/><span style="color:var(--text-dim)">Preview not supported in Chromium. Download the file to open in an AR viewer.</span>`);
      emit("warn", "USDZ preview not supported in Chrome");
      return;
    }

    if (!renderer) {
      onInfo(`<b style="color:var(--error)">3D engine not initialized</b>`);
      return;
    }

    placeholder.hidden = true;
    canvas.hidden = false;
    hint.hidden = false;
    onInfo(`<b>${escapeHtml(asset.filename)}</b> · ${asset.label} · ${escapeHtml(asset.origin || "")}`);

    clearModel();
    try {
      let gltf;
      let mode = "direct";
      try {
        const res = await chrome.runtime.sendMessage({ type: "TWD_FETCH_AS_BLOB", url: asset.url });
        if (res?.ok && res.buffer) {
          const blob = new Blob([res.buffer], { type: res.mime || "model/gltf-binary" });
          const objectUrl = URL.createObjectURL(blob);
          mode = "proxy";
          gltf = await gltfLoader.loadAsync(objectUrl);
          URL.revokeObjectURL(objectUrl);
        } else {
          throw new Error(res?.error || "Background fetch failed");
        }
      } catch (proxyErr) {
        const proxyMsg = proxyErr?.error || proxyErr?.message || String(proxyErr);
        emit("warn", `Proxy fetch failed (${proxyMsg}), trying direct…`);
        gltf = await gltfLoader.loadAsync(asset.url);
      }
      currentModel = gltf.scene;
      scene.add(currentModel);
      frameObject(currentModel);
      emit("success", `Previewing ${asset.filename} (${mode})`);
    } catch (err) {
      onInfo(`<b style="color:var(--error)">Preview failed</b><br/><small>${escapeHtml(err?.message || "Unknown error")}</small>`);
      canvas.hidden = true;
      hint.hidden = true;
      placeholder.hidden = false;
      if (placeholder) placeholder.querySelector("div:last-child").textContent = "Failed to load model";
      emit("error", `Preview failed for ${asset.filename}: ${err?.message || err}`);
    }
  }

  function resetCamera() {
    if (!currentModel) return;
    frameObject(currentModel);
  }

  return { init, renderAsset, resetCamera };
})();

// ============================================================
// Wiring
// ============================================================
function wire() {
  el.list = $("twd-list");
  el.empty = $("twd-empty");
  el.template = $("twd-item-template");
  el.search = $("twd-search");
  el.downloadAll = $("twd-download-all");
  el.clear = $("twd-clear");
  el.count = $("twd-count");
  el.version = $("twd-version");
  el.statTotal = $("twd-stat-total");
  el.statGlb = $("twd-stat-glb");
  el.statGltf = $("twd-stat-gltf");
  el.statUsdz = $("twd-stat-usdz");
  el.statDone = $("twd-stat-done");
  el.tabs = document.querySelectorAll(".twd-tab");
  el.panes = document.querySelectorAll(".twd-pane");
  el.folder = $("twd-folder");
  el.detGlb = $("twd-det-glb");
  el.detGltf = $("twd-det-gltf");
  el.detUsdz = $("twd-det-usdz");
  el.autoPreview = $("twd-auto-preview");
  el.logs = $("twd-logs");
  el.logFilter = $("twd-log-filter");
  el.logAutoscroll = $("twd-log-autoscroll");
  el.logClear = $("twd-log-clear");
  el.helpBtn = $("twd-help-btn");
  el.helpClose = $("twd-help-close");
  el.helpModal = $("twd-help-modal");
  el.previewPicker = $("twd-preview-picker");
  el.previewReset = $("twd-preview-reset");
  el.previewInfo = $("twd-preview-info");

  if (el.tabs) el.tabs.forEach((t) => t.addEventListener("click", () => openTab(t.dataset.tab)));
  if (el.search) el.search.addEventListener("input", () => { state.filter = el.search.value; renderList(); });

  if (el.downloadAll) el.downloadAll.addEventListener("click", downloadAll);

  if (el.clear) el.clear.addEventListener("click", () => {
    state.assets.clear();
    renderList();
    updateStats();
    refreshPreviewOptions();
    log("info", "Cleared asset list");
  });

  [el.folder, el.detGlb, el.detGltf, el.detUsdz, el.autoPreview].forEach((n) => {
    if (n) n.addEventListener("change", saveSettings);
  });

  if (el.previewPicker) el.previewPicker.addEventListener("change", () => {
    const a = state.assets.get(el.previewPicker.value);
    if (a && previewModule) previewModule.renderAsset(a);
  });

  if (el.previewReset) el.previewReset.addEventListener("click", () => {
    if (previewModule) previewModule.resetCamera();
  });

  if (el.logFilter) el.logFilter.addEventListener("input", renderLogs);
  if (el.logClear) el.logClear.addEventListener("click", () => { state.logBuffer = []; renderLogs(); });

  if (el.helpBtn) el.helpBtn.addEventListener("click", () => showHelp(true));
  if (el.helpClose) el.helpClose.addEventListener("click", () => showHelp(false));
  if (el.helpModal) el.helpModal.addEventListener("click", (e) => {
    if (e.target === el.helpModal) showHelp(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && el.helpModal && !el.helpModal.hidden) showHelp(false);
  });

  const manifest = chrome.runtime.getManifest?.();
  if (manifest?.version && el.version) el.version.textContent = `v${manifest.version}`;

  loadSettings();
  renderList();
  updateStats();
  refreshPreviewOptions();

  try {
    previewModule.init({ onInfo: (info) => { if (el.previewInfo) el.previewInfo.innerHTML = info; } });
  } catch (err) {
    log("error", `Preview engine init failed: ${err?.message || err}`);
  }

  log("success", "Side panel ready");
  state.booted = true;

  // Sync with the currently active tab so the list reflects the page
  // the user is looking at when the side panel opens.
  try {
    chrome.runtime.sendMessage({ type: "TWD_GET_ACTIVE_TAB" }, (r) => {
      void chrome.runtime.lastError;
      if (r?.url) handleTabChanged(r.url);
    });
  } catch {}
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    try { wire(); } catch (e) { fatal("Boot failed", e); }
  });
} else {
  try { wire(); } catch (e) { fatal("Boot failed", e); }
}