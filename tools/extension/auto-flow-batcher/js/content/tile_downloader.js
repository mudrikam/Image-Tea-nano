// Tile Downloader & Quality Selection for Auto Flow Batcher (Modern Google Flow DOM)
(function () {
  window.AFB_Downloader = {
    normalizeDownloadQuality(settings) {
      const q = (settings?.downloadQuality || '1K').toString().trim().toUpperCase();
      if (q === 'DEFAULT' || q === '1K') return '1K';
      if (q === '720P') return '720p';
      if (q === '1080P') return '1080p';
      if (q === '270P') return '270p';
      if (q === '2K') return '2K';
      if (q === '4K') return '4K';
      return q;
    },

    isOriginalQuality(settings) {
      const q = window.AFB_Downloader.normalizeDownloadQuality(settings);
      if (settings?.type === 'video') return q === '720p';
      return q === '1K';
    },

    /**
     * Finds the "More options" (more_vert) button on a tile container.
     */
    findMoreButtonOnTile(container) {
      if (!container) return null;
      const conf = window.__AFB_RUNTIME_CONFIG__?.selectors;
      if (!conf || !conf.moreAction || !conf.moreIcon) return null;
      const moreLabel = conf.moreAction.toLowerCase();
      const moreIconText = conf.moreIcon.toLowerCase();

      // 1. Direct button with flowhotbarbutton and aria-label="More options"
      const exactBtn = container.querySelector(`button[flowhotbarbutton][aria-label*="${moreLabel}" i], button[aria-label*="${moreLabel}" i]`);
      if (exactBtn) return exactBtn;

      // 2. Button containing icon with text matching moreIcon
      const allButtons = Array.from(container.querySelectorAll('button'));
      const iconSel = window.__AFB_RUNTIME_CONFIG__?.selectors?.iconElements || 'mat-icon, .google-symbols';
      const moreBtn = allButtons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').toLowerCase();
        const iconEl = b.querySelector(iconSel);
        const iconText = (iconEl?.textContent || '').trim().toLowerCase();
        return aria.includes(moreLabel) || iconText === moreIconText;
      });
      if (moreBtn) return moreBtn;

      return null;
    },

    /**
     * Hovers and reveals the tile action buttons (hotbar) on modern Flow tile.
     */
    async revealTileHotbar(container, log = console.log) {
      if (!container) return null;

      // Hover tile container to trigger CSS .hover-overlay and .hotbar-container visibility
      window.AFB_DOM.hoverElement(container, 'Tile container hover');
      await new Promise(r => setTimeout(r, 200));

      const hotbarSelector = window.__AFB_RUNTIME_CONFIG__?.selectors?.hotbar;
      const hotbar = hotbarSelector ? container.querySelector(hotbarSelector) : null;
      if (hotbar) {
        window.AFB_DOM.hoverElement(hotbar, 'Tile hotbar hover');
        await new Promise(r => setTimeout(r, 200));
      }

      return window.AFB_Downloader.findMoreButtonOnTile(container);
    },

    /**
     * Downloads specific quality (2K, 4K, 1080p, 270p, etc.) via Google Flow's native context menu.
     * Enforces Strict Fail-Fast (no hidden fallback).
     */
    async downloadViaFlowContextMenu(tileInfo, settings, log = console.log) {
      const quality = window.AFB_Downloader.normalizeDownloadQuality(settings);
      const tileContainers = window.__AFB_RUNTIME_CONFIG__?.selectors?.tileContainers;
      const container = tileInfo.container || (tileContainers ? tileInfo.element?.closest(tileContainers) : null);

      if (!container) {
        throw new Error('[AFB-Downloader] Tile container not found for menu download');
      }

      log(`[AFB-Downloader] Opening tile menu to download quality: "${quality}"...`);
      const moreBtn = await window.AFB_Downloader.revealTileHotbar(container, log);

      if (!moreBtn) {
        throw new Error('[AFB-Downloader] "More options" (more_vert) button not found on tile hotbar');
      }

      // Click "More options" button to open main context menu
      log('[AFB-Downloader] 1. Clicking tile More options (more_vert) button...');
      window.AFB_DOM.dispatchMouseSequence(moreBtn, 'Tile More options');
      await new Promise(r => setTimeout(r, 400));

      // Wait for main context menu
      const menuPanelsSelector = window.__AFB_RUNTIME_CONFIG__?.selectors?.menuPanels || '[role="menu"]';
      const menuItemsSelector = window.__AFB_RUNTIME_CONFIG__?.selectors?.menuItems || '[role="menuitem"]';
      const openMenus = () => Array.from(document.querySelectorAll(menuPanelsSelector)).filter(window.AFB_DOM.isVisibleElement);
      let downloadMenuItem = null;

      for (let attempt = 0; attempt < 10; attempt++) {
        const menus = openMenus();
        for (const menu of menus) {
          const items = Array.from(menu.querySelectorAll(menuItemsSelector));
          downloadMenuItem = items.find(item => {
            const txt = (item.textContent || '').trim().toLowerCase();
            const aria = (item.getAttribute('aria-label') || '').trim().toLowerCase();
            return txt.includes('download') || aria.includes('download');
          });
          if (downloadMenuItem) break;
        }
        if (downloadMenuItem) break;
        await new Promise(r => setTimeout(r, 150));
      }

      if (!downloadMenuItem) {
        await window.AFB_Variant.closePopupMenu(log);
        throw new Error('[AFB-Downloader] "Download" item not found in context menu');
      }

      // Hover / Expand "Download" flyout submenu
      log(`[AFB-Downloader] 2. Expanding "Download" submenu for quality "${quality}"...`);
      window.AFB_DOM.hoverElement(downloadMenuItem, 'Download menu item');
      window.AFB_DOM.dispatchMouseSequence(downloadMenuItem, 'Download menuitem click');
      await new Promise(r => setTimeout(r, 400));

      // Look for quality submenu item (1K, 2K, 4K, 720p, 1080p, 270p)
      let qualityMenuItem = null;
      for (let attempt = 0; attempt < 12; attempt++) {
        const menus = openMenus();
        for (const menu of menus) {
          const items = Array.from(menu.querySelectorAll(menuItemsSelector));
          qualityMenuItem = items.find(item => {
            const txt = (item.textContent || '').trim().toLowerCase();
            const qLower = quality.toLowerCase();
            return txt.startsWith(qLower) || txt.includes(qLower);
          });
          if (qualityMenuItem) break;
        }
        if (qualityMenuItem) break;
        await new Promise(r => setTimeout(r, 150));
      }

      if (!qualityMenuItem) {
        await window.AFB_Variant.closePopupMenu(log);
        throw new Error(`[AFB-Downloader] Quality option "${quality}" not found in Download submenu`);
      }

      const clickable = qualityMenuItem.closest('[role="menuitem"], button') || qualityMenuItem;
      const isDisabled = clickable.getAttribute('aria-disabled') === 'true' || clickable.disabled || clickable.classList.contains('disabled');
      if (isDisabled) {
        await window.AFB_Variant.closePopupMenu(log);
        throw new Error(`[AFB-Downloader] Quality option "${quality}" is disabled/locked in Flow menu`);
      }

      log(`[AFB-Downloader] 3. Clicking Quality option: "${quality}"...`);
      window.AFB_DOM.dispatchMouseSequence(clickable, `Quality ${quality}`);

      // Close open context menu cleanly
      setTimeout(() => {
        window.AFB_Variant.closePopupMenu(log).catch(() => {});
      }, 300);

      return true;
    },

    /**
     * Direct browser download via background script (fallback or default original quality).
     */
    downloadDirectMedia(url, promptText, index, settings, safeSendMsg = () => {}) {
      const ext = (settings.type === 'video') ? 'mp4' : 'jpg';
      const prefix = (settings.type === 'video') ? 'Flow_Video' : 'Flow_Image';
      const cleanPrompt = (promptText || 'generation').replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 30);

      safeSendMsg({
        type: 'DOWNLOAD_CONTENT',
        url: url,
        promptIndex: index,
        extension: ext,
        prefix: `${prefix}_${cleanPrompt}`,
        batchIndex: index
      });
    },

    getDownloadDelayMs(settings) {
      const delayMs = Number(settings?.downloadDelayMs);
      if (Number.isFinite(delayMs) && delayMs >= 0) return Math.round(delayMs);
      const delaySeconds = Number(settings?.downloadDelaySeconds);
      if (Number.isFinite(delaySeconds) && delaySeconds >= 0) return Math.round(delaySeconds * 1000);
      return 5000;
    },

    async applyDownloadCooldown(settings, currentNumber, totalNumber, isRunningFn = () => true, log = console.log, safeSendMsg = () => {}) {
      const delayMs = window.AFB_Downloader.getDownloadDelayMs(settings);
      if (delayMs <= 0 || currentNumber >= totalNumber || !isRunningFn()) return;

      const seconds = Math.ceil(delayMs / 1000);
      log(`[AFB-Downloader] Cooldown ${seconds}s before next download...`);
      safeSendMsg({ action: 'DOWNLOAD_COOLDOWN_START', seconds });
      await new Promise(r => setTimeout(r, delayMs));
      safeSendMsg({ action: 'DOWNLOAD_COOLDOWN_END' });
    },

    /**
     * Prepares and starts the download listener BEFORE triggering download action.
     * Returns an object { promise, cancel } to prevent any race condition.
     */
    prepareDownloadCompletionWaiter(timeoutMs = 90000, log = console.log) {
      log(`[AFB-Downloader] Preparing chrome.downloads listener (timeout: ${Math.round(timeoutMs / 1000)}s)...`);
      let timer = null;
      let resolved = false;
      let cleanupFn = () => {};

      const promise = new Promise((resolve) => {
        cleanupFn = () => {
          if (timer) clearTimeout(timer);
          try { chrome.runtime.onMessage.removeListener(runtimeListener); } catch (_) {}
          try { window.removeEventListener('message', windowListener); } catch (_) {}
        };

        const finish = (msg) => {
          if (resolved) return;
          resolved = true;
          cleanupFn();
          log(`[AFB-Downloader] Real download verified on disk: "${msg.filename}" (${Math.round((msg.fileSize || 0) / 1024)} KB) ✓`);
          resolve(msg);
        };

        const runtimeListener = (msg) => {
          if (msg && (msg.action === 'REAL_DOWNLOAD_COMPLETED' || msg.type === 'REAL_DOWNLOAD_COMPLETED')) {
            finish(msg);
          }
        };

        const windowListener = (event) => {
          const msg = event?.data;
          if (msg && (msg.action === 'REAL_DOWNLOAD_COMPLETED' || msg.type === 'REAL_DOWNLOAD_COMPLETED')) {
            finish(msg);
          }
        };

        try { chrome.runtime.onMessage.addListener(runtimeListener); } catch (_) {}
        try { window.addEventListener('message', windowListener); } catch (_) {}

        timer = setTimeout(() => {
          if (resolved) return;
          resolved = true;
          cleanupFn();
          log('[AFB-Downloader] ERROR: Download completion timed out (file was not written by browser)');
          resolve(null);
        }, timeoutMs);
      });

      return { promise, cancel: cleanupFn };
    },

    /**
     * Processes downloading for all newly generated tiles.
     * 100% Official Flow Context Menu Download with Pre-Registered Listener & Strict Fail-Fast.
     */
    async processBatchDownloads(foundTiles, promptIndex = 0, settings, isRunningFn = () => true, log = console.log, safeSendMsg = () => {}) {
      const count = foundTiles.length;
      let downloadedCount = 0;

      for (let i = 0; i < count && isRunningFn(); i++) {
        const tileInfo = foundTiles[i];
        const quality = window.AFB_Downloader.normalizeDownloadQuality(settings);
        log(`[AFB-Downloader] [${i + 1}/${count}] Processing download for tile "${tileInfo.promptTitle || 'tile'}" (Quality: ${quality})...`);
        safeSendMsg({ action: 'SET_PHASE_DOWNLOADING', index: promptIndex });

        // Step 1: Pre-register the download listener BEFORE clicking menu
        const waiter = window.AFB_Downloader.prepareDownloadCompletionWaiter(90000, log);

        // Step 2: Click the native Flow context menu (More options ➔ Download ➔ Quality)
        try {
          await window.AFB_Downloader.downloadViaFlowContextMenu(tileInfo, settings, log);
        } catch (err) {
          waiter.cancel();
          log(`[AFB-Downloader] [${i + 1}/${count}] ERROR: ${err.message}`);
          throw err; // Strict Fail-Fast
        }

        // Step 3: Await verified disk write confirmation from chrome.downloads
        const dlResult = await waiter.promise;
        if (!dlResult) {
          throw new Error(`[AFB-Downloader] Download confirmation timed out for quality "${quality}"`);
        }

        downloadedCount++;
        log(`[AFB-Downloader] [${i + 1}/${count}] Download step finished successfully ✓`);

        // Step 4: Apply Cooldown between downloads/prompts if configured
        await window.AFB_Downloader.applyDownloadCooldown(settings, i + 1, count, isRunningFn, log, safeSendMsg);
      }

      return downloadedCount;
    }
  };
})();
