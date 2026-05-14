(() => {
  'use strict';
  const STORE_KEY = 'mpp_settings_v1';
  const $ = (id) => document.getElementById(id);

  let imageData = null;
  let fontImageData = null;
  let prompts = [];
  let analysis = '';
  let statuses = {};
  let selectedStyle = '';
  let detailLevel = 'medium';
  let strictColor = true;
  let autoSubmit = false;
  let isGenerating = false;
  let automationMode = 'flow';
  let injectorPoints = [
    { id: 1, type: 'paste', enabled: true, selector: '', delay: 1.0 },
    { id: 2, type: 'click', enabled: true, selector: '', delay: 1.0 }
  ];
  let injectorRunning = false;
  let injectorPaused = false;
  let injectorSessionId = null;
  let injectorDb = null;
  let currentInjectorUrlKey = 'site:default';

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    // Load extension version from manifest (same as auto-flow-batcher)
    try {
      const resp = await fetch('manifest.json');
      if (resp.ok) {
        const manifest = await resp.json();
        const el = $('extensionVersion');
        if (el && manifest.version) el.textContent = 'v' + manifest.version;
      }
    } catch (e) { console.warn('Could not load manifest version:', e); }

bindTabs();
     bindImageDrop();
     bindStyleSelect();
     bindDetailButtons();
     bindColorInputs();
     bindFontInputs();
     bindGenerateButton();
     bindLogButtons();
      bindAutoSubmitToggle();
      bindModeTabs();
      bindInjectorControls();
      bindInjectorPageAutoRefresh();
      bindApiModal();
      bindPersistenceInputs();
     await initInjectorDB();
     await updateInjectorPageSettings();
    loadSettings();
    chrome.runtime.onMessage.addListener(onRuntimeMessage);
    appendLog('Extension loaded.', 'info');
  }

  // ── Tabs ──────────────────────────────────────────────────────────────────
  function bindTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        $('tab-' + btn.dataset.tab).classList.add('active');
      });
    });
  }

  // ── Image Drop Zone ───────────────────────────────────────────────────────
  function bindImageDrop() {
    const zone = $('imageDropZone');
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragging'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
    zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('dragging'); handleImageFile(e.dataTransfer.files?.[0], 'main'); });
    const fi = $('imageFileInput');
    if (fi) fi.addEventListener('change', e => handleImageFile(e.target.files?.[0], 'main'));

    // Paste button for main image
    const pasteMain = $('btnPasteMainImage');
    if (pasteMain) pasteMain.addEventListener('click', async e => {
      e.stopPropagation();
      await pasteFromClipboard('main');
    });

    // Paste button for font image
    const pasteFont = $('btnPasteFontImage');
    if (pasteFont) pasteFont.addEventListener('click', async e => {
      e.stopPropagation();
      await pasteFromClipboard('font');
    });

    // Ctrl+V global paste
    window.addEventListener('paste', e => {
      const item = Array.from(e.clipboardData?.items || []).find(i => i.type.startsWith('image/'));
      if (!item) return;
      const active = document.activeElement;
      const target = active && active.closest('#fontUploadArea') ? 'font' : 'main';
      handleImageFile(item.getAsFile(), target);
    });
  }

  async function pasteFromClipboard(target) {
    try {
      const items = await navigator.clipboard.read();
      for (const item of items) {
        for (const type of item.types) {
          if (type.startsWith('image/')) {
            const blob = await item.getType(type);
            const file = new File([blob], 'pasted.png', { type });
            handleImageFile(file, target);
            return;
          }
        }
      }
      appendLog('No image found in clipboard. Try Ctrl+V instead.', 'warn');
    } catch (e) {
      appendLog('Clipboard access denied. Use Ctrl+V to paste.', 'warn');
    }
  }

  function handleImageFile(file, target) {
    if (!file || !file.type.startsWith('image/')) return;
    const r = new FileReader();
    r.onload = () => {
      if (target === 'font') { fontImageData = r.result; renderFontImage(); }
      else { imageData = r.result; renderMainImage(); }
      saveSettings();
    };
    r.readAsDataURL(file);
  }

  function renderMainImage() {
    const zone = $('imageDropZone');
    if (imageData) {
      zone.classList.add('has-image');
      zone.innerHTML = `<img class="preview-img" src="${imageData}"><div class="image-overlay-actions"><button class="image-action-btn" id="pasteMainImg" title="Paste and replace reference">Paste</button><button class="image-action-btn danger" id="clearMainImg" title="Remove reference">✕</button></div>`;
      $('pasteMainImg').onclick = async e => { e.stopPropagation(); await pasteFromClipboard('main'); };
      $('clearMainImg').onclick = e => { e.stopPropagation(); imageData = null; renderMainImage(); saveSettings(); };
    } else {
      zone.classList.remove('has-image');
      zone.innerHTML = `
        <svg class="drop-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>
        <span class="drop-text">Drop or paste reference image here</span>
        <div class="drop-actions">
          <button class="drop-paste-btn" id="btnPasteMainImage" title="Paste from clipboard">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
            Paste
          </button>
        </div>
        <input type="file" id="imageFileInput" accept="image/*">`;
      $('imageFileInput').addEventListener('change', e => handleImageFile(e.target.files?.[0], 'main'));
      const pb = $('btnPasteMainImage');
      if (pb) pb.addEventListener('click', async e => { e.stopPropagation(); await pasteFromClipboard('main'); });
    }
  }

  function renderFontImage() {
    const area = $('fontUploadArea');
    if (fontImageData) {
      area.innerHTML = `<button class="clear-btn" id="clearFontImg" style="position:absolute;top:4px;right:4px;">x</button><img src="${fontImageData}" style="max-height:40px;max-width:100%;border-radius:4px;">`;
      $('clearFontImg').onclick = e => { e.stopPropagation(); fontImageData = null; renderFontImage(); saveSettings(); };
    } else {
      area.innerHTML = `
        <div class="font-upload-header">
          <span class="placeholder">Font / Typography Reference</span>
          <button class="drop-paste-btn" id="btnPasteFontImage" title="Paste from clipboard">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
            Paste
          </button>
        </div>
        <input type="file" id="fontFileInput" accept="image/*">`;
      $('fontFileInput').addEventListener('change', e => handleImageFile(e.target.files?.[0], 'font'));
      const pb = $('btnPasteFontImage');
      if (pb) pb.addEventListener('click', async e => { e.stopPropagation(); await pasteFromClipboard('font'); });
    }
  }

// ── Style Select ───────────────────────────────────────────────────────────
  function bindStyleSelect() {
    const sel = $('paramVisualStyle');
    if (sel) {
      sel.addEventListener('change', () => {
        selectedStyle = sel.value;
        const cs = $('paramCustomStyle');
        if (cs) cs.classList.toggle('hidden', selectedStyle !== 'Custom');
        saveSettings();
      });
    }
  }

  function updateStyleSelectUI() {
    const sel = $('paramVisualStyle');
    if (sel) sel.value = selectedStyle;
    const cs = $('paramCustomStyle');
    if (cs) cs.classList.toggle('hidden', selectedStyle !== 'Custom');
  }

  // ── Detail Level ──────────────────────────────────────────────────────────
  function bindDetailButtons() {
    document.querySelectorAll('.detail-btn').forEach(b => {
      b.addEventListener('click', () => { detailLevel = b.dataset.level; updateDetailUI(); saveSettings(); });
    });
  }
  function updateDetailUI() {
    document.querySelectorAll('.detail-btn').forEach(b => b.classList.toggle('active', b.dataset.level === detailLevel));
  }

  // ── API Settings Modal ───────────────────────────────────────────────────
  function bindApiModal() {
    const btn = $('btnApiSettings');
    const modal = $('apiSettingsModal');
    const close = $('modalClose');
    const save = $('btnSaveApi');

    const openModal = () => {
      $('apiProviderModal').value = $('apiProvider')?.value || 'gemini';
      $('apiKeyModal').value = $('apiKey')?.value || '';
      $('apiEndpointModal').value = $('apiEndpoint')?.value || '';
      $('apiModelModal').value = $('apiModel')?.value || '';
      modal.classList.remove('hidden');
    };

    const closeModal = () => modal.classList.add('hidden');

    if (btn) btn.addEventListener('click', openModal);
    if (close) close.addEventListener('click', closeModal);
    if (modal) modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

    if (save) save.addEventListener('click', () => {
      if ($('apiProvider')) $('apiProvider').value = $('apiProviderModal').value;
      if ($('apiKey')) $('apiKey').value = $('apiKeyModal').value;
      if ($('apiEndpoint')) $('apiEndpoint').value = $('apiEndpointModal').value;
      if ($('apiModel')) $('apiModel').value = $('apiModelModal').value;
      saveSettings();
      closeModal();
      appendLog('API settings saved.', 'success');
    });

    ['apiProviderModal','apiKeyModal','apiEndpointModal','apiModelModal'].forEach(id => {
      const el = $(id);
      if (el) el.addEventListener('input', () => {
        if ($('apiProvider') && id === 'apiProviderModal') $('apiProvider').value = el.value;
        if ($('apiKey') && id === 'apiKeyModal') $('apiKey').value = el.value;
        if ($('apiEndpoint') && id === 'apiEndpointModal') $('apiEndpoint').value = el.value;
        if ($('apiModel') && id === 'apiModelModal') $('apiModel').value = el.value;
      });
    });
  }

  // ── Color Inputs ──────────────────────────────────────────────────────────
  function bindColorInputs() {
    ['color60','color30','color10'].forEach(id => {
      const el = $(id);
      const swatch = $('swatch' + id.replace('color', ''));
      if (el) {
        el.addEventListener('input', () => {
          syncColorVal(id);
          updateSwatch(id, el.value);
          saveSettings();
        });
      }
      if (swatch) {
        swatch.addEventListener('click', () => {
          el?.click();
        });
      }
    });
    const toggle = $('toggleStrictColor');
    if (toggle) toggle.addEventListener('click', () => {
      strictColor = !strictColor;
      toggle.classList.toggle('active', strictColor);
      saveSettings();
    });
    const rand = $('btnRandomColors');
    if (rand) rand.addEventListener('click', () => {
      ['color60','color30','color10'].forEach(id => {
        const el = $(id);
        if (el) {
          el.value = '#' + Math.floor(Math.random()*16777215).toString(16).padStart(6,'0');
          syncColorVal(id);
          updateSwatch(id, el.value);
        }
      });
      saveSettings();
    });
  }
  function updateSwatch(id, color) {
    const swatch = $('swatch' + id.replace('color', ''));
    if (swatch) {
      swatch.style.background = color;
      const isLightBg = getContrastYIQ(color) === 'light';
      swatch.classList.toggle('light-text', !isLightBg);
      swatch.classList.toggle('dark-text', isLightBg);
    }
  }
  function getContrastYIQ(hexcolor) {
    hexcolor = hexcolor.replace('#', '');
    const r = parseInt(hexcolor.substr(0,2), 16);
    const g = parseInt(hexcolor.substr(2,2), 16);
    const b = parseInt(hexcolor.substr(4,2), 16);
    const yiq = (r*299 + g*587 + b*114) / 1000;
    return (yiq >= 128) ? 'light' : 'dark';
  }
  function syncColorVal(id) {
    const el = $(id), val = $(id + 'Val');
    if (el && val) val.textContent = el.value;
  }
  function syncAllColors() { ['color60','color30','color10'].forEach(syncColorVal); }

  // ── Font Inputs ───────────────────────────────────────────────────────────
  function bindFontInputs() {
    const fs = $('paramFontStyle');
    if (fs) fs.addEventListener('change', () => {
      const cf = $('paramCustomFont');
      if (cf) cf.classList.toggle('hidden', fs.value !== 'Custom Description');
      saveSettings();
    });
  }

  // ── Generate Button ───────────────────────────────────────────────────────
  function bindGenerateButton() {
    const btn = $('btnGenerate');
    if (btn) btn.addEventListener('click', generatePrompts);
  }

  // ── Log Buttons ───────────────────────────────────────────────────────────
  function bindLogButtons() {
    const copy = $('btnCopyLogs'), clear = $('btnClearLogs'), log = $('logArea');
    if (copy) copy.addEventListener('click', () => navigator.clipboard.writeText(log?.innerText || ''));
    if (clear) clear.addEventListener('click', () => { if (log) log.innerHTML = ''; appendLog('Logs cleared.', 'info'); });
  }

  // ── Auto Submit Toggle ────────────────────────────────────────────────────
  function bindAutoSubmitToggle() {
    const toggle = $('toggleAutoSubmit');
    if (toggle) toggle.addEventListener('click', () => {
      autoSubmit = !autoSubmit;
      toggle.classList.toggle('active', autoSubmit);
      saveSettings();
    });
  }

  // ── Automation Mode / Universal Injector ──────────────────────────────────
  function getUrlKey(urlString) {
    try {
      const url = new URL(urlString);
      return `site:${url.hostname}`;
    } catch (_) {
      return 'site:default';
    }
  }

  async function initInjectorDB() {
    return new Promise(resolve => {
      const req = indexedDB.open('MockupPreviewPromptDB', 1);
      req.onerror = () => resolve();
      req.onsuccess = e => { injectorDb = e.target.result; resolve(); };
      req.onupgradeneeded = e => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('settings')) db.createObjectStore('settings', { keyPath: 'id' });
      };
    });
  }

  async function saveInjectorToDB(key, value) {
    if (!injectorDb) return;
    return new Promise(resolve => {
      const tx = injectorDb.transaction(['settings'], 'readwrite');
      tx.objectStore('settings').put({ id: key, value });
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
    });
  }

  async function loadInjectorFromDB(key) {
    if (!injectorDb) return null;
    return new Promise(resolve => {
      const tx = injectorDb.transaction(['settings'], 'readonly');
      const req = tx.objectStore('settings').get(key);
      req.onsuccess = () => resolve(req.result?.value || null);
      req.onerror = () => resolve(null);
    });
  }

  async function getActiveUsableTab() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) return null;
    return tab;
  }

  async function updateInjectorPageSettings() {
    const tab = await getActiveUsableTab();
    const urlText = $('injector-current-url');
    if (!tab) {
      currentInjectorUrlKey = 'site:default';
      if (urlText) {
        urlText.textContent = 'No supported page detected';
        urlText.title = '';
      }
      return;
    }
    const nextUrlKey = getUrlKey(tab.url);
    const changed = nextUrlKey !== currentInjectorUrlKey;
    currentInjectorUrlKey = nextUrlKey;
    if (urlText) {
      urlText.textContent = new URL(tab.url).hostname;
      urlText.title = tab.url;
    }
    const saved = await loadInjectorFromDB(`injector:${currentInjectorUrlKey}`);
    if (saved) applyInjectorConfig(saved);
    else applyInjectorConfig({ points: normalizeFixedInjectorPoints([]), autoDownload: {} });
    syncInjectorToUI();
    if (changed && automationMode === 'injector') appendLog(`Loaded injector settings for: ${new URL(tab.url).hostname}`, 'info');
  }

  async function saveCurrentInjectorSettings() {
    await updateInjectorUrlKeyOnly();
    await saveInjectorToDB(`injector:${currentInjectorUrlKey}`, getInjectorConfig());
  }

  async function updateInjectorUrlKeyOnly() {
    const tab = await getActiveUsableTab();
    if (tab?.url) currentInjectorUrlKey = getUrlKey(tab.url);
  }

  function applyInjectorConfig(config) {
    if (!config) return;
    injectorPoints = normalizeFixedInjectorPoints(config.points);
    const ad = config.autoDownload || {};
    if ($('auto-download-enabled')) $('auto-download-enabled').checked = ad.enabled === true;
    if ($('auto-download-count')) $('auto-download-count').value = ad.count || 2;
    if ($('auto-download-delay')) $('auto-download-delay').value = ad.delay || 5;
    if ($('auto-download-monitoring')) $('auto-download-monitoring').checked = ad.monitoring === true;
    if ($('auto-download-pattern')) $('auto-download-pattern').value = ad.pattern || '';
    if ($('auto-download-extension')) $('auto-download-extension').value = ad.extension || 'jpg';
    if ($('auto-download-prefix')) $('auto-download-prefix').value = ad.prefix || 'Mockup_Preview';
  }

  function normalizeFixedInjectorPoints(points) {
    const source = Array.isArray(points) ? points : [];
    const p1 = source.find(p => p.id === 1) || {};
    const p2 = source.find(p => p.id === 2) || {};
    return [
      { id: 1, type: 'paste', enabled: p1.enabled !== false, selector: p1.selector || '', delay: parseFloat(p1.delay ?? 1) || 0 },
      { id: 2, type: 'click', enabled: p2.enabled !== false, selector: p2.selector || '', delay: parseFloat(p2.delay ?? 1) || 0 }
    ];
  }

  function bindModeTabs() {
    document.querySelectorAll('.mode-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        automationMode = btn.dataset.modeTab || 'flow';
        updateModeUI();
        if (automationMode === 'injector') updateInjectorPageSettings();
        saveSettings();
      });
    });
  }

  function updateModeUI() {
    document.querySelectorAll('.mode-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.modeTab === automationMode));
    document.querySelectorAll('.mode-panel').forEach(p => p.classList.remove('active'));
    $('mode-panel-' + automationMode)?.classList.add('active');
  }

  function bindInjectorPageAutoRefresh() {
    chrome.tabs.onActivated.addListener(() => {
      updateInjectorPageSettings().catch(e => appendLog('Injector page update failed: ' + e.message, 'warn'));
    });
    chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
      if (changeInfo.status !== 'complete') return;
      updateInjectorPageSettings().catch(e => appendLog('Injector page update failed: ' + e.message, 'warn'));
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) return;
      updateInjectorPageSettings().catch(e => appendLog('Injector page update failed: ' + e.message, 'warn'));
    });
    window.addEventListener('focus', () => {
      updateInjectorPageSettings().catch(e => appendLog('Injector page update failed: ' + e.message, 'warn'));
    });
  }

  function bindInjectorControls() {
    const refresh = $('btn-refresh-injector-page');
    if (refresh) refresh.addEventListener('click', async () => { await updateInjectorPageSettings(); appendLog('Injector page settings refreshed.', 'info'); });
    const patternPicker = $('btn-pick-pattern');
    if (patternPicker) patternPicker.addEventListener('click', async () => {
      try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab?.id || !tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) return appendLog('Cannot pick pattern on this page.', 'error');
        await ensureContentScript(tab.id);
        chrome.tabs.sendMessage(tab.id, { type: 'START_PATTERN_PICKER' }, res => {
          if (chrome.runtime.lastError) appendLog('Pattern picker failed: ' + chrome.runtime.lastError.message, 'error');
          else if (res?.pattern) {
            $('auto-download-pattern').value = res.pattern;
            appendLog('URL pattern extracted: ' + res.pattern, 'success');
            saveCurrentInjectorSettings();
          } else appendLog('No image selected or URL pattern not found.', 'warn');
        });
      } catch (e) { appendLog('Pattern picker error: ' + e.message, 'error'); }
    });
    ['auto-download-enabled','auto-download-count','auto-download-delay','auto-download-monitoring','auto-download-pattern','auto-download-extension','auto-download-prefix','point1-enabled','point1-selector','point1-delay','point2-enabled','point2-selector','point2-delay'].forEach(id => {
      const el = $(id);
      if (!el) return;
      const persist = () => { syncInjectorFromUI(); saveCurrentInjectorSettings(); };
      el.addEventListener('input', persist);
      el.addEventListener('change', persist);
    });
    document.querySelectorAll('.picker-btn[data-point]').forEach(btn => btn.addEventListener('click', async () => {
      await updateInjectorUrlKeyOnly();
      pickElement(parseInt(btn.dataset.point || '1'));
    }));
  }

  function addInjectorPoint(point) {
    const nextId = point?.id || Math.max(1, ...injectorPoints.map(p => p.id)) + 1;
    injectorPoints.push(point || { id: nextId, type: 'click', enabled: true, selector: '', delay: 1.0 });
    renderInjectorPoints();
  }

  function renderInjectorPoints() {
    const c = $('dynamic-points-container');
    if (!c) return;
    c.innerHTML = injectorPoints.filter(p => p.id !== 1).map(p => `
      <div class="point-row" data-point-row="${p.id}">
        <div class="point-header">
          <input type="checkbox" class="dyn-point-enabled" data-point="${p.id}" ${p.enabled !== false ? 'checked' : ''}>
          <span class="point-label">Point ${p.id}</span><span class="point-note">(click)</span>
          <button class="prompt-clear-btn dyn-point-remove" data-point="${p.id}" style="margin-left:auto;">Remove</button>
        </div>
        <div class="point-controls">
          <input type="text" class="selector-input dyn-point-selector" data-point="${p.id}" value="${escapeHtml(p.selector || '')}" placeholder="CSS selector...">
          <button class="picker-btn dyn-picker" data-point="${p.id}" title="Pick element from page">Pick</button>
        </div>
        <div class="delay-row"><label>Delay:</label><input type="number" class="delay-input dyn-point-delay" data-point="${p.id}" value="${p.delay ?? 1}" min="0" step="0.1"><span class="unit">s</span></div>
      </div>`).join('');
    c.querySelectorAll('.dyn-picker').forEach(b => b.addEventListener('click', () => pickElement(parseInt(b.dataset.point))));
    c.querySelectorAll('.dyn-point-remove').forEach(b => b.addEventListener('click', () => { injectorPoints = injectorPoints.filter(p => p.id !== parseInt(b.dataset.point)); renderInjectorPoints(); saveSettings(); }));
    c.querySelectorAll('.dyn-point-enabled,.dyn-point-selector,.dyn-point-delay').forEach(el => {
      el.addEventListener('input', () => { syncInjectorFromUI(); saveSettings(); });
      el.addEventListener('change', () => { syncInjectorFromUI(); saveSettings(); });
    });
    syncInjectorToUI();
  }

  function syncInjectorToUI() {
    injectorPoints = normalizeFixedInjectorPoints(injectorPoints);
    const p1 = injectorPoints.find(p => p.id === 1);
    const p2 = injectorPoints.find(p => p.id === 2);
    if (p1) {
      if ($('point1-enabled')) $('point1-enabled').checked = p1.enabled !== false;
      if ($('point1-selector')) $('point1-selector').value = p1.selector || '';
      if ($('point1-delay')) $('point1-delay').value = p1.delay ?? 1;
    }
    if (p2) {
      if ($('point2-enabled')) $('point2-enabled').checked = p2.enabled !== false;
      if ($('point2-selector')) $('point2-selector').value = p2.selector || '';
      if ($('point2-delay')) $('point2-delay').value = p2.delay ?? 1;
    }
  }

  function syncInjectorFromUI() {
    injectorPoints = [
      {
        id: 1,
        type: 'paste',
        enabled: $('point1-enabled')?.checked !== false,
        selector: $('point1-selector')?.value || '',
        delay: parseFloat($('point1-delay')?.value || '1') || 0
      },
      {
        id: 2,
        type: 'click',
        enabled: $('point2-enabled')?.checked !== false,
        selector: $('point2-selector')?.value || '',
        delay: parseFloat($('point2-delay')?.value || '1') || 0
      }
    ];
  }

  async function pickElement(pointIndex) {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || !tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) return appendLog('Cannot pick element on this page.', 'error');
      await ensureContentScript(tab.id);
      chrome.tabs.sendMessage(tab.id, { type: 'START_PICKER', pointIndex }, res => {
        if (chrome.runtime.lastError) appendLog('Picker failed: ' + chrome.runtime.lastError.message, 'error');
        else appendLog(`Picker started for Point ${pointIndex}. Click target element on page.`, 'act');
      });
    } catch (e) { appendLog('Picker error: ' + e.message, 'error'); }
  }

  function extractUrlPattern(url) {
    try {
      if (url.startsWith('blob:')) {
        const afterBlob = url.slice(5);
        const match = afterBlob.match(/^(https?:\/\/[^\/]+)/);
        if (match) {
          return 'blob:' + match[1];
        }
        return 'blob:' + afterBlob.split('/')[0];
      }
      const u = new URL(url);
      let path = u.pathname;
      const segments = path.split('/').filter(s => s);
      if (segments.length > 0 && segments[segments.length - 1].includes('.')) {
        segments.pop();
      }
      const lastSeg = segments.length > 0 ? segments[segments.length - 1] : '';
      if (lastSeg && (lastSeg.length > 30 || lastSeg.includes('_') || /^\d+$/.test(lastSeg))) {
        segments.pop();
      }
      if (u.search) {
        const params = new URLSearchParams(u.search);
        params.delete('id');
        params.delete('ts');
        params.delete('cid');
        params.delete('sig');
        params.delete('p');
        params.delete('v');
        params.delete('name');
        const cleanQuery = params.toString();
        return u.origin + (segments.length ? '/' + segments.join('/') : '') + (cleanQuery ? '?' + cleanQuery : '');
      }
      return u.origin + (segments.length ? '/' + segments.join('/') : '');
    } catch (e) {
      return url;
    }
  }

  function getInjectorConfig() {
    syncInjectorFromUI();
    return {
      points: injectorPoints.map(p => ({ ...p })),
      autoDownload: {
        enabled: $('auto-download-enabled')?.checked === true,
        count: parseInt($('auto-download-count')?.value || '2') || 2,
        delay: parseInt($('auto-download-delay')?.value || '5') || 5,
        monitoring: $('auto-download-monitoring')?.checked === true,
        pattern: $('auto-download-pattern')?.value || '',
        extension: $('auto-download-extension')?.value || 'jpg',
        prefix: $('auto-download-prefix')?.value || 'Mockup_Preview'
      }
    };
  }

  async function runInjectorPrompt(i) {
    if (!prompts[i]) return;
    if (injectorRunning) return appendLog('Injector automation already running.', 'warn');
    const tab = await getActiveUsableTab();
    if (!tab?.id) return appendLog('No active target page found. Open/select the target generator page first.', 'error');
    currentInjectorUrlKey = getUrlKey(tab.url);
    const saved = await loadInjectorFromDB(`injector:${currentInjectorUrlKey}`);
    if (saved) applyInjectorConfig(saved);
    else syncInjectorFromUI();
    syncInjectorToUI();
    const config = getInjectorConfig();
    config.promptOffset = i;
    if (!config.points.some(p => p.enabled && p.selector)) return appendLog(`No injector points saved for ${new URL(tab.url).hostname}. Pick Entry Prompt and Submit Button first.`, 'error');
    if (!config.points.find(p => p.id === 1)?.selector) return appendLog('Entry Prompt selector is required for this page.', 'error');
    if (!config.points.find(p => p.id === 2)?.selector) return appendLog('Submit Button selector is required for this page.', 'error');
    injectorRunning = true; injectorPaused = false; injectorSessionId = 'mpp-injector-' + Date.now();
    statuses[i] = config.autoDownload.enabled ? 'monitoring' : 'inserting';
    renderPrompts();
    await ensureContentScript(tab.id);
    chrome.tabs.sendMessage(tab.id, { type: 'START_AUTOMATION', config, prompts: [prompts[i]], sessionId: injectorSessionId }, res => {
      if (chrome.runtime.lastError) { appendLog('Injector start failed: ' + chrome.runtime.lastError.message, 'error'); injectorRunning = false; statuses[i] = 'failed'; renderPrompts(); }
      else appendLog(`Universal injector started for prompt #${i+1}.`, 'success');
    });
  }

  async function stopInjectorAutomation(promptIndex = null) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) chrome.tabs.sendMessage(tab.id, { type: 'STOP_AUTOMATION', sessionId: injectorSessionId });
    injectorRunning = false; injectorPaused = false; injectorSessionId = null;
    // statuses is an object, not an array. Force-clear active injector UI state immediately.
    if (Number.isInteger(promptIndex)) {
      if (statuses[promptIndex] === 'monitoring' || statuses[promptIndex] === 'inserting') statuses[promptIndex] = 'failed';
    }
    Object.keys(statuses).forEach(key => {
      if (statuses[key] === 'monitoring' || statuses[key] === 'inserting') statuses[key] = 'failed';
    });
    renderPrompts();
    appendLog('Universal injector stopped.', 'info');
  }


  function bindPersistenceInputs() {
    ['paramTitle','paramSubtitle','paramContext','paramCustomStyle','paramCustomFont','apiProvider','apiKey','apiEndpoint','apiModel'].forEach(id => {
      const el = $(id); if (el) el.addEventListener('input', saveSettings);
    });
    document.querySelectorAll('input[name="ratio"],input[name="quality"],input[name="batch"]').forEach(el => el.addEventListener('change', saveSettings));
    const fs = $('paramFontStyle'); if (fs) fs.addEventListener('change', saveSettings);
    const vs = $('paramVisualStyle'); if (vs) vs.addEventListener('change', saveSettings);
    const countInput = $('paramCount');
    if (countInput) {
      countInput.addEventListener('input', () => {
        const val = $('paramCountVal');
        if (val) val.textContent = countInput.value;
        saveSettings();
      });
    }
  }

  // ── Settings persistence ──────────────────────────────────────────────────
  function getSettings() {
    const fs = $('paramFontStyle');
    const fontStyleVal = fs ? (fs.value === 'Custom Description' ? 'Custom: ' + ($('paramCustomFont')?.value || '') : fs.value) : 'Auto/Mimic Reference';
    return {
      title: $('paramTitle')?.value || '',
      subtext: $('paramSubtitle')?.value || '',
      additionalContext: $('paramContext')?.value || '',
      count: parseInt($('paramCount')?.value || '3'),
      selectedStyle,
      customStyle: $('paramCustomStyle')?.value || '',
      fontStyle: fontStyleVal,
      customFont: $('paramCustomFont')?.value || '',
      length: detailLevel,
      color60: $('color60')?.value || '#3b82f6',
      color30: $('color30')?.value || '#ffffff',
      color10: $('color10')?.value || '#fbbf24',
      strictColor,
      autoSubmit,
      ratio: document.querySelector('input[name="ratio"]:checked')?.value || '16:9',
      downloadQuality: document.querySelector('input[name="quality"]:checked')?.value || 'default',
      batch: document.querySelector('input[name="batch"]:checked')?.value || '4',
      provider: $('apiProvider')?.value || 'gemini',
      apiKey: $('apiKey')?.value || '',
      endpoint: $('apiEndpoint')?.value?.trim() || '',
      model: $('apiModel')?.value?.trim() || '',
      imageData,
      fontImageData,
      prompts,
      statuses,
      analysis,
      automationMode
    };
  }

  async function saveSettings() {
    try { await chrome.storage.local.set({ [STORE_KEY]: getSettings() }); } catch (_) {}
  }

  async function loadSettings() {
    try {
      const data = await chrome.storage.local.get(STORE_KEY);
      const s = data[STORE_KEY] || {};
      if ($('paramTitle')) $('paramTitle').value = s.title || '';
      if ($('paramSubtitle')) $('paramSubtitle').value = s.subtext || '';
      if ($('paramContext')) $('paramContext').value = s.additionalContext || '';
      if ($('paramCount')) { $('paramCount').value = s.count || 3; if ($('paramCountVal')) $('paramCountVal').textContent = s.count || 3; }
      selectedStyle = s.selectedStyle || '';
      if ($('paramCustomStyle')) $('paramCustomStyle').value = s.customStyle || '';
      const vs = $('paramVisualStyle');
      if (vs) vs.value = s.selectedStyle || '';
      const fs = $('paramFontStyle');
      if (fs) fs.value = s.fontStyle?.startsWith('Custom:') ? 'Custom Description' : (s.fontStyle || 'Auto/Mimic Reference');
      if ($('paramCustomFont')) $('paramCustomFont').value = s.customFont || '';
      detailLevel = s.length || 'medium';
      strictColor = s.strictColor !== false;
      autoSubmit = s.autoSubmit === true;
      if ($('color60')) { $('color60').value = s.color60 || '#3b82f6'; updateSwatch('color60', s.color60 || '#3b82f6'); }
      if ($('color30')) { $('color30').value = s.color30 || '#ffffff'; updateSwatch('color30', s.color30 || '#ffffff'); }
      if ($('color10')) { $('color10').value = s.color10 || '#fbbf24'; updateSwatch('color10', s.color10 || '#fbbf24'); }
      if ($('apiProvider')) $('apiProvider').value = s.provider || 'gemini';
      if ($('apiKey')) $('apiKey').value = s.apiKey || '';
      if ($('apiEndpoint')) $('apiEndpoint').value = s.endpoint || 'https://generativelanguage.googleapis.com/v1beta';
      if ($('apiModel')) $('apiModel').value = s.model || 'gemini-2.0-flash';
      imageData = s.imageData || null;
      fontImageData = s.fontImageData || null;
      prompts = s.prompts || [];
      statuses = s.statuses || {};
      analysis = s.analysis || '';
      automationMode = s.automationMode || 'flow';
      checkRadio('ratio', s.ratio || '16:9');
      checkRadio('quality', s.downloadQuality || 'default');
      syncAllColors();
      updateStyleSelectUI();
      updateDetailUI();
      const toggle = $('toggleStrictColor');
      if (toggle) toggle.classList.toggle('active', strictColor);
      const toggleAS = $('toggleAutoSubmit');
      if (toggleAS) toggleAS.classList.toggle('active', autoSubmit);
      const cf = $('paramCustomFont');
      if (cf && fs) cf.classList.toggle('hidden', fs.value !== 'Custom Description');
      renderMainImage();
      renderFontImage();
      updateModeUI();
      syncInjectorToUI();
      renderPrompts();
    } catch (e) { appendLog('Failed to load settings: ' + e.message, 'warn'); }
  }

  function checkRadio(name, val) {
    const el = document.querySelector(`input[name="${name}"][value="${val}"]`);
    if (el) el.checked = true;
  }

  // ── API Call ──────────────────────────────────────────────────────────────
  function buildSystemInstruction(s) {
    const lengthDesc = { short: 'concise (1-1.5 sentences)', medium: 'descriptive (2-3 sentences)', long: 'elaborate and detailed (4-5 sentences)' }[s.length] || 'descriptive (2-3 sentences)';
    const colorStr = `${s.color60}, ${s.color30}, ${s.color10}`;
    const fontRule = (s.fontStyle && s.fontStyle !== 'Auto/Mimic Reference')
      ? `Mandatory Font Style: Use ${s.fontStyle} typography.`
      : `Mimic Typography: Analyze the provided typography reference (if any) or the main reference to identify and replicate font family, weight, and aesthetic personality.`;
    const colorRule = s.strictColor
      ? `Mandatory 60-30-10 Rule: Use this palette: ${colorStr}. Distribute as Primary (60%), Secondary (30%), and Accent (10%).`
      : `Creative Color Liberty: Use the colors ${colorStr} as a base, but you can distribute them freely and introduce harmonious shades or gradients for more dynamic results.`;
    const styleStr = s.selectedStyle === 'Custom' ? (s.customStyle || 'Follow Reference DNA') : (s.selectedStyle || s.style || 'Follow Reference DNA');
    const ratioStr = s.ratio || '16:9';

    return `[ROLE]
Name: Design Sense Extractor & Prompt Engineer
Role: You are a high-end design consultant and AI prompt architect. Your specialty is extracting the visual "DNA" from reference images and translating it into high-fidelity image generation prompts.

[CORE MISSION]
1. EXTRACT: Analyze the input image (if present) for its visual essence: composition, rhythm, layout, typography style, shapes, and textures.
2. ADAPT: Create image prompts for 2D design layouts that fill the entire frame. These designs will be used for marketplace mockup previews.
3. ENHANCE: While keeping the design suitable for a 2D surface, you are allowed to include gradients, subtle depth, grain, glassmorphism, or modern graphic effects if they match the style essence.

[IMAGE ANALYSIS PROTOCOL]
- If an image is provided, identify its unique "Graphic DNA" by dissecting the interaction between color theory, geometric hierarchy, typographic rhythm, and negative space.
- DNA ANCHOR: The visual DNA of the MAIN REFERENCE IMAGE is the absolute source of truth. You must not deviate from its core aesthetic principles unless the "Additional Context" explicitly demands a stylistic pivot.
- Replicate the core compositional logic and structural balance found in the reference.
- Use these discovered principles as the primary foundation for all generated prompts.

[USER INTENT & CONTEXT] (MANDATORY)
- Additional Context: ${s.additionalContext || 'No specific extra context provided. STICK STRICTLY to the discovered graphic DNA.'}
- This context is a HIGHER-LEVEL DIRECTIVE. Use it to refine or pivot the DNA. If a specific object, theme, or mood is mentioned here, it MUST be the focus of the prompt.
- DO NOT invent new styles. Enhance what is already there based on user brief.

[LANGUAGE]
- All internal analysis and final prompts must be in English.

[PROMPT RULES]
- FULL FRAME: Designs MUST be "full-bleed edge-to-edge" filling the entire image with no whitespace or margins.
- STYLE ALIGNMENT: Prompts must strictly follow the visual essence of the reference image or the "Visual Style" parameter.
- TEXT LOGIC (MANDATORY): The provided Main Title and Sub-text are REQUIRED elements.
  - If a specific phrase or literal text is provided, it MUST appear in the prompt wrapped in double quotes exactly as given, because it will be rendered as visible text in the design. Example: main title "Modern Coffee", sub-text "Premium Taste".
  - If a theme/description is provided (not a literal label), it MUST guide the visual storytelling without quoting.
  - Only if fields are explicitly empty should you synthesize contextually relevant labels based on "Graphic DNA". Synthesized labels must also be quoted.
  - Main Title: "${s.title || ''}" — treat as literal visible text in the design; always quote it in the prompt.
  - Sub-text: "${s.subtext || ''}" — treat as literal visible text in the design; always quote it in the prompt.
- TYPOGRAPHY:
  ${fontRule}
- COLOR LOGIC:
  ${colorRule}
- ASPECT RATIO: Design must fit within a ${ratioStr} frame. Adapt composition to this ratio while preserving the visual DNA.
- VISUAL STYLE / PIVOT: "${styleStr}"
- PROHIBITED: No physical mockups, no real-world photography of products, no real props, no paper textures, no real surfaces, no hands/people/rooms. This is a pure design artwork file.

[FINAL PROMPT STRUCTURE]
Mandatory phrases: "full-bleed edge-to-edge flat 2D graphic design filling the entire image from edge to edge with no whitespace no margins no empty space".
Constraints: "no objects, no props, no mockup, no photography, no 3D scene, no real-world environment".

[OUTPUT FORMAT]
Return ONLY a valid JSON object. No markdown.
{
  "analysis": "A detailed 1-2 sentence breakdown of the visual DNA extracted from the source image (style, rhythm, composition).",
  "prompts": ["Prompt 1...", "Prompt 2..."]
}`;
  }

  function dataUrlToPart(dataUrl) {
    if (!dataUrl || !dataUrl.includes(';base64,')) return null;
    const [meta, data] = dataUrl.split(';base64,');
    return { mimeType: meta.replace('data:', ''), data };
  }

  function buildUserMessage(s) {
    const lengthDesc = { short: 'concise (1-1.5 sentences)', medium: 'descriptive (2-3 sentences)', long: 'elaborate and detailed (4-5 sentences)' }[s.length] || 'descriptive (2-3 sentences)';
    const styleStr = s.selectedStyle === 'Custom' ? (s.customStyle || 'Follow Reference DNA') : (s.selectedStyle || s.style || 'Follow Reference DNA');
    const colorStr = `${s.color60}, ${s.color30}, ${s.color10}`;
    const ratioStr = s.ratio || '16:9';
    return `MANDATORY USER PARAMETERS:
- Main Title: "${s.title || 'MANDATORY: Extract from image context'}" — this is literal visible text that will appear in the design; wrap it in double quotes in your prompt exactly as given.
- Sub-text (Details): "${s.subtext || 'MANDATORY: Extract from image context'}" — this is literal visible text that will appear in the design; wrap it in double quotes in your prompt exactly as given.
- User Intent (Additional Context): "${s.additionalContext || 'MANDATORY: Follow Reference DNA exactly'}"
- Visual Style / Pivot: "${styleStr}"
- Color Constraints: "${colorStr}"
- Aspect Ratio: ${ratioStr}
- Number of Variations: ${s.count}
- Description Detail: ${lengthDesc}

CRITICAL: The "Main Title" and "Sub-text" above are absolute requirements and will be rendered as visible text in the final design. Always wrap them in double quotes inside the prompt text. If they are empty, synthesize based on the MAIN REFERENCE IMAGE DNA and still quote the synthesized text. Return JSON only.`;
  }

  async function callGemini(s) {
    const parts = [];
    const main = dataUrlToPart(s.imageData);
    const font = dataUrlToPart(s.fontImageData);
    if (main) {
      parts.push({ text: 'MAIN REFERENCE IMAGE: This is the primary stylistic source of truth. Replicate its Graphic DNA strictly.' });
      parts.push({ inlineData: main });
    }
    if (font) {
      parts.push({ text: 'TYPOGRAPHY REFERENCE: Replicate this font style.' });
      parts.push({ inlineData: font });
    }
    parts.push({ text: buildUserMessage(s) });
    const base = s.endpoint.replace(/\/$/, '');
    const url = `${base}/models/${encodeURIComponent(s.model)}:generateContent?key=${encodeURIComponent(s.apiKey)}`;
    const body = {
      contents: [{ parts }],
      generationConfig: { temperature: 0.2, responseMimeType: 'application/json' },
      systemInstruction: { parts: [{ text: buildSystemInstruction(s) }] }
    };
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!res.ok) {
      let errMsg = res.statusText;
      try {
        const json = await res.json();
        errMsg = json.error?.message || JSON.stringify(json);
      } catch (_) {}
      throw new Error(errMsg);
    }
    const json = await res.json();
    const text = json.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) throw new Error('Empty response from Gemini API');
    return text;
  }

  function buildOpenAIChatUrl(endpoint) {
    const base = String(endpoint || '').trim().replace(/\/+$/, '');
    if (/\/chat\/completions$/i.test(base)) return base;
    return `${base}/chat/completions`;
  }

  async function callOpenAI(s) {
    const userContent = [];
    if (s.imageData) {
      userContent.push({ type: 'text', text: 'MAIN REFERENCE IMAGE: This is the primary stylistic source of truth. Replicate its Graphic DNA strictly.' });
      userContent.push({ type: 'image_url', image_url: { url: s.imageData } });
    }
    if (s.fontImageData) {
      userContent.push({ type: 'text', text: 'TYPOGRAPHY REFERENCE: Replicate this font style.' });
      userContent.push({ type: 'image_url', image_url: { url: s.fontImageData } });
    }
    userContent.push({ type: 'text', text: buildUserMessage(s) });
    const url = buildOpenAIChatUrl(s.endpoint);
    const body = {
      model: s.model,
      messages: [
        { role: 'system', content: buildSystemInstruction(s) },
        { role: 'user', content: userContent }
      ],
      temperature: 0.2,
      response_format: { type: 'json_object' }
    };
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + s.apiKey }, body: JSON.stringify(body) });
    if (!res.ok) {
      let errMsg = res.statusText;
      try {
        const json = await res.json();
        errMsg = json.error?.message || JSON.stringify(json);
      } catch (_) {}
      throw new Error(errMsg);
    }
    const json = await res.json();
    const text = json.choices?.[0]?.message?.content;
    if (!text) throw new Error('Empty response from OpenAI-compatible API');
    return text;
  }

  function parseResponse(raw) {
    const str = String(raw);
    const m = str.match(/\{[\s\S]*\}/);
    const data = JSON.parse(m ? m[0] : str);
    if (!Array.isArray(data.prompts)) throw new Error('No prompts array in response');
    return data;
  }

  async function generatePrompts() {
    const s = getSettings();
    if (!s.apiKey) return appendLog('API key is required.', 'error');
    if (!s.endpoint) return appendLog('Endpoint URL is required.', 'error');
    if (!s.model) return appendLog('Model name is required.', 'error');
    if (!s.imageData && !s.title) return appendLog('Upload an image or enter a title first.', 'error');
    const btn = $('btnGenerate');
    if (btn) { btn.disabled = true; btn.classList.add('loading'); btn.textContent = 'Generating...'; }
    isGenerating = true;
    document.querySelector('[data-tab="prompts"]')?.click();
    renderPrompts();
    appendLog('Generating prompts...', 'act');
    try {
      const raw = s.provider === 'gemini' ? await callGemini(s) : await callOpenAI(s);
      const data = parseResponse(raw);
      prompts = data.prompts || [];
      analysis = data.analysis || '';
      statuses = {};
      isGenerating = false;
      renderPrompts();
      await saveSettings();
      appendLog(`Generated ${prompts.length} prompts successfully.`, 'success');
    } catch (e) {
      isGenerating = false;
      renderPrompts();
      const message = e?.message || String(e) || 'Unknown error';
      appendLog('Generate failed: ' + message, 'error');
      console.error('Generate prompts failed:', e);
    } finally {
      if (btn) { btn.disabled = false; btn.classList.remove('loading'); btn.innerHTML = '<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg> Generate Prompts'; }
    }
  }

  // ── Render Prompts Tab ────────────────────────────────────────────────────
  function clearPrompts() {
    prompts = [];
    analysis = '';
    statuses = {};
    renderPrompts();
    saveSettings();
    appendLog('Prompts cleared.', 'info');
  }

  function renderPrompts() {
    const list = $('promptList');
    if (!list) return;
    if (isGenerating) {
      list.innerHTML = '<div class="prompt-empty"><div class="spinner"></div><p>Generating prompts...</p></div>';
      return;
    }
    if (!prompts.length) {
      list.innerHTML = '<div class="prompt-empty"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg><p>Generate prompts first</p></div>';
return;
    }
    let html = `<div class="prompt-list-header">
      <span class="prompt-list-count">${prompts.length} prompt${prompts.length !== 1 ? 's' : ''}</span>
      <div class="prompt-list-actions">
        <button class="prompt-item-btn" id="btnCopyAll" style="padding: 2px 6px; font-size: 8px;">Copy All</button>
        <button class="prompt-clear-btn" id="btnClearPrompts">Clear All</button>
      </div>
    </div>`;
    if (analysis) {
      html += `<div class="prompt-item"><div class="prompt-item-text"><strong>Analysis:</strong> ${escapeHtml(analysis)}</div></div>`;
    }
    prompts.forEach((p, i) => {
      const st = statuses[i] || 'pending';
      const stLabel = { pending: 'Pending', inserting: 'Inserting...', monitoring: 'Monitoring...', downloaded: 'Downloaded', failed: 'Failed' }[st] || st;
      html += `<div class="prompt-item" id="prompt-item-${i}">
        <div class="prompt-item-header">
          <span class="prompt-item-num">#${String(i+1).padStart(2,'0')}</span>
          <div class="prompt-item-actions">
            <button class="prompt-item-btn" data-copy="${i}">Copy</button>
            <button class="prompt-item-btn btn-insert ${st === 'monitoring' ? 'inserted' : ''} ${st === 'monitoring' ? 'stop-monitor' : ''}" data-insert="${i}" ${st === 'inserting' ? 'disabled' : ''}>
              ${st === 'inserting' ? 'Running...' : st === 'monitoring' ? 'Stop' : 'Insert'}
            </button>
          </div>
        </div>
        <div class="prompt-item-text">${escapeHtml(p)}</div>
        <div class="prompt-item-status status-${st}" id="pstatus-${i}">${stLabel}</div>
      </div>`;
    });
    list.innerHTML = html;
    const clearBtn = $('btnClearPrompts');
    if (clearBtn) clearBtn.addEventListener('click', clearPrompts);
    document.querySelectorAll('[data-copy]').forEach(b => {
      b.addEventListener('click', () => {
        const idx = +b.dataset.copy;
        navigator.clipboard.writeText(prompts[idx]);
        const originalText = b.textContent;
        b.textContent = 'Copied!';
        b.classList.add('copied');
        setTimeout(() => {
          b.textContent = originalText;
          b.classList.remove('copied');
        }, 1500);
      });
    });
    const copyAllBtn = $('btnCopyAll');
    if (copyAllBtn) {
      copyAllBtn.addEventListener('click', () => {
        const allText = prompts.map((p, i) => `${i + 1}. ${p}\n`).join('\n');
        navigator.clipboard.writeText(allText);
        const originalText = copyAllBtn.textContent;
        copyAllBtn.textContent = 'Copied!';
        copyAllBtn.classList.add('copied');
        setTimeout(() => {
          copyAllBtn.textContent = originalText;
          copyAllBtn.classList.remove('copied');
        }, 1500);
      });
    }
    document.querySelectorAll('[data-insert]').forEach(b => {
      b.addEventListener('click', () => {
        const idx = +b.dataset.insert;
        if (statuses[idx] === 'monitoring' || statuses[idx] === 'inserting' || b.textContent.trim() === 'Stop') {
          if (automationMode === 'injector') stopInjectorAutomation(idx);
          else stopMonitoring(idx);
        } else {
          if (automationMode === 'injector') runInjectorPrompt(idx);
          else insertPrompt(idx);
        }
      });
    });
  }

  async function stopMonitoring(i) {
    const tab = await getCurrentFlowTab();
    if (tab) {
      chrome.tabs.sendMessage(tab.id, { action: 'STOP' });
    }
    statuses[i] = 'failed';
    renderPrompts();
    appendLog(`Prompt #${i+1} monitoring stopped.`, 'info');
  }

  async function getCurrentFlowTab() {
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (isFlowTab(activeTab)) return activeTab;
    const allTabs = await chrome.tabs.query({ currentWindow: true });
    return allTabs.find(t => isFlowTab(t));
  }

  // ── Ensure Flow tab is open and ready ────────────────────────────────────
  const FLOW_URL = 'https://labs.google/fx/tools/flow';

  function isFlowTab(tab) {
    return tab?.url && tab.url.includes('labs.google') && tab.url.includes('/tools/flow');
  }

  async function ensureFlowTab() {
    // Check if current active tab is already a Flow tab
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (isFlowTab(activeTab)) return activeTab;

    // Look for any existing Flow tab in the window
    const allTabs = await chrome.tabs.query({ currentWindow: true });
    const flowTab = allTabs.find(t => isFlowTab(t));
    if (flowTab) {
      await chrome.tabs.update(flowTab.id, { active: true });
      return flowTab;
    }

    // No Flow tab found — open one
    appendLog('No Flow tab found. Opening Flow...', 'act');
    const newTab = await chrome.tabs.create({ url: FLOW_URL, active: true });
    // Wait for it to load
    await new Promise((resolve) => {
      const listener = (tabId, info) => {
        if (tabId === newTab.id && info.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      // Fallback timeout
      setTimeout(resolve, 15000);
    });
    await new Promise(r => setTimeout(r, 1500));
    return newTab;
  }

  async function ensureFlowReady(tabId) {
    // Inject content script if needed
    await ensureContentScript(tabId);
    // Tell content script to ensure project is ready (handles landing page → new project)
    // After new project is created, the tab URL changes — wait for it then re-inject
    return new Promise((resolve) => {
      let settled = false;
      const done = (result) => { if (!settled) { settled = true; resolve(result); } };

      // Listen for tab URL change (landing → project page navigation)
      const navListener = (tabId2, info) => {
        if (tabId2 !== tabId) return;
        if (info.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(navListener);
          // Re-inject content script on new URL then ping
          ensureContentScript(tabId).then(() => done({ ok: true }));
        }
      };
      chrome.tabs.onUpdated.addListener(navListener);

      chrome.tabs.sendMessage(tabId, { action: 'ENSURE_FLOW_READY' }, res => {
        chrome.tabs.onUpdated.removeListener(navListener);
        if (chrome.runtime.lastError) done({ ok: false, error: chrome.runtime.lastError.message });
        else done(res || { ok: true });
      });

      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(navListener);
        done({ ok: false, error: 'timeout' });
      }, 35000);
    });
  }

  // ── Insert Prompt ─────────────────────────────────────────────────────────
  async function insertPrompt(i) {
    if (statuses[i] === 'inserting' || statuses[i] === 'monitoring') return;
    const s = getSettings();
    statuses[i] = 'inserting';
    renderPrompts();
    appendLog(`Inserting prompt #${i+1}...`, 'act');
    try {
      // Ensure a Flow tab is open and active
      const tab = await ensureFlowTab();
      if (!tab) { appendLog('Could not open Flow tab.', 'error'); statuses[i] = 'failed'; renderPrompts(); return; }

      // Ensure content script is injected and project is ready
      appendLog('Waiting for Flow project to be ready...', 'act');
      const ready = await ensureFlowReady(tab.id);
      if (!ready?.ok && ready?.error) {
        appendLog('Flow ready error: ' + ready.error, 'warn');
        // Non-fatal — still try to insert
      }

      chrome.tabs.sendMessage(tab.id, {
        action: 'INSERT_PROMPT',
        payload: { prompt: prompts[i], promptIndex: i, settings: { ratio: s.ratio, batch: s.batch, downloadQuality: s.downloadQuality, type: 'image', globalDelayMs: 30000, autoSubmit } }
      }, res => {
        if (chrome.runtime.lastError) { appendLog(chrome.runtime.lastError.message, 'error'); statuses[i] = 'failed'; renderPrompts(); return; }
        if (res?.status === 'inserted') {
          statuses[i] = 'monitoring';
          renderPrompts();
          appendLog(`Prompt #${i+1} inserted. ${autoSubmit ? 'Auto-submitting...' : 'Click Generate in Flow manually'} — monitoring for new images (180s).`, 'success');
        } else {
          statuses[i] = 'failed';
          renderPrompts();
          appendLog(`Insert failed: ${res?.message || 'unknown error'}`, 'error');
        }
      });
    } catch (e) {
      appendLog('Insert error: ' + e.message, 'error');
      statuses[i] = 'failed';
      renderPrompts();
    }
  }

  async function ensureContentScript(tabId) {
    try {
      await new Promise((resolve, reject) => {
        chrome.tabs.sendMessage(tabId, { action: 'PING' }, res => {
          if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
          else resolve(res);
        });
      });
    } catch (_) {
      await chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
      await new Promise(r => setTimeout(r, 400));
    }
  }

  // ── Runtime messages from content script ──────────────────────────────────
  function onRuntimeMessage(msg) {
    if (msg.type === 'ELEMENT_PICKED') {
      const id = parseInt(msg.pointIndex || 1);
      let p = injectorPoints.find(x => x.id === id);
      if (!p) return;
      p.selector = msg.selector || '';
      syncInjectorToUI();
      saveCurrentInjectorSettings();
      appendLog(`Point ${id} selected: ${msg.selector}`, 'success');
      return;
    }
    if (msg.type === 'AUTOMATION_STATUS') { appendLog('[Injector] ' + msg.text, 'info'); return; }
    if (msg.type === 'DOWNLOAD_SCANNING') { appendLog(`[Injector] Scanning: found ${msg.found}/${msg.required}`, 'info'); return; }
    if (msg.type === 'DOWNLOAD_COUNTDOWN') { if (msg.seconds % 10 === 0 || msg.seconds <= 5) appendLog(`[Injector] Waiting ${msg.seconds}s before scanning`, 'info'); return; }
    if (msg.type === 'DOWNLOAD_DONE') { if (Number.isInteger(msg.promptIndex)) { statuses[msg.promptIndex] = 'downloaded'; renderPrompts(); } appendLog(`[Injector] Downloaded ${msg.count} item(s)`, 'success'); return; }
    if (msg.type === 'AUTOMATION_PROGRESS') { appendLog(`[Injector] Progress: ${msg.done}/${msg.total}`, 'info'); return; }
    if (msg.type === 'AUTOMATION_FINISHED') { injectorRunning = false; injectorSessionId = null; renderPrompts(); appendLog('[Injector] Automation finished.', 'success'); return; }
    if (msg.type === 'AUTOMATION_ERROR') { if (Number.isInteger(msg.promptIndex)) { statuses[msg.promptIndex] = 'failed'; renderPrompts(); } appendLog('[Injector] ' + (msg.message || 'Automation error'), 'error'); return; }
    if (msg.action === 'LOG_FROM_CONTENT') appendLog('[Script] ' + msg.message, 'info');
    if (msg.action === 'PROMPT_STATUS') {
      statuses[msg.promptIndex] = msg.status;
      // clear countdown display when done
      const cd = $('pstatus-' + msg.promptIndex);
      if (cd) cd.dataset.countdown = '';
      renderPrompts();
      const type = msg.status === 'failed' ? 'error' : msg.status === 'downloaded' ? 'success' : 'info';
      appendLog(msg.message || `Prompt #${msg.promptIndex + 1}: ${msg.status}`, type);
    }
    if (msg.action === 'MONITOR_COUNTDOWN') {
      const idx = msg.promptIndex;
      const remaining = msg.remaining;
      // Update countdown inline on the prompt item status label
      const statusEl = $('pstatus-' + idx);
      if (statusEl && statuses[idx] === 'monitoring') {
        statusEl.textContent = remaining > 0
          ? `Monitoring... ${remaining}s`
          : 'Monitoring...';
        statusEl.className = 'prompt-item-status status-monitoring';
      }
      // Log every 30s
      if (remaining > 0 && remaining % 30 === 0) {
        appendLog(`Prompt #${idx + 1} monitoring: ${remaining}s remaining`, 'info');
      }
    }
    if (msg.action === 'DOWNLOAD_STARTED') {
      appendLog(`Download started: ${msg.filename}`, 'success');
    }
    if (msg.action === 'DOWNLOAD_FAILED') {
      if (Number.isInteger(msg.promptIndex)) { statuses[msg.promptIndex] = 'failed'; renderPrompts(); }
      appendLog(`Download failed: ${msg.error || 'Unknown error'}`, 'error');
    }
  }

  // ── Logging ───────────────────────────────────────────────────────────────
  function appendLog(message, type) {
    const log = $('logArea');
    if (!log) return;
    const t = new Date().toLocaleTimeString([], { hour12: false });
    const cls = { info: 'log-info', success: 'log-success', error: 'log-error', warn: 'log-warn', act: 'log-act' }[type] || 'log-info';
    const code = { info: 'INF', success: 'OK', error: 'ERR', warn: 'WRN', act: 'ACT' }[type] || 'INF';
    log.insertAdjacentHTML('beforeend', `<div class="log-line"><span class="log-time">[${t}]</span> <span class="${cls}">${code}</span> ${escapeHtml(message)}</div>`);
    log.scrollTop = log.scrollHeight;
  }

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = String(s || '');
    return d.innerHTML;
  }

})();
