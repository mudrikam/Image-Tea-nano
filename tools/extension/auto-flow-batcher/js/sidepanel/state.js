/**
 * Auto Flow Batcher - Centralized State Management
 * Holds reactive state across queue processing, step mode, UI stats, and timers.
 */

export const state = {
  currentPrompts: [], // Raw prompt strings from textarea/file
  prompts: [],        // Active prompts being processed
  queueData: [],      // Array of queue items: { prompt, status, generatedCount, promptIndex, repeatIndex, repeatTotal }
  currentIndex: 0,
  successCount: 0,
  failedCount: 0,
  downloadedCount: 0,
  isRunning: false,
  isPaused: false,
  isStepMode: false,  // Step mode: manual next
  stepReady: false,   // Step ready to run next
  isStepStopped: false, // Step-level stop: abort current step only, keep queue position
  targetTabId: null,
  countdownInterval: null,
  remainingCountdown: 0,
  lastRefreshSuccessCount: 0,
  lastNewProjectSuccessCount: 0
};

/**
 * Resets runtime process counters and timers (keeps prompt queue data intact)
 */
export function resetProcessState() {
  state.currentIndex = 0;
  state.successCount = 0;
  state.failedCount = 0;
  state.downloadedCount = 0;
  state.isRunning = false;
  state.isPaused = false;
  if (state.countdownInterval) {
    clearInterval(state.countdownInterval);
    state.countdownInterval = null;
  }
  state.remainingCountdown = 0;
  state.lastRefreshSuccessCount = 0;
}

/**
 * Resets entire state including prompt lists and targets
 */
export function fullResetState() {
  resetProcessState();
  state.currentPrompts = [];
  state.prompts = [];
  state.queueData = [];
  state.currentIndex = 0;
  state.isStepStopped = false;
  state.targetTabId = null;
  state.lastNewProjectSuccessCount = 0;
}
