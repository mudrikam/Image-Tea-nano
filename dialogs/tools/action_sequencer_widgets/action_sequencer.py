import os
import time
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QComboBox, QFileDialog, QWidget, QMessageBox
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QColor
from config import BASE_PATH
from database.db_operation import ImageTeaDB
import subprocess
import qtawesome as qta
from .action_bar_widget import ActionBarWidget
from .preset_list_widget import PresetListWidget
from .step_list_widget import StepListWidget
from .status_bar_widget import StatusBarWidget
from .action_list_widget import ActionListWidget
from .action_settings_dialog import ActionSettingsDialog
from .add_preset_dialog import AddPresetDialog
from .add_action_dialog import AddActionDialog
from .free_presets_dialog import FreePresetsDialog
from helpers.tools.action_sequencer_helpers.action_sequencer_config_helper import ActionSequencerConfig
from helpers.tools.action_sequencer_helpers.action_sequencer_photoshop_jsx_helper import PhotoshopJSXGenerator
from helpers.tools.action_sequencer_helpers.action_sequencer_illustrator_jsx_helper import IllustratorJSXGenerator
from helpers.tools.action_sequencer_helpers.action_sequencer_file_watcher_helper import ActionSequencerFileWatcher
from ui.theme_system import theme


class BatchWorkerThread(QThread):
    progress_updated = Signal(int)
    status_updated = Signal(str)
    completed = Signal(int, int, bool)
    error_occurred = Signal(str)
    segment_started = Signal(int, int)
    delay_countdown = Signal(str)
    
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
        self.processed_count = 0
    
    def run(self):
        try:
            total_files = len(self.files)
            watcher = ActionSequencerFileWatcher(self.output_path, self.config_data)
            
            # Get all export steps in order
            preset_steps = self.db.get_preset_steps(self.preset_id)
            export_steps = []
            for step in preset_steps:
                action_detail = self.db.get_action_by_id(step['action_id'])
                if action_detail and action_detail.get('type') == 'Export':
                    export_steps.append({
                        'format': action_detail.get('export_format', 'PNG'),
                        'order': step['order_index']
                    })
            
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
                    process = subprocess.Popen([self.platform_exec, jsx_path], shell=False)
                
                print(f"Illustrator batch mode: JSX command sent for {total_files} files")
                print(f"Expecting {len(export_steps)} export(s) per file: {[e['format'] for e in export_steps]}")
                print("Watching output folder for completion...")
                
                for idx, file_path in enumerate(self.files):
                    if self.should_stop:
                        break
                    
                    self.status_updated.emit(f"Waiting for output {idx + 1} / {total_files}")
                    
                    if self.config_data.get('enable_file_watcher', True):
                        # Build expected filenames for all exports
                        expected_files = []
                        for export_step in export_steps:
                            expected_variants = watcher.build_expected_variants(
                                os.path.basename(file_path), 
                                export_step['format']
                            )
                            expected_files.append(expected_variants[0])  # Use first variant as primary
                        
                        watcher._log(f"Illustrator waiting for {len(expected_files)} files: {expected_files}")
                        
                        # Use watch_for_multiple_files to wait for all exports
                        output_files = watcher.watch_for_multiple_files(
                            expected_files,
                            existing_files=None,
                            stop_check=lambda: self.should_stop
                        )
                        
                        if len(output_files) == len(expected_files):
                            print(f"All {len(output_files)} outputs detected for {Path(file_path).name}")
                            watcher._log(f"All outputs detected: {output_files}")
                            self.processed_count += 1
                        else:
                            print(f"Only {len(output_files)}/{len(expected_files)} outputs detected for {Path(file_path).name}")
                            watcher._log(f"Incomplete outputs: got {len(output_files)}, expected {len(expected_files)}")
                    
                    self.progress_updated.emit(self.processed_count)
                
            else:
                # Photoshop batch processing
                existing_files = watcher.get_existing_files_snapshot()
                for idx, file_path in enumerate(self.files):
                    if self.should_stop:
                        break
                    
                    self.status_updated.emit(f"Processing {idx + 1} / {total_files}")
                    

                    
                    if self.platform_name == 'Photoshop':
                        generator = PhotoshopJSXGenerator()
                        jsx_result = generator.generate_jsx(
                            self.preset_id, 
                            [file_path], 
                            self.output_path, 
                            self.config_data,
                            is_single_run_with_file=False
                        )
                        
                        self._execute_jsx_with_delays(jsx_result)
                    
                    if self.config_data.get('enable_file_watcher', True):
                        # Build expected filenames for all exports
                        expected_files = []
                        for export_step in export_steps:
                            expected_variants = watcher.build_expected_variants(
                                os.path.basename(file_path), 
                                export_step['format']
                            )
                            expected_files.append(expected_variants[0])  # Use first variant as primary
                        
                        # Use watch_for_multiple_files for all cases (single or multiple exports)
                        output_files = watcher.watch_for_multiple_files(
                            expected_files,
                            existing_files,
                            stop_check=lambda: self.should_stop
                        )
                        
                        if len(output_files) == len(expected_files):
                            print(f"All {len(output_files)} output(s) detected for {Path(file_path).name}")
                            watcher._log(f"All outputs detected: {output_files}")
                            self.processed_count += 1
                        else:
                            print(f"Only {len(output_files)}/{len(expected_files)} output(s) detected")
                            watcher._log(f"Incomplete outputs: got {len(output_files)}, expected {len(expected_files)}")
                        existing_files.update(output_files)
                    
                    self.progress_updated.emit(self.processed_count)
                    time.sleep(0.5)
            
            jsx_illustrator_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'illustrator')
            jsx_photoshop_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'photoshop')
            watcher.cleanup_jsx_files(jsx_illustrator_dir, jsx_photoshop_dir)
            self.completed.emit(self.processed_count, len(self.files), self.should_stop) 
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def stop(self):
        self.should_stop = True
    
    def _execute_jsx_with_delays(self, jsx_result):
        """Execute JSX file(s) with delay handling.

        Args:
            jsx_result: Either a single JSX path (str) or list of tuples [(jsx_path, delay_ms), ...]
        """
        import threading

        if isinstance(jsx_result, str):
            self.segment_started.emit(0, 1)
            self.delay_countdown.emit("-")
            process = subprocess.Popen([self.platform_exec, jsx_result], shell=False)
            # Wait with timeout to prevent indefinite hang
            process_timeout = 300  # 5 minutes max per JSX execution
            try:
                process.wait(timeout=process_timeout)
            except subprocess.TimeoutExpired:
                self.error_occurred.emit(f"JSX execution timeout after {process_timeout}s")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                return
        elif isinstance(jsx_result, list):
            total_segments = len(jsx_result)
            for idx, (jsx_path, delay_ms) in enumerate(jsx_result):
                if self.should_stop:
                    break

                self.segment_started.emit(idx, total_segments)
                self.delay_countdown.emit("-")

                print(f"Executing JSX segment {idx + 1}/{total_segments}: {jsx_path}")
                process = subprocess.Popen([self.platform_exec, jsx_path], shell=False)

                # Wait with timeout using threading.Event to allow interruption
                process_finished = threading.Event()
                process_result = {'returncode': None, 'timed_out': False}

                def wait_process():
                    try:
                        process_result['returncode'] = process.wait(timeout=300)  # 5 min timeout
                    except subprocess.TimeoutExpired:
                        process_result['timed_out'] = True
                    finally:
                        process_finished.set()

                wait_thread = threading.Thread(target=wait_process, daemon=True)
                wait_thread.start()

                # Wait for process to finish or stop signal
                while not process_finished.is_set():
                    if self.should_stop:
                        try:
                            process.terminate()
                            process.wait(timeout=5)
                        except Exception:
                            try:
                                process.kill()
                            except Exception:
                                pass
                        return
                    process_finished.wait(timeout=0.1)

                if process_result['timed_out']:
                    self.error_occurred.emit(f"JSX segment {idx + 1} timeout after 300s")
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass
                    return

                if delay_ms > 0 and idx < total_segments - 1:
                    delay_seconds = delay_ms / 1000.0
                    print(f"Waiting {delay_seconds}s before next segment...")

                    # Use integer millisecond countdown to avoid floating-point accumulation errors
                    remaining_ms = delay_ms
                    while remaining_ms > 0 and not self.should_stop:
                        self.delay_countdown.emit(f"{remaining_ms / 1000.0:.1f}s")
                        # Sleep in 100ms chunks, or the remaining time if less
                        sleep_ms = min(100, remaining_ms)
                        time.sleep(sleep_ms / 1000.0)
                        remaining_ms -= sleep_ms

                    self.delay_countdown.emit("-")

class ActionSequencerDialog(QDialog):
    single_segment_started = Signal(int, int)
    single_delay_countdown = Signal(str)
    single_completed = Signal()
    
    # Supported file extensions for batch processing (Photoshop/Illustrator)
    SUPPORTED_EXTENSIONS = {'.ai', '.psd', '.png', '.eps', '.jpg', '.jpeg', '.svg', '.pdf', '.tif', '.tiff'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Sequencer")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        
        self.db = ImageTeaDB()
        self.loaded_files = []
        self.config = ActionSequencerConfig()
        self.batch_worker = None
        self.is_batch_paused = False
        self.current_platform_name = None
        self.last_processed_index = 0
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        self.connect_signals()
        self.apply_styles()
        self.action_bar_widget.disable_all_load_buttons()
        self.preset_list_widget.load_platforms_from_db()
        self.load_output_path()
        self.load_source_path()
        self.resize(700, 600)

    @staticmethod
    def _is_supported_file(filepath):
        """Check if file extension is supported for action sequencer processing."""
        ext = os.path.splitext(filepath)[1].lower()
        return ext in ActionSequencerDialog.SUPPORTED_EXTENSIONS

    def _load_files_from_folder(self, folder_path):
        """Recursively load supported files from folder into self.loaded_files."""
        self.loaded_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                filepath = os.path.join(root, file)
                if self._is_supported_file(filepath):
                    self.loaded_files.append(filepath)
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Header above action bar
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title row with icon and main title
        title_layout = QHBoxLayout()
        title_layout.setSpacing(4)
        
        dialog_icon = qta.icon('fa6s.list-check', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(24, 24))
        title_layout.addWidget(icon_label)
        
        title_label = QLabel("Action Sequencer")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {theme.get_color('primary')};")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        header_layout.addLayout(title_layout)
        
        # Subtitle with description
        subtitle_label = QLabel("Supercharge your workflow with professional automation. Create, manage, and run complex action sequences to save time and boost productivity. Perfect for batch processing and repetitive tasks.")
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"color: {theme.get_color('gray')}; padding-top: 4px;")
        header_layout.addWidget(subtitle_label)
        
        main_layout.addLayout(header_layout)
        
        self.action_bar_widget = ActionBarWidget()
        main_layout.addWidget(self.action_bar_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.preset_list_widget = PresetListWidget()
        self.preset_list_widget.setMinimumWidth(220)
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
        _prm_q = QColor(theme.get_color('primary'))
        _prm_rgb = f"{_prm_q.red()},{_prm_q.green()},{_prm_q.blue()}"
        self.setStyleSheet(f"""
            QListWidget {{
                outline: none;
            }}
            QListWidget#stepList, QListWidget#actionList {{
                outline: none;
            }}
            QListWidget#stepList::item, QListWidget#actionList::item {{
                border: none;
                padding: 0px;
            }}
            QListWidget#stepList::item:selected, QListWidget#actionList::item:selected {{
                background-color: transparent;
            }}
            QListWidget#stepList::item:hover, QListWidget#actionList::item:hover {{
                background-color: transparent;
            }}
            QListWidget::item {{
                border: none;
                outline: none;
            }}
            QListWidget::item:selected {{
                background-color: {theme.get_color('primary')};
                color: white;
                border: none;
                outline: none;
            }}
            QListWidget::item:hover {{
                background-color: rgba({_prm_rgb},0.39);
            }}
            QListWidget::item:focus {{
                outline: none;
                border: none;
            }}
        """)
    
    def connect_signals(self):
        self.action_bar_widget.load_from_database_requested.connect(self.on_load_from_database)
        self.action_bar_widget.select_source_requested.connect(self.on_select_source)
        self.action_bar_widget.select_file_requested.connect(self.on_select_file)
        self.action_bar_widget.settings_requested.connect(self.on_open_settings)
        self.action_bar_widget.output_path_changed.connect(self.on_output_path_changed)
        # New signals: manual/paste edits
        self.action_bar_widget.source_path_changed.connect(self.on_source_path_changed)
        self.action_bar_widget.file_path_changed.connect(self.on_file_path_changed)
        self.action_bar_widget.clear_source_requested.connect(self.on_clear_source)
        
        self.preset_list_widget.preset_selected.connect(self.on_preset_selected)
        self.preset_list_widget.add_preset_requested.connect(self.on_add_preset)
        self.preset_list_widget.edit_preset_requested.connect(self.on_edit_preset)
        self.preset_list_widget.remove_preset_requested.connect(self.on_remove_preset)
        self.preset_list_widget.action_set_selected.connect(self.on_action_set_selected)
        self.preset_list_widget.tab_changed.connect(self.on_tab_changed)
        self.preset_list_widget.settings_requested.connect(self.on_open_settings)
        self.preset_list_widget.platform_changed.connect(self.on_platform_changed)
        self.preset_list_widget.action_set_removed.connect(self.on_action_set_removed)
        
        self.step_list_widget.step_moved.connect(self.on_step_moved)
        self.step_list_widget.step_edit_requested.connect(self.on_edit_step)
        self.step_list_widget.step_delete_requested.connect(self.on_delete_step)
        self.step_list_widget.settings_requested.connect(self.on_open_settings)
        self.step_list_widget.action_added_to_preset.connect(self.on_action_added_to_preset)
        
        self.action_list_widget.action_modified.connect(self.on_action_modified)
        
        self.status_bar_widget.run_sequences_requested.connect(self.on_run_sequences)
        self.status_bar_widget.stop_process_requested.connect(self.on_stop_process)
        self.status_bar_widget.restart_process_requested.connect(self.on_restart_process)
        
        self.action_bar_widget.reset_requested.connect(self.on_reset_tool)
        self.action_bar_widget.get_free_presets_requested.connect(self.on_open_free_presets)
        
        self.single_segment_started.connect(self.on_segment_started)
        self.single_delay_countdown.connect(self.on_delay_countdown)
        self.single_completed.connect(self.on_single_mode_completed)
    
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
            # Clear step list if this is the currently displayed preset
            current = self.step_list_widget.current_preset
            if current and current.get('id') == preset_data['id']:
                self.step_list_widget.clear_steps()
                self.status_bar_widget.update_steps_count(0)
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

    def on_action_set_removed(self):
        """Clear the action list on the right pane when an action set is deleted."""
        self.action_list_widget.clear_actions()
        self.status_bar_widget.update_steps_count(0)
    
    def on_open_free_presets(self):
        current_platform_id = self.preset_list_widget.current_platform_id
        dlg = FreePresetsDialog(self, current_platform_id)
        dlg.preset_imported.connect(self.preset_list_widget.load_presets_from_db)
        dlg.exec()

    def on_load_from_database(self):
        all_files = self.db.get_all_files()
        self.loaded_files = []
        
        for file_row in all_files:
            filepath = file_row[1]
            if os.path.exists(filepath):
                self.loaded_files.append(filepath)
        
        self.status_bar_widget.update_files_count(len(self.loaded_files), 'database')
        self.action_bar_widget.clear_source_button.setEnabled(len(self.loaded_files) > 0)
        print(f"Loaded {len(self.loaded_files)} files from database")
    
    def on_select_source(self):
        home_dir = os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Source Folder",
            home_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self._load_files_from_folder(folder)
            self.status_bar_widget.update_files_count(len(self.loaded_files), 'manual')
            # update ActionBar display so user sees selected source folder
            self.action_bar_widget.set_source_path(folder)
            # Save source path to config
            self.config.set('source_path', folder)
            print(f"Loaded {len(self.loaded_files)} files from folder: {folder}")
    
    def on_select_file(self):
        home_dir = os.path.expanduser('~')
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            home_dir,
            "All Files (*.*)"
        )
        
        if file_path:
            self.loaded_files = [file_path]
            self.status_bar_widget.update_files_count(1, 'manual')
            # update ActionBar display so user sees selected file
            self.action_bar_widget.set_file_path(file_path)
            # Save file path to config (save as source_path)
            self.config.set('source_path', file_path)
            print(f"Loaded file: {file_path}")

    def on_source_path_changed(self, path):
        """Handle manual/paste changes to source path field."""
        path = (path or "").strip()
        if not path:
            self.loaded_files = []
            self.status_bar_widget.update_files_count(0, '')
            self.config.set('source_path', '')
            return

        if os.path.exists(path):
            if os.path.isdir(path):
                self._load_files_from_folder(path)
                self.status_bar_widget.update_files_count(len(self.loaded_files), 'manual')
                self.action_bar_widget.set_source_path(path)
                self.config.set('source_path', path)
                print(f"Loaded {len(self.loaded_files)} files from folder: {path}")
            else:
                self.loaded_files = [path]
                self.status_bar_widget.update_files_count(1, 'manual')
                self.action_bar_widget.set_file_path(path)
                self.config.set('source_path', path)
                print(f"Loaded file: {path}")
        else:
            QMessageBox.warning(self, "Source Path Not Found", f"The specified source path does not exist:\n{path}")
            print(f"Source path does not exist: {path}")

    def on_file_path_changed(self, path):
        """Handle manual/paste changes to file field."""
        path = (path or "").strip()
        if not path:
            self.loaded_files = []
            self.status_bar_widget.update_files_count(0, '')
            self.config.set('source_path', '')
            return

        if os.path.exists(path) and os.path.isfile(path):
            self.loaded_files = [path]
            self.status_bar_widget.update_files_count(1, 'manual')
            self.config.set('source_path', path)
            self.action_bar_widget.set_file_path(path)
            print(f"Loaded file: {path}")
        else:
            QMessageBox.warning(self, "File Not Found", f"The specified file does not exist:\n{path}")
            print(f"File path does not exist: {path}")
    
    def on_open_settings(self):
        dlg = ActionSettingsDialog(self)
        dlg.platforms_changed.connect(self.on_platforms_changed)
        dlg.output_settings_saved.connect(self.on_output_settings_saved)
        dlg.exec()

    def on_output_settings_saved(self, new_config):
        """Apply output-related settings immediately when saved from Settings dialog"""
        try:
            self.config = ActionSequencerConfig()
            self.load_output_path()
            print(f"Applied action sequencer settings: {new_config}")
        except Exception as e:
            print(f"Failed to apply new settings: {e}")
    
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
        
        if not self.is_batch_paused:
            self.status_bar_widget.reset_stats()
        
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
                # Check if files are loaded OR if source path is set
                if not self.loaded_files:
                    # Try to get source path from action bar
                    source_path = self.action_bar_widget.source_path_input.text().strip()
                    if source_path and os.path.exists(source_path):
                        # Load files from source path
                        if os.path.isdir(source_path):
                            print(f"Auto-loading files from source path: {source_path}")
                            self._load_files_from_folder(source_path)
                            self.status_bar_widget.update_files_count(len(self.loaded_files), 'manual')
                        else:
                            # Single file path
                            self.loaded_files = [source_path]
                            self.status_bar_widget.update_files_count(1, 'manual')
                if not self.loaded_files:
                    QMessageBox.warning(self, "No Files Loaded", "Please load files from database or select source folder for batch processing")
                    return
                
                self.run_batch_mode(preset_id, platform_name, exec_path, output_path, config_data, total_steps)
            else:
                is_single_with_file = len(self.loaded_files) > 0
                self.run_single_mode(preset_id, platform_name, exec_path, output_path, config_data, is_single_with_file)
        except Exception as e:
            print(f"Error running sequences: {e}")
            QMessageBox.critical(
                self,
                "Error Running Sequences",
                f"Failed to run sequence:\n\n{str(e)}\n\nMake sure the platform application is installed correctly and the executable path is configured."
            )
    
    def on_stop_process(self):
        print("Stop process requested")
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.stop()
            self.is_batch_paused = True
            self.status_bar_widget.update_status("Stopped")
            self.status_bar_widget.set_continue_mode()
            self.status_bar_widget.set_run_button_enabled(True)

    def on_restart_process(self):
        """Restart processing from the beginning (reset index to 0)."""
        print("Restart process requested - resetting to beginning")

        # Stop current worker if running
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.stop()
            self.batch_worker.wait()

        # Reset state
        self.is_batch_paused = False
        self.last_processed_index = 0

        # Reset UI
        self.status_bar_widget.hide_restart_button()
        self.status_bar_widget.reset_stats()
        self.step_list_widget.clear_all_highlights()

        print("Process reset to beginning - ready to start from file 1")
    
    def run_batch_mode(self, preset_id, platform_name, exec_path, output_path, config_data, total_steps):
        self.current_platform_name = platform_name
        
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.stop()
            self.batch_worker.wait()
        
        if self.is_batch_paused and self.last_processed_index > 0:
            files_to_process = self.loaded_files[self.last_processed_index:]
            print(f"Continuing from file {self.last_processed_index + 1}/{len(self.loaded_files)}")
        else:
            files_to_process = self.loaded_files
            self.last_processed_index = 0
            print(f"Starting batch processing of {len(files_to_process)} files")
        
        self.status_bar_widget.start_running_mode(len(self.loaded_files), total_steps, platform_name)
        self.status_bar_widget.set_run_button_enabled(True)
        
        self.batch_worker = BatchWorkerThread(
            files_to_process,
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
        self.batch_worker.segment_started.connect(self.on_segment_started)
        self.batch_worker.delay_countdown.connect(self.on_delay_countdown)
        
        self.batch_worker.start()
    
    def run_single_mode(self, preset_id, platform_name, exec_path, output_path, config_data, is_single_with_file):
        generator = None
        if platform_name == 'Photoshop':
            generator = PhotoshopJSXGenerator()
            jsx_result = generator.generate_jsx(
                preset_id, 
                self.loaded_files if is_single_with_file else [], 
                output_path, 
                config_data,
                is_single_run_with_file=is_single_with_file
            )
            
            if isinstance(jsx_result, str):
                if not os.path.exists(jsx_result):
                    raise Exception(f"JSX file not found at: {jsx_result}")
                print(f"Launching {platform_name} with JSX: {jsx_result}")
                self.single_segment_started.emit(0, 1)
                self.single_delay_countdown.emit("-")
                
                # Execute JSX and WAIT for it to complete (not fire-and-forget)
                import subprocess
                process_timeout = 300  # 5 minutes max
                try:
                    print(f"Waiting for {platform_name} to complete JSX execution...")
                    result = subprocess.run([exec_path, jsx_result], timeout=process_timeout)
                    print(f"{platform_name} JSX completed with return code: {result.returncode}")
                except subprocess.TimeoutExpired:
                    print(f"ERROR: JSX execution timeout after {process_timeout}s")
                    self.status_bar_widget.update_status("Timeout")
                except Exception as e:
                    print(f"ERROR: Failed to execute JSX: {e}")
                    self.status_bar_widget.update_status("Error")
                
                self.single_completed.emit()
            elif isinstance(jsx_result, list):
                print(f"Launching {platform_name} with {len(jsx_result)} JSX segments (delayed execution)")
                self._run_split_jsx_async(exec_path, jsx_result)
            
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
                self.single_completed.emit()
            else:
                if not jsx_path or not os.path.exists(jsx_path):
                    raise Exception(f"Resident JSX not found at: {jsx_path}")
                
                norm_exec = os.path.normpath(exec_path)
                norm_jsx = os.path.normpath(jsx_path)
                
                print(f"Launching Illustrator with resident script...")
                subprocess.Popen([norm_exec, norm_jsx], shell=False)
                print("Illustrator process started")
                self.single_completed.emit()
        else:
            QMessageBox.warning(self, "Platform Not Supported", f"Platform {platform_name} is not supported yet")
            return
        
        self.status_bar_widget.update_status("Running")
    
    def _run_split_jsx_async(self, exec_path, jsx_segments):
        """Run split JSX files with delays in background thread.

        Args:
            exec_path: Path to Photoshop executable
            jsx_segments: List of tuples [(jsx_path, delay_ms), ...]
        """
        import threading

        def run_segments():
            total_segments = len(jsx_segments)
            for idx, (jsx_path, delay_ms) in enumerate(jsx_segments):
                self.single_segment_started.emit(idx, total_segments)
                self.single_delay_countdown.emit("-")

                print(f"Executing JSX segment {idx + 1}/{total_segments}: {jsx_path}")
                process = subprocess.Popen([exec_path, jsx_path], shell=False)

                # Wait with timeout to prevent indefinite hang
                process_timeout = 300  # 5 minutes max per JSX execution
                try:
                    process.wait(timeout=process_timeout)
                except subprocess.TimeoutExpired:
                    print(f"ERROR: JSX segment {idx + 1} timeout after {process_timeout}s")
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass
                    break

                if delay_ms > 0 and idx < total_segments - 1:
                    delay_seconds = delay_ms / 1000.0
                    print(f"Waiting {delay_seconds}s before next segment...")

                    # Use integer millisecond countdown to avoid floating-point accumulation errors
                    remaining_ms = delay_ms
                    while remaining_ms > 0:
                        self.single_delay_countdown.emit(f"{remaining_ms / 1000.0:.1f}s")
                        # Sleep in 100ms chunks, or the remaining time if less
                        sleep_ms = min(100, remaining_ms)
                        time.sleep(sleep_ms / 1000.0)
                        remaining_ms -= sleep_ms

                    self.single_delay_countdown.emit("-")

            print("All JSX segments completed")
            self.single_completed.emit()

        thread = threading.Thread(target=run_segments, daemon=True)
        thread.start()

    def on_batch_progress(self, processed_files):
        absolute_progress = self.last_processed_index + processed_files
        self.status_bar_widget.update_running_progress(absolute_progress)
    
    def on_batch_status(self, status):
        print(f"Batch status: {status}")
    
    def on_batch_completed(self, processed_count, total_files, was_stopped):
        self.last_processed_index = self.last_processed_index + processed_count
        
        self.step_list_widget.clear_all_highlights()
        self.status_bar_widget.update_delay("-")
        
        if was_stopped:
            self.is_batch_paused = True
            self.status_bar_widget.set_continue_mode()
            self.status_bar_widget.set_run_button_enabled(True)
            QMessageBox.information(self, "Batch Stopped", 
                                  f"Batch processing stopped.\n\n"
                                  f"Processed: {self.last_processed_index}/{len(self.loaded_files)} files\n"
                                  f"Click 'Continue Process' to resume.")
        else:
            self.is_batch_paused = False
            processed_this_run = self.last_processed_index
            self.last_processed_index = 0
            self.status_bar_widget.end_running_mode()
            self.status_bar_widget.set_run_button_enabled(True)
            QMessageBox.information(self, "Batch Completed", 
                                  f"Batch processing finished.\n\n"
                                  f"Successfully processed: {processed_this_run}/{len(self.loaded_files)} files")
    
    def on_batch_error(self, error_msg):
        self.step_list_widget.clear_all_highlights()
        self.status_bar_widget.update_delay("-")
        self.status_bar_widget.update_status("Error")
        self.status_bar_widget.end_running_mode()
        self.status_bar_widget.set_run_button_enabled(True)
        QMessageBox.critical(self, "Batch Error", f"Error during batch processing:\n{error_msg}")
    
    def on_segment_started(self, segment_index, total_segments):
        """Handle saat segment JSX dimulai untuk highlight steps"""
        self.step_list_widget.highlight_steps_by_segment(segment_index, total_segments)
    
    def on_delay_countdown(self, delay_text):
        """Handle delay countdown untuk update status bar"""
        self.status_bar_widget.update_delay(delay_text)
    
    def on_single_mode_completed(self):
        """Handle saat single mode selesai"""
        self.step_list_widget.clear_all_highlights()
        self.status_bar_widget.update_delay("-")
        self.status_bar_widget.update_status("Idle")
        
        jsx_illustrator_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'illustrator')
        jsx_photoshop_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'photoshop')
        ActionSequencerFileWatcher.cleanup_jsx_files(jsx_illustrator_dir, jsx_photoshop_dir)
    
    def load_output_path(self):
        output_path = self.config.get('output_path', '')
        if output_path:
            self.action_bar_widget.set_output_path(output_path)
    
    def load_source_path(self):
        source_path = self.config.get('source_path', '')
        if source_path and os.path.exists(source_path):
            try:
                if os.path.isdir(source_path):
                    self.action_bar_widget.set_source_path(source_path)
                else:
                    self.action_bar_widget.set_file_path(source_path)
                print(f"Loaded saved source path: {source_path}")
            except Exception as e:
                print(f"Error loading source path: {e}")
    
    def on_output_path_changed(self, path):
        """Save output path and create directory if missing."""
        if not path:
            self.config.set('output_path', '')
            return

        # Create output directory if it does not exist
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                print(f"Created output directory: {path}")
            except OSError as e:
                QMessageBox.critical(self, "Create Output Path Failed", f"Could not create output directory:\n{path}\n\n{e}")
                return

        self.config.set('output_path', path)
        # keep UI in sync
        try:
            self.action_bar_widget.set_output_path(path)
        except Exception as e:
            print(f"Failed to set output path in UI: {e}")
    
    def on_reset_tool(self):
        print("Clear All requested")

        if self.batch_worker:
            try:
                self.batch_worker.progress_updated.disconnect(self.on_batch_progress)
                self.batch_worker.status_updated.disconnect(self.on_batch_status)
                self.batch_worker.completed.disconnect(self.on_batch_completed)
                self.batch_worker.error_occurred.disconnect(self.on_batch_error)
                self.batch_worker.segment_started.disconnect(self.on_segment_started)
                self.batch_worker.delay_countdown.disconnect(self.on_delay_countdown)
            except Exception:
                pass
            if self.batch_worker.isRunning():
                self.batch_worker.stop()

        self.batch_worker = None
        self.loaded_files = []
        self.is_batch_paused = False
        self.current_platform_name = None
        self.last_processed_index = 0

        self.status_bar_widget.reset_to_idle()
        self.status_bar_widget.reset_stats()
        self.status_bar_widget.set_run_button_enabled(True)
        self.status_bar_widget.update_files_count(0, '')

        # Get source path from config
        source_path = self.config.get('source_path', '')
        
        try:
            self.action_bar_widget.set_source_path("")
            self.action_bar_widget.set_file_path("")
        except Exception:
            pass
        self.action_bar_widget.disable_all_load_buttons()

        # Reload files from source path if configured
        if source_path and os.path.exists(source_path):
            if os.path.isdir(source_path):
                print(f"Reloading files from source path: {source_path}")
                self._load_files_from_folder(source_path)
                self.status_bar_widget.update_files_count(len(self.loaded_files), 'manual')
                try:
                    self.action_bar_widget.set_source_path(source_path)
                except Exception:
                    pass
            else:
                # Single file
                self.loaded_files = [source_path]
                self.status_bar_widget.update_files_count(1, 'manual')
                try:
                    self.action_bar_widget.set_file_path(source_path)
                except Exception:
                    pass
        
        self.action_bar_widget.enable_load_buttons()

        print("Tool cleared and reloaded to initial state")

    def on_clear_source(self):
        """Clear only the source and selected file (do not clear output or other settings)."""
        print("Clear Source requested")
        self.loaded_files = []
        try:
            self.action_bar_widget.set_source_path("")
            self.action_bar_widget.set_file_path("")
        except Exception:
            pass
        try:
            self.status_bar_widget.update_files_count(0, '')
        except Exception:
            pass
        # Remove source_path from config
        self.config.set('source_path', '')
        print("Source cleared")

    def closeEvent(self, event):
        """Ensure generated JSX files are cleaned up when dialog closes."""
        # Stop any running batch worker thread
        if hasattr(self, 'batch_worker') and self.batch_worker and self.batch_worker.isRunning():
            print("Stopping batch worker thread...")
            self.batch_worker.stop()
            self.batch_worker.wait(3000)  # Wait up to 3 seconds
            if self.batch_worker.isRunning():
                print("Batch worker thread still running after timeout")
            else:
                print("Batch worker thread stopped")
        
        try:
            jsx_illustrator_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'illustrator')
            jsx_photoshop_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'photoshop')
            ActionSequencerFileWatcher.cleanup_jsx_files(jsx_illustrator_dir, jsx_photoshop_dir)
            print("Action Sequencer: cleaned up generated JSX files on close")
        except Exception as e:
            print(f"Action Sequencer: failed to cleanup JSX files on close: {e}")
        # continue with normal close
        super().closeEvent(event)
