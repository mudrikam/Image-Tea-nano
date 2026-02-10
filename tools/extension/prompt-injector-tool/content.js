(function() {
  'use strict';

  console.log('[Prompt Injector] Content script starting on:', window.location.href);

  if (window.__PROMPT_INJECTOR_LOADED__) {
    console.log('[Prompt Injector] Content script already loaded, skipping');
    return;
  }
  window.__PROMPT_INJECTOR_LOADED__ = true;
  console.log('[Prompt Injector] Content script initializing...');
  console.log('[Prompt Injector] Custom HTML tags support ENABLED (Firefly, Web Components, Shadow DOM)');

  let pickerActive = false;
  let pickerPointIndex = null;
  let highlightedElement = null;
  let highlightOverlay = null;
  let highlightLabel = null;

  let automationRunning = false;
  let automationPaused = false;
  let automationConfig = null;
  let automationPrompts = [];
  let automationIndex = 0;
  let currentMonitoringPromptIndex = -1;

  const downloadedUrls = new Set();

  function deepQuerySelectorAll(rootElement, selector) {
    const results = [];
    
    const traverse = (element) => {
      if (element.matches && element.matches(selector)) {
        results.push(element);
      }
      
      const children = element.querySelectorAll(selector);
      children.forEach(child => results.push(child));
      
      if (element.shadowRoot) {
        const shadowChildren = element.shadowRoot.querySelectorAll(selector);
        shadowChildren.forEach(child => results.push(child));
        
        element.shadowRoot.querySelectorAll('*').forEach(el => {
          if (el.shadowRoot) traverse(el);
        });
      }
      
      element.querySelectorAll('*').forEach(el => {
        if (el.shadowRoot) traverse(el);
      });
    };
    
    traverse(rootElement);
    return results;
  }

  function deepQuerySelector(rootElement, selector) {
    const results = deepQuerySelectorAll(rootElement, selector);
    return results.length > 0 ? results[0] : null;
  }

  function getAllMediaUrls() {
    const allUrls = new Set();
    
    const images = deepQuerySelectorAll(document, 'img');
    images.forEach(img => {
      let src = img.src || img.currentSrc || img.getAttribute('data-src');
      if (src && !src.startsWith('data:image/svg') && !src.includes('placeholder')) {
        const naturalWidth = img.naturalWidth || 0;
        const naturalHeight = img.naturalHeight || 0;
        if (naturalWidth >= 500 || naturalHeight >= 500) {
          allUrls.add(src);
        }
      }
    });
    
    const videos = deepQuerySelectorAll(document, 'video');
    videos.forEach(video => {
      const src = video.src || video.currentSrc || video.querySelector('source')?.src;
      if (src) {
        allUrls.add(src);
      }
    });
    
    const canvases = deepQuerySelectorAll(document, 'canvas');
    canvases.forEach(canvas => {
      if (canvas.width >= 500 || canvas.height >= 500) {
        try {
          const dataUrl = canvas.toDataURL('image/png');
          allUrls.add(dataUrl);
        } catch (e) {}
      }
    });
    
    const bgElements = deepQuerySelectorAll(document, '[style*="background"]');
    bgElements.forEach(el => {
      const style = window.getComputedStyle(el);
      const bgImage = style.backgroundImage;
      if (bgImage && bgImage !== 'none') {
        const urlMatch = bgImage.match(/url\(["']?([^"')]+)["']?\)/);
        if (urlMatch && urlMatch[1]) {
          const src = urlMatch[1];
          if (!src.startsWith('data:image/svg')) {
            const rect = el.getBoundingClientRect();
            if (rect.width >= 500 || rect.height >= 500) {
              allUrls.add(src);
            }
          }
        }
      }
    });
    
    return allUrls;
  }

  async function verifyMediaLoaded(media) {
    if (media.type === 'image') {
      let img = document.querySelector(`img[src="${media.url}"]`);
      
      if (!img) {
        img = deepQuerySelector(document, `img[src="${media.url}"]`);
      }
      
      if (!img) return false;
      
      if (img.complete && img.naturalWidth > 0 && img.naturalHeight > 0) {
        return true;
      }
      
      return new Promise((resolve) => {
        const timeout = setTimeout(() => resolve(false), 3000);
        img.onload = () => {
          clearTimeout(timeout);
          resolve(img.naturalWidth > 0 && img.naturalHeight > 0);
        };
        img.onerror = () => {
          clearTimeout(timeout);
          resolve(false);
        };
      });
    }
    return true;
  }

  function findNewMediaContent(count, urlPattern, excludeUrls = new Set()) {
    const newMedia = [];
    
    const matchesPattern = (url) => {
      if (!urlPattern || urlPattern.trim() === '') {
        return true;
      }
      return url.startsWith(urlPattern);
    };
    
    const images = deepQuerySelectorAll(document, 'img');
    images.forEach(img => {
      let src = img.src || img.currentSrc || img.getAttribute('data-src');
      if (!src || excludeUrls.has(src) || downloadedUrls.has(src)) return;
      if (src.startsWith('data:image/svg') || src.includes('placeholder')) return;
      if (!matchesPattern(src)) return;
      
      const naturalWidth = img.naturalWidth || 0;
      const naturalHeight = img.naturalHeight || 0;
      
      if (urlPattern && urlPattern.trim() !== '') {
        if (naturalWidth > 0 && naturalHeight > 0) {
          newMedia.push({ url: src, type: 'image', width: naturalWidth, height: naturalHeight });
          console.log(`[Prompt Injector] Image matched by URL pattern: ${src.substring(0, 60)}...`);
        }
      } else if (naturalWidth > 0 && naturalHeight > 0 && (naturalWidth >= 500 || naturalHeight >= 500)) {
        newMedia.push({ url: src, type: 'image', width: naturalWidth, height: naturalHeight });
      }
    });
    
    const videos = deepQuerySelectorAll(document, 'video');
    videos.forEach(video => {
      const src = video.src || video.currentSrc || video.querySelector('source')?.src;
      if (!src || excludeUrls.has(src) || downloadedUrls.has(src)) return;
      if (!matchesPattern(src)) return;
      
      const width = video.videoWidth || 0;
      const height = video.videoHeight || 0;
      
      if (urlPattern && urlPattern.trim() !== '') {
        newMedia.push({ url: src, type: 'video', width: width, height: height });
        console.log(`[Prompt Injector] Video matched by URL pattern: ${src.substring(0, 60)}...`);
      } else if (width >= 500 || height >= 500) {
        newMedia.push({ url: src, type: 'video', width: width, height: height });
      }
    });
    
    const canvases = deepQuerySelectorAll(document, 'canvas');
    canvases.forEach(canvas => {
      if (canvas.width >= 500 || canvas.height >= 500) {
        try {
          const dataUrl = canvas.toDataURL('image/png');
          if (!excludeUrls.has(dataUrl) && !downloadedUrls.has(dataUrl)) {
            newMedia.push({ url: dataUrl, type: 'canvas', width: canvas.width, height: canvas.height });
          }
        } catch (e) {
          console.warn('[Prompt Injector] Cannot export canvas (CORS):', e);
        }
      }
    });
    
    const bgElements = deepQuerySelectorAll(document, '[style*="background"]');
    bgElements.forEach(el => {
      const style = window.getComputedStyle(el);
      const bgImage = style.backgroundImage;
      if (bgImage && bgImage !== 'none') {
        const urlMatch = bgImage.match(/url\(["']?([^"')]+)["']?\)/);
        if (urlMatch && urlMatch[1]) {
          const src = urlMatch[1];
          if (!excludeUrls.has(src) && !downloadedUrls.has(src) && !src.startsWith('data:image/svg')) {
            if (!matchesPattern(src)) return;
            const rect = el.getBoundingClientRect();
            if (rect.width >= 500 || rect.height >= 500) {
              newMedia.push({ url: src, type: 'background', width: rect.width, height: rect.height });
            }
          }
        }
      }
    });
    
    newMedia.sort((a, b) => (b.width * b.height) - (a.width * a.height));
    
    const uniqueMedia = [];
    const seenUrls = new Set();
    for (const media of newMedia) {
      if (!seenUrls.has(media.url)) {
        seenUrls.add(media.url);
        uniqueMedia.push(media);
      }
    }
    
    return uniqueMedia.slice(0, count);
  }

  function createHighlightOverlay() {
    if (highlightOverlay) return;
    
    highlightOverlay = document.createElement('div');
    highlightOverlay.id = 'prompt-injector-highlight';
    highlightOverlay.style.cssText = `
      position: fixed;
      pointer-events: none;
      border: 3px solid #ff8800;
      background: rgba(255, 136, 0, 0.15);
      z-index: 2147483647;
      transition: all 0.05s ease;
      display: none;
      box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.3);
    `;
    document.body.appendChild(highlightOverlay);

    highlightLabel = document.createElement('div');
    highlightLabel.id = 'prompt-injector-label';
    highlightLabel.style.cssText = `
      position: fixed;
      pointer-events: none;
      background: #ff8800;
      color: #000;
      font-size: 11px;
      font-family: monospace;
      padding: 2px 6px;
      border-radius: 3px;
      z-index: 2147483647;
      display: none;
      white-space: nowrap;
      max-width: 300px;
      overflow: hidden;
      text-overflow: ellipsis;
    `;
    document.body.appendChild(highlightLabel);
  }

  function removeHighlightOverlay() {
    if (highlightOverlay) {
      highlightOverlay.remove();
      highlightOverlay = null;
    }
    if (highlightLabel) {
      highlightLabel.remove();
      highlightLabel = null;
    }
  }

  function updateHighlight(element) {
    if (!element || !highlightOverlay) return;
    
    const rect = element.getBoundingClientRect();
    highlightOverlay.style.left = `${rect.left}px`;
    highlightOverlay.style.top = `${rect.top}px`;
    highlightOverlay.style.width = `${rect.width}px`;
    highlightOverlay.style.height = `${rect.height}px`;
    highlightOverlay.style.display = 'block';

    if (highlightLabel) {
      const tag = element.tagName.toLowerCase();
      const id = element.id ? `#${element.id}` : '';
      const cls = element.className && typeof element.className === 'string' ? 
        '.' + element.className.split(' ').filter(c => c && !c.startsWith('prompt-injector')).slice(0, 2).join('.') : '';
      highlightLabel.textContent = `${tag}${id}${cls}`;
      highlightLabel.style.left = `${rect.left}px`;
      highlightLabel.style.top = `${Math.max(0, rect.top - 22)}px`;
      highlightLabel.style.display = 'block';
    }
  }

  function hideHighlight() {
    if (highlightOverlay) {
      highlightOverlay.style.display = 'none';
    }
    if (highlightLabel) {
      highlightLabel.style.display = 'none';
    }
  }

  function generateSelector(element) {
    if (!element || element === document.body || element === document.documentElement) {
      return null;
    }

    const tagName = element.tagName.toLowerCase();
    
    if (tagName.includes('-')) {
      const customSelector = tagName;
      try {
        if (document.querySelectorAll(customSelector).length === 1) {
          console.log('[Prompt Injector] Custom tag is unique:', customSelector);
          return customSelector;
        }
      } catch (e) {}
    }

    if (element.id && !element.id.includes(':') && !element.id.includes(' ')) {
      const idSelector = `#${CSS.escape(element.id)}`;
      try {
        if (document.querySelectorAll(idSelector).length === 1) {
          return idSelector;
        }
      } catch (e) {
        console.warn('Invalid ID selector:', idSelector);
      }
    }

    if (element.name) {
      const nameSelector = `[name="${CSS.escape(element.name)}"]`;
      try {
        if (document.querySelectorAll(nameSelector).length === 1) {
          return nameSelector;
        }
      } catch (e) {
        console.warn('Invalid name selector:', nameSelector);
      }
    }

    const dataAttrs = [
      'data-testid', 'data-id', 'data-qa', 'data-cy', 'data-automation-id',
      'aria-label', 'aria-labelledby', 'aria-describedby',
      'role', 'type', 'placeholder', 'title', 'alt'
    ];
    for (const attr of dataAttrs) {
      const value = element.getAttribute(attr);
      if (value && value.length < 100) {
        const attrSelector = `[${attr}="${CSS.escape(value)}"]`;
        try {
          if (document.querySelectorAll(attrSelector).length === 1) {
            return attrSelector;
          }
        } catch (e) {
          continue;
        }
      }
    }

    if (tagName === 'button' || tagName === 'a' || tagName === 'input' || tagName === 'textarea') {
      const textContent = element.textContent?.trim();
      if (textContent && textContent.length < 50 && textContent.length > 0) {
        const escapedText = CSS.escape(textContent.substring(0, 30));
        const textSelectors = [
          `${tagName}:has-text("${textContent.substring(0, 30)}")`,
        ];
        
        if (element.value) {
          const valSelector = `${tagName}[value="${CSS.escape(element.value)}"]`;
          try {
            if (document.querySelectorAll(valSelector).length === 1) {
              return valSelector;
            }
          } catch (e) {}
        }
      }
    }

    const classes = Array.from(element.classList || []).filter(c => 
      c && 
      !c.startsWith('prompt-injector') && 
      !c.includes(':') &&
      !c.includes('[') &&
      c.length < 50
    );
    if (classes.length > 0 && classes.length <= 5) {
      const classSelector = '.' + classes.slice(0, 3).map(c => CSS.escape(c)).join('.');
      try {
        if (document.querySelectorAll(classSelector).length === 1) {
          return classSelector;
        }
      } catch (e) {
        console.warn('Invalid class selector:', classSelector);
      }
    }

    return buildPathSelector(element);
  }

  function buildPathSelector(element) {
    const path = [];
    let current = element;
    let depth = 0;
    const maxDepth = 10;
    
    while (current && current !== document.body && current !== document.documentElement && depth < maxDepth) {
      const tagName = current.tagName.toLowerCase();
      let selector = tagName;
      
      if (current.id && !current.id.includes(':') && !current.id.includes(' ')) {
        try {
          const idSelector = `#${CSS.escape(current.id)}`;
          if (document.querySelectorAll(idSelector).length === 1) {
            path.unshift(idSelector);
            break;
          }
        } catch (e) {}
      }

      const uniqueAttrs = ['data-testid', 'aria-label', 'name', 'role'];
      let foundUnique = false;
      for (const attr of uniqueAttrs) {
        const value = current.getAttribute(attr);
        if (value && value.length < 50) {
          const attrSelector = `${tagName}[${attr}="${CSS.escape(value)}"]`;
          try {
            if (document.querySelectorAll(attrSelector).length === 1) {
              path.unshift(attrSelector);
              foundUnique = true;
              break;
            }
          } catch (e) {}
        }
      }
      
      if (foundUnique) break;
      
      const parent = current.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(el => el.tagName === current.tagName);
        if (siblings.length > 1) {
          const index = siblings.indexOf(current) + 1;
          selector += `:nth-of-type(${index})`;
        }
      }
      
      path.unshift(selector);
      current = parent;
      depth++;
    }
    
    const result = path.join(' > ');
    
    try {
      if (document.querySelectorAll(result).length >= 1) {
        return result;
      }
    } catch (e) {
      console.warn('Generated selector invalid:', result);
    }
    
    return result || element.tagName.toLowerCase();
  }

  function onMouseMove(e) {
    if (!pickerActive) return;
    
    let element = document.elementFromPoint(e.clientX, e.clientY);
    
    if (!element) return;
    
    if (element.id === 'prompt-injector-highlight' || 
        element.id === 'prompt-injector-label' ||
        element.closest('#prompt-injector-highlight') ||
        element.closest('#prompt-injector-label')) {
      if (highlightOverlay) highlightOverlay.style.pointerEvents = 'none';
      if (highlightLabel) highlightLabel.style.pointerEvents = 'none';
      element = document.elementFromPoint(e.clientX, e.clientY);
    }
    
    if (element && element !== highlightedElement && 
        element.id !== 'prompt-injector-highlight' && 
        element.id !== 'prompt-injector-label') {
      highlightedElement = element;
      updateHighlight(element);
    }
  }

  function onMouseClick(e) {
    if (!pickerActive) return;
    
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    let element = highlightedElement || document.elementFromPoint(e.clientX, e.clientY);
    
    if (element && 
        element.id !== 'prompt-injector-highlight' && 
        element.id !== 'prompt-injector-label') {
      
      const tagName = element.tagName.toLowerCase();
      const isCustomElement = tagName.includes('-');
      
      if (isCustomElement) {
        console.log('[Prompt Injector] Custom element detected:', tagName, element);
      }
      
      const selector = generateSelector(element);
      console.log('[Prompt Injector] Element picked:', element.tagName, '-> Selector:', selector);
      
      if (selector) {
        chrome.runtime.sendMessage({
          type: 'ELEMENT_PICKED',
          pointIndex: pickerPointIndex,
          selector: selector
        });
      } else {
        console.warn('[Prompt Injector] Could not generate selector for element:', element);
        const fallbackSelector = element.tagName.toLowerCase();
        chrome.runtime.sendMessage({
          type: 'ELEMENT_PICKED',
          pointIndex: pickerPointIndex,
          selector: fallbackSelector
        });
      }
    }

    stopPicker();
    return false;
  }

  function onKeyDown(e) {
    if (pickerActive && e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      console.log('[Prompt Injector] ESC pressed - cancelling picker');
      stopPicker();
      return false;
    }
  }

  function startPicker(pointIndex) {
    if (pickerActive) {
      stopPicker();
    }

    pickerActive = true;
    pickerPointIndex = pointIndex;
    highlightedElement = null;

    createHighlightOverlay();

    document.addEventListener('mousemove', onMouseMove, true);
    document.addEventListener('click', onMouseClick, true);
    document.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('keydown', onKeyDown, true);

    document.body.style.cursor = 'crosshair';

    console.log('[Prompt Injector] Picker started for point', pointIndex);
  }

  function stopPicker() {
    pickerActive = false;
    pickerPointIndex = null;
    highlightedElement = null;

    document.removeEventListener('mousemove', onMouseMove, true);
    document.removeEventListener('click', onMouseClick, true);
    document.removeEventListener('keydown', onKeyDown, true);
    window.removeEventListener('keydown', onKeyDown, true);

    document.body.style.cursor = '';
    
    hideHighlight();
    removeHighlightOverlay();

    console.log('[Prompt Injector] Picker stopped');
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async function waitWhilePaused() {
    while (automationPaused && automationRunning) {
      await sleep(100);
    }
  }

  function getRandomDelay(baseDelay, randomExtra) {
    if (randomExtra <= 0) return baseDelay;
    return baseDelay + (Math.random() * randomExtra);
  }

  function simulateInput(element, text) {
    element.focus();
    
    if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
      element.select();
    } else if (element.isContentEditable) {
      const range = document.createRange();
      range.selectNodeContents(element);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }

    document.execCommand('selectAll', false, null);
    document.execCommand('insertText', false, text);

    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function simulateClick(element) {
    element.focus();
    element.click();
    
    element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
    element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
    element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  }

  let consecutiveElementNotFound = 0;
  const MAX_CONSECUTIVE_NOT_FOUND = 3;
  
  async function executePoint(point, promptText) {
    if (!point.enabled || !point.selector) return true;

    let element = document.querySelector(point.selector);
    let foundViaShadowDOM = false;
    
    if (!element) {
      element = deepQuerySelector(document, point.selector);
      foundViaShadowDOM = !!element;
    }
    
    if (!element) {
      consecutiveElementNotFound++;
      console.warn(`[Prompt Injector] Element not found: ${point.selector} (consecutive: ${consecutiveElementNotFound})`);
      chrome.runtime.sendMessage({
        type: 'AUTOMATION_STATUS',
        text: `Element not found: ${point.selector.substring(0, 30)}...`
      });
      
      if (consecutiveElementNotFound >= MAX_CONSECUTIVE_NOT_FOUND) {
        console.error('[Prompt Injector] Too many consecutive element not found - page may have crashed');
        sendStatus('Page may have crashed. Reloading...');
        
        try {
          chrome.runtime.sendMessage({ type: 'RELOAD_PAGE' });
        } catch (e) {}
        
        return false;
      }
      return true;
    }
    
    consecutiveElementNotFound = 0;
    
    if (foundViaShadowDOM) {
      console.log(`[Prompt Injector] Element found via Shadow DOM: ${point.selector}`);
    }

    if (point.type === 'paste' && promptText) {
      simulateInput(element, promptText);
    } else {
      simulateClick(element);
    }
    return true;
  }

  async function runAutomation(config, prompts) {
    if (automationRunning) {
      console.warn('[Prompt Injector] Automation already running, ignoring duplicate start request');
      return;
    }
    
    automationRunning = true;
    automationPaused = false;
    automationConfig = config;
    automationPrompts = prompts;
    automationIndex = 0;
    currentMonitoringPromptIndex = -1;

    const enabledPoints = config.points.filter(p => p.enabled && p.selector);
    const promptDelay = (config.promptDelay || 0) * 1000;
    const autoContinue = config.autoContinue || false;

    console.log('[Prompt Injector] ========== AUTOMATION STARTING ==========');
    console.log('[Prompt Injector] Prompts count:', prompts.length);
    console.log('[Prompt Injector] Enabled points:', enabledPoints.length);
    console.log('[Prompt Injector] Auto download enabled:', config.autoDownload?.enabled);
    console.log('[Prompt Injector] Monitoring mode:', config.autoDownload?.monitoring);
    console.log('[Prompt Injector] Wait seconds:', config.autoDownload?.delay);
    console.log('[Prompt Injector] Required items:', config.autoDownload?.count);

    if (enabledPoints.length === 0) {
      console.error('[Prompt Injector] No enabled points with selectors! Stopping.');
      sendStatus('Error: No enabled points with selectors');
      try {
        chrome.runtime.sendMessage({ type: 'AUTOMATION_ERROR', message: 'No enabled points with selectors configured.' });
      } catch (e) {}
      automationRunning = false;
      return;
    }

    if (prompts.length === 0) {
      console.error('[Prompt Injector] No prompts provided! Stopping.');
      sendStatus('Error: No prompts to process');
      try {
        chrome.runtime.sendMessage({ type: 'AUTOMATION_ERROR', message: 'No prompts to process.' });
      } catch (e) {}
      automationRunning = false;
      return;
    }

    for (automationIndex = 0; automationIndex < prompts.length; automationIndex++) {
      console.log(`[Prompt Injector] ===== PROMPT ${automationIndex + 1}/${prompts.length} =====`);
      
      if (currentMonitoringPromptIndex >= 0 && currentMonitoringPromptIndex !== automationIndex) {
        console.log(`[Prompt Injector] Invalidating previous monitoring for prompt ${currentMonitoringPromptIndex + 1}`);
        currentMonitoringPromptIndex = -1;
      }
      
      consecutiveElementNotFound = 0;
      
      if (!automationRunning) {
        console.log('[Prompt Injector] Automation stopped by user (before prompt)');
        break;
      }

      await waitWhilePaused();
      if (!automationRunning) {
        console.log('[Prompt Injector] Automation stopped by user (after pause check)');
        break;
      }

      const prompt = prompts[automationIndex];
      console.log('[Prompt Injector] Processing prompt:', prompt.substring(0, 50) + '...');
      
      sendStatus(`Prompt ${automationIndex + 1}: Preparing...`);
      const beforePromptSnapshot = getAllMediaUrls();
      console.log(`[Prompt Injector] Snapshot before prompt ${automationIndex + 1}:`, beforePromptSnapshot.size, 'existing media');
      
      let pointNum = 0;

      for (const point of enabledPoints) {
        if (!automationRunning) break;
        pointNum++;

        await waitWhilePaused();
        if (!automationRunning) break;

        const delay = getRandomDelay(point.delay * 1000, config.randomDelay * 1000);
        const delaySeconds = Math.ceil(delay / 1000);
        
        console.log(`[Prompt Injector] Point ${pointNum}: waiting ${delaySeconds}s before ${point.type}`);
        
        for (let remaining = delaySeconds; remaining > 0; remaining--) {
          await waitWhilePaused();
          if (!automationRunning) break;
          sendStatus(`Point ${pointNum}: Waiting ${remaining}s (${point.type})`);
          await sleep(1000);
        }

        await waitWhilePaused();
        if (!automationRunning) break;

        sendStatus(`Point ${pointNum}: Executing (${point.type})`);
        console.log(`[Prompt Injector] Point ${pointNum}: Executing ${point.type} on ${point.selector.substring(0, 30)}...`);
        const pointSuccess = await executePoint(point, point.type === 'paste' ? prompt : null);
        
        if (!pointSuccess) {
          console.log('[Prompt Injector] Point execution failed (crash detected), waiting for reload...');
          sendStatus('Waiting for page reload...');
          await sleep(5000);
          consecutiveElementNotFound = 0;
          continue;
        }
        
        console.log(`[Prompt Injector] Point ${pointNum}: Done`);
      }

      console.log('[Prompt Injector] All points executed, moving to auto-download check');
      console.log('[Prompt Injector] config.autoDownload:', JSON.stringify(config.autoDownload));
      
      let downloadSuccess = true;
      let downloadedCount = 0;
      
      if (config.autoDownload && config.autoDownload.enabled) {
        console.log('[Prompt Injector] Auto-download is ENABLED, proceeding...');
        await waitWhilePaused();
        if (!automationRunning) {
          console.log('[Prompt Injector] Stopped before auto-download');
          break;
        }
        
        const requiredCount = config.autoDownload.count || 2;
        const pattern = config.autoDownload.pattern || '';
        const extension = config.autoDownload.extension || 'jpg';
        const prefix = config.autoDownload.prefix || 'Generated_Content';
        const monitoring = config.autoDownload.monitoring || false;
        const waitSeconds = config.autoDownload.delay || 5;
        
        const baseTimeout = (extension.toLowerCase() === 'mp4') ? 180 : 60;
        const timeoutSeconds = monitoring ? Math.max(baseTimeout, waitSeconds) : waitSeconds;
        
        downloadSuccess = false;
        let newMedia = [];
        
        console.log(`[Prompt Injector] Auto download: need ${requiredCount} items, monitoring=${monitoring}, timeout=${timeoutSeconds}s`);
        
        if (monitoring) {
          currentMonitoringPromptIndex = automationIndex;
          console.log(`[Prompt Injector] Started monitoring for prompt ${automationIndex + 1}`);
          
          const maxWaitMs = timeoutSeconds * 1000;
          const startTime = Date.now();
          let scanCount = 0;
          
          sendStatus(`Monitoring for ${requiredCount} new items (max ${timeoutSeconds}s)...`);
          
          while (automationRunning && Date.now() - startTime < maxWaitMs) {
            if (currentMonitoringPromptIndex !== automationIndex) {
              console.log(`[Prompt Injector] Monitoring loop EXPIRED: prompt ${automationIndex + 1} is no longer active (current: ${currentMonitoringPromptIndex + 1})`);
              break;
            }
            
            await waitWhilePaused();
            if (!automationRunning) {
              console.log('[Prompt Injector] Monitoring loop ABORT: automation stopped');
              break;
            }
            
            scanCount++;
            newMedia = findNewMediaContent(requiredCount, pattern, beforePromptSnapshot);
            
            console.log(`[Prompt Injector] Scan #${scanCount}: found ${newMedia.length}/${requiredCount}`);
            
            if (newMedia.length >= requiredCount) {
              console.log(`[Prompt Injector] Monitoring loop EXIT: Target reached! Found ${newMedia.length} items`);
              if (automationRunning && currentMonitoringPromptIndex === automationIndex) {
                sendStatus(`Found ${newMedia.length}/${requiredCount} items!`);
              }
              if (currentMonitoringPromptIndex === automationIndex) {
                currentMonitoringPromptIndex = -1;
                console.log(`[Prompt Injector] Monitoring completed successfully, reset tracking`);
              }
              break;
            }
            
            if (automationRunning && currentMonitoringPromptIndex === automationIndex) {
              sendStatus(`Monitoring: ${newMedia.length}/${requiredCount} found (scan #${scanCount})`);
            }
            
            if (currentMonitoringPromptIndex !== automationIndex) {
              console.log(`[Prompt Injector] Monitoring loop EXPIRED: prompt changed during scan`);
              break;
            }
            
            if (!automationRunning) {
              console.log('[Prompt Injector] Monitoring loop ABORT: automation stopped during scan');
              break;
            }
            await sleep(1500);
            
            if (currentMonitoringPromptIndex !== automationIndex) {
              console.log(`[Prompt Injector] Monitoring loop EXPIRED: prompt changed after sleep`);
              break;
            }
            
            if (!automationRunning) {
              console.log('[Prompt Injector] Monitoring loop ABORT: automation stopped after sleep');
              break;
            }
          }
          
          if (currentMonitoringPromptIndex === automationIndex) {
            if (newMedia.length < requiredCount && automationRunning) {
              console.log(`[Prompt Injector] Monitoring loop EXIT: Timeout reached, found ${newMedia.length}/${requiredCount}`);
              sendStatus(`Timeout: found ${newMedia.length}/${requiredCount} items`);
            }
          } else {
            console.log(`[Prompt Injector] Monitoring loop was EXPIRED - skipping timeout message`);
          }
          
          console.log(`[Prompt Injector] Monitoring loop ENDED for prompt ${automationIndex + 1}, resetting tracking`);
          if (currentMonitoringPromptIndex === automationIndex) {
            currentMonitoringPromptIndex = -1;
          }
        } else {
          if (automationRunning) {
            sendStatus(`Waiting ${waitSeconds}s for content generation...`);
          }
          
          for (let remaining = waitSeconds; remaining > 0 && automationRunning; remaining--) {
            await waitWhilePaused();
            if (!automationRunning) break;
            
            if (automationRunning) {
              sendStatus(`Waiting ${remaining}s before scanning...`);
            }
            await sleep(1000);
            if (!automationRunning) break;
          }
          
          if (automationRunning) {
            sendStatus('Scanning for new content...');
            newMedia = findNewMediaContent(requiredCount, pattern, beforePromptSnapshot);
            console.log(`[Prompt Injector] Fixed wait scan: found ${newMedia.length}/${requiredCount}`);
          }
        }
        
        if (!automationRunning) break;
        
        console.log(`[Prompt Injector] Monitoring/waiting phase completed, moving to verification`);
        
        if (automationRunning) {
          sendStatus(`Preparing to verify ${newMedia.length} items...`);
        }
        
        if (newMedia.length > 0 && automationRunning) {
          sendStatus(`Verifying ${newMedia.length} items are fully loaded...`);
          console.log(`[Prompt Injector] Verifying ${newMedia.length} items...`);
          
          const originalCount = newMedia.length;
          const verifiedMedia = [];
          for (const media of newMedia) {
            const isLoaded = await verifyMediaLoaded(media);
            if (isLoaded) {
              verifiedMedia.push(media);
              console.log(`[Prompt Injector] Verified: ${media.url.substring(0, 50)}...`);
            } else {
              console.log(`[Prompt Injector] Not loaded: ${media.url.substring(0, 50)}...`);
            }
          }
          
          if (verifiedMedia.length === 0 && originalCount > 0) {
            console.warn(`[Prompt Injector] Verification failed for all ${originalCount} items, keeping original unverified media`);
            sendStatus(`Verification failed, keeping ${originalCount} unverified items...`);
            newMedia = newMedia;
          } else {
            newMedia = verifiedMedia;
            console.log(`[Prompt Injector] Verification complete: ${newMedia.length}/${originalCount} items verified`);
          }
        }
        
        console.log(`[Prompt Injector] Final verified count: ${newMedia.length}/${requiredCount}`);
        
        if (newMedia.length < requiredCount && automationRunning) {
          console.log(`[Prompt Injector] Retry detection: attempting up to 3 retries...`);
          for (let retry = 1; retry <= 3 && newMedia.length < requiredCount; retry++) {
            if (automationRunning) {
              sendStatus(`Retry ${retry}/3: rescanning for ${requiredCount} items...`);
            }
            console.log(`[Prompt Injector] Retry ${retry}: waiting 2s then rescanning...`);
            await sleep(2000);
            
            if (!automationRunning) break;
            
            const retryMedia = findNewMediaContent(requiredCount, pattern, beforePromptSnapshot);
            const retryVerified = [];
            for (const media of retryMedia) {
              const isLoaded = await verifyMediaLoaded(media);
              if (isLoaded) {
                retryVerified.push(media);
              }
            }
            
            if (retryVerified.length > newMedia.length) {
              newMedia = retryVerified;
              console.log(`[Prompt Injector] Retry ${retry}: found ${newMedia.length}/${requiredCount}`);
            }
            
            if (newMedia.length >= requiredCount) {
              console.log(`[Prompt Injector] Retry ${retry}: target reached!`);
              break;
            }
          }
        }
        
        if (!automationRunning) break;
        
        if (newMedia.length === 0 && automationRunning) {
          const warnMsg = `Prompt ${automationIndex + 1}: No items found after timeout. Skipping to next prompt...`;
          console.warn(`[Prompt Injector] ${warnMsg}`);
          sendStatus(warnMsg);
          
          try {
            chrome.runtime.sendMessage({ type: 'AUTOMATION_STATUS', text: warnMsg });
          } catch (e) {}
          
          downloadSuccess = false;
        } else if (newMedia.length < requiredCount && automationRunning) {
          const partialMsg = `Prompt ${automationIndex + 1}: Found ${newMedia.length}/${requiredCount} items. Downloading available...`;
          console.log(`[Prompt Injector] ${partialMsg}`);
          sendStatus(partialMsg);
        }
        
        if (newMedia.length > 0 && automationRunning) {
          sendStatus(`Downloading ${newMedia.length} items...`);
          console.log(`[Prompt Injector] Starting download of ${newMedia.length} items`);
          
          if (automationIndex === 0 && automationRunning) {
            sendStatus(`First run: waiting 3s for full render before download...`);
            console.log(`[Prompt Injector] First run delay: waiting 3s to ensure content is fully rendered`);
            await sleep(3000);
            if (!automationRunning) {
              console.log('[Prompt Injector] Stopped during first-run delay');
              break;
            }
          }
          
          const promptWords = prompt.split(/\s+/).slice(0, 5).join('_').replace(/[^a-zA-Z0-9_]/g, '');
          
          for (let i = 0; i < newMedia.length && automationRunning; i++) {
            const media = newMedia[i];
            downloadedUrls.add(media.url);
            
            if (automationRunning) {
              sendStatus(`Downloading ${i + 1}/${newMedia.length}...`);
            }
            console.log(`[Prompt Injector] Download ${i + 1}/${newMedia.length}: ${media.type} - ${media.url.substring(0, 50)}...`);
            
            chrome.runtime.sendMessage({
              type: 'DOWNLOAD_CONTENT',
              url: media.url,
              promptIndex: automationIndex,
              mediaType: media.type,
              extension: extension,
              prefix: prefix,
              promptWords: promptWords
            });
            
            await sleep(800);
            if (!automationRunning) {
              console.log('[Prompt Injector] Stopped during download');
              break;
            }
          }
          
          if (!automationRunning) break;
          
          downloadedCount = newMedia.length;
          downloadSuccess = true;
          
          try {
            chrome.runtime.sendMessage({ type: 'DOWNLOAD_DONE', count: downloadedCount });
          } catch (e) {}
          
          if (automationRunning) {
            sendStatus(`Completed prompt ${automationIndex + 1}: Downloaded ${downloadedCount} items`);
          }
          console.log(`[Prompt Injector] Download complete: ${downloadedCount} items for prompt ${automationIndex + 1}`);
          
          await sleep(1000);
          if (!automationRunning) break;
        } else if (automationRunning) {
          console.log(`[Prompt Injector] No items to download for prompt ${automationIndex + 1}, continuing to next...`);
          sendStatus(`Prompt ${automationIndex + 1}: No items found, continuing...`);
          await sleep(500);
        }
      } else if (automationRunning) {
        console.log('[Prompt Injector] Auto-download is DISABLED, skipping download phase');
        sendStatus(`Prompt ${automationIndex + 1}: Completed (auto-download disabled)`);
      }

      if (!automationRunning) {
        console.log('[Prompt Injector] Automation stopped during download wait');
        break;
      }
      
      console.log(`[Prompt Injector] Prompt ${automationIndex + 1}/${prompts.length} completed, sending progress`);
      sendProgress(automationIndex + 1, prompts.length);
      console.log(`[Prompt Injector] Progress sent: ${automationIndex + 1}/${prompts.length}`);
      
      if (automationIndex + 1 === prompts.length && automationRunning) {
        console.log('[Prompt Injector] Last prompt completed, will finish after delay check');
        sendStatus(`All ${prompts.length} prompts completed!`);
      }

      const canAutoContinue = autoContinue && downloadSuccess;
      
      if (!canAutoContinue && promptDelay > 0 && automationIndex < prompts.length - 1) {
        await waitWhilePaused();
        if (!automationRunning) break;
        
        const delaySeconds = Math.ceil(promptDelay / 1000);
        for (let remaining = delaySeconds; remaining > 0; remaining--) {
          await waitWhilePaused();
          if (!automationRunning) break;
          if (automationRunning) {
            sendStatus(`Next prompt in ${remaining}s...`);
          }
          await sleep(1000);
        }
      } else if (canAutoContinue && automationIndex < prompts.length - 1 && automationRunning) {
        sendStatus(`Auto continuing to next prompt...`);
        console.log('[Prompt Injector] Auto continuing (download success, skipping delay)');
        await sleep(500);
      }
    }

    console.log('[Prompt Injector] ========== AUTOMATION LOOP ENDED ==========');
    console.log('[Prompt Injector] automationRunning:', automationRunning);
    console.log('[Prompt Injector] automationIndex:', automationIndex);
    console.log('[Prompt Injector] prompts.length:', prompts.length);
    console.log('[Prompt Injector] Reason:', automationRunning ? 'Completed all prompts' : 'Stopped by user');
    
    automationRunning = false;
    currentMonitoringPromptIndex = -1;
    console.log('[Prompt Injector] automationRunning set to FALSE - blocking all status messages and invalidating monitoring');
    
    await sleep(200);
    
    console.log('[Prompt Injector] Sending AUTOMATION_FINISHED...');
    sendFinished();
    console.log('[Prompt Injector] AUTOMATION_FINISHED sent successfully');
  }

  function sendProgress(done, total) {
    if (!automationRunning) {
      console.log('[Prompt Injector] Skipping sendProgress - automation not running');
      return;
    }
    try {
      chrome.runtime.sendMessage({
        type: 'AUTOMATION_PROGRESS',
        done: done,
        total: total
      });
    } catch (e) {
      console.warn('[Prompt Injector] Failed to send progress:', e);
    }
  }

  function sendStatus(text) {
    if (!automationRunning) {
      console.log('[Prompt Injector] Skipping sendStatus - automation not running');
      return;
    }
    try {
      chrome.runtime.sendMessage({
        type: 'AUTOMATION_STATUS',
        text: text
      });
    } catch (e) {
      console.warn('[Prompt Injector] Failed to send status:', e);
    }
  }

  function sendFinished() {
    try {
      chrome.runtime.sendMessage({
        type: 'AUTOMATION_FINISHED'
      });
    } catch (e) {
      console.warn('[Prompt Injector] Failed to send finished:', e);
    }
  }

  function stopAutomation() {
    automationRunning = false;
    automationPaused = false;
    currentMonitoringPromptIndex = -1;
    console.log('[Prompt Injector] Automation stopped - all monitoring invalidated');
  }

  function togglePause(paused) {
    automationPaused = paused;
    console.log('[Prompt Injector] Automation', paused ? 'paused' : 'resumed');
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('[Prompt Injector] Received message:', message.type);
    
    switch (message.type) {
      case 'PING':
        console.log('[Prompt Injector] Responding to PING');
        sendResponse({ success: true, ready: true });
        break;

      case 'START_PICKER':
        startPicker(message.pointIndex);
        sendResponse({ success: true });
        break;

      case 'START_AUTOMATION':
        runAutomation(message.config, message.prompts);
        sendResponse({ success: true });
        break;

      case 'STOP_AUTOMATION':
        stopAutomation();
        sendResponse({ success: true });
        break;

      case 'TOGGLE_PAUSE':
        togglePause(message.paused);
        sendResponse({ success: true });
        break;

      default:
        break;
    }
    return true;
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      console.log('[Prompt Injector] Content script initialized (after DOMContentLoaded) at', new Date().toISOString());
    });
  } else {
    console.log('[Prompt Injector] Content script initialized immediately at', new Date().toISOString());
  }
  
  console.log('[Prompt Injector] Content script loaded successfully');
})();
