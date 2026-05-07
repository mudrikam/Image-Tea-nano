document.addEventListener('DOMContentLoaded', async () => {
  // Load extension version from manifest
  try {
    const resp = await fetch('manifest.json');
    if (resp.ok) {
      const manifest = await resp.json();
      const verEl = document.getElementById('extensionVersion');
      if (verEl && manifest.version) {
        verEl.textContent = 'v' + manifest.version;
      }
    }
  } catch (e) {
    console.warn('Could not load manifest version:', e);
  }

  // UI Elements - Landing Page
  const landingPage = document.getElementById('landingPage');
  const mainInterface = document.getElementById('mainInterface');
  const btnOpenFlow = document.getElementById('btnOpenFlow');

  // UI Elements - Controls
  const btnStart = document.getElementById('btnStart');
  const btnPause = document.getElementById('btnPause');
  const btnStop = document.getElementById('btnStop');
  const btnReset = document.getElementById('btnReset');
  const btnLoadTXT = document.getElementById('btnLoadTXT');
  const btnLoadCSV = document.getElementById('btnLoadCSV');
   const btnClearLogs = document.getElementById('btnClearLogs');
   const btnCopyLogs = document.getElementById('btnCopyLogs');
   const btnPaste = document.getElementById('btnPaste');
   const btnClearInput = document.getElementById('btnClearInput');
   const promptDisplay = document.getElementById('promptDisplay');

   // UI Elements - Main Interface
   const fileInput = document.getElementById('fileInput');
   const fileDropArea = document.getElementById('fileDropArea');
   const manualInput = document.getElementById('manualInput');
   const logArea = document.getElementById('logArea');
   const progressBar = document.getElementById('progressBar');
   const valPct = document.getElementById('valPct');
   const queueProgress = document.getElementById('queueProgress');
   const queueRemaining = document.getElementById('queueRemaining');
   const fileLabel = document.getElementById('fileLabel');
   const typeGroup = document.getElementById('typeGroup');
   const queueTableBody = document.getElementById('queueTableBody');
   const globalDelaySecondsInput = document.getElementById('globalDelaySeconds');
   const refreshAfterPromptsInput = document.getElementById('refreshAfterPrompts');
   const repeatPerPromptInput = document.getElementById('repeatPerPrompt');

  // UI Stats Elements
  const valQueue = document.getElementById('valQueue');
  const valSuccess = document.getElementById('valSuccess');
  const valFailed = document.getElementById('valFailed');
  const valDownloaded = document.getElementById('valDownloaded');
  const countdownRow = document.getElementById('countdownRow');
  const valCountdown = document.getElementById('valCountdown');
  const cooldownLabel = document.getElementById('cooldownLabel');
  const cooldownHint = document.getElementById('cooldownHint');
  const cooldownProgressFill = document.getElementById('cooldownProgressFill');

  // Clear logs on every sidepanel open
  logArea.innerHTML = '';

  // State variables
  let currentPrompts = []; // Current prompts from textarea (loaded or typed)
  let prompts = [];       // Active prompts being processed
  let queueData = [];
  let currentIndex = 0;
  let successCount = 0;
  let failedCount = 0;
  let downloadedCount = 0;
  let isRunning = false;
  let isPaused = false;
  let targetTabId = null;
  let countdownInterval = null;
  let remainingCountdown = 0;
  let lastRefreshSuccessCount = 0;

  // Filter ratio options based on selected media type
  function updateRatioOptions(type) {
    const allRatioInputs = document.querySelectorAll('input[name="ratio"]');
    allRatioInputs.forEach(input => {
      const pill = input.closest('.radio-pill');
      const validFor = input.getAttribute('data-valid-for');
      if (validFor) {
        const validTypes = validFor.split(',');
        if (validTypes.includes(type)) {
          pill.classList.remove('disabled');
          input.disabled = false;
        } else {
          pill.classList.add('disabled');
          input.disabled = true;
          if (input.checked) {
            input.checked = false;
            const firstValid = Array.from(allRatioInputs).find(inp => {
              const vf = inp.getAttribute('data-valid-for');
              return vf && vf.split(',').includes(type);
            });
            if (firstValid) firstValid.checked = true;
          }
        }
      }
    });
  }

  // Filter download quality options based on selected media type
  function updateDownloadQualityOptions(type) {
    const allQualityInputs = document.querySelectorAll('input[name="downloadQuality"]');
    allQualityInputs.forEach(input => {
      const pill = input.closest('.radio-pill');
      const validFor = input.getAttribute('data-valid-for');
      if (!validFor) return;

      const validTypes = validFor.split(',');
      const isValid = validTypes.includes(type);
      pill.classList.toggle('disabled', !isValid);
      input.disabled = !isValid;
    });

    const selected = document.querySelector('input[name="downloadQuality"]:checked');
    if (selected && selected.disabled) {
      selected.checked = false;
      const fallback = Array.from(allQualityInputs).find(input => !input.disabled && input.value === 'default') ||
                       Array.from(allQualityInputs).find(input => !input.disabled);
      if (fallback) fallback.checked = true;
    }
  }

  // Update models on media type change
  typeGroup.addEventListener('change', (e) => {
    if (e.target.name === 'type') {
      const selectedType = document.querySelector('input[name="type"]:checked').value;
      updateRatioOptions(selectedType);
      updateDownloadQualityOptions(selectedType);
    }
  });

  // Parse prompts from text: supports both numbered (1. 2.) and line-by-line formats
  function parsePrompts(text) {
    const lines = text.split(/\r?\n/);
    const prompts = [];
    let currentPrompt = '';
    let hasNumbering = false;

    // Detect if any line uses numbering
    for (let line of lines) {
      const trimmed = line.trim();
      if (trimmed && /^\d+\.\s/.test(trimmed)) {
        hasNumbering = true;
        break;
      }
    }

    if (hasNumbering) {
      // Numbered mode
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();

        if (line === '') {
          if (currentPrompt.trim()) {
            prompts.push(currentPrompt.trim());
            currentPrompt = '';
          }
          continue;
        }

        const numberMatch = line.match(/^(\d+)\.\s*(.*)/);

        if (numberMatch) {
          if (currentPrompt.trim()) {
            prompts.push(currentPrompt.trim());
          }
          currentPrompt = numberMatch[2].trim();
        } else {
          if (currentPrompt) {
            currentPrompt += ' ' + line;
          } else {
            currentPrompt = line;
          }
        }
      }

      if (currentPrompt.trim()) {
        prompts.push(currentPrompt.trim());
      }
    } else {
      // Simple mode: each non-empty line = one prompt
      for (let line of lines) {
        const trimmed = line.trim();
        if (trimmed) {
          prompts.push(trimmed);
        }
      }
    }

     return prompts;
   }

   // Escape HTML to prevent XSS
   function escapeHtml(text) {
     const div = document.createElement('div');
     div.textContent = text;
     return div.innerHTML;
   }

   // Render prompt display with color-coded status
   function renderPromptDisplay() {
     if (!promptDisplay || queueData.length === 0) {
       promptDisplay.innerHTML = '<div style="color: var(--text-muted); padding: 8px;">No prompts</div>';
       return;
     }

     let html = '';
     queueData.forEach((item, idx) => {
       let statusClass = 'prompt-pending';
       if (item.status === 'processing') {
         statusClass = 'prompt-active';
       } else if (item.status === 'completed') {
         statusClass = 'prompt-completed';
       } else if (item.status === 'failed') {
         statusClass = 'prompt-failed';
       } else if (item.status === 'partial') {
         statusClass = 'prompt-completed'; // treat partial as completed
       }
       const repeatLabel = item.repeatTotal > 1 ? `<span style="opacity:0.5;font-size:10px;">[${item.repeatIndex + 1}/${item.repeatTotal}]</span> ` : '';
       html += `<div class="prompt-line ${statusClass}">${repeatLabel}${escapeHtml(item.prompt)}</div>`;
     });
     promptDisplay.innerHTML = html;

     // Auto-scroll to active prompt
     const activeEl = promptDisplay.querySelector('.prompt-active');
     if (activeEl) {
       activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
     }
   }

   // Load file content and auto-populate textarea
   function loadFileContent(file) {
     if (isRunning) {
       appendLog('Cannot load file while processing. Stop first.', 'warn');
       return;
     }
     const reader = new FileReader();
     fileLabel.innerText = file.name;
     reader.onload = (event) => {
       const text = event.target.result;
       const parsedPrompts = parsePrompts(text);
       currentPrompts = parsedPrompts;
       manualInput.value = text;
       fileInput.value = ''; // Reset so same file can be selected again
       updateQueue();
       appendLog(`Queue loaded: ${currentPrompts.length} prompts from file.`, 'info');
     };
     reader.readAsText(file);
   }

  // File input change handler
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      loadFileContent(file);
    }
  });

  // Drop area click — REMOVED. Input overlay handles click natively.
  // fileDropArea.addEventListener('click', () => {
  //   fileInput.click();
  // });

  // Manual input change handler
  manualInput.addEventListener('input', () => {
    const text = manualInput.value;
    currentPrompts = parsePrompts(text);
    updateQueue();
  });

  // Repeat per prompt change handler - rebuild queue when repeat changes
  repeatPerPromptInput.addEventListener('input', () => {
    if (!isRunning) {
      updateQueue();
    }
  });

  // Copy logs button
  btnCopyLogs.addEventListener('click', async () => {
    const logText = logArea.innerText || logArea.textContent || '';
    if (!logText.trim()) {
      appendLog('No logs to copy.', 'warn');
      return;
    }
    try {
      await navigator.clipboard.writeText(logText);
      // Brief visual feedback on the button
      const origTitle = btnCopyLogs.title;
      btnCopyLogs.title = 'Copied!';
      btnCopyLogs.style.color = 'var(--success)';
      setTimeout(() => { btnCopyLogs.title = origTitle; btnCopyLogs.style.color = ''; }, 1500);
    } catch (err) {
      appendLog('Failed to copy logs: ' + err.message, 'error');
    }
  });

  // Clear logs button
  btnClearLogs.addEventListener('click', () => {
    logArea.innerHTML = '';
    appendLog('Logs cleared.', 'info');
  });

  // Load TXT button
  btnLoadTXT.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.accept = '.txt';
    fileInput.click();
  });

   // Load CSV button
   btnLoadCSV.addEventListener('click', (e) => {
     e.stopPropagation();
     fileInput.accept = '.csv';
     fileInput.click();
   });

   // Paste button - read clipboard and replace prompts
   btnPaste.addEventListener('click', async () => {
     if (isRunning) {
       appendLog('Cannot paste while processing. Stop first.', 'warn');
       return;
     }
     try {
       const text = await navigator.clipboard.readText();
       if (text) {
         manualInput.value = text;
         currentPrompts = parsePrompts(text);
         updateQueue();
         appendLog('Pasted prompts from clipboard.', 'info');
       }
     } catch (err) {
       appendLog('Failed to read clipboard: ' + err.message, 'error');
     }
   });

   // Clear button - clear all prompts
   btnClearInput.addEventListener('click', () => {
     if (isRunning) {
       appendLog('Cannot clear while processing. Stop first.', 'warn');
       return;
     }
     manualInput.value = '';
     currentPrompts = [];
     updateQueue();
     appendLog('Prompts cleared.', 'info');
   });

    // Check if current tab is on Flow page
    async function checkCurrentTab() {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.url) return false;
      // Match Flow pages with optional locale segment (e.g., /id/, /my/, /en/, or none)
      // Pattern: /labs.google[.com]/fx/[optional-locale]/tools/flow
      const flowPattern = /labs\.google(\.com)?\/fx\/(?:[^/]+\/)?tools\/flow/i;
      return flowPattern.test(tab.url);
    }

  // Show appropriate view based on tab
  async function initView() {
    const isOnFlow = await checkCurrentTab();
    if (isOnFlow) {
      landingPage.classList.add('hidden');
      mainInterface.classList.remove('hidden');
      initializeMainInterface();
    } else {
      landingPage.classList.add('hidden');
      mainInterface.classList.add('hidden');
      landingPage.classList.remove('hidden');
    }
  }

  // Open Flow in new tab (detect locale from current tab if available)
  btnOpenFlow.addEventListener('click', async () => {
    let flowUrl = 'https://labs.google/fx/tools/flow';
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.url) {
        // Extract locale from current Flow URL if present (e.g., /fx/id/tools/... → "id")
        const localeMatch = tab.url.match(/labs\.google(?:\.com)?\/fx\/([a-z]{2}(?:-[a-z]{2})?)\//i);
        if (localeMatch && localeMatch[1]) {
          const locale = localeMatch[1].toLowerCase();
          // Don't treat path segments that look like tool names as locales
          if (!['tools', 'flow', 'project'].includes(locale)) {
            flowUrl = `https://labs.google/fx/${locale}/tools/flow`;
          }
        }
      }
    } catch (e) {
      // Fallback to default URL
    }
    await chrome.tabs.create({ url: flowUrl });
  });

  // Initialize main interface logic
  function initializeMainInterface() {
    appendLog('Extension loaded. Ready to attach to page.', 'info');
  }

   // Update queue data array and refresh table
   // Each prompt is expanded by repeatPerPrompt count (e.g., 3 prompts × 2 repeat = 6 queue entries)
   function updateQueue() {
     prompts = currentPrompts;
     const repeat = getRepeatPerPrompt();

     // Rebuild queueData: expand each prompt by repeat count
     queueData = [];
     prompts.forEach((prompt, promptIdx) => {
       for (let r = 0; r < repeat; r++) {
         queueData.push({
           prompt: prompt,
           status: 'pending',
           generatedCount: 0,
           promptIndex: promptIdx,   // original prompt index
           repeatIndex: r,           // which repeat (0-based)
           repeatTotal: repeat       // total repeats for display
         });
       }
     });

     updateQueueProgressLabel();
     renderQueueTable();
   }

   // Update queue progress label: "X/Y" format + remaining
   function updateQueueProgressLabel() {
     const total = queueData.length;
     const completed = currentIndex;
     const remaining = Math.max(0, total - completed);
     if (total > 0) {
       queueProgress.innerText = `${completed}/${total}`;
       queueRemaining.innerText = `(${remaining} remaining)`;
     } else {
       queueProgress.innerText = '0';
       queueRemaining.innerText = '';
     }
   }

  // Render prompt queue table
  function renderQueueTable() {
    if (queueData.length === 0) {
      queueTableBody.innerHTML = '<tr><td colspan="4" class="empty-queue">No prompts in queue</td></tr>';
      return;
    }

    queueTableBody.innerHTML = '';
    queueData.forEach((item, idx) => {
      const row = document.createElement('tr');
      row.className = item.status;
      row.id = `queue-row-${idx}`;

      let statusText = 'Pending';
      if (item.status === 'processing') statusText = 'Processing...';
      else if (item.status === 'completed') statusText = 'Completed';
      else if (item.status === 'failed') statusText = 'Failed';
      else if (item.status === 'partial') statusText = 'Partial';

      // Show index as "#P.R" when repeat > 1, otherwise just "#N"
      const indexLabel = item.repeatTotal > 1
        ? `#${item.promptIndex + 1}.${item.repeatIndex + 1}`
        : `#${idx + 1}`;

      row.innerHTML = `
        <td><span style="color: var(--text-muted); font-size: 10px;">${indexLabel}</span></td>
        <td><div class="queue-prompt-text" title="${item.prompt.replace(/"/g, '&quot;')}">${item.prompt}</div></td>
        <td><span class="queue-status status-${item.status}">${statusText}</span></td>
        <td style="font-family: monospace;">${item.generatedCount}</td>
      `;
      queueTableBody.appendChild(row);
    });

    // Auto-scroll to currently processing row
    const processingRow = queueTableBody.querySelector('tr.processing');
    if (processingRow) {
      processingRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function getGlobalDelayMs() {
    const delaySeconds = Number.parseFloat(globalDelaySecondsInput?.value);
    const safeDelaySeconds = Number.isFinite(delaySeconds) && delaySeconds >= 0 ? delaySeconds : 5;
    return Math.round(safeDelaySeconds * 1000);
  }

  function getRefreshAfterPrompts() {
    const refreshAfterPrompts = Number.parseInt(refreshAfterPromptsInput?.value, 10);
    return Number.isFinite(refreshAfterPrompts) && refreshAfterPrompts > 0 ? refreshAfterPrompts : 0;
  }

  function getRepeatPerPrompt() {
    const repeat = Number.parseInt(repeatPerPromptInput?.value, 10);
    return Number.isFinite(repeat) && repeat >= 1 ? repeat : 1;
  }

  // Get settings from UI
  function getSettings() {
    const globalDelayMs = getGlobalDelayMs();
    return {
      type: document.querySelector('input[name="type"]:checked').value,
      ratio: document.querySelector('input[name="ratio"]:checked').value,
      batch: document.querySelector('input[name="batch"]:checked').value,
      downloadQuality: document.querySelector('input[name="downloadQuality"]:checked')?.value || 'default',
      globalDelayMs,
      globalDelaySeconds: globalDelayMs / 1000,
      refreshAfterPrompts: getRefreshAfterPrompts(),
      repeatPerPrompt: getRepeatPerPrompt()
    };
  }

  function waitForCooldown(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
  }

  async function runPromptCooldownIfNeeded(delayMs) {
    if (delayMs <= 0 || currentIndex === 0) return;

    const delaySeconds = Math.ceil(delayMs / 1000);
    appendLog(`Cooldown ${delaySeconds}s before next prompt...`, 'info');
    countdownRow.classList.remove('hidden');
    startCountdown(delaySeconds, 'Prompt cooldown', `Waiting ${delaySeconds}s before sending the next prompt...`);

    // Wait in small increments so we can break out early if paused/stopped
    const startTime = Date.now();
    while (Date.now() - startTime < delayMs) {
      if (!isRunning || isPaused) break;
      await new Promise(r => setTimeout(r, 200));
    }

    clearInterval(countdownInterval);
    countdownInterval = null;
    valCountdown.innerText = '--';
    if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';
    countdownRow.classList.add('hidden');
  }

  // Reset process state (but keep prompts)
  function resetProcessState() {
    currentIndex = 0;
    successCount = 0;
    failedCount = 0;
    downloadedCount = 0;
    isRunning = false;
    isPaused = false;
    clearInterval(countdownInterval);
    countdownInterval = null;
    remainingCountdown = 0;
    lastRefreshSuccessCount = 0;
    valCountdown.innerText = '--';
    if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';
    countdownRow.classList.add('hidden');
  }

  // Full reset (including prompts and UI)

  function fullReset() {
    stopProcess();
    resetProcessState();
    currentPrompts = [];
    prompts = [];
    queueData = [];
    currentIndex = 0;
    fileInput.value = '';
    fileLabel.innerText = 'Drop .TXT or .CSV here, or click to upload';
    manualInput.value = '';
    manualInput.classList.remove('processing');
    manualInput.readOnly = false;

    // Reset Generation Type to Image
    const typeImage = document.getElementById('typeImage');
    if (typeImage) typeImage.checked = true;

    // Reset Aspect Ratio to 16:9
    const r169 = document.getElementById('r169');
    if (r169) r169.checked = true;

    // Reset Batch Count to x4
    const b4 = document.getElementById('b4');
    if (b4) b4.checked = true;

    // Reset Download Quality to Default
    const dqDefault = document.getElementById('dqDefault');
    if (dqDefault) dqDefault.checked = true;

    // Reset User Controls inputs to defaults
    if (globalDelaySecondsInput) globalDelaySecondsInput.value = '5';
    if (refreshAfterPromptsInput) refreshAfterPromptsInput.value = '5';
    if (repeatPerPromptInput) repeatPerPromptInput.value = '1';

    // Re-apply ratio/quality filtering for Image type
    updateRatioOptions('image');
    updateDownloadQualityOptions('image');

    updateQueue();
    updateStats();
    logArea.innerHTML = '';
    appendLog('Extension reset to default state.', 'info');
  }

  function isFlowLandingUrl(url) {
    return /labs\.google(\.com)?\/fx\/(?:[^/]+\/)?tools\/flow\/?(?:[?#].*)?$/i.test(url || '');
  }

  function waitForTabProjectLoad(tabId, timeoutMs = 45000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(listener);
        reject(new Error('Timed out waiting for Flow project page to load'));
      }, timeoutMs);

      const listener = (updatedTabId, changeInfo, tab) => {
        if (updatedTabId !== tabId) return;
        const url = changeInfo.url || tab.url || '';
        if (/labs\.google(\.com)?\/fx\/(?:[^/]+\/)?tools\/flow\/project\//i.test(url) && changeInfo.status === 'complete') {
          clearTimeout(timer);
          chrome.tabs.onUpdated.removeListener(listener);
          resolve(tab);
        }
      };

      chrome.tabs.onUpdated.addListener(listener);
      chrome.tabs.get(tabId, (tab) => {
        if (chrome.runtime.lastError) return;
        const url = tab?.url || '';
        if (/labs\.google(\.com)?\/fx\/(?:[^/]+\/)?tools\/flow\/project\//i.test(url) && tab.status === 'complete') {
          clearTimeout(timer);
          chrome.tabs.onUpdated.removeListener(listener);
          resolve(tab);
        }
      });
    });
  }

  function waitForTabReload(tabId, timeoutMs = 60000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(listener);
        reject(new Error('Timed out waiting for Flow page refresh'));
      }, timeoutMs);

      const listener = (updatedTabId, changeInfo, tab) => {
        if (updatedTabId !== tabId) return;
        if (changeInfo.status === 'complete') {
          clearTimeout(timer);
          chrome.tabs.onUpdated.removeListener(listener);
          resolve(tab);
        }
      };

      chrome.tabs.onUpdated.addListener(listener);
    });
  }

  async function refreshTargetTabSafely(completedPrompts) {
    if (!targetTabId) {
      appendLog('Refresh skipped: target tab is no longer available.', 'warn');
      return;
    }

    appendLog(`Refreshing Flow page after ${completedPrompts} completed prompts...`, 'act');
    await new Promise((resolve, reject) => {
      chrome.tabs.reload(targetTabId, () => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve();
        }
      });
    });
    await waitForTabReload(targetTabId);
    await ensureContentScript(targetTabId);
    lastRefreshSuccessCount = completedPrompts;
    appendLog('Flow page refreshed. Continuing from saved queue progress.', 'success');
  }

  async function refreshAfterCompletedPromptIfNeeded(settings) {
    const refreshEvery = settings.refreshAfterPrompts || 0;
    if (refreshEvery <= 0) return;
    if (successCount <= 0 || currentIndex >= queueData.length) return;
    if (successCount === lastRefreshSuccessCount) return;
    if (successCount % refreshEvery !== 0) return;

    await refreshTargetTabSafely(successCount);
  }

  async function ensureContentScript(tabId) {
    try {
      await new Promise((resolve, reject) => {
        chrome.tabs.sendMessage(tabId, { action: "PING" }, (res) => {
          if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
          else resolve(res);
        });
      });
    } catch (e) {
      appendLog('Content script missing. Auto-injecting into page...', 'warn');
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['content.js']
      });
      await new Promise(r => setTimeout(r, 500));
    }
  }

  async function prepareFlowProjectIfNeeded(tab) {
    if (!isFlowLandingUrl(tab.url)) return tab;

    appendLog('Flow landing page detected. Creating project before applying sidepanel settings...', 'act');
    await ensureContentScript(tab.id);

    const createResponse = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tab.id, { action: "CREATE_PROJECT" }, (res) => {
        if (chrome.runtime.lastError) {
          resolve({ status: 'failed', message: chrome.runtime.lastError.message });
        } else {
          resolve(res || { status: 'failed', message: 'Empty response from content script.' });
        }
      });
    });

    if (createResponse.status !== 'success') {
      throw new Error(createResponse.message || 'Failed to create Flow project');
    }

    const projectTab = await waitForTabProjectLoad(tab.id);
    await ensureContentScript(tab.id);
    return projectTab;
  }

  // Start button handler
  btnStart.addEventListener('click', async () => {
    if (isPaused) {
      // Resume from pause
      isPaused = false;
      isRunning = true;
      btnStart.classList.add('hidden');
      btnPause.classList.remove('hidden');
      btnStop.classList.remove('hidden');
      manualInput.classList.add('processing');
      manualInput.readOnly = true;
      manualInput.style.display = 'none';
      promptDisplay.classList.add('visible');
      appendLog(`Process resumed from prompt ${currentIndex + 1}/${queueData.length}.`, 'act');

      if (remainingCountdown > 0) {
        startCountdown(remainingCountdown);
      }

      // Re-acquire target tab (user may have switched tabs)
      const [targetTab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (targetTab) {
        targetTabId = targetTab.id;
        try {
          await ensureContentScript(targetTab.id);
        } catch (err) {
          appendLog(`Warning: Could not verify content script: ${err.message}`, 'warn');
        }
      }

      processQueue(getSettings());
      return;
    }

    // Use current prompts from textarea (already synced via updateQueue)
    prompts = currentPrompts;

    if (prompts.length === 0) {
      appendLog('Please upload a file or type a prompt.', 'error');
      return;
    }

    resetProcessState();
    updateQueue(); // Reset all queue statuses to pending
    updateStats();
    countdownRow.classList.add('hidden');

    const settings = getSettings();

     isRunning = true;
     btnStart.classList.add('hidden');
     btnPause.classList.remove('hidden');
     btnStop.classList.remove('hidden');
     manualInput.classList.add('processing');
     manualInput.readOnly = true;
     manualInput.style.display = 'none';
     promptDisplay.classList.add('visible');
     renderPromptDisplay();

     const repeatInfo = settings.repeatPerPrompt > 1 ? `, ${settings.repeatPerPrompt}x repeat` : '';
     appendLog(`Starting Automation for ${queueData.length} tasks (${prompts.length} prompts${repeatInfo}, ${settings.batch}x batch per prompt)`, 'act');

    // Check active tab
    const [targetTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!targetTab) {
      appendLog('No active tab found to inject the content script.', 'error');
      stopProcess();
      return;
    }

    targetTabId = targetTab.id;

    try {
      await prepareFlowProjectIfNeeded(targetTab);
      await ensureContentScript(targetTab.id);
    } catch (err) {
      appendLog(`CRITICAL: ${err.message}. Please refresh the Flow page (F5) explicitly.`, 'error');
      stopProcess();
      return;
    }

    processQueue(settings);
  });

  // Main processing loop
   async function processQueue(settings) {
     const MAX_CONSECUTIVE_FAILURES = 3; // Auto-stop after 3 consecutive failures
     let consecutiveFailures = 0;
     const totalQueue = queueData.length;

     while (isRunning && !isPaused && currentIndex < totalQueue) {
       const promptData = queueData[currentIndex];
       promptData.status = 'processing';
       renderQueueTable();
       renderPromptDisplay(); // show active highlight immediately

        updateStats();
        manualInput.classList.add('processing');
        await runPromptCooldownIfNeeded(settings.globalDelayMs || 0);
        if (!isRunning || isPaused) {
          // Revert status since we haven't actually started this prompt
          promptData.status = 'pending';
          renderQueueTable();
          renderPromptDisplay();
          break;
        }
        // Show repeat info in log if repeating
        const repeatInfo = promptData.repeatTotal > 1 ? ` (repeat ${promptData.repeatIndex + 1}/${promptData.repeatTotal})` : '';
        appendLog(`[${currentIndex + 1}/${totalQueue}] Processing: "${promptData.prompt}"${repeatInfo}`, 'act');


      try {
        // Use stored targetTabId
        if (!targetTabId) {
          appendLog('Error: No target tab ID. Please re-focus the Flow page.', 'error');
          break;
        }

        const response = await new Promise((resolve) => {
          chrome.tabs.sendMessage(targetTabId, {
            action: "PROCESS_PROMPT",
            payload: { prompt: promptData.prompt, settings }
          }, (res) => {
            if (chrome.runtime.lastError) {
              resolve({ status: 'failed', message: `Connection error: ${chrome.runtime.lastError.message}` });
            } else {
              resolve(res || { status: 'failed', message: 'Empty response from content script.' });
            }
          });
        });

        if (!isRunning) break;

        if (response.status === 'success' || response.status === 'partial') {
          successCount++;
          consecutiveFailures = 0; // Reset on success
          const downloaded = response.downloaded || 0;
          downloadedCount += downloaded;
          promptData.generatedCount += downloaded;
          promptData.status = response.status === 'success' ? 'completed' : 'partial';
          const msg = response.status === 'partial'
            ? `[${currentIndex + 1}] ${response.message}`
            : `[${currentIndex + 1}] OK: ${response.ids ? response.ids.length : 1} variations saved.`;
          appendLog(msg, 'success');
        } else if (response.status === 'stopped') {
          appendLog(`[${currentIndex + 1}] Stopped by user.`, 'warn');
          break;
        } else {
          failedCount++;
          consecutiveFailures++;
          promptData.status = 'failed';
          appendLog(`[${currentIndex + 1}] Failed: ${response.message}`, 'error');

          // Auto-stop after too many consecutive failures
          if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
            appendLog(`AUTO-STOP: ${MAX_CONSECUTIVE_FAILURES} consecutive failures. The Create button may not be working. Please check the Flow page and try again.`, 'error');
            break;
          }
        }
      } catch (err) {
        failedCount++;
        consecutiveFailures++;
        promptData.status = 'failed';
        appendLog(`[${currentIndex + 1}] Execution Error: ${err.message}`, 'error');

        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
          appendLog(`AUTO-STOP: ${MAX_CONSECUTIVE_FAILURES} consecutive failures. Please check the Flow page.`, 'error');
          break;
        }
      }

       currentIndex++;
       updateStats();
       renderQueueTable();
       renderPromptDisplay();

       // Check if user pressed Pause while the prompt was running.
       // If paused, stop the loop gracefully AFTER the current prompt completed.
       if (isPaused) {
         break;
       }

       if (isRunning) {
         try {
           await refreshAfterCompletedPromptIfNeeded(settings);
         } catch (err) {
           appendLog(`Refresh failed: ${err.message}. Continuing without refresh.`, 'warn');
         }
       }
      }

    if (currentIndex >= totalQueue && isRunning) {
      appendLog('All prompts completed successfully!', 'success');
    }

    // If paused, don't call stopProcess — just exit the loop gracefully.
    // The user will resume later via the Start/Continue button.
    if (isPaused) {
      isRunning = false;
      return;
    }

    stopProcess();
  }

  // Pause button handler
  // Pause does NOT immediately stop the current prompt — it lets the current prompt
  // finish (generate + download), then pauses before the next prompt starts.
  btnPause.addEventListener('click', () => {
    if (isRunning && !isPaused) {
      isPaused = true;
      // NOTE: We do NOT set isRunning = false here!
      // The processQueue loop will check isPaused after the current prompt completes.
      btnPause.classList.add('hidden');
      btnStart.classList.remove('hidden');
      btnStart.querySelector('.btn-label').textContent = 'Continue';
      btnStop.classList.remove('hidden');
      appendLog('Process paused. Current prompt will finish, then queue will pause.', 'warn');

      // Stop countdown display (visual only)
      clearInterval(countdownInterval);
      countdownInterval = null;
    }
  });

  // Stop button handler
  btnStop.addEventListener('click', () => {
    stopProcess();
    appendLog('Process stopped by user.', 'warn');
    if (targetTabId) {
      chrome.tabs.sendMessage(targetTabId, { action: "STOP" }).catch(() => {});
    }
  });

  // Reset button handler
  btnReset.addEventListener('click', () => {
    stopProcess();
    fullReset();
  });

   function stopProcess() {
     isRunning = false;
     isPaused = false;
     clearInterval(countdownInterval);
     countdownInterval = null;
     targetTabId = null;
     btnStart.classList.remove('hidden');
     btnStart.querySelector('.btn-label').textContent = 'Start';
     btnPause.classList.add('hidden');
     btnStop.classList.add('hidden');
     manualInput.classList.remove('processing');
     manualInput.readOnly = false;
     manualInput.style.display = '';
     promptDisplay.classList.remove('visible');
     valCountdown.innerText = '--';
     if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';
     countdownRow.classList.add('hidden');

     // Mark any still-processing rows as failed (real stop, not pause)
     queueData.forEach(item => {
       if (item.status === 'processing') {
         item.status = 'failed';
       }
     });
     renderQueueTable();
     renderPromptDisplay();
   }

  // Start visual countdown timer
  function startCountdown(seconds, label = 'Cooldown active', hint = 'Waiting safely before continuing...') {
    remainingCountdown = seconds;
    const totalSeconds = Math.max(1, seconds);
    clearInterval(countdownInterval);
    countdownRow.classList.remove('hidden');
    if (cooldownLabel) cooldownLabel.innerText = label;
    if (cooldownHint) cooldownHint.innerText = hint;
    if (cooldownProgressFill) cooldownProgressFill.style.width = '100%';
    valCountdown.innerText = remainingCountdown;

    countdownInterval = setInterval(() => {
      if (!isRunning || isPaused) {
        return; // Don't decrement if paused or stopped
      }
      remainingCountdown--;
      valCountdown.innerText = Math.max(remainingCountdown, 0);
      if (cooldownProgressFill) {
        const progressPct = Math.max(0, (remainingCountdown / totalSeconds) * 100);
        cooldownProgressFill.style.width = `${progressPct}%`;
      }
      if (remainingCountdown <= 0) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        countdownRow.classList.add('hidden');
        if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';
      }
    }, 1000);
  }

   // Update stats display
   function updateStats() {
     const total = queueData.length;
     valQueue.innerText = total > 0 ? `${currentIndex} / ${total}` : '0 / 0';
     valSuccess.innerText = successCount;
     valFailed.innerText = failedCount;
     valDownloaded.innerText = downloadedCount;

     const p = total > 0 ? ((successCount + failedCount) / total) * 100 : 0;
     progressBar.style.width = `${p}%`;
     valPct.innerText = `${Math.round(p)}%`;

     // Update queue progress label
     updateQueueProgressLabel();
   }

  // Append log message
  function appendLog(message, type = 'info') {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    const wrapper = document.createElement('div');
    wrapper.className = 'log-line';

    let typeClass = 'log-info';
    let typeText = 'INF';
    if (type === 'error') { typeClass = 'log-error'; typeText = 'ERR'; }
    else if (type === 'success') { typeClass = 'log-success'; typeText = 'OK'; }
    else if (type === 'warn') { typeClass = 'log-warn'; typeText = 'WRN'; }
    else if (type === 'act') { typeClass = 'log-act'; typeText = 'ACT'; }

    wrapper.innerHTML = `<span class="log-time">[${time}]</span> <span class="${typeClass}">${typeText}</span> ${message}`;
    logArea.appendChild(wrapper);
    logArea.scrollTop = logArea.scrollHeight;
  }

  // Message listener for real-time logs from content script
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "LOG_FROM_CONTENT") {
      appendLog(`[Script] ${msg.message}`, 'info');
    }

    // Countdown timer updates from content script
    if (msg.action === "MONITOR_COUNTDOWN") {
      const remaining = msg.remaining;
      if (remaining !== undefined && isRunning && !isPaused) {
        remainingCountdown = remaining;
        valCountdown.innerText = remaining;
        if (remaining > 0) {
          countdownRow.classList.remove('hidden');
          // (re)start countdown interval if not already running
          if (!countdownInterval) {
            startCountdown(remaining);
          }
        } else {
          countdownRow.classList.add('hidden');
          clearInterval(countdownInterval);
      countdownInterval = null;
      if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';

        }
      }
    }

    if (msg.action === "DOWNLOAD_COOLDOWN_START") {
      const seconds = Math.max(1, Math.ceil(Number(msg.seconds) || 0));
      if (isRunning && !isPaused) {
        startCountdown(seconds, 'Download cooldown', `Waiting ${seconds}s before next download...`);
      }
    }

    if (msg.action === "DOWNLOAD_COOLDOWN_END") {
      clearInterval(countdownInterval);
      countdownInterval = null;
      valCountdown.innerText = '--';
      if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';
      countdownRow.classList.add('hidden');
    }

    // Batch completion
    if (msg.action === "BATCH_COMPLETE") {
      countdownRow.classList.add('hidden');
      clearInterval(countdownInterval);
      countdownInterval = null;
      if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';
    }
  });

  appendLog('Extension loaded. Ready to attach to page.', 'info');

  // Run detection on load
  initView();
  const initialType = document.querySelector('input[name="type"]:checked').value;
  updateRatioOptions(initialType);
  updateDownloadQualityOptions(initialType);

  // Re-check when extension window gains focus
  window.addEventListener('focus', () => {
    initView();
  });

  // Listen for tab URL changes
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (tabId && changeInfo.url) {
      checkCurrentTab().then(isOnFlow => {
        if (isOnFlow) {
          landingPage.classList.add('hidden');
          mainInterface.classList.remove('hidden');
          logArea.innerHTML = '';
          appendLog('Flow page loaded. Ready.', 'info');
        } else {
          landingPage.classList.remove('hidden');
          mainInterface.classList.add('hidden');
        }
      });
    }
  });

   // Listen for active tab changes
   chrome.tabs.onActivated.addListener(() => {
     initView();
   });

   // Initial view check when sidepanel loads
   initView();

  // ─── Auto-Update Checker UI ──────────────────────────────────────────────────
  const updateBanner = document.getElementById('updateBanner');
  const updateBtnDownload = document.getElementById('updateBtnDownload');
  const updateBtnDismiss = document.getElementById('updateBtnDismiss');
  const updateVersionLabel = document.getElementById('updateVersionLabel');
  const updateGuideModal = document.getElementById('updateGuideModal');
  const updateGuideClose = document.getElementById('updateGuideClose');

  function showUpdateBanner(remoteVersion, downloadUrl) {
    if (!updateBanner) return;
    if (updateVersionLabel) updateVersionLabel.textContent = `v${remoteVersion}`;
    updateBanner.classList.remove('hidden');
    updateBanner.dataset.downloadUrl = downloadUrl;
  }

  function hideUpdateBanner() {
    if (updateBanner) updateBanner.classList.add('hidden');
  }

  // Check stored update info on load
  chrome.storage.local.get(['updateAvailable', 'remoteVersion', 'localVersion', 'downloadUrl'], (data) => {
    if (data.updateAvailable && data.remoteVersion && data.downloadUrl) {
      const localVer = chrome.runtime.getManifest().version;
      // Only show if remote is still newer than current
      if (data.remoteVersion !== localVer) {
        showUpdateBanner(data.remoteVersion, data.downloadUrl);
      }
    }
  });

  // Listen for real-time update notification from background
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === 'UPDATE_AVAILABLE') {
      showUpdateBanner(msg.remoteVersion, msg.downloadUrl);
    }
  });

  // Download button — show guide modal then trigger download
  if (updateBtnDownload) {
    updateBtnDownload.addEventListener('click', () => {
      if (updateGuideModal) updateGuideModal.classList.remove('hidden');
      const url = updateBanner?.dataset?.downloadUrl;
      if (url) {
        chrome.downloads.download({ url: url, saveAs: true });
      }
    });
  }

  // Dismiss button
  if (updateBtnDismiss) {
    updateBtnDismiss.addEventListener('click', () => {
      hideUpdateBanner();
    });
  }

  // Close guide modal
  if (updateGuideClose) {
    updateGuideClose.addEventListener('click', () => {
      if (updateGuideModal) updateGuideModal.classList.add('hidden');
    });
  }

  // Close modal on backdrop click
  if (updateGuideModal) {
    updateGuideModal.addEventListener('click', (e) => {
      if (e.target === updateGuideModal) {
        updateGuideModal.classList.add('hidden');
      }
    });
  }

  // Trigger update check on sidepanel load
  chrome.runtime.sendMessage({ type: 'CHECK_FOR_UPDATE' }).catch(() => {});
 });
