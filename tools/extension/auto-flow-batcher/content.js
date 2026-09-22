// Auto Flow Batcher - Content Script Orchestrator
// Modular architecture for Google Flow (flow.google.com)

if (window.top !== window.self) {
  // Ignore iframe injections
} else {
  (function () {
    // Prevent double-injection
    if (window.__AFB_CONTENT_LOADED__) {
      console.log('[AFB] Content script already loaded, skipping duplicate injection');
      return;
    }
    window.__AFB_CONTENT_LOADED__ = true;

    // Guard: only run on Flow pages
    const isFlowPage = location.href.includes('flow.google.com');
    if (!isFlowPage) {
      console.log('[AFB] Not on Flow page, skipping content script');
      return;
    }

    let isRunning = true;
    window.__AFB_RUNTIME_CONFIG__ = null;

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

    async function processPrompt(prompt, settings) {
      try {
        if (!isRunning) {
          log('>>> ABORT: Process stopped by user (pre-check)');
          return { status: 'stopped', message: 'Stopped by user' };
        }

        // 0. Ensure Dynamic Runtime Configuration is initialized
        if (!window.__AFB_RUNTIME_CONFIG__) {
          throw new Error('Runtime configuration missing. Please ensure session is active.');
        }

        // 1. Ensure Flow project page is loaded and ready
        await window.AFB_DOM.ensureFlowProjectReady(log, () => isRunning);

        // 2. Detect and normalize Agent mode & sidepanel
        await window.AFB_Agent.closeSidepanelIfOpen(log);
        await window.AFB_Agent.disableAgentMode(log);

        log(`>>> START: "${prompt}"`);
        const promptDelaySec = (settings.promptDelayMs || settings.globalDelayMs || 0) / 1000;
        const dlDelaySec = (settings.downloadDelayMs || 0) / 1000;
        log(`>>> Settings: type=${settings.type}, ratio=${settings.ratio}, batch=x${settings.batch}, downloadQuality=${settings.downloadQuality || 'default'}, promptDelay=${promptDelaySec}s, downloadDelay=${dlDelaySec}s`);

        // 3. Find and focus ProseMirror editor
        let editor = null;
        for (let i = 0; i < 20; i++) {
          editor = window.AFB_DOM.findEditor();
          if (editor && window.AFB_DOM.isVisibleElement(editor)) break;
          await new Promise(r => setTimeout(r, 100));
        }
        if (!editor) throw new Error('Prompt editor element not found');
        log('[AFB] Editor found ✓');

        safeRuntimeSendMessage({ action: "UPDATE_QUEUE_STATUS", status: "typing" });
        const typed = await window.AFB_Typewriter.typeIntoProseMirror(editor, prompt, () => isRunning, log);

        // Verify text content
        const currentText = (editor.textContent || '').trim();
        log(`[AFB] Editor text after typing: "${currentText}"`);
        if (currentText.includes(prompt.trim())) {
          log('[AFB] Prompt typing VERIFIED ✓');
        } else {
          log('[AFB] WARN: Prompt text verification mismatch, but continuing');
        }

        // 5. Apply Variant/Settings Popover (Type, Model, Ratio, Video Controls, Batch) & Close Popover safely
        log('[AFB] >>> Applying Settings Popover configuration...');
        safeRuntimeSendMessage({ action: "UPDATE_QUEUE_STATUS", status: "configuring" });
        const settingsResult = await window.AFB_Variant.applyVariantSettings(settings, log);
        if (!settingsResult.ok) {
          throw new Error(`[AFB] Failed to apply settings: ${settingsResult.error}`);
        }

        // 6. Post-settings assertion: ensure Agent mode was NOT accidentally re-enabled by settings interactions
        const postAgentCheck = window.AFB_Agent.checkAgentState();
        if (postAgentCheck.agentMode === 'ON') {
          log('[AFB-Agent] WARN: Agent mode detected ON after applying settings! Disabling...');
          await window.AFB_Agent.disableAgentMode(log);
        }

        if (!isRunning) {
          return { status: 'stopped', message: 'Stopped after settings' };
        }

        // 7. Snapshot current tile IDs before triggering generation
        const beforeTileIds = window.AFB_Monitor.getCurrentTileIds();
        log(`[AFB] Pre-generation snapshot: ${beforeTileIds.size} existing tile IDs detected`);

        // Post-popover input focus and space append to commit ProseMirror transaction
        if (editor) {
          editor.scrollIntoView({ behavior: 'instant', block: 'center' });
          editor.focus();
          await new Promise(r => setTimeout(r, 100));

          // Move caret to the very end of editor
          const sel = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(editor);
          range.collapse(false); // collapse to end
          sel.removeAllRanges();
          sel.addRange(range);

          // Type a space at the end to activate ProseMirror input event
          try {
            document.execCommand('insertText', false, ' ');
          } catch (_) {
            editor.dispatchEvent(new InputEvent('input', { inputType: 'insertText', data: ' ', bubbles: true }));
          }

          editor.dispatchEvent(new Event('input', { bubbles: true }));
          editor.dispatchEvent(new Event('change', { bubbles: true }));
          editor.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
          log('[AFB] Post-settings space appended to editor content ✓');
        }

        // Wait a brief tick to ensure ProseMirror state is 100% committed before submission
        await new Promise(r => setTimeout(r, 400));

        // 8. Click Start Generation / Create button
        log('[AFB] >>> Clicking Start Generation button...');
        safeRuntimeSendMessage({ action: "UPDATE_QUEUE_STATUS", status: "generating" });
        const createClicked = await window.AFB_Generator.clickCreateButton(
          beforeTileIds,
          editor,
          () => isRunning,
          log,
          window.AFB_Monitor.getCurrentTileIds
        );

        if (!createClicked) {
          if (!isRunning) return { status: 'stopped', message: 'Stopped during click Create' };
          throw new Error('Failed to trigger generation (Start Generation button could not be activated)');
        }

        log('[AFB] Generation triggered successfully! Monitoring generated tiles...');

        // 9. Monitor generation until expected batch tiles are detected in DOM
        const batchCount = parseInt(settings.batch, 10) || 1;
        const monitorResult = await window.AFB_Monitor.monitorGeneration(
          batchCount,
          beforeTileIds,
          settings,
          () => isRunning,
          log,
          (countdown) => {
            safeRuntimeSendMessage({ action: "COUNTDOWN_UPDATE", seconds: countdown });
          }
        );

        log(`[AFB-Monitor] Generation monitoring complete: Status=${monitorResult.status}, Found=${monitorResult.found}/${batchCount} media tile(s)`);

        if (monitorResult.foundTiles && monitorResult.foundTiles.length > 0) {
          monitorResult.foundTiles.forEach((tile, idx) => {
            log(`[AFB-Monitor] Tile [${idx + 1}/${monitorResult.foundTiles.length}] ID: ${tile.tileId} ➔ Media: ${tile.url ? tile.url.substring(0, 50) + '...' : 'ready'}`);
          });
        }

        // 10. Process Downloads for all found tiles
        log(`[AFB] >>> Processing download for ${monitorResult.foundTiles.length} generated tile(s) (Quality: ${settings.downloadQuality || '1K'})...`);
        const downloadedCount = await window.AFB_Downloader.processBatchDownloads(
          monitorResult.foundTiles,
          settings.currentIndex || 0,
          settings,
          () => isRunning,
          log,
          safeRuntimeSendMessage
        );

        log(`[AFB] >>> Batch Processing Result: ${downloadedCount}/${monitorResult.found} media item(s) downloaded successfully!`);

        return {
          status: downloadedCount > 0 ? 'success' : 'failed',
          message: `${downloadedCount}/${batchCount} media downloaded (${monitorResult.status})`,
          generated: monitorResult.found,
          downloaded: downloadedCount,
          expected: batchCount
        };

      } catch (err) {
        log(`>>> ERROR: ${err.message}`);
        return { status: 'failed', message: err.message };
      }
    }

    // Message Listeners
    if (hasExtensionMessageListener()) {
      chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
        if (msg.action === 'PING') {
          sendResponse({ status: 'ok' });
          return true;
        }

        if (msg.action === 'INITIALIZE_RUNTIME_CONFIG') {
          if (msg.config && msg.config.protocol && msg.config.selectors) {
            window.__AFB_RUNTIME_CONFIG__ = msg.config;
            log(`[AFB] Runtime configuration loaded (Protocol: "${msg.config.protocol}") ✓`);
            sendResponse({ status: 'ok' });
          } else {
            sendResponse({ status: 'failed', message: 'Invalid runtime configuration signature' });
          }
          return true;
        }

        if (msg.action === 'CHECK_PAGE') {
          const state = window.AFB_Agent.checkAgentState();
          sendResponse(state);
          return true;
        }

        if (msg.action === 'PREPARE_PAGE') {
          (async () => {
            try {
              const ready = await window.AFB_Agent.normalizeAndPreparePage(log);
              if (ready) {
                sendResponse({ status: 'ready', message: 'Prepare complete — Agent OFF, bottom panel ready' });
              } else {
                sendResponse({ status: 'failed', message: 'Prompt input not found after prepare' });
              }
            } catch (e) {
              sendResponse({ status: 'failed', message: e.message });
            }
          })();
          return true;
        }

        if (msg.action === 'STOP') {
          isRunning = false;
          log('>>> STOP received — aborting');
          sendResponse({ status: 'stopped' });
          return true;
        }

        if (msg.action === 'CREATE_PROJECT') {
          isRunning = true;
          if (window.AFB_DOM.isFlowProjectPage()) {
            sendResponse({ status: 'success', message: 'Already on Flow project page' });
            return true;
          }
          window.AFB_DOM.clickNewProjectFromLanding(log, () => isRunning)
            .then(clicked => sendResponse(clicked
              ? { status: 'success', message: 'New project clicked' }
              : { status: 'failed', message: 'New project button not found' }))
            .catch(e => sendResponse({ status: 'failed', message: e.message }));
          return true;
        }

        if (msg.action === 'PROCESS_PROMPT') {
          isRunning = true;
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
