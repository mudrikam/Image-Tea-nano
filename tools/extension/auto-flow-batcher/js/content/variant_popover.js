// Variant / Settings Popover Manager for Google Flow (Modern DOM)
// Robust Trigger Reference Locking, Mounting Polling & Strict Fail-Fast Architecture
(function () {
  let _lastAppliedSettings = null;
  let _activeTriggerElement = null;

  function isVisible(el) {
    if (window.AFB_DOM && typeof window.AFB_DOM.isVisibleElement === 'function') {
      return window.AFB_DOM.isVisibleElement(el);
    }
    if (!el || !(el instanceof HTMLElement)) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 &&
           style.display !== 'none' &&
           style.visibility !== 'hidden' &&
           style.opacity !== '0' &&
           style.pointerEvents !== 'none';
  }

  function normalizeText(text) {
    if (!text) return '';
    return text
      .replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu, '') // strip emojis (🍌, etc.)
      .replace(/[·•]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  // Material Symbols ligature and exact text mappings for aspect ratios
  function getRatioOrder() {
    return window.__AFB_RUNTIME_CONFIG__?.popover?.ratioOrder || [];
  }

  function getRatioIconMap() {
    return window.__AFB_RUNTIME_CONFIG__?.popover?.ratioIconMap || {};
  }

  /**
   * Helper: Poll for a truthy condition with timeout
   */
  async function waitForCondition(conditionFn, timeoutMs = 4000, intervalMs = 100) {
    const startTime = Date.now();
    while (Date.now() - startTime < timeoutMs) {
      const res = conditionFn();
      if (res) return res;
      await new Promise(r => setTimeout(r, intervalMs));
    }
    return conditionFn();
  }

  /**
   * Strict identification of the Agent button to prevent accidental clicks
   */
  function isAgentButton(el) {
    if (!el || !(el instanceof HTMLElement)) return false;
    const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
    const txt = (el.textContent || '').trim().toLowerCase();
    const id = (el.id || '').toLowerCase();
    const className = (el.className || '').toString().toLowerCase();
    return aria.includes('agent') || txt === 'agent' || id.includes('agent') || className.includes('agent');
  }

  /**
   * Identifies excluded non-settings buttons in control bars
   */
  function isExcludedControl(b) {
    if (isAgentButton(b)) return true;
    const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
    const txt = (b.textContent || '').trim().toLowerCase();
    const title = (b.getAttribute('title') || '').trim().toLowerCase();

    const excludedKeywords = window.__AFB_RUNTIME_CONFIG__?.popover?.excludedControls || [];
    return excludedKeywords.some(kw => aria.includes(kw) || txt === kw || title.includes(kw));
  }

  window.AFB_Variant = {
    resetSettingsCache() {
      _lastAppliedSettings = null;
      _activeTriggerElement = null;
    },

    /**
     * Finds the Settings Trigger button in the bottom control bar.
     * Strict exclusion: NEVER targets Agent or execution buttons.
     */
    findSettingsTrigger() {
      const buttons = Array.from(document.querySelectorAll('button')).filter(isVisible);
      const conf = window.__AFB_RUNTIME_CONFIG__?.popover;
      if (!conf) return null;

      const ariaKeys = conf.triggerAriaKeys || [];
      const textKeys = conf.triggerTextKeys || [];

      // Strategy 1: Explicit aria-label matching
      const explicit = buttons.find(b => {
        if (isExcludedControl(b)) return false;
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        return ariaKeys.includes(aria);
      });
      if (explicit) return explicit;

      // Strategy 2: Button displaying active model/ratio/batch icons or text
      return buttons.find(b => {
        if (isExcludedControl(b)) return false;
        const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
        const txt = (b.textContent || '').trim().toLowerCase();

        return textKeys.some(k => txt.includes(k)) || /\bx[1-4]\b/.test(txt) || aria.includes('settings');
      }) || null;
    },

    /**
     * Finds the Model selector dropdown trigger inside the open popover.
     */
    findModelTrigger() {
      const allButtons = Array.from(document.querySelectorAll('button')).filter(isVisible);
      const conf = window.__AFB_RUNTIME_CONFIG__?.popover;
      if (!conf) return null;

      const ariaKeys = conf.modelTriggerAriaKeys || [];
      const textKeys = conf.modelTriggerTextKeys || [];

      return allButtons.find(b => {
        if (b === _activeTriggerElement) return false;
        if (isExcludedControl(b)) return false;
        const aria = (b.getAttribute('aria-label') || '').toLowerCase();
        const txt = (b.textContent || '').toLowerCase();
        return ariaKeys.some(k => aria.includes(k)) || textKeys.some(k => txt.includes(k));
      }) || null;
    },

    /**
     * Checks whether popover content is fully mounted in the DOM.
     * Polls for radiogroups and radio elements.
     */
    isPopoverMounted() {
      const radios = Array.from(document.querySelectorAll('[role="radiogroup"] [role="radio"], [role="radio"], [role="tab"], [role="radiogroup"] button')).filter(isVisible);
      const radiogroups = Array.from(document.querySelectorAll('[role="radiogroup"]')).filter(isVisible);
      const modelTrigger = this.findModelTrigger();
      const popoverDialogs = Array.from(document.querySelectorAll('[role="dialog"], .variant-popover, flow-variant-popover')).filter(isVisible);

      return (radios.length >= 2) || (radiogroups.length > 0 && radios.length > 0) || (popoverDialogs.length > 0 && radios.length > 0) || (modelTrigger !== null && radios.length > 0);
    },

    /**
     * Checks whether the popover dialog/radiogroup container is currently open in DOM.
     */
    isPopoverOpen() {
      return this.isPopoverMounted();
    },

    /**
     * Polls until the popover content is fully mounted in the DOM with a timeout.
     */
    async waitForPopoverMounted(timeoutMs = 4000) {
      const startTime = Date.now();
      while (Date.now() - startTime < timeoutMs) {
        if (this.isPopoverMounted()) {
          await new Promise(r => setTimeout(r, 60));
          return true;
        }
        await new Promise(r => setTimeout(r, 100));
      }
      return this.isPopoverMounted();
    },

    /**
     * Dispatches a clean, realistic mouse event sequence on an element.
     */
    async clickElementSafely(el, label = 'element') {
      if (!el || !(el instanceof HTMLElement)) {
        throw new Error(`[AFB-Settings] Cannot click invalid element: ${label}`);
      }
      el.scrollIntoView({ behavior: 'instant', block: 'center' });
      el.focus?.();

      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;

      const eventInit = { bubbles: true, cancelable: true, composed: true, clientX: cx, clientY: cy, button: 0 };
      const pointerInit = { ...eventInit, pointerId: 1, pointerType: 'mouse', isPrimary: true };

      el.dispatchEvent(new PointerEvent('pointerover', pointerInit));
      el.dispatchEvent(new PointerEvent('pointerenter', { ...pointerInit, bubbles: false }));
      el.dispatchEvent(new PointerEvent('pointerdown', pointerInit));
      el.dispatchEvent(new MouseEvent('mousedown', eventInit));
      await new Promise(r => setTimeout(r, 40));
      el.dispatchEvent(new PointerEvent('pointerup', { ...pointerInit, buttons: 0 }));
      el.dispatchEvent(new MouseEvent('mouseup', { ...eventInit, buttons: 0 }));
      el.dispatchEvent(new MouseEvent('click', { ...eventInit, buttons: 0, detail: 1 }));
    },

    /**
     * Checks if an option element is checked or selected.
     */
    isElementChecked(el) {
      if (!el) return false;
      return el.getAttribute('aria-checked') === 'true' ||
             el.getAttribute('aria-selected') === 'true' ||
             el.getAttribute('aria-pressed') === 'true' ||
             el.getAttribute('data-state') === 'checked' ||
             el.getAttribute('data-state') === 'on' ||
             el.getAttribute('data-state') === 'active' ||
             el.classList.contains('active') ||
             el.classList.contains('selected') ||
             el.classList.contains('checked') ||
             el.classList.contains('mdc-radio--checked') ||
             el.classList.contains('mat-mdc-radio-checked') ||
             Boolean(el.checked) ||
             Boolean(el.querySelector?.('input[type="radio"]:checked')) ||
             Boolean(el.querySelector?.('[aria-checked="true"], .mdc-radio--checked'));
    },

    /**
     * Opens the Settings Popover, locks the trigger reference, and verifies content mounting.
     */
    async openPopover(log = console.log) {
      if (this.isPopoverOpen()) {
        log('[AFB-Settings] Popover is already OPEN and mounted ✓');
        if (!_activeTriggerElement || !_activeTriggerElement.isConnected) {
          _activeTriggerElement = this.findSettingsTrigger();
        }
        return true;
      }

      const MAX_RETRIES = 4;
      const RETRY_DELAY = 300;

      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        const trigger = this.findSettingsTrigger();
        if (!trigger) {
          log(`[AFB-Settings] Settings trigger button not found (attempt ${attempt}/${MAX_RETRIES})`);
          await new Promise(r => setTimeout(r, RETRY_DELAY));
          continue;
        }

        if (isAgentButton(trigger)) {
          throw new Error('[AFB-Settings] CRITICAL GUARD: Target trigger is the Agent button! Execution halted.');
        }

        // Store exact trigger element reference
        _activeTriggerElement = trigger;
        const triggerSummary = (trigger.textContent || trigger.getAttribute('aria-label') || '').trim().substring(0, 40);
        log(`[AFB-Settings] Trigger locked: "${triggerSummary}" (attempt ${attempt}/${MAX_RETRIES})`);

        await this.clickElementSafely(_activeTriggerElement, 'Settings trigger');

        log('[AFB-Settings] Waiting for popover content to mount in DOM...');
        const mounted = await this.waitForPopoverMounted(3500);

        if (mounted) {
          log(`[AFB-Settings] Popover confirmed OPEN and MOUNTED ✓ (attempt ${attempt})`);
          return true;
        }

        log(`[AFB-Settings] Popover content did not mount in time (attempt ${attempt})`);
        await new Promise(r => setTimeout(r, RETRY_DELAY));
      }

      throw new Error('[AFB-Settings] Failed to open Settings popover: content not mounted in DOM after retries');
    },

    /**
     * Reads current active state from the open popover.
     */
    readCurrentState() {
      const radios = Array.from(document.querySelectorAll('[role="radio"], [role="tab"], [role="radiogroup"] button')).filter(isVisible);

      const state = {
        type: null,
        modifier: null,
        ratio: null,
        model: null,
        resolution: null,
        duration: null,
        batch: null
      };

      // 1. Read Type (Image vs Video)
      for (const r of radios) {
        const txt = (r.textContent || '').trim().toLowerCase();
        const aria = (r.getAttribute('aria-label') || '').trim().toLowerCase();
        if (txt.includes('image') || aria.includes('image')) {
          if (this.isElementChecked(r)) state.type = 'image';
        } else if (txt.includes('video') || aria.includes('video')) {
          if (this.isElementChecked(r)) state.type = 'video';
        }
      }

      // 2. Read Ratio (Prioritize exact ratio token matching over shared icons)
      const ratioCandidates = ['16:9', '4:3', '1:1', '3:4', '9:16'];
      for (const r of radios) {
        const txt = (r.textContent || '').trim();
        const aria = (r.getAttribute('aria-label') || '').trim();
        if (/^x?[1-4]$/i.test(txt) || /^x?[1-4]$/i.test(aria)) continue;

        // Exact match first
        for (const candidate of ratioCandidates) {
          if ((txt === candidate || aria === candidate || txt.includes(candidate) || aria.includes(candidate)) && this.isElementChecked(r)) {
            state.ratio = candidate;
            break;
          }
        }
        if (state.ratio) break;
      }

      // 3. Read Model
      const modelTrigger = this.findModelTrigger();
      if (modelTrigger) {
        state.model = (modelTrigger.textContent || '').trim();
      }

      // 4. Read Batch (x1, x2, x3, x4)
      for (const r of radios) {
        const txt = (r.textContent || '').trim().toLowerCase();
        const aria = (r.getAttribute('aria-label') || '').trim().toLowerCase();
        const match = txt.match(/\bx?([1-4])\b/) || aria.match(/\bx?([1-4])\b/);
        if (match && this.isElementChecked(r)) {
          if (!txt.includes(':') && !aria.includes(':')) {
            state.batch = match[1];
          }
        }
      }

      // 5. Read Video Resolution & Duration
      for (const r of radios) {
        const txt = (r.textContent || '').toLowerCase();
        const aria = (r.getAttribute('aria-label') || '').toLowerCase();
        if ((txt.includes('360p') || aria.includes('360p')) && this.isElementChecked(r)) state.resolution = '360p';
        if ((txt.includes('720p') || aria.includes('720p')) && this.isElementChecked(r)) state.resolution = '720p';
        if ((txt === '4s' || aria === '4s') && this.isElementChecked(r)) state.duration = '4s';
        if ((txt === '6s' || aria === '6s') && this.isElementChecked(r)) state.duration = '6s';
        if ((txt === '8s' || aria === '8s') && this.isElementChecked(r)) state.duration = '8s';
        if ((txt === '10s' || aria === '10s') && this.isElementChecked(r)) state.duration = '10s';
      }

      return state;
    },

    /**
     * Selects Mode Type (Image vs Video) with strict verification.
     */
    async selectType(targetType, log = console.log) {
      if (!targetType) return true;
      const targetStr = targetType.toLowerCase();

      let currentState = this.readCurrentState();
      if (currentState.type === targetStr) {
        log(`[AFB-Settings] Type already "${targetType}" ✓`);
        return true;
      }

      log(`[AFB-Settings] Type diff: current="${currentState.type || 'unknown'}" ➔ target="${targetType}"`);

      const elements = Array.from(document.querySelectorAll('[role="radiogroup"] [role="radio"], [role="radio"], [role="tab"], [role="radiogroup"] button, button')).filter(isVisible);
      const targetEl = elements.find(el => {
        const txt = (el.textContent || '').trim().toLowerCase();
        const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
        // Ignore video duration / resolution / batch
        if (txt.includes('360p') || txt.includes('720p') || txt.includes('ingredients') || txt.includes('frames') || /^x?[1-4]$/.test(txt)) return false;
        
        if (targetStr === 'image') {
          return txt === 'image' || aria === 'image' || txt.includes('image') || aria.includes('image') || txt.includes('photo');
        } else if (targetStr === 'video') {
          return txt === 'video' || aria === 'video' || txt.includes('video') || aria.includes('video') || txt.includes('videocam');
        }
        return false;
      });

      if (!targetEl) {
        throw new Error(`[AFB-Settings] Type option "${targetType}" not found in popover`);
      }

      await this.clickElementSafely(targetEl, `Type ${targetType}`);

      const verified = await waitForCondition(() => {
        return this.isElementChecked(targetEl) || this.readCurrentState().type === targetStr;
      }, 2500);

      if (!verified) {
        throw new Error(`[AFB-Settings] Failed to verify Type switch to "${targetType}"`);
      }

      currentState = this.readCurrentState();
      log(`[AFB-Settings] Type switched to "${currentState.type}" VERIFIED ✓`);
      return true;
    },

    /**
     * Selects Model Family from dropdown with full menu interaction & strict verification.
     */
    async selectModel(targetModel, log = console.log) {
      if (!targetModel) return true;
      const normTarget = normalizeText(targetModel);

      const modelTrigger = this.findModelTrigger();
      if (!modelTrigger) {
        throw new Error('[AFB-Settings] Model dropdown trigger button not found in popover');
      }

      const currentRawModel = (modelTrigger.textContent || '').trim();
      const normCurrent = normalizeText(currentRawModel);

      if (normCurrent && (normCurrent === normTarget || normCurrent.includes(normTarget) || normTarget.includes(normCurrent))) {
        log(`[AFB-Settings] Model already "${currentRawModel}" ✓`);
        return true;
      }

      log(`[AFB-Settings] Model diff: current="${currentRawModel}" ➔ target="${targetModel}"`);
      log('[AFB-Settings] 1. Opening model dropdown menu...');
      await this.clickElementSafely(modelTrigger, 'Model dropdown trigger');
      await new Promise(r => setTimeout(r, 400));

      // Wait for [role="menu"] or [role="menuitem"] to mount in DOM
      const menuItems = await waitForCondition(() => {
        const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], div[role="menu"] button, [role="menu"] [role="button"], flow-menu-item')).filter(isVisible);
        return items.length > 0 ? items : null;
      }, 3500);

      if (!menuItems || menuItems.length === 0) {
        throw new Error('[AFB-Settings] Model dropdown menu [role="menu"] failed to open in DOM');
      }

      log(`[AFB-Settings] Found ${menuItems.length} menuitems in dropdown: [${menuItems.map(m => (m.textContent || '').trim().replace(/\s+/g, ' ')).join(' | ')}]`);

      // Filter menu items to interactive leaf targets
      const leafMenuItems = menuItems.filter(el => {
        const isClickableRole = el.getAttribute('role') === 'menuitem' || el.tagName === 'BUTTON' || el.getAttribute('role') === 'option';
        const hasClickableChild = el.querySelector('button, [role="menuitem"], .mdc-list-item__primary-text');
        return isClickableRole || !hasClickableChild;
      });

      const candidateList = leafMenuItems.length > 0 ? leafMenuItems : menuItems;

      const matchItem = candidateList.find(item => {
        const txt = normalizeText(item.textContent || '');
        const aria = normalizeText(item.getAttribute('aria-label') || '');
        const combined = `${txt} ${aria}`;

        if (normTarget.includes('lite')) {
          return combined.includes('lite');
        }
        if (normTarget.includes('pro')) {
          return combined.includes('pro');
        }
        if (normTarget.includes('fast')) {
          return combined.includes('fast');
        }
        if (normTarget.includes('quality')) {
          return combined.includes('quality');
        }
        if (normTarget.includes('omni') || normTarget.includes('flash')) {
          return combined.includes('omni') || combined.includes('flash');
        }
        if (normTarget.includes('banana 2') || normTarget.includes('nano 2') || normTarget === 'nano banana 2') {
          return combined.includes('2') && !combined.includes('lite') && !combined.includes('pro');
        }

        return txt === normTarget || aria === normTarget || txt.startsWith(normTarget);
      });

      if (!matchItem) {
        const available = menuItems.map(m => (m.textContent || '').trim()).filter(Boolean).slice(0, 10).join(', ');
        throw new Error(`[AFB-Settings] Model option "${targetModel}" not found in dropdown menu. Available: [${available}]`);
      }

      // Find the deepest clickable button/span inside matchItem if available
      const clickableTarget = matchItem.closest('[role="menuitem"], button') || matchItem.querySelector('[role="menuitem"], button, .mdc-list-item__primary-text') || matchItem;
      const itemLabel = (clickableTarget.textContent || matchItem.textContent || '').trim();

      log(`[AFB-Settings] 2. Selecting Model menuitem: "${itemLabel}"...`);
      await this.clickElementSafely(clickableTarget, `Model ${itemLabel}`);
      await new Promise(r => setTimeout(r, 600));

      // Wait for dropdown to close and verify trigger label updated
      log('[AFB-Settings] 3. Verifying Model selection in DOM...');
      const verified = await waitForCondition(() => {
        const currTrigger = this.findModelTrigger();
        if (!currTrigger) return false;
        const txt = normalizeText(currTrigger.textContent || '');
        return txt.includes(normTarget) || normTarget.includes(txt);
      }, 3000);

      if (!verified) {
        const currentAfter = this.findModelTrigger()?.textContent?.trim() || 'unknown';
        throw new Error(`[AFB-Settings] Failed to verify Model update to "${targetModel}" (current: "${currentAfter}")`);
      }

      log(`[AFB-Settings] Model updated to "${itemLabel}" VERIFIED ✓`);
      return true;
    },

    /**
     * Selects Aspect Ratio with ligature/numeric token matching & strict verification.
     */
    async selectRatio(targetRatio, log = console.log) {
      if (!targetRatio) return true;
      const currentState = this.readCurrentState();
      if (currentState.ratio === targetRatio) {
        log(`[AFB-Settings] Ratio already "${targetRatio}" ✓`);
        return true;
      }

      log(`[AFB-Settings] Ratio diff: current="${currentState.ratio || 'unknown'}" ➔ target="${targetRatio}"`);

      const elements = Array.from(document.querySelectorAll('[role="radiogroup"] [role="radio"], [role="radio"], [role="tab"], [role="radiogroup"] button')).filter(isVisible);

      // Strategy 1: Exact text / aria match (e.g. "4:3", "9:16")
      let targetEl = elements.find(el => {
        const txt = (el.textContent || '').trim().toLowerCase();
        const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
        if (/^x?[1-4]$/.test(txt) || /^x?[1-4]$/.test(aria)) return false;
        return txt === targetRatio || aria === targetRatio || txt.includes(targetRatio) || aria.includes(targetRatio);
      });

      // Strategy 2: Ligature mapping fallback
      if (!targetEl) {
        const iconMap = getRatioIconMap();
        const matchTokens = iconMap[targetRatio] || [];
        if (matchTokens.length > 0) {
          targetEl = elements.find(el => {
            const txt = (el.textContent || '').trim().toLowerCase();
            const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
            if (/^x?[1-4]$/.test(txt) || /^x?[1-4]$/.test(aria)) return false;
            return matchTokens.some(tok => txt.includes(tok.toLowerCase()) || aria.includes(tok.toLowerCase()));
          });
        }
      }

      if (!targetEl) {
        throw new Error(`[AFB-Settings] Aspect ratio option "${targetRatio}" not found in popover`);
      }

      await this.clickElementSafely(targetEl, `Ratio ${targetRatio}`);

      const verified = await waitForCondition(() => {
        return this.isElementChecked(targetEl) || this.readCurrentState().ratio === targetRatio;
      }, 2500);

      if (!verified) {
        throw new Error(`[AFB-Settings] Failed to verify Aspect Ratio switch to "${targetRatio}"`);
      }

      log(`[AFB-Settings] Ratio selected: "${targetRatio}" VERIFIED ✓`);
      return true;
    },

    /**
     * Ensures Video Modifier is set to "Ingredients" (strict requirement).
     */
    async ensureVideoIngredientsActive(log = console.log) {
      const radios = Array.from(document.querySelectorAll('[role="radiogroup"] [role="radio"], [role="radio"], [role="tab"], [role="radiogroup"] button')).filter(isVisible);

      const ingredientsRadio = radios.find(el => {
        const txt = (el.textContent || '').trim().toLowerCase();
        const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
        return txt === 'ingredients' || aria === 'ingredients' || txt.includes('ingredients') || aria.includes('ingredients');
      });

      if (!ingredientsRadio) {
        throw new Error('[AFB-Settings] Sub-mode option "Ingredients" not found in Video popover');
      }

      if (this.isElementChecked(ingredientsRadio)) {
        log('[AFB-Settings] Sub-mode: "Ingredients" is ALREADY ACTIVE ✓');
        return true;
      }

      log('[AFB-Settings] Switching Sub-mode to "Ingredients"...');
      await this.clickElementSafely(ingredientsRadio, 'Modifier Ingredients');

      const verified = await waitForCondition(() => this.isElementChecked(ingredientsRadio), 2500);
      if (!verified) {
        throw new Error('[AFB-Settings] Failed to verify Sub-mode switch to "Ingredients"');
      }

      log('[AFB-Settings] Sub-mode switched to "Ingredients" VERIFIED ✓');
      return true;
    },

    /**
     * Selects Video Specific Controls (Ingredients, Duration, Resolution) with strict verification.
     * Note: Duration and Resolution are ONLY applicable to Omni models in Google Flow.
     */
    async selectVideoControls(settings, log = console.log) {
      if (settings.type !== 'video') return true;

      // 1. Ensure Ingredients is active
      await this.ensureVideoIngredientsActive(log);

      // Check if current active model is Omni
      const currentModel = (this.readCurrentState().model || settings.model || '').toLowerCase();
      const isOmniModel = currentModel.includes('omni') || currentModel.includes('flash');

      // If model is NOT Omni (e.g. Veo models), Google Flow does not render Duration/Resolution
      if (!isOmniModel) {
        log(`[AFB-Settings] Model is "${currentModel}" (non-Omni) — skipping Duration & Resolution controls ✓`);
        return true;
      }

      const radios = Array.from(document.querySelectorAll('[role="radiogroup"] [role="radio"], [role="radio"], [role="radiogroup"] button')).filter(isVisible);

      // 2. Select Resolution (720p / 360p) for Omni
      if (settings.videoResolution) {
        const resStr = settings.videoResolution.toLowerCase();
        const resEl = radios.find(el => {
          const txt = (el.textContent || '').toLowerCase();
          const aria = (el.getAttribute('aria-label') || '').toLowerCase();
          return txt.includes(resStr) || aria.includes(resStr);
        });
        if (!resEl) {
          throw new Error(`[AFB-Settings] Video resolution option "${settings.videoResolution}" not found in popover`);
        }
        if (!this.isElementChecked(resEl)) {
          log(`[AFB-Settings] Selecting Video Resolution: ${settings.videoResolution}`);
          await this.clickElementSafely(resEl, `Resolution ${settings.videoResolution}`);
          const resVerified = await waitForCondition(() => this.isElementChecked(resEl), 2000);
          if (!resVerified) {
            throw new Error(`[AFB-Settings] Failed to verify Video resolution switch to "${settings.videoResolution}"`);
          }
        }
      }

      // 3. Select Duration (4s, 6s, 8s, 10s) for Omni
      if (settings.videoDuration) {
        const durStr = settings.videoDuration.toLowerCase();
        const durEl = radios.find(el => {
          const txt = (el.textContent || '').trim().toLowerCase();
          const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
          return txt === durStr || aria === durStr || txt.startsWith(durStr);
        });
        if (!durEl) {
          throw new Error(`[AFB-Settings] Video duration option "${settings.videoDuration}" not found in popover`);
        }
        if (!this.isElementChecked(durEl)) {
          log(`[AFB-Settings] Selecting Video Duration: ${settings.videoDuration}`);
          await this.clickElementSafely(durEl, `Duration ${settings.videoDuration}`);
          const durVerified = await waitForCondition(() => this.isElementChecked(durEl), 2000);
          if (!durVerified) {
            throw new Error(`[AFB-Settings] Failed to verify Video duration switch to "${settings.videoDuration}"`);
          }
        }
      }
      return true;
    },

    /**
     * Selects Batch Count (x1, x2, x3, x4) with strict verification.
     */
    async selectBatch(targetBatch, log = console.log) {
      if (!targetBatch) return true;
      const batchNum = String(targetBatch).replace(/\D/g, '') || '1';
      const batchStr = `x${batchNum}`;

      const currentState = this.readCurrentState();
      if (currentState.batch === batchNum) {
        log(`[AFB-Settings] Batch already "${batchStr}" ✓`);
        return true;
      }

      log(`[AFB-Settings] Batch diff: current="x${currentState.batch || '?'}" ➔ target="${batchStr}"`);

      const radios = Array.from(document.querySelectorAll('[role="radiogroup"] [role="radio"], [role="radio"], [role="radiogroup"] button')).filter(isVisible);
      const targetEl = radios.find(el => {
        const txt = (el.textContent || '').trim().toLowerCase();
        const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
        if (txt.includes(':') || aria.includes(':')) return false;
        return txt === batchStr || aria === batchStr || txt === batchNum || aria === batchNum ||
               txt === `x ${batchNum}` || aria === `x ${batchNum}`;
      });

      if (!targetEl) {
        throw new Error(`[AFB-Settings] Batch option "${batchStr}" not found in popover`);
      }

      await this.clickElementSafely(targetEl, `Batch ${batchStr}`);

      const verified = await waitForCondition(() => {
        return this.isElementChecked(targetEl) || this.readCurrentState().batch === batchNum;
      }, 2500);

      if (!verified) {
        throw new Error(`[AFB-Settings] Failed to verify Batch switch to "${batchStr}"`);
      }

      log(`[AFB-Settings] Batch selected: "${batchStr}" VERIFIED ✓`);
      return true;
    },

    /**
     * Closes the Settings Popover safely by clicking ONLY the stored trigger reference.
     * Fallback: neutral canvas backdrop click (coordinates 100, 100).
     * Strict rule: NEVER touch Agent, NEVER dispatch global Escape.
     */
    async closePopover(log = console.log) {
      if (!this.isPopoverOpen()) {
        log('[AFB-Settings] Popover is already closed ✓');
        _activeTriggerElement = null;
        return true;
      }

      log('[AFB-Settings] Closing Settings popover...');

      // Step 1: Click ONLY the stored trigger reference (ensuring it is NOT Agent)
      if (_activeTriggerElement && _activeTriggerElement.isConnected) {
        if (isAgentButton(_activeTriggerElement)) {
          log('[AFB-Settings] WARN: Stored trigger is identified as Agent button! Refusing to click trigger on close.');
        } else {
          log('[AFB-Settings] Clicking stored Settings trigger to close');
          await this.clickElementSafely(_activeTriggerElement, 'Stored Settings trigger close');

          const closed = await waitForCondition(() => !this.isPopoverOpen(), 1500);
          if (closed) {
            log('[AFB-Settings] Popover closed successfully via trigger VERIFIED ✓');
            _activeTriggerElement = null;
            return true;
          }
        }
      }

      // Step 2: Fallback to clicking canvas backdrop (coordinates 100, 100)
      log('[AFB-Settings] Popover still open after trigger click, clicking neutral canvas backdrop at (100, 100)');
      const backdropTarget = document.querySelector('flow-canvas, main, .canvas-container') || document.body;

      const clickEventInit = { bubbles: true, cancelable: true, composed: true, clientX: 100, clientY: 100, button: 0 };
      backdropTarget.dispatchEvent(new PointerEvent('pointerdown', { ...clickEventInit, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
      backdropTarget.dispatchEvent(new MouseEvent('mousedown', clickEventInit));
      await new Promise(r => setTimeout(r, 40));
      backdropTarget.dispatchEvent(new PointerEvent('pointerup', { ...clickEventInit, pointerId: 1, pointerType: 'mouse', buttons: 0 }));
      backdropTarget.dispatchEvent(new MouseEvent('mouseup', { ...clickEventInit, buttons: 0 }));
      backdropTarget.dispatchEvent(new MouseEvent('click', { ...clickEventInit, buttons: 0, detail: 1 }));

      const closedAfterBackdrop = await waitForCondition(() => !this.isPopoverOpen(), 1500);
      _activeTriggerElement = null;

      if (!closedAfterBackdrop) {
        throw new Error('[AFB-Settings] Failed to close Settings popover: container still present in DOM');
      }

      log('[AFB-Settings] Popover closed successfully via backdrop VERIFIED ✓');
      return true;
    },

    /**
     * Safely closes any open popup menu (e.g. tile context menu) without touching Agent or Escape.
     */
    async closePopupMenu(log = console.log) {
      log('[AFB-Settings] Closing open popup menu via neutral backdrop click');
      const backdropTarget = document.querySelector('flow-canvas, main') || document.body;
      const clickEventInit = { bubbles: true, cancelable: true, composed: true, clientX: 100, clientY: 100, button: 0 };
      backdropTarget.dispatchEvent(new PointerEvent('pointerdown', { ...clickEventInit, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
      backdropTarget.dispatchEvent(new MouseEvent('mousedown', clickEventInit));
      await new Promise(r => setTimeout(r, 40));
      backdropTarget.dispatchEvent(new PointerEvent('pointerup', { ...clickEventInit, pointerId: 1, pointerType: 'mouse', buttons: 0 }));
      backdropTarget.dispatchEvent(new MouseEvent('mouseup', { ...clickEventInit, buttons: 0 }));
      backdropTarget.dispatchEvent(new MouseEvent('click', { ...clickEventInit, buttons: 0, detail: 1 }));
      await new Promise(r => setTimeout(r, 300));
    },

    /**
     * Complete Sequential Execution Pipeline with Fail-Fast Error Propagation
     */
    async applyVariantSettings(settings, log = console.log) {
      try {
        const targetType = (settings.type || 'image').toLowerCase();
        const targetRatio = settings.ratio || (targetType === 'video' ? '16:9' : '16:9');
        const targetModel = settings.model || (targetType === 'video' ? 'Omni 1.1 Flash' : 'Nano Banana 2');
        const targetBatch = String(settings.batch || '4');

        log(`[AFB-Settings] Applying settings: Type=${targetType}, Ratio=${targetRatio}, Model=${targetModel}, Batch=x${targetBatch}`);

        // STEP 1: Buka popover & tunggu hingga content mounted dalam DOM
        await this.openPopover(log);

        // STEP 2: Validasi & sinkronisasi mode utama (Image vs Video)
        await this.selectType(targetType, log);

        // STEP 3: Pilih model family dengan menu interaction
        await this.selectModel(targetModel, log);

        // STEP 4: Pilih aspect ratio
        await this.selectRatio(targetRatio, log);

        // STEP 5: Penanganan sub-opsi video jika mode Video
        if (targetType === 'video') {
          await this.selectVideoControls(settings, log);
        }

        // STEP 6: Pilih batch count (x1, x2, x3, x4)
        await this.selectBatch(targetBatch, log);

        // STEP 7: Verifikasi akhir seluruh state aktif (Post-Check)
        const finalState = this.readCurrentState();
        log(`[AFB-Settings] Popover verified state: Type=${finalState.type}, Ratio=${finalState.ratio}, Model="${finalState.model}", Batch=x${finalState.batch}`);

        // STEP 8: Tutup popover secara aman via stored trigger reference
        await this.closePopover(log);

        log('[AFB-Settings] All popover settings applied and verified successfully ✓');
        return { ok: true, state: finalState };
      } catch (err) {
        const errMsg = err && err.message ? err.message : String(err);
        log(`[AFB-Settings] ERROR: ${errMsg}`);
        try {
          await this.closePopover(log);
        } catch (_) {}
        return { ok: false, error: errMsg };
      }
    }
  };
})();
