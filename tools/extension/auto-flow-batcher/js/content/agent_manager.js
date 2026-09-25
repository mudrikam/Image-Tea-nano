// Agent Manager for Auto Flow Batcher
// Strict Agent Guard & Panel Isolation Architecture
(function () {
  window.AFB_Agent = {
    /**
     * Uniquely locates the Agent toggle button in the Flow UI.
     * Searches by aria-label, button text, and icon indicators.
     * @returns {HTMLButtonElement|HTMLElement|null}
     */
    findAgentButton() {
      const isVisible = window.AFB_DOM ? window.AFB_DOM.isVisibleElement : (el => el && el.getBoundingClientRect().width > 0);

      // Strategy 0: Direct tag and specific class match (Google Flow Custom Element)
      const directChipBtn = document.querySelector('flow-agent-mode-toggle-chip button, button.agent-mode-chip');
      if (directChipBtn && isVisible(directChipBtn)) return directChipBtn;

      const buttons = Array.from(document.querySelectorAll('button, [role="button"], [role="switch"]')).filter(isVisible);

      // Strategy 1: Exact aria-label match (English & Indonesian)
      const exactAria = buttons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        return aria === 'agent' || aria === 'toggle agent' || aria === 'agent mode' ||
               aria === 'agen' || aria === 'alihkan agen' || aria === 'mode agen';
      });
      if (exactAria) return exactAria;

      // Strategy 2: Button text or child text matching "Agent" / "Agen"
      const exactText = buttons.find(b => {
        const text = (b.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
        if (text === 'agent' || text === 'agen') return true;
        const labelSpan = b.querySelector('.agent-mode-chip-label, .mdc-button__label, span, div');
        const spanText = (labelSpan?.textContent || '').trim().toLowerCase();
        return spanText === 'agent' || spanText === 'agen';
      });
      if (exactText) return exactText;

      // Strategy 3: Data attribute or ID/class match
      const attrMatch = buttons.find(b => {
        const testId = (b.getAttribute('data-testid') || '').toLowerCase();
        const id = (b.id || '').toLowerCase();
        const className = (typeof b.className === 'string' ? b.className : '').toLowerCase();
        const aria = (b.getAttribute('aria-label') || '').toLowerCase();
        const text = (b.textContent || '').toLowerCase();

        return (testId.includes('agent') || testId.includes('agen') ||
                id.includes('agent') || id.includes('agen') ||
                className.includes('agent') || className.includes('agen')) &&
               (text.includes('agent') || text.includes('agen') || aria.includes('agent') || aria.includes('agen'));
      });
      if (attrMatch) return attrMatch;

      // Strategy 4: Fallback partial text/aria match while excluding settings/dialogs
      return buttons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        const text = (b.textContent || '').trim().toLowerCase();
        const hasAgent = aria.includes('agent') || aria.includes('agen') || text.includes('agent') || text.includes('agen');
        const isExcluded = aria.includes('close') || aria.includes('tutup') ||
                           aria.includes('settings') || aria.includes('setelan') ||
                           aria.includes('create') || aria.includes('buat') ||
                           aria.includes('help') || aria.includes('bantuan') ||
                           aria.includes('petunjuk') || text.includes('petunjuk') ||
                           aria.includes('instruction') || text.includes('instruction');
        return hasAgent && !isExcluded;
      }) || null;
    },

    /**
     * Strictly checks if Agent mode is currently active (ON).
     * Returns true ONLY if aria-pressed="true", data-state="on", or data-state="checked".
     * If element is missing, or aria-pressed="false" / data-state="off", returns false.
     * @param {HTMLElement} [button] - Optional button element to check.
     * @returns {boolean}
     */
    isAgentOn(button = null) {
      const agentBtn = button || this.findAgentButton();
      if (!agentBtn) return false;

      const ariaPressed = agentBtn.getAttribute('aria-pressed');
      const dataState = agentBtn.getAttribute('data-state');
      const ariaChecked = agentBtn.getAttribute('aria-checked');
      const chipParent = agentBtn.closest('flow-agent-mode-toggle-chip');
      const isChipChecked = agentBtn.classList.contains('agent-mode-chip-checked') ||
                            (chipParent && chipParent.classList.contains('checked'));

      const hasActiveClass = agentBtn.classList.contains('active') ||
                             agentBtn.classList.contains('selected') ||
                             agentBtn.classList.contains('on') ||
                             isChipChecked;

      return ariaPressed === 'true' ||
             dataState === 'on' ||
             dataState === 'checked' ||
             ariaChecked === 'true' ||
             isChipChecked ||
             (hasActiveClass && ariaPressed !== 'false' && dataState !== 'off');
    },

    /**
     * Inspects Agent mode and Sidepanel status without making changes.
     * @returns {{agentMode: string, agentPanel: string, editor: string}}
     */
    checkAgentState() {
      const agentBtn = this.findAgentButton();
      const isAgentActive = this.isAgentOn(agentBtn);

      const closeBtn = this.findSidepanelCloseButton();
      const agentPanelVisible = Boolean(closeBtn);
      const editor = window.AFB_DOM ? window.AFB_DOM.findEditor() : null;

      return {
        agentMode: agentBtn ? (isAgentActive ? 'ON' : 'OFF') : 'not found',
        agentPanel: agentPanelVisible ? 'open' : 'not visible',
        editor: editor ? 'found' : 'not found'
      };
    },

    /**
     * Finds the Close button for the Agent sidepanel if open.
     * @returns {HTMLButtonElement|HTMLElement|null}
     */
    findSidepanelCloseButton() {
      const isVisible = window.AFB_DOM ? window.AFB_DOM.isVisibleElement : (el => el && el.getBoundingClientRect().width > 0);
      const buttons = Array.from(document.querySelectorAll('button, [role="button"]')).filter(isVisible);

      const iconSel = window.__AFB_RUNTIME_CONFIG__?.selectors?.iconElements || 'i, span';

      // Strategy 1: Close button within sidebar/sidepanel container
      const sidepanelContainer = document.querySelector('aside, [role="complementary"], .side-panel, .sidebar, [class*="sidepanel" i], [class*="sidebar" i], [data-testid*="sidepanel" i]');
      if (sidepanelContainer) {
        const sideCloseBtn = Array.from(sidepanelContainer.querySelectorAll('button, [role="button"]')).find(b => {
          if (!isVisible(b)) return false;
          const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
          const text = (b.textContent || '').trim().toLowerCase();
          const icon = (b.querySelector(iconSel)?.textContent || '').trim().toLowerCase();
          return aria === 'close' || aria.includes('close side') || aria.includes('close panel') || text === 'close' || icon === 'close' ||
                 aria === 'tutup' || aria.includes('tutup') || text === 'tutup' || icon === 'tutup';
        });
        if (sideCloseBtn) return sideCloseBtn;
      }

      // Strategy 2: Global visible button with explicit Close aria-label or text
      return buttons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        const text = (b.textContent || '').trim().toLowerCase();
        const icon = (b.querySelector(iconSel)?.textContent || '').trim().toLowerCase();
        return aria === 'close' || aria === 'close sidebar' || aria === 'close sidepanel' || aria === 'close panel' ||
               text === 'close' || icon === 'close' ||
               aria === 'tutup' || aria.includes('tutup') || text === 'tutup' || icon === 'tutup';
      }) || null;
    },

    /**
     * If the Agent sidepanel is open (Close button visible), clicks Close to restore bottom panel.
     * @param {Function} log
     * @returns {Promise<boolean>}
     */
    async closeSidepanelIfOpen(log = console.log) {
      const closeBtn = this.findSidepanelCloseButton();
      if (closeBtn) {
        log('[AFB-Agent] Sidepanel is open → clicking Close button to restore bottom panel');
        window.AFB_DOM.dispatchMouseSequence(closeBtn, 'Sidepanel Close button');
        await new Promise(r => setTimeout(r, 600));
        return true;
      }

      log('[AFB-Agent] Sidepanel is already bottom panel ✓');
      return false;
    },

    /**
     * Strictly verifies Agent state.
     * IF Agent is ON (aria-pressed="true" / data-state="on"), clicks it ONCE to disable it.
     * IF Agent is already OFF (aria-pressed="false" / data-state="off" / false), DO NOT CLICK IT under any circumstances.
     * @param {Function} log
     * @returns {Promise<boolean>}
     */
    async disableAgentMode(log = console.log) {
      const agentBtn = this.findAgentButton();
      if (!agentBtn) {
        log('[AFB-Agent] Agent button not found on page (assuming OFF) ✓');
        return true;
      }

      const isCurrentOn = this.isAgentOn(agentBtn);
      log(`[AFB-Agent] Agent button status: ${isCurrentOn ? 'ON (active)' : 'OFF (inactive)'}`);

      // STRICT SAFETY GUARD: If Agent is already OFF, DO NOT CLICK under any circumstances
      if (!isCurrentOn) {
        log('[AFB-Agent] Agent is already OFF — skipping toggle click ✓');
        return true;
      }

      log('[AFB-Agent] Agent is ON → clicking Agent button to turn OFF');
      window.AFB_DOM.dispatchMouseSequence(agentBtn, 'Agent button toggle');
      await new Promise(r => setTimeout(r, 600));

      const afterBtn = this.findAgentButton();
      const isStillOn = afterBtn ? this.isAgentOn(afterBtn) : false;
      log(`[AFB-Agent] Agent state after click: ${isStillOn ? 'STILL ON ⚠' : 'OFF ✓'}`);
      return !isStillOn;
    },

    /**
     * Prepares and normalizes the page: closes sidepanel, ensures Agent is OFF, and validates editor.
     * @param {Function} log
     * @returns {Promise<boolean>}
     */
    async normalizeAndPreparePage(log = console.log) {
      await this.closeSidepanelIfOpen(log);
      await this.disableAgentMode(log);

      let editor = null;
      for (let i = 0; i < 20; i++) {
        editor = window.AFB_DOM ? window.AFB_DOM.findEditor() : null;
        if (editor && window.AFB_DOM.isVisibleElement(editor)) break;
        await new Promise(r => setTimeout(r, 150));
      }

      if (editor && window.AFB_DOM.isVisibleElement(editor)) {
        log('[AFB-Prepare] Prompt input editor: found ✓');
        return true;
      } else {
        log('[AFB-Prepare] Prompt input editor: NOT FOUND ⚠');
        return false;
      }
    }
  };
})();
