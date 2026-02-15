class PromptGenerator {
  constructor(injector) {
    this.injector = injector;
    this.isGenerating = false;
    this.isPaused = false;
    this.generationAborted = false;
    this.apiKeys = {};
    this.currentProvider = 'maiarouter';
    this.generatedCount = 0;
    this.targetCount = 0;
    this.initElements();
    this.initEventListeners();
    this.loadSettings().then(() => {
      // Update API/model display after settings are loaded
      this.updateApiModelInfo();
    });
  }

  initElements() {
    this.elements = {
      btnSettings: document.getElementById('btn-generator-settings'),
      btnClear: document.getElementById('btn-generator-clear'),
      btnRun: document.getElementById('btn-gen-run'),
      btnPause: document.getElementById('btn-gen-pause'),
      btnPauseText: document.getElementById('btn-gen-pause-text'),
      btnStop: document.getElementById('btn-gen-stop'),
      minLength: document.getElementById('gen-min-length'),
      maxLength: document.getElementById('gen-max-length'),
      totalPrompts: document.getElementById('gen-total-prompts'),
      promptsPerCall: document.getElementById('gen-prompts-per-call'),
      provider: document.getElementById('gen-provider'),
      customModel: document.getElementById('gen-custom-model'),
      btnPasteModel: document.getElementById('btn-paste-model'),
      theme1: document.getElementById('gen-theme-1'),
      theme2: document.getElementById('gen-theme-2'),
      theme3: document.getElementById('gen-theme-3'),
      humanModel: document.getElementById('gen-human-model'),
      customInstructions: document.getElementById('gen-custom-instructions'),
      progressBar: document.getElementById('gen-progress-bar'),
      progressText: document.getElementById('gen-progress-text'),
      statCurrent: document.getElementById('gen-stat-current'),
      statTarget: document.getElementById('gen-stat-target'),
      statEntry: document.getElementById('gen-stat-entry'),
      statStatus: document.getElementById('gen-stat-status'),
      statApiKey: document.getElementById('gen-stat-apikey'),
      statModel: document.getElementById('gen-stat-model'),
      dialog: document.getElementById('api-settings-dialog'),
      btnCloseSettings: document.getElementById('btn-close-settings'),
      btnSaveSettings: document.getElementById('btn-save-settings'),
      btnCancelSettings: document.getElementById('btn-cancel-settings'),
      apiKeysContainer: document.getElementById('api-keys-container'),
      btnAddApiKey: document.getElementById('btn-add-api-key'),
      btnTestAll: document.getElementById('btn-test-all'),
      testAllResult: document.getElementById('test-all-result')
    };
  }

  initEventListeners() {
    this.elements.btnSettings.addEventListener('click', () => this.openSettingsDialog());
    this.elements.btnClear.addEventListener('click', () => this.resetToDefaults());
    this.elements.btnRun.addEventListener('click', () => this.handleRun());
    this.elements.btnPause.addEventListener('click', () => this.handlePause());
    this.elements.btnStop.addEventListener('click', () => this.handleStop());
    this.elements.btnCloseSettings.addEventListener('click', () => this.closeSettingsDialog());
    this.elements.btnSaveSettings.addEventListener('click', () => this.saveSettings());
    this.elements.btnCancelSettings.addEventListener('click', () => this.closeSettingsDialog());
    this.elements.btnPasteModel.addEventListener('click', () => this.pasteModel());
    this.elements.btnAddApiKey.addEventListener('click', () => this.addApiKeyRow());
    this.elements.btnTestAll.addEventListener('click', () => this.testAllKeys());

    this.elements.minLength.addEventListener('change', () => {
      this.validateLengths();
      this.saveGeneratorSettings();
    });
    this.elements.maxLength.addEventListener('change', () => {
      this.validateLengths();
      this.saveGeneratorSettings();
    });
    this.elements.totalPrompts.addEventListener('change', () => {
      this.updateStats();
      this.saveGeneratorSettings();
    });
    this.elements.promptsPerCall.addEventListener('change', () => this.saveGeneratorSettings());
    
    // Provider change - update API/model display
    const handleProviderChange = () => {
      console.log('Provider changed to:', this.elements.provider.value);
      console.log('API keys for provider:', this.apiKeys[this.elements.provider.value]);
      this.saveGeneratorSettings();
      this.updateApiModelInfo();
    };
    this.elements.provider.addEventListener('change', handleProviderChange);
    this.elements.provider.addEventListener('input', handleProviderChange); // Also catch input for programmatic changes
    
    this.elements.customModel.addEventListener('change', () => {
      this.saveGeneratorSettings();
      this.updateApiModelInfo();
    });
    this.elements.theme1.addEventListener('change', () => this.saveGeneratorSettings());
    this.elements.theme2.addEventListener('change', () => this.saveGeneratorSettings());
    this.elements.theme3.addEventListener('change', () => this.saveGeneratorSettings());
    this.elements.humanModel.addEventListener('change', () => this.saveGeneratorSettings());
    this.elements.customInstructions.addEventListener('input', () => this.saveGeneratorSettings());

    document.querySelectorAll('.api-tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => this.switchProviderTab(e.target.dataset.provider));
    });

    this.elements.dialog.addEventListener('click', (e) => {
      if (e.target === this.elements.dialog) {
        this.closeSettingsDialog();
      }
    });

    this.injector.elements.manualPromptInput.addEventListener('input', () => {
      this.updateEntryCount();
    });
  }

  validateLengths() {
    const min = parseInt(this.elements.minLength.value) || 0;
    const max = parseInt(this.elements.maxLength.value) || 0;
    if (min > max) {
      this.elements.maxLength.value = min;
    }
  }

  async pasteModel() {
    try {
      const text = await navigator.clipboard.readText();
      this.elements.customModel.value = text.trim();
      this.saveGeneratorSettings();
    } catch (error) {
      this.injector.addLog('Failed to paste from clipboard', 'error');
    }
  }

  async loadSettings() {
    const providers = ['maiarouter', 'openrouter', 'gemini', 'openai', 'groq', 'blackbox'];
    for (const provider of providers) {
      const keys = await this.injector.loadFromIndexedDB(`gen_apikeys:${provider}`);
      if (keys && Array.isArray(keys)) {
        this.apiKeys[provider] = keys;
      } else {
        this.apiKeys[provider] = [];
      }
    }

    const genSettings = await this.injector.loadFromIndexedDB('gen_settings');
    if (genSettings) {
      if (genSettings.minLength) this.elements.minLength.value = genSettings.minLength;
      if (genSettings.maxLength) this.elements.maxLength.value = genSettings.maxLength;
      if (genSettings.totalPrompts) this.elements.totalPrompts.value = genSettings.totalPrompts;
      if (genSettings.promptsPerCall) this.elements.promptsPerCall.value = genSettings.promptsPerCall;
      if (genSettings.provider) this.elements.provider.value = genSettings.provider;
      if (genSettings.customModel) this.elements.customModel.value = genSettings.customModel;
      if (genSettings.theme1) this.elements.theme1.value = genSettings.theme1;
      if (genSettings.theme2) this.elements.theme2.value = genSettings.theme2;
      if (genSettings.theme3) this.elements.theme3.value = genSettings.theme3;
      if (genSettings.humanModel) this.elements.humanModel.value = genSettings.humanModel;
      if (genSettings.customInstructions) this.elements.customInstructions.value = genSettings.customInstructions;
    }

    this.updateStats();
    this.updateEntryCount();
  }

  async saveGeneratorSettings() {
    const settings = {
      minLength: this.elements.minLength.value,
      maxLength: this.elements.maxLength.value,
      totalPrompts: this.elements.totalPrompts.value,
      promptsPerCall: this.elements.promptsPerCall.value,
      provider: this.elements.provider.value,
      customModel: this.elements.customModel.value,
      theme1: this.elements.theme1.value,
      theme2: this.elements.theme2.value,
      theme3: this.elements.theme3.value,
      humanModel: this.elements.humanModel.value,
      customInstructions: this.elements.customInstructions.value
    };
    await this.injector.saveToIndexedDB('gen_settings', settings);
  }

  async saveSettings() {
    const providers = ['maiarouter', 'openrouter', 'gemini', 'openai', 'groq', 'blackbox'];
    for (const provider of providers) {
      await this.injector.saveToIndexedDB(`gen_apikeys:${provider}`, this.apiKeys[provider]);
    }
    this.closeSettingsDialog();
    this.injector.addLog('API keys saved successfully', 'success');
  }

  openSettingsDialog() {
    this.currentProvider = this.elements.provider.value;
    this.switchProviderTab(this.currentProvider);
    this.elements.dialog.style.display = 'flex';
  }

  closeSettingsDialog() {
    this.elements.dialog.style.display = 'none';
  }

  async resetToDefaults() {
    if (!confirm('Reset prompt generator settings to defaults? This will not delete your API keys.')) {
      return;
    }
    
    // Reset form values to defaults
    this.elements.minLength.value = 50;
    this.elements.maxLength.value = 150;
    this.elements.totalPrompts.value = 10;
    this.elements.promptsPerCall.value = 5;
    this.elements.provider.value = 'maiarouter';
    this.elements.customModel.value = '';
    this.elements.theme1.value = '';
    this.elements.theme2.value = '';
    this.elements.theme3.value = '';
    this.elements.humanModel.value = '';
    this.elements.customInstructions.value = '';
    
    // Save the default settings
    await this.saveGeneratorSettings();
    
    // Update the display
    this.updateStats();
    this.injector.addLog('Settings reset to defaults', 'success');
  }

  switchProviderTab(provider) {
    this.currentProvider = provider;
    
    document.querySelectorAll('.api-tab-btn').forEach(btn => {
      if (btn.dataset.provider === provider) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    this.renderApiKeys();
  }

  renderApiKeys() {
    const keys = this.apiKeys[this.currentProvider] || [];
    this.elements.apiKeysContainer.innerHTML = '';

    keys.forEach((keyData, index) => {
      const item = document.createElement('div');
      item.className = 'api-key-item';
      
      const header = document.createElement('div');
      header.className = 'api-key-item-header';
      
      const label = document.createElement('span');
      label.className = 'api-key-item-label';
      label.textContent = `API Key #${index + 1}`;
      
      const actions = document.createElement('div');
      actions.className = 'api-key-item-actions';
      
      const btnTest = document.createElement('button');
      btnTest.className = 'btn-key-action';
      btnTest.textContent = 'Test';
      btnTest.addEventListener('click', () => this.testSingleKey(index));
      
      const btnPaste = document.createElement('button');
      btnPaste.className = 'btn-key-action';
      btnPaste.textContent = 'Paste';
      btnPaste.addEventListener('click', () => this.pasteApiKey(index));
      
      const btnDelete = document.createElement('button');
      btnDelete.className = 'btn-key-action danger';
      btnDelete.textContent = 'Delete';
      btnDelete.addEventListener('click', () => this.deleteApiKey(index));
      
      actions.appendChild(btnTest);
      actions.appendChild(btnPaste);
      actions.appendChild(btnDelete);
      header.appendChild(label);
      header.appendChild(actions);
      
      const keyRow = document.createElement('div');
      keyRow.className = 'api-key-row';
      
      const input = document.createElement('input');
      input.type = 'password';
      input.className = 'api-key-input';
      input.value = keyData.key || '';
      input.placeholder = 'Enter API key';
      input.addEventListener('input', (e) => {
        this.apiKeys[this.currentProvider][index].key = e.target.value;
      });
      
      keyRow.appendChild(input);
      
      // Add model input row
      const modelRow = document.createElement('div');
      modelRow.className = 'api-key-row';
      
      const modelLabel = document.createElement('span');
      modelLabel.className = 'api-key-label';
      modelLabel.textContent = 'Model override:';
      
      const modelInput = document.createElement('input');
      modelInput.type = 'text';
      modelInput.className = 'api-model-input';
      modelInput.value = keyData.model || '';
      modelInput.placeholder = 'Optional: e.g. google/gemini-2.0-flash-001';
      modelInput.addEventListener('input', (e) => {
        this.apiKeys[this.currentProvider][index].model = e.target.value;
      });
      
      modelRow.appendChild(modelLabel);
      modelRow.appendChild(modelInput);
      
      const status = document.createElement('span');
      status.className = 'api-status';
      status.id = `status-${this.currentProvider}-${index}`;
      
      item.appendChild(header);
      item.appendChild(keyRow);
      item.appendChild(modelRow);
      item.appendChild(status);
      this.elements.apiKeysContainer.appendChild(item);
    });
  }

  addApiKeyRow() {
    if (!this.apiKeys[this.currentProvider]) {
      this.apiKeys[this.currentProvider] = [];
    }
    this.apiKeys[this.currentProvider].push({ key: '', status: '', model: '' });
    this.renderApiKeys();
  }

  async pasteApiKey(index) {
    try {
      const text = await navigator.clipboard.readText();
      this.apiKeys[this.currentProvider][index].key = text.trim();
      this.renderApiKeys();
      this.injector.addLog('API key pasted successfully', 'success');
    } catch (error) {
      this.injector.addLog('Failed to paste from clipboard', 'error');
    }
  }

  deleteApiKey(index) {
    this.apiKeys[this.currentProvider].splice(index, 1);
    this.renderApiKeys();
  }

  async testSingleKey(index) {
    const keyData = this.apiKeys[this.currentProvider][index];
    const status = document.getElementById(`status-${this.currentProvider}-${index}`);
    
    if (!keyData.key) {
      status.textContent = 'Please enter an API key';
      status.className = 'api-status error';
      return;
    }

    status.textContent = 'Testing...';
    status.className = 'api-status testing';

    try {
      const result = await this.makeTestRequest(this.currentProvider, keyData.key);
      if (result.success) {
        status.textContent = '✓ Connection successful';
        status.className = 'api-status success';
        keyData.status = 'success';
      } else {
        status.textContent = `✗ ${result.error}`;
        status.className = 'api-status error';
        keyData.status = 'error';
      }
    } catch (error) {
      status.textContent = `✗ ${error.message}`;
      status.className = 'api-status error';
      keyData.status = 'error';
    }
  }

  async testAllKeys() {
    const keys = this.apiKeys[this.currentProvider] || [];
    if (keys.length === 0) {
      this.elements.testAllResult.textContent = 'No API keys to test';
      return;
    }

    this.elements.testAllResult.textContent = 'Testing all keys...';
    this.elements.btnTestAll.disabled = true;

    let successCount = 0;
    for (let i = 0; i < keys.length; i++) {
      await this.testSingleKey(i);
      if (keys[i].status === 'success') successCount++;
    }

    this.elements.testAllResult.textContent = `${successCount}/${keys.length} keys valid`;
    this.elements.btnTestAll.disabled = false;
  }

  async makeTestRequest(provider, apiKey) {
    const timeout = 15000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const customModel = this.elements.customModel.value.trim();

    try {
      let response;
      
      switch (provider) {
        case 'maiarouter':
          response = await fetch('https://api.maiarouter.ai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
              model: customModel || 'maia/gemini-2.0-flash',
              messages: [{ role: 'user', content: 'test' }],
              max_tokens: 5
            }),
            signal: controller.signal
          });
          break;

        case 'openrouter':
          response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`,
              'HTTP-Referer': 'https://github.com/desainia/prompt-injector',
              'X-Title': 'Prompt Injector'
            },
            body: JSON.stringify({
              model: customModel || 'google/gemini-2.0-flash-001',
              messages: [{ role: 'user', content: 'test' }],
              max_tokens: 5
            }),
            signal: controller.signal
          });
          break;

        case 'gemini':
          response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${customModel || 'gemini-2.5-flash'}:generateContent?key=${apiKey}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contents: [{ parts: [{ text: 'test' }] }]
            }),
            signal: controller.signal
          });
          break;

        case 'openai':
          response = await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
              model: customModel || 'gpt-4o',
              messages: [{ role: 'user', content: 'test' }],
              max_completion_tokens: 5
            }),
            signal: controller.signal
          });
          break;

        case 'groq':
          response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
              model: customModel || 'meta-llama/llama-4-scout-17b-16e-instruct',
              messages: [{ role: 'user', content: 'test' }],
              max_tokens: 5
            }),
            signal: controller.signal
          });
          break;

        case 'blackbox':
          response = await fetch('https://api.blackbox.ai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
              model: customModel || 'blackboxai',
              messages: [{ role: 'user', content: 'test' }],
              max_tokens: 5
            }),
            signal: controller.signal
          });
          break;

        default:
          throw new Error('Unknown provider');
      }

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error?.message || `HTTP ${response.status}`);
      }

      return { success: true };
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        return { success: false, error: 'Request timeout' };
      }
      return { success: false, error: error.message };
    }
  }

  updateStats() {
    this.targetCount = parseInt(this.elements.totalPrompts.value) || 0;
    const promptsPerRequest = parseInt(this.elements.promptsPerCall.value) || 5;
    
    // Show requests completed / total requests
    this.elements.statCurrent.textContent = this.generatedCount;
    this.elements.statTarget.textContent = this.targetCount;
    
    const percentage = this.targetCount > 0 ? (this.generatedCount / this.targetCount) * 100 : 0;
    this.elements.progressBar.style.width = `${percentage}%`;
    
    // Show both request count and estimated prompt count
    const estimatedPrompts = this.generatedCount * promptsPerRequest;
    const totalEstimatedPrompts = this.targetCount * promptsPerRequest;
    this.elements.progressText.textContent = `Req: ${this.generatedCount}/${this.targetCount} | ~${estimatedPrompts} prompts`;
    
    this.updateEntryCount();
    this.updateApiModelInfo();
  }

  updateApiModelInfo() {
    const provider = this.elements.provider.value;
    const customModel = this.elements.customModel.value.trim();
    const keys = this.apiKeys[provider] || [];
    
    // Get the first active API key
    const activeKey = keys.find(k => k.key && k.status === 'active');
    const apiKey = activeKey ? activeKey.key : (keys.length > 0 ? keys[0].key : '');
    
    // Show last 4 characters of API key
    if (apiKey && apiKey.length > 4) {
      this.elements.statApiKey.textContent = '***' + apiKey.slice(-4);
    } else if (apiKey) {
      this.elements.statApiKey.textContent = '***' + apiKey;
    } else {
      this.elements.statApiKey.textContent = 'Not set';
    }
    
    // Show model - check for per-API-key model first, then global custom model
    let model = customModel;
    if (activeKey && activeKey.model) {
      model = activeKey.model;
    }
    
    // Get default model based on provider
    if (!model) {
      switch (provider) {
        case 'maiarouter':
          model = 'maia/gemini-2.0-flash';
          break;
        case 'openrouter':
          model = 'google/gemini-2.0-flash-001';
          break;
        case 'gemini':
          model = 'gemini-2.5-flash';
          break;
        case 'openai':
          model = 'gpt-5-nano-2025-08-07';
          break;
        case 'groq':
          model = 'meta-llama/llama-4-scout-17b-16e-instruct';
          break;
        case 'blackbox':
          model = 'blackboxai';
          break;
        default:
          model = 'N/A';
      }
    }
    
    // Truncate model name if too long
    if (model.length > 25) {
      this.elements.statModel.textContent = model.slice(0, 22) + '...';
    } else {
      this.elements.statModel.textContent = model;
    }
  }

  updateEntryCount() {
    const text = this.injector.elements.manualPromptInput.value;
    const count = this.countPromptsInText(text);
    this.elements.statEntry.textContent = count;
  }

  countPromptsInText(text) {
    if (!text || !text.trim()) return 0;
    
    text = text.trim();
    
    if (text.includes('---')) {
      return text.split('---').filter(p => p.trim()).length;
    }
    
    const numbered = text.match(/^(\d+\.|#\d+)\s+/gm);
    if (numbered && numbered.length > 0) {
      return numbered.length;
    }
    
    const lines = text.split('\n\n').filter(p => p.trim());
    if (lines.length > 1) {
      return lines.length;
    }
    
    return text.split('\n').filter(line => line.trim()).length;
  }

  setRunMode(running, paused = false) {
    this.elements.btnRun.disabled = running;
    this.elements.btnPause.disabled = !running;
    this.elements.btnStop.disabled = !running;

    if (running && !paused) {
      this.elements.statStatus.textContent = 'Running';
      this.elements.statStatus.style.color = 'var(--accent)';
      this.elements.btnPauseText.textContent = 'Pause';
    } else if (paused) {
      this.elements.statStatus.textContent = 'Paused';
      this.elements.statStatus.style.color = 'var(--text-secondary)';
      this.elements.btnPauseText.textContent = 'Resume';
    } else {
      this.elements.statStatus.textContent = 'Idle';
      this.elements.statStatus.style.color = '';
      this.elements.btnPauseText.textContent = 'Pause';
    }
  }

  async handleRun() {
    if (this.isPaused) {
      this.isPaused = false;
      this.setRunMode(true, false);
      this.injector.addLog('Generation resumed', 'info');
      return;
    }

    const provider = this.elements.provider.value;
    const keys = this.apiKeys[provider] || [];
    const validKeys = keys.filter(k => k.key && k.key.trim());

    if (validKeys.length === 0) {
      this.elements.statStatus.textContent = 'No API keys';
      this.elements.statStatus.style.color = 'var(--danger)';
      this.injector.addLog('Please configure API keys in settings', 'error');
      return;
    }

    const minLength = parseInt(this.elements.minLength.value) || 50;
    const maxLength = parseInt(this.elements.maxLength.value) || 150;
    const totalRequests = parseInt(this.elements.totalPrompts.value) || 10;
    const promptsPerRequest = parseInt(this.elements.promptsPerCall.value) || 5;

    if (minLength > maxLength) {
      this.elements.statStatus.textContent = 'Invalid length';
      this.elements.statStatus.style.color = 'var(--danger)';
      this.injector.addLog('Min length must be less than max length', 'error');
      return;
    }

    this.isGenerating = true;
    this.generationAborted = false;
    this.generatedCount = 0;
    this.targetCount = totalRequests;
    this.setRunMode(true, false);
    this.updateStats();

    try {
      let keyIndex = 0;
      let currentRequestNumber = 0;
      let totalPromptsGenerated = 0;

      // Make totalRequests API calls, each generating promptsPerRequest prompts
      while (currentRequestNumber < totalRequests && !this.generationAborted) {
        while (this.isPaused && !this.generationAborted) {
          await this.delay(100);
        }

        if (this.generationAborted) break;

        const currentKeyObj = validKeys[keyIndex % validKeys.length];
        const currentKey = currentKeyObj.key;
        const currentModel = currentKeyObj.model; // Per-API-key model override
        keyIndex++;
        currentRequestNumber++;

        try {
          const prompts = await this.generatePromptBatch(provider, currentKey, currentModel, promptsPerRequest, minLength, maxLength);
          
          if (this.generationAborted) break;
          
          if (prompts && prompts.length > 0) {
            const validPrompts = prompts.filter(p => {
              const len = p.length;
              return len >= minLength && len <= maxLength;
            });

            if (validPrompts.length > 0) {
              // Insert prompts immediately after each request completes
              this.insertGeneratedPrompts(validPrompts, totalPromptsGenerated);
              totalPromptsGenerated += validPrompts.length;
              this.generatedCount = currentRequestNumber;
              this.updateStats();
              this.injector.addLog(`Request ${currentRequestNumber}/${totalRequests}: +${validPrompts.length} prompts (Total: ${totalPromptsGenerated})`, 'success');
            }
          }
        } catch (error) {
          if (this.generationAborted) break;
          this.injector.addLog(`Request ${currentRequestNumber} error: ${error.message}`, 'warning');
        }

        if (currentRequestNumber < totalRequests && !this.generationAborted && !this.isPaused) {
          await this.delay(1000);
        }
      }

      if (this.generationAborted) {
        this.elements.statStatus.textContent = 'Stopped';
        this.elements.statStatus.style.color = 'var(--danger)';
        this.injector.addLog(`Stopped at ${currentRequestNumber}/${totalRequests} requests (${totalPromptsGenerated} total prompts)`, 'warning');
      } else if (totalPromptsGenerated > 0) {
        this.elements.statStatus.textContent = 'Complete';
        this.elements.statStatus.style.color = 'var(--success)';
        this.injector.addLog(`Successfully completed ${totalRequests} requests, generated ${totalPromptsGenerated} prompts`, 'success');
      }
    } catch (error) {
      this.elements.statStatus.textContent = 'Error';
      this.elements.statStatus.style.color = 'var(--danger)';
      this.injector.addLog(`Generation error: ${error.message}`, 'error');
    } finally {
      this.isGenerating = false;
      this.isPaused = false;
      this.setRunMode(false);
    }
  }

  handlePause() {
    console.log('handlePause called, isPaused:', this.isPaused);
    
    // If paused, try to resume (consistent with tab control behavior)
    if (this.isPaused) {
      this.isPaused = false;
      this.setRunMode(true, false);
      this.injector.addLog('Generation resumed', 'info');
      return;
    }
    
    // Otherwise, pause
    this.isPaused = true;
    this.setRunMode(true, true);
    this.injector.addLog('Generation paused', 'info');
  }

  handleStop() {
    this.generationAborted = true;
    this.isPaused = false;
    this.injector.addLog('Stopping generation...', 'warning');
  }

  async generatePromptBatch(provider, apiKey, customModel, count, minLength, maxLength) {
    if (this.generationAborted) {
      throw new Error('Generation aborted');
    }

    const theme = this.elements.theme1.value;
    const mood = this.elements.theme2.value;
    const color = this.elements.theme3.value;
    const humanModel = this.elements.humanModel.value;

    const customInstructions = this.elements.customInstructions.value.trim();
    const globalCustomModel = this.elements.customModel.value.trim();
    
    // Use per-API-key model if available, otherwise use global model
    const effectiveModel = customModel || globalCustomModel || '';

    let systemPrompt = `You are a creative prompt generator. Generate exactly ${count} unique, creative prompts for image generation. Each prompt should be between ${minLength} and ${maxLength} characters.`;
    
    if (theme) {
      systemPrompt += ` Style: ${theme}.`;
    }
    
    if (mood) {
      systemPrompt += ` Mood: ${mood}.`;
    }
    
    if (color) {
      systemPrompt += ` Color palette: ${color}.`;
    }
    
    if (humanModel === 'true') {
      systemPrompt += ` Include human subjects.`;
    } else if (humanModel === 'false') {
      systemPrompt += ` Do not include human subjects.`;
    }
    
    if (customInstructions) {
      systemPrompt += ` Additional instructions: ${customInstructions}`;
    }
    
    systemPrompt += ` Return ONLY a JSON array of strings, nothing else. Example format: ["prompt 1", "prompt 2", "prompt 3"]`;

    const timeout = 60000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      let response;
      let data;

      switch (provider) {
        case 'maiarouter':
          console.log('MAIA Router - effectiveModel:', effectiveModel, 'customModel:', customModel, 'globalCustomModel:', globalCustomModel);
          const maiaBody = {
              model: effectiveModel || 'maia/gemini-2.0-flash',
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: `Generate ${count} creative image prompts now.` }
              ],
              temperature: 0.9,
              max_tokens: 2000
            };
          console.log('MAIA Router Request:', maiaBody);
          response = await fetch('https://api.maiarouter.ai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify(maiaBody),
            signal: controller.signal
          });
          data = await response.json();
          break;

        case 'openrouter':
          console.log('OpenRouter - effectiveModel:', effectiveModel, 'customModel:', customModel, 'globalCustomModel:', globalCustomModel);
          const openRouterBody = {
              model: effectiveModel || 'google/gemini-2.0-flash-lite-001',
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: `Generate ${count} creative image prompts now.` }
              ],
              temperature: 0.9,
              max_tokens: 2000
            };
          console.log('OpenRouter Request Body:', openRouterBody);
          response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`,
              'HTTP-Referer': 'https://github.com/desainia/prompt-injector',
              'X-Title': 'Prompt Injector'
            },
            body: JSON.stringify(openRouterBody),
            signal: controller.signal
          });
          data = await response.json();
          break;

        case 'gemini':
          response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${effectiveModel || 'gemini-2.5-flash'}:generateContent?key=${apiKey}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contents: [{
                parts: [{
                  text: `${systemPrompt}\n\nGenerate ${count} creative image prompts now.`
                }]
              }],
              generationConfig: {
                temperature: 0.9,
                maxOutputTokens: 2000
              }
            }),
            signal: controller.signal
          });
          data = await response.json();
          break;

        case 'openai':
          console.log('OpenAI - effectiveModel:', effectiveModel, 'customModel:', customModel, 'globalCustomModel:', globalCustomModel);
          response = await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
              model: effectiveModel || 'gpt-4o',
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: `Generate ${count} creative image prompts now.` }
              ],
              temperature: 0.9,
              max_completion_tokens: 2000
            }),
            signal: controller.signal
          });
          data = await response.json();
          break;

        case 'groq':
          response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
              model: effectiveModel || 'meta-llama/llama-4-scout-17b-16e-instruct',
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: `Generate ${count} creative image prompts now.` }
              ],
              temperature: 0.9,
              max_tokens: 2000
            }),
            signal: controller.signal
          });
          data = await response.json();
          break;

        case 'blackbox':
          response = await fetch('https://api.blackbox.ai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
              model: effectiveModel || 'blackboxai',
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: `Generate ${count} creative image prompts now.` }
              ],
              temperature: 0.9,
              max_tokens: 2000
            }),
            signal: controller.signal
          });
          data = await response.json();
          break;

        default:
          throw new Error('Unknown provider');
      }

      clearTimeout(timeoutId);

      if (this.generationAborted) {
        throw new Error('Generation aborted');
      }

      if (!response.ok) {
        const errorData = data || {};
        console.log('API Error Response - Provider:', provider, 'Error:', errorData);
        // Try different error message formats
        let errorMessage = errorData.error?.message || errorData.message || errorData.detail || `HTTP ${response.status}: ${JSON.stringify(errorData)}`;
        
        // Check for network/DNS errors
        if (!response.ok && !data) {
          errorMessage = `Network error: Could not connect to ${provider} API. This may be a DNS or connectivity issue.`;
        }
        
        throw new Error(errorMessage);
      }

      return this.parsePromptsFromResponse(data, provider);
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timeout');
      }
      throw error;
    }
  }

  parsePromptsFromResponse(data, provider) {
    let content = '';

    try {
      switch (provider) {
        case 'gemini':
          content = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
          break;

        case 'maiarouter':
        case 'openrouter':
        case 'openai':
        case 'groq':
        case 'blackbox':
          content = data.choices?.[0]?.message?.content || '';
          break;

        default:
          throw new Error('Unknown provider format');
      }

      content = content.trim();

      const jsonMatch = content.match(/\[[\s\S]*\]/);
      if (jsonMatch) {
        const prompts = JSON.parse(jsonMatch[0]);
        if (Array.isArray(prompts)) {
          return prompts.map(p => String(p).trim()).filter(p => p.length > 0);
        }
      }

      const lines = content.split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .map(line => line.replace(/^["'\d\.\-\*\#\[\]]+\s*/, ''))
        .map(line => line.replace(/["'\,\]]+$/, ''))
        .filter(line => line.length > 0);

      if (lines.length > 0) {
        return lines;
      }

      throw new Error('Could not parse prompts from response');
    } catch (error) {
      throw new Error(`Parse error: ${error.message}`);
    }
  }

  insertGeneratedPrompts(prompts, startIndex = 0) {
    const formatted = prompts.map((prompt, index) => `${startIndex + index + 1}. ${prompt}`).join('\n\n');
    
    const textarea = this.injector.elements.manualPromptInput;
    const currentValue = textarea.value.trim();
    
    if (currentValue) {
      textarea.value = currentValue + '\n\n' + formatted;
    } else {
      textarea.value = formatted;
    }

    this.injector.updateManualCount();
    this.injector.debouncedSavePrompts();
    this.updateEntryCount();
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
