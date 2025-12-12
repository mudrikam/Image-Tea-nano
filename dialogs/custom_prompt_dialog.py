from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
import os
import json
import qtawesome as qta
from PySide6.QtGui import QIcon
from config import BASE_PATH

class CustomPromptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Prompt")
        self.resize(400, 300)
        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlaceholderText("Enter a custom prompt here")
        layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.setIcon(qta.icon("fa6s.xmark"))
        self.cancel_btn.clicked.connect(self.reject)

        self.clear_btn = QPushButton("Clear", self)
        self.clear_btn.setIcon(qta.icon("fa6s.broom"))
        self.clear_btn.clicked.connect(lambda: self.text_edit.clear())

        self.save_btn = QPushButton("Save", self)
        self.save_btn.setIcon(qta.icon("fa6s.floppy-disk"))
        self.save_btn.clicked.connect(self.save_and_close)

        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        self.config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        self._initial_value = None
        self.load_prompt()

    def load_prompt(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        prompt = data["prompt"]
        value = prompt["custom_prompt"]
        self._initial_value = value
        if value and value.strip():
            self.text_edit.setPlainText(value)

    def save_and_close(self):
        text = self.text_edit.toPlainText()
        if text == self._initial_value:
            self.accept()
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to open config for saving custom prompt: {e}")
            return
        if "prompt" not in data:
            data["prompt"] = {}
        data["prompt"]["custom_prompt"] = text
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save custom prompt: {e}")
        parent = self.parent()
        if parent is not None and hasattr(parent, "prompt_section") and hasattr(parent.prompt_section, "load_prompt_config"):
            parent.prompt_section.load_prompt_config()
        self.accept()
