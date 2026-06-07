import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from config import BASE_PATH


class ProgressDialog(QDialog):
    """Progress dialog for import/export operations"""
    
    def __init__(self, title="Processing", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(120)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title label
        self.title_label = QLabel("Preparing...")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(self.title_label)
        
        # Detail label
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("font-size: 10px; color: #888;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v%")
        layout.addWidget(self.progress_bar)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.hide()
        layout.addWidget(self.cancel_btn, alignment=Qt.AlignRight)
    
    def set_title(self, title):
        """Set the main title text"""
        self.title_label.setText(title)
    
    def set_detail(self, detail):
        """Set the detail text"""
        self.detail_label.setText(detail)
    
    def set_progress(self, value, maximum=100):
        """Set progress value"""
        if maximum > 0:
            self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
    
    def set_indeterminate(self, active=True):
        """Set indeterminate state (infinite progress)"""
        if active:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
    
    def set_cancel_enabled(self, enabled):
        """Show/hide cancel button"""
        self.cancel_btn.setVisible(enabled)
    
    def update_progress(self, value, maximum=100):
        """Update progress bar (thread-safe when called via signal)
        
        For threaded operations, format shows 'count/total' instead of percentage
        to avoid confusion with small counts (e.g. 1-6 items showing 1-6%)
        """
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
        if maximum <= 100 and value <= maximum:
            # For count-based progress, show "count/total" format
            self.progress_bar.setFormat(f"{value}/{maximum}")
        else:
            # For percentage-based progress
            percentage = int((value / maximum * 100) if maximum > 0 else 0)
            self.progress_bar.setFormat(f"{percentage}%")