from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QListWidget, QListWidgetItem, QLineEdit,
                               QGridLayout, QColorDialog, QMessageBox, QWidget,
                               QScrollArea, QSizePolicy, QInputDialog)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QPixmap, QIcon
import qtawesome as qta
import json
import os


class ThemeEditorDialog(QDialog):
    theme_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Theme Editor")
        self.resize(640, 480)
        
        self.config_path = os.path.join('configs', 'app_themes.json')
        self.themes_data = self._load_themes()
        self.current_theme = None
        self.color_data = {}
        
        self._setup_ui()
        self._load_theme_list()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        
        left_panel = QVBoxLayout()
        
        title_icon = qta.icon('fa6s.palette')
        title_label = QLabel()
        title_label.setPixmap(title_icon.pixmap(24, 24))
        title_text = QLabel("Themes")
        title_text.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout = QHBoxLayout()
        title_layout.addWidget(title_label)
        title_layout.addWidget(title_text)
        title_layout.addStretch()
        left_panel.addLayout(title_layout)
        
        self.theme_list = QListWidget()
        self.theme_list.currentItemChanged.connect(self._on_theme_selected)
        left_panel.addWidget(self.theme_list)
        
        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton()
        self.new_btn.setIcon(qta.icon('fa6s.plus'))
        self.new_btn.setToolTip("Create New Theme")
        self.new_btn.clicked.connect(self._create_theme)
        
        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(qta.icon('fa6s.trash'))
        self.delete_btn.setToolTip("Delete Theme")
        self.delete_btn.clicked.connect(self._delete_theme)
        self.delete_btn.setEnabled(False)
        
        btn_layout.addWidget(self.new_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        left_panel.addLayout(btn_layout)
        
        layout.addLayout(left_panel, 1)
        
        right_panel = QVBoxLayout()
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Theme Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter theme name")
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_edit)

        self.edit_name_btn = QPushButton()
        self.edit_name_btn.setIcon(qta.icon('fa6s.pen'))
        self.edit_name_btn.setFixedSize(28, 28)
        self.edit_name_btn.setToolTip("Rename Theme")
        self.edit_name_btn.clicked.connect(self._rename_theme)
        self.edit_name_btn.setEnabled(False)
        name_layout.addWidget(self.edit_name_btn)

        right_panel.addLayout(name_layout)
        
        colors_label = QLabel("Colors:")
        colors_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        right_panel.addWidget(colors_label)
        
        colors_scroll_area = QScrollArea()
        colors_scroll_area.setWidgetResizable(True)
        colors_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.colors_container = QWidget()
        self.colors_layout = QGridLayout(self.colors_container)
        self.colors_layout.setSpacing(8)
        self.colors_layout.setContentsMargins(6, 6, 6, 6)
        colors_scroll_area.setWidget(self.colors_container)
        colors_scroll_area.setFixedHeight(340)
        right_panel.addWidget(colors_scroll_area)
        
        right_panel.addStretch()
        
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        self.save_btn.clicked.connect(self._save_theme)
        self.save_btn.setEnabled(False)
        save_layout.addWidget(self.save_btn)
        right_panel.addLayout(save_layout)
        
        layout.addLayout(right_panel, 2)
        
        self.name_edit.setEnabled(False)
    
    def _load_themes(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_themes(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.themes_data, f, indent=2)
        return True
    
    def _load_theme_list(self):
        self.theme_list.clear()
        for theme_id in self.themes_data['themes'].keys():
            theme_name = self.themes_data['themes'][theme_id]['name']
            item = QListWidgetItem(theme_name)
            item.setData(Qt.UserRole, theme_id)
            if theme_id == 'default':
                item.setIcon(qta.icon('fa6s.lock'))
            else:
                item.setIcon(qta.icon('fa6s.palette'))
            self.theme_list.addItem(item)
    
    def _on_theme_selected(self, current, previous):
        if not current:
            return
        
        theme_id = current.data(Qt.UserRole)
        self.current_theme = theme_id
        self._load_theme_colors(theme_id)
        
        is_default = theme_id == 'default'
        self.delete_btn.setEnabled(not is_default)
        self.name_edit.setEnabled(not is_default)
        self.edit_name_btn.setEnabled(not is_default)
        self.save_btn.setEnabled(True)
    
    def _clear_colors_layout(self):
        while self.colors_layout.count():
            item = self.colors_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.color_data.clear()
    
    def _load_theme_colors(self, theme_id):
        theme = self.themes_data['themes'][theme_id]
        self.name_edit.setText(theme['name'])
        
        self._clear_colors_layout()
        
        row = 0
        for color_key, color_value in theme['colors'].items():
            label = QLabel(color_key.replace('_', ' ').title() + ":")
            label.setFixedWidth(160)
            self.colors_layout.addWidget(label, row, 0, alignment=Qt.AlignVCenter)
            
            color_btn = QPushButton()
            pix = QPixmap(16, 16)
            pix.fill(QColor(color_value))
            color_btn.setIcon(QIcon(pix))
            color_btn.setIconSize(QSize(16, 16))
            color_btn.setFixedSize(28, 28)
            color_btn.setToolTip(color_value)
            color_btn.setProperty("color_key", color_key)
            color_btn.clicked.connect(self._on_color_button_clicked)
            self.colors_layout.addWidget(color_btn, row, 1, alignment=Qt.AlignVCenter)
            
            hex_label = QLabel(color_value)
            hex_label.setFixedWidth(96)
            r = int(color_value[1:3], 16)
            g = int(color_value[3:5], 16)
            b = int(color_value[5:7], 16)
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            text_color = '#000000' if luminance > 186 else '#ffffff'
            hex_label.setStyleSheet(f"background-color: {color_value}; color: {text_color}; padding: 4px; border: 1px solid #444; border-radius: 4px;")
            hex_label.setAlignment(Qt.AlignCenter)
            self.colors_layout.addWidget(hex_label, row, 2, alignment=Qt.AlignVCenter)
            
            self.color_data[color_key] = {
                'button': color_btn,
                'label': hex_label,
                'value': color_value
            }
            
            row += 1
    
    def _on_color_button_clicked(self):
        sender = self.sender()
        if not sender or not self.current_theme:
            return
        
        color_key = sender.property("color_key")
        if not color_key or color_key not in self.color_data:
            return
        
        current_hex = self.color_data[color_key]['value']
        new_color = QColorDialog.getColor(
            QColor(current_hex),
            self,
            f"Pick {color_key.replace('_', ' ').title()}",
            QColorDialog.DontUseNativeDialog
        )
        
        if new_color.isValid():
            hex_color = new_color.name()
            
            pix = QPixmap(16, 16)
            pix.fill(new_color)
            sender.setIcon(QIcon(pix))
            sender.setToolTip(hex_color)
            
            hex_label = self.color_data[color_key]['label']
            r = new_color.red()
            g = new_color.green()
            b = new_color.blue()
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            text_color = '#000000' if luminance > 186 else '#ffffff'
            hex_label.setText(hex_color)
            hex_label.setStyleSheet(f"background-color: {hex_color}; color: {text_color}; padding: 4px; border: 1px solid #444; border-radius: 4px;")
            
            self.color_data[color_key]['value'] = hex_color
            self.save_btn.setEnabled(True)
    
    def _on_name_changed(self, text):
        if self.current_theme and self.current_theme != 'default':
            self.save_btn.setEnabled(True)

    def _select_theme(self, theme_id):
        for i in range(self.theme_list.count()):
            item = self.theme_list.item(i)
            if item.data(Qt.UserRole) == theme_id:
                self.theme_list.setCurrentItem(item)
                break

    def _rename_theme(self):
        if not self.current_theme or self.current_theme == 'default':
            return
        current_name = self.themes_data['themes'][self.current_theme]['name']
        new_name, ok = QInputDialog.getText(self, "Rename Theme", "Enter new theme name:", text=current_name)
        if not ok or not new_name or not new_name.strip():
            return
        new_name = new_name.strip()
        new_id = new_name.lower().replace(' ', '_')
        if new_id == self.current_theme:
            # Only rename display name
            self.themes_data['themes'][self.current_theme]['name'] = new_name
            self._save_themes()
            self.name_edit.setText(new_name)
            QMessageBox.information(self, "Theme Renamed", f"Theme renamed to '{new_name}'")
            self._load_theme_list()
            self._select_theme(new_id)
            return
        if new_id in self.themes_data['themes']:
            QMessageBox.warning(self, "Warning", f"Theme '{new_name}' already exists")
            return
        # Move theme data to new key
        self.themes_data['themes'][new_id] = self.themes_data['themes'].pop(self.current_theme)
        self.themes_data['themes'][new_id]['name'] = new_name
        if self.themes_data.get('current_theme') == self.current_theme:
            self.themes_data['current_theme'] = new_id
        self._save_themes()
        QMessageBox.information(self, "Theme Renamed", f"Theme renamed to '{new_name}'")
        self._load_theme_list()
        self._select_theme(new_id)
    
    def _save_theme(self):
        if not self.current_theme:
            return
        
        theme_name = self.name_edit.text().strip()
        if not theme_name:
            print("Theme name cannot be empty")
            return
        
        colors = {}
        for color_key, data in self.color_data.items():
            colors[color_key] = data['value']
        
        self.themes_data['themes'][self.current_theme]['name'] = theme_name
        self.themes_data['themes'][self.current_theme]['colors'] = colors
        
        self._save_themes()
        QMessageBox.information(self, "Theme Saved", f"Theme '{theme_name}' saved successfully")
        self._load_theme_list()
        
        for i in range(self.theme_list.count()):
            item = self.theme_list.item(i)
            if item.data(Qt.UserRole) == self.current_theme:
                self.theme_list.setCurrentItem(item)
                break
        
        self.theme_changed.emit(self.current_theme)
    
    def _create_theme(self):
        theme_name, ok = QInputDialog.getText(self, "New Theme", "Enter theme name:")
        if not ok or not theme_name:
            return
        
        theme_id = theme_name.lower().replace(' ', '_')
        
        if theme_id in self.themes_data['themes']:
            QMessageBox.warning(self, "Warning", f"Theme '{theme_name}' already exists")
            return
        
        default_colors = self.themes_data['themes']['default']['colors'].copy()
        
        self.themes_data['themes'][theme_id] = {
            "name": theme_name,
            "colors": default_colors
        }
        
        self._save_themes()
        self._load_theme_list()
        
        for i in range(self.theme_list.count()):
            item = self.theme_list.item(i)
            if item.data(Qt.UserRole) == theme_id:
                self.theme_list.setCurrentItem(item)
                break
    
    def _delete_theme(self):
        if not self.current_theme or self.current_theme == 'default':
            return
        
        theme_name = self.themes_data['themes'][self.current_theme]['name']
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete theme '{theme_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.themes_data['current_theme'] == self.current_theme:
                self.themes_data['current_theme'] = 'default'
            
            del self.themes_data['themes'][self.current_theme]
            
            self._save_themes()
            QMessageBox.information(self, "Theme Deleted", f"Theme '{theme_name}' deleted")
            self.current_theme = None
            self._load_theme_list()
            self.name_edit.clear()
            self.name_edit.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self._clear_colors_layout()
            
            self.theme_changed.emit('default')
