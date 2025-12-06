import os
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel, 
    QTextEdit, QPushButton, QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextOption
import qtawesome as qta
from config import BASE_PATH


class PromptGeneratorConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Prompt Generator Configuration")
        self.resize(700, 700)
        
        self.config_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
        self.config_data = None
        self.prompt_gen_config = None
        
        self.load_configuration()
        self.setup_ui()
        self.load_values()
    
    def load_configuration(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            self.prompt_gen_config = self.config_data.get('prompt_generator', {})
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")
            self.prompt_gen_config = {}
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        title_label = QLabel("Prompt Generator Configuration")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        tab_widget = QTabWidget()
        
        instructions_tab = self.create_instructions_tab()
        requirements_tab = self.create_requirements_tab()
        variation_tab = self.create_variation_tab()
        
        tab_widget.addTab(instructions_tab, qta.icon('fa6s.pen-to-square'), "Instructions")
        tab_widget.addTab(requirements_tab, qta.icon('fa6s.list-ul'), "Requirements")
        tab_widget.addTab(variation_tab, qta.icon('fa6s.sliders'), "Variation Levels")
        
        main_layout.addWidget(tab_widget)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_button = QPushButton(qta.icon('fa6s.floppy-disk'), "Save")
        save_button.clicked.connect(self.save_configuration)
        
        cancel_button = QPushButton(qta.icon('fa6s.xmark'), "Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        main_layout.addLayout(button_layout)
    
    def create_instructions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        info_label = QLabel("Edit instructions for each prompt generation type:")
        layout.addWidget(info_label)
        
        image_gen_group = QGroupBox("Image Generation Instruction")
        image_gen_layout = QVBoxLayout(image_gen_group)
        
        self.image_instruction_edit = QTextEdit()
        self.image_instruction_edit.setMinimumHeight(150)
        image_gen_layout.addWidget(self.image_instruction_edit)
        
        layout.addWidget(image_gen_group)
        
        video_gen_group = QGroupBox("Video Generation Instruction")
        video_gen_layout = QVBoxLayout(video_gen_group)
        
        self.video_instruction_edit = QTextEdit()
        self.video_instruction_edit.setMinimumHeight(150)
        video_gen_layout.addWidget(self.video_instruction_edit)
        
        layout.addWidget(video_gen_group)
        
        return tab
    
    def create_requirements_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        info_label = QLabel("Edit requirements for each prompt generation type:")
        layout.addWidget(info_label)
        
        image_req_group = QGroupBox("Image Generation Requirements")
        image_req_layout = QVBoxLayout(image_req_group)
        
        self.image_req_list = QListWidget()
        self.image_req_list.setMinimumHeight(150)
        image_req_layout.addWidget(self.image_req_list)
        
        image_btn_layout = QHBoxLayout()
        
        add_image_req_btn = QPushButton(qta.icon('fa6s.plus'), "Add")
        add_image_req_btn.clicked.connect(lambda: self.add_requirement('image'))
        
        edit_image_req_btn = QPushButton(qta.icon('fa6s.pen-to-square'), "Edit")
        edit_image_req_btn.clicked.connect(lambda: self.edit_requirement('image'))
        
        remove_image_req_btn = QPushButton(qta.icon('fa6s.trash-can'), "Remove")
        remove_image_req_btn.clicked.connect(lambda: self.remove_requirement('image'))
        
        image_btn_layout.addWidget(add_image_req_btn)
        image_btn_layout.addWidget(edit_image_req_btn)
        image_btn_layout.addWidget(remove_image_req_btn)
        image_btn_layout.addStretch()
        
        image_req_layout.addLayout(image_btn_layout)
        layout.addWidget(image_req_group)
        
        video_req_group = QGroupBox("Video Generation Requirements")
        video_req_layout = QVBoxLayout(video_req_group)
        
        self.video_req_list = QListWidget()
        self.video_req_list.setMinimumHeight(150)
        video_req_layout.addWidget(self.video_req_list)
        
        video_btn_layout = QHBoxLayout()
        
        add_video_req_btn = QPushButton(qta.icon('fa6s.plus'), "Add")
        add_video_req_btn.clicked.connect(lambda: self.add_requirement('video'))
        
        edit_video_req_btn = QPushButton(qta.icon('fa6s.pen-to-square'), "Edit")
        edit_video_req_btn.clicked.connect(lambda: self.edit_requirement('video'))
        
        remove_video_req_btn = QPushButton(qta.icon('fa6s.trash-can'), "Remove")
        remove_video_req_btn.clicked.connect(lambda: self.remove_requirement('video'))
        
        video_btn_layout.addWidget(add_video_req_btn)
        video_btn_layout.addWidget(edit_video_req_btn)
        video_btn_layout.addWidget(remove_video_req_btn)
        video_btn_layout.addStretch()
        
        video_req_layout.addLayout(video_btn_layout)
        layout.addWidget(video_req_group)
        
        return tab
    
    def create_variation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        info_label = QLabel("Edit variation level descriptions:")
        layout.addWidget(info_label)
        
        variation_group = QGroupBox("Variation Levels")
        variation_layout = QVBoxLayout(variation_group)
        
        self.variation_list = QListWidget()
        self.variation_list.setMinimumHeight(400)
        variation_layout.addWidget(self.variation_list)
        
        btn_layout = QHBoxLayout()
        
        edit_btn = QPushButton(qta.icon('fa6s.pen-to-square'), "Edit Selected Level")
        edit_btn.clicked.connect(self.edit_variation_level)
        
        btn_layout.addWidget(edit_btn)
        btn_layout.addStretch()
        
        variation_layout.addLayout(btn_layout)
        layout.addWidget(variation_group)
        
        return tab
    
    def load_values(self):
        instructions = self.prompt_gen_config.get('instructions', {})
        self.image_instruction_edit.setPlainText(instructions.get('image_generation', ''))
        self.video_instruction_edit.setPlainText(instructions.get('video_generation', ''))
        
        requirements = self.prompt_gen_config.get('requirements', {})
        image_reqs = requirements.get('image_generation', [])
        video_reqs = requirements.get('video_generation', [])
        
        for req in image_reqs:
            item = QListWidgetItem(req)
            self.image_req_list.addItem(item)
        
        for req in video_reqs:
            item = QListWidgetItem(req)
            self.video_req_list.addItem(item)
        
        # Load variation levels
        variation_levels = self.prompt_gen_config.get('variation_levels', {})
        for level in range(1, 11):
            level_str = str(level)
            description = variation_levels.get(level_str, '')
            display_text = f"Level {level}: {description[:50]}{'...' if len(description) > 50 else ''}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, level_str)
            self.variation_list.addItem(item)
    
    def add_requirement(self, req_type):
        dialog = RequirementEditDialog("Add Requirement", "Enter requirement text:", "", self)
        if dialog.exec() == QDialog.Accepted:
            text = dialog.get_text()
            if text.strip():
                if req_type == 'image':
                    item = QListWidgetItem(text.strip())
                    self.image_req_list.addItem(item)
                else:
                    item = QListWidgetItem(text.strip())
                    self.video_req_list.addItem(item)
    
    def edit_requirement(self, req_type):
        list_widget = self.image_req_list if req_type == 'image' else self.video_req_list
        current_item = list_widget.currentItem()
        
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a requirement to edit.")
            return
        
        dialog = RequirementEditDialog("Edit Requirement", "Edit requirement text:", current_item.text(), self)
        if dialog.exec() == QDialog.Accepted:
            text = dialog.get_text()
            if text.strip():
                current_item.setText(text.strip())
    
    def remove_requirement(self, req_type):
        list_widget = self.image_req_list if req_type == 'image' else self.video_req_list
        current_item = list_widget.currentItem()
        
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a requirement to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this requirement?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            list_widget.takeItem(list_widget.row(current_item))
    
    def edit_variation_level(self):
        current_item = self.variation_list.currentItem()
        
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a variation level to edit.")
            return
        
        level_str = current_item.data(Qt.UserRole)
        current_description = self.prompt_gen_config.get('variation_levels', {}).get(level_str, '')
        
        dialog = RequirementEditDialog(f"Edit Variation Level {level_str}", 
                                     f"Edit description for Level {level_str}:", 
                                     current_description, self)
        if dialog.exec() == QDialog.Accepted:
            new_description = dialog.get_text()
            if new_description.strip():
                # Update config
                if 'variation_levels' not in self.prompt_gen_config:
                    self.prompt_gen_config['variation_levels'] = {}
                self.prompt_gen_config['variation_levels'][level_str] = new_description.strip()
                
                # Update display
                display_text = f"Level {level_str}: {new_description.strip()[:50]}{'...' if len(new_description.strip()) > 50 else ''}"
                current_item.setText(display_text)
    
    def save_configuration(self):
        try:
            instructions = {
                'image_generation': self.image_instruction_edit.toPlainText(),
                'video_generation': self.video_instruction_edit.toPlainText()
            }
            
            image_reqs = []
            for i in range(self.image_req_list.count()):
                image_reqs.append(self.image_req_list.item(i).text())
            
            video_reqs = []
            for i in range(self.video_req_list.count()):
                video_reqs.append(self.video_req_list.item(i).text())
            
            requirements = {
                'image_generation': image_reqs,
                'video_generation': video_reqs
            }
            
            self.prompt_gen_config['instructions'] = instructions
            self.prompt_gen_config['requirements'] = requirements
            # variation_levels are already updated in the config when edited
            
            self.config_data['prompt_generator'] = self.prompt_gen_config
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            
            QMessageBox.information(self, "Success", "Configuration saved successfully!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")


class RequirementEditDialog(QDialog):
    def __init__(self, title, label_text, initial_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 300)
        
        layout = QVBoxLayout(self)
        
        # Label
        label = QLabel(label_text)
        layout.addWidget(label)
        
        # Text edit with word wrap
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(initial_text)
        self.text_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_edit.setMinimumHeight(100)
        layout.addWidget(self.text_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Set focus to text edit
        self.text_edit.setFocus()
    
    def get_text(self):
        return self.text_edit.toPlainText()
