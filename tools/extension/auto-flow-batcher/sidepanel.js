document.addEventListener('DOMContentLoaded', async () => {
  // UI Elements - Landing Page
  const landingPage = document.getElementById('landingPage');
  const mainInterface = document.getElementById('mainInterface');
  const btnOpenFlow = document.getElementById('btnOpenFlow');

  // UI Elements - Main Interface
  const fileInput = document.getElementById('fileInput');
  const manualInput = document.getElementById('manualInput');
  const btnStart = document.getElementById('btnStart');
  const btnStop = document.getElementById('btnStop');
  const logArea = document.getElementById('logArea');
  const progressBar = document.getElementById('progressBar');
  const valPct = document.getElementById('valPct');
  const totalPromptsLabel = document.getElementById('totalPromptsLabel');
  const fileLabel = document.getElementById('fileLabel');
  const modelSelect = document.getElementById('modelSelect');
  const typeGroup = document.getElementById('typeGroup');
  const btnClearLogs = document.getElementById('btnClearLogs');

  // Stats
  const valQueue = document.getElementById('valQueue');
  const valSuccess = document.getElementById('valSuccess');
  const valFailed = document.getElementById('valFailed');

  // Clear logs on every sidepanel open (clean start)
  logArea.innerHTML = '';

   let filePrompts = [];
   let prompts = [];
   let currentIndex = 0;
   let successCount = 0;
   let failedCount = 0;
   let isRunning = false;
   let targetTabId = null; // store tab ID for STOP messaging

   const MODELS = {
     image: ['Nano Banana 2', 'Nano Banana Pro', 'Imagen 4'],
     video: ['Veo 3.1 - Fast', 'Veo 3.1 - Lite', 'Veo 3.1 - Quality']
   };

   // Filter ratio options based on selected media type
   function updateRatioOptions(type) {
     const allRatioInputs = document.querySelectorAll('input[name="ratio"]');
     let validRatio = null;

     allRatioInputs.forEach(input => {
       const pill = input.closest('.radio-pill');
       const validFor = input.getAttribute('data-valid-for'); // e.g. "image,video"
       
       if (validFor) {
         const validTypes = validFor.split(',');
         if (validTypes.includes(type)) {
           pill.classList.remove('disabled');
           input.disabled = false;
         } else {
           pill.classList.add('disabled');
           input.disabled = true;
           // If currently checked and becomes invalid, switch to first valid
           if (input.checked) {
             input.checked = false;
             // Find first valid ratio for this type
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
     if(e.target.name === 'type') {
       const selectedType = document.querySelector('input[name="type"]:checked').value;
       modelSelect.innerHTML = MODELS[selectedType].map(m => `<option value="${m}">${m}</option>`).join('');
       // Filter ratio options based on media type
       updateRatioOptions(selectedType);
     }
   });

  const calculateTotal = () => {
    const manualPrompts = manualInput.value.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
    totalPromptsLabel.innerText = filePrompts.length + manualPrompts.length;
  };

  // Load file content
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    fileLabel.innerText = file.name;
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target.result;
      filePrompts = text.split(/\r?\n/).map(line => line.trim()).filter(line => line.length > 0);
      calculateTotal();
      appendLog(`Queue loaded: ${filePrompts.length} prompts from file.`, 'info');
    };
    reader.readAsText(file);
  });

  manualInput.addEventListener('input', calculateTotal);

  btnClearLogs.addEventListener('click', () => { logArea.innerHTML = ''; });

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
      landingPage.classList.remove('hidden');
      mainInterface.classList.add('hidden');
    }
  }

  // Open Flow in new tab
  btnOpenFlow.addEventListener('click', async () => {
    await chrome.tabs.create({ url: 'https://labs.google/fx/tools/flow' });
  });

  // Initialize main interface logic
  function initializeMainInterface() {
    // All the original automation logic goes here
    // (Will be rebuilt from scratch)
    appendLog('Extension loaded. Ready to attach to page.', 'info');
  }

  // Start button handler
  btnStart.addEventListener('click', async () => {
    const manualPrompts = manualInput.value.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
    prompts = [...filePrompts, ...manualPrompts];

    if (prompts.length === 0) {
      appendLog('Please upload a file or type a prompt.', 'error');
      return;
    }

    // Reset state for new run
    currentIndex = 0;
    successCount = 0;
    failedCount = 0;
    updateStats();

    // Gather Config
    const settings = {
      type: document.querySelector('input[name="type"]:checked').value,
      ratio: document.querySelector('input[name="ratio"]:checked').value,
      batch: document.querySelector('input[name="batch"]:checked').value,
      model: modelSelect.value
    };

    isRunning = true;
    btnStart.classList.add('hidden');
    btnStop.classList.remove('hidden');
    appendLog(`Starting Automation for ${prompts.length} tasks... (${settings.batch}x ${settings.model})`, 'act');

     // Check active tab
     const [targetTab] = await chrome.tabs.query({ active: true, currentWindow: true });
     if (!targetTab) {
       appendLog('No active tab found to inject the content script.', 'error');
       stopProcess();
       return;
     }

     // Store tabId for STOP
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

    processQueue(settings, targetTab.id);
  });

   btnStop.addEventListener('click', () => {
     stopProcess();
     appendLog('Process aborted by user.', 'warn');
     // Send STOP to stored tab
     if (targetTabId) {
       chrome.tabs.sendMessage(targetTabId, { action: "STOP" }).catch(() => {});
     }
   });

  async function processQueue(settings, tabId) {
    while (isRunning && currentIndex < prompts.length) {
      const prompt = prompts[currentIndex];
      updateStats();
      appendLog(`[${currentIndex + 1}/${prompts.length}] Processing ...`, 'act');

      try {
        const response = await new Promise((resolve) => {
          chrome.tabs.sendMessage(tabId, {
            action: "PROCESS_PROMPT",
            payload: { prompt, settings }
          }, (res) => {
            if (chrome.runtime.lastError) {
              resolve({ status: 'failed', message: 'Could not connect. Ensure you are on Google Flow.' });
            } else {
              resolve(res || { status: 'failed', message: 'Empty response.' });
            }
          });
        });

        if (!isRunning) break;

        if (response.status === 'success') {
          successCount++;
          appendLog(`[${currentIndex + 1}] OK: ${response.ids ? response.ids.length : 1} variations saved.`, 'success');
        } else {
          failedCount++;
          appendLog(`[${currentIndex + 1}] Failed: ${response.message}`, 'error');
        }
      } catch (err) {
        failedCount++;
        appendLog(`[${currentIndex + 1}] Execution Error: ${err.message}`, 'error');
      }

      currentIndex++;
      updateStats();
    }

    if (currentIndex >= prompts.length && isRunning) {
      appendLog('All prompts completed successfully!', 'success');
      stopProcess();
    }
  }

   function stopProcess() {
     isRunning = false;
     targetTabId = null;
     btnStart.classList.remove('hidden');
     btnStop.classList.add('hidden');
   }

  function updateStats() {
    const total = prompts.length;
    valQueue.innerText = total > 0 ? `${currentIndex} / ${total}` : '0 / 0';
    valSuccess.innerText = successCount;
    valFailed.innerText = failedCount;

    const p = total > 0 ? ((successCount + failedCount) / total) * 100 : 0;
    progressBar.style.width = `${p}%`;
    valPct.innerText = `${Math.round(p)}%`;
  }

  function appendLog(message, type = 'info') {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second:'2-digit', hour12: false });
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
  });

  appendLog('Extension loaded. Ready to attach to page.', 'info');

   // Run detection on load
   initView();
   // Initialize ratio filter for current type
   const initialType = document.querySelector('input[name="type"]:checked').value;
   updateRatioOptions(initialType);

  // Re-check when extension window gains focus
  window.addEventListener('focus', () => {
    initView();
  });

  // Listen for tab URL changes (dynamic detection)
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (tabId && changeInfo.url) {
      checkCurrentTab().then(isOnFlow => {
        if (isOnFlow) {
          landingPage.classList.add('hidden');
          mainInterface.classList.remove('hidden');
          // Clear logs on fresh navigation to Flow
          logArea.innerHTML = '';
          appendLog('Flow page loaded. Ready.', 'info');
        } else {
          landingPage.classList.remove('hidden');
          mainInterface.classList.add('hidden');
        }
      });
    }
  });

  // Listen for active tab changes (switch tabs)
  chrome.tabs.onActivated.addListener(() => {
    initView();
  });
});
