from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, 
    QLineEdit, QLabel, QMessageBox, QListWidgetItem
)
from PySide6.QtCore import Qt
import qtawesome as qta
import json
import os
from config import BASE_PATH


class ImagenConfigDialog(QDialog):
    """Dialog to manage Imagen Generator configuration"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Imagen Generator Configuration")
        self.setFixedSize(500, 400)
        
        self.config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        self.config = self.load_config()
        
        self.setup_ui()
        self.load_models()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Label
        label = QLabel("Imagen Models:")
        main_layout.addWidget(label)
        
        # List widget untuk menampilkan models
        self.model_list = QListWidget()
        self.model_list.setSelectionMode(QListWidget.SingleSelection)
        main_layout.addWidget(self.model_list)
        
        # Input untuk model baru/edit
        input_layout = QHBoxLayout()
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Enter model name (e.g., imagen-4.0-generate-001)")
        input_layout.addWidget(self.model_input)
        main_layout.addLayout(input_layout)
        
        # Buttons untuk mengelola models
        buttons_layout = QHBoxLayout()
        
        self.add_btn = QPushButton(qta.icon('fa6s.plus'), " Add")
        self.add_btn.setToolTip("Add new model")
        self.add_btn.clicked.connect(self.add_model)
        buttons_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton(qta.icon('fa6s.pen-to-square'), " Edit")
        self.edit_btn.setToolTip("Edit selected model")
        self.edit_btn.clicked.connect(self.edit_model)
        self.edit_btn.setEnabled(False)
        buttons_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton(qta.icon('fa6s.trash'), " Delete")
        self.delete_btn.setToolTip("Delete selected model")
        self.delete_btn.clicked.connect(self.delete_model)
        self.delete_btn.setEnabled(False)
        buttons_layout.addWidget(self.delete_btn)
        
        buttons_layout.addStretch()
        main_layout.addLayout(buttons_layout)
        
        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.save_btn = QPushButton(qta.icon('fa6s.floppy-disk'), " Save")
        self.save_btn.setToolTip("Save configuration")
        self.save_btn.clicked.connect(self.save_config)
        bottom_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
        self.cancel_btn.setToolTip("Cancel and close")
        self.cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(bottom_layout)
        
        # Connect selection changed
        self.model_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.model_list.itemDoubleClicked.connect(self.on_item_double_clicked)
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"[ImagenConfigDialog] Config file not found: {self.config_path}")
                return {}
        except Exception as e:
            print(f"[ImagenConfigDialog] Error loading config: {e}")
            return {}
    
    def load_models(self):
        """Load models from config to list widget"""
        self.model_list.clear()
        models = self.config.get('imagen_generator', {}).get('models', [])
        for model in models:
            self.model_list.addItem(model)
    
    def on_selection_changed(self):
        """Handle selection change in list"""
        has_selection = len(self.model_list.selectedItems()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        
        if has_selection:
            selected_item = self.model_list.selectedItems()[0]
            self.model_input.setText(selected_item.text())
    
    def on_item_double_clicked(self, item):
        """Handle double click on item to edit"""
        self.model_input.setText(item.text())
        self.model_input.setFocus()
        self.model_input.selectAll()
    
    def add_model(self):
        """Add new model to list"""
        model_name = self.model_input.text().strip()
        if not model_name:
            QMessageBox.warning(self, "Empty Input", "Please enter a model name first.")
            return
        
        # Check for duplicates
        existing_models = [self.model_list.item(i).text() for i in range(self.model_list.count())]
        if model_name in existing_models:
            QMessageBox.warning(self, "Duplicate Model", "Model already exists in the list.")
            return
        
        self.model_list.addItem(model_name)
        self.model_input.clear()
        print(f"[ImagenConfigDialog] Model added: {model_name}")
    
    def edit_model(self):
        """Edit selected model"""
        selected_items = self.model_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a model to edit.")
            return
        
        model_name = self.model_input.text().strip()
        if not model_name:
            QMessageBox.warning(self, "Empty Input", "Please enter the new model name first.")
            return
        
        # Check for duplicates (excluding current item)
        current_item = selected_items[0]
        existing_models = [self.model_list.item(i).text() for i in range(self.model_list.count())
                          if self.model_list.item(i) != current_item]
        if model_name in existing_models:
            QMessageBox.warning(self, "Duplicate Model", "Model already exists in the list.")
            return
        
        current_item.setText(model_name)
        self.model_input.clear()
        print(f"[ImagenConfigDialog] Model updated to: {model_name}")
    
    def delete_model(self):
        """Delete selected model"""
        selected_items = self.model_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a model to delete.")
            return
        
        model_name = selected_items[0].text()
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the model '{model_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            row = self.model_list.row(selected_items[0])
            self.model_list.takeItem(row)
            self.model_input.clear()
            print(f"[ImagenConfigDialog] Model deleted: {model_name}")
    
    def save_config(self):
        """Save models back to configuration file"""
        if self.model_list.count() == 0:
            QMessageBox.warning(self, "Empty List", "Please add at least one model before saving.")
            return
        
        try:
            # Get all models from list
            models = [self.model_list.item(i).text() for i in range(self.model_list.count())]
            
            # Update config
            if 'imagen_generator' not in self.config:
                self.config['imagen_generator'] = {}
            
            self.config['imagen_generator']['models'] = models
            
            # Save to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            print(f"[ImagenConfigDialog] Configuration saved with {len(models)} models")
            QMessageBox.information(self, "Success", "Configuration saved successfully.")
            self.accept()
            
        except Exception as e:
            print(f"[ImagenConfigDialog] Error saving config: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")
