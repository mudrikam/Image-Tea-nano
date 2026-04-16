import threading
import time
from PySide6.QtCore import QThread, Signal
from helpers.remotion_helper.remotion_helper import render_video as remotion_render_video


class BatchRenderWorker(QThread):
    """
    Worker that processes a batch (queue) of scripts sequentially.
    Emits signals for each script's progress and completion.
    """
    script_started = Signal(int)  # script_id
    script_progress = Signal(int, int, str)  # script_id, percentage, message
    script_finished = Signal(int, bool, str, float)  # script_id, success, message, duration_seconds
    queue_finished = Signal()

    def __init__(self, scripts_queue, parent=None):
        """
        Initialize batch worker.
        
        Args:
            scripts_queue: List of dicts, each containing:
                - script_id: int
                - script_content: str
                - script_name: str
                - collection_name: str
                - output_path: str
                - render_settings: dict
        """
        super().__init__(parent)
        self.scripts_queue = scripts_queue.copy()
        self._cancel_event = threading.Event()
        self._cancel_flag = False

    def cancel(self):
        """Request cancellation of the batch render."""
        self._cancel_flag = True
        self._cancel_event.set()

    def run(self):
        """Process each script in the queue sequentially."""
        for index, script_info in enumerate(self.scripts_queue):
            if self._cancel_flag:
                # Mark remaining as cancelled
                remaining = self.scripts_queue[index:]
                for remaining_info in remaining:
                    self.script_finished.emit(
                        remaining_info['script_id'],
                        False,
                        'Render cancelled.',
                        0.0
                    )
                break

            script_id = script_info['script_id']
            script_content = script_info['script_content']
            output_path = script_info['output_path']
            render_settings = script_info['render_settings']

            # Emit started
            self.script_started.emit(script_id)

            # Progress callback for this script
            def progress_callback(pct, msg):
                if not self._cancel_flag:
                    self.script_progress.emit(script_id, pct, msg)

            # Render with timing
            start_time = time.time()
            success, message = remotion_render_video(
                script_content,
                output_path,
                render_settings,
                progress_callback,
                self._cancel_event
            )
            duration = time.time() - start_time

            # Emit finished
            self.script_finished.emit(script_id, success, message, duration)

        self.queue_finished.emit()
