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


class AddWorkspaceDialog(QDialog):
    """Dialog for creating/editing workspace"""
    workspace_saved = Signal(dict)
    
    def __init__(self, workspace_data=None, parent=None):
        super().__init__(parent)
        self.workspace_data = workspace_data
        self.is_edit_mode = workspace_data is not None
        self.selected_icon = workspace_data.get('workspace_icon', 'briefcase') if workspace_data else 'briefcase'
        self.selected_color = workspace_data.get('workspace_color', '#3b82f6') if workspace_data else '#3b82f6'
        
        self.setWindowTitle('Edit Workspace' if self.is_edit_mode else 'New Workspace')
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
        
        from PySide6.QtGui import QFont
        dialog_icon = qta.icon('fa6s.briefcase', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel('Edit Workspace' if self.is_edit_mode else 'New Workspace')
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
        self.name_input.setPlaceholderText('e.g., Chrome Profiles, Firefox Testing')
        from PySide6.QtWidgets import QSizePolicy
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
        
        # Browser exe path
        exe_label_layout = QHBoxLayout()
        exe_label_layout.setSpacing(6)
        exe_icon = QLabel()
        exe_icon.setPixmap(qta.icon('fa6s.file', color=theme.get_color('gray')).pixmap(16, 16))
        exe_label_layout.addWidget(exe_icon)
        exe_label = QLabel('Browser Exe:')
        exe_label.setMinimumWidth(70)
        exe_label_layout.addWidget(exe_label)
        
        self.exe_input = QLineEdit()
        self.exe_input.setPlaceholderText('e.g., C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe')
        self.exe_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        exe_label_layout.addWidget(self.exe_input, 1)
        
        exe_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), '')
        exe_browse_btn.setMaximumWidth(32)
        exe_browse_btn.clicked.connect(self._browse_exe)
        exe_label_layout.addWidget(exe_browse_btn)
        
        layout.addLayout(exe_label_layout)
        
        # Root profile path
        root_layout = QHBoxLayout()
        root_layout.setSpacing(6)
        root_icon = QLabel()
        root_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        root_layout.addWidget(root_icon)
        root_label = QLabel('Root Path:')
        root_label.setMinimumWidth(70)
        root_layout.addWidget(root_label)
        
        self.root_input = QLineEdit()
        self.root_input.setPlaceholderText('e.g., C:\\BrowserProfiles')
        self.root_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root_layout.addWidget(self.root_input, 1)
        
        root_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), '')
        root_browse_btn.setMaximumWidth(32)
        root_browse_btn.clicked.connect(self._browse_root)
        root_layout.addWidget(root_browse_btn)
        
        layout.addLayout(root_layout)
        
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
    
    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 
            'Select Browser Executable', 
            '', 
            'Executable Files (*.exe);;All Files (*.*)'
        )
        if path:
            self.exe_input.setText(path)
    
    def _browse_root(self):
        path = QFileDialog.getExistingDirectory(self, 'Select Root Profile Directory')
        if path:
            self.root_input.setText(path)
    
    def _load_data(self):
        if not self.workspace_data:
            return
        
        self.name_input.setText(self.workspace_data.get('workspace_name', ''))
        self.desc_input.setPlainText(self.workspace_data.get('workspace_description', ''))
        self.exe_input.setText(self.workspace_data.get('workspace_browser_exe_path', ''))
        self.root_input.setText(self.workspace_data.get('workspace_root_profile_path', ''))
        self.color_input.setText(self.selected_color)
    
    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, 'Validation Error', 'Workspace name is required')
            return
        
        data = {
            'workspace_name': name,
            'workspace_description': self.desc_input.toPlainText().strip(),
            'workspace_icon': self.selected_icon,
            'workspace_color': self.selected_color,
            'workspace_browser_exe_path': self.exe_input.text().strip(),
            'workspace_root_profile_path': self.root_input.text().strip(),
        }
        
        if self.is_edit_mode:
            data['workspace_id'] = self.workspace_data['workspace_id']
        
        self.workspace_saved.emit(data)
        self.accept()
