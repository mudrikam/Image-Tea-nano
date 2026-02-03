from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QSize
import qtawesome as qta
from ui.theme_system import theme

class EditTagDialog(QDialog):
    def __init__(self, tag_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Tag")
        self.setModal(True)
        self.setFixedWidth(280)
        
        layout = QVBoxLayout(self)
        
        self.tag_input = QLineEdit()
        self.tag_input.setText(tag_text)
        self.tag_input.selectAll()
        layout.addWidget(self.tag_input)
        
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        save_btn.setFixedWidth(72)
        save_btn.setIconSize(QSize(16, 16))
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.setFixedWidth(72)
        cancel_btn.setIconSize(QSize(16, 16))
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.tag_input.setFocus()
    
    def get_tag_text(self):
        return self.tag_input.text().strip()
