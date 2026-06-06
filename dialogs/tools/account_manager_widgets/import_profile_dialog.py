import os
import zipfile
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QMessageBox, QRadioButton, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class ImportProfileDialog(QDialog):
    """Dialog for selecting import source (zip file or folder)"""
    
    def __init__(self, workspace_browser_type='chrome', parent=None):
        super().__init__(parent)
        self.workspace_browser_type = workspace_browser_type
        self.selected_source = None
        self.selected_profiles = []  # For multi-profile zip - list of (path, name, browser_type)
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
        
        # Browser type warning
        browser_names = {'chrome': 'Chrome/Chromium', 'firefox': 'Firefox'}
        browser_type_label = QLabel(f'Current workspace: <b>{browser_names.get(self.workspace_browser_type, self.workspace_browser_type)}</b>')
        browser_type_label.setStyleSheet(f'font-size: 10px; color: {theme.get_color("gray")};')
        layout.addWidget(browser_type_label)
        
        type_layout = QVBoxLayout()
        type_layout.setSpacing(6)
        
        type_label = QLabel('Select source type:')
        type_layout.addWidget(type_label)
        
        self.zip_radio = QRadioButton('ZIP file (.zip) - Supports multiple profiles')
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
        
        # Profile list for multi-profile zip (hidden initially)
        self.profiles_list_label = QLabel('Profiles in ZIP:')
        self.profiles_list_label.setStyleSheet('font-size: 11px; font-weight: bold; margin-top: 8px;')
        self.profiles_list_label.hide()
        layout.addWidget(self.profiles_list_label)
        
        self.profiles_list = QListWidget()
        self.profiles_list.setMaximumHeight(120)
        self.profiles_list.hide()
        layout.addWidget(self.profiles_list)
        
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
            if path:
                self.selected_source = path
                self.path_label.setText(path)
                
                # Scan ZIP for profiles
                self._scan_zip_profiles(path)
        else:
            path = QFileDialog.getExistingDirectory(
                self,
                'Select Profile Folder'
            )
            if path:
                self.selected_source = path
                self.path_label.setText(path)
    
    def _scan_zip_profiles(self, zip_path):
        """Scan ZIP file for multiple profiles and show them in list"""
        self.profiles_list.clear()
        self.profiles_list_label.hide()
        self.profiles_list.hide()
        self.selected_profiles = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                namelist = zip_ref.namelist()
                
                # Find all profile folders by looking for metadata files
                profile_names = set()
                for name in namelist:
                    if 'account_management_profile_metadata.json' in name:
                        parts = name.split('/')
                        if len(parts) >= 1:
                            profile_names.add(parts[0])
                    elif name.endswith('_metadata.json'):
                        # all_profiles format
                        parts = name.split('/')
                        if len(parts) >= 1:
                            profile_names.add(parts[0].replace('_metadata.json', ''))
                
                if profile_names:
                    self.profiles_list_label.show()
                    self.profiles_list.show()
                    
                    zip_name = os.path.basename(zip_path)
                    
                    for profile_name in sorted(profile_names):
                        # Create temp item - we'll detect browser type during actual import
                        item = QListWidgetItem(f"{profile_name}")
                        item.setData(Qt.UserRole, (profile_name, zip_name))
                        self.profiles_list.addItem(item)
                    
                    # If multiple profiles, auto-select all
                    if self.profiles_list.count() > 1:
                        self.profiles_list.selectAll()
        except Exception:
            pass
    
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
        
        # For multi-profile zip, store the profile names to import
        if self.selected_source.endswith('.zip') and self.profiles_list.isVisible():
            self.selected_profiles = []
            for i in range(self.profiles_list.count()):
                item = self.profiles_list.item(i)
                profile_name, zip_name = item.data(Qt.UserRole)
                self.selected_profiles.append((profile_name, zip_name))
        else:
            self.selected_profiles = [None]  # Single profile indicator
        
        self.accept()