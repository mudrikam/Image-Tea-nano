import os
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QComboBox, QListView)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from config import BASE_PATH
import qtawesome as qta


class IconPickerDialog(QDialog):
    icon_selected = Signal(str)  # Hanya emit nama icon
    
    def __init__(self, current_icon="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Icon Picker")
        self.current_icon = current_icon
        self.icons_data = {}
        
        self.setModal(True)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.load_icons()
        self.setup_ui()
        self.load_icon_list()
        
        self.resize(500, 600)
    
    def load_icons(self):
        json_path = os.path.join(BASE_PATH, 'configs', 'fontawesome-v6.4.2-free.json')
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.icons_data = json.load(f)
        except Exception as e:
            print(f"Error loading FontAwesome icons: {e}")
            self.icons_data = {"solid": [], "regular": [], "brands": []}
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        filter_label = QLabel("Search:")
        filter_layout.addWidget(filter_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter icons...")
        self.search_input.textChanged.connect(self.filter_icons)
        filter_layout.addWidget(self.search_input)
        
        style_label = QLabel("Style:")
        filter_layout.addWidget(style_label)
        
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Solid", "Regular", "Brands"])
        self.style_combo.currentTextChanged.connect(self.load_icon_list)
        filter_layout.addWidget(self.style_combo)
        
        layout.addLayout(filter_layout)
        
        preview_layout = QHBoxLayout()
        preview_layout.setSpacing(8)
        
        preview_label = QLabel("Preview:")
        preview_layout.addWidget(preview_label)
        
        self.preview_icon_label = QLabel()
        self.preview_icon_label.setFixedSize(32, 32)
        self.preview_icon_label.setAlignment(Qt.AlignCenter)
        # No border, keep rounded preview area
        self.preview_icon_label.setStyleSheet("border-radius: 4px;")
        preview_layout.addWidget(self.preview_icon_label)
        
        self.preview_text_label = QLabel("")
        preview_layout.addWidget(self.preview_text_label)
        
        preview_layout.addStretch()
        layout.addLayout(preview_layout)
        
        list_label = QLabel("Available Icons:")
        layout.addWidget(list_label)
        
        self.icon_list = QListWidget()
        # Show icons in a grid (icon mode) for easier scanning
        self.icon_list.setViewMode(QListView.IconMode)
        self.icon_list.setIconSize(QSize(40, 40))
        self.icon_list.setGridSize(QSize(110, 72))
        self.icon_list.setResizeMode(QListView.Adjust)
        self.icon_list.setSpacing(8)
        self.icon_list.setMovement(QListView.Static)
        self.icon_list.setUniformItemSizes(True)
        self.icon_list.itemClicked.connect(self.on_icon_clicked)
        self.icon_list.itemDoubleClicked.connect(self.on_icon_double_clicked)
        layout.addWidget(self.icon_list)
        
        manual_layout = QHBoxLayout()
        manual_layout.setSpacing(8)
        
        manual_label = QLabel("Or enter manually:")
        manual_layout.addWidget(manual_label)
        
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("e.g., expand")
        self.manual_input.setText(self.current_icon)
        manual_layout.addWidget(self.manual_input)
        
        layout.addLayout(manual_layout)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        select_icon = qta.icon('fa6s.check')
        self.select_button = QPushButton(select_icon, " Select")
        self.select_button.clicked.connect(self.on_select)
        self.select_button.setDefault(True)
        button_layout.addWidget(self.select_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_icon_list(self):
        self.icon_list.clear()

        style = self.style_combo.currentText().lower()
        icons = self.icons_data.get(style, [])

        prefix_map = {
            "solid": "fa6s",
            "regular": "fa6r",
            "brands": "fa6b"
        }

        prefix = prefix_map.get(style, "fa6s")

        for icon_name in icons:
            if icon_name.startswith("fa-"):
                clean_name = icon_name[3:]
                full_name = f"{prefix}.{clean_name}"

                item = QListWidgetItem()
                # Show only the icon name (user doesn't need namespace)
                item.setText(clean_name)
                item.setData(Qt.UserRole, full_name)  # Store full icon name with prefix
                item.setData(Qt.UserRole + 1, style)  # Store style
                # Center label and make consistent size for grid layout
                item.setTextAlignment(Qt.AlignHCenter)
                item.setSizeHint(QSize(110, 72))
                item.setToolTip(full_name)

                try:
                    # Keep list icons unstyled so system theme applies
                    icon = qta.icon(full_name)
                    item.setIcon(icon)
                except:
                    pass

                self.icon_list.addItem(item)
    
    def filter_icons(self):
        search_text = self.search_input.text().lower()
        
        for i in range(self.icon_list.count()):
            item = self.icon_list.item(i)
            item_text = item.text().lower()
            item.setHidden(search_text not in item_text)
    
    def on_icon_clicked(self, item):
        full_name = item.data(Qt.UserRole)  # Full icon name with prefix
        icon_name = item.text()  # Just the name for display

        self.manual_input.setText(full_name)  # Store full icon name with prefix
        # Show only the icon name in preview
        self.preview_text_label.setText(icon_name)

        try:
            # Use yellow preview color consistent with editor
            icon = qta.icon(full_name, color='#fcb103')
            self.preview_icon_label.setPixmap(icon.pixmap(28, 28))
        except:
            self.preview_icon_label.clear()
    
    def on_icon_double_clicked(self, item):
        full_name = item.data(Qt.UserRole)  # Full icon name with prefix
        self.manual_input.setText(full_name)
        self.on_select()

    def on_select(self):
        icon_input = self.manual_input.text().strip()

        if not icon_input:
            QMessageBox.warning(self, "Validation Error", "Please select or enter an icon")
            return

        # User entered full icon name (e.g., fa6b.chrome) or just the name
        # Validate by trying to create the icon directly
        try:
            qta.icon(icon_input)
            # Store full icon name with prefix (or validate and use the current style prefix if just name)
            style = self.style_combo.currentText().lower()
            prefix_map = {
                "solid": "fa6s",
                "regular": "fa6r",
                "brands": "fa6b"
            }
            prefix = prefix_map.get(style, "fa6s")

            if "." not in icon_input:
                icon_full = f"{prefix}.{icon_input}"
            else:
                icon_full = icon_input

            self.icon_selected.emit(icon_full)
            self.accept()
        except:
            QMessageBox.warning(
                self,
                "Invalid Icon",
                f"Icon '{icon_input}' is not valid.\n\n"
                "Please select from the list or enter a valid icon name."
            )
