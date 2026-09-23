"""
Tandem Pipeline Coordinator Helper
==================================
Non-monolithic helper for Prompt Generator Tandem Mode:
- Manages Tandem Server lifecycle (automatic port 48200)
- Manages multi-prompt queue execution (one prompt per cycle, waiting for full Flow + Vector completion)
- Updates database prompt status to 'copied' upon successful completion
- Clipboard prompt parser & importer helper
"""

import os
import re
from PySide6.QtCore import QObject, Signal, QTimer
from helpers.tools.tandem_server_helper import TandemServerThread


def parse_clipboard_prompts(text: str) -> list[str]:
    """
    Parses prompts from clipboard string.
    Supports:
    - Newline-separated prompts
    - Numbered lists: "1. Prompt...", "1) Prompt...", "[1] Prompt..."
    - Bulleted lists: "- Prompt...", "* Prompt..."
    - Blank line separated paragraphs
    """
    if not text or not text.strip():
        return []

    lines = text.strip().splitlines()
    cleaned = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Strip list markers: "1.", "1)", "[1]", "-", "*", etc.
        line = re.sub(r'^(?:\d+[\.\)\]]|\-|\*|•)\s*', '', line).strip()
        if line:
            cleaned.append(line)

    return cleaned


class TandemPipelineCoordinator(QObject):
    """
    Orchestrates the prompt queue execution for Tandem Mode.
    Ensures strict order:
      1. Flow renders and finishes ALL batch downloads for 1 prompt
      2. Files are handed off to Vector Assist
      3. Vector Assist finishes ALL tracing & downloads for that batch
      4. Server marks prompt as 'copied' in DB and UI
      5. Next prompt is dispatched automatically until queue is empty
    """
    status_changed = Signal(str, str)            # worker_name, status_str
    log_emitted = Signal(str)                   # log message
    progress_updated = Signal(int, int)         # current_idx, total_prompts
    pipeline_finished = Signal(int)             # success_count
    prompt_started = Signal(int, str)           # prompt_id, prompt_text
    prompt_completed = Signal(int, str)         # prompt_id, prompt_text

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.server_thread = None
        self.port = 48200
        self.host = "127.0.0.1"

        # Worker status debounce (avoids flicker on 1-2s service worker wake)
        self._disconnect_timers = {}

        # State
        self.is_running = False
        self.queue = []         # list of dict: {"id": prompt_id, "prompt": text}
        self.current_job = None
        self.current_index = 0
        self.total_jobs = 0
        self.success_count = 0

        # Flow & Vector tracking per prompt
        self._flow_batch_files = []
        self._vector_completed = False

    def is_server_running(self) -> bool:
        return bool(self.server_thread and self.server_thread.isRunning())

    def start_server(self):
        if self.is_server_running():
            return True

        self.server_thread = TandemServerThread(host=self.host, port=self.port, parent=self)
        self.server_thread.server_status_changed.connect(self._on_server_status)
        self.server_thread.worker_status_changed.connect(self._on_worker_status)
        self.server_thread.log_emitted.connect(self.log_emitted.emit)
        self.server_thread.file_reported.connect(self._on_file_reported)
        self.server_thread.batch_completed.connect(self._on_batch_completed)
        self.server_thread.job_reported.connect(self._on_job_reported)
        self.server_thread.start()
        self.log_emitted.emit(f"[Tandem] Starting local bridge on {self.host}:{self.port}...")
        return True

    def stop_server(self):
        if self.is_running:
            self.stop_pipeline()

        if self.server_thread and self.server_thread.isRunning():
            self.server_thread.stop_server()
            self.server_thread = None
            self.log_emitted.emit("[Tandem] Bridge server stopped.")

    def _on_server_status(self, is_running, message):
        status = message if is_running else "Stopped"
        self.status_changed.emit("server", status)

    def _on_worker_status(self, worker_name, is_connected):
        timer = self._disconnect_timers.get(worker_name)
        if is_connected:
            if timer and timer.isActive():
                timer.stop()
            self.status_changed.emit(worker_name, "Connected")
        else:
            # Debounce disconnect by 3.5 seconds so brief reconnection is smooth
            if not timer:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(lambda w=worker_name: self.status_changed.emit(w, "Disconnected"))
                self._disconnect_timers[worker_name] = timer
            timer.start(3500)

    def is_ready_to_run(self) -> tuple[bool, str]:
        if not self.is_server_running():
            return False, "Server is not running. Start server first."
        if not self.server_thread.is_worker_connected("auto_flow"):
            return False, "Auto Flow Batcher is not connected in Chrome."
        if not self.server_thread.is_worker_connected("vector_assist"):
            return False, "Vector Assist is not connected in Chrome."
        return True, "Ready"

    def start_pipeline(self, prompt_items: list[dict]):
        """
        Starts executing prompt items in strict tandem sequence.
        prompt_items: list of dict {"id": prompt_id, "prompt": prompt_text}
        """
        if not prompt_items:
            self.log_emitted.emit("[Tandem] No prompts provided to execute.")
            return False

        ready, reason = self.is_ready_to_run()
        if not ready:
            self.log_emitted.emit(f"[Tandem] Cannot start: {reason}")
            return False

        self.queue = list(prompt_items)
        self.total_jobs = len(self.queue)
        self.current_index = 0
        self.success_count = 0
        self.is_running = True

        self.log_emitted.emit(f"[Tandem] Starting Tandem Pipeline for {self.total_jobs} prompt(s)...")
        self._dispatch_next()
        return True

    def stop_pipeline(self):
        self.is_running = False
        self.queue.clear()
        self.current_job = None
        self.log_emitted.emit("[Tandem] Tandem Pipeline stopped by user.")
        self.pipeline_finished.emit(self.success_count)

    def _dispatch_next(self):
        if not self.is_running:
            return

        if not self.queue:
            self.is_running = False
            self.log_emitted.emit(f"[Tandem] All {self.total_jobs} prompt(s) completed successfully!")
            self.pipeline_finished.emit(self.success_count)
            return

        self.current_job = self.queue.pop(0)
        self.current_index += 1
        self._flow_batch_files = []
        self._vector_completed = False

        prompt_text = self.current_job.get("prompt", "")
        prompt_id = self.current_job.get("id")

        self.progress_updated.emit(self.current_index, self.total_jobs)
        self.prompt_started.emit(prompt_id, prompt_text)
        self.log_emitted.emit(f"\n[Tandem] [{self.current_index}/{self.total_jobs}] Dispatching prompt to Flow: \"{prompt_text}\"")

        # Step 1: Send prompt to Auto Flow Batcher
        sent = self.server_thread.dispatch_prompt_to_flow(prompt_text)
        if not sent:
            self.log_emitted.emit("[Tandem] ERROR: Failed to dispatch prompt to Auto Flow Batcher.")
            self.stop_pipeline()

    def _on_job_reported(self, event, client, job_id):
        pass

    def _on_file_reported(self, source, filepath, filesize):
        if not self.is_running or not self.current_job:
            return

        # 1. Flow finished a file download
        if source == "auto_flow":
            if filepath and filepath not in self._flow_batch_files:
                self._flow_batch_files.append(filepath)
                self.log_emitted.emit(f"[Tandem] Flow downloaded: {os.path.basename(filepath)} ({filesize} bytes)")

        # 2. Vector Assist finished a vector download
        elif source == "vector_assist":
            self.log_emitted.emit(f"[Tandem] Vector Assist finished: {os.path.basename(filepath)} ({filesize} bytes)")

    def _on_batch_completed(self, source, filenames):
        if not self.is_running or not self.current_job:
            return

        if source == "auto_flow":
            for fn in (filenames or []):
                if fn and fn not in self._flow_batch_files:
                    self._flow_batch_files.append(fn)
            self.notify_flow_batch_completed()
        elif source == "vector_assist":
            self.notify_vector_batch_completed()

    def notify_flow_batch_completed(self, filenames: list[str] = None):
        """Called when Auto Flow Batcher finishes all downloads for the current prompt."""
        if not self.is_running or not self.current_job:
            return

        files = filenames or self._flow_batch_files
        if not files:
            self.log_emitted.emit("[Tandem] WARN: Flow batch completed but no files were recorded.")
            return

        self.log_emitted.emit(f"[Tandem] Flow finished batch ({len(files)} files). Handing off to Vector Assist...")
        self.server_thread.dispatch_files_to_vector(files)

    def notify_vector_batch_completed(self):
        """Called when Vector Assist finishes all vector tracing and downloads for the batch."""
        if not self.is_running or not self.current_job:
            return

        prompt_id = self.current_job.get("id")
        prompt_text = self.current_job.get("prompt", "")

        # Mark prompt as 'copied' in DB
        if self.db and prompt_id is not None:
            try:
                self.db.add_prompt_status(prompt_id, 'copied')
            except Exception as e:
                self.log_emitted.emit(f"[Tandem] Notice updating DB status: {e}")

        self.success_count += 1
        self.prompt_completed.emit(prompt_id, prompt_text)
        self.log_emitted.emit(f"[Tandem] Cycle complete for prompt [{self.current_index}/{self.total_jobs}]. Marked as copied ✓")

        # Automatically schedule next prompt in queue
        QTimer.singleShot(1500, self._dispatch_next)
