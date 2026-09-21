/**
 * Auto Flow Batcher - Queue Manager
 * Rebuilds queue data with repeat expansion, updates progress indicators, renders table rows and status badges.
 */

import { state } from './state.js';
import { escapeHtml } from './file_parser.js';

export function updateQueue(repeatCount = 1, onStepUpdate = null) {
  state.prompts = state.currentPrompts;
  const repeat = Number.isFinite(repeatCount) && repeatCount >= 1 ? repeatCount : 1;

  // Rebuild queueData: expand each prompt by repeat count
  state.queueData = [];
  state.prompts.forEach((prompt, promptIdx) => {
    for (let r = 0; r < repeat; r++) {
      state.queueData.push({
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
  if (state.isStepMode && typeof onStepUpdate === 'function') {
    onStepUpdate();
  }
}

export function updateQueueProgressLabel() {
  const queueProgress = document.getElementById('queueProgress');
  const queueRemaining = document.getElementById('queueRemaining');
  if (!queueProgress || !queueRemaining) return;

  const total = state.queueData.length;
  const completed = state.currentIndex;
  const remaining = Math.max(0, total - completed);
  if (total > 0) {
    queueProgress.innerText = `${completed}/${total}`;
    queueRemaining.innerText = `(${remaining} remaining)`;
  } else {
    queueProgress.innerText = '0';
    queueRemaining.innerText = '';
  }
}

export function renderQueueTable() {
  const queueTableBody = document.getElementById('queueTableBody');
  if (!queueTableBody) return;

  if (state.queueData.length === 0) {
    queueTableBody.innerHTML = '<tr><td colspan="4" class="empty-queue">No prompts in queue</td></tr>';
    return;
  }

  queueTableBody.innerHTML = '';
  state.queueData.forEach((item, idx) => {
    const row = document.createElement('tr');
    row.className = item.status;
    row.id = `queue-row-${idx}`;

    let statusText = 'Pending';
    if (item.status === 'processing') statusText = 'Processing...';
    else if (item.status === 'waiting') statusText = item.statusLabel || 'Waiting...';
    else if (item.status === 'typing') statusText = 'Typing...';
    else if (item.status === 'configuring') statusText = 'Configuring...';
    else if (item.status === 'generating') statusText = 'Generating...';
    else if (item.status === 'downloading') statusText = 'Downloading...';
    else if (item.status === 'completed') statusText = 'Completed';
    else if (item.status === 'failed') statusText = 'Failed';
    else if (item.status === 'partial') statusText = 'Partial';
    else if (item.status === 'stopped') statusText = 'Stopped';

    // Show index as "#P.R" when repeat > 1, otherwise just "#N"
    const indexLabel = item.repeatTotal > 1
      ? `#${item.promptIndex + 1}.${item.repeatIndex + 1}`
      : `#${idx + 1}`;

    row.innerHTML = `
      <td><span style="color: var(--text-muted); font-size: 10px;">${indexLabel}</span></td>
      <td><div class="queue-prompt-text" title="${escapeHtml(item.prompt)}">${escapeHtml(item.prompt)}</div></td>
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

export function renderPromptDisplay() {
  const promptDisplay = document.getElementById('promptDisplay');
  if (!promptDisplay) return;

  if (state.queueData.length === 0) {
    promptDisplay.innerHTML = '<div style="color: var(--text-muted); padding: 8px;">No prompts</div>';
    return;
  }

  let html = '';
  state.queueData.forEach((item) => {
    let statusClass = 'prompt-pending';
    if (item.status === 'processing') {
      statusClass = 'prompt-active';
    } else if (item.status === 'completed') {
      statusClass = 'prompt-completed';
    } else if (item.status === 'failed') {
      statusClass = 'prompt-failed';
    } else if (item.status === 'partial') {
      statusClass = 'prompt-completed'; // treat partial as completed
    } else if (item.status === 'stopped') {
      statusClass = 'prompt-failed';
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
