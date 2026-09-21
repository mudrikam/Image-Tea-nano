/**
 * Auto Flow Batcher - Navigation & Page Detection Helpers
 * Detects Flow landing vs project page, waits for project load / tab reload, ensures content script injection.
 */

import { state } from './state.js';
import { authState, fetchRemoteCoreEngine } from './auth_manager.js';

export function isFlowLandingUrl(url = '') {
  if (!url) return false;
  return /^https?:\/\/flow\.google\.com\/?(?:[?#].*)?$/i.test(url);
}

export function isFlowProjectUrl(url) {
  if (!url) return false;
  return /flow\.google\.com\/project\//i.test(url);
}

export async function checkCurrentTab() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url) return false;
    // Match Flow pages with optional locale segment or flow.google.com
    const flowPattern = /(labs\.google(\.com)?\/fx\/(?:[^/]+\/)?tools\/flow|flow\.google\.com)/i;
    return flowPattern.test(tab.url);
  } catch (e) {
    return false;
  }
}

export function waitForTabProjectLoad(tabId, timeoutMs = 45000) {
  return new Promise((resolve, reject) => {
    let timer = null;
    const listener = (updatedTabId, changeInfo, tab) => {
      if (updatedTabId !== tabId) return;
      const url = changeInfo.url || tab.url || '';
      if (isFlowProjectUrl(url) && changeInfo.status === 'complete') {
        if (timer) clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(tab);
      }
    };

    timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error('Timed out waiting for Flow project page to load'));
    }, timeoutMs);

    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId, (tab) => {
      if (chrome.runtime.lastError) return;
      const url = tab?.url || '';
      if (isFlowProjectUrl(url) && tab.status === 'complete') {
        if (timer) clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(tab);
      }
    });
  });
}

export function waitForTabReload(tabId, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    let timer = null;
    const listener = (updatedTabId, changeInfo, tab) => {
      if (updatedTabId !== tabId) return;
      if (changeInfo.status === 'complete') {
        if (timer) clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(tab);
      }
    };

    timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error('Timed out waiting for Flow page refresh'));
    }, timeoutMs);

    chrome.tabs.onUpdated.addListener(listener);
  });
}

export async function ensureContentScript(tabId, logger = console.log) {
  let isAlive = false;
  try {
    await new Promise((resolve, reject) => {
      chrome.tabs.sendMessage(tabId, { action: "PING" }, (res) => {
        if (chrome.runtime.lastError || !res) reject(chrome.runtime.lastError || new Error('No ping response'));
        else resolve(res);
      });
    });
    isAlive = true;
  } catch (e) {
    if (logger) logger('Content script missing. Auto-injecting into page...', 'warn');
    await chrome.scripting.executeScript({
      target: { tabId },
      files: [
        'js/content/dom_helpers.js',
        'js/content/agent_manager.js',
        'js/content/prosemirror_typewriter.js',
        'js/content/variant_popover.js',
        'js/content/generator_action.js',
        'js/content/generation_monitor.js',
        'js/content/tile_downloader.js',
        'content.js'
      ]
    });
    await new Promise(r => setTimeout(r, 500));
  }

  // Re-hydrate Dynamic Runtime Signatures into tab memory after tab reload/injection
  try {
    if (authState.isPaired && authState.cdeToken) {
      const runtimeConfig = await fetchRemoteCoreEngine(authState.cdeToken);
      await new Promise((resolve) => {
        chrome.tabs.sendMessage(tabId, { action: 'INITIALIZE_RUNTIME_CONFIG', config: runtimeConfig }, () => resolve());
      });
    }
  } catch (_) {}
}

export async function reloadTabOnFailureSafely(logger = console.log) {
  if (!state.targetTabId) return;
  if (logger) logger('Reloading Flow page to clear canvas failure glitch & refresh SPA...', 'warn');

  await new Promise((resolve) => {
    chrome.tabs.reload(state.targetTabId, () => {
      if (chrome.runtime.lastError) {
        if (logger) logger(`Reload notice: ${chrome.runtime.lastError.message}`, 'warn');
      }
      resolve();
    });
  });

  await waitForTabReload(state.targetTabId);
  await ensureContentScript(state.targetTabId, logger);
  await new Promise(r => setTimeout(r, 1500));
  if (logger) logger('Flow page reloaded & normalized successfully ✓', 'success');
}

export async function refreshTargetTabSafely(completedPrompts, logger = console.log) {
  if (!state.targetTabId) {
    if (logger) logger('Refresh skipped: target tab is no longer available.', 'warn');
    return;
  }

  if (logger) logger(`Refreshing Flow page after ${completedPrompts} completed prompts...`, 'act');
  await new Promise((resolve, reject) => {
    chrome.tabs.reload(state.targetTabId, () => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve();
      }
    });
  });
  await waitForTabReload(state.targetTabId);
  await ensureContentScript(state.targetTabId, logger);
  state.lastRefreshSuccessCount = completedPrompts;
  if (logger) logger('Flow page refreshed. Continuing from saved queue progress.', 'success');
}

export async function createNewProjectSafely(completedPrompts, logger = console.log) {
  if (!state.targetTabId) return;
  if (logger) logger(`Creating a NEW Flow project after ${completedPrompts} completed prompts...`, 'act');

  // Navigate to Home page first
  await new Promise((resolve) => {
    chrome.tabs.update(state.targetTabId, { url: 'https://flow.google.com/' }, () => resolve());
  });
  await waitForTabReload(state.targetTabId);
  await ensureContentScript(state.targetTabId, logger);

  // Wait and trigger CREATE_PROJECT
  await new Promise(r => setTimeout(r, 2000));
  await new Promise((resolve) => {
    chrome.tabs.sendMessage(state.targetTabId, { action: "CREATE_PROJECT" }, () => resolve());
  });
  await waitForTabProjectLoad(state.targetTabId);
  await ensureContentScript(state.targetTabId, logger);
  state.lastNewProjectSuccessCount = completedPrompts;
  if (logger) logger('New Flow project created successfully. Continuing automation in new canvas.', 'success');
}

export async function newProjectAfterCompletedPromptIfNeeded(settings, logger = console.log) {
  const newProjectEvery = settings.newProjectAfterPrompts || 0;
  if (newProjectEvery <= 0) return;
  if (state.successCount <= 0 || state.currentIndex >= state.queueData.length) return;
  if (state.successCount === state.lastNewProjectSuccessCount) return;
  if (state.successCount % newProjectEvery !== 0) return;

  await createNewProjectSafely(state.successCount, logger);
}

export async function refreshAfterCompletedPromptIfNeeded(settings, logger = console.log) {
  const refreshEvery = settings.refreshAfterPrompts || 0;
  if (refreshEvery <= 0) return;
  if (state.successCount <= 0 || state.currentIndex >= state.queueData.length) return;
  if (state.successCount === state.lastRefreshSuccessCount) return;
  if (state.successCount % refreshEvery !== 0) return;

  await refreshTargetTabSafely(state.successCount, logger);
}

export async function prepareFlowProjectIfNeeded(tab, logger = console.log) {
  if (!isFlowLandingUrl(tab.url)) return tab;

  if (logger) logger('Flow landing page detected. Waiting 3 seconds before creating project...', 'act');
  await ensureContentScript(tab.id, logger);

  // Add deliberate delay here to ensure page handles script execution cleanly before starting the generation loop
  await new Promise(r => setTimeout(r, 3000));

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
  await ensureContentScript(tab.id, logger);
  return projectTab;
}
