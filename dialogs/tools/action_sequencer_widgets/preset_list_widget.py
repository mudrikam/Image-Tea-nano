from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QListWidget, QListWidgetItem, QComboBox, QTabWidget, QSizePolicy, QMenu, QMessageBox, QFileDialog, QLineEdit)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
import os
import json
import qtawesome as qta
from database.db_operation import ImageTeaDB
from helpers.tools.action_sequencer_helpers.action_sequencer_import_export_helper import ActionSequencerImportExport
from .add_action_set_dialog import AddActionSetDialog
from .free_presets_dialog import FreePresetsDialog
from datetime import datetime

from ui.theme_system import theme


class JsonDropListWidget(QListWidget):
    """QListWidget that accepts drag-and-drop of one or more JSON files.

    Emits files_dropped(list[str]) with the dropped JSON file paths. Visually
    highlights the viewport while a valid drag is hovering, to give clear
    feedback that the drop target is active.
    """

    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self._drag_active = False
        self._base_stylesheet = ""

    def setStyleSheet(self, stylesheet):
        # Track the base stylesheet so we can restore it after a drag-leave.
        self._base_stylesheet = stylesheet or ""
        super().setStyleSheet(self._base_stylesheet)

    def _extract_json_paths(self, mime_data):
        if not mime_data or not mime_data.hasUrls():
            return []
        paths = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            local = url.toLocalFile()
            if local and os.path.isfile(local) and local.lower().endswith('.json'):
                paths.append(local)
        return paths

    def _apply_drag_highlight(self, active):
        if active == self._drag_active:
            return
        self._drag_active = active
        if active:
            try:
                primary = QColor(theme.get_color('primary'))
                rgb = f"{primary.red()},{primary.green()},{primary.blue()}"
            except Exception:
                rgb = "0,120,212"
            highlight = f"""
                QListWidget {{
                    border: 2px dashed rgba({rgb},0.9);
                    background-color: rgba({rgb},0.08);
                }}
            """
            super().setStyleSheet(self._base_stylesheet + highlight)
        else:
            super().setStyleSheet(self._base_stylesheet)

    def dragEnterEvent(self, event):
        if self._extract_json_paths(event.mimeData()):
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
            self._apply_drag_highlight(True)
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._extract_json_paths(event.mimeData()):
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._apply_drag_highlight(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        paths = self._extract_json_paths(event.mimeData())
        self._apply_drag_highlight(False)
        if paths:
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
            self.files_dropped.emit(paths)
        else:
            super().dropEvent(event)

class PresetListWidget(QWidget):
    preset_selected = Signal(dict)
    add_preset_requested = Signal()
    edit_preset_requested = Signal(dict)
    remove_preset_requested = Signal(dict)
    platform_changed = Signal(int)
    action_set_selected = Signal(dict)
    tab_changed = Signal(int)
    settings_requested = Signal()
    action_set_removed = Signal()   # Emitted after action set is deleted, so parent can clear action_list_widget
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_preset = None
        self.current_action_set = None
        self.current_platform_id = None
        self.db = ImageTeaDB()
        self.import_export_helper = ActionSequencerImportExport()
        self.is_first_launch = True
        self.last_selected_preset_id = None
        self.last_selected_action_set_id = None
        self._all_presets = []
        self._all_action_sets = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        platform_layout = QHBoxLayout()
        platform_layout.setSpacing(4)
        
        platform_label = QLabel("Platform:")
        platform_label.setStyleSheet("font-weight: bold;")
        platform_layout.addWidget(platform_label)
        
        self.platform_combo = QComboBox()
        self.platform_combo.currentIndexChanged.connect(self.on_platform_changed)
        # Expand combo to take remaining horizontal space
        self.platform_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        platform_layout.addWidget(self.platform_combo, 1)
        
        layout.addLayout(platform_layout)
        
        self.tab_widget = QTabWidget()
        
        presets_tab = QWidget()
        presets_layout = QVBoxLayout()
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_layout.setSpacing(8)
        
        preset_search_layout = QHBoxLayout()
        preset_search_layout.setSpacing(4)
        self.preset_search = QLineEdit()
        self.preset_search.setPlaceholderText("Search presets... (drop JSON files into the list to import)")
        self.preset_search.setToolTip("Drop one or more preset JSON files into the list below to import them.")
        self.preset_search.setClearButtonEnabled(True)
        self.preset_search.textChanged.connect(self._filter_presets)
        preset_search_layout.addWidget(self.preset_search)
        presets_layout.addLayout(preset_search_layout)
        
        self.preset_list = JsonDropListWidget()
        self.preset_list.setAlternatingRowColors(True)
        self.preset_list.setSpacing(2)
        _prim_q = QColor(theme.get_color('primary'))
        _prim_rgb = f"{_prim_q.red()},{_prim_q.green()},{_prim_q.blue()}"
        self.preset_list.setStyleSheet(f"""
            QListWidget::item:selected {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
            }}
            QListWidget::item:hover {{
                background-color: rgba({_prim_rgb},0.12);
            }}
        """)
        self.preset_list.currentItemChanged.connect(self.on_preset_selection_changed)
        self.preset_list.itemDoubleClicked.connect(self.on_preset_double_clicked)
        self.preset_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preset_list.customContextMenuRequested.connect(self.on_preset_context_menu)
        self.preset_list.files_dropped.connect(self.on_preset_files_dropped)
        presets_layout.addWidget(self.preset_list)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        
        self.add_button = QPushButton(qta.icon('fa6s.plus'), " Add")
        self.add_button.clicked.connect(self.on_add_clicked)
        button_layout.addWidget(self.add_button)
        
        self.edit_button = QPushButton(qta.icon('fa6s.pen'), " Edit")
        self.edit_button.clicked.connect(self.on_edit_clicked)
        self.edit_button.setEnabled(False)
        button_layout.addWidget(self.edit_button)
        
        self.remove_button = QPushButton(qta.icon('fa6s.trash'), " Remove")
        self.remove_button.clicked.connect(self.on_remove_clicked)
        self.remove_button.setEnabled(False)
        button_layout.addWidget(self.remove_button)
        
        self.presets_more_button = QPushButton(qta.icon('fa6s.bars'), "")
        self.presets_more_button.setToolTip("More")
        self.presets_more_button.clicked.connect(lambda: self._show_presets_overflow_menu(self.presets_more_button))
        button_layout.addWidget(self.presets_more_button)
        
        presets_layout.addLayout(button_layout)
        presets_tab.setLayout(presets_layout) 
        
        action_sets_tab = QWidget()
        action_sets_layout = QVBoxLayout()
        action_sets_layout.setContentsMargins(0, 0, 0, 0)
        action_sets_layout.setSpacing(8)
        
        action_set_search_layout = QHBoxLayout()
        action_set_search_layout.setSpacing(4)
        self.action_set_search = QLineEdit()
        self.action_set_search.setPlaceholderText("Search action sets... (drop JSON files into the list to import)")
        self.action_set_search.setToolTip("Drop one or more action set JSON files into the list below to import them.")
        self.action_set_search.setClearButtonEnabled(True)
        self.action_set_search.textChanged.connect(self._filter_action_sets)
        action_set_search_layout.addWidget(self.action_set_search)
        action_sets_layout.addLayout(action_set_search_layout)
        
        self.action_set_list = JsonDropListWidget()
        self.action_set_list.setAlternatingRowColors(True)
        self.action_set_list.setSpacing(2)
        _prim_q2 = QColor(theme.get_color('primary'))
        _prim_rgb2 = f"{_prim_q2.red()},{_prim_q2.green()},{_prim_q2.blue()}"
        self.action_set_list.setStyleSheet(f"""
            QListWidget::item:selected {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
            }}
            QListWidget::item:hover {{
                background-color: rgba({_prim_rgb2},0.12);
            }}
        """)
        self.action_set_list.currentItemChanged.connect(self.on_action_set_selection_changed)
        self.action_set_list.itemDoubleClicked.connect(self.on_action_set_double_clicked)
        self.action_set_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.action_set_list.customContextMenuRequested.connect(self.on_action_set_context_menu)
        self.action_set_list.files_dropped.connect(self.on_action_set_files_dropped)
        action_sets_layout.addWidget(self.action_set_list)
        
        action_set_button_layout = QHBoxLayout()
        action_set_button_layout.setSpacing(4)
        
        self.add_action_set_button = QPushButton(qta.icon('fa6s.plus'), " Add")
        self.add_action_set_button.clicked.connect(self.on_add_action_set_clicked)
        action_set_button_layout.addWidget(self.add_action_set_button)
        
        self.edit_action_set_button = QPushButton(qta.icon('fa6s.pen'), " Edit")
        self.edit_action_set_button.clicked.connect(self.on_edit_action_set_clicked)
        self.edit_action_set_button.setEnabled(False)
        action_set_button_layout.addWidget(self.edit_action_set_button)
        
        self.remove_action_set_button = QPushButton(qta.icon('fa6s.trash'), " Remove")
        self.remove_action_set_button.clicked.connect(self.on_remove_action_set_clicked)
        self.remove_action_set_button.setEnabled(False)
        action_set_button_layout.addWidget(self.remove_action_set_button)
        
        self.action_sets_more_button = QPushButton(qta.icon('fa6s.bars'), "")
        self.action_sets_more_button.setToolTip("More")
        self.action_sets_more_button.clicked.connect(lambda: self._show_action_sets_overflow_menu(self.action_sets_more_button))
        action_set_button_layout.addWidget(self.action_sets_more_button)
        
        action_sets_layout.addLayout(action_set_button_layout)
        action_sets_tab.setLayout(action_sets_layout)
        
        self.tab_widget.addTab(presets_tab, qta.icon('fa6s.list-check'), " Presets")
        self.tab_widget.addTab(action_sets_tab, qta.icon('fa6s.folder'), " Action Sets")
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        layout.addWidget(self.tab_widget)
        
        self.setLayout(layout)
    
    def on_tab_changed(self, index):
        if index == 0:
            if self.last_selected_preset_id:
                for i in range(self.preset_list.count()):
                    item = self.preset_list.item(i)
                    preset_data = item.data(Qt.UserRole)
                    if preset_data and preset_data['id'] == self.last_selected_preset_id:
                        self.preset_list.setCurrentItem(item)
                        break
            elif self.is_first_launch and self.preset_list.count() > 0:
                first_item = self.preset_list.item(0)
                self.preset_list.setCurrentItem(first_item)
                self.on_preset_selection_changed(first_item, None)
        elif index == 1:  # Action Sets tab
            if self.last_selected_action_set_id:
                for i in range(self.action_set_list.count()):
                    item = self.action_set_list.item(i)
                    action_set_data = item.data(Qt.UserRole)
                    if action_set_data and action_set_data['id'] == self.last_selected_action_set_id:
                        self.action_set_list.setCurrentItem(item)
                        break
            elif self.is_first_launch and self.action_set_list.count() > 0:
                first_item = self.action_set_list.item(0)
                self.action_set_list.setCurrentItem(first_item)
                self.on_action_set_selection_changed(first_item, None)
        
        if self.is_first_launch:
            self.is_first_launch = False
        
        self.tab_changed.emit(index)
    
    def load_presets_from_db(self, auto_select_first=True):
        selected_preset_id = self.current_preset['id'] if self.current_preset else None
        
        self.preset_list.clear()
        
        if self.current_platform_id is None:
            return
        
        try:
            presets = self.db.get_presets_by_platform(self.current_platform_id)
            self._all_presets = presets
            for preset in presets:
                self.add_preset_to_list(preset)
            
            search_text = self.preset_search.text().strip().lower()
            if search_text:
                self._filter_presets(search_text)
            
            if selected_preset_id:
                for i in range(self.preset_list.count()):
                    item = self.preset_list.item(i)
                    preset_data = item.data(Qt.UserRole)
                    if preset_data and preset_data['id'] == selected_preset_id:
                        self.preset_list.setCurrentItem(item)
                        break
            elif auto_select_first and self.preset_list.count() > 0:
                self.preset_list.setCurrentItem(self.preset_list.item(0))
        except Exception as e:
            print(f"Failed to load presets: {e}")
    
    def _filter_presets(self, text=None):
        if text is None:
            text = self.preset_search.text().strip().lower()
        
        self.preset_list.blockSignals(True)
        self.preset_list.clear()
        
        if not text:
            for preset in self._all_presets:
                self.add_preset_to_list(preset)
        else:
            for preset in self._all_presets:
                preset_name = preset.get('name', '').lower()
                if text in preset_name:
                    self.add_preset_to_list(preset)
        
        self.preset_list.blockSignals(False)
    
    def add_preset_to_list(self, preset_data):
        item = QListWidgetItem()
        
        widget = QWidget()
        # Horizontal main layout: left = expanding info, right = small menu button (vertically centered)
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(8)
        
        # Left: vertical info (title + small info row)
        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(2)
        
        name_label = QLabel(preset_data["name"])
        name_label.setObjectName("presetNameLabel")
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        name_label.setTextFormat(Qt.PlainText)
        name_label.setWordWrap(False)
        tooltip = preset_data.get('description', '').strip()
        if tooltip:
            name_label.setToolTip(f"{preset_data['name']} - {tooltip}")
        else:
            name_label.setToolTip(preset_data['name'])
        display_name = preset_data['name']
        if len(display_name) > 25:
            display_name = display_name[:22] + '...'
        name_label.setText(display_name)
        info_vbox.addWidget(name_label)
        
        info_h = QHBoxLayout()
        info_h.setSpacing(8)
        
        steps_label = QLabel(f"{preset_data['steps']} steps")
        steps_label.setObjectName("presetStepsLabel")
        font = steps_label.font()
        font.setPointSize(10)
        steps_label.setFont(font)
        info_h.addWidget(steps_label)
        
        preset_type = preset_data.get('type', '')
        if preset_type:
            # Scoped pill badge for type (Single Run / Batch)
            pill = QLabel(preset_type)
            pill.setObjectName("presetTypePill")
            pill.setFixedHeight(18)
            pill.setStyleSheet(f"""
                #presetTypePill {{
                    background-color: {theme.get_color('primary')};
                    color: {theme.get_color('white')};
                    border-radius: 5px;
                    padding: 2px 8px;
                    font-size: 10px;
                }}
            """)
            info_h.addWidget(pill)
        
        info_h.addStretch()
        info_vbox.addLayout(info_h)
        
        main_layout.addLayout(info_vbox)
        main_layout.addStretch()

        more_icon = qta.icon('fa6s.ellipsis-vertical')
        more_button = QPushButton(more_icon, "")
        more_button.setMaximumWidth(30)
        more_button.setMaximumHeight(30)
        more_button.setFlat(True)
        more_button.setStyleSheet("background: transparent; border: none;")
        more_button.setFocusPolicy(Qt.NoFocus)
        more_button.clicked.connect(lambda _, d=preset_data, b=more_button: self._show_preset_item_menu(d, b))
        main_layout.addWidget(more_button, 0, Qt.AlignVCenter)

        widget.setLayout(main_layout)
        
        description = preset_data.get('description', '').strip()
        if description:
            widget.setToolTip(description)
            item.setToolTip(description)
        
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, preset_data)
        
        self.preset_list.addItem(item)
        self.preset_list.setItemWidget(item, widget)
    
    def on_preset_selection_changed(self, current, previous):
        if previous:
            prev_widget = self.preset_list.itemWidget(previous)
            if prev_widget:
                for label in prev_widget.findChildren(QLabel):
                    if label.objectName() == "presetTypePill":
                        label.setStyleSheet(f"""
                            #presetTypePill {{
                                background-color: {theme.get_color('primary')};
                                color: {theme.get_color('white')};
                                border-radius: 5px;
                                padding: 2px 8px;
                                font-size: 10px;
                            }}
                        """)
                    else:
                        label.setStyleSheet("")
                        label.style().unpolish(label)
                        label.style().polish(label)
        
        if current:
            preset_data = current.data(Qt.UserRole)
            self.current_preset = preset_data
            self.last_selected_preset_id = preset_data['id']
            self.edit_button.setEnabled(True)
            self.remove_button.setEnabled(True)
            
            curr_widget = self.preset_list.itemWidget(current)
            if curr_widget:
                for label in curr_widget.findChildren(QLabel):
                    if label.objectName() == "presetTypePill":
                        label.setStyleSheet(f"""
                            #presetTypePill {{
                                background-color: {theme.get_color('white')};
                                color: {theme.get_color('primary')};
                                border-radius: 5px;
                                padding: 2px 8px;
                                font-size: 10px;
                            }}
                        """)
                    else:
                        label.setStyleSheet(f"color: {theme.get_color('white')};")
            
            self.preset_selected.emit(preset_data)
        else:
            self.current_preset = None
            self.edit_button.setEnabled(False)
            self.remove_button.setEnabled(False)
    
    def on_add_clicked(self):
        self.add_preset_requested.emit()
    
    def on_edit_clicked(self):
        if self.current_preset:
            self.edit_preset_requested.emit(self.current_preset)
    
    def on_remove_clicked(self):
        if self.current_preset:
            self.remove_preset_requested.emit(self.current_preset)

    def on_duplicate_preset(self, preset_data):
        """Duplicate a preset and its steps. New preset name will be original + '_copy'."""
        if not preset_data:
            QMessageBox.warning(self, "No Preset Selected", "Please select a preset to duplicate.")
            return
        try:
            original = self.db.get_preset_by_id(preset_data['id'])
            if not original:
                QMessageBox.warning(self, 'Error', 'Original preset not found')
                return
            new_name = f"{original['name']}_copy"
            new_id = self.db.add_preset(original['platform_id'], new_name, original.get('description', ''), original.get('type', ''))
            if new_id:
                steps = self.db.get_preset_steps(original['id'])
                for s in steps:
                    try:
                        self.db.add_preset_step(new_id, s['action_id'])
                    except Exception:
                        pass
                self.current_preset = {'id': new_id}
                self.load_presets_from_db()
                QMessageBox.information(self, 'Preset Duplicated', f"Preset duplicated as '{new_name}'")
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to duplicate preset: {e}')
    def on_preset_double_clicked(self, item):
        """Open edit dialog when a preset is double-clicked"""
        if not item:
            return
        preset_data = item.data(Qt.UserRole)
        if preset_data:
            self.edit_preset_requested.emit(preset_data)

    def on_action_set_double_clicked(self, item):
        """Open edit dialog when an action set is double-clicked"""
        if not item:
            return
        action_set_data = item.data(Qt.UserRole)
        if action_set_data:
            self.action_set_list.setCurrentItem(item)
            self.current_action_set = action_set_data
            self.last_selected_action_set_id = action_set_data['id']
            self.on_edit_action_set_clicked()
    
    def load_platforms_from_db(self):
        current_platform_id = None
        if self.platform_combo.currentIndex() >= 0:
            current_platform_id = self.platform_combo.currentData()
        
        self.platform_combo.blockSignals(True)
        self.platform_combo.clear()
        
        try:
            platforms = self.db.get_all_platforms()
            for platform in platforms:
                platform_name = platform['name']
                platform_note = platform.get('note', '')
                if platform_note:
                    display_name = f"{platform_name} ({platform_note})"
                else:
                    display_name = platform_name
                self.platform_combo.addItem(display_name, platform['id'])
            
            if current_platform_id:
                idx = self.platform_combo.findData(current_platform_id)
                if idx >= 0:
                    self.platform_combo.setCurrentIndex(idx)
                else:
                    self.preset_list.clear()
                    self.action_set_list.clear()
                    if self.platform_combo.count() > 0:
                        self.platform_combo.setCurrentIndex(0)
            elif self.platform_combo.count() > 0:
                self.platform_combo.setCurrentIndex(0)
        except Exception as e:
            print(f"Failed to load platforms: {e}")
        finally:
            self.platform_combo.blockSignals(False)
        
        if self.platform_combo.currentIndex() >= 0:
            self.on_platform_changed(self.platform_combo.currentIndex())
    
    def on_platform_changed(self, index):
        if index >= 0:
            platform_id = self.platform_combo.currentData()
            self.current_platform_id = platform_id
            
            self.current_preset = None
            self.current_action_set = None
            
            self.preset_list.clear()
            self.action_set_list.clear()
            
            self.preset_search.clear()
            self.action_set_search.clear()
            
            self.platform_changed.emit(platform_id)
            
            # Load lists without auto-selecting first item; only the active tab
            # should auto-select below to avoid emitting selection signals for the
            # inactive tab (which would populate the right pane unexpectedly).
            self.load_presets_from_db(auto_select_first=False)
            self.load_action_sets_from_db(auto_select_first=False)
            
            if self.tab_widget.currentIndex() == 0 and self.preset_list.count() > 0:
                first_item = self.preset_list.item(0)
                self.preset_list.setCurrentItem(first_item)
                self.on_preset_selection_changed(first_item, None)
            elif self.tab_widget.currentIndex() == 1 and self.action_set_list.count() > 0:
                first_item = self.action_set_list.item(0)
                self.action_set_list.setCurrentItem(first_item)
                self.on_action_set_selection_changed(first_item, None)
    
    def load_action_sets_from_db(self, auto_select_first=True):
        selected_action_set_id = self.current_action_set['id'] if self.current_action_set else None
        
        self.action_set_list.clear()
        
        if self.current_platform_id is None:
            return
        
        try:
            action_sets = self.db.get_action_sets_by_platform(self.current_platform_id)
            self._all_action_sets = action_sets
            for action_set in action_sets:
                self.add_action_set_to_list(action_set)
            
            search_text = self.action_set_search.text().strip().lower()
            if search_text:
                self._filter_action_sets(search_text)
            
            if selected_action_set_id:
                for i in range(self.action_set_list.count()):
                    item = self.action_set_list.item(i)
                    action_set_data = item.data(Qt.UserRole)
                    if action_set_data and action_set_data['id'] == selected_action_set_id:
                        self.action_set_list.setCurrentItem(item)
                        break
            elif auto_select_first and self.action_set_list.count() > 0:
                self.action_set_list.setCurrentItem(self.action_set_list.item(0))
        except Exception as e:
            print(f"Failed to load action sets: {e}")
    
    def _filter_action_sets(self, text=None):
        if text is None:
            text = self.action_set_search.text().strip().lower()
        
        self.action_set_list.blockSignals(True)
        self.action_set_list.clear()
        
        if not text:
            for action_set in self._all_action_sets:
                self.add_action_set_to_list(action_set)
        else:
            for action_set in self._all_action_sets:
                action_set_name = action_set.get('name', '').lower()
                if text in action_set_name:
                    self.add_action_set_to_list(action_set)
        
        self.action_set_list.blockSignals(False)
    
    def add_action_set_to_list(self, action_set_data):
        item = QListWidgetItem()
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        name_label = QLabel(action_set_data["name"])
        name_label.setObjectName("actionSetNameLabel")
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        name_label.setTextFormat(Qt.PlainText)
        name_label.setWordWrap(False)
        name_label.setToolTip(action_set_data['name'])
        display_name = action_set_data['name']
        if len(display_name) > 25:
            display_name = display_name[:22] + '...'
        name_label.setText(display_name)
        layout.addWidget(name_label)
        
        action_count = action_set_data.get('action_count', 0)
        count_label = QLabel(f"{action_count} actions")
        count_label.setObjectName("actionSetCountLabel")
        font = count_label.font()
        font.setPointSize(10)
        count_label.setFont(font)

        # Build an HBox where left is info (title + count), right is a small overflow button
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(8)

        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(2)
        info_vbox.addWidget(name_label)

        bottom_h = QHBoxLayout()
        bottom_h.setSpacing(8)
        bottom_h.addWidget(count_label)
        bottom_h.addStretch()
        info_vbox.addLayout(bottom_h)

        main_layout.addLayout(info_vbox)
        main_layout.addStretch()

        more_icon = qta.icon('fa6s.ellipsis-vertical')
        more_button = QPushButton(more_icon, "")
        more_button.setMaximumWidth(30)
        more_button.setMaximumHeight(30)
        more_button.setFlat(True)
        more_button.setStyleSheet("background: transparent; border: none;")
        more_button.setFocusPolicy(Qt.NoFocus)
        more_button.clicked.connect(lambda _, d=action_set_data, b=more_button: self._show_action_set_item_menu(d, b))
        main_layout.addWidget(more_button, 0, Qt.AlignVCenter)

        widget.setLayout(main_layout)
        
        # Show description as tooltip on hover when available
        description = action_set_data.get('description', '').strip()
        if description:
            widget.setToolTip(description)
            item.setToolTip(description)
        
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, action_set_data)
        
        self.action_set_list.addItem(item)
        self.action_set_list.setItemWidget(item, widget)
    
    def on_action_set_selection_changed(self, current, previous):
        if previous:
            prev_widget = self.action_set_list.itemWidget(previous)
            if prev_widget:
                for label in prev_widget.findChildren(QLabel):
                    label.setStyleSheet("")
                    label.style().unpolish(label)
                    label.style().polish(label)
        
        if current:
            action_set_data = current.data(Qt.UserRole)
            self.current_action_set = action_set_data
            self.last_selected_action_set_id = action_set_data['id']
            self.edit_action_set_button.setEnabled(True)
            self.remove_action_set_button.setEnabled(True)
            
            curr_widget = self.action_set_list.itemWidget(current)
            if curr_widget:
                for label in curr_widget.findChildren(QLabel):
                    label.setStyleSheet(f"color: {theme.get_color('white')};")
            
            self.action_set_selected.emit(action_set_data)
        else:
            self.current_action_set = None
            self.edit_action_set_button.setEnabled(False)
            self.remove_action_set_button.setEnabled(False)
    
    def on_add_action_set_clicked(self):
        if self.current_platform_id is None:
            self.settings_requested.emit()
            return
        
        dlg = AddActionSetDialog(self.current_platform_id, parent=self)
        dlg.action_set_saved.connect(self.load_action_sets_from_db)
        dlg.exec()
    
    def on_edit_action_set_clicked(self):
        if self.current_action_set:
            dlg = AddActionSetDialog(self.current_platform_id, self.current_action_set, parent=self)
            dlg.action_set_saved.connect(self.load_action_sets_from_db)
            dlg.exec()
    
    def on_remove_action_set_clicked(self):
        if not self.current_action_set:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove '{self.current_action_set['name']}'?\nAll actions in this set will also be deleted.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.db.delete_action_set(self.current_action_set['id'])
                self.current_action_set = None
                self.last_selected_action_set_id = None
                self.edit_action_set_button.setEnabled(False)
                self.remove_action_set_button.setEnabled(False)
                self.load_action_sets_from_db()
                self.action_set_removed.emit()
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Failed to remove action set: {e}')
    
    def get_selected_preset(self):
        """Return currently selected preset data"""
        return self.current_preset
    
    def on_preset_context_menu(self, pos):
        """Show context menu for preset list"""
        item = self.preset_list.itemAt(pos)
        
        menu = QMenu(self)
        
        if item:
            preset_data = item.data(Qt.UserRole)
            if preset_data:
                export_action = menu.addAction("Export This Preset")
                export_action.setIcon(qta.icon('fa6s.file-export'))
                export_action.triggered.connect(lambda: self.on_export_preset(preset_data))
                
                menu.addSeparator()

                duplicate_action = menu.addAction("Duplicate Preset")
                duplicate_action.setIcon(qta.icon('fa6s.clone'))
                duplicate_action.triggered.connect(lambda: self.on_duplicate_preset(preset_data))

                edit_action = menu.addAction("Edit")
                edit_action.setIcon(qta.icon('fa6s.pen'))
                edit_action.triggered.connect(lambda: self.edit_preset_requested.emit(preset_data))
                
                remove_action = menu.addAction("Remove")
                remove_action.setIcon(qta.icon('fa6s.trash'))
                remove_action.triggered.connect(lambda: self.remove_preset_requested.emit(preset_data))
        else:
            add_action = menu.addAction("Add New Preset")
            add_action.setIcon(qta.icon('fa6s.plus'))
            add_action.triggered.connect(self.add_preset_requested.emit)
            
            menu.addSeparator()
            
            export_all_action = menu.addAction("Export Presets")
            export_all_action.setIcon(qta.icon('fa6s.file-export'))
            export_all_action.triggered.connect(self.on_export_all_presets)
            
            import_action = menu.addAction("Import Preset")
            import_action.setIcon(qta.icon('fa6s.file-import'))
            import_action.triggered.connect(self.on_import_preset)

            menu.addSeparator()

            refresh_action = menu.addAction("Refresh Presets")
            refresh_action.setIcon(qta.icon('fa6s.arrows-rotate'))
            refresh_action.triggered.connect(self.load_presets_from_db)
            
            get_free_presets_action = menu.addAction("Get FREE Presets")
            get_free_presets_action.setIcon(qta.icon('fa6s.gift'))
            get_free_presets_action.triggered.connect(self.on_get_free_presets)
        
        global_pos = self.preset_list.viewport().mapToGlobal(pos)
        menu.exec_(global_pos)

    def _show_presets_overflow_menu(self, button):
        menu = QMenu(self)
        add_action = menu.addAction("Add New Preset")
        add_action.setIcon(qta.icon('fa6s.plus'))
        add_action.triggered.connect(self.add_preset_requested.emit)
        
        menu.addSeparator()

        duplicate_selected_action = menu.addAction("Duplicate Selected Preset")
        duplicate_selected_action.setIcon(qta.icon('fa6s.clone'))
        duplicate_selected_action.triggered.connect(lambda: self.on_duplicate_preset(self.current_preset) if self.current_preset else QMessageBox.warning(self, "No Preset Selected", "Please select a preset to duplicate."))
        
        export_all_action = menu.addAction("Export Presets")
        export_all_action.setIcon(qta.icon('fa6s.file-export'))
        export_all_action.triggered.connect(self.on_export_all_presets)
        
        import_action = menu.addAction("Import Preset")
        import_action.setIcon(qta.icon('fa6s.file-import'))
        import_action.triggered.connect(self.on_import_preset)

        menu.addSeparator()

        refresh_action = menu.addAction("Refresh Presets")
        refresh_action.setIcon(qta.icon('fa6s.arrows-rotate'))
        refresh_action.triggered.connect(self.load_presets_from_db)
        
        get_free_presets_action = menu.addAction("Get FREE Presets")
        get_free_presets_action.setIcon(qta.icon('fa6s.gift'))
        get_free_presets_action.triggered.connect(self.on_get_free_presets)
        
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def _show_preset_item_menu(self, preset_data, button):
        menu = QMenu(self)
        export_action = menu.addAction("Export This Preset")
        export_action.setIcon(qta.icon('fa6s.file-export'))
        export_action.triggered.connect(lambda: self.on_export_preset(preset_data))
        
        menu.addSeparator()

        refresh_action = menu.addAction("Refresh Presets")
        refresh_action.setIcon(qta.icon('fa6s.arrows-rotate'))
        refresh_action.triggered.connect(self.load_presets_from_db)

        duplicate_action = menu.addAction("Duplicate Preset")
        duplicate_action.setIcon(qta.icon('fa6s.clone'))
        duplicate_action.triggered.connect(lambda: self.on_duplicate_preset(preset_data))
        
        edit_action = menu.addAction("Edit")
        edit_action.setIcon(qta.icon('fa6s.pen'))
        edit_action.triggered.connect(lambda: self.edit_preset_requested.emit(preset_data))
        
        remove_action = menu.addAction("Remove")
        remove_action.setIcon(qta.icon('fa6s.trash'))
        remove_action.triggered.connect(lambda: self.remove_preset_requested.emit(preset_data))
        
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))
    
    def on_export_preset(self, preset_data):
        """Export single preset to JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = preset_data['name'].replace(' ', '_')
        filename = f"Image_Tea_Action_Sequencer_Preset_{safe_name}_{timestamp}.json"
        home_dir = os.path.expanduser('~')
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Preset",
            os.path.join(home_dir, filename),
            "JSON Files (*.json)"
        )
        
        if file_path:
            success = self.import_export_helper.export_preset(preset_data['id'], file_path)
            if success:
                QMessageBox.information(self, "Export Successful", f"Preset exported to:\n{file_path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export preset.")
    
    def on_export_all_presets(self):
        """Export all presets in current platform to JSON"""
        if self.current_platform_id is None:
            QMessageBox.warning(self, "No Platform", "Please select a platform first.")
            return
        
        presets = self.db.get_presets_by_platform(self.current_platform_id)
        if not presets:
            QMessageBox.warning(self, "No Presets", "No presets to export for this platform.")
            return
        
        home_dir = os.path.expanduser('~')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Image_Tea_Action_Sequencer_Presets_{timestamp}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Presets",
            os.path.join(home_dir, filename),
            "JSON Files (*.json)"
        )
        
        if file_path:
            preset_ids = [p['id'] for p in presets]
            success = self.import_export_helper.export_presets(preset_ids, file_path)
            if success:
                QMessageBox.information(self, "Export Successful", f"{len(preset_ids)} preset(s) exported to:\n{file_path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export presets.")
    
    def on_import_preset(self):
        """Import preset(s) from JSON"""
        home_dir = os.path.expanduser('~')
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Preset",
            home_dir,
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, "Import Failed", f"Failed to read JSON: {e}")
                return

            if 'file_type' not in data:
                QMessageBox.warning(self, "Invalid File", "Missing 'file_type' field. This file is not a valid Action Sequencer export.")
                return

            if data.get('file_type') != 'preset':
                shown_type = data.get('file_type', 'unknown').replace('_', ' ').title()
                QMessageBox.warning(self, "Wrong File Type", f"This file is of type '{shown_type}'. Please import using the Action Sets tab.")
                return

            success, message, count = self.import_export_helper.import_presets(file_path, self.current_platform_id)
            if success:
                QMessageBox.information(self, "Import Successful", message)
                self.load_presets_from_db()
                self.load_action_sets_from_db()
            else:
                QMessageBox.warning(self, "Import Failed", message) 
    
    def on_action_set_context_menu(self, pos):
        """Show context menu for action set list"""
        item = self.action_set_list.itemAt(pos)
        
        menu = QMenu(self)
        
        if item:
            action_set_data = item.data(Qt.UserRole)
            if action_set_data:
                export_action = menu.addAction("Export This Action Set")
                export_action.setIcon(qta.icon('fa6s.file-export'))
                export_action.triggered.connect(lambda: self.on_export_action_set(action_set_data))
                
                menu.addSeparator()
                
                refresh_action = menu.addAction("Refresh Action Sets")
                refresh_action.setIcon(qta.icon('fa6s.arrows-rotate'))
                refresh_action.triggered.connect(self.load_action_sets_from_db)
                
                edit_action = menu.addAction("Edit")
                edit_action.setIcon(qta.icon('fa6s.pen'))
                edit_action.triggered.connect(self.on_edit_action_set_clicked)
                
                remove_action = menu.addAction("Remove")
                remove_action.setIcon(qta.icon('fa6s.trash'))
                remove_action.triggered.connect(self.on_remove_action_set_clicked)
        else:
            add_action = menu.addAction("Add New Action Set")
            add_action.setIcon(qta.icon('fa6s.plus'))
            add_action.triggered.connect(self.on_add_action_set_clicked)
            
            menu.addSeparator()
            
            export_all_action = menu.addAction("Export Action Sets")
            export_all_action.setIcon(qta.icon('fa6s.file-export'))
            export_all_action.triggered.connect(self.on_export_all_action_sets)
            
            import_action = menu.addAction("Import Action Set")
            import_action.setIcon(qta.icon('fa6s.file-import'))
            import_action.triggered.connect(self.on_import_action_set)
            
            menu.addSeparator()
            
            refresh_action = menu.addAction("Refresh Action Sets")
            refresh_action.setIcon(qta.icon('fa6s.arrows-rotate'))
            refresh_action.triggered.connect(self.load_action_sets_from_db)
        
        global_pos = self.action_set_list.viewport().mapToGlobal(pos)
        menu.exec_(global_pos)

    def _show_action_sets_overflow_menu(self, button):
        menu = QMenu(self)
        add_action = menu.addAction("Add New Action Set")
        add_action.setIcon(qta.icon('fa6s.plus'))
        add_action.triggered.connect(self.on_add_action_set_clicked)
        
        menu.addSeparator()
        
        export_all_action = menu.addAction("Export Action Sets")
        export_all_action.setIcon(qta.icon('fa6s.file-export'))
        export_all_action.triggered.connect(self.on_export_all_action_sets)
        
        import_action = menu.addAction("Import Action Set")
        import_action.setIcon(qta.icon('fa6s.file-import'))
        import_action.triggered.connect(self.on_import_action_set)
        
        menu.addSeparator()
        
        refresh_action = menu.addAction("Refresh Action Sets")
        refresh_action.setIcon(qta.icon('fa6s.arrows-rotate'))
        refresh_action.triggered.connect(self.load_action_sets_from_db)
        
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def _show_action_set_item_menu(self, action_set_data, button):
        menu = QMenu(self)
        export_action = menu.addAction("Export This Action Set")
        export_action.setIcon(qta.icon('fa6s.file-export'))
        export_action.triggered.connect(lambda: self.on_export_action_set(action_set_data))
        
        menu.addSeparator()
        
        edit_action = menu.addAction("Edit")
        edit_action.setIcon(qta.icon('fa6s.pen'))
        edit_action.triggered.connect(self.on_edit_action_set_clicked)
        
        remove_action = menu.addAction("Remove")
        remove_action.setIcon(qta.icon('fa6s.trash'))
        remove_action.triggered.connect(self.on_remove_action_set_clicked)
        
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))
    
    def on_export_action_set(self, action_set_data):
        """Export single action set to JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = action_set_data['name'].replace(' ', '_')
        filename = f"Image_Tea_Action_Sequencer_Action_Set_{safe_name}_{timestamp}.json"
        home_dir = os.path.expanduser('~')
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Action Set",
            os.path.join(home_dir, filename),
            "JSON Files (*.json)"
        )
        
        if file_path:
            success = self.import_export_helper.export_action_set(action_set_data['id'], file_path)
            if success:
                QMessageBox.information(self, "Export Successful", f"Action set exported to:\n{file_path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export action set.")
    
    def on_export_all_action_sets(self):
        """Export all action sets in current platform to JSON"""
        if self.current_platform_id is None:
            QMessageBox.warning(self, "No Platform", "Please select a platform first.")
            return
        
        action_sets = self.db.get_action_sets_by_platform(self.current_platform_id)
        if not action_sets:
            QMessageBox.warning(self, "No Action Sets", "No action sets to export for this platform.")
            return
        
        home_dir = os.path.expanduser('~')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Image_Tea_Action_Sequencer_Action_Sets_{timestamp}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Action Sets",
            os.path.join(home_dir, filename),
            "JSON Files (*.json)"
        )
        
        if file_path:
            action_set_ids = [a['id'] for a in action_sets]
            success = self.import_export_helper.export_action_sets(action_set_ids, file_path)
            if success:
                QMessageBox.information(self, "Export Successful", f"{len(action_set_ids)} action set(s) exported to:\n{file_path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export action sets.")
    
    def on_import_action_set(self):
        """Import action set(s) from JSON"""
        home_dir = os.path.expanduser('~')
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Action Set",
            home_dir,
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, "Import Failed", f"Failed to read JSON: {e}")
                return

            if 'file_type' not in data:
                QMessageBox.warning(self, "Invalid File", "Missing 'file_type' field. This file is not a valid Action Sequencer export.")
                return

            if data.get('file_type') != 'action_set':
                shown_type = data.get('file_type', 'unknown').replace('_', ' ').title()
                QMessageBox.warning(self, "Wrong File Type", f"This file is of type '{shown_type}'. Please import using the Presets tab.")
                return

            success, message, count = self.import_export_helper.import_action_sets(file_path, self.current_platform_id)
            if success:
                QMessageBox.information(self, "Import Successful", message)
                self.load_action_sets_from_db()
            else:
                QMessageBox.warning(self, "Import Failed", message)
    
    def on_get_free_presets(self):
        """Open FREE Presets dialog to browse and download presets from GitHub"""
        dialog = FreePresetsDialog(self, self.current_platform_id)
        dialog.preset_imported.connect(self.load_presets_from_db)
        dialog.exec()

    def _read_json_file_type(self, file_path):
        """Try to read a JSON file and return its declared file_type.

        Returns:
            tuple: (file_type: str | None, error: str | None)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON format: {e}"
        except Exception as e:
            return None, f"Failed to read file: {e}"

        if not isinstance(data, dict) or 'file_type' not in data:
            return None, "Missing 'file_type' field. Not a valid Action Sequencer export."
        return data.get('file_type'), None

    def _import_dropped_files(self, file_paths, expected_type):
        """Import a list of dropped JSON files for the given expected type.

        Args:
            file_paths: list[str] of JSON file paths.
            expected_type: 'preset' or 'action_set'.

        Behavior:
            - Validates platform is selected.
            - Skips files with missing/wrong file_type and reports them.
            - Aggregates imported counts and shows a single summary dialog.
            - Reloads the appropriate list on success.
        """
        if not file_paths:
            return

        if self.current_platform_id is None:
            QMessageBox.warning(self, "No Platform", "Please select a platform first.")
            return

        type_label = "Preset" if expected_type == 'preset' else "Action Set"
        wrong_tab_label = "Action Sets tab" if expected_type == 'preset' else "Presets tab"

        total_imported = 0
        success_files = []
        failed_files = []  # list of (filename, reason)
        skipped_files = []  # list of (filename, reason)

        for path in file_paths:
            name = os.path.basename(path)
            file_type, err = self._read_json_file_type(path)
            if err:
                failed_files.append((name, err))
                continue

            if file_type != expected_type:
                shown = (file_type or 'unknown').replace('_', ' ').title()
                skipped_files.append((name, f"file_type is '{shown}', use {wrong_tab_label}"))
                continue

            try:
                if expected_type == 'preset':
                    ok, message, count = self.import_export_helper.import_presets(path, self.current_platform_id)
                else:
                    ok, message, count = self.import_export_helper.import_action_sets(path, self.current_platform_id)
            except Exception as e:
                failed_files.append((name, str(e)))
                continue

            if ok:
                total_imported += count or 0
                success_files.append((name, count or 0))
            else:
                failed_files.append((name, message or "Unknown error"))

        if total_imported > 0:
            self.load_presets_from_db()
            self.load_action_sets_from_db()

        # Build summary
        lines = []
        lines.append(f"Imported {total_imported} {type_label.lower()}(s) from {len(success_files)} of {len(file_paths)} file(s).")
        if success_files:
            lines.append("")
            lines.append("Imported:")
            for name, count in success_files:
                lines.append(f"  - {name}: {count} item(s)")
        if skipped_files:
            lines.append("")
            lines.append("Skipped (wrong type):")
            for name, reason in skipped_files:
                lines.append(f"  - {name}: {reason}")
        if failed_files:
            lines.append("")
            lines.append("Failed:")
            for name, reason in failed_files:
                lines.append(f"  - {name}: {reason}")

        summary = "\n".join(lines)
        if total_imported > 0 and not failed_files and not skipped_files:
            QMessageBox.information(self, f"Import {type_label}s", summary)
        elif total_imported > 0:
            QMessageBox.warning(self, f"Import {type_label}s (partial)", summary)
        else:
            QMessageBox.warning(self, f"Import {type_label}s Failed", summary)

    def on_preset_files_dropped(self, file_paths):
        """Handle JSON files dropped onto the preset list."""
        self._import_dropped_files(file_paths, 'preset')

    def on_action_set_files_dropped(self, file_paths):
        """Handle JSON files dropped onto the action set list."""
        self._import_dropped_files(file_paths, 'action_set')

