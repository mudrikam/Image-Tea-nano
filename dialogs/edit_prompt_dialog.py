from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel, QMessageBox, QWidget, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_PATH

class EditPromptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Prompt")
        self.setFixedSize(600, 700)
        main_layout = QVBoxLayout(self)

        top_widget = QWidget(self)
        top_grid = QGridLayout(top_widget)
        top_grid.setColumnStretch(0, 1)
        top_grid.setColumnStretch(1, 1)
        top_grid.setContentsMargins(0, 0, 0, 0)

        self.title_req_label = QLabel("Title Requirements:")
        self.title_req_edit = QTextEdit(self)
        self.title_req_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.title_req_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.title_req_edit.setAcceptRichText(False)

        self.desc_req_label = QLabel("Description Requirements:")
        self.desc_req_edit = QTextEdit(self)
        self.desc_req_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.desc_req_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.desc_req_edit.setAcceptRichText(False)

        self.keywords_req_label = QLabel("Keywords Requirements:")
        self.keywords_req_edit = QTextEdit(self)
        self.keywords_req_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.keywords_req_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.keywords_req_edit.setAcceptRichText(False)

        top_grid.addWidget(self.title_req_label, 0, 0)
        top_grid.addWidget(self.desc_req_label, 0, 1)
        top_grid.addWidget(self.title_req_edit, 1, 0)
        top_grid.addWidget(self.desc_req_edit, 1, 1)
        top_grid.addWidget(self.keywords_req_label, 2, 0)
        top_grid.addWidget(self.keywords_req_edit, 3, 0, 1, 2)
        main_layout.addWidget(top_widget, 2)

        self.general_guides_label = QLabel("General Guides:")
        self.general_guides_edit = QTextEdit(self)
        self.general_guides_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.general_guides_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.general_guides_edit.setAcceptRichText(False)
        main_layout.addWidget(self.general_guides_label)
        main_layout.addWidget(self.general_guides_edit, 1)

        self.strict_donts_label = QLabel("Strict Don'ts:")
        self.strict_donts_edit = QTextEdit(self)
        self.strict_donts_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.strict_donts_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.strict_donts_edit.setAcceptRichText(False)
        main_layout.addWidget(self.strict_donts_label)
        main_layout.addWidget(self.strict_donts_edit, 1)

        self.negative_prompt_label = QLabel("Negative Prompt:")
        self.negative_prompt_edit = QTextEdit(self)
        self.negative_prompt_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.negative_prompt_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.negative_prompt_edit.setAcceptRichText(False)
        main_layout.addWidget(self.negative_prompt_label)
        main_layout.addWidget(self.negative_prompt_edit, 1)

        placeholder_info = QLabel(
            "Prompt Placeholders:\n"
            "The prompts use the following placeholders, which will be replaced automatically when generating metadata:\n"
            "  • _MIN_LEN_: Minimum title length\n"
            "  • _MAX_LEN_: Maximum title length\n"
            "  • _MAX_DESC_LEN_: Maximum description length\n"
            "  • _TAGS_COUNT_: Required number of tags\n"
            "  • _TIMESTAMP_: Unique timestamp for each request\n"
            "  • _TOKEN_: Unique token for each request\n"
            "These placeholders ensure your prompts always match the current configuration and are always unique for every request."
        )
        placeholder_info.setWordWrap(True)
        main_layout.addWidget(placeholder_info)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.save_btn)
        main_layout.addLayout(btn_layout)

        self.config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        self.load_prompt()
        self.save_btn.clicked.connect(self.save_prompt)

    def load_prompt(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            prompt_data = data["prompt"]
            self.title_req_edit.setPlainText(prompt_data.get("title_requirements", ""))
            self.desc_req_edit.setPlainText(prompt_data.get("description_requirements", ""))
            self.keywords_req_edit.setPlainText(prompt_data.get("keywords_requirements", ""))
            self.general_guides_edit.setPlainText(prompt_data.get("general_guides", ""))
            self.strict_donts_edit.setPlainText(prompt_data.get("strict_donts", ""))
            self.negative_prompt_edit.setPlainText(prompt_data.get("negative_prompt", ""))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load prompt: {e}")

    def save_prompt(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "prompt" not in data:
                data["prompt"] = {}
            data["prompt"]["title_requirements"] = self.title_req_edit.toPlainText()
            data["prompt"]["description_requirements"] = self.desc_req_edit.toPlainText()
            data["prompt"]["keywords_requirements"] = self.keywords_req_edit.toPlainText()
            data["prompt"]["general_guides"] = self.general_guides_edit.toPlainText()
            data["prompt"]["strict_donts"] = self.strict_donts_edit.toPlainText()
            data["prompt"]["negative_prompt"] = self.negative_prompt_edit.toPlainText()
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save prompt: {e}")
