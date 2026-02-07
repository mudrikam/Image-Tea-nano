from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QFrame
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.theme_system import theme

class VideoProxyDialog(QDialog):
    def __init__(self, parent=None, batch_info=None):
        super().__init__(parent)
        self.setWindowTitle("Video Proxy Processing")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.batch_info = batch_info or {}
        self.current_file_index = 0
        self.total_files = batch_info.get('total_files', 1)
        self.stop_requested = False

        layout = QVBoxLayout()
        layout.setSpacing(10)

        title_label = QLabel("Creating Video Proxy for AI Processing")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        batch_layout = QHBoxLayout()
        batch_icon = QLabel()
        batch_icon.setPixmap(qta.icon('fa6s.layer-group', color=theme.get_color('primary')).pixmap(16, 16))
        batch_layout.addWidget(batch_icon)
        self.batch_label = QLabel(f"Video 1 of {self.total_files}")
        self.batch_label.setStyleSheet(f"font-weight: bold; color: {theme.get_color('primary')};")
        batch_layout.addWidget(self.batch_label)
        batch_layout.addStretch()
        layout.addLayout(batch_layout)

        self.filename_label = QLabel("Filename: -")
        self.filename_label.setStyleSheet(f"color: {theme.get_color('text_dark')};")
        layout.addWidget(self.filename_label)

        info_grid = QVBoxLayout()
        info_grid.setSpacing(6)
        settings_label = QLabel("Creating video proxy with settings:")
        settings_label.setStyleSheet(f"font-weight: bold; color: {theme.get_color('primary')};")
        self.settings_detail_label = QLabel("-")
        self.settings_detail_label.setStyleSheet(f"color: {theme.get_color('text_dark')};")
        info_grid.addWidget(settings_label)
        info_grid.addWidget(self.settings_detail_label)
        layout.addLayout(info_grid)

        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)

        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(8)

        batch_progress_label = QLabel("Batch Progress:")
        batch_progress_label.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 11px; font-weight: bold;")
        progress_layout.addWidget(batch_progress_label)

        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setRange(0, self.total_files)
        self.batch_progress_bar.setValue(0)
        self.batch_progress_bar.setTextVisible(True)
        self.batch_progress_bar.setFormat("%v / %m videos")
        progress_layout.addWidget(self.batch_progress_bar)

        current_progress_label = QLabel("Current Video:")
        current_progress_label.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 11px; font-weight: bold;")
        progress_layout.addWidget(current_progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Please wait: creating video proxy...")
        self.status_label.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 11px;")
        progress_layout.addWidget(self.status_label)

        layout.addLayout(progress_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_button = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
        self.cancel_button.clicked.connect(self.request_stop)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def request_stop(self):
        self.stop_requested = True
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Status: Cancelling...")

    def set_current_file(self, index, filename):
        self.current_file_index = index
        self.batch_label.setText(f"Video {index + 1} of {self.total_files}")
        self.filename_label.setText(f"Filename: {filename}")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.status_label.setText("Please wait: creating video proxy...")
        self.status_label.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 11px;")

    def set_total_files(self, total):
        self.total_files = total
        self.batch_progress_bar.setRange(0, total)
        self.batch_label.setText(f"Video {self.current_file_index + 1} of {total}")

    def update_batch_progress(self, completed_count):
        self.batch_progress_bar.setValue(completed_count)

    def update_progress(self, data):
        status = data.get("status")
        if status == "starting":
            preset_name = data.get("preset", "-")
            preset_label = data.get("preset_label", "-")
            self.settings_detail_label.setText(f"{preset_name} ({preset_label})")
            self.status_label.setText("Please wait: creating video proxy...")
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setTextVisible(False)
        elif status == "processing":
            progress = data.get("progress", 0)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(progress)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setFormat(f"{progress}%")
            current_time = data.get("current_time", 0)
            duration = data.get("duration", 0)
            if duration > 0:
                self.status_label.setText(f"Encoding: {current_time:.1f}s / {duration:.1f}s")
        elif status == "completed":
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setFormat("100%")
            self.status_label.setText("Video completed")
            self.status_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold; font-size: 11px;")
        elif status == "error":
            error = data.get("error", "Unknown error")
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet(f"color: {theme.get_color('error')}; font-weight: bold; font-size: 11px;")
        elif status == "info":
            info = data.get("info", "")
            self.status_label.setText(info)
        elif status == "batch_complete":
            self.status_label.setText("All videos processed")
            self.status_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold; font-size: 11px;")
            self.cancel_button.setText(" Close")
            self.cancel_button.setIcon(qta.icon('fa6s.check'))
        else:
            self.status_label.setText("Please wait: creating video proxy...")
