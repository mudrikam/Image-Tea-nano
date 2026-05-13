// Mockup Preview Prompt - Content Script
if (window.top !== window.self) {
  // skip iframes
} else {
  (function () {
    if (window.__MPP_CONTENT_LOADED__) return;
    window.__MPP_CONTENT_LOADED__ = true;

    const isFlowPage = location.href.includes('labs.google') && location.href.includes('/tools/flow');

    let isRunning = true;

    function safeMsg(msg) {
      try {
        const r = chrome.runtime.sendMessage(msg);
        if (r && typeof r.catch === 'function') r.catch(() => {});
      } catch (_) {}
    }

    function log(msg) {
      safeMsg({ action: 'LOG_FROM_CONTENT', message: msg });
      console.log('[MPP]', msg);
    }

    function isVisible(el) {
      if (!el || !(el instanceof HTMLElement)) return false;
      const r = el.getBoundingClientRect(), s = window.getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
    }

    function findEditor() {
      return document.querySelector('[data-slate-editor="true"]') ||
             document.querySelector('[role="textbox"][contenteditable="true"]') ||
             document.querySelector('.sc-522e4d41-5.gihCJr');
    }

    function getParagraph(editor) {
      return editor.querySelector('p[data-slate-node="element"]') ||
             editor.querySelector('p') ||
             editor.querySelector('div[data-slate-node="element"]') ||
             editor.firstElementChild ||
             editor;
    }

    // ── Type text char by char ──────────────────────────────────────────────
    async function typeText(element, text) {
      if (!text) return;
      const sel = window.getSelection();
      let range = sel.rangeCount > 0 ? sel.getRangeAt(0) : null;
      if (!range || !element.contains(range.commonAncestorContainer)) {
        range = document.createRange();
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null, false);
        let last = null;
        while (walker.nextNode()) last = walker.currentNode;
        if (last) { range.setStartAfter(last); range.setEndAfter(last); }
        else { range.setStart(element, 0); range.setEnd(element, 0); }
        sel.removeAllRanges();
        sel.addRange(range);
      }
      for (let i = 0; i < text.length && isRunning; i++) {
        const char = text[i];
        let delay = Math.random() * 10 + 3;
        if (char === ' ') delay *= 2;
        await new Promise(r => setTimeout(r, delay));
        if (!isRunning) break;
        const key = char === ' ' ? ' ' : char;
        const code = 'Key' + key.toUpperCase();
        const kc = key.charCodeAt(0);
        element.dispatchEvent(new KeyboardEvent('keydown', { key, code, keyCode: kc, which: kc, bubbles: true, cancelable: true }));
        const bi = new InputEvent('beforeinput', { inputType: 'insertText', data: char, bubbles: true, cancelable: true });
        const canceled = !element.dispatchEvent(bi);
        if (!canceled) element.dispatchEvent(new InputEvent('input', { inputType: 'insertText', data: char, bubbles: true }));
        element.dispatchEvent(new KeyboardEvent('keyup', { key, code, keyCode: kc, which: kc, bubbles: true }));
      }
      element.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // ── Mouse helpers ───────────────────────────────────────────────────────
    function dispatchMouse(el, label) {
      const r = el.getBoundingClientRect(), cx = r.left + r.width/2, cy = r.top + r.height/2;
      ['pointermove','mouseover','mousemove'].forEach(t => el.dispatchEvent(new MouseEvent(t, { bubbles: true, clientX: cx, clientY: cy })));
      el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: cx, clientY: cy, button: 0, pointerType: 'mouse' }));
      el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: cx, clientY: cy, button: 0 }));
      el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, clientX: cx, clientY: cy, button: 0, pointerType: 'mouse' }));
      el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: cx, clientY: cy, button: 0 }));
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: cx, clientY: cy, button: 0 }));
      log('Mouse click: ' + label);
    }

    // ── CDP click via background ────────────────────────────────────────────
    async function cdpClick(x, y) {
      try {
        const res = await new Promise(resolve => {
          chrome.runtime.sendMessage({ type: 'CDP_CLICK', x, y }, r => {
            if (chrome.runtime.lastError) resolve({ ok: false });
            else resolve(r || { ok: false });
          });
        });
        return res && res.ok;
      } catch (_) { return false; }
    }

    // ── Variant button (ratio/batch popup) ─────────────────────────────────
    async function clickVariantButton() {
      for (let attempt = 0; attempt < 20; attempt++) {
        const buttons = Array.from(document.querySelectorAll('button[aria-haspopup="menu"]'));
        let btn = buttons.find(b => {
          const txt = b.textContent || '';
          return isVisible(b) && !b.disabled && (txt.includes('Image') || txt.includes('Video') || txt.includes('Imagen') || txt.includes('Nano'));
        }) || (buttons.length === 1 ? buttons[0] : null);
        if (btn) {
          dispatchMouse(btn, 'variant button');
          await new Promise(r => setTimeout(r, 800));
          const menu = document.querySelector('div[role="menu"][data-state="open"]');
          if (menu) { log('Variant popup opened'); return true; }
        }
        await new Promise(r => setTimeout(r, 200));
      }
      return false;
    }

    function isBatchTab(txt, batch) {
      const n = txt.toLowerCase().replace(/\s/g, '');
      return n === batch + 'x' || n === 'x' + batch;
    }

    async function selectModeTab(ratio, batch) {
      for (let attempt = 0; attempt < 10; attempt++) {
        const menu = document.querySelector('div[role="menu"][data-state="open"]');
        if (!menu) { await new Promise(r => setTimeout(r, 150)); continue; }
        const tabs = Array.from(menu.querySelectorAll('button[role="tab"]'));
        // Select Image tab
        const imgTab = tabs.find(t => t.textContent.trim().toUpperCase().includes('IMAGE'));
        if (imgTab && imgTab.getAttribute('aria-selected') !== 'true') {
          dispatchMouse(imgTab, 'Image tab');
          await new Promise(r => setTimeout(r, 400));
        }
        // Select ratio
        if (ratio) {
          const updMenu = document.querySelector('div[role="menu"][data-state="open"]');
          if (updMenu) {
            const ratioTab = Array.from(updMenu.querySelectorAll('button[role="tab"]')).find(t => t.textContent.trim().includes(ratio));
            if (ratioTab && ratioTab.getAttribute('aria-selected') !== 'true') {
              dispatchMouse(ratioTab, 'ratio tab ' + ratio);
              await new Promise(r => setTimeout(r, 300));
            }
          }
        }
        // Select batch
        if (batch) {
          const updMenu2 = document.querySelector('div[role="menu"][data-state="open"]');
          if (updMenu2) {
            const batchTab = Array.from(updMenu2.querySelectorAll('button[role="tab"]')).find(t => isBatchTab(t.textContent.trim(), batch));
            if (batchTab && batchTab.getAttribute('aria-selected') !== 'true') {
              dispatchMouse(batchTab, 'batch tab x' + batch);
              await new Promise(r => setTimeout(r, 300));
            }
          }
        }
        return true;
      }
      return false;
    }

    async function closePopupMenu() {
      for (let attempt = 0; attempt < 5; attempt++) {
        const menu = document.querySelector('div[role="menu"][data-state="open"]');
        if (!menu) { log('Popup already closed'); return; }
        // Focus menu then send Escape — this is the reliable strategy on Flow
        menu.focus();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true }));
        await new Promise(r => setTimeout(r, 300));
        if (!document.querySelector('div[role="menu"][data-state="open"]')) { log('Popup closed via Escape'); return; }
      }
      log('WARN: Popup may still be open after Escape attempts');
    }
    // ── Find and click the Generate/Submit button ───────────────────────────
    function getButtonText(btn) {
      return (btn?.textContent || '').replace(/\s+/g, ' ').trim();
    }

    function isButtonDisabled(btn) {
      return !btn || btn.disabled ||
             btn.getAttribute('aria-disabled') === 'true' ||
             btn.getAttribute('data-disabled') === 'true';
    }

    function findCreateButton() {
      const buttons = Array.from(document.querySelectorAll('button'));
      const candidates = [];
      for (const btn of buttons) {
        const txt = getButtonText(btn);
        const lowerText = txt.toLowerCase();
        const html = btn.innerHTML || '';
        const iconTexts = Array.from(btn.querySelectorAll('i, .google-symbols'))
          .map(icon => (icon.textContent || icon.innerHTML || '').trim())
          .join(' ');
        const accessibleText = [txt, btn.getAttribute('aria-label') || '', btn.getAttribute('title') || '', iconTexts].join(' ').toLowerCase();
        const hasArrow = html.includes('arrow_forward') || iconTexts.includes('arrow_forward') || accessibleText.includes('arrow_forward');
        const hasCreate = lowerText.includes('create') || accessibleText.includes('create') || btn.querySelector('span')?.textContent?.trim().toLowerCase() === 'create';
        const hasAdd2 = html.includes('add_2') || iconTexts.includes('add_2');
        const isDialog = btn.getAttribute('aria-haspopup') === 'dialog';
        const isMenuButton = btn.getAttribute('aria-haspopup') === 'menu';
        if (!hasArrow || hasAdd2 || isDialog || isMenuButton) continue;
        if (!hasCreate && !lowerText.includes('arrow_forward')) continue;
        if (!isVisible(btn) || isButtonDisabled(btn)) continue;
        const rect = btn.getBoundingClientRect();
        candidates.push({ btn, score: (hasCreate ? 10 : 0) + rect.width + rect.height });
      }
      candidates.sort((a, b) => b.score - a.score);
      return candidates[0]?.btn || null;
    }

    async function clickCreateTarget(element, label) {
      if (!element) return;
      element.scrollIntoView?.({ behavior: 'instant', block: 'center', inline: 'center' });
      await new Promise(r => setTimeout(r, 40));
      const rect = element.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const ei = { bubbles: true, cancelable: true, composed: true, clientX: cx, clientY: cy, button: 0, buttons: 1 };
      const pi = { ...ei, pointerId: 1, pointerType: 'mouse', isPrimary: true };
      element.focus?.();
      element.dispatchEvent(new PointerEvent('pointerover', pi));
      element.dispatchEvent(new PointerEvent('pointerenter', { ...pi, bubbles: false }));
      element.dispatchEvent(new MouseEvent('mouseover', ei));
      element.dispatchEvent(new MouseEvent('mouseenter', { ...ei, bubbles: false }));
      element.dispatchEvent(new PointerEvent('pointermove', pi));
      element.dispatchEvent(new MouseEvent('mousemove', ei));
      element.dispatchEvent(new PointerEvent('pointerdown', pi));
      element.dispatchEvent(new MouseEvent('mousedown', ei));
      await new Promise(r => setTimeout(r, 80));
      element.dispatchEvent(new PointerEvent('pointerup', { ...pi, buttons: 0 }));
      element.dispatchEvent(new MouseEvent('mouseup', { ...ei, buttons: 0 }));
      element.dispatchEvent(new MouseEvent('click', { ...ei, buttons: 0, detail: 1 }));
      element.click?.();
      log('Synthetic click sent to ' + label);
    }

    function hasGenerationStarted(beforeIds) {
      const current = getCurrentTileIds();
      if ([...current].filter(id => !beforeIds.has(id)).length > 0) return true;
      const busy = document.querySelector('[aria-busy="true"],[role="progressbar"],[class*="progress"],[class*="loading"]');
      return Boolean(busy && isVisible(busy));
    }

    async function clickGenerateButton(beforeIds) {
      const TIMEOUT_MS = 15000;
      const start = Date.now();
      let attempt = 0;
      while (Date.now() - start < TIMEOUT_MS && isRunning) {
        attempt++;
        const createBtn = findCreateButton();
        if (!createBtn) {
          log('Create button not found (attempt ' + attempt + ')');
          await new Promise(r => setTimeout(r, 300));
          continue;
        }
        createBtn.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
        await new Promise(r => setTimeout(r, 150));
        const rect = createBtn.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        log('Trying CDP click on Create button at (' + Math.round(cx) + ',' + Math.round(cy) + ')');
        const cdpOk = await cdpClick(cx, cy);
        if (cdpOk) {
          await new Promise(r => setTimeout(r, 800));
          if (hasGenerationStarted(beforeIds)) { log('Auto-submit: Create verified via CDP'); return true; }
        }
        await clickCreateTarget(createBtn, 'Create button');
        await new Promise(r => setTimeout(r, 600));
        if (hasGenerationStarted(beforeIds)) { log('Auto-submit: Create verified via synthetic click'); return true; }
        const icon = createBtn.querySelector('i, .google-symbols');
        if (icon) {
          await clickCreateTarget(icon, 'Create icon');
          await new Promise(r => setTimeout(r, 400));
          if (hasGenerationStarted(beforeIds)) { log('Auto-submit: Create verified via icon click'); return true; }
        }
        await new Promise(r => setTimeout(r, 200));
      }
      log('Auto-submit: Create button click failed after ' + attempt + ' attempts');
      return false;
    }
    function getCurrentTileIds() {
      const ids = new Set();
      document.querySelectorAll('[data-tile-id]').forEach(t => {
        const id = t.getAttribute('data-tile-id');
        if (id && id.startsWith('fe_id_')) ids.add(id);
      });
      return ids;
    }

    async function monitorForNewImages(beforeIds, expectedCount, promptIndex) {
      const MAX_WAIT = 180000;
      const POLL = 1500;
      const start = Date.now();
      const seenIds = new Set();
      const foundTiles = [];
      log('Monitoring for ' + expectedCount + ' new image(s)... (180s timeout)');

      // Send countdown every second via interval
      let lastRemaining = Math.ceil(MAX_WAIT / 1000);
      safeMsg({ action: 'MONITOR_COUNTDOWN', remaining: lastRemaining, promptIndex });
      const countdownInterval = setInterval(() => {
        const remaining = Math.max(0, Math.ceil((MAX_WAIT - (Date.now() - start)) / 1000));
        if (remaining !== lastRemaining) {
          lastRemaining = remaining;
          safeMsg({ action: 'MONITOR_COUNTDOWN', remaining, promptIndex });
        }
      }, 1000);

      while (Date.now() - start < MAX_WAIT) {
        if (!isRunning) break;

        const current = getCurrentTileIds();
        current.forEach(id => {
          if (beforeIds.has(id) || seenIds.has(id)) return;
          const tile = document.querySelector('[data-tile-id="' + id + '"]');
          if (!tile) return;
          const media = tile.querySelector('img[src*="media.getMediaUrlRedirect"], video[src*="media.getMediaUrlRedirect"]');
          if (!media) return;
          const src = media.src || media.getAttribute('src');
          if (src && src.includes('name=')) {
            seenIds.add(id);
            foundTiles.push({ tileId: id, url: src });
            log('New tile detected: ' + id.substring(0, 12));
          }
        });

        if (seenIds.size >= expectedCount) {
          log('All ' + expectedCount + ' image(s) detected. Downloading...');
          break;
        }
        await new Promise(r => setTimeout(r, POLL));
      }

      clearInterval(countdownInterval);
      safeMsg({ action: 'MONITOR_COUNTDOWN', remaining: 0, promptIndex });

      if (foundTiles.length === 0) {
        safeMsg({ action: 'PROMPT_STATUS', promptIndex: promptIndex, status: 'failed', message: 'Prompt #' + (promptIndex+1) + ': No new images detected (timeout).' });
        return;
      }

      foundTiles.slice(0, expectedCount).forEach(function(t, i) {
        safeMsg({ type: 'DOWNLOAD_CONTENT', url: t.url, promptIndex: promptIndex, batchIndex: i, extension: 'jpg', prefix: 'Mockup_Preview' });
      });

      safeMsg({ action: 'PROMPT_STATUS', promptIndex: promptIndex, status: 'downloaded', message: 'Prompt #' + (promptIndex+1) + ': ' + foundTiles.length + ' image(s) downloaded.' });
    }

    // -- Main insert handler -------------------------------------------------
    async function insertPrompt(prompt, promptIndex, settings) {
      try {
        log('Inserting prompt #' + (promptIndex+1));

        let editor = null;
        for (let i = 0; i < 20; i++) {
          editor = findEditor();
          if (editor) break;
          await new Promise(r => setTimeout(r, 150));
        }
        if (!editor) throw new Error('Editor not found on page');

        editor.focus();
        await new Promise(r => setTimeout(r, 150));

        const pEl = getParagraph(editor);
        const range = document.createRange();
        range.selectNodeContents(pEl);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        await new Promise(r => setTimeout(r, 100));

        const freshP = getParagraph(editor);
        const freshRange = document.createRange();
        freshRange.selectNodeContents(freshP);
        sel.removeAllRanges();
        sel.addRange(freshRange);
        await typeText(freshP, prompt);
        log('Prompt typed into editor');

        const clicked = await clickVariantButton();
        if (clicked) {
          await selectModeTab(settings.ratio, settings.batch);
          await closePopupMenu();
          log('Settings applied: ratio=' + settings.ratio + ', batch=x' + settings.batch);
        }

        const beforeIds = getCurrentTileIds();
        log('Pre-generate snapshot: ' + beforeIds.size + ' existing tiles');

        if (settings.autoSubmit) {
          await new Promise(r => setTimeout(r, 400));
          await clickGenerateButton(beforeIds);
        }

        // Start monitoring in background (non-blocking)
        monitorForNewImages(beforeIds, parseInt(settings.batch) || 4, promptIndex);

        return { status: 'inserted', message: 'Prompt inserted. Click Generate in Flow.' };

      } catch (e) {
        log('Insert error: ' + e.message);
        return { status: 'failed', message: e.message };
      }
    }

    // -- Flow project ready --------------------------------------------------
    function isFlowProjectPage() {
      return location.href.includes('/tools/flow/project/');
    }

    function findNewProjectButton() {
      const buttons = Array.from(document.querySelectorAll('button'));
      const byText = buttons.find(b => {
        const txt = (b.textContent || '').replace(/\s+/g, ' ').trim();
        return isVisible(b) && !b.disabled && txt.includes('New project') && txt.includes('add_2');
      });
      if (byText) return byText;
      const byIcon = buttons.find(b => {
        if (!isVisible(b) || b.disabled) return false;
        if (b.getAttribute('aria-haspopup') === 'dialog') return false;
        const html = b.innerHTML || '';
        if (!html.includes('add_2')) return false;
        if (b.closest('[role="toolbar"]')) return false;
        if (html.includes('arrow_forward')) return false;
        return true;
      });
      if (byIcon) return byIcon;
      return buttons.find(b => {
        const txt = (b.textContent || '').replace(/\s+/g, ' ').trim();
        return isVisible(b) && !b.disabled && txt === 'New project';
      });
    }

    async function ensureFlowProjectReady() {
      if (isFlowProjectPage() && findEditor()) return;
      if (!isFlowProjectPage()) {
        log('Flow landing page — creating new project...');
        let clicked = false;
        for (let i = 0; i < 40 && isRunning; i++) {
          const btn = findNewProjectButton();
          if (btn) {
            btn.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
            await new Promise(r => setTimeout(r, 100));
            dispatchMouse(btn, 'New project button');
            clicked = true;
            break;
          }
          await new Promise(r => setTimeout(r, 250));
        }
        if (!clicked) throw new Error('New project button not found');
      }
      const start = Date.now();
      while (Date.now() - start < 30000 && isRunning) {
        if (isFlowProjectPage()) {
          const editor = findEditor();
          if (editor && isVisible(editor)) {
            log('Flow project ready: ' + location.href);
            await new Promise(r => setTimeout(r, 1500));
            return;
          }
        }
        await new Promise(r => setTimeout(r, 250));
      }
      if (!isRunning) throw new Error('Stopped while waiting for Flow project');
      throw new Error('Timed out waiting for Flow project editor');
    }

    // -- Universal Prompt Injector helpers -----------------------------------
    let pickerActive = false;
    let pickerPointIndex = null;
    let highlightedElement = null;
    let highlightOverlay = null;
    let highlightLabel = null;
    let injectorRunning = false;
    let injectorPaused = false;
    let injectorSessionId = null;
    const downloadedUrls = new Set();

    function deepQuerySelectorAll(rootElement, selector) {
      const results = [];
      const traverse = (element) => {
        if (!element) return;
        try { if (element.matches && element.matches(selector)) results.push(element); } catch (_) {}
        try { element.querySelectorAll(selector).forEach(child => results.push(child)); } catch (_) {}
        if (element.shadowRoot) {
          try { element.shadowRoot.querySelectorAll(selector).forEach(child => results.push(child)); } catch (_) {}
          try { element.shadowRoot.querySelectorAll('*').forEach(el => { if (el.shadowRoot) traverse(el); }); } catch (_) {}
        }
        try { element.querySelectorAll('*').forEach(el => { if (el.shadowRoot) traverse(el); }); } catch (_) {}
      };
      traverse(rootElement);
      return results;
    }
    function deepQuerySelector(rootElement, selector) { return deepQuerySelectorAll(rootElement, selector)[0] || null; }
    function getAllMediaUrls() {
      const allUrls = new Set();
      deepQuerySelectorAll(document, 'img').forEach(img => {
        const src = img.src || img.currentSrc || img.getAttribute('data-src');
        if (!src || src.startsWith('data:image/svg') || src.includes('placeholder')) return;
        if ((img.naturalWidth || 0) >= 500 || (img.naturalHeight || 0) >= 500) allUrls.add(src);
      });
      deepQuerySelectorAll(document, 'video').forEach(video => {
        const src = video.src || video.currentSrc || video.querySelector('source')?.src;
        if (src) allUrls.add(src);
      });
      deepQuerySelectorAll(document, 'canvas').forEach(canvas => {
        if (canvas.width >= 500 || canvas.height >= 500) { try { allUrls.add(canvas.toDataURL('image/png')); } catch (_) {} }
      });
      deepQuerySelectorAll(document, '[style*="background"]').forEach(el => {
        const bgImage = getComputedStyle(el).backgroundImage;
        const m = bgImage && bgImage.match(/url\(["']?([^"')]+)["']?\)/);
        if (m?.[1] && !m[1].startsWith('data:image/svg')) {
          const rect = el.getBoundingClientRect();
          if (rect.width >= 500 || rect.height >= 500) allUrls.add(m[1]);
        }
      });
      return allUrls;
    }
    function findNewMediaContent(count, urlPattern, excludeUrls = new Set()) {
      const matchesPattern = url => !urlPattern || !urlPattern.trim() || url.startsWith(urlPattern.trim());
      const newMedia = [];
      deepQuerySelectorAll(document, 'img').forEach(img => {
        const src = img.src || img.currentSrc || img.getAttribute('data-src');
        if (!src || excludeUrls.has(src) || downloadedUrls.has(src) || src.startsWith('data:image/svg') || src.includes('placeholder') || !matchesPattern(src)) return;
        const width = img.naturalWidth || 0, height = img.naturalHeight || 0;
        if ((urlPattern && urlPattern.trim() && width > 0 && height > 0) || width >= 500 || height >= 500) newMedia.push({ url: src, type: 'image', width, height });
      });
      deepQuerySelectorAll(document, 'video').forEach(video => {
        const src = video.src || video.currentSrc || video.querySelector('source')?.src;
        if (!src || excludeUrls.has(src) || downloadedUrls.has(src) || !matchesPattern(src)) return;
        const width = video.videoWidth || 0, height = video.videoHeight || 0;
        if ((urlPattern && urlPattern.trim()) || width >= 500 || height >= 500) newMedia.push({ url: src, type: 'video', width, height });
      });
      deepQuerySelectorAll(document, 'canvas').forEach(canvas => {
        if (canvas.width >= 500 || canvas.height >= 500) { try { const url = canvas.toDataURL('image/png'); if (!excludeUrls.has(url) && !downloadedUrls.has(url)) newMedia.push({ url, type: 'canvas', width: canvas.width, height: canvas.height }); } catch (_) {} }
      });
      deepQuerySelectorAll(document, '[style*="background"]').forEach(el => {
        const bgImage = getComputedStyle(el).backgroundImage;
        const m = bgImage && bgImage.match(/url\(["']?([^"')]+)["']?\)/);
        const src = m?.[1];
        if (!src || excludeUrls.has(src) || downloadedUrls.has(src) || src.startsWith('data:image/svg') || !matchesPattern(src)) return;
        const rect = el.getBoundingClientRect();
        if (rect.width >= 500 || rect.height >= 500) newMedia.push({ url: src, type: 'background', width: rect.width, height: rect.height });
      });
      newMedia.sort((a, b) => (b.width * b.height) - (a.width * a.height));
      const seen = new Set();
      return newMedia.filter(m => !seen.has(m.url) && seen.add(m.url)).slice(0, count);
    }
    function generateSelector(element) {
      if (!element || element === document.body || element === document.documentElement) return null;
      const tag = element.tagName.toLowerCase();
      if (element.id && !element.id.includes(':') && !element.id.includes(' ')) {
        const sel = '#' + CSS.escape(element.id); try { if (document.querySelectorAll(sel).length === 1) return sel; } catch (_) {}
      }
      for (const attr of ['data-testid','data-id','data-qa','aria-label','name','role','type','placeholder','title']) {
        const val = element.getAttribute(attr);
        if (val && val.length < 100) { const sel = `[${attr}="${CSS.escape(val)}"]`; try { if (document.querySelectorAll(sel).length === 1) return sel; } catch (_) {} }
      }
      const classes = Array.from(element.classList || []).filter(c => c && !c.includes(':') && !c.includes('[') && c.length < 50).slice(0, 3);
      if (classes.length) { const sel = '.' + classes.map(c => CSS.escape(c)).join('.'); try { if (document.querySelectorAll(sel).length === 1) return sel; } catch (_) {} }
      const path = [];
      let cur = element, depth = 0;
      while (cur && cur !== document.body && cur !== document.documentElement && depth < 8) {
        let sel = cur.tagName.toLowerCase();
        const parent = cur.parentElement;
        if (parent) {
          const siblings = Array.from(parent.children).filter(el => el.tagName === cur.tagName);
          if (siblings.length > 1) sel += `:nth-of-type(${siblings.indexOf(cur) + 1})`;
        }
        path.unshift(sel); cur = parent; depth++;
      }
      return path.join(' > ') || tag;
    }
    function createHighlightOverlay() {
      if (highlightOverlay || !document.body) return;
      highlightOverlay = document.createElement('div');
      highlightOverlay.style.cssText = 'position:fixed;pointer-events:none;border:3px solid #ff8800;background:rgba(255,136,0,.15);z-index:2147483647;display:none;box-shadow:0 0 0 9999px rgba(0,0,0,.3);';
      document.body.appendChild(highlightOverlay);
      highlightLabel = document.createElement('div');
      highlightLabel.style.cssText = 'position:fixed;pointer-events:none;background:#ff8800;color:#000;font-size:11px;font-family:monospace;padding:2px 6px;border-radius:3px;z-index:2147483647;display:none;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
      document.body.appendChild(highlightLabel);
    }
    function updateHighlight(element) {
      if (!element || !highlightOverlay) return;
      const rect = element.getBoundingClientRect();
      Object.assign(highlightOverlay.style, { left: rect.left + 'px', top: rect.top + 'px', width: rect.width + 'px', height: rect.height + 'px', display: 'block' });
      if (highlightLabel) { highlightLabel.textContent = `${element.tagName.toLowerCase()}${element.id ? '#' + element.id : ''}`; Object.assign(highlightLabel.style, { left: rect.left + 'px', top: Math.max(0, rect.top - 22) + 'px', display: 'block' }); }
    }
    function stopPicker() {
      pickerActive = false; pickerPointIndex = null; highlightedElement = null;
      document.removeEventListener('mousemove', onPickerMove, true); document.removeEventListener('click', onPickerClick, true); document.removeEventListener('keydown', onPickerKey, true);
      try { document.body.style.cursor = ''; } catch (_) {}
      highlightOverlay?.remove(); highlightLabel?.remove(); highlightOverlay = null; highlightLabel = null;
    }
    function onPickerMove(e) { if (!pickerActive) return; const el = document.elementFromPoint(e.clientX, e.clientY); if (el && el !== highlightedElement) { highlightedElement = el; updateHighlight(el); } }
    function onPickerClick(e) { if (!pickerActive) return; e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); const el = highlightedElement || document.elementFromPoint(e.clientX, e.clientY); const selector = generateSelector(el); if (selector) safeMsg({ type: 'ELEMENT_PICKED', pointIndex: pickerPointIndex, selector }); stopPicker(); return false; }
    function onPickerKey(e) { if (pickerActive && e.key === 'Escape') { e.preventDefault(); stopPicker(); } }
    function startPicker(pointIndex) { stopPicker(); pickerActive = true; pickerPointIndex = pointIndex; createHighlightOverlay(); document.addEventListener('mousemove', onPickerMove, true); document.addEventListener('click', onPickerClick, true); document.addEventListener('keydown', onPickerKey, true); document.body.style.cursor = 'crosshair'; }
    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
    async function waitWhileInjectorPaused() { while (injectorPaused && injectorRunning) await sleep(100); }
    
    // Typewriter effect for injector (consistent with Flow mode)
    async function typeTextInjector(element, text) {
      if (!text || !injectorRunning) return;
      element.focus();
      
      // Clear existing content first
      if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
        element.select();
        element.value = '';
      } else if (element.isContentEditable) {
        const r = document.createRange();
        r.selectNodeContents(element);
        const s = getSelection();
        s.removeAllRanges();
        s.addRange(r);
        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
      }
      
      // Type character by character
      for (let i = 0; i < text.length && injectorRunning; i++) {
        await waitWhileInjectorPaused();
        const char = text[i];
        let delay = Math.random() * 10 + 3;
        if (char === ' ') delay *= 2;
        await sleep(delay);
        if (!injectorRunning) break;
        
        const key = char === ' ' ? ' ' : char;
        const code = 'Key' + key.toUpperCase();
        const kc = key.charCodeAt(0);
        
        element.dispatchEvent(new KeyboardEvent('keydown', { key, code, keyCode: kc, which: kc, bubbles: true, cancelable: true }));
        const bi = new InputEvent('beforeinput', { inputType: 'insertText', data: char, bubbles: true, cancelable: true });
        const canceled = !element.dispatchEvent(bi);
        if (!canceled) {
          if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
            element.value += char;
          } else {
            document.execCommand('insertText', false, char);
          }
          element.dispatchEvent(new InputEvent('input', { inputType: 'insertText', data: char, bubbles: true }));
        }
        element.dispatchEvent(new KeyboardEvent('keyup', { key, code, keyCode: kc, which: kc, bubbles: true }));
      }
      
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
    }
    
    function simulateClick(element) { element.focus?.(); element.click?.(); element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true })); element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); }
    async function executeInjectorPoint(point, promptText) { if (!point.enabled || !point.selector) return true; let el; try { el = document.querySelector(point.selector) || deepQuerySelector(document, point.selector); } catch (_) {} if (!el) { safeMsg({ type: 'AUTOMATION_STATUS', text: 'Element not found: ' + point.selector, sessionId: injectorSessionId }); return true; } if (point.type === 'paste') await typeTextInjector(el, promptText); else simulateClick(el); return true; }
    async function requestDownload(payload) {
      try {
        return await new Promise(resolve => {
          chrome.runtime.sendMessage({ type: 'DOWNLOAD_CONTENT', ...payload }, response => {
            if (chrome.runtime.lastError) {
              resolve({ ok: false, error: chrome.runtime.lastError.message || 'Download message failed' });
              return;
            }
            resolve(response || { ok: false, error: 'No download response from background' });
          });
        });
      } catch (err) {
        return { ok: false, error: err.message || String(err) };
      }
    }

    async function runUniversalAutomation(config, automationPrompts, sessionId) {
      if (injectorRunning) return;
      injectorRunning = true; injectorPaused = false; injectorSessionId = sessionId || null;
      const enabledPoints = (config.points || []).filter(p => p.enabled && p.selector);
      if (!enabledPoints.length) { safeMsg({ type: 'AUTOMATION_ERROR', message: 'No enabled points with selectors configured.', sessionId: injectorSessionId }); injectorRunning = false; return; }
      for (let idx = 0; idx < automationPrompts.length && injectorRunning; idx++) {
        await waitWhileInjectorPaused();
        const prompt = automationPrompts[idx];
        const before = getAllMediaUrls();
        for (let p = 0; p < enabledPoints.length && injectorRunning; p++) {
          await waitWhileInjectorPaused();
           const delay = (enabledPoints[p].delay || 0) * 1000;
          if (delay > 0) { safeMsg({ type: 'AUTOMATION_STATUS', text: `Point ${p+1}: Waiting ${Math.ceil(delay/1000)}s`, sessionId: injectorSessionId }); await sleep(delay); }
          safeMsg({ type: 'AUTOMATION_STATUS', text: `Point ${p+1}: Executing ${enabledPoints[p].type}`, sessionId: injectorSessionId });
          await executeInjectorPoint(enabledPoints[p], enabledPoints[p].type === 'paste' ? prompt : null);
        }
        let downloadSuccess = true;
        if (config.autoDownload?.enabled && injectorRunning) {
          downloadSuccess = false;
          const req = config.autoDownload.count || 2, pattern = config.autoDownload.pattern || '', ext = config.autoDownload.extension || 'jpg', prefix = config.autoDownload.prefix || 'Mockup_Preview';
          const timeout = (config.autoDownload.monitoring ? Math.max(ext === 'mp4' ? 900 : 600, config.autoDownload.delay || 5) : (config.autoDownload.delay || 5)) * 1000;
          let media = [];
          if (config.autoDownload.monitoring) {
            const start = Date.now(); let scan = 0;
            while (injectorRunning && Date.now() - start < timeout) {
              scan++; media = findNewMediaContent(req, pattern, before);
              safeMsg({ type: 'DOWNLOAD_SCANNING', found: media.length, required: req, sessionId: injectorSessionId });
              if (media.length >= req) break;
              await sleep(1500);
            }
          } else {
            for (let rem = Math.ceil(timeout/1000); rem > 0 && injectorRunning; rem--) { safeMsg({ type: 'DOWNLOAD_COUNTDOWN', seconds: rem, sessionId: injectorSessionId }); await sleep(1000); }
            media = findNewMediaContent(req, pattern, before);
          }
          if (media.length) {
            const promptWords = prompt.split(/\s+/).slice(0, 5).join('_').replace(/[^a-zA-Z0-9_]/g, '');
            let startedCount = 0;
            for (let j = 0; j < media.length && injectorRunning; j++) {
              const promptIndex = (config.promptOffset || 0) + idx;
              const res = await requestDownload({ url: media[j].url, promptIndex, batchIndex: j, mediaType: media[j].type, extension: ext, prefix, promptWords });
              if (res.ok) {
                downloadedUrls.add(media[j].url);
                startedCount++;
                safeMsg({ type: 'AUTOMATION_STATUS', text: `Download started: ${res.filename || media[j].url}`, sessionId: injectorSessionId });
              } else {
                safeMsg({ type: 'AUTOMATION_ERROR', message: `Download failed: ${res.error || 'Unknown error'}`, promptIndex: (config.promptOffset || 0) + idx, sessionId: injectorSessionId });
              }
              await sleep(800);
            }
            downloadSuccess = startedCount > 0;
            if (downloadSuccess) safeMsg({ type: 'DOWNLOAD_DONE', count: startedCount, promptIndex: (config.promptOffset || 0) + idx, sessionId: injectorSessionId });
            else safeMsg({ type: 'AUTOMATION_ERROR', message: 'Detected media but no downloads could be started.', promptIndex: (config.promptOffset || 0) + idx, sessionId: injectorSessionId });
          } else {
            safeMsg({ type: 'AUTOMATION_ERROR', message: 'No new media matched the configured URL pattern.', promptIndex: (config.promptOffset || 0) + idx, sessionId: injectorSessionId });
          }
        }
        safeMsg({ type: 'AUTOMATION_PROGRESS', done: idx + 1, total: automationPrompts.length, sessionId: injectorSessionId });
      }
      injectorRunning = false; safeMsg({ type: 'AUTOMATION_FINISHED', sessionId: injectorSessionId }); injectorSessionId = null;
    }

    // -- Message listener ----------------------------------------------------
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
      if (msg.action === 'PING' || msg.type === 'PING') {
        sendResponse({ status: 'ok', success: true, ready: true });
        return true;
      }
      if (msg.type === 'START_PICKER') { startPicker(msg.pointIndex); sendResponse({ success: true, started: true }); return true; }
      if (msg.type === 'START_AUTOMATION') { runUniversalAutomation(msg.config, msg.prompts || [], msg.sessionId); sendResponse({ success: true }); return true; }
      if (msg.type === 'STOP_AUTOMATION') { injectorRunning = false; injectorPaused = false; sendResponse({ success: true }); return true; }
      if (msg.type === 'TOGGLE_PAUSE') { injectorPaused = !!msg.paused; sendResponse({ success: true }); return true; }
      if (msg.action === 'STOP') {
        isRunning = false;
        sendResponse({ status: 'stopped' });
        return true;
      }
      if (msg.action === 'ENSURE_FLOW_READY') {
        if (!isFlowPage) { sendResponse({ ok: false, error: 'Not a Flow page' }); return true; }
        ensureFlowProjectReady()
          .then(() => sendResponse({ ok: true }))
          .catch(e => sendResponse({ ok: false, error: e.message }));
        return true;
      }
      if (msg.action === 'INSERT_PROMPT') {
        if (!isFlowPage) { sendResponse({ status: 'failed', message: 'Not a Flow page' }); return true; }
        if (!isRunning) { sendResponse({ status: 'failed', message: 'Content script stopped' }); return true; }
        const payload = msg.payload;
        insertPrompt(payload.prompt, payload.promptIndex, payload.settings).then(result => {
          sendResponse(result);
        });
        return true;
      }
    });

    log('Content script loaded and ready');
  })();
}
