// Auto Flow Batcher - Content Script vPURE
// No DOM building, no extra events — just clear → selection → beforeinput

if (window.top !== window.self) {
} else {
  (function () {
     // Prevent double-injection: if content script was already loaded (e.g., by manifest
     // content_scripts AND ensureContentScript), skip the second execution to avoid
     // duplicate message listeners that cause prompts to run twice simultaneously.
     if (window.__AFB_CONTENT_LOADED__) {
       console.log('[AFB] Content script already loaded, skipping duplicate injection');
       return;
     }
     window.__AFB_CONTENT_LOADED__ = true;

     // Guard: only run on Flow pages. Project creation is handled when started from the Flow landing page.
     // Supports any locale prefix (e.g., /id/, /my/, /en/, or none) before /tools/flow/
     const isFlowPage = location.href.includes('/labs.google/fx/') &&
                        location.href.includes('/tools/flow');
     if (!isFlowPage) {
       console.log('[AFB] Not on Flow page, skipping content script');
       return;
     }

    let isRunning = true;

      function hasExtensionRuntime() {
        return typeof chrome !== 'undefined' && chrome.runtime && typeof chrome.runtime.sendMessage === 'function';
      }

      function hasExtensionMessageListener() {
        return typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.onMessage && typeof chrome.runtime.onMessage.addListener === 'function';
      }

      function safeRuntimeSendMessage(message) {
        if (!hasExtensionRuntime()) return;
        try {
          const result = chrome.runtime.sendMessage(message);
          if (result && typeof result.catch === 'function') result.catch(() => {});
        } catch (e) {}
      }

      function log(msg) {
        safeRuntimeSendMessage({ action: "LOG_FROM_CONTENT", message: msg });
        console.log('[AFB]', msg);
      }

    function findEditor() {
      return document.querySelector('[data-slate-editor="true"]') ||
             document.querySelector('[role="textbox"][contenteditable="true"]') ||
             document.querySelector('.sc-522e4d41-5.gihCJr');
    }

    function isFlowProjectPage() {
      return location.href.includes('/tools/flow/project/');
    }

    function findNewProjectButton() {
      const buttons = Array.from(document.querySelectorAll('button'));
      // Strategy 1: Button with add_2 icon + known English text
      const byEnglishText = buttons.find(button => {
        const text = (button.textContent || '').replace(/\s+/g, ' ').trim();
        return isVisibleElement(button) && !button.disabled &&
               text.includes('New project') && text.includes('add_2');
      });
      if (byEnglishText) return byEnglishText;

      // Strategy 2: Button with add_2 icon that is NOT a reference/upload button
      // The "New project" button uses add_2 icon and is typically on the Flow landing page
      // It does NOT have aria-haspopup="dialog" (which is the reference upload button)
      const byAdd2Icon = buttons.find(button => {
        if (!isVisibleElement(button) || button.disabled) return false;
        if (button.getAttribute('aria-haspopup') === 'dialog') return false;
        const html = button.innerHTML || '';
        // Must have add_2 icon, must NOT be inside a toolbar (those are tile action buttons)
        if (!html.includes('add_2')) return false;
        if (button.closest('[role="toolbar"]')) return false;
        // Exclude buttons that are clearly for other purposes (Create, arrow_forward)
        if (html.includes('arrow_forward')) return false;
        return true;
      });
      if (byAdd2Icon) return byAdd2Icon;

      // Strategy 3: Exact English text match (fallback)
      return buttons.find(button => {
        const text = (button.textContent || '').replace(/\s+/g, ' ').trim();
        return isVisibleElement(button) && !button.disabled && text === 'New project';
      });
    }

    async function clickNewProjectFromLanding() {
      log('Flow landing page detected; creating a new project with current page settings');
      for (let attempt = 1; attempt <= 40 && isRunning; attempt++) {
        const button = findNewProjectButton();
        if (button) {
          button.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
          await new Promise(r => setTimeout(r, 100));
          dispatchMouseSequence(button, 'New project button');
          return true;
        }
        await new Promise(r => setTimeout(r, 250));
      }
      return false;
    }

    async function ensureFlowProjectReady() {
      if (isFlowProjectPage() && findEditor()) return;

      if (!isFlowProjectPage()) {
        const clicked = await clickNewProjectFromLanding();
        if (!clicked) throw new Error('New project button not found');
      }

      const startTime = Date.now();
      while (Date.now() - startTime < 30000 && isRunning) {
        if (isFlowProjectPage()) {
          const editor = findEditor();
          if (editor && isVisibleElement(editor)) {
            log(`Flow project ready: ${location.href}`);
            await new Promise(r => setTimeout(r, 1500));
            return;
          }
        }
        await new Promise(r => setTimeout(r, 250));
      }

      if (!isRunning) throw new Error('Stopped while waiting for Flow project');
      throw new Error('Timed out waiting for Flow project editor');
    }
 
// Get any editable content element in the editor
      function getParagraph(editor) {
        // Try standard Slate paragraphs first
        let p = editor.querySelector('p[data-slate-node="element"]') ||
                editor.querySelector('p') ||
                editor.querySelector('div[data-slate-node="element"]');
        
        if (p) return p;
        
        // Empty editor handling: look for placeholder or first child
        const placeholder = editor.querySelector('[data-slate-placeholder]');
        if (placeholder) {
          // Placeholder usually inside a paragraph - get its parent
          return placeholder.closest('p') || placeholder.parentElement;
        }
        
        // Any element child
        if (editor.firstElementChild) {
          return editor.firstElementChild;
        }
        
        // Text node only? Return editor itself
        return editor;
      }

      function isVisibleElement(element) {
        if (!element || !(element instanceof HTMLElement)) return false;
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 &&
               style.display !== 'none' &&
               style.visibility !== 'hidden' &&
               style.opacity !== '0' &&
               style.pointerEvents !== 'none';
      }

      function getElementCenter(element) {
        const rect = element.getBoundingClientRect();
        return {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
          rect
        };
      }

      function distanceBetweenElements(a, b) {
        const ca = getElementCenter(a);
        const cb = getElementCenter(b);
        return Math.hypot(ca.x - cb.x, ca.y - cb.y);
      }

      function dispatchMouseSequence(element, label = 'element') {
        const rect = element.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        element.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, pointerType: 'mouse' }));
        element.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, cancelable: true, clientX: cx, clientY: cy }));
        element.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, cancelable: true, clientX: cx, clientY: cy }));
        element.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0, pointerType: 'mouse' }));
        element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
        element.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0, pointerType: 'mouse' }));
        element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
        element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
        log(`DEBUG: Dispatched mouse sequence on ${label}`);
      }

      function hoverElement(element, label = 'element') {
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
        log(`>>> Hover triggered on ${label} at ${Math.round(cx)},${Math.round(cy)}`);
      }

// Click the variant settings button (opens popup menu) — robust selector
      async function clickVariantButton() {
        const MAX_RETRIES = 20;
        const RETRY_DELAY = 200;

        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
          try {
            let button = null;
            const buttons = document.querySelectorAll('button[aria-haspopup="menu"]');
            log(`DEBUG: Found ${buttons.length} button(s) with aria-haspopup="menu"`);

            if (buttons.length === 1) {
              button = buttons[0];
            } else {
               for (let btn of buttons) {
                 const txt = (btn.textContent || '').trim();
                 if (txt.includes('🍌') || txt.includes('📷') || txt.includes('Nano Banana') || txt.includes('Imagen') || txt.includes('Veo') || txt.includes('3D') || txt.includes('Audio') || txt.includes('Video') || txt.includes('Image')) {
                   button = btn;
                   log(`DEBUG: Selected variant button by text: "${txt.substring(0, 50)}"`);
                   break;
                 }
               }
              if (!button) {
                for (let btn of buttons) {
                  const txt = (btn.textContent || '').trim();
                  if (!txt.includes('Create') && !txt.includes('arrow_forward')) {
                    button = btn;
                    log(`DEBUG: Selected first non-Create button`);
                    break;
                  }
                }
              }
            }

            if (!button) {
              await new Promise(r => setTimeout(r, RETRY_DELAY));
              continue;
            }

            const style = window.getComputedStyle(button);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
              await new Promise(r => setTimeout(r, RETRY_DELAY));
              continue;
            }

            if (button.disabled) {
              await new Promise(r => setTimeout(r, RETRY_DELAY));
              continue;
            }

            // Get bounding rect for coordinates
            const rect = button.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;

            // Dispatch pointer events (more realistic for modern UI)
            const pointerDown = new PointerEvent('pointerdown', {
              bubbles: true,
              cancelable: true,
              clientX: centerX,
              clientY: centerY,
              button: 0,
              pointerType: 'mouse'
            });
            button.dispatchEvent(pointerDown);
            await new Promise(r => setTimeout(r, 50));

            const pointerUp = new PointerEvent('pointerup', {
              bubbles: true,
              cancelable: true,
              clientX: centerX,
              clientY: centerY,
              button: 0,
              pointerType: 'mouse'
            });
            button.dispatchEvent(pointerUp);
            await new Promise(r => setTimeout(r, 50));

            const clickEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
              clientX: centerX,
              clientY: centerY,
              button: 0
            });
            button.dispatchEvent(clickEvent);

            log(`>>> Variant button clicked (attempt ${attempt}) via pointer+click`);

            // Wait for popup to render
            await new Promise(r => setTimeout(r, 1000));

            // VERIFY: check button state changed to open or popup element visible
            const controlsId = button.getAttribute('aria-controls');
            const newState = button.getAttribute('data-state');
            const newExpanded = button.getAttribute('aria-expanded');
            log(`DEBUG: Post-click state: data-state="${newState}", aria-expanded="${newExpanded}, aria-controls="${controlsId}"`);

            let popupVisible = false;
            if (controlsId) {
              const popup = document.getElementById(controlsId);
              if (popup) {
                const style = window.getComputedStyle(popup);
                popupVisible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' && style.pointerEvents !== 'none';
                log(`DEBUG: Popup element found: ${popup.tagName}, visible=${popupVisible}`);
              } else {
                log(`DEBUG: Popup element not found (id=${controlsId})`);
              }
            }

            if (newState === 'open' || newExpanded === 'true' || popupVisible) {
              log(`>>> Popup confirmed open`);
              return true;
            }

            // If not verified, continue retry
            await new Promise(r => setTimeout(r, RETRY_DELAY));
          } catch (e) {
            log(`DEBUG: Error on attempt ${attempt}: ${e.message}`);
            await new Promise(r => setTimeout(r, RETRY_DELAY));
          }
        }

        log('WARN: Variant button not clicked after ' + MAX_RETRIES + ' attempts');
        return false;
      }

        function isBatchTab(text, batch) {
          const normalized = text.toLowerCase().replace(/\s/g, '');
          const batchStr = String(batch);
          return normalized === batchStr + 'x' || normalized === 'x' + batchStr;
        }

        async function selectModeTab(mode, ratio = null, batch = '1') {
        const MAX_RETRIES = 10;
        const RETRY_DELAY = 150;

        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
          try {
            // Find open popup menu
            const menu = document.querySelector('div[role="menu"][data-state="open"]');
            if (!menu) {
              await new Promise(r => setTimeout(r, RETRY_DELAY));
              continue;
            }

            // Find all tabs within menu
            const tabs = menu.querySelectorAll('button[role="tab"]');
            log(`DEBUG: Found ${tabs.length} mode tabs in popup`);

            // STEP 1: Select top-level tab (Image or Video)
            let targetTab = null;
            const upperMode = mode.toUpperCase();
            for (let tab of tabs) {
              const txt = (tab.textContent || '').trim();
              if (txt.toUpperCase().includes(upperMode)) {
                targetTab = tab;
                log(`DEBUG: Found top-level ${mode} tab: "${txt}"`);
                break;
              }
            }

            if (!targetTab) {
              await new Promise(r => setTimeout(r, RETRY_DELAY));
              continue;
            }

            // If not selected, click it
            if (targetTab.getAttribute('aria-selected') !== 'true') {
              const style = window.getComputedStyle(targetTab);
              if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                await new Promise(r => setTimeout(r, RETRY_DELAY));
                continue;
              }

              targetTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
              await new Promise(r => setTimeout(r, 80));
              targetTab.focus();
              await new Promise(r => setTimeout(r, 50));

              const rect = targetTab.getBoundingClientRect();
              const cx = rect.left + rect.width / 2;
              const cy = rect.top + rect.height / 2;

              targetTab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
              await new Promise(r => setTimeout(r, 50));
              targetTab.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
              await new Promise(r => setTimeout(r, 50));
              targetTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));

              log(`>>> Top-level tab "${mode}" clicked (attempt ${attempt})`);
              await new Promise(r => setTimeout(r, 500));
            } else {
              log(`>>> Top-level tab "${mode}" already selected`);
            }

            // STEP 2a: For video mode, select "Ingredients" sub-tab first
            if (mode === 'video') {
              await new Promise(r => setTimeout(r, 200));
              const updatedMenu = document.querySelector('div[role="menu"][data-state="open"]');
              if (!updatedMenu) {
                log('WARN: Menu disappeared after selecting Video tab');
                return true;
              }

              // Select Ingredients sub-tab
              const allSubTabs = updatedMenu.querySelectorAll('button[role="tab"]');
              let ingredientsTab = null;
              for (let tab of allSubTabs) {
                const txt = (tab.textContent || '').trim().toLowerCase();
                if (txt.includes('ingredients')) {
                  ingredientsTab = tab;
                  log(`DEBUG: Found Ingredients sub-tab: "${txt}"`);
                  break;
                }
              }

              if (!ingredientsTab) {
                log('WARN: Ingredients sub-tab not found');
              } else if (ingredientsTab.getAttribute('aria-selected') !== 'true') {
                const style = window.getComputedStyle(ingredientsTab);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                  await new Promise(r => setTimeout(r, RETRY_DELAY));
                  continue;
                }

                ingredientsTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
                await new Promise(r => setTimeout(r, 80));
                ingredientsTab.focus();
                await new Promise(r => setTimeout(r, 50));

                const rect2 = ingredientsTab.getBoundingClientRect();
                const cx2 = rect2.left + rect2.width / 2;
                const cy2 = rect2.top + rect2.height / 2;

                ingredientsTab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx2, clientY: cy2, button: 0 }));
                await new Promise(r => setTimeout(r, 50));
                ingredientsTab.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx2, clientY: cy2, button: 0 }));
                await new Promise(r => setTimeout(r, 50));
                ingredientsTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx2, clientY: cy2, button: 0 }));

                log(`>>> Ingredients sub-tab clicked`);
                await new Promise(r => setTimeout(r, 250));
              } else {
                log(`>>> Ingredients already selected`);
              }

              // STEP 2b: After selecting Ingredients, now select the ratio sub-tab for video (16:9 or 9:16)
              await new Promise(r => setTimeout(r, 200));
              const finalMenu = document.querySelector('div[role="menu"][data-state="open"]');
              if (!finalMenu) {
                log('WARN: Menu disappeared after selecting Ingredients');
                return true;
              }

              const ratioTabs = finalMenu.querySelectorAll('button[role="tab"]');
              let targetRatioTab = null;
              if (ratio) {
                for (let tab of ratioTabs) {
                  const txt = (tab.textContent || '').trim().toLowerCase();
                  if (txt.includes(ratio.toLowerCase())) {
                    targetRatioTab = tab;
                    log(`DEBUG: Found video ratio tab "${ratio}": "${txt}"`);
                    break;
                  }
                }
              }

              if (!targetRatioTab && ratio) {
                log(`WARN: Video ratio tab "${ratio}" not found, available: ${Array.from(ratioTabs).map(t => t.textContent.trim()).join(', ')}`);
                // Not fatal — continue without ratio selection
              } else if (targetRatioTab) {
                if (targetRatioTab.getAttribute('aria-selected') !== 'true') {
                  const style = window.getComputedStyle(targetRatioTab);
                  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    // Skip if disabled
                    log(`WARN: Ratio tab "${ratio}" is disabled/not visible`);
                  } else {
                    targetRatioTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await new Promise(r => setTimeout(r, 80));
                    targetRatioTab.focus();
                    await new Promise(r => setTimeout(r, 50));

                    const rect3 = targetRatioTab.getBoundingClientRect();
                    const cx3 = rect3.left + rect3.width / 2;
                    const cy3 = rect3.top + rect3.height / 2;

                    targetRatioTab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));
                    await new Promise(r => setTimeout(r, 50));
                    targetRatioTab.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));
                    await new Promise(r => setTimeout(r, 50));
                    targetRatioTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));

                    log(`>>> Video ratio tab "${ratio}" clicked`);
                    await new Promise(r => setTimeout(r, 250));

                    if (targetRatioTab.getAttribute('aria-selected') === 'true') {
                      log(`>>> Video ratio confirmed: ${ratio}`);
                    } else {
                      log(`WARN: Video ratio not confirmed after click`);
                    }
                  }
                } else {
                  log(`>>> Video ratio "${ratio}" already selected`);
                }
              }

              // STEP 2c: After ratio, select batch count
              if (batch) {
                await new Promise(r => setTimeout(r, 200));
                const batchMenu = document.querySelector('div[role="menu"][data-state="open"]');
                if (!batchMenu) {
                  log('WARN: Menu disappeared after selecting video ratio');
                  return true;
                }

                const batchTabs = batchMenu.querySelectorAll('button[role="tab"]');
                let batchTab = null;
                const batchKey = `x${batch}`;
                for (let tab of batchTabs) {
                  const txt = (tab.textContent || '').trim();
                   if (isBatchTab(txt, batch)) {
                    batchTab = tab;
                    log(`DEBUG: Found video batch tab "${batchKey}": "${txt}"`);
                    break;
                  }
                }

                if (!batchTab) {
                  log(`WARN: Video batch tab "${batchKey}" not found, available: ${Array.from(batchTabs).map(t => t.textContent.trim()).join(', ')}`);
                } else if (batchTab.getAttribute('aria-selected') !== 'true') {
                  const style = window.getComputedStyle(batchTab);
                  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    log(`WARN: Batch tab "${batchKey}" is disabled/not visible`);
                  } else {
                    batchTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await new Promise(r => setTimeout(r, 80));
                    batchTab.focus();
                    await new Promise(r => setTimeout(r, 50));

                    const rect3 = batchTab.getBoundingClientRect();
                    const cx3 = rect3.left + rect3.width / 2;
                    const cy3 = rect3.top + rect3.height / 2;

                    batchTab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));
                    await new Promise(r => setTimeout(r, 50));
                    batchTab.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));
                    await new Promise(r => setTimeout(r, 50));
                    batchTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));

                    log(`>>> Video batch tab "${batchKey}" clicked`);
                    await new Promise(r => setTimeout(r, 250));

                    if (batchTab.getAttribute('aria-selected') === 'true') {
                      log(`>>> Video batch confirmed: ${batchKey}`);
                    } else {
                      log(`WARN: Video batch not confirmed after click`);
                    }
                  }
                } else {
                  log(`>>> Video batch "${batchKey}" already selected`);
                }
              }

              // Success after completing video flow (up to batch)
              return true;
            }

            // STEP 2b: For image mode, select ratio sub-tab if ratio provided
            if (mode === 'image' && ratio) {
              await new Promise(r => setTimeout(r, 200));
              const updatedMenu = document.querySelector('div[role="menu"][data-state="open"]');
              if (!updatedMenu) {
                log('WARN: Menu disappeared after selecting Image tab');
                return true;
              }

              const subTabs = updatedMenu.querySelectorAll('button[role="tab"]');
              let ratioTab = null;
              for (let tab of subTabs) {
                const txt = (tab.textContent || '').trim();
                if (txt.toLowerCase().includes(ratio.toLowerCase())) {
                  ratioTab = tab;
                  log(`DEBUG: Found ratio tab "${ratio}": "${txt}"`);
                  break;
                }
              }

              if (!ratioTab) {
                log(`WARN: Ratio tab "${ratio}" not found, will skip ratio selection`);
                // Don't return — continue to batch selection
              } else if (ratioTab.getAttribute('aria-selected') !== 'true') {
                const style = window.getComputedStyle(ratioTab);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                  await new Promise(r => setTimeout(r, RETRY_DELAY));
                  continue;
                }

                ratioTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
                await new Promise(r => setTimeout(r, 80));
                ratioTab.focus();
                await new Promise(r => setTimeout(r, 50));

                const rect2 = ratioTab.getBoundingClientRect();
                const cx2 = rect2.left + rect2.width / 2;
                const cy2 = rect2.top + rect2.height / 2;

                ratioTab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx2, clientY: cy2, button: 0 }));
                await new Promise(r => setTimeout(r, 50));
                ratioTab.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx2, clientY: cy2, button: 0 }));
                await new Promise(r => setTimeout(r, 50));
                ratioTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx2, clientY: cy2, button: 0 }));

                log(`>>> Ratio tab "${ratio}" clicked`);
                await new Promise(r => setTimeout(r, 250));
              } else {
                log(`>>> Ratio "${ratio}" already selected`);
              }

              // STEP 2c: After ratio, select batch count
              if (batch) {
                await new Promise(r => setTimeout(r, 200));
                const finalMenu = document.querySelector('div[role="menu"][data-state="open"]');
                if (!finalMenu) {
                  log('WARN: Menu disappeared after selecting ratio');
                  return true;
                }

                const batchTabs = finalMenu.querySelectorAll('button[role="tab"]');
                let batchTab = null;
                const batchKey = `x${batch}`;
                for (let tab of batchTabs) {
                  const txt = (tab.textContent || '').trim();
                   if (isBatchTab(txt, batch)) {
                    batchTab = tab;
                    log(`DEBUG: Found batch tab "${batchKey}": "${txt}"`);
                    break;
                  }
                }

                if (!batchTab) {
                  log(`WARN: Batch tab "${batchKey}" not found, available: ${Array.from(batchTabs).map(t => t.textContent.trim()).join(', ')}`);
                } else if (batchTab.getAttribute('aria-selected') !== 'true') {
                  const style = window.getComputedStyle(batchTab);
                  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    log(`WARN: Batch tab "${batchKey}" is disabled/not visible`);
                  } else {
                    batchTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await new Promise(r => setTimeout(r, 80));
                    batchTab.focus();
                    await new Promise(r => setTimeout(r, 50));

                    const rect3 = batchTab.getBoundingClientRect();
                    const cx3 = rect3.left + rect3.width / 2;
                    const cy3 = rect3.top + rect3.height / 2;

                    batchTab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));
                    await new Promise(r => setTimeout(r, 50));
                    batchTab.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));
                    await new Promise(r => setTimeout(r, 50));
                    batchTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx3, clientY: cy3, button: 0 }));

                    log(`>>> Batch tab "${batchKey}" clicked`);
                    await new Promise(r => setTimeout(r, 250));

                    if (batchTab.getAttribute('aria-selected') === 'true') {
                      log(`>>> Batch confirmed: ${batchKey}`);
                    } else {
                      log(`WARN: Batch "${batchKey}" not confirmed after click`);
                    }
                  }
                } else {
                  log(`>>> Batch "${batchKey}" already selected`);
                }
              }

              // Success after completing image flow (up to batch)
              return true;
            }

            // Should not get here
            return true;
          } catch (e) {
            await new Promise(r => setTimeout(r, RETRY_DELAY));
          }
        }

        log(`WARN: Mode tab "${mode}" (or sub-tab) not fully selected after retries`);
        return false;
      }

// Close the popup menu — uses double-click on trigger, then click outside, then Escape
        async function closePopupMenu() {
         const MAX_RETRIES = 5;
         const RETRY_DELAY = 150;

         for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
           try {
             // Find variant trigger button
             const buttons = document.querySelectorAll('button[aria-haspopup="menu"]');
             let button = null;
             for (let btn of buttons) {
               const txt = (btn.textContent || '').trim();
               if (txt.includes('🍌') || txt.includes('📷') || txt.includes('Nano Banana') || txt.includes('Imagen') || txt.includes('Veo') || txt.includes('3D') || txt.includes('Audio') || txt.includes('Video') || txt.includes('Image')) {
                 button = btn;
                 break;
               }
             }
             if (!button) {
               // No button = menu probably gone
               log(`>>> Popup closed (button gone)`);
               return true;
             }

             const state = button.getAttribute('data-state');
             const expanded = button.getAttribute('aria-expanded');
             if (state === 'closed' && expanded !== 'true') {
               log(`>>> Popup already closed`);
               return true;
             }

             // Strategy 1: double-click the button
             const rect = button.getBoundingClientRect();
             const cx = rect.left + rect.width / 2;
             const cy = rect.top + rect.height / 2;

             const doClick = (el) => {
               el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
               el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
               el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
             };

             // First click
             doClick(button);
             await new Promise(r => setTimeout(r, 80));
             // Second click (toggle)
             doClick(button);
             await new Promise(r => setTimeout(r, 300));

             // After double-click, check if popup menu is gone
             const stillOpen = document.querySelector('div[role="menu"][data-state="open"]');
             if (!stillOpen) {
               log(`>>> Popup closed after double-click`);
               return true;
             }

             // Strategy 2: click outside (top-left corner of page)
             const body = document.body;
             const bodyRect = body.getBoundingClientRect();
             const outsideX = bodyRect.left + 5;
             const outsideY = bodyRect.top + 5;

             body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: outsideX, clientY: outsideY, button: 0 }));
             body.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: outsideX, clientY: outsideY, button: 0 }));
             body.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: outsideX, clientY: outsideY, button: 0 }));
             await new Promise(r => setTimeout(r, 300));

             // Re-check after click-outside
             const stillOpen2 = document.querySelector('div[role="menu"][data-state="open"]');
             if (!stillOpen2) {
               log(`>>> Popup closed after click-outside`);
               return true;
             }

             // Strategy 3: Escape key — focus menu first then dispatch
             const menu = document.querySelector('div[role="menu"][data-state="open"]');
             if (menu) {
               menu.focus();
             }
             const escEvent = new KeyboardEvent('keydown', {
               key: 'Escape',
               code: 'Escape',
               keyCode: 27,
               which: 27,
               bubbles: true,
               cancelable: true
             });
             document.dispatchEvent(escEvent);
             await new Promise(r => setTimeout(r, 300));

             const stillOpen3 = document.querySelector('div[role="menu"][data-state="open"]');
             if (!stillOpen3) {
               log(`>>> Popup closed after Escape`);
               return true;
             }

           } catch (e) {
             await new Promise(r => setTimeout(r, RETRY_DELAY));
           }
         }

         log('WARN: Popup may still be open after all close attempts');
         return false;
       }

      function isButtonDisabled(button) {
        return !button || button.disabled ||
               button.getAttribute('aria-disabled') === 'true' ||
               button.getAttribute('data-disabled') === 'true';
      }

      function getButtonText(button) {
        return (button?.textContent || '').replace(/\s+/g, ' ').trim();
      }

      function findCreateButton() {
        const buttons = Array.from(document.querySelectorAll('button'));
        const candidates = [];

        for (let btn of buttons) {
          const txt = getButtonText(btn);
          const lowerText = txt.toLowerCase();
          const html = btn.innerHTML || '';
          const iconTexts = Array.from(btn.querySelectorAll('i, .google-symbols'))
            .map(icon => (icon.textContent || icon.innerHTML || '').trim())
            .join(' ');
          const accessibleText = [
            txt,
            btn.getAttribute('aria-label') || '',
            btn.getAttribute('title') || '',
            iconTexts
          ].join(' ').toLowerCase();

          const hasArrow = html.includes('arrow_forward') ||
                           iconTexts.includes('arrow_forward') ||
                           accessibleText.includes('arrow_forward');
          const hasCreate = lowerText.includes('create') ||
                            accessibleText.includes('create') ||
                            btn.querySelector('span')?.textContent?.trim().toLowerCase() === 'create';
          const hasAdd2 = html.includes('add_2') || iconTexts.includes('add_2');
          const isDialog = btn.getAttribute('aria-haspopup') === 'dialog';
          const isMenuButton = btn.getAttribute('aria-haspopup') === 'menu';

          if (!hasArrow || hasAdd2 || isDialog || isMenuButton) continue;
          if (!hasCreate && !lowerText.includes('arrow_forward')) continue;
          if (!isVisibleElement(btn) || isButtonDisabled(btn)) continue;

          const rect = btn.getBoundingClientRect();
          candidates.push({ btn, score: (hasCreate ? 10 : 0) + rect.width + rect.height });
        }

        candidates.sort((a, b) => b.score - a.score);
        return candidates[0]?.btn || null;
      }

      function hasGenerationStarted(beforeTileIds, createBtn, editor) {
        const currentTileIds = getCurrentTileIds();
        const newTileCount = [...currentTileIds].filter(id => !beforeTileIds.has(id)).length;
        if (newTileCount > 0) return true;
        if (createBtn && !document.body.contains(createBtn)) return true;
        if (createBtn && isButtonDisabled(createBtn)) return true;
        if (editor && !getButtonText(editor).trim()) return true;
        const busy = document.querySelector('[aria-busy="true"], [role="progressbar"], [data-testid*="progress"], [class*="progress"], [class*="loading"]');
        return Boolean(busy && isVisibleElement(busy));
      }

      // Send a CDP native click via background.js → chrome.debugger
      // This produces a trusted (isTrusted:true) mouse event that React handles
      async function cdpClick(x, y) {
        if (!hasExtensionRuntime()) return false;
        try {
          const response = await new Promise((resolve) => {
            chrome.runtime.sendMessage({ type: 'CDP_CLICK', x, y }, (res) => {
              if (chrome.runtime.lastError) resolve({ ok: false, error: chrome.runtime.lastError.message });
              else resolve(res || { ok: false, error: 'empty response' });
            });
          });
          return response && response.ok;
        } catch (e) {
          log(`DEBUG: CDP click error: ${e.message}`);
          return false;
        }
      }

      async function clickCreateTarget(element, label) {
        if (!element) return;
        element.scrollIntoView?.({ behavior: 'instant', block: 'center', inline: 'center' });
        await new Promise(r => setTimeout(r, 40));

        const rect = element.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const eventInit = { bubbles: true, cancelable: true, composed: true, clientX: cx, clientY: cy, button: 0, buttons: 1 };
        const pointerInit = { ...eventInit, pointerId: 1, pointerType: 'mouse', isPrimary: true };

        element.focus?.();
        element.dispatchEvent(new PointerEvent('pointerover', pointerInit));
        element.dispatchEvent(new PointerEvent('pointerenter', { ...pointerInit, bubbles: false }));
        element.dispatchEvent(new MouseEvent('mouseover', eventInit));
        element.dispatchEvent(new MouseEvent('mouseenter', { ...eventInit, bubbles: false }));
        element.dispatchEvent(new PointerEvent('pointermove', pointerInit));
        element.dispatchEvent(new MouseEvent('mousemove', eventInit));
        element.dispatchEvent(new PointerEvent('pointerdown', pointerInit));
        element.dispatchEvent(new MouseEvent('mousedown', eventInit));
        await new Promise(r => setTimeout(r, 80));
        element.dispatchEvent(new PointerEvent('pointerup', { ...pointerInit, buttons: 0 }));
        element.dispatchEvent(new MouseEvent('mouseup', { ...eventInit, buttons: 0 }));
        element.dispatchEvent(new MouseEvent('click', { ...eventInit, buttons: 0, detail: 1 }));
        element.click?.();
        log(`DEBUG: Synthetic click sent to ${label}`);
      }

      // Click the "Create" button to send the prompt (after popup closed)
      // Hard timeout of 15 seconds to prevent infinite loops
      async function clickCreateButton(beforeTileIds = getCurrentTileIds(), editor = findEditor()) {
        const TIMEOUT_MS = 15000;
        const startTime = Date.now();
        let attempt = 0;

        const elapsed = () => Date.now() - startTime;
        const timedOut = () => elapsed() >= TIMEOUT_MS;

        while (!timedOut() && isRunning) {
          attempt++;
          try {
            const createBtn = findCreateButton();

            if (!createBtn) {
              log(`DEBUG: Create button not found (attempt ${attempt}, ${Math.round(elapsed()/1000)}s)`);
              await new Promise(r => setTimeout(r, 300));
              continue;
            }

            createBtn.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
            await new Promise(r => setTimeout(r, 150));

            const rect = createBtn.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;

            log(`DEBUG: Create button found (attempt ${attempt}, ${Math.round(elapsed()/1000)}s) at (${Math.round(cx)}, ${Math.round(cy)})`);

            // === Strategy 1: CDP native click (trusted isTrusted:true event) ===
            log(`DEBUG: Trying CDP click at (${Math.round(cx)}, ${Math.round(cy)})...`);
            const cdpOk = await cdpClick(cx, cy);
            if (cdpOk) {
              log(`DEBUG: CDP click dispatched OK`);
              await new Promise(r => setTimeout(r, 800));
              if (!isRunning) break;
              if (hasGenerationStarted(beforeTileIds, createBtn, editor)) {
                log(`>>> Create VERIFIED via CDP click (attempt ${attempt}, ${Math.round(elapsed()/1000)}s)`);
                return true;
              }
            } else {
              log(`DEBUG: CDP click failed, using synthetic fallback`);
            }

            if (timedOut() || !isRunning) break;

            // === Strategy 2: Synthetic click on button ===
            await clickCreateTarget(createBtn, 'Create button');
            await new Promise(r => setTimeout(r, 600));
            if (!isRunning) break;
            if (hasGenerationStarted(beforeTileIds, createBtn, editor)) {
              log(`>>> Create VERIFIED via synthetic click (attempt ${attempt}, ${Math.round(elapsed()/1000)}s)`);
              return true;
            }

            if (timedOut() || !isRunning) break;

            // === Strategy 3: Click child elements (icon, overlay) ===
            const icon = createBtn.querySelector('i, .google-symbols');
            if (icon && !timedOut() && isRunning) {
              await clickCreateTarget(icon, 'Create icon');
              await new Promise(r => setTimeout(r, 400));
              if (!isRunning) break;
              if (hasGenerationStarted(beforeTileIds, createBtn, editor)) {
                log(`>>> Create VERIFIED via icon click (attempt ${attempt})`);
                return true;
              }
            }

            await new Promise(r => setTimeout(r, 200));
          } catch (e) {
            log(`DEBUG: Error clicking Create (attempt ${attempt}): ${e.message}`);
            await new Promise(r => setTimeout(r, 300));
          }
        }

        if (!isRunning) {
          log('>>> Create aborted: stopped by user');
        } else {
          log(`ERROR: Create button click FAILED after ${attempt} attempts (${Math.round(elapsed()/1000)}s timeout)`);
        }
        return false;
      }

      // Get all current image tile IDs on page (data-tile-id attribute)
      function getCurrentTileIds() {
        const ids = new Set();
        const tiles = document.querySelectorAll('[data-tile-id]');
        tiles.forEach(tile => {
          const tileId = tile.getAttribute('data-tile-id');
          if (tileId && tileId.startsWith('fe_id_')) {
            ids.add(tileId);
          }
        });
        return ids;
      }



      // Detect visible failure elements (class-based, language-agnostic)
      function detectFailures() {
        const failureElements = document.querySelectorAll('div[class*="sc-adc89304"], div[class*="AGiNi"]');
        const failures = [];
        failureElements.forEach(el => {
          // Only count if visible (inside an element with data-state="open")
          if (el.closest('[data-state="open"]')) {
            failures.push(el);
          }
        });
        return failures;
      }

      // Wait for generation to complete, monitor new images, detect failures
      async function monitorGeneration(expectedCount, beforeTileIds, settings) {
        const MAX_WAIT_SECONDS = (settings.type === 'video') ? 180 : 180; // 3 min for both
        const POLL_INTERVAL = 1500;
        const COUNTDOWN_UPDATE_INTERVAL = 1000; // send countdown every 1s
        const maxWaitMs = MAX_WAIT_SECONDS * 1000;

        log(`>>> Monitoring generation: expect ${expectedCount} new media items, timeout ${MAX_WAIT_SECONDS}s`);
        log(`DEBUG: Pre-generation snapshot: ${beforeTileIds.size} tile IDs already present`);

        const startTime = Date.now();
        let scanCount = 0;
        let lastSeenCount = 0;
        let consecutiveNoChange = 0;
        let lastCountdownSent = 0;

        // Accumulate all newly seen tile IDs and their image URLs (so we don't lose them if DOM changes)
        const seenTileIds = new Set();
        const foundTiles = []; // array of {tileId, url, element}

        const sendCountdown = (remaining) => {
          safeRuntimeSendMessage({
            action: 'MONITOR_COUNTDOWN',
            remaining: remaining
          });
        };

        const tryAddTile = (tileId) => {
          if (seenTileIds.has(tileId)) return;
          const tile = document.querySelector(`[data-tile-id="${tileId}"]`);
          if (!tile) return;
          // Support both images and videos; match media endpoint regardless of locale prefix in path
          const mediaElement = tile.querySelector('img[src*="media.getMediaUrlRedirect"], video[src*="media.getMediaUrlRedirect"]');
          if (!mediaElement) return;
          const src = mediaElement.src || mediaElement.currentSrc || mediaElement.getAttribute('src');
          // Ensure it's a media redirect URL with a name parameter (works for any locale path)
          if (src && src.includes('media.getMediaUrlRedirect') && src.includes('name=')) {
            seenTileIds.add(tileId);
            foundTiles.push({ tileId, url: src, element: mediaElement, tile: tile });
            log(`DEBUG: Captured new tile ${tileId.substring(0, 12)} → ${src.substring(0, 40)}`);
          }
        };

        const MAX_CONSECUTIVE_NO_CHANGE = 5; // ~7.5s of no changes

        while (Date.now() - startTime < maxWaitMs) {
          if (!isRunning) {
            log('>>> ABORT: Monitoring stopped by user');
            safeRuntimeSendMessage({ action: 'BATCH_COMPLETE' });
            break;
          }

          scanCount++;
          // Get current tile IDs
          const currentTileIds = getCurrentTileIds();
          const newTileIds = new Set([...currentTileIds].filter(id => !beforeTileIds.has(id)));

          // Accumulate any new tiles we haven't seen before
          newTileIds.forEach(tryAddTile);

          const seenCount = seenTileIds.size;

          // Send countdown update every second
          const elapsed = Date.now() - startTime;
          const remaining = Math.max(0, Math.ceil((maxWaitMs - elapsed) / 1000));
          if (remaining !== lastCountdownSent) {
            sendCountdown(remaining);
            lastCountdownSent = remaining;
          }

          // Check for failures
          const failures = detectFailures();
          if (failures.length > 0) {
            log(`WARN: Detected ${failures.length} failure element(s)`);
          }

          // Log progress
          if (seenCount !== lastSeenCount) {
            log(`>>> Generation progress: ${seenCount}/${expectedCount} new tiles detected`);
            consecutiveNoChange = 0;
          } else {
            consecutiveNoChange++;
          }
          lastSeenCount = seenCount;

          // Success condition: we have at least expectedCount new tiles
          if (seenCount >= expectedCount) {
            log(`>>> SUCCESS: All ${expectedCount} tiles appeared`);
            safeRuntimeSendMessage({ action: 'BATCH_COMPLETE' });
            return { status: 'complete', found: seenCount, failed: failures.length, foundTiles };
          }

          // Smart early exit: some images + no new + failures → partial
          if (seenCount > 0 && consecutiveNoChange >= MAX_CONSECUTIVE_NO_CHANGE && failures.length > 0) {
            log(`>>> PARTIAL: ${seenCount} tiles found, ${failures.length} failures, no new after ${MAX_CONSECUTIVE_NO_CHANGE} polls`);
            safeRuntimeSendMessage({ action: 'BATCH_COMPLETE' });
            return { status: 'partial', found: seenCount, failed: failures.length, foundTiles };
          }

          // Timeout
          if (Date.now() - startTime >= maxWaitMs) {
            if (seenCount > 0) {
              log(`>>> TIMEOUT: Found ${seenCount}/${expectedCount} (${failures.length} failures)`);
              safeRuntimeSendMessage({ action: 'BATCH_COMPLETE' });
              return { status: 'partial', found: seenCount, failed: failures.length, foundTiles };
            } else {
              log('>>> TIMEOUT: No new tiles detected');
              safeRuntimeSendMessage({ action: 'BATCH_COMPLETE' });
              return { status: 'failed', found: 0, failed: failures.length, foundTiles: [] };
            }
          }

          await new Promise(r => setTimeout(r, POLL_INTERVAL));
        }

        safeRuntimeSendMessage({ action: 'BATCH_COMPLETE' });
        return { status: 'timeout', found: seenTileIds.size, failed: 0, foundTiles };
      }

      function normalizeDownloadQuality(settings) {
        const quality = (settings.downloadQuality || 'default').toString().trim();
        if (!quality || quality.toLowerCase() === 'default') return 'default';
        return quality;
      }

      function isDefaultDownloadQuality(settings) {
        const quality = normalizeDownloadQuality(settings);
        if (quality === 'default') return true;
        if (settings.type === 'image' && quality === '1K') return true;
        if (settings.type === 'video' && quality === '720p') return true;
        return false;
      }

      function findMenuItemByText(text, root = document) {
        const target = text.toLowerCase();
        const items = root.querySelectorAll('button[role="menuitem"], div[role="menuitem"]');
        for (let item of items) {
          if (!isVisibleElement(item)) continue;
          const itemText = (item.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
          if (itemText.includes(target)) return item;
        }
        return null;
      }

      function getTileInteractionRoots(tile) {
        const roots = [];
        let current = tile;
        for (let depth = 0; current && depth < 12; depth++) {
          if (current instanceof HTMLElement) roots.push(current);
          current = current.parentElement;
        }
        return roots;
      }

      function getTileHoverTargets(tileInfo, tile) {
        const targets = [];
        const media = tileInfo.element || tile.querySelector('img, video');
        if (media) targets.push({ element: media, label: 'generated media element' });
        targets.push({ element: tile, label: `generated tile ${tile.getAttribute('data-tile-id') || ''}`.trim() });

        const draggable = tile.closest('[role="button"][aria-roledescription="draggable"]');
        if (draggable) targets.push({ element: draggable, label: 'draggable tile wrapper' });

        const roots = getTileInteractionRoots(tile);
        roots.slice(1, 5).forEach((root, index) => {
          targets.push({ element: root, label: `tile ancestor ${index + 1}` });
        });

        return targets.filter((target, index, arr) =>
          target.element && arr.findIndex(other => other.element === target.element) === index
        );
      }

      function isTileMoreButton(button) {
        const text = (button.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
        const html = button.innerHTML || '';
        if (!(text.includes('more') || html.includes('more_vert'))) return false;
        if (text.includes('more options')) return false;
        if (button.closest('nav')) return false;
        const toolbar = button.closest('[role="toolbar"][aria-orientation="horizontal"]');
        if (toolbar) return true;
        return button.getAttribute('aria-haspopup') === 'menu' && html.includes('more_vert');
      }

      function findMoreButtonForTile(tile) {
        const roots = getTileInteractionRoots(tile);
        const tileRect = tile.getBoundingClientRect();
        const tileCenterX = tileRect.left + tileRect.width / 2;
        const tileCenterY = tileRect.top + tileRect.height / 2;
        const candidates = [];

        for (let root of roots) {
          const buttons = Array.from(root.querySelectorAll('button'));
          for (let btn of buttons) {
            if (!isVisibleElement(btn) || !isTileMoreButton(btn)) continue;
            const rect = btn.getBoundingClientRect();
            const insideExpandedTileArea = rect.left >= tileRect.left - 48 &&
                                           rect.right <= tileRect.right + 48 &&
                                           rect.top >= tileRect.top - 48 &&
                                           rect.bottom <= tileRect.bottom + 48;
            if (!insideExpandedTileArea && !btn.closest('[role="toolbar"]')) continue;
            candidates.push({ button: btn, distance: distanceBetweenElements(tile, btn), root });
          }
        }

        const documentButtons = Array.from(document.querySelectorAll('button'));
        for (let btn of documentButtons) {
          if (!isVisibleElement(btn) || !isTileMoreButton(btn)) continue;
          const rect = btn.getBoundingClientRect();
          const nearTile = rect.left >= tileRect.left - 80 &&
                           rect.right <= tileRect.right + 80 &&
                           rect.top >= tileRect.top - 80 &&
                           rect.bottom <= tileRect.bottom + 80;
          if (nearTile) candidates.push({ button: btn, distance: Math.hypot((rect.left + rect.width / 2) - tileCenterX, (rect.top + rect.height / 2) - tileCenterY), root: document });
        }

        candidates.sort((a, b) => a.distance - b.distance);
        const best = candidates[0];
        if (best) {
          const text = (best.button.textContent || '').replace(/\s+/g, ' ').trim();
          const rootLabel = best.root === document ? 'document-near-tile' : `${best.root.tagName.toLowerCase()}${best.root.getAttribute('data-tile-id') ? '[data-tile-id]' : ''}`;
          log(`>>> More button found in ${rootLabel}, distance=${Math.round(best.distance)}, text="${text}"`);
          return best.button;
        }

        log('DEBUG: Tile More candidate count=0');
        return null;
      }

      async function revealTileToolbar(tileInfo, tile) {
        const targets = getTileHoverTargets(tileInfo, tile);
        log(`>>> Revealing tile toolbar via ${targets.length} hover target(s)`);
        for (let target of targets) {
          hoverElement(target.element, target.label);
          await new Promise(r => setTimeout(r, 350));
          const moreButton = findMoreButtonForTile(tile);
          if (moreButton) return moreButton;
        }
        await new Promise(r => setTimeout(r, 800));
        return findMoreButtonForTile(tile);
      }

      async function waitForOpenMenuCount(minCount, timeoutMs, label) {
        const started = Date.now();
        while (Date.now() - started < timeoutMs) {
          const menus = Array.from(document.querySelectorAll('div[role="menu"][data-state="open"]')).filter(isVisibleElement);
          log(`DEBUG: ${label}: open visible menus=${menus.length}`);
          if (menus.length >= minCount) return menus;
          await new Promise(r => setTimeout(r, 200));
        }
        return Array.from(document.querySelectorAll('div[role="menu"][data-state="open"]')).filter(isVisibleElement);
      }

      async function clickDownloadFromTileMenu(tileInfo, settings) {
        const quality = normalizeDownloadQuality(settings);
        if (isDefaultDownloadQuality(settings)) {
          return false;
        }

        const tile = tileInfo.tile || tileInfo.element?.closest('[data-tile-id]');
        if (!tile) {
          log('WARN: Cannot use Flow download menu; tile element not found');
          return false;
        }

        log(`>>> Using Flow download menu for ${settings.type} quality ${quality}`);
        const moreButton = await revealTileToolbar(tileInfo, tile);
        if (!moreButton) {
          log('ERROR: More button not found after hover; not downloading default URL for non-default quality');
          return false;
        }

        log('>>> Clicking tile More button');
        dispatchMouseSequence(moreButton, 'tile More button');
        await waitForOpenMenuCount(1, 2500, 'after More click');

        const openMenus = () => Array.from(document.querySelectorAll('div[role="menu"][data-state="open"]')).filter(isVisibleElement);
        let downloadItem = null;
        for (let attempt = 0; attempt < 10; attempt++) {
          const menus = openMenus();
          log(`DEBUG: Looking for Download menu item (attempt ${attempt + 1}), open menus=${menus.length}`);
          for (let menu of menus) {
            downloadItem = findMenuItemByText('download', menu);
            if (downloadItem) break;
          }
          if (downloadItem) break;
          await new Promise(r => setTimeout(r, 200));
        }

        if (!downloadItem) {
          log('ERROR: Download menu item not found after clicking More; not downloading default URL for non-default quality');
          await closePopupMenu();
          return false;
        }

        log('>>> Hovering Download menu item to open quality submenu');
        hoverElement(downloadItem, 'Download menu item');
        await waitForOpenMenuCount(2, 2500, 'after Download hover');

        let qualityItem = null;
        for (let attempt = 0; attempt < 12; attempt++) {
          const menus = openMenus();
          log(`DEBUG: Looking for quality "${quality}" (attempt ${attempt + 1}), open menus=${menus.length}`);
          for (let menu of menus) {
            qualityItem = findMenuItemByText(quality, menu);
            if (qualityItem) break;
          }
          if (qualityItem) break;
          await new Promise(r => setTimeout(r, 200));
        }

        if (!qualityItem) {
          log(`ERROR: Download quality "${quality}" not found; not downloading default URL for non-default quality`);
          await closePopupMenu();
          return false;
        }

        const disabled = qualityItem.getAttribute('aria-disabled') === 'true' || qualityItem.disabled;
        if (disabled) {
          log(`ERROR: Download quality "${quality}" is disabled; not downloading default URL for non-default quality`);
          await closePopupMenu();
          return false;
        }

        log(`>>> Clicking Download quality ${quality}`);
        dispatchMouseSequence(qualityItem, `Download quality ${quality}`);
        await new Promise(r => setTimeout(r, 1000));
        log(`>>> Flow download menu click completed for quality ${quality}`);
        return true;
      }

      // Download a single image via background script (chrome.downloads)
      function downloadImage(url, promptIndex, batchIndex, settings) {
        const ext = (settings.type === 'video') ? 'mp4' : 'jpg';
        const prefix = (settings.type === 'video') ? 'Flow_Video' : 'Flow_Image';

        // Generate prompt words for filename (first 5 words, sanitized)
        const promptWords = ''; // Could enhance if we have access to current prompt text

        safeRuntimeSendMessage({
          type: 'DOWNLOAD_CONTENT',
          url: url,
          promptIndex: promptIndex,
          extension: ext,
          prefix: prefix,
          promptWords: promptWords,
          batchIndex: batchIndex
        });
      }

      function getGlobalDelayMs(settings) {
        const delayMs = Number(settings?.globalDelayMs);
        if (Number.isFinite(delayMs) && delayMs >= 0) return Math.round(delayMs);

        const delaySeconds = Number(settings?.globalDelaySeconds);
        if (Number.isFinite(delaySeconds) && delaySeconds >= 0) return Math.round(delaySeconds * 1000);

        return 5000;
      }

      async function applyDownloadCooldown(settings, currentNumber, totalNumber) {
        const delayMs = getGlobalDelayMs(settings);
        if (delayMs <= 0 || currentNumber >= totalNumber || !isRunning) return;

        const seconds = Math.ceil(delayMs / 1000);
        log(`>>> Cooldown ${seconds}s before next download`);
        safeRuntimeSendMessage({ action: 'DOWNLOAD_COOLDOWN_START', seconds });
        await new Promise(r => setTimeout(r, delayMs));
        safeRuntimeSendMessage({ action: 'DOWNLOAD_COOLDOWN_END' });
      }

      // Process batch: monitor, detect, download
      async function processBatch(promptIndex, batchCount, beforeTileIds, settings) {
        log(`>>> Starting batch processing: expect ${batchCount} media items for prompt ${promptIndex + 1}`);

        // Step 1: Monitor generation (after Create button clicked by caller)
        const monitorResult = await monitorGeneration(batchCount, beforeTileIds, settings);

        // Use the accumulated foundTiles (captured at first sight, even if DOM later changes)
        const foundTiles = monitorResult.foundTiles;
        const foundCount = foundTiles.length;

        if (foundCount === 0) {
          log(`>>> FAILED: No media detected for prompt ${promptIndex + 1}`);
          return { success: false, downloaded: 0, message: 'No media detected' };
        }

        log(`>>> Batch monitoring complete: ${monitorResult.status}, captured ${foundCount} tile(s) during generation`);

        // Step 2: Download images from captured tiles (up to batchCount)
        const maxToTake = Math.min(batchCount, foundCount);
        let downloaded = 0;
        for (let i = 0; i < maxToTake && isRunning; i++) {
          const tileInfo = foundTiles[i];
          log(`>>> Downloading media ${i + 1}/${maxToTake}: ${tileInfo.url.substring(0, 60)}`);
          const usedFlowMenu = await clickDownloadFromTileMenu(tileInfo, settings);
          if (usedFlowMenu) {
            downloaded++;
          } else if (isDefaultDownloadQuality(settings)) {
            log('>>> Default quality selected; downloading captured media URL');
            downloadImage(tileInfo.url, promptIndex, i, settings);
            downloaded++;
          } else {
            log(`ERROR: Failed to download requested quality "${normalizeDownloadQuality(settings)}"; skipped default URL fallback`);
          }
          // Configurable cooldown between downloads
          await applyDownloadCooldown(settings, i + 1, maxToTake);
        }

        return {
          success: monitorResult.status === 'complete' && downloaded >= batchCount,
          downloaded: downloaded,
          message: `${monitorResult.status}: ${foundCount} captured, ${downloaded} downloaded, ${monitorResult.failed} failed`
        };
      }



      async function processPrompt(prompt, settings) {
        try {
          // Check stop flag
          if (!isRunning) {
            log('>>> ABORT: Process stopped by user (pre-check)');
            return { status: 'stopped', message: 'Stopped by user' };
          }

          await ensureFlowProjectReady();

          log(`>>> START: "${prompt}"`);
          log(`>>> Settings: type=${settings.type}, ratio=${settings.ratio}, batch=x${settings.batch}, downloadQuality=${settings.downloadQuality || 'default'}, cooldown=${getGlobalDelayMs(settings) / 1000}s`);

          let editor = null;
          for (let i = 0; i < 20; i++) {
            editor = findEditor();
            if (editor) break;
            await new Promise(r => setTimeout(r, 100));
          }
          if (!editor) throw new Error('Editor not found');
          log('Editor found');

          // Focus editor
          editor.focus();
          await new Promise(r => setTimeout(r, 150));

          // Get editor content element (works for empty or populated editor)
          let pEl = getParagraph(editor);

           // If no paragraph found, try to create one by focusing first
           if (!pEl) {
             log('WARN: No paragraph found, trying to focus blank editor');
             editor.scrollIntoView({ behavior: 'instant', block: 'center' });
             await new Promise(r => setTimeout(r, 200));

             pEl = getParagraph(editor);
             if (!pEl) {
               log('WARN: Still no paragraph, typing directly into editor');
               const sel = window.getSelection();
               const range = document.createRange();
               range.selectNodeContents(editor);
               sel.removeAllRanges();
               sel.addRange(range);

               const beforeInput = new InputEvent('beforeinput', {
                 inputType: 'insertText',
                 data: prompt,
                 bubbles: true,
                 cancelable: true,
                 isComposing: false
               });
               editor.dispatchEvent(beforeInput);
               await new Promise(r => setTimeout(r, 800));

               // Verify direct typing succeeded
               if (!editor.textContent || !editor.textContent.trim().includes(prompt.trim())) {
                 throw new Error('Direct typing failed: prompt text not found in editor');
               }

               log('>>> SUCCESS (direct editor insert)');
               // UI automation
               const clicked = await clickVariantButton();
               if (clicked) {
                 await selectModeTab(settings.type, settings.ratio, settings.batch);
                 await closePopupMenu();
                 const beforeTileIds = getCurrentTileIds();
                 const createClicked = await clickCreateButton(beforeTileIds, editor);
                 if (createClicked && isRunning) {
                   const batchResult = await processBatch(0, parseInt(settings.batch), beforeTileIds, settings);
                   log(`>>> Batch result: ${batchResult.message}`);
                   return {
                     status: batchResult.downloaded === 0 ? 'failed' : (batchResult.success ? 'success' : 'partial'),
                     message: batchResult.message,
                     downloaded: batchResult.downloaded,
                     expected: parseInt(settings.batch)
                   };
                 } else if (!isRunning) {
                   return { status: 'stopped', message: 'Stopped during batch processing' };
                 } else {
                   return { status: 'failed', message: 'Failed to click Create button' };
                 }
               }
               // If UI interaction failed to start, still consider prompt typed
               return { status: 'success', message: 'Prompt typed (direct, UI start failed)' };
             }
             // If pEl became available after focus attempt, fall through to main verification
           }

          log(`Paragraph: ${pEl.tagName}, innerHTML before: ${pEl.innerHTML.substring(0, 50)}`);

          // Select all content in paragraph
          const range = document.createRange();
          range.selectNodeContents(pEl);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
          log('Selection set on paragraph (select all)');
          await new Promise(r => setTimeout(r, 100));

          // Re-acquire fresh paragraph (Slate may replace DOM)
          let freshP = getParagraph(editor);
          if (!freshP) {
            log('WARN: Fresh paragraph not found, using original');
            freshP = pEl;
          }
          log(`Fresh paragraph acquired: ${freshP.tagName}`);

          // Re-select fresh paragraph
          const freshRange = document.createRange();
          freshRange.selectNodeContents(freshP);
          sel.removeAllRanges();
          sel.addRange(freshRange);
          await new Promise(r => setTimeout(r, 50));

          // Dispatch beforeinput
          const beforeInput = new InputEvent('beforeinput', {
            inputType: 'insertText',
            data: prompt,
            bubbles: true,
            cancelable: true,
            isComposing: false
          });

          const canceled = !freshP.dispatchEvent(beforeInput);
          log(`beforeinput: canceled=${canceled}, proceeding regardless`);

          // Wait for React render
          await new Promise(r => setTimeout(r, 800));

          // Verification with retry
          let verifyP = getParagraph(editor);
          if (!verifyP) {
            log('WARN: Paragraph element gone after insert, retrying...');
            await new Promise(r => setTimeout(r, 400));
            verifyP = getParagraph(editor);
          }

           if (!verifyP) {
             log('WARN: Could not find paragraph for verification, assuming success');
             if (editor.textContent && editor.textContent.trim().includes(prompt.trim())) {
               log('>>> SUCCESS (verified via editor.textContent)');
               const clicked = await clickVariantButton();
                if (clicked) {
                  await selectModeTab(settings.type, settings.ratio, settings.batch);
                  await closePopupMenu();
                  const beforeTileIds = getCurrentTileIds();
                  const createClicked = await clickCreateButton(beforeTileIds, editor);
                  if (createClicked && isRunning) {
                    const batchResult = await processBatch(0, parseInt(settings.batch), beforeTileIds, settings);
                    log(`>>> Batch result: ${batchResult.message}`);
                    return {
                      status: batchResult.downloaded === 0 ? 'failed' : (batchResult.success ? 'success' : 'partial'),
                      message: batchResult.message,
                      downloaded: batchResult.downloaded,
                      expected: parseInt(settings.batch)
                    };
                  }
                }
               return { status: 'success', message: 'Prompt typed (editor content check)' };
             }
             throw new Error('Cannot verify: paragraph element missing and editor.textContent does not contain prompt');
           }

          const actual = verifyP.textContent.trim();
          log(`VERIFY: expected="${prompt}" actual="${actual}"`);

          if (actual !== prompt.trim() && !actual.includes(prompt.trim()) && !prompt.trim().includes(actual)) {
            log(`WARN: Text may not fully match, but continuing`);
          }

          log('>>> SUCCESS');

          // Check stop before UI interaction
          if (!isRunning) {
            log('>>> ABORT: Process stopped by user (before UI)');
            return { status: 'stopped', message: 'Stopped by user' };
          }

            // Click variant settings button to open popup menu
            const clicked = await clickVariantButton();
              if (clicked) {
                // Select mode tab (image/video), ratio, and batch count
                await selectModeTab(settings.type, settings.ratio, settings.batch);
                // Close popup menu to avoid interfering with next prompt
                await closePopupMenu();

                // Capture pre-generation snapshot of tile IDs BEFORE clicking Create
                const beforeTileIds = getCurrentTileIds();

                // Click Create button to send prompt and then monitor/download
                const createClicked = await clickCreateButton(beforeTileIds, editor);
                if (createClicked && isRunning) {
                  const batchResult = await processBatch(0, parseInt(settings.batch), beforeTileIds, settings);
                  log(`>>> Batch result: ${batchResult.message}`);
                  return {
                    status: batchResult.downloaded === 0 ? 'failed' : (batchResult.success ? 'success' : 'partial'),
                    message: batchResult.message,
                    downloaded: batchResult.downloaded,
                    expected: parseInt(settings.batch)
                  };
                } else if (!isRunning) {
                  return { status: 'stopped', message: 'Stopped during batch processing' };
                } else {
                  return { status: 'failed', message: 'Failed to click Create button' };
                }
              }

          return { status: 'success', message: 'Prompt typed' };
        } catch (err) {
          log(`>>> ERROR: ${err.message}`);
          return { status: 'failed', message: err.message };
        }
      }

      if (hasExtensionMessageListener()) {
        chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
          if (msg.action === 'PING') {
            sendResponse({ status: 'ok' });
            return true;
          }
          if (msg.action === 'STOP') {
            isRunning = false;
            log('>>> STOP received — aborting');
            sendResponse({ status: 'stopped' });
            return true;
          }
          if (msg.action === 'CREATE_PROJECT') {
            if (!isRunning) {
              sendResponse({ status: 'stopped', message: 'Process stopped by user' });
              return true;
            }
            if (isFlowProjectPage()) {
              sendResponse({ status: 'success', message: 'Already on Flow project page' });
              return true;
            }
            clickNewProjectFromLanding()
              .then(clicked => sendResponse(clicked
                ? { status: 'success', message: 'New project clicked' }
                : { status: 'failed', message: 'New project button not found' }))
              .catch(e => sendResponse({ status: 'failed', message: e.message }));
            return true;
          }
          if (msg.action === 'PROCESS_PROMPT') {
            // Check isRunning before starting
            if (!isRunning) {
              sendResponse({ status: 'stopped', message: 'Process stopped by user' });
              return true;
            }
            processPrompt(msg.payload.prompt, msg.payload.settings)
              .then(r => sendResponse(r))
              .catch(e => sendResponse({ status: 'failed', message: e.message }));
            return true;
          }
        });
      } else {
        console.warn('[AFB] chrome.runtime.onMessage unavailable; content script loaded outside extension context.');
      }

     log('Content script loaded and ready');
  })();
}
