from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt


class PromptEditDialog(QDialog):
    """Dialog for editing a single prompt with character count display"""
    
    def __init__(self, prompt_id, prompt_text, parent=None):
        super().__init__(parent)
        self.prompt_id = prompt_id
        self.original_text = prompt_text
        self.db = getattr(parent, 'db', None)
        
        self.setWindowTitle("Edit Prompt")
        self.setFixedSize(800, 600)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Character count label
        self.char_count_label = QLabel("Characters: 0")
        self.char_count_label.setStyleSheet("color: #666; margin-bottom: 5px;")
        layout.addWidget(self.char_count_label)
        
        # Text edit area
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(prompt_text)
        self.text_edit.textChanged.connect(self.update_char_count)
        layout.addWidget(self.text_edit)
        
        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_and_close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Initial character count
        self.update_char_count()
        
        # Focus on text area
        self.text_edit.setFocus()
    
    def update_char_count(self):
        """Update the character count display"""
        text = self.text_edit.toPlainText()
        char_count = len(text)
        self.char_count_label.setText(f"Characters: {char_count}")
    
    def save_and_close(self):
        """Save the edited prompt to database and close dialog"""
        if not self.db:
            self.reject()
            return
            
        new_text = self.text_edit.toPlainText().strip()
        if new_text != self.original_text:
            try:
                self.db.update_generated_prompt(self.prompt_id, new_text)
                self.accept()
            except Exception as e:
                print(f"Error saving prompt: {e}")
                self.reject()
        else:
            self.reject()
