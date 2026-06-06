import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class ExportProfileDialog(QDialog):
    """Dialog for selecting profile to export"""
    
    def __init__(self, profiles, parent=None):
        super().__init__(parent)
        self.profiles = profiles
        self.selected_profile = None
        self.setWindowTitle('Export Profile')
        self.setModal(True)
        self.setMinimumWidth(400)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.file-zipper', color=theme.get_color('primary')).pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel('Select Profile to Export')
        title_label.setStyleSheet('font-size: 14px; font-weight: bold;')
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        self.list_widget = QListWidget()
        for profile in self.profiles:
            item = QListWidgetItem(profile.get('profile_name', 'Unnamed'))
            item.setData(Qt.UserRole, profile)
            self.list_widget.addItem(item)
        
        layout.addWidget(self.list_widget)
        
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton(qta.icon('fa6s.xmark'), ' Cancel')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        export_btn = QPushButton(qta.icon('fa6s.file-zipper'), ' Export')
        export_btn.clicked.connect(self._on_export)
        export_btn.setDefault(True)
        button_layout.addWidget(export_btn)
        
        layout.addLayout(button_layout)
    
    def _on_export(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, 'No Selection', 'Please select a profile to export')
            return
        
        self.selected_profile = current_item.data(Qt.UserRole)
        self.accept()