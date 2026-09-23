/**
 * Auto Flow Batcher - Automation Runner
 * Executes single step mode or continuous queue automation, handles cooldown timers,
 * error retries, pause/stop states, auto-refresh and new project triggers.
 */

import { state, resetProcessState, fullResetState } from './state.js';
import { renderQueueTable, renderPromptDisplay, updateQueue } from './queue_manager.js';
import { appendLog, updateStats, startCountdown, stopCountdown, updateStepButton, getSettings } from './ui_manager.js';
import { 
  ensureContentScript, 
  prepareFlowProjectIfNeeded, 
  refreshAfterCompletedPromptIfNeeded, 
  newProjectAfterCompletedPromptIfNeeded,
  reloadTabOnFailureSafely
} from './navigation_manager.js';

export function waitForCooldown(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

export async function runPromptCooldownIfNeeded(delayMs) {
  if (delayMs <= 0 || state.currentIndex === 0) return;

  const delaySeconds = Math.ceil(delayMs / 1000);

  appendLog(`Cooldown ${delaySeconds}s before next prompt...`, 'info');
  startCountdown(delaySeconds, 'Prompt cooldown', `Waiting ${delaySeconds}s before sending the next prompt...`);

  // Wait in small increments so we can break out early if paused/stopped
  const startTime = Date.now();
  while (Date.now() - startTime < delayMs) {
    if (!state.isRunning || state.isPaused) break;
    await new Promise(r => setTimeout(r, 200));
  }

  stopCountdown();
}

export function stopProcess(elements) {
  state.isRunning = false;
  state.isPaused = false;
  state.isStepStopped = false;
  stopCountdown();
  state.targetTabId = null;

  const { btnStart, btnPause, btnStop, manualInput, promptDisplay, btnStep, btnStopStep, btnRetryStep, stepIndicator } = elements;

  if (btnStart) {
    btnStart.classList.remove('hidden');
    const label = btnStart.querySelector('.btn-label');
    if (label) label.textContent = 'Start';
  }
  btnPause?.classList.add('hidden');
  btnStop?.classList.add('hidden');

  if (manualInput) {
    manualInput.classList.remove('processing');
    manualInput.readOnly = false;
    manualInput.style.display = '';
  }
  promptDisplay?.classList.remove('visible');

  // Reset step button
  if (state.isStepMode) {
    if (btnStep) {
      btnStep.disabled = true;
      btnStep.classList.remove('step-ready');
      const label = btnStep.querySelector('.btn-step-label');
      if (label) label.textContent = 'Generation Step';
    }
    btnStopStep?.classList.add('hidden');
    btnRetryStep?.classList.add('hidden');
    const total = state.queueData.length;
    if (stepIndicator) stepIndicator.textContent = `Step ${state.currentIndex}/${total}`;
  }

  // Mark any still-processing rows as failed (real stop, not pause)
  state.queueData.forEach(item => {
    if (item.status === 'processing') {
      item.status = 'failed';
    }
  });
  renderQueueTable();
  renderPromptDisplay();
}

export async function runOneStep(settings, elements) {
  if (state.currentIndex >= state.queueData.length || !state.isRunning) return;

  state.isStepStopped = false; // Reset step-level stop flag
  const totalQueue = state.queueData.length;
  const promptData = state.queueData[state.currentIndex];
  promptData.status = 'processing';
  renderQueueTable();
  renderPromptDisplay();
  updateStats();

  // No cooldown on first step, apply on subsequent steps
  await runPromptCooldownIfNeeded(settings.globalDelayMs || 0);
  if (!state.isRunning || state.isStepStopped) {
    promptData.status = state.isStepStopped ? 'stopped' : 'pending';
    renderQueueTable();
    renderPromptDisplay();
    if (state.isStepStopped) {
      appendLog(`[Step ${state.currentIndex + 1}] Stopped by user (step-level).`, 'warn');
    }
    return;
  }

  const repeatInfo = promptData.repeatTotal > 1 ? ` (repeat ${promptData.repeatIndex + 1}/${promptData.repeatTotal})` : '';
  appendLog(`[Step ${state.currentIndex + 1}/${totalQueue}] Processing: "${promptData.prompt}"${repeatInfo}`, 'act');

  try {
    if (!state.targetTabId) {
      appendLog('Error: No target tab ID. Please re-focus the Flow page.', 'error');
      promptData.status = 'failed';
      state.failedCount++;
      state.currentIndex++;
      updateStats();
      renderQueueTable();
      renderPromptDisplay();
      return;
    }

    const response = await new Promise((resolve) => {
      chrome.tabs.sendMessage(state.targetTabId, {
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

    // Check if step was stopped during processing
    if (!state.isRunning || state.isStepStopped) {
      promptData.status = 'stopped';
      renderQueueTable();
      renderPromptDisplay();
      appendLog(`[Step ${state.currentIndex + 1}] Stopped during processing.`, 'warn');
      return;
    }

    if (response.status === 'success' || response.status === 'partial') {
      state.successCount++;
      const downloaded = response.downloaded || 0;
      const generated = response.generated !== undefined ? response.generated : (response.found || downloaded);
      state.downloadedCount += downloaded;
      promptData.generatedCount += generated;
      promptData.status = response.status === 'success' ? 'completed' : 'partial';
      const msg = response.status === 'partial'
        ? `[Step ${state.currentIndex + 1}] ${response.message}`
        : `[Step ${state.currentIndex + 1}] OK: ${response.ids ? response.ids.length : 1} variations saved.`;
      appendLog(msg, 'success');
    } else if (response.status === 'stopped') {
      appendLog(`[Step ${state.currentIndex + 1}] Stopped by content script.`, 'warn');
      promptData.status = 'stopped';
      state.failedCount++;
    } else {
      state.failedCount++;
      promptData.status = 'failed';
      appendLog(`[Step ${state.currentIndex + 1}] Failed: ${response.message}`, 'error');
    }
  } catch (err) {
    state.failedCount++;
    promptData.status = 'failed';
    appendLog(`[Step ${state.currentIndex + 1}] Execution Error: ${err.message}`, 'error');
  }

  state.currentIndex++;
  updateStats();
  renderQueueTable();
  renderPromptDisplay();

  // Refresh / New Project if needed
  if (state.isRunning && !state.isStepStopped) {
    try {
      await refreshAfterCompletedPromptIfNeeded(settings, appendLog);
      await newProjectAfterCompletedPromptIfNeeded(settings, appendLog);
    } catch (err) {
      appendLog(`Refresh failed: ${err.message}. Continuing.`, 'warn');
    }
  }

  // Check if all done
  if (state.currentIndex >= totalQueue) {
    appendLog('All prompts completed!', 'success');
    stopProcess(elements);
  }
}

export async function processQueue(settings, elements) {
  const MAX_CONSECUTIVE_FAILURES = 3; // Auto-stop after 3 consecutive failures
  let consecutiveFailures = 0;
  const totalQueue = state.queueData.length;
  const maxRetryRounds = settings.autoRetryRounds !== undefined ? settings.autoRetryRounds : 10;
  let currentRound = 1;

  while (state.isRunning && !state.isPaused) {
    while (state.isRunning && !state.isPaused && state.currentIndex < totalQueue) {
      const promptData = state.queueData[state.currentIndex];

      // If in a retry round, skip already completed items
      if (promptData.status === 'completed') {
        state.currentIndex++;
        continue;
      }

      promptData.status = 'waiting';
      promptData.statusLabel = `Waiting ${Math.ceil((settings.promptDelayMs || settings.globalDelayMs || 0)/1000)}s`;
      renderQueueTable();
      renderPromptDisplay(); // show active highlight immediately

      updateStats();
      if (elements.manualInput) elements.manualInput.classList.add('processing');

      await runPromptCooldownIfNeeded(settings.promptDelayMs || settings.globalDelayMs || 0);
      if (!state.isRunning || state.isPaused) {
        promptData.status = 'pending';
        renderQueueTable();
        renderPromptDisplay();
        break;
      }

      promptData.status = 'processing';
      renderQueueTable();
      renderPromptDisplay();

      const repeatInfo = promptData.repeatTotal > 1 ? ` (repeat ${promptData.repeatIndex + 1}/${promptData.repeatTotal})` : '';
      const roundPrefix = currentRound > 1 ? `[Round ${currentRound}/${maxRetryRounds}] ` : '';
      appendLog(`${roundPrefix}[${state.currentIndex + 1}/${totalQueue}] Processing: "${promptData.prompt}"${repeatInfo}`, 'act');

      try {
        if (!state.targetTabId) {
          appendLog('Error: No target tab ID. Please re-focus the Flow page.', 'error');
          break;
        }

        // Ensure content script and runtime signatures are active before processing prompt
        try {
          await ensureContentScript(state.targetTabId, null);
        } catch (_) {}

        const response = await new Promise((resolve) => {
          chrome.tabs.sendMessage(state.targetTabId, {
            action: "PROCESS_PROMPT",
            payload: { prompt: promptData.prompt, settings: { ...settings, currentIndex: state.currentIndex } }
          }, (res) => {
            if (chrome.runtime.lastError) {
              resolve({ status: 'failed', message: `Connection error: ${chrome.runtime.lastError.message}` });
            } else {
              resolve(res || { status: 'failed', message: 'Empty response from content script.' });
            }
          });
        });

        if (!state.isRunning) break;

        if (response.status === 'success' || response.status === 'partial') {
          state.successCount++;
          consecutiveFailures = 0; // Reset on success
          const downloaded = response.downloaded || 0;
          const generated = response.generated !== undefined ? response.generated : (response.found || downloaded);
          promptData.generatedCount += generated;
          promptData.status = response.status === 'success' ? 'completed' : 'partial';
          const msg = response.status === 'partial'
            ? `[${state.currentIndex + 1}] ${response.message}`
            : `[${state.currentIndex + 1}] OK: ${response.ids ? response.ids.length : 1} variations saved.`;
          appendLog(msg, 'success');
        } else if (response.status === 'stopped') {
          appendLog(`[${state.currentIndex + 1}] Stopped by user.`, 'warn');
          break;
        } else {
          state.failedCount++;
          consecutiveFailures++;
          promptData.status = 'failed';
          appendLog(`[${state.currentIndex + 1}] Failed: ${response.message}`, 'error');

          // Auto-stop after too many consecutive failures
          if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
            appendLog(`AUTO-STOP: ${MAX_CONSECUTIVE_FAILURES} consecutive failures. Google Flow server might be throttling or down. Stopping batch.`, 'error');
            break;
          }

          // Auto-reload Flow page on failure as safety recovery
          try {
            await reloadTabOnFailureSafely(appendLog);
          } catch (reloadErr) {
            appendLog(`Auto-reload after failure notice: ${reloadErr.message}`, 'warn');
          }

          // Safety delay / evaluation pause after failure before proceeding
          const failCooldownMs = Math.max(5000, (settings.promptDelayMs || settings.globalDelayMs || 5000));
          const failCooldownSec = Math.ceil(failCooldownMs / 1000);
          appendLog(`[${state.currentIndex + 1}] Waiting ${failCooldownSec}s cooldown after failure before proceeding...`, 'warn');
          startCountdown(failCooldownSec, 'Failure recovery', `Cooling down ${failCooldownSec}s before next attempt...`);
          const failStart = Date.now();
          while (Date.now() - failStart < failCooldownMs) {
            if (!state.isRunning || state.isPaused) break;
            await new Promise(r => setTimeout(r, 200));
          }
          stopCountdown();
        }
      } catch (err) {
        state.failedCount++;
        consecutiveFailures++;
        promptData.status = 'failed';
        appendLog(`[${state.currentIndex + 1}] Execution Error: ${err.message}`, 'error');

        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
          appendLog(`AUTO-STOP: ${MAX_CONSECUTIVE_FAILURES} consecutive failures. Please check the Flow page.`, 'error');
          break;
        }
      }

      state.currentIndex++;
      updateStats();
      renderQueueTable();
      renderPromptDisplay();

      if (state.isPaused) {
        break;
      }

      if (state.isRunning) {
        try {
          await refreshAfterCompletedPromptIfNeeded(settings, appendLog);
          await newProjectAfterCompletedPromptIfNeeded(settings, appendLog);
        } catch (err) {
          appendLog(`Refresh failed: ${err.message}. Continuing without refresh.`, 'warn');
        }
      }
    }

    if (state.isPaused || !state.isRunning) break;

    // Check for remaining failed prompts to auto-retry (Vector-Assist Multi-Round Architecture)
    const failedItems = state.queueData.filter(item => item.status === 'failed');
    if (failedItems.length > 0 && currentRound < maxRetryRounds) {
      currentRound++;
      consecutiveFailures = 0; // Reset consecutive counter for new round

      const retryCooldownSec = Math.max(5, settings.retryCooldownSeconds || 15);
      appendLog(`[Auto-Retry] Round ${currentRound}/${maxRetryRounds}: Found ${failedItems.length} failed prompt(s). Retrying in ${retryCooldownSec}s...`, 'warn');
      startCountdown(retryCooldownSec, `Auto-retry Round ${currentRound}`, `Retrying ${failedItems.length} failed prompt(s) in ${retryCooldownSec}s...`);

      const cdStart = Date.now();
      while (Date.now() - cdStart < retryCooldownSec * 1000) {
        if (!state.isRunning || state.isPaused) break;
        await new Promise(r => setTimeout(r, 200));
      }
      stopCountdown();

      if (!state.isRunning || state.isPaused) break;

      // Reset failed items status to pending and find first failed index to restart
      failedItems.forEach(item => {
        item.status = 'pending';
      });

      const firstFailedIndex = state.queueData.findIndex(item => item.status === 'pending');
      state.currentIndex = firstFailedIndex >= 0 ? firstFailedIndex : 0;
      renderQueueTable();
      renderPromptDisplay();
      updateStats();
      appendLog(`[Auto-Retry] Round ${currentRound}/${maxRetryRounds} started!`, 'act');
    } else {
      // No more failed items or max retry rounds reached
      break;
    }
  }

  if (state.isRunning && !state.isPaused) {
    const finalFailed = state.queueData.filter(item => item.status === 'failed').length;
    if (finalFailed === 0) {
      appendLog('All prompts completed successfully!', 'success');
      // Broadcast prompt batch finished with all downloaded files
      try {
        chrome.runtime.sendMessage({
          action: 'AFB_PROMPT_ALL_DOWNLOADS_FINISHED',
          downloadedCount: state.downloadedCount,
          successCount: state.successCount
        });
      } catch (_) {}
    } else {
      appendLog(`Batch ended: ${state.successCount} completed, ${finalFailed} failed after ${currentRound} round(s).`, 'warn');
    }
  }

  // If paused, don't call stopProcess — just exit the loop gracefully.
  if (state.isPaused) {
    state.isRunning = false;
    return;
  }

  stopProcess(elements);
}
