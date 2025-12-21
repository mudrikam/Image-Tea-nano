from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QSpinBox, QLineEdit,
                               QDialogButtonBox, QTabWidget, QWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import qtawesome as qta
import json
import os
from config import BASE_PATH


class EnvatoSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 350)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.config = config
        self.parent_window = parent
        
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        
        limits_tab = QWidget()
        limits_layout = QFormLayout(limits_tab)
        
        limits = self.config['limits']
        
        self.title_min_spin = QSpinBox()
        self.title_min_spin.setRange(1, 200)
        self.title_min_spin.setValue(limits['title_min'])
        limits_layout.addRow("Title Min Characters:", self.title_min_spin)
        
        self.title_max_spin = QSpinBox()
        self.title_max_spin.setRange(10, 200)
        self.title_max_spin.setValue(limits['title_max'])
        limits_layout.addRow("Title Max Characters:", self.title_max_spin)
        
        self.tagline_max_spin = QSpinBox()
        self.tagline_max_spin.setRange(10, 500)
        self.tagline_max_spin.setValue(limits['tagline_max'])
        limits_layout.addRow("Tagline Max Characters:", self.tagline_max_spin)
        
        self.tags_expected_spin = QSpinBox()
        self.tags_expected_spin.setRange(1, 50)
        self.tags_expected_spin.setValue(limits['tags_expected'])
        limits_layout.addRow("Expected Tags Count:", self.tags_expected_spin)
        
        self.features_expected_spin = QSpinBox()
        self.features_expected_spin.setRange(1, 20)
        self.features_expected_spin.setValue(limits['expected_features'])
        limits_layout.addRow("Expected Features Count:", self.features_expected_spin)
        
        tabs.addTab(limits_tab, qta.icon('fa6s.ruler'), "Field Limits")
        
        defaults_tab = QWidget()
        defaults_layout = QFormLayout(defaults_tab)
        
        defaults = self.config['defaults']
        
        self.default_items_spin = QSpinBox()
        self.default_items_spin.setRange(1, 100)
        self.default_items_spin.setValue(defaults['items_count'])
        defaults_layout.addRow("Default Items Count:", self.default_items_spin)
        
        self.default_dpi = QLineEdit(str(defaults['dpi']))
        defaults_layout.addRow("Default DPI:", self.default_dpi)
        
        self.default_width = QLineEdit(str(defaults['width']))
        defaults_layout.addRow("Default Width:", self.default_width)
        
        self.default_height = QLineEdit(str(defaults['height']))
        defaults_layout.addRow("Default Height:", self.default_height)
        
        tabs.addTab(defaults_tab, qta.icon('fa6s.gear'), "Default Values")
        
        layout.addWidget(tabs)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setIcon(qta.icon('fa6s.floppy-disk'))
        buttons.button(QDialogButtonBox.Cancel).setIcon(qta.icon('fa6s.xmark'))
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def save_settings(self):
        self.config['limits'] = {
            'title_min': self.title_min_spin.value(),
            'title_max': self.title_max_spin.value(),
            'tagline_max': self.tagline_max_spin.value(),
            'tags_expected': self.tags_expected_spin.value(),
            'expected_features': self.features_expected_spin.value()
        }
        
        self.config['defaults'] = {
            'items_count': self.default_items_spin.value(),
            'dpi': self.default_dpi.text(),
            'width': self.default_width.text(),
            'height': self.default_height.text()
        }
        
        config_path = os.path.join(BASE_PATH, 'configs', 'elements_mockup_metadata_generator_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
        
        if self.parent_window and hasattr(self.parent_window, 'update_field_counts'):
            self.parent_window.update_field_counts()
        
        self.accept()
