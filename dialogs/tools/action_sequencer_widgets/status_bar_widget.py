from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, 
                               QProgressBar, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import qtawesome as qta
import time


class StatusBarWidget(QWidget):
    run_sequences_requested = Signal()
    stop_process_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        self.is_running = False
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self.files_label = QLabel("Files: 0")
        self.files_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.files_label)
        
        self.steps_label = QLabel("Steps: 0")
        self.steps_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.steps_label)
        
        self.elapsed_label = QLabel("Elapsed: 00:00")
        self.elapsed_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.elapsed_label)
        
        self.completed_label = QLabel("Completed: 0")
        self.completed_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.completed_label)
        
        self.remaining_label = QLabel("Remaining: 0")
        self.remaining_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.remaining_label)
        
        self.eta_label = QLabel("ETA: 00:00")
        self.eta_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.eta_label)
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.status_label)
        
        stats_layout.addStretch()
        
        main_layout.addLayout(stats_layout)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_layout.addWidget(self.progress_bar)
        
        run_icon = qta.icon('fa6s.play')
        self.run_button = QPushButton(run_icon, " RUN SEQUENCES")
        self.run_button.setMinimumHeight(40)
        self.run_button.setMinimumWidth(180)
        self.run_button.clicked.connect(self.on_run_clicked)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4e9e20;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d7307;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        bottom_layout.addWidget(self.run_button)
        
        main_layout.addLayout(bottom_layout)
        
        self.setLayout(main_layout)
    
    def set_dummy_status(self):
        self.update_files_count(200)
        self.update_steps_count(4)
        self.update_status("Running")
        self.update_progress(60)
    
    def start_running_mode(self, total_files, total_steps):
        self.is_running = True
        self.total_files = total_files
        self.processed_files = 0
        self.start_time = time.time()
        
        self.files_label.setText(f"Files: {total_files}")
        self.steps_label.setText(f"Steps: {total_steps}")
        self.completed_label.setText(f"Completed: 0")
        self.remaining_label.setText(f"Remaining: {total_files}")
        self.elapsed_label.setText("Elapsed: 00:00")
        self.eta_label.setText("ETA: 00:00")
        
        stop_icon = qta.icon('fa6s.stop')
        self.run_button.setIcon(stop_icon)
        self.run_button.setText(" STOP PROCESS")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
        """)
        
        self.update_status("Running")
        self.update_progress(0)
    
    def update_running_progress(self, processed_files):
        self.processed_files = processed_files
        
        progress = int((processed_files / self.total_files) * 100) if self.total_files > 0 else 0
        self.progress_bar.setValue(progress)
        self.progress_bar.setFormat(f"{processed_files} / {self.total_files} files ({progress}%)")
        
        remaining_files = self.total_files - processed_files
        self.completed_label.setText(f"Completed: {processed_files}")
        self.remaining_label.setText(f"Remaining: {remaining_files}")
        
        if self.start_time:
            elapsed = time.time() - self.start_time
            self.elapsed_label.setText(f"Elapsed: {self._format_time(elapsed)}")
            
            if processed_files > 0:
                avg_time_per_file = elapsed / processed_files
                eta_seconds = avg_time_per_file * remaining_files
                self.eta_label.setText(f"ETA: {self._format_time(eta_seconds)}")
            else:
                self.eta_label.setText("ETA: 00:00")
    
    def end_running_mode(self):
        self.is_running = False
        
        run_icon = qta.icon('fa6s.play')
        self.run_button.setIcon(run_icon)
        self.run_button.setText(" RUN SEQUENCES")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4e9e20;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d7307;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        
        if self.start_time:
            elapsed = time.time() - self.start_time
            self.elapsed_label.setText(f"Elapsed: {self._format_time(elapsed)}")
        
        self.update_status("Completed")
        self.update_progress(100)
    
    def reset_stats(self):
        self.is_running = False
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        
        self.files_label.setText("Files: 0")
        self.steps_label.setText("Steps: 0")
        self.elapsed_label.setText("Elapsed: 00:00")
        self.completed_label.setText("Completed: 0")
        self.remaining_label.setText("Remaining: 0")
        self.eta_label.setText("ETA: 00:00")
        self.update_status("Idle")
        self.update_progress(0)
        self.progress_bar.setFormat("")
    
    def _format_time(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def update_files_count(self, count, source='manual'):
        if not self.is_running:
            self.files_label.setText(f"Files: {count}")
    
    def update_steps_count(self, count):
        if not self.is_running:
            self.steps_label.setText(f"Steps: {count}")
    
    def update_status(self, status):
        self.status_label.setText(f"Status: {status}")
        
        if status == "Running":
            self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        elif status == "Error":
            self.status_label.setStyleSheet("font-weight: bold; color: #f44336;")
        elif status == "Completed":
            self.status_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        else:
            self.status_label.setStyleSheet("font-weight: bold; color: #888;")
    
    def update_progress(self, value):
        if not self.is_running:
            self.progress_bar.setValue(value)
    
    def on_run_clicked(self):
        if self.is_running:
            self.stop_process_requested.emit()
        else:
            self.run_sequences_requested.emit()
    
    def set_run_button_enabled(self, enabled):
        self.run_button.setEnabled(enabled)
