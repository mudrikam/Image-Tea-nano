// Generator Action (Create / Start Generation Button) for Auto Flow Batcher
(function () {
  window.AFB_Generator = {
    isButtonDisabled(button) {
      return !button || button.disabled ||
             button.getAttribute('aria-disabled') === 'true' ||
             button.getAttribute('data-disabled') === 'true';
    },

    getButtonText(button) {
      return (button?.textContent || '').replace(/\s+/g, ' ').trim();
    },

    findCreateButton() {
      const isVisible = window.AFB_DOM.isVisibleElement;
      const conf = window.__AFB_RUNTIME_CONFIG__?.selectors;
      if (!conf) return null;

      const exactQuerySelectors = conf.submitSelectors || [];

      for (const sel of exactQuerySelectors) {
        try {
          const el = document.querySelector(sel);
          if (el && isVisible(el) && !this.isButtonDisabled(el)) {
            return el;
          }
        } catch (_) {}
      }

      const buttons = Array.from(document.querySelectorAll('button')).filter(isVisible);
      if (!conf.createAction || !conf.createIcon) return null;

      const act1 = (conf.createAction || '').toLowerCase();
      const act2 = (conf.createAltAction || '').toLowerCase();
      const iconKey = (conf.createIcon || '').toLowerCase();

      // Strategy 2: Match for "Start generation" or "Create"
      const explicit = buttons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        const txt = (b.textContent || '').trim().toLowerCase();
        const isExcluded = aria.includes('agent') || txt === 'agent' || aria.includes('settings') || aria.includes('clear prompt');
        if (isExcluded) return false;
        return (act1 && (aria.includes(act1) || txt.includes(act1))) ||
               (act2 && (aria === act2 || txt === act2));
      });
      if (explicit && !this.isButtonDisabled(explicit)) return explicit;

      // Strategy 3: Button with arrow_forward icon in the bottom control bar
      const withArrow = buttons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        const txt = (b.textContent || '').trim().toLowerCase();
        const html = b.innerHTML || '';
        const isExcluded = aria.includes('agent') || txt === 'agent' || aria.includes('settings') || aria.includes('clear prompt');
        if (isExcluded) return false;
        return (iconKey && (txt.includes(iconKey) || html.includes(iconKey)));
      });
      if (withArrow && !this.isButtonDisabled(withArrow)) return withArrow;

      return null;
    },

    hasGenerationStarted(beforeTileIds, createBtn, editor, getCurrentTileIdsFn = () => new Set()) {
      const currentTileIds = getCurrentTileIdsFn();
      const newTileCount = [...currentTileIds].filter(id => !beforeTileIds.has(id)).length;
      if (newTileCount > 0) return true;
      if (createBtn && !document.body.contains(createBtn)) return true;
      if (createBtn && window.AFB_Generator.isButtonDisabled(createBtn)) return true;
      if (editor && !window.AFB_Generator.getButtonText(editor).trim()) return true;

      const busySelectors = window.__AFB_RUNTIME_CONFIG__?.selectors?.busyIndicators || [];
      if (!busySelectors.length) return false;
      const busy = document.querySelector(busySelectors.join(', '));
      return Boolean(busy && window.AFB_DOM.isVisibleElement(busy));
    },

    async clickCreateTarget(element, label = 'element', log = console.log) {
      if (!element) return;
      element.scrollIntoView?.({ behavior: 'instant', block: 'center', inline: 'center' });
      await new Promise(r => setTimeout(r, 60));

      const rect = element.getBoundingClientRect();
      const cx = Math.round(rect.left + rect.width / 2);
      const cy = Math.round(rect.top + rect.height / 2);

      // 1. Primary: Execute trusted OS-level hardware click via Chrome Debugger CDP
      try {
        const cdpRes = await new Promise(resolve => {
          chrome.runtime.sendMessage({
            type: 'TRIGGER_CDP_CLICK',
            x: cx,
            y: cy
          }, resp => {
            resolve(resp);
          });
        });
        if (cdpRes && cdpRes.ok) {
          log(`[AFB-Generator] Trusted CDP hardware click dispatched at (${cx}, ${cy}) ✓`);
          return;
        }
      } catch (err) {
        log(`[AFB-Generator] CDP dispatch notice: ${err.message}`);
      }

      // 2. Fallback: Isolated World DOM Click
      element.focus?.();
      try {
        element.click();
      } catch (e) {
        element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, composed: true, detail: 1 }));
      }

      const hostContainerTag = window.__AFB_RUNTIME_CONFIG__?.selectors?.hostContainer;
      if (hostContainerTag) {
        const parentHost = element.closest(hostContainerTag);
        if (parentHost && parentHost !== element) {
          try {
            parentHost.click();
          } catch (_) {}
        }
      }

      log(`[AFB-Generator] Native click dispatched to ${label}`);
    },

    submitViaEnter(editor, log = console.log) {
      if (!editor) return false;
      try {
        editor.focus();
        const eventParams = {
          key: 'Enter',
          code: 'Enter',
          keyCode: 13,
          which: 13,
          bubbles: true,
          cancelable: true,
          composed: true
        };
        editor.dispatchEvent(new KeyboardEvent('keydown', eventParams));
        editor.dispatchEvent(new KeyboardEvent('keypress', eventParams));
        editor.dispatchEvent(new KeyboardEvent('keyup', eventParams));
        log('[AFB-Generator] Dispatched Enter key event to ProseMirror editor');
        return true;
      } catch (e) {
        log(`[AFB-Generator] Error dispatching Enter key: ${e.message}`);
        return false;
      }
    },

    async clickCreateButton(beforeTileIds = new Set(), editor = null, isRunningFn = () => true, log = console.log, getCurrentTileIdsFn = () => new Set()) {
      const TIMEOUT_MS = 15000;
      const startTime = Date.now();
      let attempt = 0;

      const elapsed = () => Date.now() - startTime;
      const timedOut = () => elapsed() >= TIMEOUT_MS;

      while (!timedOut() && isRunningFn()) {
        attempt++;
        try {
          const createBtn = window.AFB_Generator.findCreateButton();

          if (!createBtn) {
            log(`[AFB-Generator] Create button not found (attempt ${attempt}, ${Math.round(elapsed()/1000)}s)`);
            await new Promise(r => setTimeout(r, 300));
            continue;
          }

          createBtn.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
          await new Promise(r => setTimeout(r, 100));

          // Dispatch ultra-fast trusted hardware click
          await window.AFB_Generator.clickCreateTarget(createBtn, 'Create button', log);
          await new Promise(r => setTimeout(r, 1000));
          if (!isRunningFn()) break;
          if (window.AFB_Generator.hasGenerationStarted(beforeTileIds, createBtn, editor, getCurrentTileIdsFn)) {
            log(`>>> Create VERIFIED via trusted click (attempt ${attempt})`);
            return true;
          }

          if (timedOut() || !isRunningFn()) break;
          await new Promise(r => setTimeout(r, 500));
        } catch (e) {
          log(`[AFB-Generator] Error clicking Create (attempt ${attempt}): ${e.message}`);
          await new Promise(r => setTimeout(r, 300));
        }
      }

      if (!isRunningFn()) {
        log('>>> Create aborted: stopped by user');
      } else {
        log(`ERROR: Create button click FAILED after ${attempt} attempts`);
      }
      return false;
    }
  };
})();
