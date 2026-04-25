from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt
from ui.theme_system import theme


class PromptedImageSorterStatsWidget(QWidget):
    """Stats bar with two rows for image sorting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_retry = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Row 1: Source count and Target count
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self.source_label = QLabel("Source: —")
        self.source_label.setStyleSheet("font-size: 11px;")
        row1.addWidget(self.source_label)
        self.target_label = QLabel("Target: —")
        self.target_label.setStyleSheet("font-size: 11px;")
        row1.addWidget(self.target_label)
        self.retry_label = QLabel("Retry: —")
        self.retry_label.setStyleSheet("font-size: 11px; color: gray;")
        row1.addWidget(self.retry_label)
        row1.addStretch()
        layout.addLayout(row1)

        # Row 2: Elapsed, ETA, Files remaining
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        self.elapsed_label = QLabel("Elapsed: —")
        self.elapsed_label.setStyleSheet("font-size: 11px; color: gray;")
        row2.addWidget(self.elapsed_label)
        self.remaining_time_label = QLabel("ETA: —")
        self.remaining_time_label.setStyleSheet("font-size: 11px; color: gray;")
        row2.addWidget(self.remaining_time_label)
        self.remaining_files_label = QLabel("Files left: —")
        self.remaining_files_label.setStyleSheet("font-size: 11px; color: gray;")
        row2.addWidget(self.remaining_files_label)
        row2.addStretch()
        layout.addLayout(row2)

        # Progress bar — full width
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (%v/%m)")
        self.progress_bar.setMinimumHeight(16)
        layout.addWidget(self.progress_bar)

    def set_stats(self, source_count=0, target_count=0, elapsed="—", remaining_time="—", remaining_files="—"):
        """Update stats display."""
        self.source_label.setText(f"Source: {source_count:,} files" if source_count else "Source: 0 files")
        self.target_label.setText(f"Target: {target_count}")
        self.elapsed_label.setText(f"Elapsed: {elapsed}")
        self.remaining_time_label.setText(f"ETA: {remaining_time}")
        self.remaining_files_label.setText(f"Files left: {remaining_files}")

    def set_retry(self, current, maximum):
        """Update retry display."""
        print(f"[StatsWidget] set_retry called: current={current}, maximum={maximum}")
        if current > 0:
            self.retry_label.setText(f"Retry: {current}/{maximum}")
            self.retry_label.setStyleSheet("font-size: 11px; color: #f59e0b;")
        else:
            self.retry_label.setText("Retry: —")
            self.retry_label.setStyleSheet("font-size: 11px; color: gray;")
            self._last_retry = 0

    def set_last_retry(self, value):
        """Store the last retry value to persist it."""
        self._last_retry = value
        if value > 0:
            self.retry_label.setText(f"Last Retry: {value}")
            self.retry_label.setStyleSheet("font-size: 11px; color: #f59e0b;")
        else:
            self.retry_label.setText("Retry: —")
            self.retry_label.setStyleSheet("font-size: 11px; color: gray;")

    def set_progress_value(self, value):
        if self.progress_bar.maximum() > 0:
            self.progress_bar.setValue(value)

    def set_progress_max(self, maximum):
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(0)

    def reset_progress(self):
        self.progress_bar.setValue(0)
        self.source_label.setText("Source: —")
        self.target_label.setText("Target: —")
        self.retry_label.setText("Retry: —")
        self.retry_label.setStyleSheet("font-size: 11px; color: gray;")
        self.elapsed_label.setText("Elapsed: —")
        self.remaining_time_label.setText("ETA: —")
        self.remaining_files_label.setText("Files left: —")
