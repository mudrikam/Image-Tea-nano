import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QLineEdit, QMessageBox, QColorDialog, QTextEdit, QComboBox, QSpinBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QColor, QFont
from config import BASE_PATH
import qtawesome as qta
from database.db_operation import ImageTeaDB
from dialogs.tools.icon_picker_dialog import IconPickerDialog


class AddActionDialog(QDialog):
    action_saved = Signal()
    
    def __init__(self, action_set_id, action_data=None, parent=None):
        super().__init__(parent)
        self.action_set_id = action_set_id
        self.action_data = action_data
        self.db = ImageTeaDB()
        self.selected_color = "#888888"
        
        if action_data:
            self.setWindowTitle("Edit Action")
            self.selected_color = action_data.get('color', '#888888')
        else:
            self.setWindowTitle("Add Action")
        
        self.setModal(True)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        
        if action_data:
            self.load_data()
        else:
            self.on_type_changed(0)
        
        self.setFixedWidth(450)
        self.resize(450, 250)
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        dialog_icon = qta.icon('fa6s.bolt', color='#E67E22')
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel("Edit Action" if self.action_data else "Add New Action")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        type_layout = QHBoxLayout()
        type_layout.setSpacing(6)
        type_icon_label = QLabel()
        type_icon_label.setPixmap(qta.icon('fa6s.list', color='#888').pixmap(16, 16))
        type_layout.addWidget(type_icon_label)
        type_label = QLabel("Type:")
        type_label.setMinimumWidth(70)
        type_layout.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Action", "Delay", "Script", "Export"])
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.type_combo, 1)
        layout.addLayout(type_layout)
        
        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)
        name_icon_label = QLabel()
        name_icon_label.setPixmap(qta.icon('fa6s.signature', color='#888').pixmap(16, 16))
        name_layout.addWidget(name_icon_label)
        name_label = QLabel("Name:")
        name_label.setMinimumWidth(70)
        name_layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Resize 300 DPI, Convert Smart Object")
        name_layout.addWidget(self.name_input, 1)
        layout.addLayout(name_layout)
        
        icon_row_layout = QHBoxLayout()
        icon_row_layout.setSpacing(6)
        icon_icon_label = QLabel()
        icon_icon_label.setPixmap(qta.icon('fa6s.icons', color='#888').pixmap(16, 16))
        icon_row_layout.addWidget(icon_icon_label)
        icon_text_label = QLabel("Icon:")
        icon_text_label.setMinimumWidth(70)
        icon_row_layout.addWidget(icon_text_label)
        
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(28, 28)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        icon_row_layout.addWidget(self.icon_preview)
        
        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText("e.g., expand, image")
        self.icon_input.textChanged.connect(self.update_icon_preview)
        icon_row_layout.addWidget(self.icon_input, 1)
        
        self.icon_picker_button = QPushButton(qta.icon('fa6s.magnifying-glass'), "")
        self.icon_picker_button.setMaximumWidth(32)
        self.icon_picker_button.clicked.connect(self.show_icon_picker)
        icon_row_layout.addWidget(self.icon_picker_button)
        
        layout.addLayout(icon_row_layout)
        
        color_layout = QHBoxLayout()
        color_layout.setSpacing(6)
        color_icon_label = QLabel()
        color_icon_label.setPixmap(qta.icon('fa6s.palette', color='#888').pixmap(16, 16))
        color_layout.addWidget(color_icon_label)
        color_text_label = QLabel("Color:")
        color_text_label.setMinimumWidth(70)
        color_layout.addWidget(color_text_label)
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(28, 28)
        self.update_color_preview()
        color_layout.addWidget(self.color_preview)
        
        self.color_input = QLineEdit()
        self.color_input.setText(self.selected_color)
        self.color_input.setPlaceholderText("#888888")
        self.color_input.textChanged.connect(self.on_color_input_changed)
        color_layout.addWidget(self.color_input, 1)
        
        self.color_picker_button = QPushButton(qta.icon('fa6s.eye-dropper'), "")
        self.color_picker_button.setMaximumWidth(32)
        self.color_picker_button.clicked.connect(self.pick_color)
        color_layout.addWidget(self.color_picker_button)
        
        layout.addLayout(color_layout)
        
        delay_layout = QHBoxLayout()
        delay_layout.setSpacing(6)
        delay_icon_label = QLabel()
        delay_icon_label.setPixmap(qta.icon('fa6s.clock', color='#888').pixmap(16, 16))
        delay_layout.addWidget(delay_icon_label)
        delay_label = QLabel("Delay (ms):")
        delay_label.setMinimumWidth(70)
        delay_layout.addWidget(delay_label)
        self.delay_input = QSpinBox()
        self.delay_input.setRange(0, 60000)
        self.delay_input.setValue(0)
        self.delay_input.setSuffix(" ms")
        self.delay_input.setEnabled(False)
        delay_layout.addWidget(self.delay_input, 1)
        layout.addLayout(delay_layout)
        
        export_format_layout = QHBoxLayout()
        export_format_layout.setSpacing(6)
        export_icon_label = QLabel()
        export_icon_label.setPixmap(qta.icon('fa6s.file-export', color='#888').pixmap(16, 16))
        export_format_layout.addWidget(export_icon_label)
        export_label = QLabel("Export:")
        export_label.setMinimumWidth(70)
        export_format_layout.addWidget(export_label)
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["PNG", "JPG", "PSD", "AI", "EPS", "PDF", "SVG", "TIFF"])
        self.export_format_combo.setEnabled(False)
        export_format_layout.addWidget(self.export_format_combo, 1)
        layout.addLayout(export_format_layout)
        
        self.js_toggle_button = QPushButton(qta.icon('fa6s.code'), " JavaScript (Advanced)")
        self.js_toggle_button.setCheckable(True)
        self.js_toggle_button.setChecked(False)
        self.js_toggle_button.clicked.connect(self.toggle_js_editor)
        layout.addWidget(self.js_toggle_button)
        
        self.js_editor = QTextEdit()
        self.js_editor.setPlaceholderText("// Enter JavaScript code here\n// Example: app.activeDocument.flatten();")
        self.js_editor.setMaximumHeight(120)
        self.js_editor.setVisible(False)
        layout.addWidget(self.js_editor)
        
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
    
    def on_type_changed(self, index):
        action_type = self.type_combo.currentText()

        # Default: enable all editable fields
        self.icon_input.setEnabled(True)
        self.icon_picker_button.setEnabled(True)
        self.color_input.setEnabled(True)
        self.color_picker_button.setEnabled(True)
        self.export_format_combo.setEnabled(False)
        self.js_toggle_button.setEnabled(False)
        self.js_toggle_button.setChecked(False)
        self.js_editor.setVisible(False)
        self.js_editor.setEnabled(False)
        self.delay_input.setEnabled(False)
        self.delay_input.setValue(0)

        if action_type == "Export":
            # Export: fixed icon + color, enable export format
            self.icon_input.setText("file-export")
            self.icon_input.setEnabled(False)
            self.icon_picker_button.setEnabled(False)

            self.selected_color = "#f44336"
            self.color_input.setText("#f44336")
            self.color_input.setEnabled(False)
            self.color_picker_button.setEnabled(False)
            self.update_color_preview()
            self.update_icon_preview()

            self.export_format_combo.setEnabled(True)
        elif action_type == "Delay":
            # Delay: fixed icon 'clock' and blue color, allow delay input
            self.icon_input.setText("clock")
            self.icon_input.setEnabled(False)
            self.icon_picker_button.setEnabled(False)

            self.selected_color = "#03a5fc"
            self.color_input.setText("#03a5fc")
            self.color_input.setEnabled(False)
            self.color_picker_button.setEnabled(False)
            self.update_color_preview()
            self.update_icon_preview()

            self.delay_input.setEnabled(True)
        elif action_type == "Script":
            # Script: fixed icon 'code' and red color (same as export), enable JS editor
            self.icon_input.setText("code")
            self.icon_input.setEnabled(False)
            self.icon_picker_button.setEnabled(False)

            self.selected_color = "#f44336"
            self.color_input.setText("#f44336")
            self.color_input.setEnabled(False)
            self.color_picker_button.setEnabled(False)
            self.update_color_preview()
            self.update_icon_preview()

            self.delay_input.setEnabled(True)
            self.js_toggle_button.setEnabled(True)
            self.js_toggle_button.setChecked(True)
            self.js_editor.setVisible(True)
            self.js_editor.setEnabled(True)
        else:
            # Action: default editable
            pass
    
    def toggle_js_editor(self):
        # JS editor controlled by action type now
        if self.type_combo.currentText() == "Script":
            is_checked = self.js_toggle_button.isChecked()
            self.js_editor.setVisible(is_checked)
    
    def load_data(self):
        self.name_input.setText(self.action_data.get('name', ''))
        self.icon_input.setText(self.action_data.get('icon', ''))
        self.color_input.setText(self.action_data.get('color', '#888888'))
        self.selected_color = self.action_data.get('color', '#888888')
        
        action_type = self.action_data.get('type', 'Action')
        self.type_combo.setCurrentText(action_type)
        
        delay = self.action_data.get('delay', 0)
        self.delay_input.setValue(delay)
        
        export_format = self.action_data.get('export_format', 'PNG')
        if export_format:
            self.export_format_combo.setCurrentText(export_format)
        
        js_code = self.action_data.get('javascript_code', '')
        if js_code:
            self.js_editor.setPlainText(js_code)
            self.js_toggle_button.setChecked(True)
            self.js_editor.setVisible(True)
        self.update_color_preview()
        self.update_icon_preview()
    
    def update_color_preview(self):
        self.color_preview.setStyleSheet(f"background-color: {self.selected_color}; border-radius: 4px;")
    
    def on_color_input_changed(self, text: str):
        """Update preview when user types a valid hex color.
        Accepts #RGB, RGB, #RRGGBB, or RRGGBB formats.
        """
        txt = text.strip()
        if txt.startswith('#'):
            hexpart = txt[1:]
        else:
            hexpart = txt
        # expand short form e.g. 'abc' -> 'aabbcc'
        if len(hexpart) == 3 and all(c in '0123456789abcdefABCDEF' for c in hexpart):
            hexpart = ''.join([c*2 for c in hexpart])
        if len(hexpart) == 6 and all(c in '0123456789abcdefABCDEF' for c in hexpart):
            self.selected_color = '#' + hexpart.lower()
            self.update_color_preview()
    
    def update_icon_preview(self):
        icon_name = self.icon_input.text().strip()
        if icon_name:
            # Default render dengan fa6s (solid)
            if "." not in icon_name:
                full_name = f"fa6s.{icon_name}"
            else:
                full_name = icon_name
            
            try:
                icon = qta.icon(full_name, color='#fcb103')
                self.icon_preview.setPixmap(icon.pixmap(24, 24))
            except:
                self.icon_preview.clear()
        else:
            self.icon_preview.clear()
    
    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.selected_color), self, "Pick Color")
        if color.isValid():
            self.selected_color = color.name()
            self.color_input.setText(self.selected_color)
            self.update_color_preview()
    
    def show_icon_picker(self):
        current_icon = self.icon_input.text().strip()
        dialog = IconPickerDialog(current_icon, self)
        dialog.icon_selected.connect(self.on_icon_picked)
        dialog.exec()
    
    def on_icon_picked(self, icon_name):
        self.icon_input.setText(icon_name)  # Simpan hanya nama
        self.update_icon_preview()
    
    def on_save(self):
        name = self.name_input.text().strip()
        icon = self.icon_input.text().strip()
        color = self.color_input.text().strip() or self.selected_color
        action_type = self.type_combo.currentText()
        delay = self.delay_input.value()
        js_code = self.js_editor.toPlainText().strip()
        export_format = self.export_format_combo.currentText() if action_type == "Export" else None
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Action name is required")
            return
        
        if not icon:
            QMessageBox.warning(self, "Validation Error", "Icon is required")
            return
        
        if not color:
            QMessageBox.warning(self, "Validation Error", "Color is required")
            return
        
        try:
            if self.action_data:
                self.db.update_action(self.action_data['id'], name, icon, color, action_type, delay, js_code, export_format)
            else:
                self.db.add_action(self.action_set_id, name, icon, color, action_type, delay, js_code, export_format)
            
            self.action_saved.emit()
            self.accept()
        except Exception as e:
            print(f"Failed to save action: {e}")
