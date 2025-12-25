import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QLineEdit, QTextEdit, QMessageBox, QComboBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont
from config import BASE_PATH
import qtawesome as qta
from database.db_operation import ImageTeaDB


class AddPresetDialog(QDialog):
    preset_saved = Signal()
    
    def __init__(self, platform_id, preset_data=None, parent=None):
        super().__init__(parent)
        self.platform_id = platform_id
        self.preset_data = preset_data
        self.db = ImageTeaDB()
        
        if preset_data:
            self.setWindowTitle("Edit Preset")
        else:
            self.setWindowTitle("Add Preset")
        
        self.setModal(True)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        
        if preset_data:
            self.load_data()
        
        self.resize(400, 300)
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        dialog_icon = qta.icon('fa6s.list-check', color='#4A90E2')
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel("Edit Preset" if self.preset_data else "Add New Preset")
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
        name_icon.setPixmap(qta.icon('fa6s.tag', color='#888').pixmap(16, 16))
        name_layout.addWidget(name_icon)
        name_label = QLabel("Preset Name:")
        name_label.setMinimumWidth(90)
        name_layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., BUAT MOCKUP, PRINT PREP")
        name_layout.addWidget(self.name_input, 1)
        layout.addLayout(name_layout)
        
        type_layout = QHBoxLayout()
        type_layout.setSpacing(6)
        type_icon = QLabel()
        type_icon.setPixmap(qta.icon('fa6s.folder-tree', color='#888').pixmap(16, 16))
        type_layout.addWidget(type_icon)
        type_label = QLabel("Preset Type:")
        type_label.setMinimumWidth(90)
        type_layout.addWidget(type_label)
        self.type_input = QComboBox()
        self.type_input.setEditable(False)
        self.type_input.addItems(["Batch", "Single Run"])
        self.type_input.setCurrentIndex(-1)
        type_layout.addWidget(self.type_input, 1)
        layout.addLayout(type_layout)
        
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
        self.desc_input.setPlaceholderText("Optional description for this preset")
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
        self.name_input.setText(self.preset_data.get('name', ''))
        preset_type = self.preset_data.get('type', '')
        if preset_type:
            index = self.type_input.findText(preset_type)
            if index >= 0:
                self.type_input.setCurrentIndex(index)
            else:
                self.type_input.setEditText(preset_type)
        self.desc_input.setPlainText(self.preset_data.get('description', ''))
    
    def on_save(self):
        name = self.name_input.text().strip()
        preset_type = self.type_input.currentText().strip()
        description = self.desc_input.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Preset name is required")
            return
        
        if not preset_type:
            QMessageBox.warning(self, "Validation Error", "Preset type is required")
            return
        
        try:
            if self.preset_data:
                self.db.update_preset(self.preset_data['id'], name, description, preset_type)
            else:
                self.db.add_preset(self.platform_id, name, description, preset_type)
            
            self.preset_saved.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save preset: {e}")
