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
    bindStyleButtons();
    bindDetailButtons();
    bindColorInputs();
    bindFontInputs();
    bindGenerateButton();
    bindLogButtons();
    bindAutoSubmitToggle();
    bindPersistenceInputs();
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

  // ── Style Buttons ─────────────────────────────────────────────────────────
  function bindStyleButtons() {
    document.querySelectorAll('.style-btn').forEach(b => {
      b.addEventListener('click', () => {
        selectedStyle = selectedStyle === b.dataset.style ? '' : b.dataset.style;
        updateStyleUI();
        saveSettings();
      });
    });
  }
  function updateStyleUI() {
    document.querySelectorAll('.style-btn').forEach(b => b.classList.toggle('active', b.dataset.style === selectedStyle));
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

  // ── Color Inputs ──────────────────────────────────────────────────────────
  function bindColorInputs() {
    ['color60','color30','color10'].forEach(id => {
      const el = $(id);
      if (el) el.addEventListener('input', () => { syncColorVal(id); saveSettings(); });
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
        if (el) { el.value = '#' + Math.floor(Math.random()*16777215).toString(16).padStart(6,'0'); syncColorVal(id); }
      });
      saveSettings();
    });
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

  // ── Persistence inputs ────────────────────────────────────────────────────
  function bindPersistenceInputs() {
    ['paramTitle','paramSubtitle','paramContext','paramCustomStyle','paramCustomFont','apiProvider','apiKey','apiEndpoint','apiModel'].forEach(id => {
      const el = $(id); if (el) el.addEventListener('input', saveSettings);
    });
    document.querySelectorAll('input[name="ratio"],input[name="quality"],input[name="batch"]').forEach(el => el.addEventListener('change', saveSettings));
    const fs = $('paramFontStyle'); if (fs) fs.addEventListener('change', saveSettings);
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
      analysis
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
      const fs = $('paramFontStyle');
      if (fs) fs.value = s.fontStyle?.startsWith('Custom:') ? 'Custom Description' : (s.fontStyle || 'Auto/Mimic Reference');
      if ($('paramCustomFont')) $('paramCustomFont').value = s.customFont || '';
      detailLevel = s.length || 'medium';
      strictColor = s.strictColor !== false;
      autoSubmit = s.autoSubmit === true;
      if ($('color60')) $('color60').value = s.color60 || '#3b82f6';
      if ($('color30')) $('color30').value = s.color30 || '#ffffff';
      if ($('color10')) $('color10').value = s.color10 || '#fbbf24';
      if ($('apiProvider')) $('apiProvider').value = s.provider || 'gemini';
      if ($('apiKey')) $('apiKey').value = s.apiKey || '';
      if ($('apiEndpoint')) $('apiEndpoint').value = s.endpoint || 'https://generativelanguage.googleapis.com/v1beta';
      if ($('apiModel')) $('apiModel').value = s.model || 'gemini-2.0-flash';
      imageData = s.imageData || null;
      fontImageData = s.fontImageData || null;
      prompts = s.prompts || [];
      analysis = s.analysis || '';
      checkRadio('ratio', s.ratio || '16:9');
      checkRadio('quality', s.downloadQuality || 'default');
      checkRadio('batch', s.batch || '4');
      syncAllColors();
      updateStyleUI();
      updateDetailUI();
      const toggle = $('toggleStrictColor');
      if (toggle) toggle.classList.toggle('active', strictColor);
      const toggleAS = $('toggleAutoSubmit');
      if (toggleAS) toggleAS.classList.toggle('active', autoSubmit);
      const cf = $('paramCustomFont');
      if (cf && fs) cf.classList.toggle('hidden', fs.value !== 'Custom Description');
      renderMainImage();
      renderFontImage();
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
    return `MANDATORY USER PARAMETERS:
- Main Title: "${s.title || 'MANDATORY: Extract from image context'}" — this is literal visible text that will appear in the design; wrap it in double quotes in your prompt exactly as given.
- Sub-text (Details): "${s.subtext || 'MANDATORY: Extract from image context'}" — this is literal visible text that will appear in the design; wrap it in double quotes in your prompt exactly as given.
- User Intent (Additional Context): "${s.additionalContext || 'MANDATORY: Follow Reference DNA exactly'}"
- Visual Style / Pivot: "${styleStr}"
- Color Constraints: "${colorStr}"
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
      contents: { parts },
      generationConfig: { temperature: 0.2, responseMimeType: 'application/json' },
      systemInstruction: { parts: [{ text: buildSystemInstruction(s) }] }
    };
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error?.message || res.statusText);
    return json.candidates?.[0]?.content?.parts?.[0]?.text || '';
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
    const base = s.endpoint.replace(/\/$/, '');
    const url = `${base}/chat/completions`;
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
    const json = await res.json();
    if (!res.ok) throw new Error(json.error?.message || res.statusText);
    return json.choices?.[0]?.message?.content || '';
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
      appendLog('Generate failed: ' + e.message, 'error');
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
      <button class="prompt-clear-btn" id="btnClearPrompts">Clear All</button>
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
              ${st === 'inserting' ? 'Inserting...' : st === 'monitoring' ? 'Stop' : 'Insert'}
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
    document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () => navigator.clipboard.writeText(prompts[+b.dataset.copy])));
    document.querySelectorAll('[data-insert]').forEach(b => {
      b.addEventListener('click', () => {
        const idx = +b.dataset.insert;
        if (b.classList.contains('stop-monitor') && statuses[idx] === 'monitoring') {
          stopMonitoring(idx);
        } else {
          insertPrompt(idx);
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
