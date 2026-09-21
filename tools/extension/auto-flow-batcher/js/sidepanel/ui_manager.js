/**
 * Auto Flow Batcher - UI Manager
 * Handles DOM elements, settings retrieval, log output, stats updating, countdown timers, ratio/quality filtering, and auto-update UI.
 */

import { state } from './state.js';
import { updateQueueProgressLabel } from './queue_manager.js';

export function getUIElements() {
  return {
    landingPage: document.getElementById('landingPage'),
    mainInterface: document.getElementById('mainInterface'),
    btnOpenFlow: document.getElementById('btnOpenFlow'),
    btnStart: document.getElementById('btnStart'),
    btnPause: document.getElementById('btnPause'),
    btnStop: document.getElementById('btnStop'),
    btnReset: document.getElementById('btnReset'),
    btnToggleStepMode: document.getElementById('btnToggleStepMode'),
    btnStep: document.getElementById('btnStep'),
    btnStopStep: document.getElementById('btnStopStep'),
    btnRetryStep: document.getElementById('btnRetryStep'),
    stepModeBar: document.getElementById('stepModeBar'),
    stepIndicator: document.getElementById('stepIndicator'),
    btnLoadTXT: document.getElementById('btnLoadTXT'),
    btnLoadCSV: document.getElementById('btnLoadCSV'),
    btnClearLogs: document.getElementById('btnClearLogs'),
    btnCopyLogs: document.getElementById('btnCopyLogs'),
    btnPaste: document.getElementById('btnPaste'),
    btnClearInput: document.getElementById('btnClearInput'),
    promptDisplay: document.getElementById('promptDisplay'),
    fileInput: document.getElementById('fileInput'),
    fileDropArea: document.getElementById('fileDropArea'),
    manualInput: document.getElementById('manualInput'),
    logArea: document.getElementById('logArea'),
    progressBar: document.getElementById('progressBar'),
    valPct: document.getElementById('valPct'),
    queueProgress: document.getElementById('queueProgress'),
    queueRemaining: document.getElementById('queueRemaining'),
    fileLabel: document.getElementById('fileLabel'),
    typeGroup: document.getElementById('typeGroup'),
    queueTableBody: document.getElementById('queueTableBody'),
    globalDelaySecondsInput: document.getElementById('globalDelaySeconds'),
    refreshAfterPromptsInput: document.getElementById('refreshAfterPrompts'),
    newProjectAfterPromptsInput: document.getElementById('newProjectAfterPrompts'),
    repeatPerPromptInput: document.getElementById('repeatPerPrompt'),
    valQueue: document.getElementById('valQueue'),
    valSuccess: document.getElementById('valSuccess'),
    valFailed: document.getElementById('valFailed'),
    valDownloaded: document.getElementById('valDownloaded'),
    countdownRow: document.getElementById('countdownRow'),
    valCountdown: document.getElementById('valCountdown'),
    cooldownLabel: document.getElementById('cooldownLabel'),
    cooldownHint: document.getElementById('cooldownHint'),
    cooldownProgressFill: document.getElementById('cooldownProgressFill'),
    tabBtnPrompts: document.getElementById('tabBtnPrompts'),
    tabBtnMode: document.getElementById('tabBtnMode'),
    tabBtnLogs: document.getElementById('tabBtnLogs'),
    tabPrompts: document.getElementById('tabPrompts'),
    tabMode: document.getElementById('tabMode'),
    tabLogs: document.getElementById('tabLogs'),
    updateBanner: document.getElementById('updateBanner'),
    updateBtnDownload: document.getElementById('updateBtnDownload'),
    updateBtnDismiss: document.getElementById('updateBtnDismiss'),
    updateVersionLabel: document.getElementById('updateVersionLabel'),
    updateGuideModal: document.getElementById('updateGuideModal'),
    updateGuideClose: document.getElementById('updateGuideClose')
  };
}

export function switchTab(activeBtn, activePane, elements) {
  const { tabBtnPrompts, tabBtnMode, tabBtnLogs, tabPrompts, tabMode, tabLogs } = elements;
  [tabBtnPrompts, tabBtnMode, tabBtnLogs].forEach(btn => btn?.classList.remove('active'));
  [tabPrompts, tabMode, tabLogs].forEach(pane => pane?.classList.add('hidden'));
  activeBtn?.classList.add('active');
  activePane?.classList.remove('hidden');
}

export function appendLog(message, type = 'info') {
  const logArea = document.getElementById('logArea');
  if (!logArea) return;
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

export function updateStats() {
  const valQueue = document.getElementById('valQueue');
  const valSuccess = document.getElementById('valSuccess');
  const valFailed = document.getElementById('valFailed');
  const valDownloaded = document.getElementById('valDownloaded');
  const progressBar = document.getElementById('progressBar');
  const valPct = document.getElementById('valPct');

  const total = state.queueData.length;
  if (valQueue) valQueue.innerText = total > 0 ? `${state.currentIndex} / ${total}` : '0 / 0';
  if (valSuccess) valSuccess.innerText = state.successCount;
  if (valFailed) valFailed.innerText = state.failedCount;
  if (valDownloaded) valDownloaded.innerText = state.downloadedCount;

  const p = total > 0 ? ((state.successCount + state.failedCount) / total) * 100 : 0;
  if (progressBar) progressBar.style.width = `${p}%`;
  if (valPct) valPct.innerText = `${Math.round(p)}%`;

  updateQueueProgressLabel();
}

export function startCountdown(seconds, label = 'Cooldown active', hint = 'Waiting safely before continuing...') {
  const countdownRow = document.getElementById('countdownRow');
  const cooldownLabel = document.getElementById('cooldownLabel');
  const cooldownHint = document.getElementById('cooldownHint');
  const cooldownProgressFill = document.getElementById('cooldownProgressFill');
  const valCountdown = document.getElementById('valCountdown');

  state.remainingCountdown = seconds;
  const totalSeconds = Math.max(1, seconds);
  if (state.countdownInterval) {
    clearInterval(state.countdownInterval);
  }
  if (countdownRow) {
    countdownRow.classList.remove('hidden');
    countdownRow.className = 'modal-countdown-overlay';
  }
  if (cooldownLabel) cooldownLabel.innerText = label;
  if (cooldownHint) cooldownHint.innerText = hint;
  if (cooldownProgressFill) cooldownProgressFill.style.width = '100%';
  if (valCountdown) valCountdown.innerText = state.remainingCountdown;

  state.countdownInterval = setInterval(() => {
    if (!state.isRunning || state.isPaused) {
      return; // Don't decrement if paused or stopped
    }
    state.remainingCountdown--;
    if (valCountdown) valCountdown.innerText = Math.max(state.remainingCountdown, 0);
    if (cooldownProgressFill) {
      const progressPct = Math.max(0, (state.remainingCountdown / totalSeconds) * 100);
      cooldownProgressFill.style.width = `${progressPct}%`;
    }
    if (state.remainingCountdown <= 0) {
      clearInterval(state.countdownInterval);
      state.countdownInterval = null;
      if (countdownRow) countdownRow.classList.add('hidden');
      if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';
    }
  }, 1000);
}

export function stopCountdown() {
  const countdownRow = document.getElementById('countdownRow');
  const cooldownProgressFill = document.getElementById('cooldownProgressFill');
  const valCountdown = document.getElementById('valCountdown');

  if (state.countdownInterval) {
    clearInterval(state.countdownInterval);
    state.countdownInterval = null;
  }
  state.remainingCountdown = 0;
  if (valCountdown) valCountdown.innerText = '--';
  if (cooldownProgressFill) cooldownProgressFill.style.width = '0%';
  if (countdownRow) countdownRow.classList.add('hidden');
}

export function updateRatioOptions(type) {
  const allRatioInputs = document.querySelectorAll('input[name="ratio"]');
  allRatioInputs.forEach(input => {
    const pill = input.closest('.radio-pill');
    const validFor = input.getAttribute('data-valid-for');
    if (validFor) {
      const validTypes = validFor.split(',');
      const isValid = validTypes.includes(type);
      pill?.classList.toggle('disabled', !isValid);
      input.disabled = !isValid;
    }
  });

  const checkedRatio = document.querySelector('input[name="ratio"]:checked');
  if (!checkedRatio || checkedRatio.disabled) {
    if (checkedRatio) checkedRatio.checked = false;
    const firstValid = Array.from(allRatioInputs).find(input => !input.disabled);
    if (firstValid) firstValid.checked = true;
  }
}

export function updateModelOptions(type) {
  const modelPills = document.querySelectorAll('#modelGroup .radio-pill');
  modelPills.forEach(pill => {
    const modelType = pill.getAttribute('data-model-type');
    const isMatch = modelType === type;
    pill.classList.toggle('hidden', !isMatch);
    const input = pill.querySelector('input');
    if (input) input.disabled = !isMatch;
  });

  // Ensure an enabled model is checked
  const checkedModel = document.querySelector('#modelGroup input:checked');
  if (!checkedModel || checkedModel.disabled) {
    if (checkedModel) checkedModel.checked = false;
    const firstEnabled = document.querySelector('#modelGroup input:not(:disabled)');
    if (firstEnabled) firstEnabled.checked = true;
  }

  // Toggle Video specific sections (Duration & Resolution only apply to Omni Flash)
  const isVideo = type === 'video';
  const checkedModelVal = document.querySelector('input[name="model"]:checked:not(:disabled)')?.value || '';
  const isOmni = isVideo && (checkedModelVal.includes('Omni') || checkedModelVal.includes('Flash'));

  const durationSec = document.getElementById('videoDurationSection');
  const resSec = document.getElementById('videoResolutionSection');
  durationSec?.classList.toggle('hidden', !isOmni);
  resSec?.classList.toggle('hidden', !isOmni);

  // Enable/disable inputs inside video-specific sections
  const durationInputs = document.querySelectorAll('input[name="videoDuration"]');
  durationInputs.forEach(inp => { inp.disabled = !isOmni; });
  const resInputs = document.querySelectorAll('input[name="videoResolution"]');
  resInputs.forEach(inp => { inp.disabled = !isOmni; });
}

export function updateDownloadQualityOptions(type) {
  const isVideo = type === 'video';
  const qualityPills = document.querySelectorAll('#downloadQualityGroup .radio-pill');

  qualityPills.forEach(pill => {
    const qualityType = pill.getAttribute('data-quality-type');
    const input = pill.querySelector('input');
    const isVisible = (isVideo && qualityType === 'video') || (!isVideo && qualityType === 'image');
    pill.classList.toggle('hidden', !isVisible);
    if (input) input.disabled = !isVisible;
  });

  const selected = document.querySelector('input[name="downloadQuality"]:checked');
  if (!selected || selected.disabled) {
    if (selected) selected.checked = false;
    const fallback = isVideo
      ? document.querySelector('input[name="downloadQuality"][value="720p"]')
      : document.querySelector('input[name="downloadQuality"][value="1K"]');
    if (fallback) fallback.checked = true;
  }
}

export function getPromptDelayMs() {
  const el = document.getElementById('promptDelaySeconds');
  const val = Number.parseFloat(el?.value);
  const safe = Number.isFinite(val) && val >= 0 ? val : 10;
  return Math.round(safe * 1000);
}

export function getDownloadDelayMs() {
  const el = document.getElementById('downloadDelaySeconds');
  const val = Number.parseFloat(el?.value);
  const safe = Number.isFinite(val) && val >= 0 ? val : 5;
  return Math.round(safe * 1000);
}

export function getGlobalDelayMs() {
  return getPromptDelayMs();
}

export function getAutoRetryRounds() {
  const el = document.getElementById('autoRetryRounds');
  const val = Number.parseInt(el?.value, 10);
  return Number.isFinite(val) && val >= 0 ? Math.min(10, val) : 10;
}

export function getRetryCooldownSeconds() {
  const el = document.getElementById('retryCooldownSeconds');
  const val = Number.parseFloat(el?.value);
  return Number.isFinite(val) && val >= 0 ? val : 15;
}

export function getRefreshAfterPrompts() {
  const refreshAfterPromptsInput = document.getElementById('refreshAfterPrompts');
  const refreshAfterPrompts = Number.parseInt(refreshAfterPromptsInput?.value, 10);
  return Number.isFinite(refreshAfterPrompts) && refreshAfterPrompts > 0 ? refreshAfterPrompts : 0;
}

export function getNewProjectAfterPrompts() {
  const newProjectAfterPromptsInput = document.getElementById('newProjectAfterPrompts');
  const newProjectAfterPrompts = Number.parseInt(newProjectAfterPromptsInput?.value, 10);
  return Number.isFinite(newProjectAfterPrompts) && newProjectAfterPrompts > 0 ? newProjectAfterPrompts : 0;
}

export function getRepeatPerPrompt() {
  const repeatPerPromptInput = document.getElementById('repeatPerPrompt');
  const repeat = Number.parseInt(repeatPerPromptInput?.value, 10);
  return Number.isFinite(repeat) && repeat >= 1 ? repeat : 1;
}

export function getSettings() {
  const promptDelayMs = getPromptDelayMs();
  const downloadDelayMs = getDownloadDelayMs();
  const selectedType = document.querySelector('input[name="type"]:checked')?.value || 'image';
  return {
    type: selectedType,
    ratio: document.querySelector('input[name="ratio"]:checked')?.value || '16:9',
    model: document.querySelector('input[name="model"]:checked:not(:disabled)')?.value || (selectedType === 'video' ? 'Omni 1.1 Flash' : 'Nano Banana 2'),
    videoDuration: document.querySelector('input[name="videoDuration"]:checked')?.value || '8s',
    videoResolution: document.querySelector('input[name="videoResolution"]:checked')?.value || '720p',
    batch: document.querySelector('input[name="batch"]:checked')?.value || '1',
    downloadQuality: document.querySelector('input[name="downloadQuality"]:checked')?.value || 'default',
    promptDelayMs,
    promptDelaySeconds: promptDelayMs / 1000,
    downloadDelayMs,
    downloadDelaySeconds: downloadDelayMs / 1000,
    globalDelayMs: promptDelayMs,
    globalDelaySeconds: promptDelayMs / 1000,
    autoRetryRounds: getAutoRetryRounds(),
    retryCooldownSeconds: getRetryCooldownSeconds(),
    refreshAfterPrompts: getRefreshAfterPrompts(),
    newProjectAfterPrompts: getNewProjectAfterPrompts(),
    repeatPerPrompt: getRepeatPerPrompt()
  };
}

export function saveSettingsToStorage() {
  try {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      const settings = getSettings();
      chrome.storage.local.set({ afb_saved_settings: settings });
    }
  } catch (_) {}
}

export function loadSettingsFromStorage() {
  try {
    if (typeof chrome === 'undefined' || !chrome.storage || !chrome.storage.local) return;
    chrome.storage.local.get(['afb_saved_settings'], (data) => {
      if (!data || !data.afb_saved_settings) return;
      const s = data.afb_saved_settings;

      // 1. Restore Type first
      if (s.type) {
        const typeEl = document.querySelector(`input[name="type"][value="${s.type}"]`);
        if (typeEl) {
          typeEl.checked = true;
        }
      }

      const activeType = document.querySelector('input[name="type"]:checked')?.value || 'image';
      updateRatioOptions(activeType);
      updateModelOptions(activeType);
      updateDownloadQualityOptions(activeType);

      // 2. Restore Model first (before video duration/resolution sections are updated)
      if (s.model) {
        const modelEl = document.querySelector(`input[name="model"][value="${s.model}"]`);
        if (modelEl && !modelEl.disabled) {
          modelEl.checked = true;
        }
      }
      updateModelOptions(activeType);

      // 3. Restore Ratio
      if (s.ratio) {
        const ratioEl = document.querySelector(`input[name="ratio"][value="${s.ratio}"]`);
        if (ratioEl && !ratioEl.disabled) {
          ratioEl.checked = true;
        }
      }

      // 4. Restore Batch
      if (s.batch) {
        const batchEl = document.querySelector(`input[name="batch"][value="${s.batch}"]`);
        if (batchEl) {
          batchEl.checked = true;
        }
      }

      // 5. Restore Quality
      if (s.downloadQuality) {
        const dqEl = document.querySelector(`input[name="downloadQuality"][value="${s.downloadQuality}"]`);
        if (dqEl && !dqEl.disabled) {
          dqEl.checked = true;
        }
      }

      // 6. Restore Video Duration
      if (s.videoDuration) {
        const vdEl = document.querySelector(`input[name="videoDuration"][value="${s.videoDuration}"]`);
        if (vdEl && !vdEl.disabled) {
          vdEl.checked = true;
        }
      }

      // 7. Restore Video Resolution
      if (s.videoResolution) {
        const vrEl = document.querySelector(`input[name="videoResolution"][value="${s.videoResolution}"]`);
        if (vrEl && !vrEl.disabled) {
          vrEl.checked = true;
        }
      }

      // 8. Restore Numeric Controls
      if (s.promptDelaySeconds !== undefined) {
        const el = document.getElementById('promptDelaySeconds');
        if (el) el.value = s.promptDelaySeconds;
      } else if (s.globalDelaySeconds !== undefined) {
        const el = document.getElementById('promptDelaySeconds');
        if (el) el.value = s.globalDelaySeconds;
      }
      if (s.downloadDelaySeconds !== undefined) {
        const el = document.getElementById('downloadDelaySeconds');
        if (el) el.value = s.downloadDelaySeconds;
      }
      if (s.autoRetryRounds !== undefined) {
        const el = document.getElementById('autoRetryRounds');
        if (el) el.value = s.autoRetryRounds;
      }
      if (s.retryCooldownSeconds !== undefined) {
        const el = document.getElementById('retryCooldownSeconds');
        if (el) el.value = s.retryCooldownSeconds;
      }
      if (s.refreshAfterPrompts !== undefined) {
        const el = document.getElementById('refreshAfterPrompts');
        if (el) el.value = s.refreshAfterPrompts;
      }
      if (s.newProjectAfterPrompts !== undefined) {
        const el = document.getElementById('newProjectAfterPrompts');
        if (el) el.value = s.newProjectAfterPrompts;
      }
      if (s.repeatPerPrompt !== undefined) {
        const el = document.getElementById('repeatPerPrompt');
        if (el) el.value = s.repeatPerPrompt;
      }
    });
  } catch (_) {}
}

export function setStepMode(enabled, elements) {
  const { stepModeBar, btnToggleStepMode } = elements;
  state.isStepMode = enabled;
  if (enabled) {
    stepModeBar?.classList.remove('hidden');
    if (btnToggleStepMode) {
      btnToggleStepMode.style.color = '#f27d26';
      btnToggleStepMode.style.background = 'rgba(242,125,38,0.15)';
      btnToggleStepMode.title = 'Step Mode ON — click to disable';
    }
    appendLog('Step Mode enabled. Click "Generation Step" to run one prompt at a time.', 'info');
  } else {
    stepModeBar?.classList.add('hidden');
    if (btnToggleStepMode) {
      btnToggleStepMode.style.color = '';
      btnToggleStepMode.style.background = '';
      btnToggleStepMode.title = 'Toggle Step Mode (manual next)';
    }
    if (!state.isRunning) appendLog('Step Mode disabled.', 'info');
  }
  updateStepButton(elements);
}

export function updateStepButton(elements) {
  if (!state.isStepMode) return;
  const { btnStep, btnStopStep, btnRetryStep, stepIndicator } = elements;
  const total = state.queueData.length;
  const remaining = total - state.currentIndex;
  if (stepIndicator) {
    stepIndicator.textContent = total > 0 ? `Step ${state.currentIndex}/${total}` : 'Step 0/0';
  }

  // Hide stop/retry by default
  btnStopStep?.classList.add('hidden');
  btnRetryStep?.classList.add('hidden');

  if (total === 0) {
    if (btnStep) {
      btnStep.disabled = true;
      btnStep.classList.remove('step-ready');
      const label = btnStep.querySelector('.btn-step-label');
      if (label) label.textContent = 'Generation Step';
    }
  } else if (state.isRunning && remaining > 0) {
    const currentLabel = btnStep?.querySelector('.btn-step-label')?.textContent;
    if (currentLabel === 'Running...') {
      // Currently executing — show Stop Step button
      if (btnStep) {
        btnStep.disabled = true;
        btnStep.classList.remove('step-ready');
      }
      btnStopStep?.classList.remove('hidden');
    } else {
      // Ready for next step
      if (btnStep) {
        btnStep.disabled = false;
        btnStep.classList.add('step-ready');
        const label = btnStep.querySelector('.btn-step-label');
        if (label) label.textContent = `Step ${state.currentIndex + 1}/${total}`;
      }
    }
  } else if (!state.isRunning && remaining > 0) {
    // Not started yet, but prompts loaded
    if (btnStep) {
      btnStep.disabled = false;
      btnStep.classList.add('step-ready');
      const label = btnStep.querySelector('.btn-step-label');
      if (label) label.textContent = `Step 1/${total}`;
    }
  } else if (remaining <= 0 && total > 0) {
    // All done — allow restart from beginning
    if (btnStep) {
      btnStep.disabled = false;
      btnStep.classList.add('step-ready');
      const label = btnStep.querySelector('.btn-step-label');
      if (label) label.textContent = 'Restart (Step 1)';
    }
  } else {
    // Fallback
    if (btnStep) {
      btnStep.disabled = true;
      btnStep.classList.remove('step-ready');
      const label = btnStep.querySelector('.btn-step-label');
      if (label) label.textContent = 'Generation Step';
    }
  }

  // Show Retry if current or last step was stopped or failed
  const currentStatus = state.queueData[state.currentIndex]?.status;
  const lastStatus = state.currentIndex > 0 ? state.queueData[state.currentIndex - 1]?.status : null;
  if (currentStatus === 'failed' || currentStatus === 'stopped' ||
      lastStatus === 'failed' || lastStatus === 'stopped') {
    btnRetryStep?.classList.remove('hidden');
  }
}
