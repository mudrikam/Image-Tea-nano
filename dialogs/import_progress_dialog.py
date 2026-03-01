from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QProgressBar, QPushButton, QGridLayout)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont
import time
import os
import qtawesome as qta

class ImportWorkerThread(QThread):
    """Thread untuk melakukan import file dengan progress reporting"""
    
    file_started = Signal(str, int, int)  # filename, current_index, total_files
    file_completed = Signal(bool)  # success
    import_finished = Signal(int)  # total_imported
    error_occurred = Signal(str, str)  # filename, error_message
    
    def __init__(self, file_paths, db, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.db = db
        self.cancelled = False
        
    def cancel(self):
        """Cancel import process"""
        self.cancelled = True
        
    def run(self):
        """Main import processing"""
        from helpers.metadata_helper.metadata_operation import read_metadata_pyexiv2, read_metadata_video
        try:
            from PIL import Image
            PILLOW_FORMATS = set()
            for ext, fmt in Image.registered_extensions().items():
                PILLOW_FORMATS.add(ext.lower())
        except ImportError:
            PILLOW_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.eps', '.svg', '.pdf'}
        
        added = 0
        video_exts = {'.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp', '.3gpp'}
        extra_exts = {'.svg', '.eps', '.pdf', '.ai'}
        
        for idx, path in enumerate(self.file_paths):
            if self.cancelled:
                break
                
            if os.path.isfile(path):
                fname = os.path.basename(path)
                ext = os.path.splitext(path)[1].lower()
                
                self.file_started.emit(fname, idx + 1, len(self.file_paths))
                
                try:
                    if ext in video_exts:
                        t, d, tg = read_metadata_video(path)
                    elif ext in PILLOW_FORMATS or ext in extra_exts:
                        t, d, tg = read_metadata_pyexiv2(path)
                    else:
                        self.error_occurred.emit(fname, f"Unsupported file extension {ext}")
                        self.file_completed.emit(False)
                        continue
                    
                    title = t if t else None
                    description = d if d else None
                    tags = tg if tg else None
                    
                    self.db.add_file(path, fname, title, description, tags, status="draft", original_filename=fname)
                    added += 1
                    self.file_completed.emit(True)
                    
                except Exception as e:
                    self.error_occurred.emit(fname, str(e))
                    self.file_completed.emit(False)
            else:
                fname = os.path.basename(path)
                self.error_occurred.emit(fname, "File not found")
                self.file_completed.emit(False)
        
        self.import_finished.emit(added)

class ImportProgressDialog(QDialog):
    """Dialog untuk menampilkan progress import file dengan vanilla PySide6"""
    
    def __init__(self, file_paths, db, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.db = db
        self.total_files = len(file_paths)
        self.processed_files = 0
        self.imported_files = 0
        self.failed_files = 0
        self.skipped_files = 0
        self.start_time = None
        self.worker_thread = None
        self.current_file_name = ""
        
        self.setWindowTitle("Import Files Progress")
        self.setModal(True)
        self.setFixedWidth(550)
        self.setup_ui()
        self.setup_timer()
        self.adjustSize()
        
    def setup_ui(self):
        """Setup user interface dengan vanilla PySide6 tanpa frame"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(25, 25, 25, 25)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa6s.database').pixmap(22, 22))
        header_layout.addWidget(title_icon)
        title_label = QLabel("Importing Files to Database")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        current_file_title_layout = QHBoxLayout()
        current_file_title_layout.setSpacing(6)
        current_file_icon = QLabel()
        current_file_icon.setPixmap(qta.icon('fa6s.file-lines').pixmap(14, 14))
        current_file_title_layout.addWidget(current_file_icon)
        current_file_title = QLabel("Current File:")
        current_file_title_font = QFont()
        current_file_title_font.setBold(True)
        current_file_title.setFont(current_file_title_font)
        current_file_title_layout.addWidget(current_file_title)
        current_file_title_layout.addStretch()
        main_layout.addLayout(current_file_title_layout)
        
        self.current_file_label = QLabel("Preparing to import files...")
        self.current_file_label.setWordWrap(True)
        self.current_file_label.setMargin(5)
        main_layout.addWidget(self.current_file_label)
        
        progress_title_layout = QHBoxLayout()
        progress_title_layout.setSpacing(6)
        progress_icon = QLabel()
        progress_icon.setPixmap(qta.icon('fa6s.chart-line').pixmap(14, 14))
        progress_title_layout.addWidget(progress_icon)
        progress_title = QLabel("Progress:")
        progress_title_font = QFont()
        progress_title_font.setBold(True)
        progress_title.setFont(progress_title_font)
        progress_title_layout.addWidget(progress_title)
        progress_title_layout.addStretch()
        main_layout.addLayout(progress_title_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(self.total_files)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(25)
        main_layout.addWidget(self.progress_bar)
        
        stats_title_layout = QHBoxLayout()
        stats_title_layout.setSpacing(6)
        stats_icon = QLabel()
        stats_icon.setPixmap(qta.icon('fa6s.table').pixmap(14, 14))
        stats_title_layout.addWidget(stats_icon)
        stats_title = QLabel("Statistics:")
        stats_title_font = QFont()
        stats_title_font.setBold(True)
        stats_title.setFont(stats_title_font)
        stats_title_layout.addWidget(stats_title)
        stats_title_layout.addStretch()
        main_layout.addLayout(stats_title_layout)
        
        stats_layout = QGridLayout()
        stats_layout.setHorizontalSpacing(20)
        stats_layout.setVerticalSpacing(8)
        
        stats_layout.addWidget(QLabel("Total Files:"), 0, 0)
        self.total_files_label = QLabel(str(self.total_files))
        self.total_files_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.total_files_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Processed:"), 0, 2)
        self.processed_files_label = QLabel("0")
        self.processed_files_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.processed_files_label, 0, 3)
        
        stats_layout.addWidget(QLabel("Imported:"), 1, 0)
        self.imported_files_label = QLabel("0")
        self.imported_files_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.imported_files_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Failed:"), 1, 2)
        self.failed_files_label = QLabel("0")
        self.failed_files_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.failed_files_label, 1, 3)
        
        stats_layout.addWidget(QLabel("Elapsed Time:"), 2, 0)
        self.elapsed_time_label = QLabel("00:00")
        self.elapsed_time_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.elapsed_time_label, 2, 1)
        
        stats_layout.addWidget(QLabel("Estimated Remaining:"), 2, 2)
        self.estimated_time_label = QLabel("--:--")
        self.estimated_time_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.estimated_time_label, 2, 3)
        
        stats_layout.addWidget(QLabel("Files per Second:"), 3, 0)
        self.speed_label = QLabel("--")
        self.speed_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.speed_label, 3, 1)
        
        stats_layout.addWidget(QLabel("Status:"), 3, 2)
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignRight)
        stats_layout.addWidget(self.status_label, 3, 3)
        
        main_layout.addLayout(stats_layout)
        
        main_layout.addStretch()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton(qta.icon('fa6s.xmark'), " Cancel Import")
        self.cancel_button.setMinimumWidth(120)
        self.cancel_button.clicked.connect(self.cancel_import)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
    def setup_timer(self):
        """Setup timer untuk update elapsed time"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_elapsed_time)
        self.timer.start(1000)  # Update every second
        
    def start_import(self):
        """Mulai proses import"""
        self.start_time = time.time()
        
        self.worker_thread = ImportWorkerThread(self.file_paths, self.db, self)
        self.worker_thread.file_started.connect(self.on_file_started)
        self.worker_thread.file_completed.connect(self.on_file_completed)
        self.worker_thread.import_finished.connect(self.on_import_finished)
        self.worker_thread.error_occurred.connect(self.on_error_occurred)
        
        self.worker_thread.start()
        
    def on_file_started(self, filename, current_index, total_files):
        self.current_file_name = filename
        self.current_file_label.setText(f"Processing: {filename}")
        self.status_label.setText("Processing...")
        self.adjustSize()
        
    def on_file_completed(self, success):
        self.processed_files += 1
        if success:
            self.imported_files += 1
        else:
            self.failed_files += 1
            
        self.progress_bar.setValue(self.processed_files)
        
        self.processed_files_label.setText(str(self.processed_files))
        self.imported_files_label.setText(str(self.imported_files))
        self.failed_files_label.setText(str(self.failed_files))
        
        self.update_time_calculations()
        self.adjustSize()
        
    def on_import_finished(self, total_imported):
        self.timer.stop()
        
        self.current_file_label.setText(f"Import completed successfully!")
        self.progress_bar.setValue(self.total_files)
        self.status_label.setText("Completed")
        
        summary = f"Import completed! {total_imported} files imported successfully"
        if self.failed_files > 0:
            summary += f", {self.failed_files} files failed"
        summary += "."
        self.current_file_label.setText(summary)
        self.adjustSize()
        QTimer.singleShot(2000, self.accept)
        
    def on_error_occurred(self, filename, error_message):
        print(f"[IMPORT ERROR] {filename}: {error_message}")
        self.current_file_label.setText(f"Error importing {filename}: {error_message}")
        self.status_label.setText("Error")
        self.adjustSize()
        
    def update_elapsed_time(self):
        """Update elapsed time setiap detik"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            elapsed_str = self.format_time(elapsed)
            self.elapsed_time_label.setText(elapsed_str)
            
            if elapsed > 0 and self.processed_files > 0:
                speed = self.processed_files / elapsed
                self.speed_label.setText(f"{speed:.1f}")
            else:
                self.speed_label.setText("--")
                
    def update_time_calculations(self):
        """Update estimated completion time dan speed"""
        if self.start_time and self.processed_files > 0:
            elapsed = time.time() - self.start_time
            
            avg_time_per_file = elapsed / self.processed_files
            remaining_files = self.total_files - self.processed_files
            
            if remaining_files > 0:
                estimated_remaining = avg_time_per_file * remaining_files
                estimated_str = self.format_time(estimated_remaining)
                self.estimated_time_label.setText(estimated_str)
            else:
                self.estimated_time_label.setText("00:00")
                
            if elapsed > 0:
                speed = self.processed_files / elapsed
                self.speed_label.setText(f"{speed:.1f}")
                
    def format_time(self, seconds):
        """Format waktu dalam detik ke format MM:SS atau HH:MM:SS untuk waktu yang lama"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
        
    def cancel_import(self):
        """Cancel import atau close dialog"""
        if self.worker_thread and self.worker_thread.isRunning():
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, 
                "Cancel Import", 
                "Are you sure you want to cancel the import process?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker_thread.cancel()
                self.status_label.setText("Cancelling...")
                self.cancel_button.setText("Cancelling...")
                self.cancel_button.setEnabled(False)
                self.worker_thread.wait()  # Wait for thread to finish
                self.reject()
        else:
            self.reject()
                
    def closeEvent(self, event):
        """Override close event untuk cleanup"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.cancel()
            self.worker_thread.wait()
        if hasattr(self, 'timer'):
            self.timer.stop()
        event.accept()
