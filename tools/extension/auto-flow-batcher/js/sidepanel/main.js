/**
 * Auto Flow Batcher - Main Sidepanel Entry Point
 * Orchestrates event listeners, tab switching, file drops, Chrome messaging, and auto-update flow.
 */

import { state, resetProcessState, fullResetState } from './state.js';
import { parsePrompts, readFileAsync } from './file_parser.js';
import { updateQueue, renderQueueTable, renderPromptDisplay, updateQueueProgressLabel } from './queue_manager.js';
import { 
  getUIElements, 
  switchTab, 
  appendLog, 
  updateStats, 
  startCountdown, 
  stopCountdown, 
  updateRatioOptions, 
  updateModelOptions,
  updateDownloadQualityOptions, 
  getSettings, 
  saveSettingsToStorage,
  loadSettingsFromStorage,
  restoreModeSettings,
  getRepeatPerPrompt,
  setStepMode, 
  updateStepButton 
} from './ui_manager.js';
import { 
  checkCurrentTab, 
  isFlowLandingUrl, 
  ensureContentScript, 
  prepareFlowProjectIfNeeded 
} from './navigation_manager.js';
import { runOneStep, processQueue, stopProcess } from './automation_runner.js';
import { 
  authState, 
  loadSavedAuthSession, 
  initiateDevicePairing, 
  cancelDevicePairing, 
  logoutCioraSession, 
  fetchRemoteCoreEngine 
} from './auth_manager.js';
import { 
  licenseState, 
  verifyAppLicense 
} from './license_manager.js';

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

  // ─── Tandem Mode Live Badge ─────────────────────────────────────────────
  const tandemBadge = document.getElementById('tandemBadge');
  function updateTandemBadge(connected) {
    if (tandemBadge) {
      if (connected) {
        tandemBadge.classList.add('active');
        tandemBadge.classList.remove('hidden');
      } else {
        tandemBadge.classList.remove('active');
        tandemBadge.classList.add('hidden');
      }
    }
  }
  // Check initial tandem connection state
  try {
    chrome.runtime.sendMessage({ type: 'GET_TANDEM_STATUS' }, (res) => {
      if (res?.connected) updateTandemBadge(true);
    });
  } catch (_) {}

  const elements = getUIElements();
  const {
    landingPage, mainInterface, btnOpenFlow,
    btnStart, btnPause, btnStop, btnReset,
    btnToggleStepMode, btnStep, btnStopStep, btnRetryStep,
    btnLoadTXT, btnLoadCSV, btnClearLogs, btnCopyLogs, btnPaste, btnClearInput,
    promptDisplay, fileInput, fileDropArea, manualInput, logArea,
    typeGroup, repeatPerPromptInput,
    countdownRow, valCountdown, cooldownProgressFill,
    tabBtnPrompts, tabBtnMode, tabBtnLogs, tabPrompts, tabMode, tabLogs,
    updateBanner, updateBtnDownload, updateBtnDismiss, updateVersionLabel,
    updateGuideModal, updateGuideClose
  } = elements;

  // ─── CIORA Universal Device Auth & UI Binding ───────────────────────────
  const btnConnectCiora = document.getElementById('btnConnectCiora');
  const cioraPairingStatus = document.getElementById('cioraPairingStatus');
  const btnCancelPair = document.getElementById('btnCancelPair');
  const cioraProfileBar = document.getElementById('cioraProfileBar');
  const cioraUserAvatar = document.getElementById('cioraUserAvatar');
  const cioraUserName = document.getElementById('cioraUserName');
  const cioraProfilePopover = document.getElementById('cioraProfilePopover');
  const popoverFullName = document.getElementById('popoverFullName');
  const popoverEmail = document.getElementById('popoverEmail');
  const btnOpenCioraDashboard = document.getElementById('btnOpenCioraDashboard');
  const btnLogoutCiora = document.getElementById('btnLogoutCiora');

  // ─── CIORA License Authority & UI Lock State ─────────────────────────────
  const licenseTierBadge = document.getElementById('licenseTierBadge');
  const licenseTierText = document.getElementById('licenseTierText');
  const licenseNoticeBanner = document.getElementById('licenseNoticeBanner');
  const licenseNoticeText = document.getElementById('licenseNoticeText');

  function renderLicenseState() {
    if (!authState.isPaired) {
      // 1. Unpaired: Lock GUI, hide tier pill, show pairing notice
      document.body.classList.add('license-locked');
      licenseTierBadge?.classList.add('hidden');
      if (licenseNoticeBanner) {
        licenseNoticeBanner.classList.remove('hidden');
        if (licenseNoticeText) {
          licenseNoticeText.textContent = 'Hubungkan akun CIORA untuk memvalidasi lisensi software.';
        }
      }
      return;
    }

    if (licenseState.isValid) {
      // 2. Valid License: Unlock GUI, show tier pill, hide notice banner
      document.body.classList.remove('license-locked');
      if (licenseNoticeBanner) {
        licenseNoticeBanner.classList.add('hidden');
      }

      if (licenseTierBadge) {
        const tier = (licenseState.tier || 'pro').toLowerCase();
        licenseTierBadge.className = `license-tier-badge tier-${tier}`;
        if (licenseTierText) {
          licenseTierText.textContent = tier.toUpperCase();
        }
        licenseTierBadge.title = `CIORA License Active: ${tier.toUpperCase()}`;
        licenseTierBadge.classList.remove('hidden');
      }
    } else {
      // 3. Paired but No Matching License: Lock GUI with blur, show missing license notice
      document.body.classList.add('license-locked');
      licenseTierBadge?.classList.add('hidden');
      if (licenseNoticeBanner) {
        licenseNoticeBanner.classList.remove('hidden');
        if (licenseNoticeText) {
          licenseNoticeText.textContent = 'Akun belum memiliki lisensi untuk Auto Flow Batcher.';
        }
      }
    }
  }

  async function checkAppLicense() {
    if (!authState.cdeToken) {
      licenseState.isValid = false;
      renderLicenseState();
      return;
    }

    const result = await verifyAppLicense(authState.cdeToken, 'auto-flow-batcher');
    renderLicenseState();

    if (!result.valid) {
      appendLog('Perhatian: Akun CIORA kamu belum memiliki lisensi aktif untuk Auto Flow Batcher.', 'warn');
    }
  }

  function updateAuthUI() {
    if (authState.isPaired && authState.user) {
      // Paired state
      btnConnectCiora?.classList.add('hidden');
      cioraPairingStatus?.classList.add('hidden');
      cioraProfileBar?.classList.remove('hidden');

      const name = authState.user.name || authState.user.email?.split('@')[0] || 'CIORA User';
      const email = authState.user.email || 'user@ciora.id';
      const avatar = authState.user.imageUrl || authState.user.avatarUrl || authState.user.picture || '';

      if (cioraUserName) cioraUserName.textContent = name;
      if (cioraUserAvatar) {
        if (avatar) {
          cioraUserAvatar.src = avatar;
          cioraUserAvatar.classList.remove('hidden');
        } else {
          // Generate nice initial badge or fallback
          cioraUserAvatar.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=f27d26&color=fff&size=36`;
        }
      }
      if (popoverFullName) popoverFullName.textContent = name;
      if (popoverEmail) popoverEmail.textContent = email;

      // Unlock Start button
      if (btnStart) {
        btnStart.classList.remove('btn-disabled-gate');
        btnStart.removeAttribute('title');
      }
    } else if (authState.isPolling) {
      // Pairing in progress
      btnConnectCiora?.classList.add('hidden');
      cioraPairingStatus?.classList.remove('hidden');
      cioraProfileBar?.classList.add('hidden');
      cioraProfilePopover?.classList.add('hidden');

      // Lock Start button
      if (btnStart) {
        btnStart.classList.add('btn-disabled-gate');
        btnStart.title = 'Pairing with CIORA required to start automation.';
      }
    } else {
      // Unpaired state
      btnConnectCiora?.classList.remove('hidden');
      cioraPairingStatus?.classList.add('hidden');
      cioraProfileBar?.classList.add('hidden');
      cioraProfilePopover?.classList.add('hidden');

      // Lock Start button
      if (btnStart) {
        btnStart.classList.add('btn-disabled-gate');
        btnStart.title = 'Please connect your CIORA account to start automation.';
      }
    }
  }

  // Load persistent auth session & verify app license
  await loadSavedAuthSession();
  updateAuthUI();
  await checkAppLicense();

  // Connect button click
  btnConnectCiora?.addEventListener('click', () => {
    initiateDevicePairing((status, data) => {
      if (status === 'requesting_code') {
        appendLog('Initiating CIORA device authorization...', 'info');
      } else if (status === 'waiting_approval') {
        appendLog(`Pairing code opened in browser: "${data.user_code}". Waiting for approval...`, 'act');
      } else if (status === 'approved') {
        appendLog(`CIORA Account connected successfully: ${data.user?.email || 'User'} ✓`, 'success');
        checkAppLicense();
      } else if (status === 'denied') {
        appendLog('CIORA device pairing was denied by user.', 'warn');
      } else if (status === 'expired') {
        appendLog('Pairing code expired. Please click Connect CIORA again.', 'warn');
      } else if (status === 'error') {
        appendLog(`Pairing error: ${data.message}`, 'error');
      }
      updateAuthUI();
    });
    updateAuthUI();
  });

  // Cancel pairing button
  btnCancelPair?.addEventListener('click', (e) => {
    e.stopPropagation();
    cancelDevicePairing();
    appendLog('CIORA device pairing cancelled.', 'warn');
    updateAuthUI();
  });

  // Toggle Profile Popover
  cioraProfileBar?.addEventListener('click', (e) => {
    e.stopPropagation();
    cioraProfilePopover?.classList.toggle('hidden');
  });

  // Close popover when clicking anywhere outside
  document.addEventListener('click', (e) => {
    if (!cioraProfileBar?.contains(e.target) && !cioraProfilePopover?.contains(e.target)) {
      cioraProfilePopover?.classList.add('hidden');
    }
  });

  // Open CIORA Dashboard
  btnOpenCioraDashboard?.addEventListener('click', () => {
    cioraProfilePopover?.classList.add('hidden');
    chrome.tabs.create({ url: 'https://ciora.id/dashboard' });
  });

  // Logout / Disconnect Device
  btnLogoutCiora?.addEventListener('click', async () => {
    cioraProfilePopover?.classList.add('hidden');
    await logoutCioraSession();
    licenseState.isValid = false;
    renderLicenseState();
    appendLog('CIORA Account disconnected. Extension locked.', 'warn');
    updateAuthUI();
  });

  // Clear logs on every sidepanel open
  if (logArea) logArea.innerHTML = '';

  // Tab Switcher
  if (tabBtnPrompts && tabBtnMode && tabBtnLogs) {
    tabBtnPrompts.addEventListener('click', () => switchTab(tabBtnPrompts, tabPrompts, elements));
    tabBtnMode.addEventListener('click', () => switchTab(tabBtnMode, tabMode, elements));
    tabBtnLogs.addEventListener('click', () => switchTab(tabBtnLogs, tabLogs, elements));
  }

  // Ratio / Model / Quality change listener on Media Type change
  if (typeGroup) {
    typeGroup.addEventListener('change', (e) => {
      if (e.target.name === 'type') {
        const selectedType = document.querySelector('input[name="type"]:checked')?.value || 'image';
        updateRatioOptions(selectedType);
        updateModelOptions(selectedType);
        updateDownloadQualityOptions(selectedType);

        // Instantly restore the specific settings saved for this mode!
        chrome.storage.local.get(['afb_saved_settings'], (data) => {
          if (data && data.afb_saved_settings) {
            restoreModeSettings(selectedType, data.afb_saved_settings);
            updateModelOptions(selectedType);
          }
          saveSettingsToStorage();
        });
      }
    });
  }

  // Model change listener to update duration/resolution visibility when on Video mode
  const modelGroup = document.getElementById('modelGroup');
  if (modelGroup) {
    modelGroup.addEventListener('change', (e) => {
      if (e.target.name === 'model') {
        const selectedType = document.querySelector('input[name="type"]:checked')?.value || 'image';
        updateModelOptions(selectedType);
        saveSettingsToStorage();
      }
    });
  }

  // Load File helper
  async function loadFileContent(file) {
    if (state.isRunning) {
      appendLog('Cannot load file while processing. Stop first.', 'warn');
      return;
    }
    try {
      const { text, prompts, fileName } = await readFileAsync(file);
      if (elements.fileLabel) elements.fileLabel.innerText = fileName;
      state.currentPrompts = prompts;
      if (manualInput) manualInput.value = text;
      if (fileInput) fileInput.value = ''; // Reset so same file can be re-selected
      updateQueue(getRepeatPerPrompt(), () => updateStepButton(elements));
      appendLog(`Queue loaded: ${state.currentPrompts.length} prompts from file.`, 'info');
    } catch (err) {
      appendLog(`Failed to read file: ${err.message}`, 'error');
    }
  }

  // File input change handler
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (file) {
        loadFileContent(file);
      }
    });
  }

  // Manual input handler
  if (manualInput) {
    manualInput.addEventListener('input', () => {
      const text = manualInput.value;
      state.currentPrompts = parsePrompts(text);
      updateQueue(getRepeatPerPrompt(), () => updateStepButton(elements));
    });
  }

  // Repeat per prompt change handler - rebuild queue when repeat changes
  if (repeatPerPromptInput) {
    repeatPerPromptInput.addEventListener('input', () => {
      if (!state.isRunning) {
        updateQueue(getRepeatPerPrompt(), () => updateStepButton(elements));
      }
    });
  }

  // Copy logs button
  if (btnCopyLogs) {
    btnCopyLogs.addEventListener('click', async () => {
      const logText = logArea?.innerText || logArea?.textContent || '';
      if (!logText.trim()) {
        appendLog('No logs to copy.', 'warn');
        return;
      }
      try {
        await navigator.clipboard.writeText(logText);
        const origTitle = btnCopyLogs.title;
        btnCopyLogs.title = 'Copied!';
        btnCopyLogs.style.color = 'var(--success)';
        setTimeout(() => { btnCopyLogs.title = origTitle; btnCopyLogs.style.color = ''; }, 1500);
      } catch (err) {
        appendLog('Failed to copy logs: ' + err.message, 'error');
      }
    });
  }

  // Clear logs button
  if (btnClearLogs) {
    btnClearLogs.addEventListener('click', () => {
      if (logArea) logArea.innerHTML = '';
      appendLog('Logs cleared.', 'info');
    });
  }

  // Load TXT button
  if (btnLoadTXT) {
    btnLoadTXT.addEventListener('click', (e) => {
      e.stopPropagation();
      if (fileInput) {
        fileInput.accept = '.txt';
        fileInput.click();
      }
    });
  }

  // Load CSV button
  if (btnLoadCSV) {
    btnLoadCSV.addEventListener('click', (e) => {
      e.stopPropagation();
      if (fileInput) {
        fileInput.accept = '.csv';
        fileInput.click();
      }
    });
  }

  // Paste button
  if (btnPaste) {
    btnPaste.addEventListener('click', async () => {
      if (state.isRunning) {
        appendLog('Cannot paste while processing. Stop first.', 'warn');
        return;
      }
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          if (manualInput) manualInput.value = text;
          state.currentPrompts = parsePrompts(text);
          updateQueue(getRepeatPerPrompt(), () => updateStepButton(elements));
          appendLog('Pasted prompts from clipboard.', 'info');
        }
      } catch (err) {
        appendLog('Failed to read clipboard: ' + err.message, 'error');
      }
    });
  }

  // Clear button
  if (btnClearInput) {
    btnClearInput.addEventListener('click', () => {
      if (state.isRunning) {
        appendLog('Cannot clear while processing. Stop first.', 'warn');
        return;
      }
      if (manualInput) manualInput.value = '';
      state.currentPrompts = [];
      updateQueue(getRepeatPerPrompt(), () => updateStepButton(elements));
      appendLog('Prompts cleared.', 'info');
    });
  }

  // View state initialisation based on current tab
  async function initView() {
    const isOnFlow = await checkCurrentTab();
    if (isOnFlow) {
      landingPage?.classList.add('hidden');
      mainInterface?.classList.remove('hidden');
    } else {
      landingPage?.classList.remove('hidden');
      mainInterface?.classList.add('hidden');
    }
  }

  // Open Flow in new tab
  if (btnOpenFlow) {
    btnOpenFlow.addEventListener('click', async () => {
      let flowUrl = 'https://flow.google.com/';
      await chrome.tabs.create({ url: flowUrl });
    });
  }

  // Full reset helper
  function fullReset() {
    stopProcess(elements);
    fullResetState();

    if (fileInput) fileInput.value = '';
    if (elements.fileLabel) elements.fileLabel.innerText = 'Drop .TXT or .CSV here, or click to upload';
    if (manualInput) {
      manualInput.value = '';
      manualInput.classList.remove('processing');
      manualInput.readOnly = false;
    }

    const typeImage = document.getElementById('typeImage');
    if (typeImage) typeImage.checked = true;

    const r169 = document.getElementById('r169');
    if (r169) r169.checked = true;

    const mNano2 = document.getElementById('mNano2');
    if (mNano2) mNano2.checked = true;

    const vd8s = document.getElementById('vd8s');
    if (vd8s) vd8s.checked = true;

    const vr720p = document.getElementById('vr720p');
    if (vr720p) vr720p.checked = true;

    const b1 = document.getElementById('b1');
    if (b1) b1.checked = true;

    const dqDefault = document.getElementById('dqDefault');
    if (dqDefault) dqDefault.checked = true;

    if (elements.globalDelaySecondsInput) elements.globalDelaySecondsInput.value = '30';
    if (elements.refreshAfterPromptsInput) elements.refreshAfterPromptsInput.value = '5';
    if (elements.newProjectAfterPromptsInput) elements.newProjectAfterPromptsInput.value = '0';
    if (elements.repeatPerPromptInput) elements.repeatPerPromptInput.value = '1';

    if (state.isStepMode) {
      if (btnStep) {
        btnStep.disabled = true;
        btnStep.classList.remove('step-ready');
        const label = btnStep.querySelector('.btn-step-label');
        if (label) label.textContent = 'Generation Step';
      }
      if (elements.stepIndicator) elements.stepIndicator.textContent = 'Step 0/0';
    }

    updateRatioOptions('image');
    updateModelOptions('image');
    updateDownloadQualityOptions('image');

    saveSettingsToStorage();

    updateQueue(1, () => updateStepButton(elements));
    updateStats();
    if (logArea) logArea.innerHTML = '';
    appendLog('Extension reset to default state.', 'info');
  }

  // Start button handler
  if (btnStart) {
    btnStart.addEventListener('click', async () => {
      if (state.isPaused) {
        // Resume from pause
        state.isPaused = false;
        state.isRunning = true;
        btnStart.classList.add('hidden');
        btnPause?.classList.remove('hidden');
        btnStop?.classList.remove('hidden');
        if (manualInput) {
          manualInput.classList.add('processing');
          manualInput.readOnly = true;
          manualInput.style.display = 'none';
        }
        promptDisplay?.classList.add('visible');
        appendLog(`Process resumed from prompt ${state.currentIndex + 1}/${state.queueData.length}.`, 'act');

        if (state.remainingCountdown > 0) {
          startCountdown(state.remainingCountdown);
        }

        const [targetTab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (targetTab) {
          state.targetTabId = targetTab.id;
          try {
            await ensureContentScript(targetTab.id, appendLog);
            await new Promise(r => setTimeout(r, 2000));
          } catch (err) {
            appendLog(`Warning: Could not verify content script: ${err.message}`, 'warn');
          }
        }

        processQueue(getSettings(), elements);
        return;
      }

      // 0. Gatecheck: Must be paired with CIORA and possess valid license
      if (!authState.isPaired || !authState.cdeToken) {
        appendLog('Access locked: Please connect your CIORA account at the bottom footer to start.', 'warn');
        btnConnectCiora?.click();
        return;
      }

      if (!licenseState.isValid) {
        appendLog('Access locked: Akun kamu belum memiliki lisensi aktif untuk Auto Flow Batcher.', 'error');
        return;
      }

      state.prompts = state.currentPrompts;
      if (state.prompts.length === 0) {
        appendLog('Please upload a file or type a prompt.', 'error');
        return;
      }

      resetProcessState();
      updateQueue(getRepeatPerPrompt(), () => updateStepButton(elements));
      updateStats();
      if (countdownRow) countdownRow.classList.add('hidden');

      const settings = getSettings();

      // Check active tab
      const [targetTab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!targetTab) {
        appendLog('No active tab found to inject the content script.', 'error');
        stopProcess(elements);
        return;
      }
      state.targetTabId = targetTab.id;
      const tabUrl = targetTab.url || '';
      appendLog(`[Check] Tab URL: ${tabUrl}`, 'info');

      if (isFlowLandingUrl(tabUrl)) {
        appendLog('[Check] Detected: Flow HOME page → Will click New Project', 'info');
      } else if (/flow\.google\.com\/project\//i.test(tabUrl) || /labs\.google.*\/tools\/flow\/project\//i.test(tabUrl)) {
        appendLog('[Check] Detected: Flow PROJECT page → Skipping New Project', 'info');
      } else {
        appendLog('[Check] Warning: URL is not a recognized Flow page!', 'warn');
      }

      try {
        await prepareFlowProjectIfNeeded(targetTab, appendLog);
        await ensureContentScript(targetTab.id, appendLog);
      } catch (err) {
        appendLog(`CRITICAL: ${err.message}. Please refresh the Flow page (F5) explicitly.`, 'error');
        stopProcess(elements);
        return;
      }

      // Fetch dynamic Runtime Signatures from CIORA Storage & inject into tab memory
      try {
        appendLog('[Security] Authenticating session & loading runtime signatures from CIORA Storage...', 'act');
        const runtimeConfig = await fetchRemoteCoreEngine(authState.cdeToken);
        appendLog(`[Security] Authenticated! Live Signature from CIORA Server: "${runtimeConfig.protocol}" (v${runtimeConfig.version}) ✓`, 'success');

        const injectRes = await new Promise((resolve) => {
          chrome.tabs.sendMessage(targetTab.id, { action: 'INITIALIZE_RUNTIME_CONFIG', config: runtimeConfig }, (res) => {
            if (chrome.runtime.lastError || !res) resolve({ status: 'failed' });
            else resolve(res);
          });
        });

        if (injectRes.status !== 'ok') {
          throw new Error('Failed to initialize dynamic runtime signatures in tab memory.');
        }
        appendLog('[Security] Dynamic runtime signatures loaded into memory successfully ✓', 'success');
      } catch (authErr) {
        appendLog(`[Security] ${authErr.message}`, 'error');
        stopProcess(elements);
        return;
      }

      // Check page & prepare page
      await new Promise((resolve) => {
        chrome.tabs.sendMessage(targetTab.id, { action: 'CHECK_PAGE' }, (res) => {
          if (chrome.runtime.lastError || !res) {
            appendLog('[Check] Could not check page state (content script may be initializing)', 'warn');
          } else {
            appendLog(`[Check] Agent mode: ${res.agentMode}`, 'info');
            appendLog(`[Check] Agent panel: ${res.agentPanel}`, 'info');
            appendLog(`[Check] Prompt input: ${res.editor}`, 'info');
          }
          resolve();
        });
      });

      const prepareResult = await new Promise((resolve) => {
        chrome.tabs.sendMessage(targetTab.id, { action: 'PREPARE_PAGE' }, (res) => {
          if (chrome.runtime.lastError || !res) {
            resolve({ status: 'failed', message: 'No response from PREPARE_PAGE' });
          } else {
            resolve(res);
          }
        });
      });

      if (prepareResult.status !== 'ready') {
        appendLog(`[Prepare] Failed: ${prepareResult.message || 'Unknown error'}`, 'error');
        stopProcess(elements);
        return;
      }
      appendLog('[Prepare] Page is ready ✓', 'info');

      state.isRunning = true;
      btnStart.classList.add('hidden');
      btnPause?.classList.remove('hidden');
      btnStop?.classList.remove('hidden');
      if (manualInput) {
        manualInput.classList.add('processing');
        manualInput.readOnly = true;
        manualInput.style.display = 'none';
      }
      promptDisplay?.classList.add('visible');
      renderPromptDisplay();

      const repeatInfo = settings.repeatPerPrompt > 1 ? `, ${settings.repeatPerPrompt}x repeat` : '';
      if (state.isStepMode) {
        appendLog(`Step Mode: ${state.queueData.length} tasks ready (${state.prompts.length} prompts${repeatInfo}). Click "Generation Step" to run each one.`, 'act');
        updateStepButton(elements);
      } else {
        appendLog(`Starting Automation for ${state.queueData.length} tasks (${state.prompts.length} prompts${repeatInfo}, ${settings.batch}x batch per prompt)`, 'act');
        processQueue(settings, elements);
      }
    });
  }

  // Step button handler
  if (btnStep) {
    btnStep.addEventListener('click', async () => {
      if (!state.isStepMode) return;

      if (!state.isRunning) {
        state.prompts = state.currentPrompts;
        if (state.prompts.length === 0) {
          appendLog('Please upload a file or type a prompt.', 'error');
          return;
        }

        resetProcessState();
        updateQueue(getRepeatPerPrompt(), () => updateStepButton(elements));
        updateStats();
        if (countdownRow) countdownRow.classList.add('hidden');

        if (state.queueData.length === 0) {
          appendLog('No prompts in queue.', 'error');
          return;
        }

        const settings = getSettings();
        state.isRunning = true;
        btnStart?.classList.add('hidden');
        btnPause?.classList.remove('hidden');
        btnStop?.classList.remove('hidden');
        if (manualInput) {
          manualInput.classList.add('processing');
          manualInput.readOnly = true;
          manualInput.style.display = 'none';
        }
        promptDisplay?.classList.add('visible');
        renderPromptDisplay();

        const repeatInfo = settings.repeatPerPrompt > 1 ? `, ${settings.repeatPerPrompt}x repeat` : '';
        appendLog(`Step Mode: ${state.queueData.length} tasks (${state.prompts.length} prompts${repeatInfo}). Running step 1...`, 'act');

        const [targetTab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!targetTab) {
          appendLog('No active tab found.', 'error');
          stopProcess(elements);
          return;
        }

        state.targetTabId = targetTab.id;
        const tabUrl = targetTab.url || '';
        appendLog(`[Check] Tab URL: ${tabUrl}`, 'info');

        if (isFlowLandingUrl(tabUrl)) {
          appendLog('[Check] Detected: Flow HOME page → Will click New Project', 'info');
        } else if (/flow\.google\.com\/project\//i.test(tabUrl) || /labs\.google.*\/tools\/flow\/project\//i.test(tabUrl)) {
          appendLog('[Check] Detected: Flow PROJECT page → Skipping New Project', 'info');
        } else {
          appendLog('[Check] Warning: URL is not a recognized Flow page!', 'warn');
        }

        try {
          await prepareFlowProjectIfNeeded(targetTab, appendLog);
          await ensureContentScript(targetTab.id, appendLog);
        } catch (err) {
          appendLog(`CRITICAL: ${err.message}. Please refresh the Flow page (F5).`, 'error');
          stopProcess(elements);
          return;
        }
      }

      // If all done, restart from beginning
      if (state.currentIndex >= state.queueData.length) {
        state.currentIndex = 0;
        state.queueData.forEach(item => { item.status = 'pending'; item.generatedCount = 0; });
        state.successCount = 0;
        state.failedCount = 0;
        state.downloadedCount = 0;
        updateStats();
        renderQueueTable();
        renderPromptDisplay();
        appendLog('Restarting from step 1...', 'act');
      }

      btnStep.disabled = true;
      btnStep.classList.remove('step-ready');
      const label = btnStep.querySelector('.btn-step-label');
      if (label) label.textContent = 'Running...';
      updateStepButton(elements);

      await runOneStep(getSettings(), elements);

      if (label) label.textContent = '';
      updateStepButton(elements);
    });
  }

  // Toggle Step Mode button
  if (btnToggleStepMode) {
    btnToggleStepMode.addEventListener('click', () => {
      if (state.isRunning) {
        appendLog('Cannot toggle Step Mode while running. Stop first.', 'warn');
        return;
      }
      setStepMode(!state.isStepMode, elements);
    });
  }

  // Stop Step button
  if (btnStopStep) {
    btnStopStep.addEventListener('click', () => {
      if (!state.isStepMode || !state.isRunning) return;
      state.isStepStopped = true;
      appendLog('Step stop requested. Aborting current step...', 'warn');
      if (state.targetTabId) {
        chrome.tabs.sendMessage(state.targetTabId, { action: "STOP" }).catch(() => {});
      }
    });
  }

  // Retry Step button
  if (btnRetryStep) {
    btnRetryStep.addEventListener('click', async () => {
      if (!state.isStepMode) return;

      const currentStepStatus = state.queueData[state.currentIndex]?.status;
      const needsDecrement = (currentStepStatus !== 'stopped' && currentStepStatus !== 'failed') && state.currentIndex > 0;

      if (needsDecrement) {
        state.currentIndex--;
      }

      if (state.currentIndex < 0) {
        appendLog('No step to retry.', 'warn');
        return;
      }

      if (state.currentIndex >= state.queueData.length) {
        state.currentIndex = state.queueData.length - 1;
      }

      const retryData = state.queueData[state.currentIndex];
      if ((retryData.status === 'failed') && state.failedCount > 0) state.failedCount--;

      retryData.status = 'pending';
      retryData.generatedCount = 0;

      updateStats();
      renderQueueTable();
      renderPromptDisplay();
      appendLog(`Retrying step ${state.currentIndex + 1}/${state.queueData.length}: "${retryData.prompt}"`, 'act');

      btnRetryStep.classList.add('hidden');
      btnStep.disabled = true;
      btnStep.classList.remove('step-ready');
      const label = btnStep.querySelector('.btn-step-label');
      if (label) label.textContent = 'Running...';
      btnStopStep?.classList.remove('hidden');

      if (!state.isRunning) {
        state.isRunning = true;
        btnStart?.classList.add('hidden');
        btnPause?.classList.remove('hidden');
        btnStop?.classList.remove('hidden');
      }

      await runOneStep(getSettings(), elements);

      if (label) label.textContent = '';
      updateStepButton(elements);
    });
  }

  // Pause button
  if (btnPause) {
    btnPause.addEventListener('click', () => {
      if (state.isRunning && !state.isPaused) {
        state.isPaused = true;
        btnPause.classList.add('hidden');
        btnStart?.classList.remove('hidden');
        const startLabel = btnStart?.querySelector('.btn-label');
        if (startLabel) startLabel.textContent = 'Continue';
        btnStop?.classList.remove('hidden');
        appendLog('Process paused. Current prompt will finish, then queue will pause.', 'warn');

        if (state.countdownInterval) {
          clearInterval(state.countdownInterval);
          state.countdownInterval = null;
        }
      }
    });
  }

  // Stop button
  if (btnStop) {
    btnStop.addEventListener('click', () => {
      stopProcess(elements);
      appendLog('Process stopped by user.', 'warn');
      if (state.targetTabId) {
        chrome.tabs.sendMessage(state.targetTabId, { action: "STOP" }).catch(() => {});
      }
    });
  }

  // Reset button
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      stopProcess(elements);
      fullReset();
    });
  }

  // Chrome Message listener for logs, countdowns, real downloads, and completion
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "LOG_FROM_CONTENT") {
      appendLog(`[Script] ${msg.message}`, 'info');
    }

    if (msg.action === "REAL_DOWNLOAD_COMPLETED") {
      const filename = msg.filename ? msg.filename.split(/[\\/]/).pop() : 'media file';
      appendLog(`[Download] File saved to disk: "${filename}" (${Math.round((msg.fileSize || 0) / 1024)} KB) ✓`, 'success');
      state.downloadedCount++;
      updateStats();
    }

    if (msg.action === "UPDATE_QUEUE_STATUS") {
      const idx = msg.index !== undefined ? msg.index : state.currentIndex;
      if (state.queueData[idx]) {
        state.queueData[idx].status = msg.status || 'processing';
        if (msg.statusLabel) state.queueData[idx].statusLabel = msg.statusLabel;
        renderQueueTable();
        renderPromptDisplay();
      }
    }

    if (msg.action === "SET_PHASE_DOWNLOADING") {
      const idx = msg.index !== undefined ? msg.index : state.currentIndex;
      if (state.queueData[idx]) {
        state.queueData[idx].status = 'downloading';
        renderQueueTable();
        renderPromptDisplay();
      }
    }

    if (msg.action === "MONITOR_COUNTDOWN") {
      const remaining = msg.remaining;
      if (remaining !== undefined && state.isRunning && !state.isPaused) {
        state.remainingCountdown = remaining;
        if (valCountdown) valCountdown.innerText = remaining;
        if (remaining > 0) {
          countdownRow?.classList.remove('hidden');
          if (!state.countdownInterval) {
            startCountdown(remaining);
          }
        } else {
          stopCountdown();
        }
      }
    }

    if (msg.action === "DOWNLOAD_COOLDOWN_START") {
      const seconds = Math.max(1, Math.ceil(Number(msg.seconds) || 0));
      if (state.isRunning && !state.isPaused) {
        startCountdown(seconds, 'Download cooldown', `Waiting ${seconds}s before next download...`);
      }
    }

    if (msg.action === "DOWNLOAD_COOLDOWN_END" || msg.action === "BATCH_COMPLETE") {
      stopCountdown();
    }

    if (msg.action === "TANDEM_STATUS_CHANGED") {
      updateTandemBadge(Boolean(msg.connected));
    }

    if (msg.action === "TANDEM_EXECUTE_PROMPT") {
      const promptText = (msg.prompt || '').trim();
      if (promptText && manualInput) {
        // Enforce Image mode for Tandem pipeline if currently in Video
        const typeImage = document.getElementById('typeImage');
        const activeType = document.querySelector('input[name="type"]:checked')?.value;
        if (activeType !== 'image' && typeImage) {
          typeImage.click(); // Triggers existing UI listeners cleanly
          appendLog('[Tandem] Switched mode to Image for vector pipeline.', 'info');
        }

        // Clear old prompt cleanly
        if (state.isRunning) {
          stopProcess(elements);
        }
        if (elements.btnClearInput) {
          elements.btnClearInput.click();
        } else {
          manualInput.value = '';
          state.currentPrompts = [];
        }
        state.currentIndex = 0;

        // Set new prompt and start
        manualInput.value = promptText;
        state.currentPrompts = parsePrompts(promptText);
        updateQueue(getRepeatPerPrompt(), () => updateStepButton(elements));
        updateStats();
        appendLog(`[Tandem] Received remote prompt: "${promptText}"`, 'act');

        if (btnStart) {
          setTimeout(() => {
            btnStart.click();
          }, 200);
        }
      }
    }
  });

  appendLog('Extension loaded. Ready to attach to page.', 'info');

  // Initial tab setup & view check
  initView();
  loadSettingsFromStorage();

  // Save settings automatically on any change
  document.querySelectorAll('input[name="type"], input[name="ratio"], input[name="model"], input[name="batch"], input[name="downloadQuality"], input[name="videoDuration"], input[name="videoResolution"]').forEach(input => {
    input.addEventListener('change', () => {
      saveSettingsToStorage();
    });
  });
  ['promptDelaySeconds', 'downloadDelaySeconds', 'autoRetryRounds', 'retryCooldownSeconds', 'refreshAfterPrompts', 'newProjectAfterPrompts', 'repeatPerPrompt'].forEach(id => {
    const el = document.getElementById(id);
    el?.addEventListener('input', () => {
      saveSettingsToStorage();
    });
    el?.addEventListener('change', () => {
      saveSettingsToStorage();
    });
  });

  window.addEventListener('focus', () => {
    initView();
  });

  chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
    if (tabId && changeInfo.url) {
      checkCurrentTab().then(isOnFlow => {
        if (isOnFlow) {
          landingPage?.classList.add('hidden');
          mainInterface?.classList.remove('hidden');
          if (logArea) logArea.innerHTML = '';
          appendLog('Flow page loaded. Ready.', 'info');
        } else {
          landingPage?.classList.remove('hidden');
          mainInterface?.classList.add('hidden');
        }
      });
    }
  });

  chrome.tabs.onActivated.addListener(() => {
    initView();
  });

  // ─── Auto-Update UI ────────────────────────────────────────────────────────
  function showUpdateBanner(remoteVersion, downloadUrl) {
    if (!updateBanner) return;
    if (updateVersionLabel) updateVersionLabel.textContent = `v${remoteVersion}`;
    updateBanner.classList.remove('hidden');
    updateBanner.dataset.downloadUrl = downloadUrl;
  }

  function hideUpdateBanner() {
    if (updateBanner) updateBanner.classList.add('hidden');
  }

  chrome.storage.local.get(['updateAvailable', 'remoteVersion', 'localVersion', 'downloadUrl'], (data) => {
    if (data.updateAvailable && data.remoteVersion && data.downloadUrl) {
      const localVer = chrome.runtime.getManifest().version;
      if (data.remoteVersion !== localVer) {
        showUpdateBanner(data.remoteVersion, data.downloadUrl);
      }
    }
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === 'UPDATE_AVAILABLE') {
      showUpdateBanner(msg.remoteVersion, msg.downloadUrl);
    }
  });

  if (updateBtnDownload) {
    updateBtnDownload.addEventListener('click', () => {
      if (updateGuideModal) updateGuideModal.classList.remove('hidden');
      const url = updateBanner?.dataset?.downloadUrl;
      if (url) {
        chrome.downloads.download({ url: url, saveAs: true });
      }
    });
  }

  if (updateBtnDismiss) {
    updateBtnDismiss.addEventListener('click', () => {
      hideUpdateBanner();
    });
  }

  if (updateGuideClose) {
    updateGuideClose.addEventListener('click', () => {
      if (updateGuideModal) updateGuideModal.classList.add('hidden');
    });
  }

  if (updateGuideModal) {
    updateGuideModal.addEventListener('click', (e) => {
      if (e.target === updateGuideModal) {
        updateGuideModal.classList.add('hidden');
      }
    });
  }

  chrome.runtime.sendMessage({ type: 'CHECK_FOR_UPDATE' }).catch(() => {});
});
