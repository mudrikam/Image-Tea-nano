class PromptInjector {
  constructor() {
    this.prompts = [];
    this.currentIndex = 0;
    this.isRunning = false;
    this.isPaused = false;
    this.startTime = null;
    this.pauseAccum = 0;
    this.pauseStart = null;
    this.statsInterval = null;
    this.loadedFiles = [];
    this.currentTabId = null;
    this.dynamicPointCounter = 1;
    this.db = null;
    this.currentUrlKey = null;
    this.saveSettingsDebounceTimer = null;
    this.savePromptsDebounceTimer = null;
    this.isLoadingSettings = false;
    
    this.initDB().then(async () => {
      this.initElements();
      await this.updateCurrentUrl();
      this.initEventListeners();
      this.updateManualCount();
      this.generator = new PromptGenerator(this);
    });
  }

  getUrlKey(urlString) {
    try {
      const url = new URL(urlString);
      return `site:${url.hostname}`;
    } catch (e) {
      return 'site:default';
    }
  }

  async initDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('PromptInjectorDB', 1);
      
      request.onerror = () => {
        console.error('Failed to open IndexedDB');
        resolve();
      };
      
      request.onsuccess = (event) => {
        this.db = event.target.result;
        console.log('[DB] IndexedDB opened successfully');
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains('settings')) {
          db.createObjectStore('settings', { keyPath: 'id' });
        }
        console.log('[DB] IndexedDB upgraded');
      };
    });
  }

  async saveToIndexedDB(key, value) {
    if (!this.db) return;
    return new Promise((resolve) => {
      const transaction = this.db.transaction(['settings'], 'readwrite');
      const store = transaction.objectStore('settings');
      store.put({ id: key, value: value });
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => resolve();
    });
  }

  async loadFromIndexedDB(key) {
    if (!this.db) return null;
    return new Promise((resolve) => {
      const transaction = this.db.transaction(['settings'], 'readonly');
      const store = transaction.objectStore('settings');
      const request = store.get(key);
      request.onsuccess = () => resolve(request.result?.value || null);
      request.onerror = () => resolve(null);
    });
  }

  async deleteFromIndexedDB(key) {
    if (!this.db) return false;
    return new Promise((resolve) => {
      const transaction = this.db.transaction(['settings'], 'readwrite');
      const store = transaction.objectStore('settings');
      const request = store.delete(key);
      transaction.oncomplete = () => resolve(true);
      transaction.onerror = () => resolve(false);
    });
  }

  async savePromptsToStorage() {
    if (!this.currentUrlKey) {
      await this.updateCurrentUrl();
      if (!this.currentUrlKey) return;
    }
    
    const text = this.elements.manualPromptInput.value;
    console.log(`[Prompts] Saving ${text.length} chars to ${this.currentUrlKey}`);
    await this.saveToIndexedDB(`prompts:${this.currentUrlKey}`, text);
  }

  debouncedSavePrompts() {
    if (this.savePromptsDebounceTimer) {
      clearTimeout(this.savePromptsDebounceTimer);
    }
    this.savePromptsDebounceTimer = setTimeout(() => {
      this.savePromptsToStorage();
    }, 500);
  }

  updateMonitoringState() {
    const isMonitoring = this.elements.autoDownload.monitoring.checked;
    const monitoringLabel = this.elements.autoDownload.monitoring.parentElement.querySelector('label');
    
    this.elements.autoDownload.delay.disabled = isMonitoring;
    
    if (isMonitoring) {
      monitoringLabel.style.color = '#ff8800';
      this.elements.autoDownload.delay.style.opacity = '0.5';
      if (this.elements && this.elements.statStatus) {
        if (this.isRunning) {
          this.elements.statStatus.textContent = 'Monitoring';
          this.elements.statStatus.style.color = '#ff8800';
        } else if (this.elements.statStatus.textContent === 'Monitoring') {
          this.elements.statStatus.textContent = 'Idle';
          this.elements.statStatus.style.color = '';
        }
      }
    } else {
      monitoringLabel.style.color = '';
      this.elements.autoDownload.delay.style.opacity = '1';
      if (this.elements && this.elements.statStatus) {
        this.elements.statStatus.style.color = '';
        if (!this.isRunning) this.elements.statStatus.textContent = 'Idle';
      }
    }
  }

  updateAutoContinueState() {
    if (!this.elements.autoContinue || !this.elements.promptDelay) return;
    
    const isAutoContinue = this.elements.autoContinue.checked;
    const label = this.elements.autoContinue.parentElement.querySelector('label');
    
    this.elements.promptDelay.disabled = isAutoContinue;
    
    if (isAutoContinue) {
      label.style.color = '#ff8800';
      this.elements.promptDelay.style.opacity = '0.5';
    } else {
      label.style.color = '';
      this.elements.promptDelay.style.opacity = '1';
    }
  }

  async loadPromptsFromStorage() {
    if (!this.currentUrlKey) return;
    console.log(`[Prompts] Loading from ${this.currentUrlKey}`);
    const savedPrompts = await this.loadFromIndexedDB(`prompts:${this.currentUrlKey}`);
    console.log(`[Prompts] Loaded ${savedPrompts ? savedPrompts.length : 0} chars`);
    if (savedPrompts !== null && savedPrompts !== undefined) {
      this.elements.manualPromptInput.value = savedPrompts;
      this.updateManualCount();
    } else {
      console.log('[Prompts] No saved prompts for this site; leaving textarea unchanged');
    }
  }

  initElements() {
    this.elements = {
      point1: {
        enabled: document.getElementById('point1-enabled'),
        selector: document.getElementById('point1-selector'),
        delay: document.getElementById('point1-delay'),
        picker: document.querySelector('.picker-btn[data-point="1"]'),
        htmlBtn: document.querySelector('.html-btn[data-point="1"]')
      },
      autoDownload: {
        enabled: document.getElementById('auto-download-enabled'),
        count: document.getElementById('auto-download-count'),
        delay: document.getElementById('auto-download-delay'),
        monitoring: document.getElementById('auto-download-monitoring'),
        pattern: document.getElementById('auto-download-pattern'),
        extension: document.getElementById('auto-download-extension'),
        prefix: document.getElementById('auto-download-prefix'),
        note: document.getElementById('download-note')
      },
      tabs: {
        nav: document.querySelectorAll('.tab-btn'),
        panels: document.querySelectorAll('.tab-panel')
      },
      dynamicContainer: document.getElementById('dynamic-points-container'),
      btnAddPoint: document.getElementById('btn-add-point'),
      btnRun: document.getElementById('btn-run'),
      btnPause: document.getElementById('btn-pause'),
      btnStop: document.getElementById('btn-stop'),
      btnLoadCsv: document.getElementById('btn-load-csv'),
      btnLoadManual: document.getElementById('btn-load-manual'),
      btnClearManual: document.getElementById('btn-clear-manual'),
      btnClear: document.getElementById('btn-clear'),
      btnHelp: document.getElementById('btn-help'),
      btnRefreshUrl: document.getElementById('btn-refresh-url'),
      currentUrl: document.getElementById('current-url'),
      fileLabel: document.getElementById('file-label'),
      dropZone: document.getElementById('drop-zone'),
      manualPromptInput: document.getElementById('manual-prompt-input'),
      promptDisplay: document.getElementById('prompt-display'),
      manualCount: document.getElementById('manual-count'),
      progressBar: document.getElementById('progress-bar'),
      progressText: document.getElementById('progress-text'),
      randomDelay: document.getElementById('random-delay'),
      promptDelay: document.getElementById('prompt-delay'),
      autoContinue: document.getElementById('auto-continue-enabled'),
      delayText: document.getElementById('delay-text'),
      statEta: document.getElementById('stat-eta'),
      statProgress: document.getElementById('stat-progress'),
      statRemaining: document.getElementById('stat-remaining'),
      statSpeed: document.getElementById('stat-speed'),
      statElapsed: document.getElementById('stat-elapsed'),
      statStatus: document.getElementById('stat-status'),
      logsContainer: document.getElementById('logs-container'),
      btnClearLogs: document.getElementById('btn-clear-logs')
    };

    if (this.elements.btnClearLogs) {
      this.elements.btnClearLogs.classList.add('btn-clear-logs');
      this.elements.btnClearLogs.title = 'Clear Logs';
      this.elements.btnClearLogs.setAttribute('aria-label', 'Clear Logs');
    }

    this.dynamicPoints = [];
  }

  initEventListeners() {
    this.elements.tabs.nav.forEach(btn => {
      btn.addEventListener('click', (e) => this.switchTab(e.target.closest('.tab-btn').dataset.tab));
    });

    this.elements.btnRun.addEventListener('click', () => this.run());
    this.elements.btnPause.addEventListener('click', () => this.togglePause());
    this.elements.btnStop.addEventListener('click', () => this.stop());
    this.elements.btnLoadCsv.addEventListener('click', () => this.loadFile());
    this.elements.btnLoadManual.addEventListener('click', () => this.loadManualInput());
    if (this.elements.btnClearManual) {
      this.elements.btnClearManual.addEventListener('click', () => this.clearData());
    }
    this.elements.btnClear.addEventListener('click', () => this.clearData());
    this.elements.btnRefreshUrl.addEventListener('click', () => this.forceRefreshUrl());
    this.elements.btnAddPoint.addEventListener('click', () => this.addDynamicPoint());

    if (this.elements.btnClearLogs) {
      this.elements.btnClearLogs.addEventListener('click', () => this.clearLogs());
    }

    this.elements.manualPromptInput.addEventListener('input', () => {
      this.updateManualCount();
      this.debouncedSavePrompts();
    });

    this.elements.point1.picker.addEventListener('click', () => this.pickElement(1));
    this.elements.point1.htmlBtn.addEventListener('click', () => this.htmlToSelector(1));
    this.elements.point1.selector.addEventListener('change', () => this.debouncedSaveSettings());
    this.elements.point1.selector.addEventListener('input', () => this.debouncedSaveSettings());
    this.elements.point1.delay.addEventListener('change', () => this.debouncedSaveSettings());
    this.elements.point1.delay.addEventListener('input', () => this.debouncedSaveSettings());
    this.elements.point1.enabled.addEventListener('change', () => this.debouncedSaveSettings());

    this.elements.autoDownload.enabled.addEventListener('change', () => this.debouncedSaveSettings());
    this.elements.autoDownload.count.addEventListener('change', () => this.debouncedSaveSettings());
    this.elements.autoDownload.delay.addEventListener('change', () => this.debouncedSaveSettings());
    this.elements.autoDownload.delay.addEventListener('input', () => this.debouncedSaveSettings());
    this.elements.autoDownload.monitoring.addEventListener('change', () => {
      this.updateMonitoringState();
      this.debouncedSaveSettings();
    });
    this.elements.autoDownload.pattern.addEventListener('change', () => this.debouncedSaveSettings());
    this.elements.autoDownload.pattern.addEventListener('input', () => this.debouncedSaveSettings());
    this.elements.autoDownload.extension.addEventListener('change', () => this.debouncedSaveSettings());
    this.elements.autoDownload.prefix.addEventListener('change', () => this.debouncedSaveSettings());
    this.elements.autoDownload.prefix.addEventListener('input', () => this.debouncedSaveSettings());

    if (this.elements.randomDelay) {
      this.elements.randomDelay.addEventListener('change', () => this.debouncedSaveSettings());
      this.elements.randomDelay.addEventListener('input', () => this.debouncedSaveSettings());
    }
    if (this.elements.promptDelay) {
      this.elements.promptDelay.addEventListener('change', () => this.debouncedSaveSettings());
      this.elements.promptDelay.addEventListener('input', () => this.debouncedSaveSettings());
    }
    if (this.elements.autoContinue) {
      this.elements.autoContinue.addEventListener('change', () => {
        this.updateAutoContinueState();
        this.debouncedSaveSettings();
    });

    const patternPickerBtn = document.getElementById('btn-pick-pattern');
    if (patternPickerBtn) {
      patternPickerBtn.addEventListener('click', () => this.pickPattern());
    }
  }

    this.elements.dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.elements.dropZone.classList.add('drag-over');
    });

    this.elements.dropZone.addEventListener('dragleave', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.elements.dropZone.classList.remove('drag-over');
    });

    this.elements.dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.elements.dropZone.classList.remove('drag-over');
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        this.processFiles(files);
      }
    });

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      // ELEMENT_PICKED must be handled immediately and not blocked by session/origin checks
      if (message && message.type === 'ELEMENT_PICKED') {
        if (message.pointIndex !== undefined && message.selector) {
          this.onElementPicked(message.pointIndex, message.selector);
        }
        return;
      }

      const originTab = sender && sender.tab ? sender.tab.id : null;
      const relayTypes = ['ELEMENT_PICKED','AUTOMATION_PROGRESS','AUTOMATION_FINISHED','AUTOMATION_STATUS','AUTOMATION_ERROR','DOWNLOAD_COUNTDOWN','DOWNLOAD_SCANNING','DOWNLOAD_DONE'];
      if (originTab && originTab !== this.currentTabId) return;
      if (!originTab && relayTypes.includes(message.type)) return;
      if (relayTypes.includes(message.type)) {
        if (!message.sessionId || message.sessionId !== this.currentSessionId) return;
      }
      if (!this._lastMessageTimestamps) this._lastMessageTimestamps = new Map();
      const key = message.type + '::' + JSON.stringify(message);
      const now = Date.now();
      const last = this._lastMessageTimestamps.get(key) || 0;
      if (now - last < 700) return;
      this._lastMessageTimestamps.set(key, now);

      if (message.type === 'AUTOMATION_PROGRESS') {
        if (!this.isRunning) return;
        this.onAutomationProgress(message.done, message.total);
        this.addLog(`Progress: ${message.done}/${message.total} prompts completed`, 'info');
      } else if (message.type === 'AUTOMATION_FINISHED') {
        this.onAutomationFinished();
        this.currentSessionId = null;
        this.elements.autoDownload.note.textContent = 'Matches images/videos starting with pattern';
        this.elements.autoDownload.note.style.color = '';
        this.addLog('Automation finished', 'success');
      } else if (message.type === 'AUTOMATION_STATUS') {
        if (!this.isRunning) return;
        this.updateDelayText(message.text);
        if (!this.elements.autoDownload.monitoring.checked) {
          this.elements.statStatus.textContent = 'Running';
          this.elements.statStatus.style.color = '';
        }
        this.addLog(message.text, 'status');
      } else if (message.type === 'DOWNLOAD_COUNTDOWN') {
        if (!this.isRunning) return;
        const mode = message.mode === 'monitoring' ? 'Monitoring' : 'Waiting';
        this.elements.autoDownload.note.textContent = `${mode}: ${message.seconds}s`;
        this.elements.autoDownload.note.style.color = '#ff8800';
        if (!this.elements.autoDownload.monitoring.checked) {
          this.elements.statStatus.textContent = 'Waiting';
          this.elements.statStatus.style.color = '#ff8800';
        }
      } else if (message.type === 'DOWNLOAD_SCANNING') {
        if (!this.isRunning) return;
        this.elements.autoDownload.note.textContent = 'Scanning for new content...';
        this.elements.autoDownload.note.style.color = '#ff8800';
        if (!this.elements.autoDownload.monitoring.checked) {
          this.elements.statStatus.textContent = 'Scanning';
          this.elements.statStatus.style.color = '#ff8800';
        }
        if (message.found !== undefined) this.addLog(`Scanning: found ${message.found}/${message.required} items`, 'info');
      } else if (message.type === 'DOWNLOAD_DONE') {
        if (!this.isRunning) return;
        this.elements.autoDownload.note.textContent = `Downloaded ${message.count} item(s)`;
        this.elements.autoDownload.note.style.color = '#00cc66';
        if (!this.elements.autoDownload.monitoring.checked) {
          this.elements.statStatus.textContent = 'Downloaded';
          this.elements.statStatus.style.color = '#00cc66';
        }
        this.addLog(`Downloaded ${message.count} item(s)`, 'download');
      } else if (message.type === 'AUTOMATION_ERROR') {
        this.isRunning = false;
        this.isPaused = false;
        this.currentIndex = 0;
        this.setRunMode(false);
        this.stopStatsTimer();
        this.resetStats();
        this.resetPromptDisplay();
        this.currentSessionId = null;
        this.elements.statStatus.textContent = 'Error';
        this.elements.statStatus.style.color = '#ff3333';
        this.updateDelayText(message.message);
        this.updateProgress(0, this.prompts.length);
        this.elements.autoDownload.note.textContent = message.message;
        this.elements.autoDownload.note.style.color = '#ff3333';
        this.addLog(`ERROR: ${message.message}`, 'error');
      }
    });

    chrome.tabs.onActivated.addListener(async () => {
      console.log('[Event] Tab activated, reloading settings');
      await this.updateCurrentUrl();
    });

    chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
      if (changeInfo.status === 'complete') {
        console.log('[Event] Tab updated (complete), reloading settings');
        await this.updateCurrentUrl();
      }
    });

    document.addEventListener('visibilitychange', async () => {
      if (!document.hidden) {
        console.log('[Event] Sidepanel visible, force reloading settings');
        await this.updateCurrentUrl();
      }
    });
  }

  switchTab(tabName) {
    this.elements.tabs.nav.forEach(btn => {
      if (btn.dataset.tab === tabName) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    this.elements.tabs.panels.forEach(panel => {
      if (panel.dataset.panel === tabName) {
        panel.classList.add('active');
      } else {
        panel.classList.remove('active');
      }
    });
  }

  async updateCurrentUrl() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (tab && tab.url) {
        this.currentTabId = tab.id;
        const url = new URL(tab.url);
        const displayUrl = url.hostname;
        this.elements.currentUrl.textContent = displayUrl;
        this.elements.currentUrl.title = tab.url;
        
        const newUrlKey = this.getUrlKey(tab.url);
        const urlKeyChanged = newUrlKey !== this.currentUrlKey;
        
        console.log(`[URL] Current: ${this.currentUrlKey}, New: ${newUrlKey}, Changed: ${urlKeyChanged}`);
        
        if (urlKeyChanged) {
          this.currentUrlKey = newUrlKey;
          
          while (this.dynamicPoints.length > 0) {
            const point = this.dynamicPoints.pop();
            point.element.remove();
          }
          this.dynamicPointCounter = 1;
        } else {
          this.currentUrlKey = newUrlKey;
        }
        
        console.log(`[URL] Force reloading settings for: ${url.hostname}`);
        await this.loadSettings();
        await this.loadPromptsFromStorage();
        
        if (urlKeyChanged) {
          this.addLog(`Loaded settings for: ${url.hostname}`, 'info');
        }
      } else {
        this.elements.currentUrl.textContent = 'No page loaded';
        this.elements.currentUrl.title = '';
      }
    } catch (err) {
      console.error('Failed to get current URL:', err);
      this.elements.currentUrl.textContent = 'Error getting URL';
    }
  }

  async forceRefreshUrl() {
    console.log('[Refresh] forceRefreshUrl called');
    this.elements.currentUrl.textContent = 'Updating...';
    try {
      const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      console.log('[Refresh] Found tabs:', tabs.length);
      if (tabs && tabs.length > 0) {
        const tab = tabs[0];
        console.log('[Refresh] Tab:', tab.id, tab.url);
        this.currentTabId = tab.id;
        if (tab.url) {
          try {
            const url = new URL(tab.url);
            const displayUrl = url.hostname;
            this.elements.currentUrl.textContent = displayUrl;
            this.elements.currentUrl.title = tab.url;
            console.log('[Refresh] URL updated to:', displayUrl);
          } catch (e) {
            this.elements.currentUrl.textContent = tab.url.substring(0, 40);
            this.elements.currentUrl.title = tab.url;
          }
        } else {
          this.elements.currentUrl.textContent = 'No URL available';
        }
      } else {
        this.elements.currentUrl.textContent = 'No active tab';
      }
    } catch (err) {
      console.error('[Refresh] Failed to refresh URL:', err);
      this.elements.currentUrl.textContent = 'Error: ' + err.message;
    }
  }

  async htmlToSelector(pointId) {
    console.log('[HTML] htmlToSelector called with pointId:', pointId, typeof pointId);
    const html = prompt('Paste raw HTML element here:\n\n(Right-click element in DevTools → Copy → Copy element)');
    if (!html || !html.trim()) return;

    const selector = this.parseHtmlToSelector(html.trim());
    console.log('[HTML] Generated selector:', selector);
    if (!selector) {
      alert('Could not generate selector from that HTML.');
      return;
    }

    if (pointId === 1) {
      this.elements.point1.selector.value = selector;
    } else {
      const dynamicPoint = this.dynamicPoints.find(p => p.id === pointId);
      console.log('[HTML] Found dynamic point:', dynamicPoint);
      if (dynamicPoint) {
        dynamicPoint.selector.value = selector;
      }
    }
    this.debouncedSaveSettings();
  }

  parseHtmlToSelector(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const element = doc.body.firstElementChild;
    
    if (!element) return null;

    if (element.id) {
      return '#' + CSS.escape(element.id);
    }

    if (element.name) {
      return `[name="${CSS.escape(element.name)}"]`;
    }

    const priorityAttrs = ['data-testid', 'data-id', 'aria-label', 'role', 'placeholder', 'title'];
    for (const attr of priorityAttrs) {
      const value = element.getAttribute(attr);
      if (value && value.length < 60) {
        return `[${attr}="${CSS.escape(value)}"]`;
      }
    }

    const tagName = element.tagName.toLowerCase();
    const classes = Array.from(element.classList || []).filter(c => c && c.length < 40);
    if (classes.length > 0 && classes.length <= 3) {
      return tagName + '.' + classes.map(c => CSS.escape(c)).join('.');
    }

    if (classes.length > 0) {
      return '.' + CSS.escape(classes[0]);
    }

    return tagName;
  }

  addDynamicPoint(savedData = null) {
    this.dynamicPointCounter++;
    const pointId = this.dynamicPointCounter;
    const pointNumber = this.dynamicPoints.length + 2;

    const colors = ['#00cc88', '#4488ff', '#cc66ff', '#ff6688', '#ffaa00'];
    const colorIndex = (pointNumber - 2) % colors.length;
    const pointColor = colors[colorIndex];

    const pointRow = document.createElement('div');
    pointRow.className = 'point-row point-dynamic';
    pointRow.dataset.pointId = pointId;
    pointRow.innerHTML = `
      <button class="btn-remove-point" title="Remove this point">&times;</button>
      <div class="point-header">
        <input type="checkbox" class="point-enabled" ${savedData ? (savedData.enabled ? 'checked' : '') : 'checked'}>
        <span class="point-label" style="color: ${pointColor};">Point ${pointNumber}</span>
        <span class="point-note">(click)</span>
      </div>
      <div class="point-controls">
        <input type="text" class="selector-input point-selector" placeholder="CSS selector..." value="">
        <button class="picker-btn" title="Pick element from page">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M20.71,5.63l-2.34-2.34a1,1,0,0,0-1.41,0L3,17.25V21H6.75L20.71,7a1,1,0,0,0,0-1.41ZM6.17,19H5V17.83L16.93,5.9l1.17,1.17Z"/></svg>
        </button>
        <button class="html-btn" title="Selector from HTML">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12,17.56L16.07,16.43L16.62,10.33H9.38L9.2,8.3H16.8L17,6.31H7L7.56,12.32H14.45L14.22,14.9L12,15.5L9.78,14.9L9.64,13.24H7.64L7.93,16.43L12,17.56M4.07,3H19.93L18.5,19.2L12,21L5.5,19.2L4.07,3Z"/></svg>
        </button>
      </div>
      <div class="delay-row">
        <label>Delay:</label>
        <input type="number" class="delay-input point-delay" value="${savedData?.delay || '1.0'}" min="0" step="0.1">
        <span class="unit">s</span>
      </div>
    `;

    const deleteBtn = pointRow.querySelector('.btn-remove-point');
    const pickerBtn = pointRow.querySelector('.picker-btn');
    const htmlBtn = pointRow.querySelector('.html-btn');
    const enabledCheckbox = pointRow.querySelector('.point-enabled');
    const selectorInput = pointRow.querySelector('.point-selector');
    const delayInput = pointRow.querySelector('.point-delay');

    deleteBtn.addEventListener('click', () => this.deleteDynamicPoint(pointId));
    pickerBtn.addEventListener('click', () => this.pickElement(pointId));
    htmlBtn.addEventListener('click', () => this.htmlToSelector(pointId));
    enabledCheckbox.addEventListener('change', () => this.debouncedSaveSettings());
    if (savedData?.selector) {
      selectorInput.value = savedData.selector;
    }
    selectorInput.addEventListener('change', () => this.debouncedSaveSettings());
    selectorInput.addEventListener('input', () => this.debouncedSaveSettings());
    delayInput.addEventListener('change', () => this.debouncedSaveSettings());
    delayInput.addEventListener('input', () => this.debouncedSaveSettings());

    this.elements.dynamicContainer.appendChild(pointRow);

    this.dynamicPoints.push({
      id: pointId,
      element: pointRow,
      enabled: enabledCheckbox,
      selector: selectorInput,
      delay: delayInput,
      picker: pickerBtn,
      htmlBtn: htmlBtn
    });

    this.updatePointNumbers();
    
    if (!this.isLoadingSettings) {
      console.log(`[Dynamic Point] Auto-saving after adding point ${pointId}`);
      this.debouncedSaveSettings();
    } else {
      console.log(`[Dynamic Point] Skipping auto-save during load for point ${pointId}`);
    }
  }

  deleteDynamicPoint(pointId) {
    const index = this.dynamicPoints.findIndex(p => p.id === pointId);
    if (index !== -1) {
      this.dynamicPoints[index].element.remove();
      this.dynamicPoints.splice(index, 1);
      this.updatePointNumbers();
      this.debouncedSaveSettings();
    }
  }

  updatePointNumbers() {
    const colors = ['#00cc88', '#4488ff', '#cc66ff', '#ff6688', '#ffaa00'];
    this.dynamicPoints.forEach((point, idx) => {
      const label = point.element.querySelector('.point-label');
      if (label) {
        label.textContent = `Point ${idx + 2}`;
        label.style.color = colors[idx % colors.length];
      }
    });
  }

  async ensureContentScriptInjected(tabId) {
    const tryPing = () => {
      return new Promise((resolve) => {
        try {
          chrome.tabs.sendMessage(tabId, { type: 'PING' }, (response) => {
            if (chrome.runtime.lastError) {
              console.log('[Ping] Error:', chrome.runtime.lastError.message);
              resolve(false);
            } else if (response && response.ready) {
              console.log('[Ping] Content script ready');
              resolve(true);
            } else {
              console.log('[Ping] No valid response');
              resolve(false);
            }
          });
        } catch (err) {
          console.log('[Ping] Exception:', err);
          resolve(false);
        }
      });
    };

    const tryInject = async () => {
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tabId },
          files: ['content.js']
        });
        console.log('[Inject] Successfully injected content script');
        return true;
      } catch (err) {
        console.warn('[Inject] Failed:', err.message);
        return false;
      }
    };

    if (await tryPing()) {
      return true;
    }

    console.log('[Inject] Content script not found, attempting injection');
    await tryInject();
    await new Promise(resolve => setTimeout(resolve, 500));

    for (let attempt = 0; attempt < 3; attempt++) {
      console.log(`[Ping] Attempt ${attempt + 1}/3`);
      if (await tryPing()) {
        return true;
      }
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    console.error('[Error] Content script not responding after injection and 3 ping attempts');
    return false;
  }

  async pickElement(pointId) {
    let picker;
    if (pointId === 1) {
      picker = this.elements.point1.picker;
    } else {
      const dynamicPoint = this.dynamicPoints.find(p => p.id === pointId);
      if (dynamicPoint) {
        picker = dynamicPoint.picker;
      }
    }

    if (!picker) {
      console.error('Picker not found for point:', pointId);
      return;
    }

    picker.classList.add('active');

    try {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      
      if (!tab || !tab.url) {
        throw new Error('No active tab found');
      }

      if (tab.url.startsWith('chrome://') || 
          tab.url.startsWith('chrome-extension://') || 
          tab.url.startsWith('edge://') ||
          tab.url.startsWith('about:')) {
        throw new Error('Cannot run on browser internal pages');
      }

      if (tab.status !== 'complete') {
        throw new Error('Page is still loading, please wait');
      }

      const injected = await this.ensureContentScriptInjected(tab.id);
      if (!injected) {
        throw new Error('Content script not responding after injection.\n\nSolution:\n1. Refresh the page (Ctrl+R or F5)\n2. If still failing, close and reopen the tab');
      }

      chrome.tabs.sendMessage(tab.id, {
        type: 'START_PICKER',
        pointIndex: pointId
      }, (response) => {
        if (chrome.runtime.lastError) {
          console.error('START_PICKER error:', chrome.runtime.lastError);
          picker.classList.remove('active');
          alert('Failed to start picker.\n\nTry refreshing the page first.');
          return;
        }

        if (response && response.started === false) {
          console.warn('START_PICKER explicitly not started in frame, response:', response);
          picker.classList.remove('active');
          alert('Picker could not start in the main page frame. Try focusing the page, reloading, or opening the page in a normal tab (not an internal/embedded frame).');
        }
      });
    } catch (err) {
      console.error('Failed to start picker:', err);
      picker.classList.remove('active');
      
      let message = 'Cannot start picker.\n\n';
      if (err.message.includes('internal pages')) {
        message += 'You cannot use the picker on chrome:// or extension pages.';
      } else if (err.message.includes('loading')) {
        message += 'Page is still loading. Wait until it fully loads.';
      } else if (err.message.includes('not responding')) {
        message += err.message + '\n\nOr try opening a regular web page.';
      } else {
        message += 'Make sure:\n- Page is fully loaded\n- Not a chrome:// or extension page\n- Refresh the page if needed';
      }
      
      alert(message);
    }
  }

  async pickPattern() {
    let picker = document.getElementById('btn-pick-pattern');
    if (!picker) return;

    picker.classList.add('active');

    try {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (!tab || !tab.url) {
        throw new Error('No active tab found');
      }

      if (tab.url.startsWith('chrome://') ||
          tab.url.startsWith('chrome-extension://') ||
          tab.url.startsWith('edge://') ||
          tab.url.startsWith('about:')) {
        throw new Error('Cannot run on browser internal pages');
      }

      if (tab.status !== 'complete') {
        throw new Error('Page is still loading, please wait');
      }

      const injected = await this.ensureContentScriptInjected(tab.id);
      if (!injected) {
        throw new Error('Content script not responding after injection.\n\nSolution:\n1. Refresh the page (Ctrl+R or F5)\n2. If still failing, close and reopen the tab');
      }

      chrome.tabs.sendMessage(tab.id, {
        type: 'START_PATTERN_PICKER'
      }, (response) => {
        if (chrome.runtime.lastError) {
          console.error('START_PATTERN_PICKER error:', chrome.runtime.lastError);
          picker.classList.remove('active');
          alert('Failed to start pattern picker.\n\nTry refreshing the page first.');
          return;
        }

        if (response && response.pattern) {
          this.elements.autoDownload.pattern.value = response.pattern;
          this.debouncedSaveSettings();
          picker.classList.remove('active');
        } else {
          picker.classList.remove('active');
        }
      });
    } catch (err) {
      console.error('Failed to start pattern picker:', err);
      picker.classList.remove('active');
      alert('Cannot start pattern picker.\n\n' + err.message);
    }
  }

  onElementPicked(pointId, selector) {
    if (pointId === 1) {
      this.elements.point1.selector.value = selector;
      this.elements.point1.picker.classList.remove('active');
    } else {
      const dynamicPoint = this.dynamicPoints.find(p => p.id === pointId);
      if (dynamicPoint) {
        dynamicPoint.selector.value = selector;
        dynamicPoint.picker.classList.remove('active');
      }
    }
    this.debouncedSaveSettings();
  }

  loadFile() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.txt';
    input.multiple = true;
    input.onchange = (e) => {
      if (e.target.files.length > 0) {
        this.processFiles(e.target.files);
      }
    };
    input.click();
  }

  async processFiles(files) {
    let allPrompts = [];
    let fileInfos = [];

    for (const file of files) {
      const text = await file.text();
      const ext = file.name.split('.').pop().toLowerCase();
      let prompts = [];

      if (ext === 'csv') {
        prompts = this.parseCSV(text);
      } else if (ext === 'txt') {
        prompts = this.parseTXT(text);
      }

      if (prompts.length > 0) {
        allPrompts = allPrompts.concat(prompts);
        fileInfos.push({
          name: file.name,
          type: ext.toUpperCase(),
          count: prompts.length
        });
      }
    }

    if (allPrompts.length > 0) {
      this.elements.manualPromptInput.value = allPrompts.join('\n---\n');
      this.prompts = allPrompts;
      this.loadedFiles = fileInfos;
      await this.savePromptsToStorage();
    }

    this.updateFileLabel();
    this.updateProgress(0, this.prompts.length);
    this.updateManualCount();
  }

  async loadManualInput() {
    const text = this.elements.manualPromptInput.value.trim();
    if (!text) {
      alert('Textarea is empty. Type some prompts first.');
      return;
    }

    const prompts = this.parseManualInput(text);
    if (prompts.length === 0) {
      alert('No valid prompts found.');
      return;
    }

    this.prompts = prompts;
    this.loadedFiles = [{
      name: 'Manual Input',
      type: 'MANUAL',
      count: prompts.length
    }];

    this.updateFileLabel();
    this.updateProgress(0, this.prompts.length);
    this.updateManualCount();
    await this.savePromptsToStorage();
  }

  parseManualInput(text) {
    const prompts = [];
    
    if (text.includes('---')) {
      const blocks = text.split(/\n?---\n?/);
      blocks.forEach(block => {
        const trimmed = block.trim();
        if (trimmed) {
          prompts.push(trimmed);
        }
      });
      
      if (prompts.length > 0) {
        return prompts;
      }
    }
    
    if (/#\d+\s+/.test(text)) {
      const regex = /#\d+\s+([^#]+)/g;
      let match;
      while ((match = regex.exec(text)) !== null) {
        const prompt = match[1].trim();
        if (prompt) {
          prompts.push(prompt);
        }
      }
      
      if (prompts.length > 0) {
        return prompts;
      }
    }
    
    if (/^\d+\.\s+/m.test(text)) {
      const regex = /\d+\.\s+([^\n]+(?:\n(?!\d+\.\s)[^\n]+)*)/g;
      let match;
      while ((match = regex.exec(text)) !== null) {
        const prompt = match[1].trim();
        if (prompt) {
          prompts.push(prompt);
        }
      }
      
      if (prompts.length > 0) {
        return prompts;
      }
    }
    
    if (/\n\s*\n/.test(text)) {
      const blocks = text.split(/\n\s*\n+/);
      blocks.forEach(block => {
        const trimmed = block.trim();
        if (trimmed) {
          prompts.push(trimmed);
        }
      });
      
      if (prompts.length > 0) {
        return prompts;
      }
    }
    
    const lines = text.split('\n');
    lines.forEach(line => {
      const trimmed = line.trim();
      if (trimmed) {
        prompts.push(trimmed);
      }
    });

    return prompts;
  }

  updateManualCount() {
    const text = this.elements.manualPromptInput.value.trim();
    if (!text) {
      this.elements.manualCount.textContent = '0 prompts';
      return;
    }

    const prompts = this.parseManualInput(text);
    this.elements.manualCount.textContent = `${prompts.length} prompts`;
  }

  parseCSV(text) {
    const lines = text.split('\n');
    const prompts = [];
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        const cells = this.parseCSVLine(trimmed);
        const joined = cells.map(c => c.trim()).filter(c => c).join(', ');
        if (joined) {
          prompts.push(joined);
        }
      }
    }
    
    return prompts;
  }

  parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === ',' && !inQuotes) {
        result.push(current);
        current = '';
      } else {
        current += char;
      }
    }
    
    result.push(current);
    return result;
  }

  parseTXT(text) {
    const lines = text.split('\n');
    const prompts = [];
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        prompts.push(trimmed);
      }
    }
    
    return prompts;
  }

  updateFileLabel() {
    if (this.loadedFiles.length === 0) {
      this.elements.fileLabel.textContent = 'No file loaded';
    } else {
      const total = this.prompts.length;
      const fileNames = this.loadedFiles.map(f => `${f.name} (${f.count})`).join(', ');
      this.elements.fileLabel.textContent = `${total} prompts from: ${fileNames}`;
    }
  }

  async clearData() {
    this.prompts = [];
    this.loadedFiles = [];
    this.currentIndex = 0;
    this.elements.manualPromptInput.value = '';
    this.updateFileLabel();
    this.updateProgress(0, 0);
    this.updateManualCount();
    this.resetStats();
    if (this.currentUrlKey) {
      await this.deleteFromIndexedDB(`prompts:${this.currentUrlKey}`);
      console.log(`[Prompts] Deleted saved prompts for ${this.currentUrlKey}`);
    }
  }

  async run() {
    const manualText = this.elements.manualPromptInput.value.trim();
    if (manualText) {
      const freshPrompts = this.parseManualInput(manualText);
      if (freshPrompts.length > 0) {
        this.prompts = freshPrompts;
        this.loadedFiles = [{
          name: 'Manual Input (Fresh)',
          type: 'MANUAL',
          count: freshPrompts.length
        }];
        this.updateFileLabel();
      } else {
        this.prompts = [];
      }
    } else {
      this.prompts = [];
    }

    if (this.prompts.length === 0) {
      alert('No prompts loaded.\n\nHow to:\n- Type prompts in the Manual Input textarea, or\n- Load a CSV/TXT file');
      return;
    }

    const config = this.buildConfig();
    if (!config.points.some(p => p.enabled)) {
      alert('At least one point must be enabled.');
      return;
    }

    this.isRunning = true;
    this.isPaused = false;
    this.currentIndex = 0;
    this.startTime = Date.now();
    this.pauseAccum = 0;
    this.pauseStart = null;

    this.setRunMode(true);
    this.startStatsTimer();
    this.updatePromptDisplay(0, this.prompts.length);
    
    this.addLog(`Starting automation with ${this.prompts.length} prompts`, 'info');
    this.addLog(`Config: ${config.points.filter(p => p.enabled).length} points, autoDownload=${config.autoDownload.enabled}, monitoring=${config.autoDownload.monitoring}`, 'info');

    try {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      
      if (!tab || !tab.url) {
        throw new Error('No active tab found');
      }

      if (tab.url.startsWith('chrome://') || 
          tab.url.startsWith('chrome-extension://') || 
          tab.url.startsWith('edge://') ||
          tab.url.startsWith('about:')) {
        throw new Error('Cannot run on browser internal pages');
      }

      if (tab.status !== 'complete') {
        throw new Error('Page is still loading, please wait');
      }

      const injected = await this.ensureContentScriptInjected(tab.id);
      if (!injected) {
        throw new Error('Content script not responding.\n\nRefresh the page first.');
      }

      const sessionId = `${Date.now()}-${Math.random().toString(36).slice(2,8)}`;
      this.currentSessionId = sessionId;

      chrome.tabs.sendMessage(tab.id, {
        type: 'START_AUTOMATION',
        config: config,
        prompts: this.prompts,
        sessionId: sessionId
      }, (response) => {
        if (chrome.runtime.lastError) {
          console.error('START_AUTOMATION error:', chrome.runtime.lastError);
          this.currentSessionId = null;
          this.stop();
          alert('Failed to start automation.\n\nTry refreshing the page first.');
        }
      });
    } catch (err) {
      console.error('Failed to start automation:', err);
      this.stop();
      
      let message = 'Failed to start automation.\n\n';
      if (err.message.includes('internal pages')) {
        message += 'You cannot run automation on chrome:// or extension pages.';
      } else if (err.message.includes('loading')) {
        message += 'Page is still loading. Wait until it fully loads.';
      } else if (err.message.includes('not responding')) {
        message += err.message + '\n\nOr try opening a regular web page.';
      } else {
        message += 'Make sure:\n- Page is fully loaded\n- Not a chrome:// or extension page\n- Refresh the page if needed\n- Selected selectors are valid';
      }
      
      alert(message);
    }
  }

  buildConfig() {
    const points = [];
    
    points.push({
      index: 1,
      type: 'paste',
      enabled: this.elements.point1.enabled.checked,
      selector: this.elements.point1.selector.value.trim(),
      delay: parseFloat(this.elements.point1.delay.value) || 0
    });

    this.dynamicPoints.forEach((point, idx) => {
      points.push({
        index: point.id,
        type: 'click',
        enabled: point.enabled.checked,
        selector: point.selector.value.trim(),
        delay: parseFloat(point.delay.value) || 0
      });
    });

    return {
      points: points,
      randomDelay: this.elements.randomDelay ? (parseFloat(this.elements.randomDelay.value) || 0) : 0,
      promptDelay: this.elements.promptDelay ? (parseFloat(this.elements.promptDelay.value) || 0) : 0,
      autoContinue: this.elements.autoContinue ? this.elements.autoContinue.checked : false,
      autoDownload: {
        enabled: this.elements.autoDownload.enabled.checked,
        count: parseInt(this.elements.autoDownload.count.value) || 2,
        delay: parseInt(this.elements.autoDownload.delay.value) || 5,
        monitoring: this.elements.autoDownload.monitoring.checked,
        pattern: this.elements.autoDownload.pattern.value.trim(),
        extension: this.elements.autoDownload.extension.value || 'jpg',
        prefix: this.elements.autoDownload.prefix.value.trim() || 'Generated_Content'
      }
    };
  }

  togglePause() {
    if (!this.isRunning) return;

    this.isPaused = !this.isPaused;

    if (this.isPaused) {
      this.pauseStart = Date.now();
      this.elements.btnPause.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M8,5.14V19.14L19,12.14L8,5.14Z"/></svg>
        Resume
      `;
      this.elements.statStatus.textContent = 'Paused';
    } else {
      if (this.pauseStart) {
        this.pauseAccum += Date.now() - this.pauseStart;
        this.pauseStart = null;
      }
      this.elements.btnPause.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M14,19H18V5H14M6,19H10V5H6V19Z"/></svg>
        Pause
      `;
      if (this.elements.autoDownload && this.elements.autoDownload.monitoring && this.elements.autoDownload.monitoring.checked) {
        this.elements.statStatus.textContent = 'Monitoring';
        this.elements.statStatus.style.color = '#ff8800';
      } else {
        this.elements.statStatus.textContent = 'Running';
        this.elements.statStatus.style.color = '';
      }
    }

    // Update prompt display to reflect paused state
    this.updatePromptDisplay(this.currentIndex, this.prompts.length);

    chrome.tabs.query({ active: true, lastFocusedWindow: true }).then(([tab]) => {
      chrome.tabs.sendMessage(tab.id, {
        type: 'TOGGLE_PAUSE',
        paused: this.isPaused
      });
    });
  }

  stop() {
    this.isRunning = false;
    this.isPaused = false;
    this.currentIndex = 0;
    this.setRunMode(false);
    this.stopStatsTimer();
    this.updateProgress(0, this.prompts.length);
    this.resetStats();
    this.resetPromptDisplay();
    this.elements.statStatus.textContent = 'Stopped';
    this.updateDelayText('Stopped - Ready to start from prompt 1');

    chrome.tabs.query({ active: true, lastFocusedWindow: true }).then(([tab]) => {
      chrome.tabs.sendMessage(tab.id, { type: 'STOP_AUTOMATION', sessionId: this.currentSessionId });
      this.currentSessionId = null;
    }).catch(() => {});
  }

  setRunMode(running) {
    this.elements.btnRun.disabled = running;
    this.elements.btnPause.disabled = !running;
    this.elements.btnStop.disabled = !running;
    this.elements.btnRun.innerHTML = running ? 
      `<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M8,5.14V19.14L19,12.14L8,5.14Z"/></svg> Running...` :
      `<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M8,5.14V19.14L19,12.14L8,5.14Z"/></svg> Run`;
    
    if (running) {
      if (this.elements.autoDownload && this.elements.autoDownload.monitoring && this.elements.autoDownload.monitoring.checked) {
        this.elements.statStatus.textContent = 'Monitoring';
        this.elements.statStatus.style.color = '#ff8800';
      } else {
        this.elements.statStatus.textContent = 'Running';
        this.elements.statStatus.style.color = '';
      }
      document.body.classList.add('running');
    } else {
      document.body.classList.remove('running');
      this.elements.statStatus.textContent = 'Idle';
      this.elements.statStatus.style.color = '';
    }
  }

  onAutomationProgress(done, total) {
    this.currentIndex = done;
    this.updateProgress(done, total);
    this.updateStats(done, total);
  }

  onAutomationFinished() {
    this.isRunning = false;
    this.isPaused = false;
    this.currentIndex = 0;
    this.setRunMode(false);
    this.stopStatsTimer();
    
    this.updateProgress(0, 0);
    this.resetPromptDisplay();
    this.elements.statEta.textContent = '-';
    this.elements.statRemaining.textContent = '-';
    this.elements.statSpeed.textContent = '-';
    this.elements.statElapsed.textContent = '-';
    this.elements.statStatus.textContent = 'Completed';
    this.updateDelayText('Completed');
    
    if (this.elements.autoDownload.note) {
      this.elements.autoDownload.note.textContent = 'Matches images/videos starting with pattern';
      this.elements.autoDownload.note.style.color = '';
    }
    
    console.log('[Automation] Finished - all stats and progress reset');
  }

  updateProgress(done, total) {
    const percent = total > 0 ? (done / total) * 100 : 0;
    const percentRounded = Math.round(percent * 100) / 100;
    this.elements.progressBar.style.width = `${percentRounded}%`;

    if (percent > 2 && percent < 100) {
      this.elements.progressBar.classList.add('progress-active');
    } else {
      this.elements.progressBar.classList.remove('progress-active');
    }

    if (percentRounded > 50 && percentRounded < 100) {
      this.elements.progressText.classList.add('progress-text-dark');
    } else {
      this.elements.progressText.classList.remove('progress-text-dark');
    }

    this.elements.progressText.textContent = `${done} / ${total}`;
    this.elements.statProgress.textContent = `${done}/${total}`;
    
    // Update prompt display highlighting
    this.updatePromptDisplay(done, total);
  }

  // Update prompt display with color coding based on status
  updatePromptDisplay(currentIndex, total) {
    if (!this.elements.promptDisplay || !this.prompts || this.prompts.length === 0) {
      return;
    }

    // Show the prompt display container when running
    if (this.isRunning || this.isPaused) {
      this.elements.promptDisplay.classList.add('visible');
      this.elements.manualPromptInput.style.display = 'none';
    } else {
      this.elements.promptDisplay.classList.remove('visible');
      this.elements.manualPromptInput.style.display = '';
      return;
    }

    // Build the display HTML
    let html = '';
    this.prompts.forEach((prompt, index) => {
      let statusClass = 'prompt-pending';
      
      if (index < currentIndex) {
        // Completed prompts - darker color
        statusClass = 'prompt-completed';
      } else if (index === currentIndex) {
        // Active prompt - orange with glow
        statusClass = 'prompt-active';
      }
      
      // Escape HTML to prevent XSS
      const escapedPrompt = this.escapeHtml(prompt);
      html += `<div class="prompt-line ${statusClass}">${escapedPrompt}</div>`;
    });

    this.elements.promptDisplay.innerHTML = html;
    
    // Scroll to active prompt
    const activePrompt = this.elements.promptDisplay.querySelector('.prompt-active');
    if (activePrompt) {
      activePrompt.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // Reset prompt display when automation stops
  resetPromptDisplay() {
    if (this.elements.promptDisplay) {
      this.elements.promptDisplay.classList.remove('visible');
      this.elements.promptDisplay.innerHTML = '';
    }
    if (this.elements.manualPromptInput) {
      this.elements.manualPromptInput.style.display = '';
    }
  }

  updateDelayText(text) {
    this.elements.delayText.textContent = text;
  }

  addLog(message, type = 'info') {
    if (!this.elements.logsContainer) return;
    
    const now = new Date();
    const time = now.toTimeString().split(' ')[0];
    
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.innerHTML = `
      <span class="log-time">${time}</span>
      <span class="log-message">${this.escapeHtml(message)}</span>
    `;
    
    const placeholder = this.elements.logsContainer.querySelector('.log-entry');
    if (placeholder && placeholder.querySelector('.log-message').textContent.includes('Logs will appear')) {
      placeholder.remove();
    }
    
    this.elements.logsContainer.appendChild(entry);
    this.elements.logsContainer.scrollTop = this.elements.logsContainer.scrollHeight;
    
    if (this.elements.logsContainer.children.length > 500) {
      this.elements.logsContainer.removeChild(this.elements.logsContainer.firstChild);
    }
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  clearLogs() {
    if (!this.elements.logsContainer) return;
    
    const confirmClear = confirm('Clear all logs?');
    if (!confirmClear) return;
    
    this.elements.logsContainer.innerHTML = `
      <div class="log-entry log-info">
        <span class="log-time">--:--:--</span>
        <span class="log-message">Logs cleared. New logs will appear here...</span>
      </div>
    `;
    
    console.log('[Logs] Cleared by user');
  }

  startStatsTimer() {
    this.statsInterval = setInterval(() => {
      this.updateStats(this.currentIndex, this.prompts.length);
    }, 1000);
  }

  stopStatsTimer() {
    if (this.statsInterval) {
      clearInterval(this.statsInterval);
      this.statsInterval = null;
    }
  }

  updateStats(done, total) {
    if (!this.startTime) return;

    let elapsed = Date.now() - this.startTime - this.pauseAccum;
    if (this.pauseStart) {
      elapsed -= (Date.now() - this.pauseStart);
    }

    const elapsedSec = elapsed / 1000;
    const speed = elapsedSec > 0 ? (done / elapsedSec) * 60 : 0;
    const remaining = total - done;
    const etaSec = speed > 0 ? (remaining / speed) * 60 : 0;

    this.elements.statElapsed.textContent = this.formatDuration(elapsedSec);
    this.elements.statSpeed.textContent = `${speed.toFixed(2)}/m`;
    this.elements.statRemaining.textContent = remaining.toString();
    this.elements.statEta.textContent = this.formatDuration(etaSec);
  }

  resetStats() {
    this.elements.statEta.textContent = '-';
    this.elements.statProgress.textContent = '0/0';
    this.elements.statRemaining.textContent = '-';
    this.elements.statSpeed.textContent = '0.00/m';
    this.elements.statElapsed.textContent = '-';
    this.elements.statStatus.textContent = 'Idle';
    this.elements.statStatus.style.color = '';
    this.updateDelayText('');
  }

  formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '-';
    
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    
    if (h > 0) {
      return `${h}h ${m}m ${s}s`;
    } else if (m > 0) {
      return `${m}m ${s}s`;
    } else {
      return `${s}s`;
    }
  }

  showHelp() {
    this.switchTab('help');
  }

  debouncedSaveSettings() {
    if (this.saveSettingsDebounceTimer) {
      clearTimeout(this.saveSettingsDebounceTimer);
    }
    this.saveSettingsDebounceTimer = setTimeout(() => {
      this.saveSettings();
    }, 300);
  }

  async saveSettings() {
    if (this.isLoadingSettings) {
      console.log('[Settings] Skipping save during load');
      return;
    }
    
    if (!this.currentUrlKey) {
      await this.updateCurrentUrl();
      if (!this.currentUrlKey) {
        console.warn('[Settings] Cannot save: no currentUrlKey');
        return;
      }
    }
    
    const settings = {
      point1: {
        enabled: this.elements.point1.enabled.checked,
        selector: this.elements.point1.selector.value,
        delay: this.elements.point1.delay.value
      },
      dynamicPoints: this.dynamicPoints.map(point => ({
        enabled: point.enabled.checked,
        selector: point.selector.value,
        delay: point.delay.value
      })),
      autoDownload: {
        enabled: this.elements.autoDownload.enabled.checked,
        count: parseInt(this.elements.autoDownload.count.value) || 2,
        delay: parseInt(this.elements.autoDownload.delay.value) || 5,
        monitoring: this.elements.autoDownload.monitoring.checked,
        pattern: this.elements.autoDownload.pattern.value,
        extension: this.elements.autoDownload.extension.value || 'jpg',
        prefix: this.elements.autoDownload.prefix.value || 'Generated_Content'
      },
      randomDelay: this.elements.randomDelay ? this.elements.randomDelay.value : '0',
      promptDelay: this.elements.promptDelay ? this.elements.promptDelay.value : '0',
      autoContinue: this.elements.autoContinue ? this.elements.autoContinue.checked : false
    };

    console.log(`[Settings] Saving to ${this.currentUrlKey}:`, settings);
    await this.saveToIndexedDB(`settings:${this.currentUrlKey}`, settings);
  }

  async loadSettings() {
    if (!this.currentUrlKey) {
      console.warn('[Settings] Cannot load: no currentUrlKey');
      return;
    }
    
    this.isLoadingSettings = true;
    
    if (this.saveSettingsDebounceTimer) {
      clearTimeout(this.saveSettingsDebounceTimer);
      this.saveSettingsDebounceTimer = null;
      console.log('[Settings] Cleared pending save timer before loading');
    }
    
    console.log(`[Settings] Loading from ${this.currentUrlKey}`);

    if (this.dynamicPoints && this.dynamicPoints.length > 0) {
      console.log('[Settings] Clearing existing dynamic points before applying loaded settings');
      while (this.dynamicPoints.length > 0) {
        const p = this.dynamicPoints.pop();
        try { p.element.remove(); } catch (e) {}
      }
      this.dynamicPointCounter = 1;
    }
    
    const settings = await this.loadFromIndexedDB(`settings:${this.currentUrlKey}`);
    console.log(`[Settings] Loaded data:`, settings);
    
    this.elements.point1.enabled.checked = true;
    this.elements.point1.selector.value = '';
    this.elements.point1.delay.value = '1.0';
    this.elements.autoDownload.enabled.checked = true;
    this.elements.autoDownload.count.value = '4';
    this.elements.autoDownload.delay.value = '5';
    this.elements.autoDownload.monitoring.checked = true;
    this.elements.autoDownload.pattern.value = '';
    this.elements.autoDownload.extension.value = 'jpg';
    this.elements.autoDownload.prefix.value = 'Generated_Content';
    if (this.elements.randomDelay) this.elements.randomDelay.value = '0';
    if (this.elements.promptDelay) this.elements.promptDelay.value = '0';
    if (this.elements.autoContinue) this.elements.autoContinue.checked = true;
    
    if (settings) {
      if (settings.point1) {
        this.elements.point1.enabled.checked = settings.point1.enabled;
        this.elements.point1.selector.value = settings.point1.selector || '';
        this.elements.point1.delay.value = settings.point1.delay || '1.0';
      }

      if (settings.dynamicPoints && settings.dynamicPoints.length > 0) {
        console.log(`[Settings] Loading ${settings.dynamicPoints.length} dynamic points`);
        settings.dynamicPoints.forEach(pointData => {
          this.addDynamicPoint(pointData);
        });
        console.log(`[Settings] Successfully loaded ${this.dynamicPoints.length} dynamic points`);
      }

      if (settings.autoDownload) {
        this.elements.autoDownload.enabled.checked = settings.autoDownload.enabled;
        this.elements.autoDownload.count.value = settings.autoDownload.count || 2;
        this.elements.autoDownload.delay.value = settings.autoDownload.delay || 5;
        this.elements.autoDownload.monitoring.checked = settings.autoDownload.monitoring || false;
        this.elements.autoDownload.pattern.value = settings.autoDownload.pattern || '';
        this.elements.autoDownload.extension.value = settings.autoDownload.extension || 'jpg';
        this.elements.autoDownload.prefix.value = settings.autoDownload.prefix || '';
      }

      if (this.elements.randomDelay && settings.randomDelay) {
        this.elements.randomDelay.value = settings.randomDelay;
      }

      if (this.elements.promptDelay && settings.promptDelay) {
        this.elements.promptDelay.value = settings.promptDelay;
      }

      if (this.elements.autoContinue && settings.autoContinue !== undefined) {
        this.elements.autoContinue.checked = settings.autoContinue;
      }
    }
    
    this.updateMonitoringState();
    this.updateAutoContinueState();
    
    this.isLoadingSettings = false;
    console.log('[Settings] Load complete');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.promptInjector = new PromptInjector();
});
