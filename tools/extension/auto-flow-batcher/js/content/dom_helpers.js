// DOM Helpers for Auto Flow Batcher
// Real Mouse Sequences, Reliable ProseMirror Discovery & Component Utilities
(function () {
  window.AFB_DOM = {
    /**
     * Checks if a DOM element is rendered and visible in viewport.
     * @param {HTMLElement} element
     * @returns {boolean}
     */
    isVisibleElement(element) {
      if (!element || !(element instanceof HTMLElement)) return false;
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 &&
             style.display !== 'none' &&
             style.visibility !== 'hidden' &&
             style.opacity !== '0' &&
             style.pointerEvents !== 'none';
    },

    /**
     * Verifies if current location is a Flow project workspace.
     * @returns {boolean}
     */
    isFlowProjectPage() {
      return location.href.includes('flow.google.com/project/');
    },

    /**
     * Locates the active ProseMirror rich-text editor for prompt input.
     * @returns {HTMLElement|null}
     */
    findEditor() {
      const isVisible = window.AFB_DOM.isVisibleElement;
      const editorSelector = window.__AFB_RUNTIME_CONFIG__?.selectors?.editor;
      if (editorSelector) {
        const customEl = Array.from(document.querySelectorAll(editorSelector)).filter(isVisible);
        if (customEl.length > 0) return customEl[0];
      }

      const promptEditors = Array.from(document.querySelectorAll('[role="textbox"][contenteditable="true"], div[contenteditable="true"]')).filter(isVisible);
      if (promptEditors.length > 0) return promptEditors[0];

      return null;
    },

    /**
     * Locates the 'New Project' button on Flow landing page.
     * @returns {HTMLButtonElement|HTMLElement|null}
     */
    findNewProjectButton() {
      const isVisible = window.AFB_DOM.isVisibleElement;

      // Strategy 0: Direct class or aria-label match
      const directButton = document.querySelector('.new-project-button, button[aria-label="New project"]');
      if (directButton && isVisible(directButton) && !directButton.disabled) return directButton;

      // Strategy 0.5: Search by looking at child mat-icon element content for "add" mapping to a button with "New project"
      const buttons = Array.from(document.querySelectorAll('button'));
      const iconSel = window.__AFB_RUNTIME_CONFIG__?.selectors?.iconElements || 'mat-icon, .google-symbols';
      const exactMatchByDOM = buttons.find(button => {
        if (!isVisible(button) || button.disabled) return false;
        const textSpan = button.querySelector('span');
        const iconSpan = button.querySelector(iconSel);
        return textSpan && textSpan.textContent.includes('New project') && iconSpan && (iconSpan.textContent.includes('add') || iconSpan.textContent.includes('add_2'));
      });
      if (exactMatchByDOM) return exactMatchByDOM;

      // Strategy 1: Button with add_2 or add icon + known English text
      const byEnglishText = buttons.find(button => {
        const text = (button.textContent || '').replace(/\s+/g, ' ').trim();
        return isVisible(button) && !button.disabled &&
               text.includes('New project') && (text.includes('add_2') || text.includes('add') || button.innerHTML.includes('>add<'));
      });
      if (byEnglishText) return byEnglishText;

      // Strategy 2: Button with add_2 or add icon that is NOT a reference/upload button
      const byAdd2Icon = buttons.find(button => {
        if (!isVisible(button) || button.disabled) return false;
        if (button.getAttribute('aria-haspopup') === 'dialog') return false;
        const html = button.innerHTML || '';
        if (!html.includes('add_2') && !html.includes('>add<')) return false;
        if (button.closest('[role="toolbar"]')) return false;
        if (html.includes('arrow_forward')) return false;
        return true;
      });
      if (byAdd2Icon) return byAdd2Icon;

      // Strategy 3: Exact English text match
      return buttons.find(button => {
        const text = (button.textContent || '').replace(/\s+/g, ' ').trim();
        return isVisible(button) && !button.disabled && text === 'New project';
      }) || null;
    },

    /**
     * Clicks the 'New project' button from Flow landing page.
     * @param {Function} log
     * @param {Function} isRunningFn
     * @returns {Promise<boolean>}
     */
    async clickNewProjectFromLanding(log = console.log, isRunningFn = () => true) {
      log('Flow landing page detected; creating a new project with current page settings');
      for (let attempt = 1; attempt <= 40 && isRunningFn(); attempt++) {
        const button = window.AFB_DOM.findNewProjectButton();
        if (button) {
          button.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
          await new Promise(r => setTimeout(r, 100));
          window.AFB_DOM.dispatchMouseSequence(button, 'New project button');
          return true;
        }
        await new Promise(r => setTimeout(r, 250));
      }
      return false;
    },

    /**
     * Ensures Flow project workspace is active and editor is available.
     * @param {Function} log
     * @param {Function} isRunningFn
     */
    async ensureFlowProjectReady(log = console.log, isRunningFn = () => true) {
      if (window.AFB_DOM.isFlowProjectPage() && window.AFB_DOM.findEditor()) return;

      if (!window.AFB_DOM.isFlowProjectPage()) {
        const clicked = await window.AFB_DOM.clickNewProjectFromLanding(log, isRunningFn);
        if (!clicked) throw new Error('New project button not found');
      }

      const startTime = Date.now();
      while (Date.now() - startTime < 30000 && isRunningFn()) {
        if (window.AFB_DOM.isFlowProjectPage()) {
          const editor = window.AFB_DOM.findEditor();
          if (editor && window.AFB_DOM.isVisibleElement(editor)) {
            log(`Flow project ready: ${location.href}`);
            await new Promise(r => setTimeout(r, 1500));
            return;
          }
        }
        await new Promise(r => setTimeout(r, 250));
      }

      if (!isRunningFn()) throw new Error('Stopped while waiting for Flow project');
      throw new Error('Timed out waiting for Flow project editor');
    },

    /**
     * Computes the bounding center of a DOM element.
     * @param {HTMLElement} element
     * @returns {{x: number, y: number, rect: DOMRect}}
     */
    getElementCenter(element) {
      const rect = element.getBoundingClientRect();
      return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
        rect
      };
    },

    /**
     * Calculates Euclidean distance between two elements.
     * @param {HTMLElement} a
     * @param {HTMLElement} b
     * @returns {number}
     */
    distanceBetweenElements(a, b) {
      const ca = window.AFB_DOM.getElementCenter(a);
      const cb = window.AFB_DOM.getElementCenter(b);
      return Math.hypot(ca.x - cb.x, ca.y - cb.y);
    },

    /**
     * Dispatches exact, realistic pointer & mouse events:
     * pointerover -> pointerenter -> pointerdown -> mousedown -> pointerup -> mouseup -> click
     * Uses element center coordinates without synthetic cancellation.
     * @param {HTMLElement} element
     * @param {string} [label]
     */
    dispatchMouseSequence(element, label = 'element') {
      if (!element) return;
      element.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
      const rect = element.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const eventInit = { bubbles: true, cancelable: true, composed: true, clientX: cx, clientY: cy, button: 0, buttons: 1 };
      const pointerInit = { ...eventInit, pointerId: 1, pointerType: 'mouse', isPrimary: true };

      element.focus?.();
      element.dispatchEvent(new PointerEvent('pointerover', pointerInit));
      element.dispatchEvent(new PointerEvent('pointerenter', { ...pointerInit, bubbles: false }));
      element.dispatchEvent(new PointerEvent('pointerdown', pointerInit));
      element.dispatchEvent(new MouseEvent('mousedown', eventInit));
      element.dispatchEvent(new PointerEvent('pointerup', { ...pointerInit, buttons: 0 }));
      element.dispatchEvent(new MouseEvent('mouseup', { ...eventInit, buttons: 0 }));
      element.dispatchEvent(new MouseEvent('click', { ...eventInit, buttons: 0, detail: 1 }));
    },

    /**
     * Simulates hover sequence on an element.
     * @param {HTMLElement} element
     * @param {string} [label]
     */
    hoverElement(element, label = 'element') {
      if (!element) return;
      element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
      const rect = element.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      element.dispatchEvent(new PointerEvent('pointerover', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, pointerType: 'mouse' }));
      element.dispatchEvent(new PointerEvent('pointerenter', { bubbles: false, cancelable: true, clientX: cx, clientY: cy, pointerType: 'mouse' }));
      element.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, pointerType: 'mouse' }));
      element.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, cancelable: true, clientX: cx, clientY: cy }));
      element.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false, cancelable: true, clientX: cx, clientY: cy }));
      element.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, cancelable: true, clientX: cx, clientY: cy }));
    },

    /**
     * Finds a menuitem element matching given text within root.
     * @param {string} text
     * @param {HTMLElement|Document} root
     * @returns {HTMLElement|null}
     */
    findMenuItemByText(text, root = document) {
      const target = text.toLowerCase();
      const items = root.querySelectorAll('button[role="menuitem"], div[role="menuitem"], [role="option"]');
      for (let item of items) {
        if (!window.AFB_DOM.isVisibleElement(item)) continue;
        const itemText = (item.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
        if (itemText.includes(target)) return item;
      }
      return null;
    },

    /**
     * Waits for a minimum count of open menus in DOM.
     * @param {number} minCount
     * @param {number} timeoutMs
     * @param {string} [label]
     * @param {Function} [log]
     * @returns {Promise<HTMLElement[]>}
     */
    async waitForOpenMenuCount(minCount, timeoutMs, label = 'menu', log = console.log) {
      const started = Date.now();
      while (Date.now() - started < timeoutMs) {
        const menus = Array.from(document.querySelectorAll('div[role="menu"][data-state="open"], [role="menu"]')).filter(window.AFB_DOM.isVisibleElement);
        if (menus.length >= minCount) return menus;
        await new Promise(r => setTimeout(r, 200));
      }
      return Array.from(document.querySelectorAll('div[role="menu"][data-state="open"], [role="menu"]')).filter(window.AFB_DOM.isVisibleElement);
    }
  };
})();
