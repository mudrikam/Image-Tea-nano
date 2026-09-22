// Generation Monitor for Auto Flow Batcher (Modern Google Flow Architecture)
(function () {
  window.AFB_Monitor = {
    /**
     * Extracts all currently COMPLETED generated media tiles from DOM.
     * Uses strict unique media identity (UUID, clean CDN path, or data-media-id).
     * No unstable index-based fallbacks that shift when new tiles are prepended.
     */
    getCurrentCompletedTiles() {
      const conf = window.__AFB_RUNTIME_CONFIG__?.selectors;
      if (!conf || !conf.tileContainers) return new Map();
      const selector = conf.tileContainers;
      const tileContainers = Array.from(document.querySelectorAll(selector));
      const snapshot = new Map();

      const mediaImgSel = conf.mediaImages || 'img';
      const mediaVidSel = conf.mediaVideos || 'video';
      const cdnHost = conf.cdnHost || '';

      tileContainers.forEach((container) => {
        // Look for completed media element
        const img = container.querySelector(mediaImgSel);
        const video = container.querySelector(mediaVidSel);

        // Extract stable unique UUID or CDN identifier
        let mediaId = img?.getAttribute('data-media-id') || null;
        if (!mediaId && img?.src && cdnHost && img.src.includes(cdnHost)) {
          mediaId = img.src.split('?')[0].split('/').pop();
        }
        if (!mediaId && video?.src && cdnHost && video.src.includes(cdnHost)) {
          mediaId = video.src.split('?')[0].split('/').pop();
        }
        if (!mediaId && container.getAttribute('data-tile-id')) {
          mediaId = container.getAttribute('data-tile-id');
        }

        // Check if tile is still rendering (has percentage text or progress indicator)
        const progressEl = container.querySelector('[role="progressbar"], .progress-text, mat-progress-spinner');
        const textContent = (container.textContent || '');
        const isStillRendering = Boolean(progressEl) || textContent.includes('%') || textContent.includes('Generating');

        const tileFooterSelector = conf?.tileFooter;
        const promptTitle = (tileFooterSelector ? container.querySelector(tileFooterSelector)?.textContent?.trim() : '') ||
                            container.getAttribute('aria-label') || '';

        // Only register if media has a valid, non-empty stable ID and is NOT currently rendering
        const hasValidSource = (img?.src && (!cdnHost || img.src.includes(cdnHost))) || (video?.src && video.src.length > 5);
        if (mediaId && !isStillRendering && hasValidSource) {
          snapshot.set(mediaId, {
            id: mediaId,
            element: img || video,
            container: container,
            promptTitle: promptTitle,
            src: img?.src || video?.src || ''
          });
        }
      });

      return snapshot;
    },

    getCurrentTileIds() {
      const snapshot = window.AFB_Monitor.getCurrentCompletedTiles();
      return new Set(snapshot.keys());
    },

    detectFailures(beforeFailureCount = 0) {
      const conf = window.__AFB_RUNTIME_CONFIG__?.selectors;
      if (!conf || !conf.tileContainers || !conf.failedSignatures) return [];
      const selector = conf.tileContainers + ', div';
      const allElements = Array.from(document.querySelectorAll(selector));
      const failures = [];
      const sigs = conf.failedSignatures;

      allElements.forEach(el => {
        if (!window.AFB_DOM.isVisibleElement(el)) return;
        const text = (el.textContent || '').trim().toLowerCase();
        
        const iconSel = conf.iconElements || 'mat-icon, .google-symbols';
        const isFailedCard = (sigs[0] && text.includes(sigs[0])) ||
                             (sigs[1] && text.includes('failed') && text.includes(sigs[1])) ||
                             (sigs[2] && text.includes('failed') && el.querySelector(iconSel)?.textContent === sigs[2]) ||
                             (text.startsWith('failed') && text.length < 100);
        if (isFailedCard) {
          failures.push(el);
        }
      });
      return failures;
    },

    /**
     * Monitors generation until expectedCount genuinely COMPLETED tiles appear in DOM matching prompt title or new IDs.
     */
    async monitorGeneration(expectedCount, beforeTileIds = new Set(), settings = {}, isRunningFn = () => true, log = console.log, sendCountdown = () => {}) {
      const MAX_WAIT_SECONDS = (settings.type === 'video') ? 240 : 180;
      const POLL_INTERVAL = 1500;
      const maxWaitMs = MAX_WAIT_SECONDS * 1000;
      const targetPrompt = (settings.currentPrompt || settings.prompt || '').trim().toLowerCase();

      const beforeFailures = window.AFB_Monitor.detectFailures();
      const beforeFailureCount = beforeFailures.length;
      log(`[AFB-Monitor] Baseline: ${beforeTileIds.size} completed tiles, ${beforeFailureCount} error cards already existed before generation`);

      const startTime = Date.now();
      let lastSeenCount = 0;
      let lastCountdownSent = 0;

      while (Date.now() - startTime < maxWaitMs) {
        if (!isRunningFn()) {
          log('[AFB-Monitor] ABORT: Monitoring stopped by user');
          break;
        }

        const currentCompleted = window.AFB_Monitor.getCurrentCompletedTiles();
        const newTiles = [];

        for (const [id, tileInfo] of currentCompleted.entries()) {
          const isBrandNew = !beforeTileIds.has(id);
          const tileTitle = (tileInfo.promptTitle || '').toLowerCase();
          const matchesPrompt = !targetPrompt || tileTitle.includes(targetPrompt) || targetPrompt.includes(tileTitle);

          // Priority: Must be newly rendered tile (not in baseline snapshot)
          if (isBrandNew) {
            newTiles.push({
              tileId: id,
              url: tileInfo.src,
              element: tileInfo.element,
              container: tileInfo.container,
              promptTitle: tileInfo.promptTitle,
              score: matchesPrompt ? 10 : 1
            });
          }
        }

        // Sort by match score and recency (top-leftmost in grid is newest in Flow)
        newTiles.sort((a, b) => (b.score || 0) - (a.score || 0));

        const seenCount = newTiles.length;
        const elapsed = Date.now() - startTime;
        const remaining = Math.max(0, Math.ceil((maxWaitMs - elapsed) / 1000));
        if (remaining !== lastCountdownSent) {
          sendCountdown(remaining);
          lastCountdownSent = remaining;
        }

        if (seenCount !== lastSeenCount) {
          log(`[AFB-Monitor] Generation progress: ${seenCount}/${expectedCount} completed tiles ready in DOM ✓`);
        }
        lastSeenCount = seenCount;

        if (seenCount >= expectedCount) {
          log(`[AFB-Monitor] SUCCESS: All ${expectedCount} expected tiles finished rendering and verified in DOM!`);
          return { status: 'complete', found: seenCount, failed: 0, foundTiles: newTiles };
        }

        // Check if a NEW error card appeared during this prompt run (not from previous history)
        const currentFailures = window.AFB_Monitor.detectFailures();
        const newFailuresCount = currentFailures.length - beforeFailureCount;
        if (newFailuresCount > 0) {
          if (seenCount > 0) {
            log(`[AFB-Monitor] PARTIAL: ${seenCount} tiles generated, ${newFailuresCount} new failure(s) detected`);
            return { status: 'partial', found: seenCount, failed: newFailuresCount, foundTiles: newTiles };
          } else {
            log(`[AFB-Monitor] FAILED: Server returned new error card ("Failed to load image" / render error)`);
            return { status: 'failed', found: 0, failed: newFailuresCount, foundTiles: [] };
          }
        }

        await new Promise(r => setTimeout(r, POLL_INTERVAL));
      }

      const finalCompleted = window.AFB_Monitor.getCurrentCompletedTiles();
      const finalNewTiles = Array.from(finalCompleted.values()).filter(t => !beforeTileIds.has(t.id));

      if (finalNewTiles.length > 0) {
        log(`[AFB-Monitor] TIMEOUT: Detected ${finalNewTiles.length}/${expectedCount} completed tiles`);
        return { status: 'partial', found: finalNewTiles.length, failed: 0, foundTiles: finalNewTiles };
      }

      log('[AFB-Monitor] TIMEOUT: No new completed tiles detected within time limit');
      return { status: 'failed', found: 0, failed: 0, foundTiles: [] };
    }
  };
})();
