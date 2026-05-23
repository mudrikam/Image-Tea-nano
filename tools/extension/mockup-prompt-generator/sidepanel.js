(() => {
  'use strict';
  const STORE_KEY = 'mpp_settings_v2';
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
  let generatorMode = 'mockup'; // 'mockup' or 'preview'
  let injectorPoints = [
    { id: 1, type: 'paste', enabled: true, selector: '', delay: 1.0 },
    { id: 2, type: 'click', enabled: true, selector: '', delay: 1.0 }
  ];
  let injectorRunning = false;
  let injectorPaused = false;
  let injectorSessionId = null;
  let injectorDb = null;
  let currentInjectorUrlKey = 'site:default';

  // Mockup generator state
  let mockupDetailLevel = 'medium';
  let mockupColorEnabled = false;

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
       bindHelpModal();
       bindPersistenceInputs();
       bindGeneratorModeSwitch();
       bindMockupControls();
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

  // ── Generator Mode Switch ────────────────────────────────────────────────
  function bindGeneratorModeSwitch() {
    document.querySelectorAll('.gen-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        generatorMode = btn.dataset.genMode;
        updateGeneratorModeUI();
        saveSettings();
      });
    });
  }

  function updateGeneratorModeUI() {
    document.querySelectorAll('.gen-mode-btn').forEach(b => b.classList.toggle('active', b.dataset.genMode === generatorMode));
    document.querySelectorAll('.gen-mode-panel').forEach(p => p.classList.remove('active'));
    const panel = $('panel-' + generatorMode);
    if (panel) panel.classList.add('active');
  }

  // ── Mockup Generator Controls ────────────────────────────────────────────
  function bindMockupControls() {
    // Mockup visual style select
    const sel = $('mockupVisualStyle');
    if (sel) sel.addEventListener('change', () => {
      const cs = $('mockupCustomStyle');
      if (cs) cs.classList.toggle('hidden', sel.value !== 'Custom');
      saveSettings();
    });

    // Mockup detail buttons
    document.querySelectorAll('.mockup-detail-btn').forEach(b => {
      b.addEventListener('click', () => {
        mockupDetailLevel = b.dataset.level;
        updateMockupDetailUI();
        saveSettings();
      });
    });

    // Mockup color toggle
    const colorToggle = $('toggleMockupColor');
    if (colorToggle) colorToggle.addEventListener('click', () => {
      mockupColorEnabled = !mockupColorEnabled;
      colorToggle.classList.toggle('active', mockupColorEnabled);
      const row = $('mockupColorRow');
      if (row) row.style.opacity = mockupColorEnabled ? '1' : '0.4';
      saveSettings();
    });

    // Mockup color inputs
    ['mockupColorBg', 'mockupColorEnv'].forEach(id => {
      const el = $(id);
      const swatchId = id === 'mockupColorBg' ? 'mockupSwatchBg' : 'mockupSwatchEnv';
      const swatch = $(swatchId);
      if (el) {
        el.addEventListener('input', () => {
          const valEl = $(id + 'Val');
          if (valEl) valEl.textContent = el.value;
          if (swatch) {
            swatch.style.background = el.value;
            const isLight = getContrastYIQ(el.value) === 'light';
            swatch.classList.toggle('light-text', !isLight);
            swatch.classList.toggle('dark-text', isLight);
          }
          saveSettings();
        });
      }
      if (swatch) swatch.addEventListener('click', () => el?.click());
    });

    // Mockup random color
    const rand = $('btnRandomMockupColor');
    if (rand) rand.addEventListener('click', () => {
      ['mockupColorBg', 'mockupColorEnv'].forEach(id => {
        const el = $(id);
        if (el) {
          el.value = '#' + Math.floor(Math.random()*16777215).toString(16).padStart(6,'0');
          el.dispatchEvent(new Event('input'));
        }
      });
    });

    // Mockup count slider
    const countInput = $('mockupCount');
    if (countInput) {
      countInput.addEventListener('input', () => {
        const val = $('mockupCountVal');
        if (val) val.textContent = countInput.value;
        saveSettings();
      });
    }

    // Mockup context textarea
    const ctx = $('mockupContext');
    if (ctx) ctx.addEventListener('input', saveSettings);

    // Mockup custom style
    const cs = $('mockupCustomStyle');
    if (cs) cs.addEventListener('input', saveSettings);
  }

  function updateMockupDetailUI() {
    document.querySelectorAll('.mockup-detail-btn').forEach(b => b.classList.toggle('active', b.dataset.level === mockupDetailLevel));
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

  // ── Help Modal ─────────────────────────────────────────────────────────────
  function bindHelpModal() {
    const btn = $('btnHelp');
    const modal = $('helpModal');
    const close = $('helpModalClose');
    const gotIt = $('btnCloseHelp');

    if (!btn || !modal) return;

    const openModal = () => modal.classList.remove('hidden');
    const closeModal = () => modal.classList.add('hidden');

    btn.addEventListener('click', openModal);
    if (close) close.addEventListener('click', closeModal);
    if (gotIt) gotIt.addEventListener('click', closeModal);
    modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
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
    document.querySelectorAll('input[name="ratio"],input[name="ratio-injector"],input[name="quality"],input[name="batch"]').forEach(el => {
      el.addEventListener('input', () => { syncInjectorFromUI(); saveSettings(); });
      el.addEventListener('change', () => { syncInjectorFromUI(); saveSettings(); });
    });
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
    const flowRatio = document.querySelector('input[name="ratio"]:checked')?.value || '16:9';
    const injectorRatio = document.querySelector('input[name="ratio-injector"]:checked')?.value || '16:9';
    return {
      // Generator mode
      generatorMode,
      // Preview settings
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
      ratio: flowRatio,
      injectorRatio,
      downloadQuality: document.querySelector('input[name="quality"]:checked')?.value || 'default',
      batch: document.querySelector('input[name="batch"]:checked')?.value || '1',
      // Mockup settings
      mockupContext: $('mockupContext')?.value || '',
      mockupCount: parseInt($('mockupCount')?.value || '3'),
      mockupVisualStyle: $('mockupVisualStyle')?.value || '',
      mockupCustomStyle: $('mockupCustomStyle')?.value || '',
      mockupDetailLevel,
      mockupColorEnabled,
      mockupColorBg: $('mockupColorBg')?.value || '#f5f5f5',
      mockupColorEnv: $('mockupColorEnv')?.value || '#e0e0e0',
      // Shared
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
      // Generator mode
      generatorMode = s.generatorMode || 'mockup';
      // Preview settings
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
      checkRadio('ratio-injector', s.injectorRatio || s.ratio || '16:9');
      checkRadio('quality', s.downloadQuality || 'default');
      checkRadio('batch', s.batch || '1');
      // Mockup settings
      mockupDetailLevel = s.mockupDetailLevel || 'medium';
      mockupColorEnabled = s.mockupColorEnabled === true;
      if ($('mockupContext')) $('mockupContext').value = s.mockupContext || '';
      if ($('mockupCount')) { $('mockupCount').value = s.mockupCount || 3; if ($('mockupCountVal')) $('mockupCountVal').textContent = s.mockupCount || 3; }
      const mvs = $('mockupVisualStyle');
      if (mvs) mvs.value = s.mockupVisualStyle || '';
      if ($('mockupCustomStyle')) {
        $('mockupCustomStyle').value = s.mockupCustomStyle || '';
        $('mockupCustomStyle').classList.toggle('hidden', (s.mockupVisualStyle || '') !== 'Custom');
      }
      if ($('mockupColorBg')) {
        $('mockupColorBg').value = s.mockupColorBg || '#f5f5f5';
        $('mockupColorBg').dispatchEvent(new Event('input'));
      }
      if ($('mockupColorEnv')) {
        $('mockupColorEnv').value = s.mockupColorEnv || '#e0e0e0';
        $('mockupColorEnv').dispatchEvent(new Event('input'));
      }
      const colorToggle = $('toggleMockupColor');
      if (colorToggle) colorToggle.classList.toggle('active', mockupColorEnabled);
      const colorRow = $('mockupColorRow');
      if (colorRow) colorRow.style.opacity = mockupColorEnabled ? '1' : '0.4';
      // UI updates
      syncAllColors();
      updateStyleSelectUI();
      updateDetailUI();
      updateMockupDetailUI();
      updateGeneratorModeUI();
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

  // ── Mockup Generator System Instruction ──────────────────────────────────
  function buildMockupSystemInstruction(s) {
    const lengthDesc = { short: 'concise (1-2 sentences)', medium: 'descriptive (2-3 sentences)', long: 'elaborate and detailed (4-5 sentences)' }[s.mockupDetailLevel] || 'descriptive (2-3 sentences)';
    const envStyle = s.mockupVisualStyle === 'Custom' ? (s.mockupCustomStyle || 'Blank/Isolated') : (s.mockupVisualStyle || 'Blank/Isolated');
    const colorInstruction = s.mockupColorEnabled
      ? `Environment/Background Color: Use ${s.mockupColorBg} as the primary background color and ${s.mockupColorEnv} as the environment/surface accent color. The MAIN OBJECT must remain WHITE regardless of these color settings.`
      : `Environment/Background Color: Use natural, clean colors appropriate for the chosen visual style. The MAIN OBJECT must remain WHITE.`;
    const ratioStr = s.ratio || '16:9';

    return `[ROLE]
Name: Mockup Raw Material Prompt Generator
Role: You are a professional mockup base photo prompt engineer specializing in photorealistic product photography prompts. Your task is to craft rich, highly detailed prompts for clean blank mockup base photos — pure raw materials without any design elements, graphics, or text. Every prompt must read like a professional photography brief: vivid, specific, and production-ready.

[CORE MISSION]
1. ANALYZE: If a reference image is provided, extract the object type, shape, material, construction details, and context to understand exactly what kind of mockup base is needed.
2. GENERATE: Craft richly detailed prompts for clean, blank mockup base photos. The main object MUST be WHITE/plain with NO design elements, NO text, NO graphics, NO patterns — ever.
3. VARY: Each prompt variation must differ meaningfully in environment, lighting setup, camera angle, surface treatment, props, and atmospheric mood while keeping the same white blank object as the hero.

[IMAGE ANALYSIS PROTOCOL]
- IF an image is provided, identify the PRIMARY OBJECT in precise detail (e.g., crew-neck t-shirt, ceramic mug with handle, slim phone case, canvas tote bag, A3 poster, etc.)
- Extract: exact object type, material (cotton, ceramic, leather, paper, etc.), shape, construction, and any contextual clues about desired setting
- Use this information to generate highly specific, accurate mockup base prompts
- DO NOT replicate any designs, text, or graphics from the reference — only identify and describe the physical object

[MANDATORY RULES]
1. WHITE MAIN OBJECT: The primary mockup item MUST be described as white, blank, plain, unprinted, clean surface. No exceptions. Reinforce this in every prompt.
2. NO DESIGN ELEMENTS: Absolutely no text, logos, typography, patterns, graphics, prints, embroidery, or branding on the main object.
3. SHARP FOCUS: Main object must be in tack-sharp focus, crisp edges, clear surface detail.
4. FULL VISIBILITY: Object must be fully visible, properly oriented, not obscured, not tilted excessively, not stacked or overlapping with other objects.
5. CLEAN COMPOSITION: Professional product photography style, centered or rule-of-thirds composition with the white main object as the undisputed hero.
6. PHOTOREALISTIC: All prompts must describe photorealistic, high-resolution product photography — not illustration, not 3D render, not flat design.

[ENVIRONMENT & STYLE]
- Visual Style/Environment: "${envStyle}"
- ${colorInstruction}
- Aspect Ratio: ${ratioStr} — explicitly describe the composition orientation and framing in every prompt.

[PROMPT STRUCTURE — MANDATORY ELEMENTS]
Every prompt MUST include ALL of the following elements, described with rich specificity:
1. SUBJECT: Precise description of the white blank object — material, shape, size impression, surface finish (matte/glossy/textured), construction details
2. ENVIRONMENT/BACKGROUND: Detailed scene description — surface material, background elements, props, spatial depth, scene atmosphere
3. LIGHTING: Specific lighting setup — light source type (softbox, natural window, ring light, golden hour, etc.), direction (front, side, top, backlit), quality (soft diffused, hard dramatic, warm, cool), shadows and highlights behavior
4. CAMERA & LENS: Shooting angle (eye-level, overhead flat lay, 3/4 angle, close-up detail), focal length feel (wide, standard 50mm, telephoto compression), depth of field (sharp throughout or shallow bokeh background)
5. ATMOSPHERE & MOOD: Overall feeling — clean and clinical, warm and inviting, moody and dramatic, fresh and airy, etc.
6. TECHNICAL QUALITY: Resolution, sharpness, color accuracy descriptors — "ultra-high resolution", "studio-quality", "photorealistic", "sharp product photography"

[DETAIL LEVEL — STRICTLY ENFORCED]
${lengthDesc === 'concise (1-2 sentences)' ? 
  'SHORT MODE: Write each prompt as 1-2 dense, information-packed sentences covering subject, environment, and lighting.' :
  lengthDesc === 'descriptive (2-3 sentences)' ?
  'MEDIUM MODE: Write each prompt as 2-3 well-developed sentences. Cover subject details, environment/lighting, and camera/mood.' :
  'LONG MODE: Write each prompt as a rich, elaborate paragraph of 4-6 sentences minimum. Describe the subject in full material and construction detail, paint the environment vividly, specify the exact lighting rig and its effect on the object surface, describe the camera angle and lens characteristics, and convey the atmospheric mood. Every sentence must add specific visual information — no filler, no repetition. This is a professional photography brief.'
}

[VARIATION REQUIREMENT]
When generating multiple prompts, each MUST be meaningfully different:
- ENVIRONMENT: Completely different backgrounds/settings/surfaces within the chosen style
- LIGHTING: Different lighting setups with different moods and shadow behaviors
- CAMERA ANGLE: Vary between front-facing, 3/4 angle, overhead, close-up detail shots
- PROPS & CONTEXT: Different supporting elements (if any) that complement without distracting
- ATMOSPHERE: Different emotional tones — clinical, warm, dramatic, airy, moody
All variations MUST keep the main object WHITE, BLANK, and UNPRINTED.

[OUTPUT FORMAT]
Return ONLY a valid JSON object. No markdown, no code fences.
{
  "analysis": "Precise description of the identified object type, material, and the chosen approach for the prompt set.",
  "prompts": ["Prompt 1...", "Prompt 2..."]
}`;
  }

  function buildMockupUserMessage(s) {
    const envStyle = s.mockupVisualStyle === 'Custom' ? (s.mockupCustomStyle || 'Blank/Isolated') : (s.mockupVisualStyle || 'Blank/Isolated');
    const colorStr = s.mockupColorEnabled ? `Background: ${s.mockupColorBg}, Environment: ${s.mockupColorEnv}` : 'Natural/Auto';
    const ratioStr = s.ratio || '16:9';

    const detailInstruction = s.mockupDetailLevel === 'long'
      ? 'LONG — Write each prompt as a rich, elaborate paragraph of 4-6 sentences. Cover: precise object material/construction, vivid environment description, exact lighting rig and its effect on the surface, camera angle and lens feel, and atmospheric mood. Every sentence must add specific visual information.'
      : s.mockupDetailLevel === 'short'
      ? 'SHORT — Write each prompt as 1-2 dense sentences covering subject, environment, and lighting.'
      : 'MEDIUM — Write each prompt as 2-3 well-developed sentences covering subject, environment/lighting, and camera/mood.';

    return `MOCKUP BASE GENERATION REQUEST:
- Context/Description: "${s.mockupContext || 'Generate based on reference image'}"
- Visual Style/Environment: "${envStyle}"
- Color Settings: ${colorStr} (main object MUST be WHITE)
- Aspect Ratio: ${ratioStr}
- Number of Variations: ${s.mockupCount || 3}
- Detail Level: ${detailInstruction}

MANDATORY PROMPT ELEMENTS (include ALL in every prompt):
1. Subject: precise white blank object with material, shape, surface finish details
2. Environment: detailed scene — surface, background, props, spatial depth
3. Lighting: specific setup — source type, direction, quality, shadow/highlight behavior
4. Camera: angle, focal length feel, depth of field
5. Mood: atmospheric feeling of the scene
6. Quality: photorealistic, ultra-high resolution, studio-quality

CRITICAL RULES:
1. Main object MUST be WHITE, blank, unprinted — no design/text/graphics/patterns
2. Object must be in tack-sharp focus, fully visible, properly oriented
3. All prompts must be in ENGLISH
4. Return JSON only with "analysis" and "prompts" fields`;
  }

  // ── Preview Generator System Instruction (original) ──────────────────────
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
1. TRANSLATE: Convert the user's title, subtext, style preferences, and design DNA into a standalone 2D graphic design prompt.
2. DESIGN: Create image prompts for 2D design layouts that fill the entire frame. These designs will be used for marketplace mockup previews.
3. ENHANCE: While keeping the design suitable for a 2D surface, you are allowed to include gradients, subtle depth, grain, glassmorphism, or modern graphic effects if they match the style essence.

[IMAGE ANALYSIS PROTOCOL]
- IF an image is provided, use it ONLY to extract the visual "DNA": composition, rhythm, layout, typography style, shapes, textures, and color philosophy.
- DNA AS TEMPLATE: The extracted DNA informs the prompt's structure and style language, but the final prompt MUST describe the completed design directly — never reference the source image or say "based on" or "in the style of". The prompt must describe WHAT TO DRAW, not what it's based on.
- DO NOT include phrases like "replicate", "mimic", "based on reference", "similar to", "inspired by". Instead, describe the final visual directly.

[USER INTENT & CONTEXT] (MANDATORY)
- Additional Context: ${s.additionalContext || 'No specific extra context provided. Use the extracted design language as your primary guide.'}
- This context is a HIGHER-LEVEL DIRECTIVE. Use it to refine or adjust the visual direction. If a specific object, theme, or mood is mentioned here, it MUST be the focus of the prompt.
- DO NOT invent new styles. Enhance what is already indicated by the DNA extraction and user brief.

[LANGUAGE]
- All internal analysis and final prompts must be in English.

[PROMPT RULES]
- FULL FRAME: Designs MUST be "full-bleed edge-to-edge" filling the entire frame with no whitespace or margins.
- STYLE ALIGNMENT: Prompts must strictly follow the visual language and design principles derived from the reference (if provided) or the "Visual Style" parameter.
- TEXT LOGIC (MANDATORY): The provided Main Title and Sub-text are REQUIRED elements.
  - If a specific phrase or literal text is provided, it MUST appear in the prompt wrapped in double quotes exactly as given, because it will be rendered as visible text in the design. Example: main title "Modern Coffee", sub-text "Premium Taste".
  - If a theme/description is provided (not a literal label), it MUST guide the visual storytelling without quoting.
  - Only if fields are explicitly empty should you synthesize contextually relevant labels based on user intent, style direction, and color scheme. Synthesized labels must also be quoted.
  - Main Title: "${s.title || ''}" — treat as literal visible text in the design; always quote it in the prompt.
  - Sub-text: "${s.subtext || ''}" — treat as literal visible text in the design; always quote it in the prompt.
 - TYPOGRAPHY:
   ${fontRule}
 - COLOR LOGIC:
   ${colorRule}
 - ASPECT RATIO (MANDATORY):
   * Target ratio: ${ratioStr}
   * EVERY prompt MUST explicitly mention the aspect ratio and orientation in the composition description (e.g., "16:9 landscape layout", "21:9 ultrawide", "9:16 vertical portrait", "1:1 square canvas", "4:3 portrait", "3:4 portrait", "9:21 tall vertical"). Do not omit this.
 - VISUAL STYLE / PIVOT: "${styleStr}"
- PROHIBITED: No physical mockups, no real-world photography of products, no real props, no paper textures, no real surfaces, no hands/people/rooms. This is a pure design artwork file.

[VARIATION REQUIREMENT FOR MULTIPLE PROMPTS]
When generating more than one prompt (Number of Variations > 1), EACH prompt MUST be meaningfully different from the others while staying true to the core Graphic DNA. Vary these aspects:
- COLOR DISTRIBUTION: Swap color roles (e.g., make the accent color the primary, or the secondary become dominant). Introduce gradients or color shifts.
- DOMINANT VISUAL ELEMENT: Change what dominates the composition — focus on typography in one, geometric shapes in another, texture/pattern in another, while keeping the theme.
- OBJECT substitutions: Keep the same overall theme/message but replace specific objects.
- COMPOSITION LAYOUT: Vary between centered, asymmetric, grid-based, radial, or layered compositions.
- MOOD & ENERGY: Vary between calm and minimal, vibrant and dynamic, soft and dreamy, bold and graphic.
All variations must still follow all rules above (full-bleed, text quotes, no prohibited elements).

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
- User Intent (Additional Context): "${s.additionalContext || 'MANDATORY: Follow the extracted design DNA'}"
- Visual Style / Pivot: "${styleStr}"
- Color Constraints: "${colorStr}"
- Aspect Ratio: ${ratioStr}
- Number of Variations: ${s.count}
- Description Detail: ${lengthDesc}

CRITICAL: The "Main Title" and "Sub-text" above are absolute requirements and will be rendered as visible text in the final design. Always wrap them in double quotes inside the prompt text. If they are empty, synthesize appropriate labels based on the user intent, visual style, and color direction, then quote them. DO NOT reference any input image or DNA extraction process in the final prompts — describe the finished design directly. Return JSON only.`;
  }

  async function callGemini(s) {
    const parts = [];
    const main = dataUrlToPart(s.imageData);
    const font = dataUrlToPart(s.fontImageData);
    if (main) {
      parts.push({ text: 'DESIGN DNA REFERENCE: Analyze this image to extract its visual language — color relationships, geometric rhythm, typography mannerisms, texture vocabulary, and compositional logic. You will use this DNA to author standalone design prompts that describe the final artwork directly (no "based on" or "replicate" phrasing).' });
      parts.push({ inlineData: main });
    }
    if (font) {
      parts.push({ text: 'TYPOGRAPHY DNA: Analyze this font reference to understand its letterform personality, weight, and treatment. You will apply these typographic principles directly in the prompts.' });
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
      userContent.push({ type: 'text', text: 'DESIGN DNA REFERENCE: Analyze this image to extract its visual language — color relationships, geometric rhythm, typography mannerisms, texture vocabulary, and compositional logic. You will use this DNA to author standalone design prompts that describe the final artwork directly (no "based on" or "replicate" phrasing).' });
      userContent.push({ type: 'image_url', image_url: { url: s.imageData } });
    }
    if (s.fontImageData) {
      userContent.push({ type: 'text', text: 'TYPOGRAPHY DNA: Analyze this font reference to understand its letterform personality, weight, and treatment. You will apply these typographic principles directly in the prompts.' });
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
    // Use appropriate aspect ratio based on current automation mode
    if (s.automationMode === 'injector') {
      s.ratio = s.injectorRatio || s.ratio;
    }
    if (!s.apiKey) return appendLog('API key is required.', 'error');
    if (!s.endpoint) return appendLog('Endpoint URL is required.', 'error');
    if (!s.model) return appendLog('Model name is required.', 'error');
    if (generatorMode === 'mockup') {
      if (!s.imageData && !s.mockupContext) return appendLog('Upload an image or enter a context description first.', 'error');
    } else {
      if (!s.imageData && !s.title) return appendLog('Upload an image or enter a title first.', 'error');
    }
    const btn = $('btnGenerate');
    if (btn) { btn.disabled = true; btn.classList.add('loading'); btn.textContent = 'Generating...'; }
    isGenerating = true;
    document.querySelector('[data-tab="prompts"]')?.click();
    renderPrompts();
    appendLog(`Generating ${generatorMode} prompts...`, 'act');
    try {
      const raw = s.provider === 'gemini' ? await callGeminiDual(s) : await callOpenAIDual(s);
      const data = parseResponse(raw);
      prompts = data.prompts || [];
      analysis = data.analysis || '';
      statuses = {};
      isGenerating = false;
      renderPrompts();
      await saveSettings();
      appendLog(`Generated ${prompts.length} ${generatorMode} prompts successfully.`, 'success');
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

  // ── Dual-mode API Calls ──────────────────────────────────────────────────
  async function callGeminiDual(s) {
    if (generatorMode === 'mockup') return callGeminiMockup(s);
    return callGemini(s);
  }

  async function callOpenAIDual(s) {
    if (generatorMode === 'mockup') return callOpenAIMockup(s);
    return callOpenAI(s);
  }

  async function callGeminiMockup(s) {
    const parts = [];
    const main = dataUrlToPart(s.imageData);
    if (main) {
      parts.push({ text: 'REFERENCE IMAGE: Analyze this image to identify the primary object type, shape, material, and context. You will use this to generate appropriate blank white mockup base prompts. Do NOT replicate any designs or text from this image.' });
      parts.push({ inlineData: main });
    }
    parts.push({ text: buildMockupUserMessage(s) });
    const base = s.endpoint.replace(/\/$/, '');
    const url = `${base}/models/${encodeURIComponent(s.model)}:generateContent?key=${encodeURIComponent(s.apiKey)}`;
    const body = {
      contents: [{ parts }],
      generationConfig: { temperature: 0.3, responseMimeType: 'application/json' },
      systemInstruction: { parts: [{ text: buildMockupSystemInstruction(s) }] }
    };
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!res.ok) {
      let errMsg = res.statusText;
      try { const json = await res.json(); errMsg = json.error?.message || JSON.stringify(json); } catch (_) {}
      throw new Error(errMsg);
    }
    const json = await res.json();
    const text = json.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) throw new Error('Empty response from Gemini API');
    return text;
  }

  async function callOpenAIMockup(s) {
    const userContent = [];
    if (s.imageData) {
      userContent.push({ type: 'text', text: 'REFERENCE IMAGE: Analyze this image to identify the primary object type, shape, material, and context. You will use this to generate appropriate blank white mockup base prompts. Do NOT replicate any designs or text from this image.' });
      userContent.push({ type: 'image_url', image_url: { url: s.imageData } });
    }
    userContent.push({ type: 'text', text: buildMockupUserMessage(s) });
    const url = buildOpenAIChatUrl(s.endpoint);
    const body = {
      model: s.model,
      messages: [
        { role: 'system', content: buildMockupSystemInstruction(s) },
        { role: 'user', content: userContent }
      ],
      temperature: 0.3,
      response_format: { type: 'json_object' }
    };
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + s.apiKey }, body: JSON.stringify(body) });
    if (!res.ok) {
      let errMsg = res.statusText;
      try { const json = await res.json(); errMsg = json.error?.message || JSON.stringify(json); } catch (_) {}
      throw new Error(errMsg);
    }
    const json = await res.json();
    const text = json.choices?.[0]?.message?.content;
    if (!text) throw new Error('Empty response from OpenAI-compatible API');
    return text;
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
