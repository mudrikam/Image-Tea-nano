import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QComboBox, QListView, QApplication)
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtGui import QIcon, QKeyEvent
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
        """Load all available icons dynamically from qtawesome"""
        self.icons_data = {"solid": [], "regular": [], "brands": []}
        
        try:
            # Force qtawesome initialization
            qta.icon('fa5s.home')
            
            # Get all available icons from qtawesome charmap
            charmap = qta._instance().charmap
            
            for prefix, icons in charmap.items():
                if isinstance(icons, dict):
                    for icon_name in icons.keys():
                        # Map qtawesome prefixes to our style categories
                        if prefix in ['fa5s', 'fa6s']:  # Solid icons
                            self.icons_data["solid"].append(f"fa-{icon_name}")
                        elif prefix in ['fa5', 'fa6']:  # Regular icons (fa5 and fa6 are regular style)
                            self.icons_data["regular"].append(f"fa-{icon_name}")
                        elif prefix in ['fa5b', 'fa6b']:  # Brand icons
                            self.icons_data["brands"].append(f"fa-{icon_name}")
            
            # Remove duplicates and sort
            for style in self.icons_data:
                self.icons_data[style] = sorted(list(set(self.icons_data[style])))
                
        except Exception as e:
            print(f"Error loading QtAwesome icons: {e}")
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
        self.search_input.installEventFilter(self)  # Install event filter for Delete key
        filter_layout.addWidget(self.search_input)
        
        # Add paste button
        paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        paste_button.setToolTip("Paste from clipboard")
        paste_button.setFixedWidth(32)
        paste_button.clicked.connect(self.paste_from_clipboard)
        filter_layout.addWidget(paste_button)
        
        # Add clear button
        clear_button = QPushButton(qta.icon('fa6s.xmark'), "")
        clear_button.setToolTip("Clear search")
        clear_button.setFixedWidth(32)
        clear_button.clicked.connect(self.clear_search)
        filter_layout.addWidget(clear_button)
        
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
        
        self.list_label = QLabel("Available Icons:")
        layout.addWidget(self.list_label)
        
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

        # For regular style, we need to use 'fa6' prefix (not 'fa6r')
        # because FontAwesome 6 regular icons use 'fa6' prefix in qtawesome
        prefix_map = {
            "solid": "fa6s",
            "regular": "fa6",  # Changed from fa6r to fa6
            "brands": "fa6b"
        }

        prefix = prefix_map.get(style, "fa6s")

        rendered_count = 0
        for icon_name in icons:
            if icon_name.startswith("fa-"):
                clean_name = icon_name[3:]
                full_name = f"{prefix}.{clean_name}"

                # Try to create the icon first to validate it can be rendered
                try:
                    icon = qta.icon(full_name)
                    
                    item = QListWidgetItem()
                    # Show only the icon name (user doesn't need namespace)
                    item.setText(clean_name)
                    item.setData(Qt.UserRole, full_name)  # Store full icon name with prefix
                    item.setData(Qt.UserRole + 1, style)  # Store style
                    # Center label and make consistent size for grid layout
                    item.setTextAlignment(Qt.AlignHCenter)
                    item.setSizeHint(QSize(110, 72))
                    item.setToolTip(full_name)
                    item.setIcon(icon)
                    
                    self.icon_list.addItem(item)
                    rendered_count += 1
                except:
                    # Skip icons that can't be rendered
                    pass
        
        # Update label with stats
        self.update_icon_stats()
    
    def filter_icons(self):
        search_text = self.search_input.text().lower().strip()
        
        if not search_text:
            # Show all icons if search is empty
            for i in range(self.icon_list.count()):
                item = self.icon_list.item(i)
                item.setHidden(False)
            self.update_icon_stats()
            return
        
        # First, try to find in current style
        visible_count = 0
        for i in range(self.icon_list.count()):
            item = self.icon_list.item(i)
            item_text = item.text().lower()
            is_visible = search_text in item_text
            item.setHidden(not is_visible)
            if is_visible:
                visible_count += 1
        
        # If no results in current style, auto-switch to style that has the icon
        if visible_count == 0:
            self.auto_switch_style(search_text)
        else:
            self.update_icon_stats()
    
    def auto_switch_style(self, search_text):
        """Auto switch to style that contains the searched icon"""
        current_style = self.style_combo.currentText().lower()
        styles_to_check = ["solid", "regular", "brands"]
        
        # Remove current style from check list
        if current_style in styles_to_check:
            styles_to_check.remove(current_style)
        
        # Check other styles
        for style in styles_to_check:
            icons = self.icons_data.get(style, [])
            for icon_name in icons:
                if icon_name.startswith("fa-"):
                    clean_name = icon_name[3:]
                    if search_text in clean_name.lower():
                        # Found in this style, switch to it
                        style_display = style.capitalize()
                        self.style_combo.setCurrentText(style_display)
                        return
        
        # If still not found, just update stats
        self.update_icon_stats()
    
    def update_icon_stats(self):
        """Update the label with icon count statistics"""
        total = self.icon_list.count()
        visible = sum(1 for i in range(total) if not self.icon_list.item(i).isHidden())
        style = self.style_combo.currentText()
        
        if visible < total:
            self.list_label.setText(f"Available Icons ({style}): {visible} of {total}")
        else:
            self.list_label.setText(f"Available Icons ({style}): {total}")
    
    def paste_from_clipboard(self):
        """Paste text from clipboard to search input"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.search_input.setText(text)
            self.search_input.setFocus()
    
    def clear_search(self):
        """Clear search input"""
        self.search_input.clear()
        self.search_input.setFocus()
        # Trigger filter update to show all icons
        self.filter_icons()
    
    def eventFilter(self, obj, event):
        """Event filter to handle Delete key on search input"""
        if obj == self.search_input and event.type() == QEvent.KeyPress:
            key_event = event
            # Delete key clears the entire search
            if key_event.key() == Qt.Key_Delete:
                self.clear_search()
                return True  # Event handled
        return super().eventFilter(obj, event)
    
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
                "regular": "fa6",  # Changed from fa6r to fa6
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
