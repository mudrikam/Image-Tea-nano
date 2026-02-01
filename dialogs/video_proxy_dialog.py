from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QFrame
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.theme_system import theme

class VideoProxyDialog(QDialog):
    def __init__(self, parent=None, batch_info=None):
        super().__init__(parent)
        self.setWindowTitle("Video Proxy Processing")
        self.setModal(True)
        self.setMinimumWidth(420)
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

        if self.total_files > 1:
            batch_layout = QHBoxLayout()
            batch_icon = QLabel()
            batch_icon.setPixmap(qta.icon('fa6s.layer-group', color=theme.get_color('primary')).pixmap(16, 16))
            batch_layout.addWidget(batch_icon)
            self.batch_label = QLabel(f"File 1 of {self.total_files}")
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
        progress_layout.setSpacing(5)

        self.status_label = QLabel("Please wait: creating video proxy...")
        self.status_label.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 11px;")
        progress_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        # Indeterminate progress bar while FFmpeg runs
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_bar)

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
        if hasattr(self, 'batch_label'):
            self.batch_label.setText(f"File {index + 1} of {self.total_files}")
        self.filename_label.setText(f"Filename: {filename}")

    def update_progress(self, data):
        status = data.get("status")
        if status == "starting":
            preset_name = data.get("preset", "-")
            preset_label = data.get("preset_label", "-")
            self.settings_detail_label.setText(f"{preset_name} ({preset_label})")
            self.status_label.setText("Please wait: creating video proxy...")
            # keep indeterminate bar
        elif status == "completed":
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.status_label.setText("Completed")
            self.status_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold;")
        elif status == "error":
            error = data.get("error", "Unknown error")
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet(f"color: {theme.get_color('error')}; font-weight: bold;")
        else:
            self.status_label.setText("Please wait: creating video proxy...")
