from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel, QMessageBox, QWidget, QGridLayout, QTabWidget, QFileDialog, QComboBox, QInputDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption, QPixmap, QPainter, QColor, QIcon
import qtawesome as qta
import os
import sys
import json
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_PATH

class EditPromptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Prompt")
        self.setFixedSize(600, 700)
        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        def _fa_icon(name, rgb_tuple, alpha_f=1.0):
            r, g, b = rgb_tuple
            color = QColor(r, g, b)
            color.setAlphaF(alpha_f)
            return qta.icon(name, color=color)

        title_tab = QWidget()
        title_layout = QVBoxLayout(title_tab)
        self.title_req_label = QLabel("Title Requirements:")
        self.title_req_edit = QTextEdit(self)
        self.title_req_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.title_req_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.title_req_edit.setAcceptRichText(False)
        title_layout.addWidget(self.title_req_label)
        title_layout.addWidget(self.title_req_edit)
        self.tab_widget.addTab(title_tab, _fa_icon("fa6s.pen", (230, 35, 55), alpha_f=1.0), "Title")

        desc_tab = QWidget()
        desc_layout = QVBoxLayout(desc_tab)
        self.desc_req_label = QLabel("Description Requirements:")
        self.desc_req_edit = QTextEdit(self)
        self.desc_req_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.desc_req_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.desc_req_edit.setAcceptRichText(False)
        desc_layout.addWidget(self.desc_req_label)
        desc_layout.addWidget(self.desc_req_edit)
        self.tab_widget.addTab(desc_tab, _fa_icon("fa6s.file-lines", (155, 89, 182), alpha_f=1.0), "Description")

        keywords_tab = QWidget()
        keywords_layout = QVBoxLayout(keywords_tab)
        self.keywords_req_label = QLabel("Keywords Requirements:")
        self.keywords_req_edit = QTextEdit(self)
        self.keywords_req_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.keywords_req_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.keywords_req_edit.setAcceptRichText(False)
        keywords_layout.addWidget(self.keywords_req_label)
        keywords_layout.addWidget(self.keywords_req_edit)
        self.tab_widget.addTab(keywords_tab, _fa_icon("fa6s.tags", (46, 204, 113), alpha_f=1.0), "Keywords")

        guides_tab = QWidget()
        guides_layout = QVBoxLayout(guides_tab)
        self.general_guides_label = QLabel("General Guides:")
        self.general_guides_edit = QTextEdit(self)
        self.general_guides_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.general_guides_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.general_guides_edit.setAcceptRichText(False)
        guides_layout.addWidget(self.general_guides_label)
        guides_layout.addWidget(self.general_guides_edit)
        self.tab_widget.addTab(guides_tab, _fa_icon("fa6s.book-open", (52, 152, 219), alpha_f=1.0), "General Guides")

        donts_tab = QWidget()
        donts_layout = QVBoxLayout(donts_tab)
        self.strict_donts_label = QLabel("Strict Don'ts:")
        self.strict_donts_edit = QTextEdit(self)
        self.strict_donts_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.strict_donts_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.strict_donts_edit.setAcceptRichText(False)
        donts_layout.addWidget(self.strict_donts_label)
        donts_layout.addWidget(self.strict_donts_edit)
        self.tab_widget.addTab(donts_tab, _fa_icon("fa6s.ban", (243, 156, 18), alpha_f=1.0), "Strict Don'ts")

        negative_tab = QWidget()
        negative_layout = QVBoxLayout(negative_tab)
        self.negative_prompt_label = QLabel("Negative Prompt:")
        self.negative_prompt_edit = QTextEdit(self)
        self.negative_prompt_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.negative_prompt_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.negative_prompt_edit.setAcceptRichText(False)
        negative_layout.addWidget(self.negative_prompt_label)
        negative_layout.addWidget(self.negative_prompt_edit)
        self.tab_widget.addTab(negative_tab, _fa_icon("fa6s.xmark", (142, 68, 173), alpha_f=1.0), "Negative Prompt")

        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        self.custom_prompt_label = QLabel("Custom Prompt:")
        self.custom_prompt_edit = QTextEdit(self)
        self.custom_prompt_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.custom_prompt_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.custom_prompt_edit.setAcceptRichText(False)
        custom_layout.addWidget(self.custom_prompt_label)
        custom_layout.addWidget(self.custom_prompt_edit)
        self.tab_widget.addTab(custom_tab, _fa_icon("fa6s.comment", (231, 76, 60), alpha_f=1.0), "Custom Prompt")

        main_layout.addWidget(self.tab_widget)

        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox(self)
        self.preset_combo.currentIndexChanged.connect(self.load_selected_preset)
        preset_layout.addWidget(self.preset_combo, 1)
        
        self.add_preset_btn = QPushButton()
        self.add_preset_btn.setIcon(qta.icon("fa6s.plus"))
        self.add_preset_btn.setToolTip("Add New Preset")
        self.add_preset_btn.clicked.connect(self.add_preset)
        preset_layout.addWidget(self.add_preset_btn)
        
        self.delete_preset_btn = QPushButton()
        self.delete_preset_btn.setIcon(qta.icon("fa6s.trash"))
        self.delete_preset_btn.setToolTip("Delete Preset")
        self.delete_preset_btn.clicked.connect(self.delete_preset)
        preset_layout.addWidget(self.delete_preset_btn)
        
        self.rename_preset_btn = QPushButton()
        self.rename_preset_btn.setIcon(qta.icon("fa6s.pen-to-square"))
        self.rename_preset_btn.setToolTip("Rename Preset")
        self.rename_preset_btn.clicked.connect(self.rename_preset)
        preset_layout.addWidget(self.rename_preset_btn)
        
        self.duplicate_preset_btn = QPushButton()
        self.duplicate_preset_btn.setIcon(qta.icon("fa6s.copy"))
        self.duplicate_preset_btn.setToolTip("Duplicate Preset")
        self.duplicate_preset_btn.clicked.connect(self.duplicate_preset)
        preset_layout.addWidget(self.duplicate_preset_btn)
        
        main_layout.addLayout(preset_layout)

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
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setIcon(qta.icon("fa6s.xmark"))
        self.cancel_btn.clicked.connect(self.reject)

        self.import_btn = QPushButton("Import")
        self.import_btn.setIcon(qta.icon("fa6s.file-import"))
        self.import_btn.clicked.connect(self.import_prompt)

        self.export_btn = QPushButton("Export")
        self.export_btn.setIcon(qta.icon("fa6s.file-export"))
        self.export_btn.clicked.connect(self.export_prompt)

        self.save_btn = QPushButton("Save")
        self.save_btn.setIcon(qta.icon("fa6s.floppy-disk"))

        btn_layout.addStretch(1)
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        main_layout.addLayout(btn_layout)

        self.config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        self.load_presets()
        self.save_btn.clicked.connect(self.save_prompt)

    def load_presets(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
            
            if "prompt_presets" not in self.config_data:
                self.config_data["prompt_presets"] = [{
                    "name": "Default",
                    "title_requirements": self.config_data["prompt"].get("title_requirements", ""),
                    "description_requirements": self.config_data["prompt"].get("description_requirements", ""),
                    "keywords_requirements": self.config_data["prompt"].get("keywords_requirements", ""),
                    "general_guides": self.config_data["prompt"].get("general_guides", ""),
                    "strict_donts": self.config_data["prompt"].get("strict_donts", ""),
                    "negative_prompt": self.config_data["prompt"].get("negative_prompt", ""),
                    "custom_prompt": self.config_data["prompt"].get("custom_prompt", "")
                }]
            
            self.preset_combo.clear()
            for preset in self.config_data["prompt_presets"]:
                self.preset_combo.addItem(preset["name"])
            
            self.load_prompt_from_main()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load presets: {e}")

    def load_prompt_from_main(self):
        try:
            prompt_data = self.config_data["prompt"]
            self.title_req_edit.setPlainText(prompt_data.get("title_requirements", ""))
            self.desc_req_edit.setPlainText(prompt_data.get("description_requirements", ""))
            self.keywords_req_edit.setPlainText(prompt_data.get("keywords_requirements", ""))
            self.general_guides_edit.setPlainText(prompt_data.get("general_guides", ""))
            self.strict_donts_edit.setPlainText(prompt_data.get("strict_donts", ""))
            self.negative_prompt_edit.setPlainText(prompt_data.get("negative_prompt", ""))
            self.custom_prompt_edit.setPlainText(prompt_data.get("custom_prompt", ""))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load prompt: {e}")

    def load_selected_preset(self):
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            return
        
        for preset in self.config_data.get("prompt_presets", []):
            if preset["name"] == preset_name:
                self.title_req_edit.setPlainText(preset.get("title_requirements", ""))
                self.desc_req_edit.setPlainText(preset.get("description_requirements", ""))
                self.keywords_req_edit.setPlainText(preset.get("keywords_requirements", ""))
                self.general_guides_edit.setPlainText(preset.get("general_guides", ""))
                self.strict_donts_edit.setPlainText(preset.get("strict_donts", ""))
                self.negative_prompt_edit.setPlainText(preset.get("negative_prompt", ""))
                self.custom_prompt_edit.setPlainText(preset.get("custom_prompt", ""))
                break

    def save_prompt(self):
        try:
            preset_name = self.preset_combo.currentText()
            if not preset_name:
                QMessageBox.warning(self, "Error", "No preset selected")
                return
            
            for preset in self.config_data.get("prompt_presets", []):
                if preset["name"] == preset_name:
                    preset["title_requirements"] = self.title_req_edit.toPlainText()
                    preset["description_requirements"] = self.desc_req_edit.toPlainText()
                    preset["keywords_requirements"] = self.keywords_req_edit.toPlainText()
                    preset["general_guides"] = self.general_guides_edit.toPlainText()
                    preset["strict_donts"] = self.strict_donts_edit.toPlainText()
                    preset["negative_prompt"] = self.negative_prompt_edit.toPlainText()
                    preset["custom_prompt"] = self.custom_prompt_edit.toPlainText()
                    break
            
            self.config_data["prompt"]["title_requirements"] = self.title_req_edit.toPlainText()
            self.config_data["prompt"]["description_requirements"] = self.desc_req_edit.toPlainText()
            self.config_data["prompt"]["keywords_requirements"] = self.keywords_req_edit.toPlainText()
            self.config_data["prompt"]["general_guides"] = self.general_guides_edit.toPlainText()
            self.config_data["prompt"]["strict_donts"] = self.strict_donts_edit.toPlainText()
            self.config_data["prompt"]["negative_prompt"] = self.negative_prompt_edit.toPlainText()
            self.config_data["prompt"]["custom_prompt"] = self.custom_prompt_edit.toPlainText()
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save prompt: {e}")

    def add_preset(self):
        text, ok = QInputDialog.getText(self, "Add Preset", "Enter preset name:")
        if ok and text:
            for preset in self.config_data.get("prompt_presets", []):
                if preset["name"] == text:
                    QMessageBox.warning(self, "Error", "Preset name already exists")
                    return
            
            new_preset = {
                "name": text,
                "title_requirements": self.title_req_edit.toPlainText(),
                "description_requirements": self.desc_req_edit.toPlainText(),
                "keywords_requirements": self.keywords_req_edit.toPlainText(),
                "general_guides": self.general_guides_edit.toPlainText(),
                "strict_donts": self.strict_donts_edit.toPlainText(),
                "negative_prompt": self.negative_prompt_edit.toPlainText(),
                "custom_prompt": self.custom_prompt_edit.toPlainText()
            }
            self.config_data["prompt_presets"].append(new_preset)
            
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save preset: {e}")
                return
            
            self.preset_combo.addItem(text)
            self.preset_combo.setCurrentText(text)
            
            self.title_req_edit.clear()
            self.desc_req_edit.clear()
            self.keywords_req_edit.clear()
            self.general_guides_edit.clear()
            self.strict_donts_edit.clear()
            self.negative_prompt_edit.clear()
            self.custom_prompt_edit.clear()

    def delete_preset(self):
        preset_name = self.preset_combo.currentText()
        if preset_name == "Default":
            QMessageBox.warning(self, "Error", "Cannot delete Default preset")
            return
        
        reply = QMessageBox.question(self, "Delete Preset", 
                                    f"Are you sure you want to delete preset '{preset_name}'?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_data["prompt_presets"] = [p for p in self.config_data["prompt_presets"] if p["name"] != preset_name]
            self.preset_combo.removeItem(self.preset_combo.currentIndex())

    def rename_preset(self):
        preset_name = self.preset_combo.currentText()
        if preset_name == "Default":
            QMessageBox.warning(self, "Error", "Cannot rename Default preset")
            return
        
        text, ok = QInputDialog.getText(self, "Rename Preset", "Enter new preset name:", text=preset_name)
        if ok and text:
            for preset in self.config_data.get("prompt_presets", []):
                if preset["name"] == text:
                    QMessageBox.warning(self, "Error", "Preset name already exists")
                    return
            
            for preset in self.config_data.get("prompt_presets", []):
                if preset["name"] == preset_name:
                    preset["name"] = text
                    break
            
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save preset: {e}")
                return
            
            current_index = self.preset_combo.currentIndex()
            self.preset_combo.setItemText(current_index, text)

    def duplicate_preset(self):
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            return
        
        new_name = preset_name + "_copy"
        counter = 1
        while any(p["name"] == new_name for p in self.config_data.get("prompt_presets", [])):
            new_name = f"{preset_name}_copy{counter}"
            counter += 1
        
        for preset in self.config_data.get("prompt_presets", []):
            if preset["name"] == preset_name:
                new_preset = {
                    "name": new_name,
                    "title_requirements": preset.get("title_requirements", ""),
                    "description_requirements": preset.get("description_requirements", ""),
                    "keywords_requirements": preset.get("keywords_requirements", ""),
                    "general_guides": preset.get("general_guides", ""),
                    "strict_donts": preset.get("strict_donts", ""),
                    "negative_prompt": preset.get("negative_prompt", ""),
                    "custom_prompt": preset.get("custom_prompt", "")
                }
                self.config_data["prompt_presets"].append(new_preset)
                
                try:
                    with open(self.config_path, "w", encoding="utf-8") as f:
                        json.dump(self.config_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to save duplicated preset: {e}")
                    return
                
                self.preset_combo.addItem(new_name)
                self.preset_combo.setCurrentText(new_name)
                break

    def export_prompt(self):
        try:
            data = {
                "prompt": {
                    "title_requirements": self.title_req_edit.toPlainText(),
                    "description_requirements": self.desc_req_edit.toPlainText(),
                    "keywords_requirements": self.keywords_req_edit.toPlainText(),
                    "general_guides": self.general_guides_edit.toPlainText(),
                    "strict_donts": self.strict_donts_edit.toPlainText(),
                    "negative_prompt": self.negative_prompt_edit.toPlainText(),
                    "custom_prompt": self.custom_prompt_edit.toPlainText(),
                }
            }
            default_name = f"Image_Tea_Prompt_Backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            start_path = os.path.join(os.path.expanduser("~"), default_name)
            path, _ = QFileDialog.getSaveFileName(self, "Export Prompt Backup", start_path, "JSON files (*.json)")
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Exported", f"Prompt exported to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to export prompt: {e}")

    def import_prompt(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Import Prompt Backup", os.path.expanduser("~"), "JSON files (*.json)")
            if not path:
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "prompt" not in data or not isinstance(data["prompt"], dict):
                QMessageBox.warning(self, "Invalid File", "Selected file does not contain a valid prompt backup.")
                return
            prompt_data = data["prompt"]
            self.title_req_edit.setPlainText(prompt_data.get("title_requirements", ""))
            self.desc_req_edit.setPlainText(prompt_data.get("description_requirements", ""))
            self.keywords_req_edit.setPlainText(prompt_data.get("keywords_requirements", ""))
            self.general_guides_edit.setPlainText(prompt_data.get("general_guides", ""))
            self.strict_donts_edit.setPlainText(prompt_data.get("strict_donts", ""))
            self.negative_prompt_edit.setPlainText(prompt_data.get("negative_prompt", ""))
            self.custom_prompt_edit.setPlainText(prompt_data.get("custom_prompt", ""))
            QMessageBox.information(self, "Imported", "Prompt values loaded into editor. Click Save to persist changes to the application configuration.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to import prompt: {e}")
