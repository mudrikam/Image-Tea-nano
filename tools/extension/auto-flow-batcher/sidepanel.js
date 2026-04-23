document.addEventListener('DOMContentLoaded', async () => {
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

  // UI Elements - Main Interface
  const fileInput = document.getElementById('fileInput');
  const fileDropArea = document.getElementById('fileDropArea');
  const manualInput = document.getElementById('manualInput');
  const logArea = document.getElementById('logArea');
  const progressBar = document.getElementById('progressBar');
  const valPct = document.getElementById('valPct');
  const totalPromptsLabel = document.getElementById('totalPromptsLabel');
  const fileLabel = document.getElementById('fileLabel');
  const typeGroup = document.getElementById('typeGroup');
  const queueTableBody = document.getElementById('queueTableBody');

  // UI Stats Elements
  const valQueue = document.getElementById('valQueue');
  const valSuccess = document.getElementById('valSuccess');
  const valFailed = document.getElementById('valFailed');
  const valDownloaded = document.getElementById('valDownloaded');
  const countdownRow = document.getElementById('countdownRow');
  const valCountdown = document.getElementById('valCountdown');

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

  // Update models on media type change
  typeGroup.addEventListener('change', (e) => {
    if (e.target.name === 'type') {
      const selectedType = document.querySelector('input[name="type"]:checked').value;
      updateRatioOptions(selectedType);
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

  // Load file content and auto-populate textarea
  function loadFileContent(file) {
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

  // Check if current tab is on Flow page
  async function checkCurrentTab() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const flowUrlPattern = /https?:\/\/labs\.google\/fx\/tools\/flow/i;
    return tab && flowUrlPattern.test(tab.url);
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

  // Open Flow in new tab
  btnOpenFlow.addEventListener('click', async () => {
    await chrome.tabs.create({ url: 'https://labs.google/fx/tools/flow' });
  });

  // Initialize main interface logic
  function initializeMainInterface() {
    appendLog('Extension loaded. Ready to attach to page.', 'info');
  }

  // Update queue data array and refresh table
  function updateQueue() {
    prompts = currentPrompts;

    // Rebuild queueData with fresh pending status
    queueData = prompts.map((prompt, idx) => ({
      prompt: prompt,
      status: 'pending',
      generatedCount: 0,
      index: idx
    }));

    totalPromptsLabel.innerText = prompts.length;
    valQueue.innerText = prompts.length > 0 ? `${currentIndex} / ${prompts.length}` : '0 / 0';
    renderQueueTable();
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

      row.innerHTML = `
        <td><span style="color: var(--text-muted); font-size: 10px;">#${idx + 1}</span></td>
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

  // Get settings from UI
  function getSettings() {
    return {
      type: document.querySelector('input[name="type"]:checked').value,
      ratio: document.querySelector('input[name="ratio"]:checked').value,
      batch: document.querySelector('input[name="batch"]:checked').value
    };
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
    valCountdown.innerText = '--';
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
    updateQueue();
    updateStats();
    logArea.innerHTML = '';
    appendLog('Extension reset to default state.', 'info');
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
      appendLog('Process resumed.', 'act');

      if (remainingCountdown > 0) {
        startCountdown(remainingCountdown);
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

    appendLog(`Starting Automation for ${prompts.length} prompts... (${settings.batch}x per prompt)`, 'act');

    // Check active tab
    const [targetTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!targetTab) {
      appendLog('No active tab found to inject the content script.', 'error');
      stopProcess();
      return;
    }

    targetTabId = targetTab.id;

    // Auto-inject content script if missing
    try {
      await new Promise((resolve, reject) => {
        chrome.tabs.sendMessage(targetTab.id, { action: "PING" }, (res) => {
          if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
          else resolve(res);
        });
      });
    } catch (e) {
      appendLog('Content script missing. Auto-injecting into page...', 'warn');
      try {
        await chrome.scripting.executeScript({
          target: { tabId: targetTab.id },
          files: ['content.js']
        });
        await new Promise(r => setTimeout(r, 500));
      } catch (err) {
        appendLog('CRITICAL: Cannot inject script. Please REFRESH the page (F5) explicitly.', 'error');
        stopProcess();
        return;
      }
    }

    processQueue(settings);
  });

  // Main processing loop
  async function processQueue(settings) {
    while (isRunning && currentIndex < prompts.length) {
      const promptData = queueData[currentIndex];
      promptData.status = 'processing';
      renderQueueTable();

      updateStats();
      manualInput.classList.add('processing');
      appendLog(`[${currentIndex + 1}/${prompts.length}] Processing: "${promptData.prompt}"`, 'act');

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
          const downloaded = response.downloaded || 0;
          downloadedCount += downloaded;
          promptData.generatedCount += downloaded;
          promptData.status = response.status === 'success' ? 'completed' : 'partial';
          const msg = response.status === 'partial'
            ? `[${currentIndex + 1}] ${response.message}`
            : `[${currentIndex + 1}] OK: ${response.ids ? response.ids.length : 1} variations saved.`;
          appendLog(msg, 'success');
        } else {
          failedCount++;
          promptData.status = 'failed';
          appendLog(`[${currentIndex + 1}] Failed: ${response.message}`, 'error');
        }
      } catch (err) {
        failedCount++;
        promptData.status = 'failed';
        appendLog(`[${currentIndex + 1}] Execution Error: ${err.message}`, 'error');
      }

      currentIndex++;
      updateStats();
      renderQueueTable();
    }

    if (currentIndex >= prompts.length && isRunning) {
      appendLog('All prompts completed successfully!', 'success');
      stopProcess();
    }
  }

  // Pause button handler
  btnPause.addEventListener('click', () => {
    if (isRunning) {
      isPaused = true;
      isRunning = false;
      btnPause.classList.add('hidden');
      btnStart.classList.remove('hidden');
      btnStop.classList.remove('hidden');
      manualInput.classList.remove('processing');
      appendLog('Process paused.', 'warn');

      // Stop countdown
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
    btnPause.classList.add('hidden');
    btnStop.classList.add('hidden');
    manualInput.classList.remove('processing');
    manualInput.readOnly = false;
    valCountdown.innerText = '--';
    countdownRow.classList.add('hidden');

    // Reset any processing rows
    queueData.forEach(item => {
      if (item.status === 'processing') {
        item.status = 'failed';
      }
    });
    renderQueueTable();
  }

  // Start countdown timer
  function startCountdown(seconds) {
    remainingCountdown = seconds;
    clearInterval(countdownInterval);
    countdownInterval = setInterval(() => {
      if (!isRunning || isPaused) {
        return; // Don't decrement if paused or stopped
      }
      remainingCountdown--;
      valCountdown.innerText = remainingCountdown;
      if (remainingCountdown <= 0) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        countdownRow.classList.add('hidden');
      }
    }, 1000);
  }

  // Update stats display
  function updateStats() {
    const total = prompts.length;
    valQueue.innerText = total > 0 ? `${currentIndex} / ${total}` : '0 / 0';
    valSuccess.innerText = successCount;
    valFailed.innerText = failedCount;
    valDownloaded.innerText = downloadedCount;

    const p = total > 0 ? ((successCount + failedCount) / total) * 100 : 0;
    progressBar.style.width = `${p}%`;
    valPct.innerText = `${Math.round(p)}%`;
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
        }
      }
    }

    // Batch completion
    if (msg.action === "BATCH_COMPLETE") {
      countdownRow.classList.add('hidden');
      clearInterval(countdownInterval);
      countdownInterval = null;
    }
  });

  appendLog('Extension loaded. Ready to attach to page.', 'info');

  // Run detection on load
  initView();
  const initialType = document.querySelector('input[name="type"]:checked').value;
  updateRatioOptions(initialType);

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
});
