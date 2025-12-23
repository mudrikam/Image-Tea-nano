from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QListWidget, QListWidgetItem, QPushButton, QMenu, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import qtawesome as qta
from database.db_operation import ImageTeaDB

class StepListWidget(QWidget):
    step_selected = Signal(dict)
    step_moved = Signal(int, int)
    step_edit_requested = Signal(dict)
    step_delete_requested = Signal(dict)
    action_added_to_preset = Signal()
    settings_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_preset = None
        self.current_platform_id = None
        self.db = ImageTeaDB()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.step_list = QListWidget()
        self.step_list.setObjectName("stepList")
        self.step_list.setAlternatingRowColors(False)
        self.step_list.setSpacing(2)
        self.step_list.setDragDropMode(QListWidget.InternalMove)
        self.step_list.setDefaultDropAction(Qt.MoveAction)
        self.step_list.setSelectionMode(QListWidget.SingleSelection)
        self.step_list.setMovement(QListWidget.Snap)
        self.step_list.setResizeMode(QListWidget.Adjust)
        self.step_list.model().rowsMoved.connect(self.on_rows_moved)
        self.step_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.step_list.customContextMenuRequested.connect(self.on_step_context_menu)
        layout.addWidget(self.step_list)
        
        self.setLayout(layout)
    
    def load_preset_steps(self, preset_data, platform_id=None):
        self.current_preset = preset_data
        if platform_id:
            self.current_platform_id = platform_id
        self.step_list.clear()
        
        try:
            steps = self.db.get_preset_steps(preset_data['id'])
            for step in steps:
                self.add_step_to_list(step)
        except Exception as e:
            print(f"Failed to load preset steps: {e}")
        
        self.add_new_action_button()
    
    def add_step_to_list(self, step_data):
        item = QListWidgetItem()
        
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.setSpacing(0)
        
        widget = QWidget()
        widget.setObjectName(f"stepItem_{step_data['id']}")
        color = step_data.get("color", "#888888")
        hex_color = color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        widget.setStyleSheet(f"""
            QWidget#stepItem_{step_data['id']} {{
                background-color: rgba({r}, {g}, {b}, 30);
                border-radius: 4px;
                border: 1px solid rgba({r}, {g}, {b}, 0); /* transparent default */
            }}
            QWidget#stepItem_{step_data['id']}:hover {{
                background-color: rgba({r}, {g}, {b}, 80);
                border: 1px solid rgba({r}, {g}, {b}, 1);
            }}
        """)
        
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        icon_label = QLabel()
        if "icon" in step_data and step_data["icon"]:
            # Default render dengan fa6s (solid)
            icon_name = step_data["icon"]
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
        
        name_label = QLabel(step_data["name"])
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)
        name_label.setFont(name_font)
        name_label.setStyleSheet("background: transparent;")
        content_layout.addWidget(name_label)
        
        order_label = QLabel(f"Order: {step_data.get('order_index', 0)}")
        order_label.setStyleSheet("color: #888; font-size: 9px; background: transparent;")
        content_layout.addWidget(order_label)
        
        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        
        pen_icon = qta.icon('fa6s.pen')
        pen_button = QPushButton(pen_icon, "")
        pen_button.setMaximumWidth(30)
        pen_button.setMaximumHeight(30)
        pen_button.setFlat(True)
        pen_button.setStyleSheet("background: transparent; border: none;")
        pen_button.setFocusPolicy(Qt.NoFocus)
        pen_button.clicked.connect(lambda: self.step_edit_requested.emit(step_data))
        main_layout.addWidget(pen_button)
        
        trash_icon = qta.icon('fa6s.trash')
        trash_button = QPushButton(trash_icon, "")
        trash_button.setMaximumWidth(30)
        trash_button.setMaximumHeight(30)
        trash_button.setFlat(True)
        trash_button.setStyleSheet("background: transparent; border: none;")
        trash_button.setFocusPolicy(Qt.NoFocus)
        trash_button.clicked.connect(lambda: self.step_delete_requested.emit(step_data))
        main_layout.addWidget(trash_button)
        
        container_layout.addWidget(widget)
        container.setLayout(container_layout)
        
        item.setSizeHint(container.sizeHint())
        item.setData(Qt.UserRole, step_data)
        
        self.step_list.addItem(item)
        self.step_list.setItemWidget(item, container)
    
    def _create_step_menu(self, step_data):
        menu = QMenu(self)

        edit_action = menu.addAction("Edit Step")
        edit_action.setIcon(qta.icon('fa6s.pen'))

        menu.addSeparator()
        
        action_id = step_data.get('action_id')
        action_detail = self.db.get_action_by_id(action_id)
        is_export = action_detail and action_detail.get('type') == 'Export'
        
        to_top_action = menu.addAction("To Top")
        to_top_action.setIcon(qta.icon('fa6s.angles-up'))
        to_top_action.setEnabled(not is_export)
        
        move_up_action = menu.addAction("Move Up")
        move_up_action.setIcon(qta.icon('fa6s.arrow-up'))
        move_up_action.setEnabled(not is_export)

        move_down_action = menu.addAction("Move Down")
        move_down_action.setIcon(qta.icon('fa6s.arrow-down'))
        
        to_bottom_action = menu.addAction("To Bottom")
        to_bottom_action.setIcon(qta.icon('fa6s.angles-down'))

        menu.addSeparator()
        delete_action = menu.addAction("Delete Step")
        delete_action.setIcon(qta.icon('fa6s.trash'))

        # connect signals
        edit_action.triggered.connect(lambda: self.step_edit_requested.emit(step_data))
        to_top_action.triggered.connect(lambda: self.move_step_to_top(step_data))
        move_up_action.triggered.connect(lambda: self.move_step_up(step_data))
        move_down_action.triggered.connect(lambda: self.move_step_down(step_data))
        to_bottom_action.triggered.connect(lambda: self.move_step_to_bottom(step_data))
        delete_action.triggered.connect(lambda: self.step_delete_requested.emit(step_data))

        return menu

    def show_step_menu(self, step_data, button):
        menu = self._create_step_menu(step_data)
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def on_step_context_menu(self, pos):
        # pos is relative to the widget; map to item under cursor
        item = self.step_list.itemAt(pos)
        if not item:
            return
        step_data = item.data(Qt.UserRole)
        if not step_data:
            return
        global_pos = self.step_list.viewport().mapToGlobal(pos)
        menu = self._create_step_menu(step_data)
        menu.exec_(global_pos)
    
    def move_step_up(self, step_data):
        if not self.current_preset:
            return
        
        action_id = step_data.get('action_id')
        action_detail = self.db.get_action_by_id(action_id)
        if action_detail and action_detail.get('type') == 'Export':
            QMessageBox.warning(self, "Cannot Move Export", "Export actions must stay at the bottom and cannot be moved up")
            return
        
        current_order = step_data["order_index"]
        if current_order <= 1:
            return
        
        # Kumpulkan semua steps dan tukar order
        step_orders = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if item and item.flags() & Qt.ItemIsDragEnabled:
                data = item.data(Qt.UserRole)
                if data:
                    if data['id'] == step_data['id']:
                        # Step ini turun order (naik posisi)
                        step_orders.append((data['id'], current_order - 1))
                    elif data['order_index'] == current_order - 1:
                        # Step sebelumnya naik order (turun posisi)
                        step_orders.append((data['id'], current_order))
                    else:
                        step_orders.append((data['id'], data['order_index']))
        
        try:
            self.db.update_preset_step_order(self.current_preset['id'], step_orders)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
        except Exception as e:
            print(f"Failed to move step up: {e}")
    
    def move_step_down(self, step_data):
        if not self.current_preset:
            return
        
        current_order = step_data["order_index"]
        # Hitung jumlah step (exclude button)
        total_steps = sum(1 for i in range(self.step_list.count()) 
                         if self.step_list.item(i).flags() & Qt.ItemIsDragEnabled)
        
        if current_order >= total_steps:
            return
        
        # Kumpulkan semua steps dan tukar order
        step_orders = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if item and item.flags() & Qt.ItemIsDragEnabled:
                data = item.data(Qt.UserRole)
                if data:
                    if data['id'] == step_data['id']:
                        # Step ini naik order (turun posisi)
                        step_orders.append((data['id'], current_order + 1))
                    elif data['order_index'] == current_order + 1:
                        # Step setelahnya turun order (naik posisi)
                        step_orders.append((data['id'], current_order))
                    else:
                        step_orders.append((data['id'], data['order_index']))
        
        try:
            self.db.update_preset_step_order(self.current_preset['id'], step_orders)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
        except Exception as e:
            print(f"Failed to move step down: {e}")
    
    def move_step_to_top(self, step_data):
        if not self.current_preset:
            return
        
        action_id = step_data.get('action_id')
        action_detail = self.db.get_action_by_id(action_id)
        if action_detail and action_detail.get('type') == 'Export':
            QMessageBox.warning(self, "Cannot Move Export", "Export actions must stay at the bottom and cannot be moved")
            return
        
        current_order = step_data["order_index"]
        if current_order <= 1:
            return
        
        # Step ini pindah ke order 1, sisanya geser ke bawah
        step_orders = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if item and item.flags() & Qt.ItemIsDragEnabled:
                data = item.data(Qt.UserRole)
                if data:
                    if data['id'] == step_data['id']:
                        step_orders.append((data['id'], 1))
                    elif data['order_index'] < current_order:
                        # Step yang di atas current: order naik 1
                        step_orders.append((data['id'], data['order_index'] + 1))
                    else:
                        step_orders.append((data['id'], data['order_index']))
        
        try:
            self.db.update_preset_step_order(self.current_preset['id'], step_orders)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
        except Exception as e:
            print(f"Failed to move step to top: {e}")
    
    def move_step_to_bottom(self, step_data):
        if not self.current_preset:
            return
        
        current_order = step_data["order_index"]
        # Hitung total steps
        total_steps = sum(1 for i in range(self.step_list.count()) 
                         if self.step_list.item(i).flags() & Qt.ItemIsDragEnabled)
        
        if current_order >= total_steps:
            return
        
        # Step ini pindah ke order terakhir, sisanya geser ke atas
        step_orders = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if item and item.flags() & Qt.ItemIsDragEnabled:
                data = item.data(Qt.UserRole)
                if data:
                    if data['id'] == step_data['id']:
                        step_orders.append((data['id'], total_steps))
                    elif data['order_index'] > current_order:
                        # Step yang di bawah current: order turun 1
                        step_orders.append((data['id'], data['order_index'] - 1))
                    else:
                        step_orders.append((data['id'], data['order_index']))
        
        try:
            self.db.update_preset_step_order(self.current_preset['id'], step_orders)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
        except Exception as e:
            print(f"Failed to move step to bottom: {e}")
    
    def on_rows_moved(self, parent, start, end, destination, row):
        """Handle drag-drop reordering"""
        if not self.current_preset:
            return
        
        # Cek apakah yang digeser adalah Export action
        moved_item = self.step_list.item(row)
        if moved_item:
            moved_step_data = moved_item.data(Qt.UserRole)
            if moved_step_data:
                action_id = moved_step_data.get('action_id')
                action_detail = self.db.get_action_by_id(action_id)
                if action_detail and action_detail.get('type') == 'Export':
                    QMessageBox.warning(self, "Cannot Move Export", "Export actions must stay at the bottom")
                    self.load_preset_steps(self.current_preset, self.current_platform_id)
                    return
        
        # Kumpulkan semua step dengan order baru
        step_orders = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if item and item.flags() & Qt.ItemIsDragEnabled:
                step_data = item.data(Qt.UserRole)
                if step_data:
                    step_orders.append((step_data['id'], i + 1))
        
        # Update ke database
        if step_orders:
            try:
                self.db.update_preset_step_order(self.current_preset['id'], step_orders)
                print(f"Updated order for {len(step_orders)} steps")
                self.load_preset_steps(self.current_preset, self.current_platform_id)
            except Exception as e:
                print(f"Failed to update step order: {e}")
    
    def clear_steps(self):
        self.step_list.clear()
        self.current_preset = None
    
    def add_new_action_button(self):
        from .select_action_dialog import SelectActionDialog
        
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
        
        name_label = QLabel("Select Action")
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #888; background: transparent; border: none;")
        main_layout.addWidget(name_label)
        main_layout.addStretch()
        
        widget.mousePressEvent = lambda e: self.show_select_action_dialog()
        
        container_layout.addWidget(widget)
        container.setLayout(container_layout)
        
        item.setSizeHint(container.sizeHint())
        
        self.step_list.addItem(item)
        self.step_list.setItemWidget(item, container)
    
    def show_select_action_dialog(self):
        if not self.current_preset:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Preset", "Please select a preset first")
            return
        
        if not self.current_platform_id:
            self.settings_requested.emit()
            return
        
        from .select_action_dialog import SelectActionDialog
        dialog = SelectActionDialog(self.current_platform_id, self)
        dialog.action_selected.connect(self.on_action_selected_from_dialog)
        dialog.exec()
    
    def on_action_selected_from_dialog(self, action_data):
        print(f"Action selected from dialog: {action_data}")
        if self.current_preset:
            try:
                print(f"Adding action {action_data.get('id')} to preset {self.current_preset['id']}")
                self.db.add_preset_step(self.current_preset['id'], action_data['id'])
                self.action_added_to_preset.emit()
                self.load_preset_steps(self.current_preset, self.current_platform_id)
                print("Action added successfully")
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                print(f"Error adding action: {e}")
                QMessageBox.warning(self, 'Error', f'Failed to add action to preset: {e}')
