import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class DeleteConfirmationDialog(QDialog):
    """Dialog that requires user to type exact name to confirm deletion"""
    
    def __init__(self, item_type, item_name, parent=None):
        """
        Args:
            item_type: "Workspace", "Group", or "Profile"
            item_name: The exact name that must be typed
            parent: Parent widget
        """
        super().__init__(parent)
        self.item_type = item_type
        self.item_name = item_name
        
        self.setWindowTitle(f'Delete {item_type}')
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
        
        # Warning header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        warning_icon = QLabel()
        warning_icon.setPixmap(qta.icon('fa6s.triangle-exclamation', color='#ef4444').pixmap(32, 32))
        header_layout.addWidget(warning_icon)
        
        title_label = QLabel(f'Delete {self.item_type}?')
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Warning message
        warning_text = QLabel(
            f'This will permanently delete <b>{self.item_name}</b>.'
        )
        warning_text.setWordWrap(True)
        layout.addWidget(warning_text)
        
        # Additional warning for workspace/group
        if self.item_type in ['Workspace', 'Group']:
            cascade_text = QLabel(
                f'⚠️ All nested items will also be deleted.'
            )
            cascade_text.setStyleSheet('color: #ef4444; font-weight: bold;')
            layout.addWidget(cascade_text)
        
        # Confirmation instruction
        confirm_label = QLabel(
            f'Type <b>{self.item_name}</b> to confirm:'
        )
        layout.addWidget(confirm_label)
        
        # Input field
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(f'Type "{self.item_name}" here')
        self.name_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.name_input)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton(' Cancel')
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.delete_btn = QPushButton(' Delete')
        self.delete_btn.setIcon(qta.icon('fa6s.trash'))
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.accept)
        self.delete_btn.setDefault(True)
        button_layout.addWidget(self.delete_btn)
        
        layout.addLayout(button_layout)
    
    def _on_text_changed(self, text):
        """Enable delete button only if exact name is typed"""
        self.delete_btn.setEnabled(text == self.item_name)
