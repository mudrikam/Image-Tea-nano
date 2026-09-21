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
      const buttons = Array.from(document.querySelectorAll('button')).filter(isVisible);
      const conf = window.__AFB_RUNTIME_CONFIG__?.selectors;
      if (!conf || !conf.createAction || !conf.createIcon) return null;

      const act1 = conf.createAction.toLowerCase();
      const act2 = (conf.createAltAction || '').toLowerCase();
      const iconKey = conf.createIcon.toLowerCase();

      // Strategy 1: Match for "Start generation" or "Create"
      const explicit = buttons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        const txt = (b.textContent || '').trim().toLowerCase();
        const isExcluded = aria.includes('agent') || txt === 'agent' || aria.includes('settings') || aria.includes('clear prompt');
        if (isExcluded) return false;
        return aria.includes(act1) || txt.includes(act1) ||
               (act2 && (aria === act2 || txt === act2)) || aria.includes('create generation');
      });
      if (explicit && !this.isButtonDisabled(explicit)) return explicit;

      // Strategy 2: Button with arrow_forward icon in the bottom control bar
      const withArrow = buttons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        const txt = (b.textContent || '').trim().toLowerCase();
        const html = b.innerHTML || '';
        const isExcluded = aria.includes('agent') || txt === 'agent' || aria.includes('settings') || aria.includes('clear prompt');
        if (isExcluded) return false;
        return txt.includes(iconKey) || html.includes(iconKey);
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
      const busy = document.querySelector('[aria-busy="true"], [role="progressbar"], [data-testid*="progress"], [class*="progress"], [class*="loading"]');
      return Boolean(busy && window.AFB_DOM.isVisibleElement(busy));
    },

    async clickCreateTarget(element, label = 'element', log = console.log) {
      if (!element) return;
      element.scrollIntoView?.({ behavior: 'instant', block: 'center', inline: 'center' });
      await new Promise(r => setTimeout(r, 40));

      const rect = element.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const eventInit = { bubbles: true, cancelable: true, composed: true, clientX: cx, clientY: cy, button: 0, buttons: 1 };
      const pointerInit = { ...eventInit, pointerId: 1, pointerType: 'mouse', isPrimary: true };

      element.focus?.();
      element.dispatchEvent(new PointerEvent('pointerdown', pointerInit));
      element.dispatchEvent(new MouseEvent('mousedown', eventInit));
      await new Promise(r => setTimeout(r, 60));
      element.dispatchEvent(new PointerEvent('pointerup', { ...pointerInit, buttons: 0 }));
      element.dispatchEvent(new MouseEvent('mouseup', { ...eventInit, buttons: 0 }));
      element.dispatchEvent(new MouseEvent('click', { ...eventInit, buttons: 0, detail: 1 }));
      log(`[AFB-Generator] Single click dispatched to ${label}`);
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
          await new Promise(r => setTimeout(r, 150));

          // Dispatch single precise click
          await window.AFB_Generator.clickCreateTarget(createBtn, 'Create button', log);
          await new Promise(r => setTimeout(r, 1000));
          if (!isRunningFn()) break;
          if (window.AFB_Generator.hasGenerationStarted(beforeTileIds, createBtn, editor, getCurrentTileIdsFn)) {
            log(`>>> Create VERIFIED via button click (attempt ${attempt})`);
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
