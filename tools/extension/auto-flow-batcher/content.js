// Auto Flow Batcher - Content Script vPURE
// No DOM building, no extra events — just clear → selection → beforeinput

if (window.top !== window.self) {
} else {
  (function () {
    // Guard: only run on Flow editor pages, not the project list/home
    const isEditorPage = location.href.includes('/labs.google/fx/tools/flow/project/') ||
                        location.href.includes('/labs.google/fx/id/tools/flow/project/');
    if (!isEditorPage) {
      console.log('[AFB] Not on Flow editor page, skipping content script');
      return;
    }

    let isRunning = true;

     function log(msg) {
       try {
         chrome.runtime.sendMessage({ action: "LOG_FROM_CONTENT", message: msg }).catch(() => {});
       } catch (e) {}
       console.log('[AFB]', msg);
     }

    function findEditor() {
      return document.querySelector('[data-slate-editor="true"]') ||
             document.querySelector('[role="textbox"][contenteditable="true"]') ||
             document.querySelector('.sc-522e4d41-5.gihCJr');
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
                  if (txt.toLowerCase() === batchKey.toLowerCase()) {
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
                  if (txt.toLowerCase() === batchKey.toLowerCase()) {
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

      // Click the "Create" button to send the prompt (after popup closed)
      async function clickCreateButton() {
        const MAX_RETRIES = 15;
        const RETRY_DELAY = 200;

        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
          try {
            // Find Create button: MUST have arrow_forward icon, NOT add_2 (which is for reference upload)
            // Also exclude buttons with aria-haspopup="dialog"
            const buttons = document.querySelectorAll('button');
            let createBtn = null;

            // First pass: look for arrow_forward icon specifically
            for (let btn of buttons) {
              const txt = (btn.textContent || '').trim();
              const hasArrow = btn.innerHTML.includes('arrow_forward') ||
                               btn.querySelector('i[font-size="1.25rem"]')?.innerHTML?.includes('arrow_forward') ||
                               (btn.querySelector('.google-symbols') && btn.textContent.trim() === '');
              const hasAdd2 = btn.innerHTML.includes('add_2') ||
                              btn.querySelector('i[font-size="1.35rem"]')?.innerHTML?.includes('add_2');
              const isDialog = btn.getAttribute('aria-haspopup') === 'dialog';

              // Skip reference upload button (add_2 + aria-haspopup="dialog")
              if (hasAdd2 || isDialog) {
                continue;
              }

              if ((txt.includes('Create') || txt === '') && hasArrow) {
                createBtn = btn;
                log(`DEBUG: Found Create button by arrow_forward icon (attempt ${attempt})`);
                break;
              }
            }

            // Fallback: try known class pattern for Create button (NOT dialog)
            if (!createBtn) {
              // The Create button typically has: sc-e8425ea6-0 gLXNUV ... ewQKQI eaSocK jaSpBd
              // The dialog upload button has: ... AyIIS hxYNKs
              const allButtons = document.querySelectorAll('button.ewQKQI:not(.AyIIS)');
              for (let btn of allButtons) {
                const hasArrow = btn.innerHTML.includes('arrow_forward');
                const hasAdd2 = btn.innerHTML.includes('add_2');
                if (hasArrow && !hasAdd2) {
                  createBtn = btn;
                  log(`DEBUG: Found Create button by class+arrow pattern (attempt ${attempt})`);
                  break;
                }
              }
            }

            if (!createBtn) {
              await new Promise(r => setTimeout(r, RETRY_DELAY));
              continue;
            }

            const style = window.getComputedStyle(createBtn);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0' || createBtn.disabled) {
              await new Promise(r => setTimeout(r, RETRY_DELAY));
              continue;
            }

            const rect = createBtn.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;

            // Dispatch pointer events
            createBtn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0, pointerType: 'mouse' }));
            await new Promise(r => setTimeout(r, 50));
            createBtn.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0, pointerType: 'mouse' }));
            await new Promise(r => setTimeout(r, 50));
            createBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));

            log(`>>> Create button clicked (attempt ${attempt})`);
            await new Promise(r => setTimeout(r, 500));

            // Verify: button still visible but don't require state change
            const stillExists = document.body.contains(createBtn);
            if (stillExists) {
              log(`DEBUG: Create button still exists after click`);
            }

            return true;
          } catch (e) {
            log(`DEBUG: Error clicking Create button (attempt ${attempt}): ${e.message}`);
            await new Promise(r => setTimeout(r, RETRY_DELAY));
          }
        }

        log('WARN: Create button not found/clicked after retries');
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



      // Detect failure elements (Gagal/Error messages)
      function detectFailures() {
        const failures = [];
        const failureElements = document.querySelectorAll('div[class*="sc-adc89304"], div[class*="AGiNi"]');
        failureElements.forEach(el => {
          const text = el.textContent || '';
          if (text.includes('Gagal') || text.includes('error') || text.includes('Error') || text.includes('Maaf, terjadi error')) {
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
          chrome.runtime.sendMessage({
            action: 'MONITOR_COUNTDOWN',
            remaining: remaining
          }).catch(() => {});
        };

        const tryAddTile = (tileId) => {
          if (seenTileIds.has(tileId)) return;
          const tile = document.querySelector(`[data-tile-id="${tileId}"]`);
          if (!tile) return;
          // Support both images and videos
          const mediaElement = tile.querySelector('img[src*="/fx/api/trpc/media.getMediaUrlRedirect"], video[src*="/fx/api/trpc/media.getMediaUrlRedirect"]');
          if (!mediaElement) return;
          const src = mediaElement.src || mediaElement.currentSrc || mediaElement.getAttribute('src');
          if (src && src.includes('/fx/api/trpc/media.getMediaUrlRedirect?name=')) {
            seenTileIds.add(tileId);
            foundTiles.push({ tileId, url: src, element: mediaElement, tile: tile });
            log(`DEBUG: Captured new tile ${tileId.substring(0, 12)} → ${src.substring(0, 40)}`);
          }
        };

        const MAX_CONSECUTIVE_NO_CHANGE = 5; // ~7.5s of no changes

        while (Date.now() - startTime < maxWaitMs) {
          if (!isRunning) {
            log('>>> ABORT: Monitoring stopped by user');
            chrome.runtime.sendMessage({ action: 'BATCH_COMPLETE' }).catch(() => {});
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
            chrome.runtime.sendMessage({ action: 'BATCH_COMPLETE' }).catch(() => {});
            return { status: 'complete', found: seenCount, failed: failures.length, foundTiles };
          }

          // Smart early exit: some images + no new + failures → partial
          if (seenCount > 0 && consecutiveNoChange >= MAX_CONSECUTIVE_NO_CHANGE && failures.length > 0) {
            log(`>>> PARTIAL: ${seenCount} tiles found, ${failures.length} failures, no new after ${MAX_CONSECUTIVE_NO_CHANGE} polls`);
            chrome.runtime.sendMessage({ action: 'BATCH_COMPLETE' }).catch(() => {});
            return { status: 'partial', found: seenCount, failed: failures.length, foundTiles };
          }

          // Timeout
          if (Date.now() - startTime >= maxWaitMs) {
            if (seenCount > 0) {
              log(`>>> TIMEOUT: Found ${seenCount}/${expectedCount} (${failures.length} failures)`);
              chrome.runtime.sendMessage({ action: 'BATCH_COMPLETE' }).catch(() => {});
              return { status: 'partial', found: seenCount, failed: failures.length, foundTiles };
            } else {
              log('>>> TIMEOUT: No new tiles detected');
              chrome.runtime.sendMessage({ action: 'BATCH_COMPLETE' }).catch(() => {});
              return { status: 'failed', found: 0, failed: failures.length, foundTiles: [] };
            }
          }

          await new Promise(r => setTimeout(r, POLL_INTERVAL));
        }

        chrome.runtime.sendMessage({ action: 'BATCH_COMPLETE' }).catch(() => {});
        return { status: 'timeout', found: seenTileIds.size, failed: 0, foundTiles };
      }

      // Download a single image via background script (chrome.downloads)
      function downloadImage(url, promptIndex, batchIndex, settings) {
        const ext = (settings.type === 'video') ? 'mp4' : 'jpg';
        const prefix = (settings.type === 'video') ? 'Flow_Video' : 'Flow_Image';

        // Generate prompt words for filename (first 5 words, sanitized)
        const promptWords = ''; // Could enhance if we have access to current prompt text

        chrome.runtime.sendMessage({
          type: 'DOWNLOAD_CONTENT',
          url: url,
          promptIndex: promptIndex,
          extension: ext,
          prefix: prefix,
          promptWords: promptWords,
          batchIndex: batchIndex
        }).catch(err => {
          log(`ERROR: Failed to send download message: ${err.message}`);
        });
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
          downloadImage(tileInfo.url, promptIndex, i, settings);
          downloaded++;
          // Small delay between downloads
          await new Promise(r => setTimeout(r, 500));
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

          log(`>>> START: "${prompt}"`);

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
                 const createClicked = await clickCreateButton();
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
                  const createClicked = await clickCreateButton();
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
                const createClicked = await clickCreateButton();
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

    log('Content script loaded and ready');
  })();
}
