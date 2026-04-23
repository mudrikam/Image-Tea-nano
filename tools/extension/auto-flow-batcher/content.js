// Auto Flow Batcher - Content Script vPURE
// No DOM building, no extra events — just clear → selection → beforeinput

if (window.top !== window.self) {
} else {
   (function () {
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

     function getParagraph(editor) {
       return editor.querySelector('p[data-slate-node="element"]') ||
              editor.querySelector('p');
     }

     // Click the variant settings button (opens popup menu) — robust selector
     async function clickVariantButton() {
       const MAX_RETRIES = 20;
       const RETRY_DELAY = 400;

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
           await new Promise(r => setTimeout(r, 100));

           const pointerUp = new PointerEvent('pointerup', {
             bubbles: true,
             cancelable: true,
             clientX: centerX,
             clientY: centerY,
             button: 0,
             pointerType: 'mouse'
           });
           button.dispatchEvent(pointerUp);
           await new Promise(r => setTimeout(r, 100));

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
           await new Promise(r => setTimeout(r, 2000));

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

     // Select mode tab (Image/Video) inside the opened popup menu
     async function selectModeTab(mode) {
       const MAX_RETRIES = 15;
       const RETRY_DELAY = 300;

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

           let targetTab = null;
           for (let tab of tabs) {
             const txt = (tab.textContent || '').trim().toLowerCase();
             if (txt.includes(mode.toLowerCase())) {
               targetTab = tab;
               log(`DEBUG: Found ${mode} tab: "${txt}"`);
               break;
             }
           }

           if (!targetTab) {
             await new Promise(r => setTimeout(r, RETRY_DELAY));
             continue;
           }

           // If already selected, skip
           if (targetTab.getAttribute('aria-selected') === 'true') {
             log(`>>> Mode tab "${mode}" already selected`);
             return true;
           }

           // Safety: visible?
           const style = window.getComputedStyle(targetTab);
           if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
             await new Promise(r => setTimeout(r, RETRY_DELAY));
             continue;
           }

           // Click with mouse events
           targetTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
           await new Promise(r => setTimeout(r, 150));
           targetTab.focus();
           await new Promise(r => setTimeout(r, 100));

           const rect = targetTab.getBoundingClientRect();
           const cx = rect.left + rect.width / 2;
           const cy = rect.top + rect.height / 2;

           targetTab.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
           await new Promise(r => setTimeout(r, 100));
           targetTab.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));
           await new Promise(r => setTimeout(r, 100));
           targetTab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }));

           log(`>>> Mode tab "${mode}" clicked (attempt ${attempt})`);
           await new Promise(r => setTimeout(r, 500));

           // Verify
           if (targetTab.getAttribute('aria-selected') === 'true') {
             log(`>>> Mode confirmed: ${mode}`);
             return true;
           }
         } catch (e) {
           await new Promise(r => setTimeout(r, RETRY_DELAY));
         }
       }

       log(`WARN: Mode tab "${mode}" not selected after retries`);
       return false;
     }

      // Close the popup menu — uses double-click on trigger, then click outside, then Escape
      async function closePopupMenu() {
        const MAX_RETRIES = 8;
        const RETRY_DELAY = 300;

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
            await new Promise(r => setTimeout(r, 150));
            // Second click (toggle)
            doClick(button);
            await new Promise(r => setTimeout(r, 600));

            // Verify
            const newState = button.getAttribute('data-state');
            const newExpanded = button.getAttribute('aria-expanded');
            const controlsId = button.getAttribute('aria-controls');
            let popupGone = true;
            if (controlsId) {
              const popup = document.getElementById(controlsId);
              if (popup) {
                const style = window.getComputedStyle(popup);
                popupGone = style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0' || style.pointerEvents === 'none';
              }
            }

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
            await new Promise(r => setTimeout(r, 600));

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
            await new Promise(r => setTimeout(r, 600));

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

      async function processPrompt(prompt, settings) {
        try {
          // Check stop flag
          if (!isRunning) {
            log('>>> ABORT: Process stopped by user (pre-check)');
            return { status: 'stopped', message: 'Stopped by user' };
          }

          log(`>>> START: "${prompt}"`);

         let editor = null;
         for (let i = 0; i < 40; i++) {
           editor = findEditor();
           if (editor) break;
           await new Promise(r => setTimeout(r, 150));
         }
         if (!editor) throw new Error('Editor not found');
         log('Editor found');

         // Focus editor
         editor.focus();
         await new Promise(r => setTimeout(r, 300));

         // Select All on the fresh paragraph (no delete/clear at all)
         const pEl = getParagraph(editor);
         if (!pEl) throw new Error('Paragraph not found');
         log(`Paragraph: ${pEl.tagName}, innerHTML before: ${pEl.innerHTML.substring(0, 50)}`);

          const range = document.createRange();
          range.selectNodeContents(pEl);
          const sel = window.getSelection();
         sel.removeAllRanges();
         sel.addRange(range);
         log('Selection set on paragraph (select all)');
         await new Promise(r => setTimeout(r, 200));

         // IMPORTANT: Re-acquire fresh paragraph reference (React may have replaced it)
         const freshP = getParagraph(editor);
         if (!freshP) throw new Error('Fresh paragraph not found after select-all');
         log(`Fresh paragraph acquired: ${freshP.tagName}`);

          // Set selection on fresh paragraph (full select for replace)
          const freshRange = document.createRange();
          freshRange.selectNodeContents(freshP);
          sel.removeAllRanges();
          sel.addRange(freshRange);
         await new Promise(r => setTimeout(r, 100));

         // Dispatch beforeinput with insertText on FRESH paragraph
         const beforeInput = new InputEvent('beforeinput', {
           inputType: 'insertText',
           data: prompt,
           bubbles: true,
           cancelable: true,
           isComposing: false
         });

         const canceled = !freshP.dispatchEvent(beforeInput);
         log(`beforeinput: canceled=${canceled}`);

         // Wait for render
         await new Promise(r => setTimeout(r, 1500));

         // Verify — read from fresh paragraph
         const verifyP = getParagraph(editor);
         if (!verifyP) throw new Error('Paragraph vanished after insert');
         const actual = verifyP.textContent.trim();
         log(`VERIFY: expected="${prompt}" actual="${actual}"`);
         log(`pEl.innerHTML: ${verifyP.innerHTML.substring(0, 300)}`);

          if (actual !== prompt.trim()) {
            throw new Error(`Mismatch: expected "${prompt}", got "${actual}"`);
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
            // Select mode tab (image/video) based on settings
            await selectModeTab(settings.type);
            // Close popup menu to avoid interfering with next prompt
            await closePopupMenu();
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
