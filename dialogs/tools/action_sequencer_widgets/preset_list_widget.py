from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QListWidget, QListWidgetItem, QComboBox, QTabWidget, QSizePolicy, QMenu, QMessageBox, QFileDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import os
import qtawesome as qta
from database.db_operation import ImageTeaDB
from helpers.tools.action_sequencer_helpers.action_sequencer_import_export_helper import ActionSequencerImportExport

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
        self.import_export_helper = ActionSequencerImportExport()
        self.is_first_launch = True
        self.last_selected_preset_id = None
        self.last_selected_action_set_id = None
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
        self.preset_list.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #4e9e20;
                color: white;
            }
            QListWidget::item:hover {
                background-color: rgba(78, 158, 32, 150);
            }
        """)
        self.preset_list.currentItemChanged.connect(self.on_preset_selection_changed)
        self.preset_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preset_list.customContextMenuRequested.connect(self.on_preset_context_menu)
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
        self.action_set_list.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #4e9e20;
                color: white;
            }
            QListWidget::item:hover {
                background-color: rgba(78, 158, 32, 150);
            }
        """)
        self.action_set_list.currentItemChanged.connect(self.on_action_set_selection_changed)
        self.action_set_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.action_set_list.customContextMenuRequested.connect(self.on_action_set_context_menu)
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
        if index == 0:  # Presets tab
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
    
    def load_presets_from_db(self):
        selected_preset_id = self.current_preset['id'] if self.current_preset else None
        
        self.preset_list.clear()
        
        if self.current_platform_id is None:
            return
        
        try:
            presets = self.db.get_presets_by_platform(self.current_platform_id)
            for preset in presets:
                self.add_preset_to_list(preset)
            
            if selected_preset_id:
                for i in range(self.preset_list.count()):
                    item = self.preset_list.item(i)
                    preset_data = item.data(Qt.UserRole)
                    if preset_data and preset_data['id'] == selected_preset_id:
                        self.preset_list.setCurrentItem(item)
                        break
            elif self.preset_list.count() > 0:
                self.preset_list.setCurrentItem(self.preset_list.item(0))
        except Exception as e:
            print(f"Failed to load presets: {e}")
    
    def add_preset_to_list(self, preset_data):
        item = QListWidgetItem()
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        name_label = QLabel(preset_data["name"])
        name_label.setObjectName("presetNameLabel")
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        layout.addWidget(name_label)
        
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)
        
        steps_label = QLabel(f"{preset_data['steps']} steps")
        steps_label.setObjectName("presetStepsLabel")
        font = steps_label.font()
        font.setPointSize(10)
        steps_label.setFont(font)
        info_layout.addWidget(steps_label)
        
        preset_type = preset_data.get('type', '')
        if preset_type:
            # Scoped pill badge for type (Single Run / Batch)
            pill = QLabel(preset_type)
            pill.setObjectName("presetTypePill")
            pill.setFixedHeight(18)
            pill.setStyleSheet("""
                #presetTypePill {
                    background-color: #4e9e20;
                    color: white;
                    border-radius: 5px;
                    padding: 2px 8px;
                    font-size: 10px;
                }
            """)
            info_layout.addWidget(pill)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        widget.setLayout(layout)
        
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
                        label.setStyleSheet("""
                            #presetTypePill {
                                background-color: #4e9e20;
                                color: white;
                                border-radius: 5px;
                                padding: 2px 8px;
                                font-size: 10px;
                            }
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
                        label.setStyleSheet("""
                            #presetTypePill {
                                background-color: white;
                                color: #4e9e20;
                                border-radius: 5px;
                                padding: 2px 8px;
                                font-size: 10px;
                            }
                        """)
                    else:
                        label.setStyleSheet("color: white;")
            
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
            
            # Clear current selections before loading new platform data
            self.current_preset = None
            self.current_action_set = None
            
            # Clear lists
            self.preset_list.clear()
            self.action_set_list.clear()
            
            # Emit signal to parent to clear step and action lists FIRST
            self.platform_changed.emit(platform_id)
            
            # Load new platform data
            self.load_presets_from_db()
            self.load_action_sets_from_db()
            
            # Now manually select first item if available
            if self.tab_widget.currentIndex() == 0 and self.preset_list.count() > 0:
                first_item = self.preset_list.item(0)
                self.preset_list.setCurrentItem(first_item)
                # Manually trigger selection handler for proper styling
                self.on_preset_selection_changed(first_item, None)
            elif self.tab_widget.currentIndex() == 1 and self.action_set_list.count() > 0:
                first_item = self.action_set_list.item(0)
                self.action_set_list.setCurrentItem(first_item)
                # Manually trigger selection handler for proper styling
                self.on_action_set_selection_changed(first_item, None)
    
    def load_action_sets_from_db(self):
        selected_action_set_id = self.current_action_set['id'] if self.current_action_set else None
        
        self.action_set_list.clear()
        
        if self.current_platform_id is None:
            return
        
        try:
            action_sets = self.db.get_action_sets_by_platform(self.current_platform_id)
            for action_set in action_sets:
                self.add_action_set_to_list(action_set)
            
            if selected_action_set_id:
                for i in range(self.action_set_list.count()):
                    item = self.action_set_list.item(i)
                    action_set_data = item.data(Qt.UserRole)
                    if action_set_data and action_set_data['id'] == selected_action_set_id:
                        self.action_set_list.setCurrentItem(item)
                        break
            elif self.action_set_list.count() > 0:
                self.action_set_list.setCurrentItem(self.action_set_list.item(0))
        except Exception as e:
            print(f"Failed to load action sets: {e}")
    
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
        layout.addWidget(name_label)
        
        action_count = action_set_data.get('action_count', 0)
        count_label = QLabel(f"{action_count} actions")
        count_label.setObjectName("actionSetCountLabel")
        font = count_label.font()
        font.setPointSize(10)
        count_label.setFont(font)
        layout.addWidget(count_label)
        
        widget.setLayout(layout)
        
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
                    label.setStyleSheet("color: white;")
            
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
        
        global_pos = self.preset_list.viewport().mapToGlobal(pos)
        menu.exec_(global_pos)
    
    def on_export_preset(self, preset_data):
        """Export single preset to JSON"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Image_Tea_Action_Sequencer_{preset_data['name']}_{timestamp}.json"
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
        from datetime import datetime
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
            success, message, count = self.import_export_helper.import_presets(file_path)
            if success:
                QMessageBox.information(self, "Import Successful", message)
                self.load_presets_from_db()
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
        
        global_pos = self.action_set_list.viewport().mapToGlobal(pos)
        menu.exec_(global_pos)
    
    def on_export_action_set(self, action_set_data):
        """Export single action set to JSON"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Image_Tea_Action_Sequencer_{action_set_data['name']}_{timestamp}.json"
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
        from datetime import datetime
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
            success, message, count = self.import_export_helper.import_action_sets(file_path)
            if success:
                QMessageBox.information(self, "Import Successful", message)
                self.load_action_sets_from_db()
            else:
                QMessageBox.warning(self, "Import Failed", message)
