from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QListWidget, QListWidgetItem, QPushButton, QMenu, QMessageBox)
from PySide6.QtCore import Qt, Signal, QPoint, QTimer
from PySide6.QtGui import QFont, QDrag, QPixmap, QPainter, QColor
import qtawesome as qta
from .select_action_dialog import SelectActionDialog
from database.db_operation import ImageTeaDB
from helpers.tools.action_sequencer_helpers.action_sequencer_platform_validator import PlatformFormatValidator
from ui.theme_system import theme

class DraggableListWidget(QListWidget):
    """QListWidget subclass that creates a drag pixmap so the item follows the cursor while dragging."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._click_item = None
        self._click_was_selected = False
        self._mouse_moved = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            self._click_item = item
            self._click_was_selected = item is not None and item.isSelected()
            self._mouse_moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse_moved = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and not self._mouse_moved:
            modifiers = event.modifiers()
            item = self.itemAt(event.pos())
            if (item is not None and item is self._click_item
                    and self._click_was_selected
                    and not (modifiers & (Qt.ControlModifier | Qt.ShiftModifier))):
                item.setSelected(False)
        self._click_item = None
        self._click_was_selected = False

    def startDrag(self, supportedActions):
        selected_items = [
            self.item(i) for i in range(self.count())
            if self.item(i) and self.item(i).isSelected()
            and (self.item(i).flags() & Qt.ItemIsDragEnabled)
        ]
        if not selected_items:
            return

        pixmaps = []
        for it in selected_items:
            w = self.itemWidget(it)
            try:
                if w:
                    pixmaps.append(w.grab())
                else:
                    rect = self.visualItemRect(it)
                    px = QPixmap(rect.size())
                    px.fill(Qt.transparent)
                    pixmaps.append(px)
            except Exception:
                px = QPixmap(200, 40)
                px.fill(Qt.lightGray)
                pixmaps.append(px)

        if not pixmaps:
            return

        total_w = max(p.width() for p in pixmaps)
        total_h = sum(p.height() for p in pixmaps)
        composite = QPixmap(total_w, total_h)
        composite.fill(Qt.transparent)
        painter = QPainter(composite)
        painter.setOpacity(0.7)
        y_offset = 0
        for px in pixmaps:
            painter.drawPixmap(0, y_offset, px)
            y_offset += px.height()
        painter.end()

        drag = QDrag(self)
        mime = self.model().mimeData(self.selectedIndexes())
        drag.setMimeData(mime)
        drag.setPixmap(composite)
        drag.setHotSpot(QPoint(composite.width() // 2, pixmaps[0].height() // 2))
        drag.exec(Qt.MoveAction)

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
        self._rows_moved_timer = QTimer()
        self._rows_moved_timer.setSingleShot(True)
        self._rows_moved_timer.timeout.connect(self._save_and_reload_after_drag)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.step_list = DraggableListWidget()
        self.step_list.setObjectName("stepList")
        self.step_list.setAlternatingRowColors(False)
        self.step_list.setSpacing(2)
        self.step_list.setDragEnabled(True)
        self.step_list.setAcceptDrops(True)
        self.step_list.setDropIndicatorShown(True)
        self.step_list.setDragDropMode(QListWidget.InternalMove)
        self.step_list.setDefaultDropAction(Qt.MoveAction)
        self.step_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.step_list.setMovement(QListWidget.Snap)
        self.step_list.setResizeMode(QListWidget.Adjust)
        self.step_list.model().rowsMoved.connect(self.on_rows_moved)
        self.step_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.step_list.customContextMenuRequested.connect(self.on_step_context_menu)
        self.step_list.itemDoubleClicked.connect(lambda item: self.step_edit_requested.emit(item.data(Qt.UserRole)))
        self.step_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.step_list)
        
        self.setLayout(layout)
    
    def load_preset_steps(self, preset_data, platform_id=None):
        self.current_preset = preset_data
        if platform_id:
            self.current_platform_id = platform_id
        scroll_val = self.step_list.verticalScrollBar().value()
        self.step_list.clear()
        
        try:
            steps = self.db.get_preset_steps(preset_data['id'])
            for step in steps:
                self.add_step_to_list(step)
        except Exception as e:
            print(f"Failed to load preset steps: {e}")
        
        self.add_new_action_button()
        QTimer.singleShot(0, lambda: self.step_list.verticalScrollBar().setValue(scroll_val))
    
    def add_step_to_list(self, step_data):
        item = QListWidgetItem()
        
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.setSpacing(0)
        
        widget = QWidget()
        widget.setObjectName(f"stepItem_{step_data['id']}")
        color = step_data.get("color", theme.get_color('gray'))
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
        order_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 9px; background: transparent;")
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
        clone_button.setToolTip("Duplicate step")
        clone_button.clicked.connect(lambda: self.on_duplicate_step(step_data))
        main_layout.addWidget(clone_button)

        replace_icon = qta.icon('fa6s.arrows-rotate')
        replace_button = QPushButton(replace_icon, "")
        replace_button.setMaximumWidth(30)
        replace_button.setMaximumHeight(30)
        replace_button.setFlat(True)
        replace_button.setStyleSheet("background: transparent; border: none;")
        replace_button.setFocusPolicy(Qt.NoFocus)
        replace_button.setToolTip("Replace step")
        replace_button.clicked.connect(lambda: self.on_replace_step(step_data))
        main_layout.addWidget(replace_button)

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
    
    def _on_selection_changed(self):
        selected_ids = set()
        for item in self.step_list.selectedItems():
            d = item.data(Qt.UserRole)
            if d and d.get('id'):
                selected_ids.add(d['id'])
        for i in range(self.step_list.count()):
            list_item = self.step_list.item(i)
            if not list_item:
                continue
            d = list_item.data(Qt.UserRole)
            if d and d.get('id'):
                self._set_step_item_selected(list_item, d, d['id'] in selected_ids)

    def _get_selected_step_data_list(self) -> list:
        result = []
        for item in self.step_list.selectedItems():
            d = item.data(Qt.UserRole)
            if d and d.get('id'):
                result.append(d)
        result.sort(key=lambda s: s.get('order_index', 0))
        return result

    def _get_all_steps_from_list(self) -> list:
        steps = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if item and item.flags() & Qt.ItemIsDragEnabled:
                d = item.data(Qt.UserRole)
                if d and d.get('id'):
                    steps.append(d)
        return steps

    def _set_step_item_selected(self, item, step_data: dict, selected: bool):
        widget_container = self.step_list.itemWidget(item)
        if not widget_container:
            return
        step_widget = widget_container.findChild(QWidget, f"stepItem_{step_data['id']}")
        if not step_widget:
            return
        color = step_data.get("color", theme.get_color('gray'))
        hex_color = color.lstrip('#')
        try:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        except Exception:
            r, g, b = 128, 128, 128
        sid = step_data['id']
        if selected:
            step_widget.setStyleSheet(f"""
                QWidget#stepItem_{sid} {{
                    background-color: rgba({r}, {g}, {b}, 80);
                    border-radius: 4px;
                    border: 1px solid rgba({r}, {g}, {b}, 200);
                }}
                QWidget#stepItem_{sid}:hover {{
                    background-color: rgba({r}, {g}, {b}, 100);
                    border: 1px solid rgba({r}, {g}, {b}, 255);
                }}
            """)
        else:
            step_widget.setStyleSheet(f"""
                QWidget#stepItem_{sid} {{
                    background-color: rgba({r}, {g}, {b}, 30);
                    border-radius: 4px;
                    border: 1px solid rgba({r}, {g}, {b}, 0);
                }}
                QWidget#stepItem_{sid}:hover {{
                    background-color: rgba({r}, {g}, {b}, 80);
                    border: 1px solid rgba({r}, {g}, {b}, 1);
                }}
            """)

    def _multi_delete_steps(self, steps: list):
        if not steps or not self.current_preset:
            return
        if len(steps) == 1:
            msg = f"Are you sure you want to remove '{steps[0]['name']}' from this preset?"
        else:
            msg = f"Are you sure you want to remove {len(steps)} selected steps from this preset?"
        reply = QMessageBox.question(self, "Confirm Deletion", msg, QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        for step in steps:
            self.db.delete_preset_step(step['id'])
        self.load_preset_steps(self.current_preset, self.current_platform_id)
        self.action_added_to_preset.emit()

    def _create_step_menu(self, step_data):
        menu = QMenu(self)

        edit_action = menu.addAction("Edit Step")
        edit_action.setIcon(qta.icon('fa6s.pen'))

        add_above_action = menu.addAction("Add Step Above")
        add_above_action.setIcon(qta.icon('fa6s.plus'))
        add_below_action = menu.addAction("Add Step Below")
        add_below_action.setIcon(qta.icon('fa6s.plus'))

        duplicate_action = menu.addAction("Duplicate Step")
        duplicate_action.setIcon(qta.icon('fa6s.clone'))

        replace_action = menu.addAction("Replace Step")
        replace_action.setIcon(qta.icon('fa6s.arrows-rotate'))

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
        clear_action = menu.addAction("Clear All Steps")
        clear_action.setIcon(qta.icon('fa6s.broom'))

        edit_action.triggered.connect(lambda: self.step_edit_requested.emit(step_data))
        add_above_action.triggered.connect(lambda: self.add_step_above(step_data))
        add_below_action.triggered.connect(lambda: self.add_step_below(step_data))
        to_top_action.triggered.connect(lambda: self.move_step_to_top([step_data]))
        move_up_action.triggered.connect(lambda: self.move_step_up([step_data]))
        move_down_action.triggered.connect(lambda: self.move_step_down([step_data]))
        to_bottom_action.triggered.connect(lambda: self.move_step_to_bottom([step_data]))
        duplicate_action.triggered.connect(lambda: self.on_duplicate_step([step_data]))
        replace_action.triggered.connect(lambda: self.on_replace_step(step_data))
        delete_action.triggered.connect(lambda: self._multi_delete_steps([step_data]))
        clear_action.triggered.connect(self._clear_all_steps_of_current_preset)

        return menu

    def show_step_menu(self, step_data, button):
        menu = self._create_step_menu(step_data)
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def on_step_context_menu(self, pos):
        item = self.step_list.itemAt(pos)
        if not item:
            return
        step_data = item.data(Qt.UserRole)
        if not step_data:
            return

        selected = self._get_selected_step_data_list()
        selected_ids = {s['id'] for s in selected}
        if step_data['id'] not in selected_ids:
            selected = [step_data]
        is_multi = len(selected) > 1
        count_label = f" ({len(selected)})" if is_multi else ""

        if not is_multi:
            menu = self._create_step_menu(step_data)
            menu.exec_(self.step_list.viewport().mapToGlobal(pos))
            return

        menu = QMenu(self)
        dup_action = menu.addAction(qta.icon('fa6s.clone'), f"Duplicate{count_label}")
        menu.addSeparator()
        to_top_action = menu.addAction(qta.icon('fa6s.angles-up'), "To Top")
        move_up_action = menu.addAction(qta.icon('fa6s.arrow-up'), "Move Up")
        move_down_action = menu.addAction(qta.icon('fa6s.arrow-down'), "Move Down")
        to_bottom_action = menu.addAction(qta.icon('fa6s.angles-down'), "To Bottom")
        menu.addSeparator()
        del_action = menu.addAction(qta.icon('fa6s.trash'), f"Delete{count_label}")
        clear_action = menu.addAction(qta.icon('fa6s.broom'), "Clear All Steps")

        total_steps = sum(1 for i in range(self.step_list.count())
                          if self.step_list.item(i) and self.step_list.item(i).flags() & Qt.ItemIsDragEnabled)
        orders = [s.get('order_index', 0) for s in selected]
        to_top_action.setEnabled(min(orders) > 1)
        move_up_action.setEnabled(min(orders) > 1)
        move_down_action.setEnabled(max(orders) < total_steps)
        to_bottom_action.setEnabled(max(orders) < total_steps)

        dup_action.triggered.connect(lambda: self.on_duplicate_step(selected))
        to_top_action.triggered.connect(lambda: self.move_step_to_top(selected))
        move_up_action.triggered.connect(lambda: self.move_step_up(selected))
        move_down_action.triggered.connect(lambda: self.move_step_down(selected))
        to_bottom_action.triggered.connect(lambda: self.move_step_to_bottom(selected))
        del_action.triggered.connect(lambda: self._multi_delete_steps(selected))
        clear_action.triggered.connect(self._clear_all_steps_of_current_preset)

        menu.exec_(self.step_list.viewport().mapToGlobal(pos))
    
    def move_step_up(self, step_input):
        if isinstance(step_input, dict):
            step_input = [step_input]
        if not self.current_preset:
            return
        for sd in step_input:
            aid = sd.get('action_id')
            ad = self.db.get_action_by_id(aid)
            if ad and ad.get('type') == 'Export':
                QMessageBox.warning(self, "Cannot Move Export", "Export actions must stay at the bottom. Cannot move above non-export actions.")
                return
        selected_ids = {s['id'] for s in step_input}
        all_steps = sorted(self._get_all_steps_from_list(), key=lambda s: s.get('order_index', 0))
        ids_ordered = [s['id'] for s in all_steps]
        if not ids_ordered or ids_ordered[0] in selected_ids:
            return
        for i in range(1, len(ids_ordered)):
            if ids_ordered[i] in selected_ids and ids_ordered[i - 1] not in selected_ids:
                ids_ordered[i - 1], ids_ordered[i] = ids_ordered[i], ids_ordered[i - 1]
        step_orders = [(pid, i + 1) for i, pid in enumerate(ids_ordered)]
        try:
            self.db.update_preset_step_order(self.current_preset['id'], step_orders)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
        except Exception as e:
            print(f"Failed to move step up: {e}")
    
    def move_step_down(self, step_input):
        if isinstance(step_input, dict):
            step_input = [step_input]
        if not self.current_preset:
            return
        selected_ids = {s['id'] for s in step_input}
        export_order = self._get_export_order()
        for sd in step_input:
            ad = self.db.get_action_by_id(sd.get('action_id'))
            if ad and ad.get('type') != 'Export' and export_order is not None:
                if sd.get('order_index', 0) + 1 >= export_order:
                    QMessageBox.warning(self, "Invalid Move", "Cannot move non-export steps below Export actions. Export must stay at the bottom.")
                    return
        all_steps = sorted(self._get_all_steps_from_list(), key=lambda s: s.get('order_index', 0))
        ids_ordered = [s['id'] for s in all_steps]
        if not ids_ordered or ids_ordered[-1] in selected_ids:
            return
        for i in range(len(ids_ordered) - 2, -1, -1):
            if ids_ordered[i] in selected_ids and ids_ordered[i + 1] not in selected_ids:
                ids_ordered[i], ids_ordered[i + 1] = ids_ordered[i + 1], ids_ordered[i]
        step_orders = [(pid, i + 1) for i, pid in enumerate(ids_ordered)]
        try:
            self.db.update_preset_step_order(self.current_preset['id'], step_orders)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
        except Exception as e:
            print(f"Failed to move step down: {e}")

    def move_step_to_top(self, step_input):
        if isinstance(step_input, dict):
            step_input = [step_input]
        if not self.current_preset:
            return
        for sd in step_input:
            ad = self.db.get_action_by_id(sd.get('action_id'))
            if ad and ad.get('type') == 'Export':
                QMessageBox.warning(self, "Cannot Move Export", "Export actions must stay at the bottom and cannot be moved to top")
                return
        selected_ids = {s['id'] for s in step_input}
        all_steps = sorted(self._get_all_steps_from_list(), key=lambda s: s.get('order_index', 0))
        selected_sorted = [s for s in all_steps if s['id'] in selected_ids]
        others = [s for s in all_steps if s['id'] not in selected_ids]
        new_order = selected_sorted + others
        step_orders = [(s['id'], i + 1) for i, s in enumerate(new_order)]
        try:
            self.db.update_preset_step_order(self.current_preset['id'], step_orders)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
        except Exception as e:
            print(f"Failed to move step to top: {e}")

    def move_step_to_bottom(self, step_input):
        if isinstance(step_input, dict):
            step_input = [step_input]
        if not self.current_preset:
            return
        export_order = self._get_export_order()
        for sd in step_input:
            ad = self.db.get_action_by_id(sd.get('action_id'))
            if ad and ad.get('type') != 'Export' and export_order is not None:
                QMessageBox.warning(self, "Invalid Move", "Cannot move steps below Export action. Export must stay at the bottom.")
                return
        selected_ids = {s['id'] for s in step_input}
        all_steps = sorted(self._get_all_steps_from_list(), key=lambda s: s.get('order_index', 0))
        selected_sorted = [s for s in all_steps if s['id'] in selected_ids]
        others = [s for s in all_steps if s['id'] not in selected_ids]
        new_order = others + selected_sorted
        step_orders = [(s['id'], i + 1) for i, s in enumerate(new_order)]
        try:
            self.db.update_preset_step_order(self.current_preset['id'], step_orders)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
        except Exception as e:
            print(f"Failed to move step to bottom: {e}")

    def on_duplicate_step(self, step_input):
        if isinstance(step_input, dict):
            step_input = [step_input]
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Please select a preset first")
            return
        steps = sorted(step_input, key=lambda s: s.get('order_index', 0))
        insert_after = max(s.get('order_index', 0) for s in steps)
        shift = len(steps)
        all_steps = self.db.get_preset_steps(self.current_preset['id'])
        step_orders = []
        for s in all_steps:
            if s['order_index'] > insert_after:
                step_orders.append((s['id'], s['order_index'] + shift))
            else:
                step_orders.append((s['id'], s['order_index']))
        self.db.update_preset_step_order(self.current_preset['id'], step_orders)
        for i, sd in enumerate(steps):
            self.db.add_preset_step(self.current_preset['id'], sd.get('action_id'), insert_at=insert_after + 1 + i)
        self.load_preset_steps(self.current_preset, self.current_platform_id)
        self.action_added_to_preset.emit()

    def on_replace_step(self, step_data):
        """Replace a preset step with an action selected from SelectActionDialog."""
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Please select a preset first")
            return
        if not self.current_platform_id:
            self.settings_requested.emit()
            return

        # Open SelectActionDialog to choose replacement action
        dialog = SelectActionDialog(self.current_platform_id, parent=self)

        def _on_action_chosen(action_data):
            # Validate export placement rules
            selected_action_type = action_data.get('type')
            current_order = step_data.get('order_index', 0)
            export_order = self._get_export_order()

            # If selecting Export and another Export exists elsewhere -> not allowed
            if selected_action_type == 'Export' and export_order is not None and export_order != current_order:
                QMessageBox.warning(self, "Cannot Replace", "This preset already contains an Export action. Only one Export step is allowed.")
                return

            # If selecting non-export and the current position would be after an Export -> not allowed
            if selected_action_type != 'Export' and export_order is not None and current_order > export_order:
                QMessageBox.warning(self, "Invalid Position", "Cannot place a non-export step after an Export action.")
                return

            # Perform DB update
            self.db.update_preset_step_action(step_data['id'], action_data.get('id'))
            # Reload and notify
            self.load_preset_steps(self.current_preset, self.current_platform_id)
            self.action_added_to_preset.emit()
            dialog.accept()

        dialog.action_selected.connect(_on_action_chosen)
        dialog.exec()
    
    def on_rows_moved(self, parent, start, end, destination, row):
        """Handle drag-drop reordering — debounced so multi-row drag only saves once."""
        if not self.current_preset:
            return
        self._rows_moved_timer.start(80)

    def _save_and_reload_after_drag(self):
        """Called once after all rowsMoved signals settle for a single drag operation."""
        if not self.current_preset:
            return

        # Validasi: cari first export position
        first_export_pos = None
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if item and item.flags() & Qt.ItemIsDragEnabled:
                data = item.data(Qt.UserRole)
                if data:
                    action = self.db.get_action_by_id(data['action_id'])
                    if action and action.get('type') == 'Export':
                        if first_export_pos is None:
                            first_export_pos = i + 1
                        break

        # Validasi: pastikan tidak ada non-export di bawah export
        if first_export_pos:
            for i in range(self.step_list.count()):
                item = self.step_list.item(i)
                if item and item.flags() & Qt.ItemIsDragEnabled:
                    data = item.data(Qt.UserRole)
                    if data:
                        action = self.db.get_action_by_id(data['action_id'])
                        position = i + 1
                        if action and action.get('type') != 'Export' and position >= first_export_pos:
                            QMessageBox.warning(self, "Invalid Reorder", "Cannot place non-export actions below Export actions. Reordering reverted.")
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
    
    def _get_export_order(self):
        """Return 1-based order index of Export action in current preset, or None if no Export."""
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if item and item.flags() & Qt.ItemIsDragEnabled:
                data = item.data(Qt.UserRole)
                if data:
                    action = self.db.get_action_by_id(data['action_id'])
                    if action and action.get('type') == 'Export':
                        return data.get('order_index', i + 1)
        return None
    
    def add_new_action_button(self):
        
        item = QListWidgetItem()
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsDragEnabled)
        
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.setSpacing(0)
        
        _gray_q = QColor(theme.get_color('gray'))
        _gray_rgb = f"{_gray_q.red()},{_gray_q.green()},{_gray_q.blue()}"
        _prm_q = QColor(theme.get_color('primary'))
        _prm_rgb = f"{_prm_q.red()},{_prm_q.green()},{_prm_q.blue()}"
        
        widget = QWidget()
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: rgba({_gray_rgb},0.08);
                border: 2px dashed rgba({_gray_rgb},0.2);
                border-radius: 4px;
            }}
            QWidget:hover {{
                background-color: rgba({_prm_rgb},0.12);
                border: 2px dashed rgba({_prm_rgb},0.35);
            }}
        """)
        widget.setCursor(Qt.PointingHandCursor)
        
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        icon_label = QLabel()
        icon = qta.icon('fa6s.plus', color=theme.get_color('gray'))
        icon_label.setPixmap(icon.pixmap(20, 20))
        icon_label.setFixedWidth(24)
        icon_label.setStyleSheet("background: transparent; border: none;")
        main_layout.addWidget(icon_label)
        
        name_label = QLabel("Select Action")
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {theme.get_color('gray')}; background: transparent; border: none;")
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
            QMessageBox.warning(self, "No Preset", "Please select a preset first")
            return
        
        if not self.current_platform_id:
            self.settings_requested.emit()
            return
        
        dialog = SelectActionDialog(self.current_platform_id, self)
        dialog.action_selected.connect(self.on_action_selected_from_dialog)
        dialog.exec()

    def add_step_above(self, step_data):
        """Open SelectActionDialog and insert chosen action above the given step."""
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Please select a preset first")
            return
        if not self.current_platform_id:
            self.settings_requested.emit()
            return
        insert_at = step_data.get('order_index', 1)
        dialog = SelectActionDialog(self.current_platform_id, self)
        dialog.action_selected.connect(lambda action: self._insert_selected_action(action, insert_at))
        dialog.exec()

    def add_step_below(self, step_data):
        """Open SelectActionDialog and insert chosen action below the given step."""
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Please select a preset first")
            return
        if not self.current_platform_id:
            self.settings_requested.emit()
            return
        current_order = step_data.get('order_index', 0)
        insert_at = current_order + 1
        dialog = SelectActionDialog(self.current_platform_id, self)
        dialog.action_selected.connect(lambda action: self._insert_selected_action(action, insert_at))
        dialog.exec()

    def _insert_selected_action(self, action_data, insert_at):
        """Insert the selected action into the current preset at the 1-based insert_at position,
        with validation for Export placement rules, platform format support, and duplicate prevention."""
        try:
            action_id = action_data.get('id')
            action_type = action_data.get('type')
            
            # Check for duplicate action (any type)
            existing_steps = self.db.get_preset_steps(self.current_preset['id'])
            for step in existing_steps:
                if step['action_id'] == action_id:
                    action_name = action_data.get('name', 'this action')
                    QMessageBox.warning(
                        self, 
                        "Duplicate Action", 
                        f"'{action_name}' is already added to this preset.\n\n"
                        f"You cannot add the same action twice."
                    )
                    return
            
            if action_type == 'Export':
                # Platform format validation
                export_format = action_data.get('export_format')
                if export_format and self.current_platform_id:
                    platform = self.db.get_platform_by_id(self.current_platform_id)
                    if platform:
                        platform_name = platform.get('name', '')
                        if not PlatformFormatValidator.is_format_supported(platform_name, export_format):
                            msg = PlatformFormatValidator.get_unsupported_message(platform_name, export_format)
                            QMessageBox.warning(self, "Unsupported Format", msg)
                            return
                
                # Smart positioning: Export must be at or after last export
                export_positions = []
                for step in existing_steps:
                    step_action = self.db.get_action_by_id(step['action_id'])
                    if step_action and step_action.get('type') == 'Export':
                        export_positions.append(step['order_index'])
                
                if export_positions:
                    last_export_pos = max(export_positions)
                    if insert_at <= last_export_pos:
                        insert_at = last_export_pos + 1
            else:
                # Non-export: Must be before first export
                first_export_pos = None
                existing_steps = self.db.get_preset_steps(self.current_preset['id'])
                for step in existing_steps:
                    step_action = self.db.get_action_by_id(step['action_id'])
                    if step_action and step_action.get('type') == 'Export':
                        if first_export_pos is None or step['order_index'] < first_export_pos:
                            first_export_pos = step['order_index']
                
                if first_export_pos and insert_at >= first_export_pos:
                    QMessageBox.warning(
                        self, 
                        "Invalid Position", 
                        "Cannot add a non-export step after Export actions.\n"
                        "All export actions must be at the end of the sequence."
                    )
                    return
            
            self.db.add_preset_step(self.current_preset['id'], action_id, insert_at=insert_at)
            self.load_preset_steps(self.current_preset, self.current_platform_id)
            self.action_added_to_preset.emit()
        except Exception as e:
            print(f"Failed to insert selected action: {e}")
    
    def on_action_selected_from_dialog(self, action_data):
        print(f"Action selected from dialog: {action_data}")
        if self.current_preset:
            try:
                action_id = action_data.get('id')
                action_type = action_data.get('type')
                print(f"Adding action {action_id} to preset {self.current_preset['id']}")

                # Check for duplicate action (any type)
                existing_steps = self.db.get_preset_steps(self.current_preset['id'])
                for step in existing_steps:
                    if step['action_id'] == action_id:
                        action_name = action_data.get('name', 'this action')
                        QMessageBox.warning(
                            self, 
                            "Duplicate Action", 
                            f"'{action_name}' is already added to this preset.\n\n"
                            f"You cannot add the same action twice."
                        )
                        return

                if action_type == 'Export':
                    # Platform format validation
                    export_format = action_data.get('export_format')
                    if export_format and self.current_platform_id:
                        platform = self.db.get_platform_by_id(self.current_platform_id)
                        if platform:
                            platform_name = platform.get('name', '')
                            if not PlatformFormatValidator.is_format_supported(platform_name, export_format):
                                msg = PlatformFormatValidator.get_unsupported_message(platform_name, export_format)
                                QMessageBox.warning(self, "Unsupported Format", msg)
                                return
                    
                    # Export always appends to end
                    self.db.add_preset_step(self.current_preset['id'], action_id)
                else:
                    # Non-export action: insert before first Export if exists
                    existing_steps = self.db.get_preset_steps(self.current_preset['id'])
                    insert_pos = None
                    for s in existing_steps:
                        existing_action = self.db.get_action_by_id(s['action_id'])
                        if existing_action and existing_action.get('type') == 'Export':
                            if insert_pos is None or s['order_index'] < insert_pos:
                                insert_pos = s['order_index']
                    
                    if insert_pos:
                        self.db.add_preset_step(self.current_preset['id'], action_id, insert_at=insert_pos)
                    else:
                        self.db.add_preset_step(self.current_preset['id'], action_id)
                
                self.action_added_to_preset.emit()
                self.load_preset_steps(self.current_preset, self.current_platform_id)
                print("Action added successfully")
            except Exception as e:
                print(f"Error adding action: {e}")
                QMessageBox.warning(self, 'Error', f'Failed to add action to preset: {e}')

    def _clear_all_steps_of_current_preset(self):
        """Delete all steps belonging to the currently selected preset after confirmation."""
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Please select a preset first")
            return
        reply = QMessageBox.question(
            self,
            "Clear All Steps",
            f"Are you sure you want to delete ALL steps for preset '{self.current_preset.get('name', '')}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            steps = self.db.get_preset_steps(self.current_preset['id'])
            for s in steps:
                self.db.delete_preset_step(s['id'])
            self.load_preset_steps(self.current_preset, self.current_platform_id)
            self.action_added_to_preset.emit()
        except Exception as e:
            print(f"Failed to clear steps: {e}")

    def highlight_steps_by_segment(self, segment_index, total_segments):
        """Highlight steps yang sedang diproses dalam segment tertentu.
        
        Args:
            segment_index: Index segment yang sedang aktif (0-based)
            total_segments: Total jumlah segment
        """
        if total_segments <= 1:
            self.highlight_all_steps()
            return
        
        steps = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if not item or not (item.flags() & Qt.ItemIsDragEnabled):
                continue
            step_data = item.data(Qt.UserRole)
            if step_data:
                steps.append((i, step_data))
        
        if not steps:
            return
        
        delay_indices = []
        for idx, (list_idx, step_data) in enumerate(steps):
            action_detail = self.db.get_action_by_id(step_data['action_id'])
            if action_detail and action_detail.get('type') == 'Delay':
                delay_indices.append(idx)
        
        if not delay_indices:
            self.highlight_all_steps()
            return
        
        segment_ranges = []
        start = 0
        for delay_idx in delay_indices:
            segment_ranges.append((start, delay_idx + 1))
            start = delay_idx + 1
        if start < len(steps):
            segment_ranges.append((start, len(steps)))
        
        if segment_index >= len(segment_ranges):
            return
        
        start_idx, end_idx = segment_ranges[segment_index]
        
        for idx, (list_idx, step_data) in enumerate(steps):
            widget_container = self.step_list.itemWidget(self.step_list.item(list_idx))
            if not widget_container:
                continue
            
            step_widget = widget_container.findChild(QWidget, f"stepItem_{step_data['id']}")
            if not step_widget:
                continue
            
            color = step_data.get("color", theme.get_color('gray'))
            hex_color = color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            if start_idx <= idx < end_idx:
                step_widget.setStyleSheet(f"""
                    QWidget#stepItem_{step_data['id']} {{
                        background-color: rgba({r}, {g}, {b}, 80);
                        border-radius: 4px;
                        border: 1px solid rgba({r}, {g}, {b}, 1);
                    }}
                """)
            else:
                step_widget.setStyleSheet(f"""
                    QWidget#stepItem_{step_data['id']} {{
                        background-color: rgba({r}, {g}, {b}, 30);
                        border-radius: 4px;
                        border: 1px solid rgba({r}, {g}, {b}, 0);
                    }}
                    QWidget#stepItem_{step_data['id']}:hover {{
                        background-color: rgba({r}, {g}, {b}, 80);
                        border: 1px solid rgba({r}, {g}, {b}, 1);
                    }}
                """)
    
    def highlight_all_steps(self):
        """Highlight semua steps (untuk mode tanpa delay)"""
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if not item or not (item.flags() & Qt.ItemIsDragEnabled):
                continue
            
            step_data = item.data(Qt.UserRole)
            if not step_data:
                continue
            
            widget_container = self.step_list.itemWidget(item)
            if not widget_container:
                continue
            
            step_widget = widget_container.findChild(QWidget, f"stepItem_{step_data['id']}")
            if not step_widget:
                continue
            
            color = step_data.get("color", theme.get_color('gray'))
            hex_color = color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            step_widget.setStyleSheet(f"""
                QWidget#stepItem_{step_data['id']} {{
                    background-color: rgba({r}, {g}, {b}, 80);
                    border-radius: 4px;
                    border: 1px solid rgba({r}, {g}, {b}, 1);
                }}
            """)
    
    def clear_all_highlights(self):
        """Clear semua highlights, kembalikan ke style normal"""
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if not item or not (item.flags() & Qt.ItemIsDragEnabled):
                continue
            
            step_data = item.data(Qt.UserRole)
            if not step_data:
                continue
            
            widget_container = self.step_list.itemWidget(item)
            if not widget_container:
                continue
            
            step_widget = widget_container.findChild(QWidget, f"stepItem_{step_data['id']}")
            if not step_widget:
                continue
            
            color = step_data.get("color", theme.get_color('gray'))
            hex_color = color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            step_widget.setStyleSheet(f"""
                QWidget#stepItem_{step_data['id']} {{
                    background-color: rgba({r}, {g}, {b}, 30);
                    border-radius: 4px;
                    border: 1px solid rgba({r}, {g}, {b}, 0);
                }}
                QWidget#stepItem_{step_data['id']}:hover {{
                    background-color: rgba({r}, {g}, {b}, 80);
                    border: 1px solid rgba({r}, {g}, {b}, 1);
                }}
            """)
