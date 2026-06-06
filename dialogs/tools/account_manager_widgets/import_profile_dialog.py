import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QMessageBox, QRadioButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class ImportProfileDialog(QDialog):
    """Dialog for selecting import source (zip file or folder)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_source = None
        self.setWindowTitle('Import Profile')
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
        icon_label.setPixmap(qta.icon('fa6s.file-import', color=theme.get_color('primary')).pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel('Import Profile')
        title_label.setStyleSheet('font-size: 14px; font-weight: bold;')
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        type_layout = QVBoxLayout()
        type_layout.setSpacing(6)
        
        type_label = QLabel('Select source type:')
        type_layout.addWidget(type_label)
        
        self.zip_radio = QRadioButton('ZIP file (.zip)')
        self.zip_radio.setChecked(True)
        type_layout.addWidget(self.zip_radio)
        
        self.folder_radio = QRadioButton('Profile folder')
        type_layout.addWidget(self.folder_radio)
        
        layout.addLayout(type_layout)
        
        path_layout = QHBoxLayout()
        path_layout.setSpacing(6)
        
        self.path_label = QLabel('No file selected')
        path_layout.addWidget(self.path_label, 1)
        
        self.browse_btn = QPushButton(qta.icon('fa6s.folder-open'), ' Browse')
        self.browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(self.browse_btn)
        
        layout.addLayout(path_layout)
        
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton(qta.icon('fa6s.xmark'), ' Cancel')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        import_btn = QPushButton(qta.icon('fa6s.file-import'), ' Import')
        import_btn.clicked.connect(self._on_import)
        import_btn.setDefault(True)
        button_layout.addWidget(import_btn)
        
        layout.addLayout(button_layout)
    
    def _on_browse(self):
        if self.zip_radio.isChecked():
            path, _ = QFileDialog.getOpenFileName(
                self,
                'Select ZIP File',
                '',
                'ZIP Files (*.zip);;All Files (*.*)'
            )
        else:
            path = QFileDialog.getExistingDirectory(
                self,
                'Select Profile Folder'
            )
        
        if path:
            self.selected_source = path
    
    def _on_import(self):
        if not self.selected_source:
            QMessageBox.warning(self, 'No Source', 'Please select a source file or folder first')
            return
        
        if self.zip_radio.isChecked() and not self.selected_source.endswith('.zip'):
            QMessageBox.warning(self, 'Invalid File', 'Selected file is not a ZIP file')
            return
        
        if self.folder_radio.isChecked() and not os.path.isdir(self.selected_source):
            QMessageBox.warning(self, 'Invalid Folder', 'Selected path is not a valid folder')
            return
        
        self.accept()