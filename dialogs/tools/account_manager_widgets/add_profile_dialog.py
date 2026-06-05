import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QFileDialog, QMessageBox, QSizePolicy, QColorDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class AddProfileDialog(QDialog):
    """Dialog for creating/editing profile"""
    profile_saved = Signal(dict)
    
    def __init__(self, profile_data=None, workspace_data=None, parent=None):
        super().__init__(parent)
        self.profile_data = profile_data
        self.workspace_data = workspace_data
        self.is_edit_mode = profile_data is not None
        self.selected_icon = profile_data.get('profile_icon', 'user') if profile_data else 'user'
        self.selected_color = profile_data.get('profile_color', '#3b82f6') if profile_data else '#3b82f6'
        
        self.setWindowTitle('Edit Profile' if self.is_edit_mode else 'New Profile')
        self.setModal(True)
        self.setMinimumWidth(450)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self._setup_ui()
        if self.is_edit_mode:
            self._load_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        dialog_icon = qta.icon('fa6s.user', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel('Edit Profile' if self.is_edit_mode else 'New Profile')
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Name field
        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)
        name_icon = QLabel()
        name_icon.setPixmap(qta.icon('fa6s.signature', color=theme.get_color('gray')).pixmap(16, 16))
        name_layout.addWidget(name_icon)
        name_label = QLabel('Name:')
        name_label.setMinimumWidth(70)
        name_layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('e.g., John Doe, Admin Profile')
        self.name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        name_layout.addWidget(self.name_input, 1)
        layout.addLayout(name_layout)
        
        # Description field
        desc_layout = QHBoxLayout()
        desc_layout.setSpacing(6)
        desc_icon = QLabel()
        desc_icon.setPixmap(qta.icon('fa6s.align-left', color=theme.get_color('gray')).pixmap(16, 16))
        desc_layout.addWidget(desc_icon)
        desc_label = QLabel('Description:')
        desc_label.setMinimumWidth(70)
        desc_layout.addWidget(desc_label)
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText('Optional description...')
        self.desc_input.setMaximumHeight(60)
        desc_layout.addWidget(self.desc_input, 1)
        layout.addLayout(desc_layout)
        
        # Icon picker
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(6)
        icon_icon = QLabel()
        icon_icon.setPixmap(qta.icon('fa6s.icons', color=theme.get_color('gray')).pixmap(16, 16))
        icon_layout.addWidget(icon_icon)
        icon_label = QLabel('Icon:')
        icon_label.setMinimumWidth(70)
        icon_layout.addWidget(icon_label)
        
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(28, 28)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setCursor(Qt.PointingHandCursor)
        self.icon_preview.setToolTip('Click to choose icon')
        self.icon_preview.mousePressEvent = lambda e: self._choose_icon()
        self._update_icon_preview()
        icon_layout.addWidget(self.icon_preview)
        
        self.icon_btn = QPushButton(qta.icon('fa6s.magnifying-glass'), '')
        self.icon_btn.setMaximumWidth(32)
        self.icon_btn.setToolTip('Choose Icon')
        self.icon_btn.clicked.connect(self._choose_icon)
        icon_layout.addWidget(self.icon_btn)
        
        icon_layout.addStretch()
        layout.addLayout(icon_layout)
        
        # Color picker
        color_layout = QHBoxLayout()
        color_layout.setSpacing(6)
        color_icon = QLabel()
        color_icon.setPixmap(qta.icon('fa6s.palette', color=theme.get_color('gray')).pixmap(16, 16))
        color_layout.addWidget(color_icon)
        color_label = QLabel('Color:')
        color_label.setMinimumWidth(70)
        color_layout.addWidget(color_label)
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(28, 28)
        self.color_preview.setCursor(Qt.PointingHandCursor)
        self.color_preview.setToolTip('Click to choose color')
        self.color_preview.mousePressEvent = lambda e: self._choose_color()
        self._update_color_preview()
        color_layout.addWidget(self.color_preview)
        
        self.color_input = QLineEdit()
        self.color_input.setText(self.selected_color)
        self.color_input.setPlaceholderText('#3b82f6')
        self.color_input.textChanged.connect(self._on_color_changed)
        self.color_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        color_layout.addWidget(self.color_input, 1)
        
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        # Browser profile name - auto-generated from name
        profile_name_layout = QHBoxLayout()
        profile_name_layout.setSpacing(6)
        profile_icon = QLabel()
        profile_icon.setPixmap(qta.icon('fa6s.tag', color=theme.get_color('gray')).pixmap(16, 16))
        profile_name_layout.addWidget(profile_icon)
        profile_label = QLabel('Profile Folder:')
        profile_label.setMinimumWidth(70)
        profile_name_layout.addWidget(profile_label)
        
        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText('Auto-generated from profile name')
        self.profile_name_input.setEnabled(False)
        self.profile_name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.profile_name_input.setStyleSheet('QLineEdit:disabled { background-color: rgba(255,255,255,0.05); color: #888; }')
        profile_name_layout.addWidget(self.profile_name_input, 1)
        layout.addLayout(profile_name_layout)
        
        # Auto-update browser profile name from profile name
        self.name_input.textChanged.connect(self._update_browser_profile_name)
        
        # Browser profile path - auto-generated
        path_layout = QHBoxLayout()
        path_layout.setSpacing(6)
        path_icon = QLabel()
        path_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        path_layout.addWidget(path_icon)
        path_label = QLabel('Profile Path:')
        path_label.setMinimumWidth(70)
        path_layout.addWidget(path_label)
        
        self.profile_path_input = QLineEdit()
        self.profile_path_input.setPlaceholderText('Auto-generated from workspace root + name')
        self.profile_path_input.setEnabled(False)
        self.profile_path_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.profile_path_input.setStyleSheet('QLineEdit:disabled { background-color: rgba(255,255,255,0.05); color: #888; }')
        path_layout.addWidget(self.profile_path_input, 1)
        
        layout.addLayout(path_layout)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton(qta.icon('fa6s.xmark'), ' Cancel')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton(qta.icon('fa6s.floppy-disk'), ' Save')
        save_btn.clicked.connect(self._on_save)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def _update_browser_profile_name(self, text):
        """Auto-generate sanitized browser profile name from profile name"""
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        sanitized = re.sub(r'\s+', '_', sanitized).strip('_')
        self.profile_name_input.setText(sanitized)
        self._generate_browser_profile_path(sanitized)
    
    def _generate_browser_profile_path(self, profile_folder_name):
        """Generate full profile path from workspace root + profile folder name"""
        if not self.workspace_data:
            return
        
        root_path = self.workspace_data.get('workspace_root_profile_path', '')
        if not root_path:
            return
        
        # Combine root path with profile folder name
        full_path = os.path.join(root_path, profile_folder_name)
        self.profile_path_input.setText(full_path)
    
    def _update_icon_preview(self):
        try:
            icon = qta.icon(f'fa6s.{self.selected_icon}', color=self.selected_color)
            self.icon_preview.setPixmap(icon.pixmap(24, 24))
        except:
            self.icon_preview.setText('?')
    
    def _update_color_preview(self):
        self.color_preview.setStyleSheet(f'background-color: {self.selected_color}; border: 1px solid #444; border-radius: 3px;')
    
    def _choose_icon(self):
        from dialogs.tools.icon_picker_dialog import IconPickerDialog
        dialog = IconPickerDialog(current_icon=self.selected_icon, parent=self)
        dialog.icon_selected.connect(self._on_icon_selected)
        dialog.exec()
    
    def _on_icon_selected(self, icon_name):
        self.selected_icon = icon_name
        self._update_icon_preview()
    
    def _on_color_changed(self, text):
        if text.startswith('#') and len(text) == 7:
            self.selected_color = text
            self._update_color_preview()
            self._update_icon_preview()
    
    def _choose_color(self):
        """Open color dialog to choose color"""
        from PySide6.QtGui import QColor
        color = QColorDialog.getColor(QColor(self.selected_color), self, 'Choose Color')
        if color.isValid():
            self.selected_color = color.name()
            self.color_input.setText(self.selected_color)
            self._update_color_preview()
            self._update_icon_preview()
    
    def _load_data(self):
        if not self.profile_data:
            return
        
        self.name_input.setText(self.profile_data.get('profile_name', ''))
        self.desc_input.setPlainText(self.profile_data.get('profile_description', ''))
        
        # Browser profile name is auto-generated, but load if exists
        browser_profile_name = self.profile_data.get('profile_browser_profile_name', '')
        if browser_profile_name:
            self.profile_name_input.setText(browser_profile_name)
        
        # Generate profile path from workspace + profile name
        self._generate_browser_profile_path(browser_profile_name)
        self.color_input.setText(self.selected_color)
    
    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, 'Validation Error', 'Profile name is required')
            return
        
        # Use sanitized browser profile name
        browser_profile_name = self.profile_name_input.text().strip()
        
        data = {
            'profile_name': name,
            'profile_description': self.desc_input.toPlainText().strip(),
            'profile_icon': self.selected_icon,
            'profile_color': self.selected_color,
            'profile_browser_profile_name': browser_profile_name,
            'profile_browser_profile_path': self.profile_path_input.text().strip(),
        }
        
        if self.is_edit_mode:
            data['profile_id'] = self.profile_data['profile_id']
        
        self.profile_saved.emit(data)
        self.accept()
