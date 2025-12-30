from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QListWidget, QListWidgetItem, QPushButton, QMenu, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import qtawesome as qta
from dialogs.tools.add_action_dialog import AddActionDialog
from database.db_operation import ImageTeaDB


class ActionListWidget(QWidget):
    action_selected = Signal(dict)
    action_modified = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_action_set = None
        self.db = ImageTeaDB()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.action_list = QListWidget()
        self.action_list.setObjectName("actionList")
        self.action_list.setAlternatingRowColors(False)
        self.action_list.setSpacing(2)
        self.action_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.action_list.customContextMenuRequested.connect(self.on_action_context_menu)
        self.action_list.itemDoubleClicked.connect(self._on_action_item_double_clicked)
        layout.addWidget(self.action_list)
        
        self.setLayout(layout)
    
    def load_actions_for_action_set(self, action_set_data):
        self.current_action_set = action_set_data
        self.action_list.clear()
        
        try:
            actions = self.db.get_actions_by_action_set(action_set_data['id'])
            
            for action in actions:
                self.add_action_to_list(action)
            
            self.add_new_action_button()
        except Exception as e:
            print(f"Failed to load actions: {e}")
    
    def add_action_to_list(self, action_data):
        item = QListWidgetItem()
        
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.setSpacing(0)
        
        widget = QWidget()
        widget.setObjectName(f"actionItem_{action_data['id']}")
        color = action_data.get("color", "#888888")
        hex_color = color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        widget.setStyleSheet(f"""
            QWidget#actionItem_{action_data['id']} {{
                background-color: rgba({r}, {g}, {b}, 30);
                border-radius: 4px;
                border: 1px solid rgba({r}, {g}, {b}, 0); /* transparent default */
            }}
            QWidget#actionItem_{action_data['id']}:hover {{
                background-color: rgba({r}, {g}, {b}, 80);
                border: 1px solid rgba({r}, {g}, {b}, 1);
            }}
        """)
        
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        icon_label = QLabel()
        if "icon" in action_data and action_data["icon"]:
            # Default render dengan fa6s (solid)
            icon_name = action_data["icon"]
            if "." not in icon_name:
                full_icon_name = f"fa6s.{icon_name}"
            else:
                full_icon_name = icon_name
            try:
                icon = qta.icon(full_icon_name, color=color)
                icon_label.setPixmap(icon.pixmap(24, 24))
            except:
                pass
        icon_label.setFixedWidth(24)
        icon_label.setStyleSheet("background: transparent;")
        main_layout.addWidget(icon_label)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        
        name_label = QLabel(action_data["name"])
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)
        name_label.setFont(name_font)
        name_label.setStyleSheet("background: transparent;")
        content_layout.addWidget(name_label)
        
        order_label = QLabel(f"Order: {action_data.get('order_index', 0)}")
        order_label.setStyleSheet("color: #888; font-size: 9px; background: transparent;")
        content_layout.addWidget(order_label)
        
        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        
        clone_icon = qta.icon('fa6s.clone')
        clone_button = QPushButton(clone_icon, "")
        clone_button.setMaximumWidth(30)
        clone_button.setMaximumHeight(30)
        clone_button.setFlat(True)
        clone_button.setStyleSheet("background: transparent; border: none;")
        clone_button.setFocusPolicy(Qt.NoFocus)
        clone_button.setToolTip("Duplicate action")
        clone_button.clicked.connect(lambda: self.on_duplicate_action(action_data))
        main_layout.addWidget(clone_button)

        pen_icon = qta.icon('fa6s.pen')
        pen_button = QPushButton(pen_icon, "")
        pen_button.setMaximumWidth(30)
        pen_button.setMaximumHeight(30)
        pen_button.setFlat(True)
        pen_button.setStyleSheet("background: transparent; border: none;")
        pen_button.setFocusPolicy(Qt.NoFocus)
        pen_button.clicked.connect(lambda: self.on_edit_action(action_data))
        main_layout.addWidget(pen_button)
        
        trash_icon = qta.icon('fa6s.trash')
        trash_button = QPushButton(trash_icon, "")
        trash_button.setMaximumWidth(30)
        trash_button.setMaximumHeight(30)
        trash_button.setFlat(True)
        trash_button.setStyleSheet("background: transparent; border: none;")
        trash_button.setFocusPolicy(Qt.NoFocus)
        trash_button.clicked.connect(lambda: self.on_delete_action(action_data))
        main_layout.addWidget(trash_button)
        
        container_layout.addWidget(widget)
        container.setLayout(container_layout)
        
        item.setSizeHint(container.sizeHint())
        item.setData(Qt.UserRole, action_data)
        
        self.action_list.addItem(item)
        self.action_list.setItemWidget(item, container)
    
    def _create_action_menu(self, action_data):
        menu = QMenu(self)

        edit_action = menu.addAction("Edit Action")
        edit_action.setIcon(qta.icon('fa6s.pen'))

        duplicate_action = menu.addAction("Duplicate Action")
        duplicate_action.setIcon(qta.icon('fa6s.clone'))

        menu.addSeparator()

        delete_action = menu.addAction("Delete Action")
        delete_action.setIcon(qta.icon('fa6s.trash'))
        clear_action = menu.addAction("Delete All Actions")
        clear_action.setIcon(qta.icon('fa6s.broom'))

        edit_action.triggered.connect(lambda: self.on_edit_action(action_data))
        duplicate_action.triggered.connect(lambda: self.on_duplicate_action(action_data))
        delete_action.triggered.connect(lambda: self.on_delete_action(action_data))
        clear_action.triggered.connect(self._clear_all_actions_of_current_action_set)

        return menu

    def show_action_menu(self, action_data, button):
        menu = self._create_action_menu(action_data)
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def _on_action_item_double_clicked(self, item):
        action_data = item.data(Qt.UserRole)
        if action_data:
            self.on_edit_action(action_data)

    def on_action_context_menu(self, pos):
        item = self.action_list.itemAt(pos)
        if not item:
            return
        action_data = item.data(Qt.UserRole)
        if not action_data:
            return
        global_pos = self.action_list.viewport().mapToGlobal(pos)
        menu = self._create_action_menu(action_data)
        menu.exec_(global_pos)
    
    def on_edit_action(self, action_data):
        dlg = AddActionDialog(self.current_action_set['id'], action_data, parent=self)
        dlg.action_saved.connect(lambda: self.load_actions_for_action_set(self.current_action_set))
        dlg.action_saved.connect(self.action_modified.emit)
        dlg.exec()
    
    def on_delete_action(self, action_data):
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete '{action_data['name']}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_action(action_data['id'])
                self.load_actions_for_action_set(self.current_action_set)
                self.action_modified.emit()
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Failed to delete action: {e}')

    def on_duplicate_action(self, action_data):
        """Duplicate an existing action in the same action set.
        New action name is original + '_copy'."""
        try:
            original = self.db.get_action_by_id(action_data['id'])
            if not original:
                QMessageBox.warning(self, 'Error', 'Original action not found')
                return
            new_name = f"{original['name']}_copy"
            new_id = self.db.add_action(
                self.current_action_set['id'],
                new_name,
                original.get('icon', ''),
                original.get('color', '#888888'),
                original.get('type', 'Action'),
                original.get('delay', 0),
                original.get('javascript_code', ''),
                original.get('export_format')
            )
            if new_id:
                self.load_actions_for_action_set(self.current_action_set)
                self.action_modified.emit()
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to duplicate action: {e}')

    def _clear_all_actions_of_current_action_set(self):
        """Delete all actions belonging to the currently selected action set after confirmation."""
        if not self.current_action_set:
            QMessageBox.warning(self, "No Action Set", "Please select an action set first")
            return
        reply = QMessageBox.question(
            self,
            "Delete All Actions",
            f"Are you sure you want to delete ALL actions in action set '{self.current_action_set.get('name', '')}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            actions = self.db.get_actions_by_action_set(self.current_action_set['id'])
            for a in actions:
                self.db.delete_action(a['id'])
            self.load_actions_for_action_set(self.current_action_set)
            self.action_modified.emit()
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to delete actions: {e}')
    
    def clear_actions(self):
        self.action_list.clear()
        self.current_action_set = None
    
    def add_new_action_button(self):
        
        item = QListWidgetItem()
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsDragEnabled)
        
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.setSpacing(0)
        
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: rgba(100, 100, 100, 20);
                border: 2px dashed rgba(150, 150, 150, 0.2);
                border-radius: 4px;
            }
            QWidget:hover {
                background-color: rgba(78, 158, 32, 30);
                border: 2px dashed rgba(78,158,32,0.35);
            }
        """)
        widget.setCursor(Qt.PointingHandCursor)
        
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        icon_label = QLabel()
        icon = qta.icon('fa6s.plus', color='#888888')
        icon_label.setPixmap(icon.pixmap(20, 20))
        icon_label.setFixedWidth(24)
        icon_label.setStyleSheet("background: transparent; border: none;")
        main_layout.addWidget(icon_label)
        
        name_label = QLabel("Add New Action")
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #888; background: transparent; border: none;")
        main_layout.addWidget(name_label)
        main_layout.addStretch()
        
        widget.mousePressEvent = lambda event: self.show_add_action_dialog()
        
        container_layout.addWidget(widget)
        container.setLayout(container_layout)
        
        item.setSizeHint(container.sizeHint())
        
        self.action_list.addItem(item)
        self.action_list.setItemWidget(item, container)
    
    def show_add_action_dialog(self):
        if not self.current_action_set:
            return
        
        dlg = AddActionDialog(self.current_action_set['id'], parent=self)
        dlg.action_saved.connect(lambda: self.load_actions_for_action_set(self.current_action_set))
        dlg.action_saved.connect(self.action_modified.emit)
        dlg.exec()
