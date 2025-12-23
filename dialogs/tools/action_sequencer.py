import os
import time
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QComboBox, QFileDialog, QWidget, QMessageBox
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont
from config import BASE_PATH
from database.db_operation import ImageTeaDB
from dialogs.tools.action_sequencer_widgets import (ActionBarWidget, PresetListWidget, 
                                                     StepListWidget, StatusBarWidget, ActionListWidget)
from dialogs.tools.action_settings_dialog import ActionSettingsDialog
from dialogs.tools.add_preset_dialog import AddPresetDialog
from dialogs.tools.add_action_set_dialog import AddActionSetDialog
from dialogs.tools.add_action_dialog import AddActionDialog
from helpers.tools.action_sequencer_helpers.action_sequencer_config_helper import ActionSequencerConfig
from helpers.tools.action_sequencer_helpers.action_sequencer_photoshop_jsx_helper import PhotoshopJSXGenerator
from helpers.tools.action_sequencer_helpers.action_sequencer_illustrator_jsx_helper import IllustratorJSXGenerator
from helpers.tools.action_sequencer_helpers.action_sequencer_file_watcher_helper import ActionSequencerFileWatcher


class BatchWorkerThread(QThread):
    progress_updated = Signal(int)
    status_updated = Signal(str)
    completed = Signal()
    error_occurred = Signal(str)
    
    def __init__(self, files, preset_id, platform_name, platform_exec, output_path, config_data, db):
        super().__init__()
        self.files = files
        self.preset_id = preset_id
        self.platform_name = platform_name
        self.platform_exec = platform_exec
        self.output_path = output_path
        self.config_data = config_data
        self.db = db
        self.should_stop = False
    
    def run(self):
        try:
            total_files = len(self.files)
            watcher = ActionSequencerFileWatcher(self.output_path, self.config_data)
            
            preset_steps = self.db.get_preset_steps(self.preset_id)
            export_format = None
            for step in preset_steps:
                action_detail = self.db.get_action_by_id(step['action_id'])
                if action_detail and action_detail.get('type') == 'Export':
                    export_format = action_detail.get('export_format', 'PNG')
                    break
            
            if self.platform_name == 'Illustrator':
                generator = IllustratorJSXGenerator(self.platform_exec)
                jsx_result = generator.generate_jsx(
                    self.preset_id, 
                    self.files, 
                    self.output_path, 
                    self.config_data,
                    is_single_run_with_file=False
                )
                
                jsx_path, is_resident = jsx_result
                
                if not is_resident and jsx_path:
                    import subprocess
                    process = subprocess.Popen([self.platform_exec, jsx_path], shell=False)
                
                print(f"Illustrator batch mode: JSX command sent for {total_files} files")
                print("Watching output folder for completion...")
                
                for idx, file_path in enumerate(self.files):
                    if self.should_stop:
                        break
                    
                    self.status_updated.emit(f"Waiting for output {idx + 1} / {total_files}")
                    
                    if self.config_data.get('enable_file_watcher', True):
                        expected_filename = watcher.build_expected_filename(os.path.basename(file_path), export_format)
                        
                        max_wait = 60
                        start_wait = time.time()
                        output_file = None
                        
                        while time.time() - start_wait < max_wait:
                            current_files = set(watcher._get_all_files())
                            
                            for cf in current_files:
                                if Path(cf).name == expected_filename:
                                    if watcher._is_file_stable(cf, stable_duration=0.2):
                                        output_file = cf
                                        break
                            
                            if output_file:
                                break
                            
                            time.sleep(0.3)
                        
                        if output_file:
                            print(f"Output detected: {output_file}")
                        else:
                            print(f"Output not detected: {expected_filename}")
                    
                    self.progress_updated.emit(idx + 1)
                
            else:
                for idx, file_path in enumerate(self.files):
                    if self.should_stop:
                        break
                    
                    self.status_updated.emit(f"Processing {idx + 1} / {total_files}")
                    
                    existing_files = watcher.get_existing_files_snapshot()
                    
                    if self.platform_name == 'Photoshop':
                        generator = PhotoshopJSXGenerator()
                        jsx_path = generator.generate_jsx(
                            self.preset_id, 
                            [file_path], 
                            self.output_path, 
                            self.config_data,
                            is_single_run_with_file=False
                        )
                        
                        import subprocess
                        process = subprocess.Popen([self.platform_exec, jsx_path], shell=False)
                        process.wait()
                    
                    if self.config_data.get('enable_file_watcher', True):
                        expected_filename = watcher.build_expected_filename(os.path.basename(file_path), export_format)
                        output_file = watcher.watch_for_file(expected_filename, existing_files)
                        
                        if output_file:
                            print(f"Output file detected: {output_file}")
                        else:
                            print(f"Output file not detected within timeout")
                    
                    self.progress_updated.emit(idx + 1)
                    time.sleep(0.5)
            
            jsx_illustrator_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'illustrator')
            jsx_photoshop_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'photoshop')
            watcher.cleanup_jsx_files(jsx_illustrator_dir, jsx_photoshop_dir)
            
            self.completed.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def stop(self):
        self.should_stop = True

class ActionSequencerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Sequencer")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        
        self.db = ImageTeaDB()
        self.loaded_files = []
        self.config = ActionSequencerConfig()
        self.batch_worker = None
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        self.connect_signals()
        self.apply_styles()
        self.action_bar_widget.disable_all_load_buttons()
        self.preset_list_widget.load_platforms_from_db()
        self.load_output_path()
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
        self.action_bar_widget.output_path_changed.connect(self.on_output_path_changed)
        
        self.preset_list_widget.preset_selected.connect(self.on_preset_selected)
        self.preset_list_widget.add_preset_requested.connect(self.on_add_preset)
        self.preset_list_widget.edit_preset_requested.connect(self.on_edit_preset)
        self.preset_list_widget.remove_preset_requested.connect(self.on_remove_preset)
        self.preset_list_widget.action_set_selected.connect(self.on_action_set_selected)
        self.preset_list_widget.tab_changed.connect(self.on_tab_changed)
        self.preset_list_widget.settings_requested.connect(self.on_open_settings)
        self.preset_list_widget.platform_changed.connect(self.on_platform_changed)
        
        self.step_list_widget.step_moved.connect(self.on_step_moved)
        self.step_list_widget.step_edit_requested.connect(self.on_edit_step)
        self.step_list_widget.step_delete_requested.connect(self.on_delete_step)
        self.step_list_widget.settings_requested.connect(self.on_open_settings)
        self.step_list_widget.action_added_to_preset.connect(self.on_action_added_to_preset)
        
        self.action_list_widget.action_modified.connect(self.on_action_modified)
        
        self.status_bar_widget.run_sequences_requested.connect(self.on_run_sequences)
        self.status_bar_widget.stop_process_requested.connect(self.on_stop_process)
    
    def on_platform_changed(self, platform_id):
        """Clear all loaded data when platform changes"""
        print(f"Platform changed to ID: {platform_id}")
        self.step_list_widget.clear_steps()
        self.action_list_widget.clear_actions()
        self.action_bar_widget.disable_all_load_buttons()
        self.status_bar_widget.update_steps_count(0)
        self.loaded_files = []
        self.status_bar_widget.update_files_count(0, '')
    
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
            self.preset_list_widget.load_presets_from_db()
    
    def on_action_added_to_preset(self):
        self.preset_list_widget.load_presets_from_db()
    
    def on_action_modified(self):
        self.preset_list_widget.load_action_sets_from_db()
    
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
    
    def on_run_sequences(self):
        print("Run sequences requested")
        
        selected_preset = self.preset_list_widget.get_selected_preset()
        if not selected_preset:
            QMessageBox.warning(self, "No Preset Selected", "Please select a preset before running")
            return
        
        preset_id = selected_preset['id']
        platform_id = selected_preset.get('platform_id')
        preset_type = selected_preset.get('type', 'Batch')
        
        platform_data = self.db.get_platform_by_id(platform_id)
        if not platform_data:
            QMessageBox.warning(self, "Platform Not Found", "Platform data not found in database")
            return
        
        platform_name = platform_data.get('name', 'Photoshop')
        
        exec_path = platform_data.get('exec_path', '')
        if not exec_path or not os.path.exists(exec_path):
            QMessageBox.warning(self, "Platform Not Configured", f"Platform executable path not configured or not found.\nPlease set the exe path in Settings.")
            return
        
        output_path = self.config.get('output_path', '')
        if not output_path:
            QMessageBox.warning(self, "No Output Path", "Please set output path in Action Bar")
            return
        
        config_data = {
            'output_prefix': self.config.get('output_prefix', ''),
            'output_suffix': self.config.get('output_suffix', ''),
            'enable_file_watcher': self.config.get('enable_file_watcher', True),
            'watch_timeout': self.config.get('watch_timeout', 30)
        }
        
        total_steps = selected_preset.get('steps', 0)
        
        try:
            if preset_type == 'Batch':
                if not self.loaded_files:
                    QMessageBox.warning(self, "No Files Loaded", "Please load files from database or select source folder for batch processing")
                    return
                
                self.run_batch_mode(preset_id, platform_name, exec_path, output_path, config_data, total_steps)
            else:
                is_single_with_file = len(self.loaded_files) > 0
                self.run_single_mode(preset_id, platform_name, exec_path, output_path, config_data, is_single_with_file)
        except Exception as e:
            print(f"Error running sequences: {e}")
    
    def on_stop_process(self):
        print("Stop process requested")
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.stop()
            self.status_bar_widget.update_status("Stopped")
            self.status_bar_widget.end_running_mode()
            self.status_bar_widget.set_run_button_enabled(True)
    
    def run_batch_mode(self, preset_id, platform_name, exec_path, output_path, config_data, total_steps):
        self.status_bar_widget.start_running_mode(len(self.loaded_files), total_steps)
        self.status_bar_widget.set_run_button_enabled(True)
        
        self.batch_worker = BatchWorkerThread(
            self.loaded_files,
            preset_id,
            platform_name,
            exec_path,
            output_path,
            config_data,
            self.db
        )
        
        self.batch_worker.progress_updated.connect(self.on_batch_progress)
        self.batch_worker.status_updated.connect(self.on_batch_status)
        self.batch_worker.completed.connect(self.on_batch_completed)
        self.batch_worker.error_occurred.connect(self.on_batch_error)
        
        self.batch_worker.start()
    
    def run_single_mode(self, preset_id, platform_name, exec_path, output_path, config_data, is_single_with_file):
        generator = None
        if platform_name == 'Photoshop':
            generator = PhotoshopJSXGenerator()
            jsx_path = generator.generate_jsx(
                preset_id, 
                self.loaded_files if is_single_with_file else [], 
                output_path, 
                config_data,
                is_single_run_with_file=is_single_with_file
            )
            
            if not os.path.exists(jsx_path):
                raise Exception(f"JSX file not found at: {jsx_path}")
            
            print(f"Launching {platform_name} with JSX: {jsx_path}")
            import subprocess
            subprocess.Popen([exec_path, jsx_path], shell=False)
            
        elif platform_name == 'Illustrator':
            generator = IllustratorJSXGenerator(exec_path)
            jsx_result = generator.generate_jsx(
                preset_id, 
                self.loaded_files if is_single_with_file else [], 
                output_path, 
                config_data,
                is_single_run_with_file=is_single_with_file
            )
            
            jsx_path, is_resident = jsx_result
            
            if is_resident:
                print("Command sent to resident Illustrator")
            else:
                if not jsx_path or not os.path.exists(jsx_path):
                    raise Exception(f"Resident JSX not found at: {jsx_path}")
                
                norm_exec = os.path.normpath(exec_path)
                norm_jsx = os.path.normpath(jsx_path)
                
                print(f"Launching Illustrator with resident script...")
                import subprocess
                subprocess.Popen([norm_exec, norm_jsx], shell=False)
                print("Illustrator process started")
        else:
            QMessageBox.warning(self, "Platform Not Supported", f"Platform {platform_name} is not supported yet")
            return
        
        self.status_bar_widget.update_status("Running")
    
    def on_batch_progress(self, processed_files):
        self.status_bar_widget.update_running_progress(processed_files)
    
    def on_batch_status(self, status):
        print(f"Batch status: {status}")
    
    def on_batch_completed(self):
        self.status_bar_widget.end_running_mode()
        self.status_bar_widget.set_run_button_enabled(True)
        QMessageBox.information(self, "Batch Completed", f"Successfully processed {len(self.loaded_files)} files")
    
    def on_batch_error(self, error_msg):
        self.status_bar_widget.update_status("Error")
        self.status_bar_widget.end_running_mode()
        self.status_bar_widget.set_run_button_enabled(True)
        QMessageBox.critical(self, "Batch Error", f"Error during batch processing:\n{error_msg}")
    
    def load_output_path(self):
        output_path = self.config.get('output_path', '')
        if output_path:
            self.action_bar_widget.set_output_path(output_path)
    
    def on_output_path_changed(self, path):
        self.config.set('output_path', path)
