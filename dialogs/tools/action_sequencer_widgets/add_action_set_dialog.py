import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QLineEdit, QTextEdit, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont
from config import BASE_PATH
import qtawesome as qta
from database.db_operation import ImageTeaDB
from ui.theme_system import theme


class AddActionSetDialog(QDialog):
    action_set_saved = Signal()
    
    def __init__(self, platform_id, action_set_data=None, parent=None):
        super().__init__(parent)
        self.platform_id = platform_id
        self.action_set_data = action_set_data
        self.db = ImageTeaDB()
        
        if action_set_data:
            self.setWindowTitle("Edit Action Set")
        else:
            self.setWindowTitle("Add Action Set")
        
        self.setModal(True)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        
        if action_set_data:
            self.load_data()
        
        # Dynamically resize to fit content
        self.adjustSize()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        dialog_icon = qta.icon('fa6s.layer-group', color=theme.get_color('secondary'))
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel("Edit Action Set" if self.action_set_data else "Add New Action Set")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)
        name_icon = QLabel()
        name_icon.setPixmap(qta.icon('fa6s.cube', color='#888').pixmap(16, 16))
        name_layout.addWidget(name_icon)
        name_label = QLabel("Set Name:")
        name_label.setMinimumWidth(90)
        name_layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., DOC_SETUP, EXPORT, COLOR")
        name_layout.addWidget(self.name_input, 1)
        layout.addLayout(name_layout)
        
        desc_layout = QHBoxLayout()
        desc_layout.setSpacing(6)
        desc_layout.setAlignment(Qt.AlignTop)
        desc_icon = QLabel()
        desc_icon.setPixmap(qta.icon('fa6s.align-left', color='#888').pixmap(16, 16))
        desc_layout.addWidget(desc_icon)
        desc_label = QLabel("Description:")
        desc_label.setMinimumWidth(90)
        desc_layout.addWidget(desc_label)
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Optional description for this action set")
        self.desc_input.setMaximumHeight(70)
        desc_layout.addWidget(self.desc_input, 1)
        layout.addLayout(desc_layout)
        
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        save_icon = qta.icon('fa6s.floppy-disk')
        self.save_button = QPushButton(save_icon, " Save")
        self.save_button.clicked.connect(self.on_save)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_data(self):
        self.name_input.setText(self.action_set_data.get('name', ''))
        self.desc_input.setPlainText(self.action_set_data.get('description', ''))
    
    def on_save(self):
        name = self.name_input.text().strip()
        description = self.desc_input.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Action Set name is required")
            return
        
        try:
            if self.action_set_data:
                self.db.update_action_set(self.action_set_data['id'], name, description)
            else:
                self.db.add_action_set(self.platform_id, name, description)
            
            self.action_set_saved.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save action set: {e}")
