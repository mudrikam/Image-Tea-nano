from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QProgressBar, QSizePolicy)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.theme_system import theme


class RenderQueueWidget(QWidget):
    """Compact widget showing batch render progress and stats."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._total = 0
        self._completed = 0
        self._failed = 0
        self._cancelled = 0
        self._current_script_name = ''
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Stats row: compact single-line stats
        self.stats_label = QLabel("Queue: 0/0 | Completed: 0 | Failed: 0")
        self.stats_label.setStyleSheet("font-size: 11px;")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.stats_label)

        # Current script label
        self.current_label = QLabel("Waiting...")
        self.current_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(self.current_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('Ready')
        layout.addWidget(self.progress_bar)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(90)  # Compact under 100px

    def set_queue_stats(self, total, completed=0, failed=0, cancelled=0):
        """Update the displayed stats."""
        self._total = total
        self._completed = completed
        self._failed = failed
        self._cancelled = cancelled
        self.stats_label.setText(f"Queue: {completed + failed + cancelled}/{total} | OK: {completed} | Failed: {failed}")

    def set_current_script(self, script_name, collection_name=None, render_settings=None):
        """Set the currently rendering script with detailed info."""
        # Build detail string from render settings
        details = []
        if render_settings:
            width = render_settings.get('width', 0)
            height = render_settings.get('height', 0)
            fps = render_settings.get('fps', 0)
            duration = render_settings.get('duration', 0)
            codec = render_settings.get('codec', '')
            pixel_format = render_settings.get('pixel_format', '')
            scale = render_settings.get('scale', 1.0)

            # Resolution with scale
            if width and height:
                if scale != 1.0:
                    res = f"{int(width*scale)}x{int(height*scale)}"
                else:
                    res = f"{width}x{height}"
                details.append(res)

            # FPS
            if fps:
                details.append(f"{fps}fps")

            # Duration
            if duration:
                details.append(f"{duration}s")

            # Codec
            if codec:
                details.append(codec.upper())

            # Pixel format (show only if not default)
            if pixel_format and pixel_format != 'yuv420p':
                details.append(pixel_format)

        # Build display: collection / script [details]
        display = script_name
        if collection_name:
            display = f"{collection_name} / {script_name}"

        detail_str = " | ".join(details) if details else ""
        if detail_str:
            self.current_label.setText(f"Rendering: {display} [{detail_str}]")
        else:
            self.current_label.setText(f"Rendering: {display}")

    def set_progress(self, percentage, message=''):
        """Update progress bar."""
        if percentage >= 0:
            self.progress_bar.setValue(percentage)
            if message:
                self.progress_bar.setFormat(f'{message}')
        else:
            self.progress_bar.setFormat(message or 'Processing...')

    def on_script_completed(self):
        """Called when a script finishes successfully."""
        self._completed += 1
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat('Completed')
        self._update_stats()

    def on_script_failed(self):
        """Called when a script fails."""
        self._failed += 1
        self.progress_bar.setFormat('Failed')
        self._update_stats()

    def on_script_cancelled(self):
        """Called when a script is cancelled."""
        self._cancelled += 1
        self.progress_bar.setFormat('Cancelled')
        self._update_stats()

    def _update_stats(self):
        self.stats_label.setText(f"Queue: {self._completed + self._failed + self._cancelled}/{self._total} | OK: {self._completed} | Failed: {self._failed}")

    def reset(self):
        """Reset all stats and display."""
        self._total = 0
        self._completed = 0
        self._failed = 0
        self._cancelled = 0
        self._current_script_name = ''
        self.stats_label.setText("Queue: 0/0 | Completed: 0 | Failed: 0")
        self.current_label.setText("Waiting...")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('Ready')
