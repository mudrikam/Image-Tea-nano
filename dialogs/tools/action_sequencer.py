import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QComboBox, QFileDialog, QWidget, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont
from config import BASE_PATH
from database.db_operation import ImageTeaDB
from dialogs.tools.action_sequencer_widgets import (ActionBarWidget, PresetListWidget, 
                                                     StepListWidget, StatusBarWidget, ActionListWidget)
from dialogs.tools.action_settings_dialog import ActionSettingsDialog
from dialogs.tools.add_preset_dialog import AddPresetDialog
from dialogs.tools.add_action_set_dialog import AddActionSetDialog
from dialogs.tools.add_action_dialog import AddActionDialog

class ActionSequencerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Sequencer")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        
        self.db = ImageTeaDB()
        self.loaded_files = []
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        self.connect_signals()
        self.apply_styles()
        self.action_bar_widget.disable_all_load_buttons()
        self.preset_list_widget.load_platforms_from_db()
        self.resize(700, 600)
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        self.action_bar_widget = ActionBarWidget()
        main_layout.addWidget(self.action_bar_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.preset_list_widget = PresetListWidget()
        self.preset_list_widget.setMinimumWidth(220)
        self.preset_list_widget.setMaximumWidth(300)
        splitter.addWidget(self.preset_list_widget)
        
        self.step_list_widget = StepListWidget()
        self.action_list_widget = ActionListWidget()
        self.action_list_widget.hide()
        
        right_container = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.step_list_widget)
        right_layout.addWidget(self.action_list_widget)
        right_container.setLayout(right_layout)
        
        splitter.addWidget(right_container)
        
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter, 1)
        
        self.status_bar_widget = StatusBarWidget()
        main_layout.addWidget(self.status_bar_widget, 0)
        
        self.setLayout(main_layout)
    
    def apply_styles(self):
        self.setStyleSheet("""
            QListWidget {
                outline: none;
            }
            QListWidget#stepList, QListWidget#actionList {
                outline: none;
            }
            QListWidget#stepList::item, QListWidget#actionList::item {
                border: none;
                padding: 0px;
            }
            QListWidget#stepList::item:selected, QListWidget#actionList::item:selected {
                background-color: transparent;
            }
            QListWidget#stepList::item:hover, QListWidget#actionList::item:hover {
                background-color: transparent;
            }
            QListWidget::item {
                border: none;
                outline: none;
            }
            QListWidget::item:selected {
                background-color: #4e9e20;
                color: white;
                border: none;
                outline: none;
            }
            QListWidget::item:hover {
                background-color: rgba(78, 158, 32, 100);
            }
            QListWidget::item:focus {
                outline: none;
                border: none;
            }
        """)
    
    def connect_signals(self):
        self.action_bar_widget.load_from_database_requested.connect(self.on_load_from_database)
        self.action_bar_widget.select_source_requested.connect(self.on_select_source)
        self.action_bar_widget.select_file_requested.connect(self.on_select_file)
        self.action_bar_widget.settings_requested.connect(self.on_open_settings)
        
        self.preset_list_widget.preset_selected.connect(self.on_preset_selected)
        self.preset_list_widget.add_preset_requested.connect(self.on_add_preset)
        self.preset_list_widget.edit_preset_requested.connect(self.on_edit_preset)
        self.preset_list_widget.remove_preset_requested.connect(self.on_remove_preset)
        self.preset_list_widget.action_set_selected.connect(self.on_action_set_selected)
        self.preset_list_widget.tab_changed.connect(self.on_tab_changed)
        self.preset_list_widget.settings_requested.connect(self.on_open_settings)
        
        self.step_list_widget.step_moved.connect(self.on_step_moved)
        self.step_list_widget.step_edit_requested.connect(self.on_edit_step)
        self.step_list_widget.step_delete_requested.connect(self.on_delete_step)
        self.step_list_widget.settings_requested.connect(self.on_open_settings)
        
        self.status_bar_widget.run_actions_requested.connect(self.on_run_actions)
    
    def on_tab_changed(self, index):
        if index == 0:
            self.action_list_widget.hide()
            self.step_list_widget.show()
            if self.preset_list_widget.current_preset:
                self.on_preset_selected(self.preset_list_widget.current_preset)
            else:
                self.action_bar_widget.disable_all_load_buttons()
        else:
            self.step_list_widget.hide()
            self.action_list_widget.show()
            self.action_bar_widget.disable_all_load_buttons()
            if self.preset_list_widget.current_action_set:
                self.on_action_set_selected(self.preset_list_widget.current_action_set)
    
    def on_preset_selected(self, preset_data):
        print(f"Preset selected: {preset_data['name']}")
        platform_id = self.preset_list_widget.current_platform_id
        self.step_list_widget.load_preset_steps(preset_data, platform_id)
        self.step_list_widget.show()
        self.action_list_widget.hide()
        self.status_bar_widget.update_steps_count(preset_data['steps'])
        
        preset_type = preset_data.get('type', 'batch')
        self.action_bar_widget.set_preset_type(preset_type)
    
    def on_action_set_selected(self, action_set_data):
        print(f"Action set selected: {action_set_data['name']}")
        self.action_list_widget.load_actions_for_action_set(action_set_data)
        self.action_list_widget.show()
        self.step_list_widget.hide()
        self.status_bar_widget.update_steps_count(action_set_data['action_count'])
        self.action_bar_widget.disable_all_load_buttons()
    
    def on_add_preset(self):
        if self.preset_list_widget.current_platform_id is None:
            self.on_open_settings()
            return
        
        from dialogs.tools.add_preset_dialog import AddPresetDialog
        dlg = AddPresetDialog(self.preset_list_widget.current_platform_id, parent=self)
        dlg.preset_saved.connect(self.preset_list_widget.load_presets_from_db)
        dlg.exec()
    
    def on_edit_preset(self, preset_data):
        dlg = AddPresetDialog(self.preset_list_widget.current_platform_id, preset_data, parent=self)
        dlg.preset_saved.connect(self.preset_list_widget.load_presets_from_db)
        dlg.exec()
    
    def on_remove_preset(self, preset_data):
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove preset '{preset_data['name']}'?\nAll steps in this preset will also be deleted.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db.delete_preset(preset_data['id'])
            self.preset_list_widget.load_presets_from_db()
    
    def on_step_moved(self, from_order, to_order):
        print(f"Step moved from {from_order} to {to_order}")
    
    def on_edit_step(self, step_data):
        action_id = step_data['action_id']
        action = self.db.get_action_by_id(action_id)
        dlg = AddActionDialog(action['action_set_id'], action, parent=self)
        dlg.action_saved.connect(lambda: self.step_list_widget.load_preset_steps(self.step_list_widget.current_preset))
        dlg.exec()
    
    def on_delete_step(self, step_data):
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to remove '{step_data['name']}' from this preset?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db.delete_preset_step(step_data['id'])
            self.step_list_widget.load_preset_steps(self.step_list_widget.current_preset)
    
    def on_load_from_database(self):
        all_files = self.db.get_all_files()
        self.loaded_files = []
        
        for file_row in all_files:
            filepath = file_row[1]
            if os.path.exists(filepath):
                self.loaded_files.append(filepath)
        
        self.status_bar_widget.update_files_count(len(self.loaded_files), 'database')
        print(f"Loaded {len(self.loaded_files)} files from database")
    
    def on_select_source(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Source Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.loaded_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    filepath = os.path.join(root, file)
                    self.loaded_files.append(filepath)
            
            self.status_bar_widget.update_files_count(len(self.loaded_files), 'manual')
            print(f"Loaded {len(self.loaded_files)} files from folder: {folder}")
    
    def on_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "All Files (*.*)"
        )
        
        if file_path:
            self.loaded_files = [file_path]
            self.status_bar_widget.update_files_count(1, 'manual')
            print(f"Loaded file: {file_path}")
    
    def on_open_settings(self):
        dlg = ActionSettingsDialog(self)
        dlg.platforms_changed.connect(self.on_platforms_changed)
        dlg.exec()
    
    def on_platforms_changed(self):
        self.preset_list_widget.load_platforms_from_db()
    
    def load_platforms_from_db(self):
        self.preset_list_widget.load_platforms_from_db()
    
    def on_run_actions(self):
        print("Run actions requested")
        self.status_bar_widget.update_status("Running")
        self.status_bar_widget.update_progress(0)
