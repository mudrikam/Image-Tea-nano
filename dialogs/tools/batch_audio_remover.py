from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QLabel, QSplitter, QWidget,
    QProgressBar, QFileDialog, QGridLayout, QFrame, QSpacerItem, QSizePolicy,
    QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor
import qtawesome as qta
import os
import time
import json
from datetime import datetime
from config import BASE_PATH
from database.db_operation import ImageTeaDB
from helpers.tools.batch_audio_remover_helper import (
    scan_directory_for_videos,
    is_video_file,
    check_gpu_support,
    remove_audio_from_video
)
from ui.theme_system import theme


class AudioRemovalWorker(QThread):
    progress_updated = Signal(int)
    file_processed = Signal(str, str)
    all_finished = Signal()
    
    def __init__(self, source_files, destination_folder, db, use_gpu):
        super().__init__()
        self.source_files = source_files
        self.destination_folder = destination_folder
        self.db = db
        self.use_gpu = use_gpu
        self.stop_flag = False
        self.start_time = None
        
    def stop(self):
        self.stop_flag = True
        
    def run(self):
        self.start_time = time.time()
        total = len(self.source_files)
        
        for i, source_path in enumerate(self.source_files):
            if self.stop_flag:
                break
                
            filename = os.path.basename(source_path)
            dest_path = os.path.join(self.destination_folder, filename)
            
            success, error_msg = remove_audio_from_video(source_path, dest_path, self.use_gpu)
            
            if success:
                status = 'success'
            else:
                status = 'failed'
                
            self.db.save_batch_audio_status(source_path, dest_path, status, error_msg)
            self.file_processed.emit(source_path, status)
            self.progress_updated.emit(i + 1)
            
        self.all_finished.emit()


class BatchAudioRemoverDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Audio Remover")
        self.resize(900, 750)
        
        if parent:
            parent_rect = parent.frameGeometry()
            self_rect = self.frameGeometry()
            center_point = parent_rect.center()
            self_rect.moveCenter(center_point)
            self.move(self_rect.topLeft())
        
        self.db = ImageTeaDB()
        self.db_path = self.db.db_path
        
        self.source_files = []
        self.destination_folder = None
        self.destination_files = []
        
        self.worker = None
        self.is_processing = False
        self.use_gpu = None
        
        self.total_files = 0
        self.success_count = 0
        self.failed_count = 0
        self.stopped_count = 0
        self.start_time = None
        
        self.load_from_db = False
        
        self.setup_ui()
        self.load_persistent_data()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        
        self.load_db_btn = QPushButton(qta.icon('fa6s.database'), " Load from Database")
        self.load_db_btn.setToolTip("Load video files from the existing database")
        self.load_db_btn.clicked.connect(self.on_load_from_database)
        top_layout.addWidget(self.load_db_btn)
        
        self.select_source_btn = QPushButton(qta.icon('fa6s.folder-open'), " Select Source")
        self.select_source_btn.setToolTip("Select source directory containing videos")
        self.select_source_btn.clicked.connect(self.on_select_source)
        top_layout.addWidget(self.select_source_btn)
        
        self.select_dest_btn = QPushButton(qta.icon('fa6s.folder-open'), " Select Destination")
        self.select_dest_btn.setToolTip("Select destination directory for processed videos")
        self.select_dest_btn.clicked.connect(self.on_select_destination)
        top_layout.addWidget(self.select_dest_btn)
        
        self.scan_dest_btn = QPushButton(qta.icon('fa6s.magnifying-glass'), " Scan Destination")
        self.scan_dest_btn.setToolTip("Scan destination folder to check for existing files")
        self.scan_dest_btn.clicked.connect(self.on_scan_destination)
        top_layout.addWidget(self.scan_dest_btn)
        
        self.check_gpu_btn = QPushButton(qta.icon('fa6s.microchip'), " Check GPU")
        self.check_gpu_btn.setToolTip("Check GPU compatibility for hardware acceleration")
        self.check_gpu_btn.clicked.connect(self.on_check_gpu)
        top_layout.addWidget(self.check_gpu_btn)
        
        self.clear_all_btn = QPushButton(qta.icon('fa6s.trash'), " Clear All")
        self.clear_all_btn.setToolTip("Reset tool and clear all data")
        self.clear_all_btn.clicked.connect(self.clear_all)
        top_layout.addWidget(self.clear_all_btn)
        
        top_layout.addStretch()
        
        main_layout.addLayout(top_layout)
        
        path_info_layout = QHBoxLayout()
        
        source_path_layout = QVBoxLayout()
        source_path_label_title = QLabel("Source:")
        source_path_label_title.setStyleSheet("font-weight: bold;")
        source_path_layout.addWidget(source_path_label_title)
        self.source_path_label = QLabel("No source selected")
        self.source_path_label.setStyleSheet(f"color: {theme.get_color('gray')};")
        source_path_layout.addWidget(self.source_path_label)
        source_path_layout.addStretch()
        path_info_layout.addLayout(source_path_layout)
        
        dest_path_layout = QVBoxLayout()
        dest_path_label_title = QLabel("Destination:")
        dest_path_label_title.setStyleSheet("font-weight: bold;")
        dest_path_layout.addWidget(dest_path_label_title)
        self.dest_path_label = QLabel("No destination selected")
        self.dest_path_label.setStyleSheet(f"color: {theme.get_color('gray')};")
        dest_path_layout.addWidget(self.dest_path_label)
        dest_path_layout.addStretch()
        path_info_layout.addLayout(dest_path_layout)
        
        main_layout.addLayout(path_info_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        source_label = QLabel("Source Files")
        left_layout.addWidget(source_label, 0)
        
        self.source_table = QTableWidget()
        self.source_table.setColumnCount(2)
        self.source_table.setHorizontalHeaderLabels(["Filename", "Status"])
        self.source_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.source_table.setColumnWidth(1, 120)
        self.source_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.source_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.source_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.source_table, 1)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        dest_label = QLabel("Destination Files")
        right_layout.addWidget(dest_label, 0)
        
        self.dest_table = QTableWidget()
        self.dest_table.setColumnCount(2)
        self.dest_table.setHorizontalHeaderLabels(["Filename", "Status"])
        self.dest_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.dest_table.setColumnWidth(1, 120)
        self.dest_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.dest_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.dest_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.dest_table, 1)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([500, 500])
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout.addWidget(splitter, 1)
        
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.StyledPanel)
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        stats_layout.setSpacing(20)
        
        self.total_label = QLabel("Total: 0")
        self.success_label = QLabel("Success: 0")
        self.failed_label = QLabel("Failed: 0")
        self.stopped_label = QLabel("Stopped: 0")
        self.remaining_label = QLabel("Remaining: 0")
        self.progress_label = QLabel("Progress: 0%")
        self.elapsed_label = QLabel("Elapsed: 00:00:00")
        self.eta_label = QLabel("ETA: --:--:--")
        self.speed_label = QLabel("Speed: 0 files/s")
        
        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.success_label)
        stats_layout.addWidget(self.failed_label)
        stats_layout.addWidget(self.stopped_label)
        stats_layout.addWidget(self.remaining_label)
        stats_layout.addWidget(self.progress_label)
        stats_layout.addWidget(self.elapsed_label)
        stats_layout.addWidget(self.eta_label)
        stats_layout.addWidget(self.speed_label)
        stats_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        main_layout.addWidget(stats_frame, 0)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        self.start_btn = QPushButton(qta.icon('fa6s.play'), " Start Process")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setMinimumWidth(150)
        self.start_btn.setToolTip("Start audio removal process")
        self.start_btn.clicked.connect(self.toggle_processing)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
        """)
        bottom_layout.addWidget(self.start_btn)
        
        main_layout.addLayout(bottom_layout, 0)
        
    def load_persistent_data(self):
        config_path = os.path.join(BASE_PATH, 'temp', 'batch_audio_remover_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                self.use_gpu = config.get('gpu_support')
                if self.use_gpu is not None:
                    print(f"[DEBUG] GPU support loaded from config: {self.use_gpu}")
                
                self.destination_folder = config.get('destination_folder')
                if self.destination_folder and os.path.exists(self.destination_folder):
                    self.dest_path_label.setText(self.destination_folder)
                    self.dest_path_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold;")
                    print(f"[DEBUG] Auto scanning destination folder: {self.destination_folder}")
                    self.destination_files = scan_directory_for_videos(self.destination_folder)
                    print(f"[DEBUG] Found {len(self.destination_files)} files in destination")
                
                source_type = config.get('source_type')
                if source_type == 'database':
                    self.load_from_db = True
                    self.select_source_btn.setEnabled(False)
                    self.source_path_label.setText("Loaded from database")
                    self.source_path_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold;")
                    
                    files = self.db.get_all_files()
                    video_files = []
                    for file_data in files:
                        filepath = file_data[1]
                        if is_video_file(filepath) and os.path.exists(filepath):
                            video_files.append(filepath)
                    
                    if video_files:
                        self.source_files = video_files
                        self.update_source_table()
                        self.update_destination_table()
                        self.update_stats()
                        print(f"[DEBUG] Restored {len(video_files)} files from database")
                    
                elif source_type == 'folder':
                    source_folder = config.get('source_folder')
                    if source_folder and os.path.exists(source_folder):
                        self.source_path_label.setText(source_folder)
                        self.source_path_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold;")
                        self.load_from_db = False
                        self.select_source_btn.setEnabled(True)
                        
                        self.source_files = scan_directory_for_videos(source_folder)
                        if self.source_files:
                            self.update_source_table()
                            self.update_destination_table()
                            self.update_stats()
                            print(f"[DEBUG] Restored {len(self.source_files)} files from folder")
    
    def save_paths_to_config(self):
        config_path = os.path.join(BASE_PATH, 'temp', 'batch_audio_remover_config.json')
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        config = {
            'destination_folder': self.destination_folder,
            'source_type': 'database' if self.load_from_db else 'folder',
            'source_folder': self.source_path_label.text() if not self.load_from_db and self.source_path_label.text() != "No source selected" and self.source_path_label.text() != "Loaded from database" else None,
            'gpu_support': self.use_gpu
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    def on_load_from_database(self):
        self.load_from_db = True
        self.select_source_btn.setEnabled(False)
        
        files = self.db.get_all_files()
        video_files = []
        
        print(f"[DEBUG] Total files in database: {len(files)}")
        
        for file_data in files:
            filepath = file_data[1]
            if is_video_file(filepath):
                if os.path.exists(filepath):
                    video_files.append(filepath)
                else:
                    print(f"[DEBUG] File not found: {filepath}")
        
        if len(video_files) == 0:
            print(f"[DEBUG] No video files found in database")
        else:
            print(f"[DEBUG] Total video files loaded: {len(video_files)}")
        
        self.source_files = video_files
        self.source_path_label.setText("Loaded from database")
        self.source_path_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold;")
        self.save_paths_to_config()
        self.update_source_table()
        self.update_destination_table()
        self.update_stats()
        
    def on_select_source(self):
        home_dir = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Source Directory",
            home_dir
        )
        
        if directory:
            video_files = scan_directory_for_videos(directory)
            
            if len(video_files) == 0:
                print(f"[DEBUG] No video files found in directory: {directory}")
            else:
                print(f"[DEBUG] Found {len(video_files)} video files in directory: {directory}")
            
            for video_path in video_files:
                filename = os.path.basename(video_path)
                self.db.add_file(
                    filepath=video_path,
                    filename=filename,
                    original_filename=filename
                )
            
            self.load_from_db = False
            self.source_files = video_files
            self.source_path_label.setText(directory)
            self.source_path_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold;")
            self.save_paths_to_config()
            self.update_source_table()
            self.update_destination_table()
            self.update_stats()
            
    def on_select_destination(self):
        home_dir = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Destination Directory",
            home_dir
        )
        
        if directory:
            self.destination_folder = directory
            self.dest_path_label.setText(directory)
            self.dest_path_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold;")
            self.save_paths_to_config()
            # Auto-scan destination when selected
            print(f"[DEBUG] Destination folder selected: {directory} - starting auto-scan")
            if os.path.exists(self.destination_folder):
                self.destination_files = scan_directory_for_videos(self.destination_folder)
                print(f"[DEBUG] Auto-scanned destination and found {len(self.destination_files)} files")
                self.update_destination_table()
                self.update_source_table()
                self.update_stats()
    
    def on_scan_destination(self):
        if not self.destination_folder:
            print("[DEBUG] No destination folder to scan")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("No Destination Folder")
            msg.setText("Please select a destination folder first.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.button(QMessageBox.Ok).setIcon(qta.icon('fa6s.check'))
            msg.exec()
            return
        
        if not os.path.exists(self.destination_folder):
            print(f"[DEBUG] Destination folder does not exist: {self.destination_folder}")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Folder Not Found")
            msg.setText("The destination folder no longer exists.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.button(QMessageBox.Ok).setIcon(qta.icon('fa6s.check'))
            msg.exec()
            return
        
        print(f"[DEBUG] Scanning destination folder: {self.destination_folder}")
        self.destination_files = scan_directory_for_videos(self.destination_folder)
        self.update_destination_table()
        self.update_source_table()
        print(f"[DEBUG] Found {len(self.destination_files)} video files in destination")
    
    def on_check_gpu(self):
        print("[DEBUG] Manual GPU check initiated")
        self.use_gpu = check_gpu_support()
        print(f"[DEBUG] GPU support detected: {self.use_gpu}")
        
        self.save_paths_to_config()
        
        result_msg = QMessageBox(self)
        result_msg.setIcon(QMessageBox.Information)
        result_msg.setWindowTitle("GPU Check Complete")
        if self.use_gpu:
            result_msg.setText("GPU acceleration is available and will be used for faster processing.")
        else:
            result_msg.setText("GPU acceleration is not available. CPU will be used for processing.")
        result_msg.setStandardButtons(QMessageBox.Ok)
        result_msg.button(QMessageBox.Ok).setIcon(qta.icon('fa6s.check'))
        result_msg.exec()
        print(f"[DEBUG] GPU check completed and saved to config")
            
    def update_source_table(self):
        self.source_table.setRowCount(len(self.source_files))
        
        dest_filenames = {os.path.basename(f) for f in self.destination_files}
        
        for row, filepath in enumerate(self.source_files):
            filename = os.path.basename(filepath)
            
            status_data = self.db.get_batch_audio_status(filepath)
            if status_data:
                status_text = status_data['status']
            else:
                status_text = 'pending'
            
            filename_item = QTableWidgetItem(filename)
            status_item = QTableWidgetItem(status_text)
            
            if status_text == 'success':
                filename_item.setForeground(QColor(theme.get_color('success')))
                status_item.setForeground(QColor(theme.get_color('success')))
            elif status_text == 'pending' and filename in dest_filenames:
                filename_item.setForeground(QColor(theme.get_color('error')))
            
            self.source_table.setItem(row, 0, filename_item)
            self.source_table.setItem(row, 1, status_item)
            
    def update_destination_table(self):
        self.dest_table.setRowCount(len(self.destination_files))
        
        source_status_map = {}
        for source_path in self.source_files:
            filename = os.path.basename(source_path)
            status_data = self.db.get_batch_audio_status(source_path)
            if status_data:
                source_status_map[filename] = status_data['status']
            else:
                source_status_map[filename] = 'pending'
        
        for row, filepath in enumerate(self.destination_files):
            filename = os.path.basename(filepath)
            
            filename_item = QTableWidgetItem(filename)
            status_item = QTableWidgetItem('exists')
            
            if filename in source_status_map:
                if source_status_map[filename] == 'success':
                    filename_item.setForeground(QColor(theme.get_color('success')))
                    status_item.setForeground(QColor(theme.get_color('success')))
                elif source_status_map[filename] == 'pending':
                    filename_item.setForeground(QColor(theme.get_color('error')))
                    status_item.setForeground(QColor(theme.get_color('error')))
                
            self.dest_table.setItem(row, 0, filename_item)
            self.dest_table.setItem(row, 1, status_item)
            
    def clear_all(self):
        self.db.clear_all_batch_audio_status()
        
        self.source_files = []
        self.source_table.setRowCount(0)
        self.destination_files = []
        self.destination_folder = None
        self.dest_table.setRowCount(0)
        self.load_from_db = False
        self.select_source_btn.setEnabled(True)
        
        self.success_count = 0
        self.failed_count = 0
        self.stopped_count = 0
        self.start_time = None
        
        self.progress_bar.setValue(0)
        
        self.source_path_label.setText("No source selected")
        self.source_path_label.setStyleSheet(f"color: {theme.get_color('gray')};")
        self.dest_path_label.setText("No destination selected")
        self.dest_path_label.setStyleSheet(f"color: {theme.get_color('gray')};")
        
        config_path = os.path.join(BASE_PATH, 'temp', 'batch_audio_remover_config.json')
        if os.path.exists(config_path):
            os.remove(config_path)
        
        self.update_stats()
        print("[DEBUG] Tool reset: batch_audio_remover table cleared, all data cleared")
        
    def toggle_processing(self):
        if self.is_processing:
            self.stop_processing()
        else:
            self.start_processing()
            
    def start_processing(self):
        if not self.source_files:
            print("[DEBUG] No source files to process")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("No Source Files")
            msg.setText("Please select source files or load from database first.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.button(QMessageBox.Ok).setIcon(qta.icon('fa6s.check'))
            msg.exec()
            return
            
        if not self.destination_folder:
            print("[DEBUG] No destination folder selected")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("No Destination Folder")
            msg.setText("Please select a destination folder first.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.button(QMessageBox.Ok).setIcon(qta.icon('fa6s.check'))
            msg.exec()
            return
        
        dest_filenames = {os.path.basename(f) for f in self.destination_files}
        source_filenames = [os.path.basename(f) for f in self.source_files]
        conflicts = [name for name in source_filenames if name in dest_filenames]
        
        if len(conflicts) > 0:
            print(f"[DEBUG] Found {len(conflicts)} file conflicts that will be overwritten")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Overwrite Confirmation")
            msg.setText(f"{len(conflicts)} file(s) already exist in destination folder and will be overwritten.\n\nDo you want to continue?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.button(QMessageBox.Yes).setIcon(qta.icon('fa6s.check'))
            msg.button(QMessageBox.No).setIcon(qta.icon('fa6s.xmark'))
            msg.setDefaultButton(QMessageBox.No)
            result = msg.exec()
            if result == QMessageBox.No:
                print("[DEBUG] User cancelled processing due to file conflicts")
                return
        
        if self.use_gpu is None:
            print("[DEBUG] Checking GPU support...")
            self.use_gpu = check_gpu_support()
            print(f"[DEBUG] GPU support detected: {self.use_gpu}")
            
            self.save_paths_to_config()
            
            result_msg = QMessageBox(self)
            result_msg.setIcon(QMessageBox.Information)
            result_msg.setWindowTitle("GPU Check Complete")
            if self.use_gpu:
                result_msg.setText("GPU acceleration is available and will be used for faster processing.")
            else:
                result_msg.setText("GPU acceleration is not available. CPU will be used for processing.")
            result_msg.setStandardButtons(QMessageBox.Ok)
            result_msg.button(QMessageBox.Ok).setIcon(qta.icon('fa6s.check'))
            result_msg.exec()
            
        self.is_processing = True
        self.start_time = time.time()
        
        self.progress_bar.setValue(0)
        
        self.start_btn.setText(" Stop Process")
        self.start_btn.setIcon(qta.icon('fa6s.stop'))
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('secondary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('secondary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('secondary_pressed')};
            }}
        """)
        
        self.success_count = 0
        self.failed_count = 0
        self.stopped_count = 0
        
        self.worker = AudioRemovalWorker(
            self.source_files,
            self.destination_folder,
            self.db,
            self.use_gpu
        )
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.file_processed.connect(self.on_file_processed)
        self.worker.all_finished.connect(self.on_processing_finished)
        self.worker.start()
        
    def stop_processing(self):
        if self.worker:
            self.worker.stop()
            
        for filepath in self.source_files:
            status_data = self.db.get_batch_audio_status(filepath)
            if not status_data or status_data['status'] == 'pending':
                filename = os.path.basename(filepath)
                dest_path = os.path.join(self.destination_folder, filename)
                self.db.save_batch_audio_status(filepath, dest_path, 'stopped', None)
                self.stopped_count += 1
                
        self.is_processing = False
        self.start_btn.setText(" Start Process")
        self.start_btn.setIcon(qta.icon('fa6s.play'))
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
        """)
        self.update_stats()
        
    def on_progress_updated(self, count):
        total = len(self.source_files)
        if total > 0:
            progress_percent = int((count / total) * 100)
            self.progress_bar.setValue(progress_percent)
            
        self.update_stats()
        
    def on_file_processed(self, source_path, status):
        if status == 'success':
            self.success_count += 1
        elif status == 'failed':
            self.failed_count += 1
            
        self.update_source_table()
        self.update_stats()
        
    def on_processing_finished(self):
        self.is_processing = False
        self.start_btn.setText(" Start Process")
        self.start_btn.setIcon(qta.icon('fa6s.play'))
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
        """)
        self.progress_bar.setValue(100)
        
        if self.destination_folder:
            self.destination_files = scan_directory_for_videos(self.destination_folder)
            self.update_destination_table()
        
        self.update_stats()
        
    def update_stats(self):
        total = len(self.source_files)
        processed = self.success_count + self.failed_count
        remaining = total - processed
        
        self.total_files = total
        
        self.total_label.setText(f"Total: {total}")
        self.success_label.setText(f"Success: {self.success_count}")
        self.failed_label.setText(f"Failed: {self.failed_count}")
        self.stopped_label.setText(f"Stopped: {self.stopped_count}")
        self.remaining_label.setText(f"Remaining: {remaining}")
        
        if total > 0:
            progress_percent = int((processed / total) * 100)
            self.progress_label.setText(f"Progress: {progress_percent}%")
        else:
            self.progress_label.setText("Progress: 0%")
            
        if self.start_time and self.is_processing:
            elapsed = time.time() - self.start_time
            elapsed_str = self.format_time(elapsed)
            self.elapsed_label.setText(f"Elapsed: {elapsed_str}")
            
            if processed > 0:
                avg_time_per_file = elapsed / processed
                eta = avg_time_per_file * remaining
                eta_str = self.format_time(eta)
                self.eta_label.setText(f"ETA: {eta_str}")
                
                speed = processed / elapsed
                self.speed_label.setText(f"Speed: {speed:.2f} files/s")
            else:
                self.eta_label.setText("ETA: --:--:--")
                self.speed_label.setText("Speed: 0 files/s")
        else:
            self.elapsed_label.setText("Elapsed: 00:00:00")
            self.eta_label.setText("ETA: --:--:--")
            self.speed_label.setText("Speed: 0 files/s")
            
    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
