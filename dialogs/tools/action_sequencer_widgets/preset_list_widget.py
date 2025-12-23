from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QListWidget, QListWidgetItem, QComboBox, QTabWidget, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import qtawesome as qta
from database.db_operation import ImageTeaDB

class PresetListWidget(QWidget):
    preset_selected = Signal(dict)
    add_preset_requested = Signal()
    edit_preset_requested = Signal(dict)
    remove_preset_requested = Signal(dict)
    platform_changed = Signal(int)
    action_set_selected = Signal(dict)
    tab_changed = Signal(int)
    settings_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_preset = None
        self.current_action_set = None
        self.current_platform_id = None
        self.db = ImageTeaDB()
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
        
        self.preset_list = QListWidget()
        self.preset_list.setAlternatingRowColors(True)
        self.preset_list.setSpacing(2)
        self.preset_list.currentItemChanged.connect(self.on_preset_selection_changed)
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
        
        presets_layout.addLayout(button_layout)
        presets_tab.setLayout(presets_layout)
        
        action_sets_tab = QWidget()
        action_sets_layout = QVBoxLayout()
        action_sets_layout.setContentsMargins(0, 0, 0, 0)
        action_sets_layout.setSpacing(8)
        
        self.action_set_list = QListWidget()
        self.action_set_list.setAlternatingRowColors(True)
        self.action_set_list.setSpacing(2)
        self.action_set_list.currentItemChanged.connect(self.on_action_set_selection_changed)
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
        
        action_sets_layout.addLayout(action_set_button_layout)
        action_sets_tab.setLayout(action_sets_layout)
        
        self.tab_widget.addTab(presets_tab, qta.icon('fa6s.list-check'), " Presets")
        self.tab_widget.addTab(action_sets_tab, qta.icon('fa6s.folder'), " Action Sets")
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        layout.addWidget(self.tab_widget)
        
        self.setLayout(layout)
    
    def on_tab_changed(self, index):
        if index == 0:
            if self.preset_list.count() > 0 and self.preset_list.currentRow() == -1:
                self.preset_list.setCurrentRow(0)
        elif index == 1:
            if self.action_set_list.count() > 0 and self.action_set_list.currentRow() == -1:
                self.action_set_list.setCurrentRow(0)
        
        self.tab_changed.emit(index)
    
    def load_presets_from_db(self):
        self.preset_list.clear()
        
        if self.current_platform_id is None:
            return
        
        try:
            presets = self.db.get_presets_by_platform(self.current_platform_id)
            for preset in presets:
                self.add_preset_to_list(preset)
            
            if self.preset_list.count() > 0 and self.tab_widget.currentIndex() == 0:
                self.preset_list.setCurrentRow(0)
        except Exception as e:
            print(f"Failed to load presets: {e}")
    
    def add_preset_to_list(self, preset_data):
        item = QListWidgetItem()
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        name_label = QLabel(preset_data["name"])
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        layout.addWidget(name_label)
        
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)
        
        steps_label = QLabel(f"{preset_data['steps']} steps")
        steps_label.setStyleSheet("color: #888; font-size: 10px;")
        info_layout.addWidget(steps_label)
        
        preset_type = preset_data.get('type', '')
        if preset_type:
            type_label = QLabel(f"• {preset_type}")
            type_label.setStyleSheet("color: #666; font-size: 10px;")
            info_layout.addWidget(type_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        widget.setLayout(layout)
        
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, preset_data)
        
        self.preset_list.addItem(item)
        self.preset_list.setItemWidget(item, widget)
    
    def on_preset_selection_changed(self, current, previous):
        if current:
            preset_data = current.data(Qt.UserRole)
            self.current_preset = preset_data
            self.edit_button.setEnabled(True)
            self.remove_button.setEnabled(True)
            self.preset_selected.emit(preset_data)
        else:
            self.current_preset = None
            self.edit_button.setEnabled(False)
            self.remove_button.setEnabled(False)
    
    def on_platform_changed(self, platform):
        pass
    
    def on_add_clicked(self):
        self.add_preset_requested.emit()
    
    def on_edit_clicked(self):
        if self.current_preset:
            self.edit_preset_requested.emit(self.current_preset)
    
    def on_remove_clicked(self):
        if self.current_preset:
            self.remove_preset_requested.emit(self.current_preset)
    
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
            self.platform_changed.emit(platform_id)
            self.load_presets_from_db()
            self.load_action_sets_from_db()
    
    def load_action_sets_from_db(self):
        self.action_set_list.clear()
        
        if self.current_platform_id is None:
            return
        
        try:
            action_sets = self.db.get_action_sets_by_platform(self.current_platform_id)
            for action_set in action_sets:
                self.add_action_set_to_list(action_set)
            
            if self.action_set_list.count() > 0 and self.tab_widget.currentIndex() == 1:
                self.action_set_list.setCurrentRow(0)
        except Exception as e:
            print(f"Failed to load action sets: {e}")
    
    def add_action_set_to_list(self, action_set_data):
        item = QListWidgetItem()
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        name_label = QLabel(action_set_data["name"])
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        layout.addWidget(name_label)
        
        action_count = action_set_data.get('action_count', 0)
        count_label = QLabel(f"{action_count} actions")
        count_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(count_label)
        
        widget.setLayout(layout)
        
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, action_set_data)
        
        self.action_set_list.addItem(item)
        self.action_set_list.setItemWidget(item, widget)
    
    def on_action_set_selection_changed(self, current, previous):
        if current:
            action_set_data = current.data(Qt.UserRole)
            self.current_action_set = action_set_data
            self.edit_action_set_button.setEnabled(True)
            self.remove_action_set_button.setEnabled(True)
            self.action_set_selected.emit(action_set_data)
        else:
            self.current_action_set = None
            self.edit_action_set_button.setEnabled(False)
            self.remove_action_set_button.setEnabled(False)
    
    def on_add_action_set_clicked(self):
        if self.current_platform_id is None:
            self.settings_requested.emit()
            return
        
        from dialogs.tools.add_action_set_dialog import AddActionSetDialog
        dlg = AddActionSetDialog(self.current_platform_id, parent=self)
        dlg.action_set_saved.connect(self.load_action_sets_from_db)
        dlg.exec()
    
    def on_edit_action_set_clicked(self):
        if self.current_action_set:
            from dialogs.tools.add_action_set_dialog import AddActionSetDialog
            dlg = AddActionSetDialog(self.current_platform_id, self.current_action_set, parent=self)
            dlg.action_set_saved.connect(self.load_action_sets_from_db)
            dlg.exec()
    
    def on_remove_action_set_clicked(self):
        if not self.current_action_set:
            return
        
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove '{self.current_action_set['name']}'?\nAll actions in this set will also be deleted.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_action_set(self.current_action_set['id'])
                self.load_action_sets_from_db()
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Failed to remove action set: {e}')
