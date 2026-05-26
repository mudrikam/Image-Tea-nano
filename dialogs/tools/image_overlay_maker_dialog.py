import os
import platform
import subprocess
from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit, 
    QPushButton, QProgressBar, QFileDialog, QMessageBox, QApplication,
    QSpacerItem, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QDragEnterEvent, QDropEvent


class DropTableWidget(QTableWidget):
    """Custom QTableWidget with drag and drop support"""
    
    def __init__(self, parent_dialog, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent_dialog
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move event"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                dropped_files = []
                dropped_folders = []
                
                # Collect all dropped items
                for url in urls:
                    path = url.toLocalFile()
                    path = self.parent_dialog._sanitize_path(path)
                    
                    if os.path.isdir(path):
                        dropped_folders.append(path)
                    elif os.path.isfile(path) and path.lower().endswith(('.png', '.jpg', '.jpeg')):
                        dropped_files.append(path)
                
                # Process dropped items
                new_files = []
                
                # Add files from folders
                for folder in dropped_folders:
                    for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
                        new_files.extend([str(f) for f in Path(folder).glob(f"**/{ext}")])
                
                # Add individual files
                new_files.extend(dropped_files)
                
                if new_files:
                    # Add to existing files (avoid duplicates)
                    for file in new_files:
                        if file not in self.parent_dialog.image_files:
                            self.parent_dialog.image_files.append(file)
                    
                    # Update source input
                    if len(dropped_folders) > 0:
                        self.parent_dialog.source_input.setText(dropped_folders[0])
                        self.parent_dialog.config.set('last_source_path', dropped_folders[0])
                        self.parent_dialog.update_output_path(dropped_folders[0])
                    elif len(dropped_files) > 0:
                        folder = os.path.dirname(dropped_files[0])
                        self.parent_dialog.source_input.setText(f"{len(self.parent_dialog.image_files)} files selected")
                        self.parent_dialog.config.set('last_source_path', folder)
                        if not self.parent_dialog.output_input.text():
                            self.parent_dialog.update_output_path(folder)
                    
                    self.parent_dialog.update_file_table()
                    self.parent_dialog.update_ui_state()
                    event.accept()
                else:
                    QMessageBox.information(self.parent_dialog, "No Images", "No valid image files found in dropped items.")
                    event.ignore()
            else:
                event.ignore()
        else:
            event.ignore()
import qtawesome as qta
from PIL import Image

from config import BASE_PATH
from helpers.tools.overlay_maker_helper import OverlayMakerConfig
from ui.theme_system import theme


class ImageProcessor(QThread):
    """Thread for processing images to avoid blocking the UI"""
    
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished_processing = Signal(str)
    processing_stopped = Signal()
    error_occurred = Signal(str)
    
    def __init__(self, image_files: List[str], overlay_path: str, output_dir: str):
        super().__init__()
        self.image_files = image_files
        self.overlay_path = overlay_path
        self.output_dir = output_dir
        self.should_stop = False
        
    def stop(self):
        """Stop processing"""
        self.should_stop = True
        
    def run(self):
        try:
            # Create output directory if it doesn't exist
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Load overlay image
            if not os.path.exists(self.overlay_path):
                self.error_occurred.emit(f"Overlay image not found: {self.overlay_path}")
                return
                
            overlay = Image.open(self.overlay_path).convert("RGBA")
            
            total_files = len(self.image_files)
            
            for i, image_path in enumerate(self.image_files):
                if self.should_stop:
                    self.status_updated.emit("Processing stopped")
                    self.processing_stopped.emit()
                    return
                    
                try:
                    filename = os.path.basename(image_path)
                    self.status_updated.emit(f"Processing {i + 1}/{total_files}: {filename}")
                    
                    # Load base image
                    base_image = Image.open(image_path)
                    
                    # Convert to RGBA if not already
                    if base_image.mode != 'RGBA':
                        base_image = base_image.convert('RGBA')
                    
                    # Resize overlay to match base image if needed
                    overlay_resized = overlay.resize(base_image.size, Image.Resampling.LANCZOS)
                    
                    # Composite images (overlay on top)
                    result = Image.alpha_composite(base_image, overlay_resized)
                    
                    # Save result
                    output_path = os.path.join(self.output_dir, filename)
                    extension = Path(image_path).suffix.lower()
                    
                    if extension in ['.jpg', '.jpeg']:
                        # Convert back to RGB for JPEG and save with high quality
                        result_rgb = result.convert('RGB')
                        result_rgb.save(output_path, 'JPEG', quality=100)
                    else:
                        # Save as PNG
                        result.save(output_path, 'PNG')
                    
                    # Update progress
                    progress = int((i + 1) / total_files * 100)
                    self.progress_updated.emit(progress)
                    
                except Exception as e:
                    self.error_occurred.emit(f"Error processing {image_path}: {str(e)}")
                    continue
            
            if not self.should_stop:
                self.finished_processing.emit(self.output_dir)
            
        except Exception as e:
            self.error_occurred.emit(f"Processing error: {str(e)}")


class ImageOverlayMakerDialog(QDialog):
    """Image Overlay Maker Tool - Standalone dialog for applying overlays to images"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Overlay Maker")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.config = OverlayMakerConfig()
        self.image_files = []
        self.processor = None
        self.is_processing = False
        
        self.setMinimumWidth(700)
        self.setMinimumHeight(400)
        
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        
        # File input sections at the top
        self._build_file_inputs(main_layout)
        
        # File table
        self._build_file_table(main_layout)
        
        # Stats and action buttons
        self._build_actions_bar(main_layout)
        
        self.setLayout(main_layout)
    
    def _build_file_inputs(self, parent_layout):
        """Build compact file input sections"""
        
        # Source folder input
        source_layout = QHBoxLayout()
        source_layout.setSpacing(8)
        
        source_icon = QLabel()
        source_icon.setPixmap(qta.icon('fa6s.folder-open', color=theme.get_color('gray')).pixmap(16, 16))
        source_layout.addWidget(source_icon)
        
        source_label = QLabel("Source:")
        source_label.setStyleSheet("font-weight: bold;")
        source_label.setMinimumWidth(60)
        source_layout.addWidget(source_label)
        
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("Select source folder or files...")
        self.source_input.editingFinished.connect(self.on_source_edited)
        self.source_input.setAcceptDrops(True)
        self.source_input.dragEnterEvent = self._make_drag_enter_handler(self.source_input)
        self.source_input.dropEvent = self._make_drop_handler(self.source_input, 'source')
        source_layout.addWidget(self.source_input, 1)
        
        self.source_paste_btn = QPushButton(qta.icon('fa6s.paste'), "")
        self.source_paste_btn.setToolTip("Paste from clipboard")
        self.source_paste_btn.setMaximumWidth(32)
        self.source_paste_btn.clicked.connect(self.on_paste_source)
        source_layout.addWidget(self.source_paste_btn)
        
        self.source_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.source_browse_btn.setToolTip("Browse folder")
        self.source_browse_btn.setMaximumWidth(32)
        self.source_browse_btn.clicked.connect(self.browse_folder)
        source_layout.addWidget(self.source_browse_btn)
        
        self.source_files_btn = QPushButton(qta.icon('fa6s.images'), "")
        self.source_files_btn.setToolTip("Browse files")
        self.source_files_btn.setMaximumWidth(32)
        self.source_files_btn.clicked.connect(self.browse_files)
        source_layout.addWidget(self.source_files_btn)
        
        self.source_open_btn = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.source_open_btn.setToolTip("Open folder location")
        self.source_open_btn.setMaximumWidth(32)
        self.source_open_btn.clicked.connect(self.on_open_source)
        source_layout.addWidget(self.source_open_btn)
        
        parent_layout.addLayout(source_layout)
        
        # Overlay input
        overlay_layout = QHBoxLayout()
        overlay_layout.setSpacing(8)
        
        overlay_icon = QLabel()
        overlay_icon.setPixmap(qta.icon('fa6s.layer-group', color=theme.get_color('gray')).pixmap(16, 16))
        overlay_layout.addWidget(overlay_icon)
        
        overlay_label = QLabel("Overlay:")
        overlay_label.setStyleSheet("font-weight: bold;")
        overlay_label.setMinimumWidth(60)
        overlay_layout.addWidget(overlay_label)
        
        self.overlay_input = QLineEdit()
        self.overlay_input.setPlaceholderText("Select overlay image (PNG with transparency)...")
        self.overlay_input.editingFinished.connect(self.on_overlay_edited)
        self.overlay_input.setAcceptDrops(True)
        self.overlay_input.dragEnterEvent = self._make_drag_enter_handler(self.overlay_input)
        self.overlay_input.dropEvent = self._make_drop_handler(self.overlay_input, 'overlay')
        overlay_layout.addWidget(self.overlay_input, 1)
        
        self.overlay_paste_btn = QPushButton(qta.icon('fa6s.paste'), "")
        self.overlay_paste_btn.setToolTip("Paste from clipboard")
        self.overlay_paste_btn.setMaximumWidth(32)
        self.overlay_paste_btn.clicked.connect(self.on_paste_overlay)
        overlay_layout.addWidget(self.overlay_paste_btn)
        
        self.overlay_browse_btn = QPushButton(qta.icon('fa6s.image'), "")
        self.overlay_browse_btn.setToolTip("Browse overlay image")
        self.overlay_browse_btn.setMaximumWidth(32)
        self.overlay_browse_btn.clicked.connect(self.browse_overlay)
        overlay_layout.addWidget(self.overlay_browse_btn)
        
        self.overlay_open_btn = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.overlay_open_btn.setToolTip("Open file location")
        self.overlay_open_btn.setMaximumWidth(32)
        self.overlay_open_btn.clicked.connect(self.on_open_overlay)
        overlay_layout.addWidget(self.overlay_open_btn)
        
        parent_layout.addLayout(overlay_layout)
        
        # Output folder input
        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        
        output_icon = QLabel()
        output_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        output_layout.addWidget(output_icon)
        
        output_label = QLabel("Output:")
        output_label.setStyleSheet("font-weight: bold;")
        output_label.setMinimumWidth(60)
        output_layout.addWidget(output_label)
        
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Output folder (auto-generated from source)...")
        self.output_input.editingFinished.connect(self.on_output_edited)
        self.output_input.setAcceptDrops(True)
        self.output_input.dragEnterEvent = self._make_drag_enter_handler(self.output_input)
        self.output_input.dropEvent = self._make_drop_handler(self.output_input, 'output')
        output_layout.addWidget(self.output_input, 1)
        
        self.output_paste_btn = QPushButton(qta.icon('fa6s.paste'), "")
        self.output_paste_btn.setToolTip("Paste from clipboard")
        self.output_paste_btn.setMaximumWidth(32)
        self.output_paste_btn.clicked.connect(self.on_paste_output)
        output_layout.addWidget(self.output_paste_btn)
        
        self.output_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.output_browse_btn.setToolTip("Browse folder")
        self.output_browse_btn.setMaximumWidth(32)
        self.output_browse_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_browse_btn)
        
        self.output_open_btn = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.output_open_btn.setToolTip("Open folder location")
        self.output_open_btn.setMaximumWidth(32)
        self.output_open_btn.clicked.connect(self.on_open_output)
        output_layout.addWidget(self.output_open_btn)
        
        parent_layout.addLayout(output_layout)
    
    def _build_file_table(self, parent_layout):
        """Build file table to display loaded images"""
        # Table header
        table_header_layout = QHBoxLayout()
        table_header_layout.setSpacing(8)
        
        table_icon = QLabel()
        table_icon.setPixmap(qta.icon('fa6s.list', color=theme.get_color('gray')).pixmap(16, 16))
        table_header_layout.addWidget(table_icon)
        
        table_label = QLabel("Image Files:")
        table_label.setStyleSheet("font-weight: bold;")
        table_header_layout.addWidget(table_label)
        
        table_header_layout.addStretch()
        
        # Clear button
        self.clear_files_btn = QPushButton(qta.icon('fa6s.trash'), " Clear")
        self.clear_files_btn.setToolTip("Clear all files from list")
        self.clear_files_btn.clicked.connect(self.clear_files)
        table_header_layout.addWidget(self.clear_files_btn)
        
        parent_layout.addLayout(table_header_layout)
        
        # File table with drag and drop support
        self.file_table = DropTableWidget(self)
        self.file_table.setColumnCount(2)
        self.file_table.setHorizontalHeaderLabels(["Filename", "Path"])
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.setAlternatingRowColors(True)
        
        parent_layout.addWidget(self.file_table, 1)
    
    def _build_actions_bar(self, parent_layout):
        """Build actions bar with stats on left and process button on right"""
        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self.files_count_label = QLabel("Files: 0")
        self.files_count_label.setStyleSheet("font-size: 11px; font-weight: bold;")
        stats_layout.addWidget(self.files_count_label)
        
        self.ready_label = QLabel("Ready to process")
        self.ready_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold; font-size: 11px;")
        stats_layout.addWidget(self.ready_label)
        
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 11px;")
        stats_layout.addWidget(self.status_label)
        
        stats_layout.addStretch()
        
        parent_layout.addLayout(stats_layout)
        
        # Progress bar and button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button_layout.addWidget(self.progress_bar, 1)
        
        self.process_btn = QPushButton(qta.icon('fa6s.play', color=theme.get_color('white')), " Process Images")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.setMinimumWidth(180)
        self.process_btn.setToolTip("Start processing images with overlay")
        self.process_btn.clicked.connect(self.toggle_processing)
        self.process_btn.setEnabled(False)
        self.process_btn.setStyleSheet(f"""
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
            QPushButton:disabled {{
                background-color: {theme.get_color('gray')};
            }}
        """)
        button_layout.addWidget(self.process_btn)
        
        parent_layout.addLayout(button_layout)
    
    def browse_folder(self):
        """Browse and select a folder to load all images"""
        last_path = self.config.get('last_source_path', '')
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", last_path)
        if folder:
            folder = self._sanitize_path(folder)
            self.source_input.setText(folder)
            self.load_images_from_folder(folder)
            self.config.set('last_source_path', folder)
    
    def browse_files(self):
        """Browse and select multiple image files"""
        last_path = self.config.get('last_source_path', '')
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Image Files", 
            last_path,
            "Image Files (*.png *.jpg *.jpeg)"
        )
        if files:
            files = [self._sanitize_path(f) for f in files]
            self.image_files = files
            if files:
                first_dir = os.path.dirname(files[0])
                self.source_input.setText(f"{len(files)} files selected")
                self.config.set('last_source_path', first_dir)
                self.update_output_path(first_dir)
            self.update_file_table()
            self.update_ui_state()
    
    def browse_overlay(self):
        """Browse for overlay image"""
        last_overlay = self.config.get('overlay_path', '')
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Overlay Image", 
            last_overlay,
            "PNG Files (*.png)"
        )
        if file_path:
            file_path = self._sanitize_path(file_path)
            self.overlay_input.setText(file_path)
            self.config.set('overlay_path', file_path)
            self.update_ui_state()
    
    def browse_output(self):
        """Browse for output folder"""
        last_output = self.config.get('last_output_path', '')
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", last_output)
        if folder:
            folder = self._sanitize_path(folder)
            self.output_input.setText(folder)
            self.config.set('last_output_path', folder)
    
    def load_images_from_folder(self, folder):
        """Load all image files from a folder"""
        image_files = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
            image_files.extend(Path(folder).glob(f"**/{ext}"))
        
        self.image_files = [str(f) for f in image_files]
        
        if not self.image_files:
            QMessageBox.information(self, "No Images", "No image files found in the selected folder.")
        else:
            self.update_output_path(folder)
        
        self.update_file_table()
        self.update_ui_state()
    
    def update_file_table(self):
        """Update the file table with current image files"""
        self.file_table.setRowCount(0)
        
        for file_path in self.image_files:
            row_count = self.file_table.rowCount()
            self.file_table.insertRow(row_count)
            
            filename = os.path.basename(file_path)
            self.file_table.setItem(row_count, 0, QTableWidgetItem(filename))
            self.file_table.setItem(row_count, 1, QTableWidgetItem(file_path))
    
    def clear_files(self):
        """Clear all files from the list"""
        self.image_files.clear()
        self.file_table.setRowCount(0)
        self.source_input.clear()
        self.update_ui_state()
    
    def update_output_path(self, source_folder):
        """Auto-generate output path from source folder"""
        output_dir = os.path.join(source_folder, "OVERLAY_OUTPUT")
        self.output_input.setText(output_dir)
        self.config.set('last_output_path', output_dir)
    
    def on_source_edited(self):
        """Handle manual source path edit"""
        path = self._sanitize_path(self.source_input.text())
        if path and os.path.isdir(path):
            self.load_images_from_folder(path)
            self.config.set('last_source_path', path)
    
    def on_overlay_edited(self):
        """Handle manual overlay path edit"""
        path = self._sanitize_path(self.overlay_input.text())
        if path:
            self.config.set('overlay_path', path)
            self.update_ui_state()
    
    def on_output_edited(self):
        """Handle manual output path edit"""
        path = self._sanitize_path(self.output_input.text())
        if path:
            self.config.set('last_output_path', path)
    
    def on_paste_source(self):
        """Paste source path from clipboard"""
        clipboard = QApplication.clipboard()
        text = self._sanitize_path(clipboard.text())
        if text:
            self.source_input.setText(text)
            if os.path.isdir(text):
                self.load_images_from_folder(text)
                self.config.set('last_source_path', text)
    
    def on_paste_overlay(self):
        """Paste overlay path from clipboard"""
        clipboard = QApplication.clipboard()
        text = self._sanitize_path(clipboard.text())
        if text:
            self.overlay_input.setText(text)
            self.config.set('overlay_path', text)
            self.update_ui_state()
    
    def on_paste_output(self):
        """Paste output path from clipboard"""
        clipboard = QApplication.clipboard()
        text = self._sanitize_path(clipboard.text())
        if text:
            self.output_input.setText(text)
            self.config.set('last_output_path', text)
    
    def on_open_source(self):
        """Open source folder in file explorer"""
        path = self._sanitize_path(self.source_input.text())
        if not path:
            QMessageBox.information(self, "No Path", "Please select a source folder first.")
            return
        
        if not os.path.exists(path):
            QMessageBox.warning(self, "Path Not Found", f"The path does not exist:\n{path}")
            return
        
        self._open_file_explorer(path)
    
    def on_open_overlay(self):
        """Open overlay file location in file explorer"""
        path = self._sanitize_path(self.overlay_input.text())
        if not path:
            QMessageBox.information(self, "No Path", "Please select an overlay image first.")
            return
        
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", f"The file does not exist:\n{path}")
            return
        
        folder_path = os.path.dirname(path)
        self._open_file_explorer(folder_path, select_file=path)
    
    def on_open_output(self):
        """Open output folder in file explorer"""
        path = self._sanitize_path(self.output_input.text())
        if not path:
            QMessageBox.information(self, "No Path", "Please select an output folder first.")
            return
        
        if not os.path.exists(path):
            reply = QMessageBox.question(
                self,
                "Folder Not Found",
                f"The output folder does not exist:\n{path}\n\nDo you want to create it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                os.makedirs(path, exist_ok=True)
                self._open_file_explorer(path)
            return
        
        self._open_file_explorer(path)
    
    def _open_file_explorer(self, path, select_file=None):
        """Open file explorer at the given path"""
        system = platform.system()
        
        if system == "Windows":
            if select_file and os.path.isfile(select_file):
                subprocess.Popen(['explorer', '/select,', os.path.normpath(select_file)])
            else:
                subprocess.Popen(['explorer', os.path.normpath(path)])
        elif system == "Darwin":
            if select_file and os.path.isfile(select_file):
                subprocess.Popen(['open', '-R', select_file])
            else:
                subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
    
    def _sanitize_path(self, text):
        """Remove surrounding quotes from path"""
        if not isinstance(text, str):
            return text
        t = text.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t
    
    def _make_drag_enter_handler(self, widget):
        """Create drag enter event handler for a widget"""
        def handler(event: QDragEnterEvent):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                event.ignore()
        return handler
    
    def _make_drop_handler(self, widget, field_type):
        """Create drop event handler for a widget"""
        def handler(event: QDropEvent):
            if event.mimeData().hasUrls():
                urls = event.mimeData().urls()
                if urls:
                    path = urls[0].toLocalFile()
                    path = self._sanitize_path(path)
                    
                    if field_type == 'source':
                        self.source_input.setText(path)
                        if os.path.isdir(path):
                            self.load_images_from_folder(path)
                            self.config.set('last_source_path', path)
                        elif os.path.isfile(path):
                            # If single file dropped, load it
                            if path.lower().endswith(('.png', '.jpg', '.jpeg')):
                                self.image_files = [path]
                                folder = os.path.dirname(path)
                                self.source_input.setText(f"1 file selected")
                                self.config.set('last_source_path', folder)
                                self.update_output_path(folder)
                                self.update_file_table()
                                self.update_ui_state()
                    
                    elif field_type == 'overlay':
                        if os.path.isfile(path) and path.lower().endswith('.png'):
                            self.overlay_input.setText(path)
                            self.config.set('overlay_path', path)
                            self.update_ui_state()
                        else:
                            QMessageBox.warning(self, "Invalid File", "Please drop a PNG file for overlay.")
                    
                    elif field_type == 'output':
                        if os.path.isdir(path):
                            self.output_input.setText(path)
                            self.config.set('last_output_path', path)
                        elif os.path.isfile(path):
                            # If file dropped, use its directory
                            folder = os.path.dirname(path)
                            self.output_input.setText(folder)
                            self.config.set('last_output_path', folder)
                    
                    event.acceptProposedAction()
                else:
                    event.ignore()
            else:
                event.ignore()
        return handler
    
    def update_ui_state(self):
        """Update UI state based on current data"""
        # Update file count
        self.files_count_label.setText(f"Files: {len(self.image_files)}")
        
        # Check if ready to process
        overlay_path = self._sanitize_path(self.overlay_input.text())
        can_process = (
            len(self.image_files) > 0 and 
            overlay_path and 
            os.path.exists(overlay_path)
        )
        
        self.process_btn.setEnabled(can_process and not self.is_processing)
        
        if can_process:
            self.ready_label.setText("Ready to process")
            self.ready_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold; font-size: 11px;")
        else:
            self.ready_label.setText("Select files and overlay to begin")
            self.ready_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-weight: bold; font-size: 11px;")
    
    def toggle_processing(self):
        """Start or stop processing"""
        if self.is_processing:
            self.stop_processing()
        else:
            self.start_processing()
    
    def start_processing(self):
        """Start processing images"""
        overlay_path = self._sanitize_path(self.overlay_input.text())
        output_path = self._sanitize_path(self.output_input.text())
        
        if not self.image_files or not overlay_path or not output_path:
            QMessageBox.warning(self, "Missing Information", "Please select source files, overlay image, and output folder.")
            return
        
        if not os.path.exists(overlay_path):
            QMessageBox.warning(self, "Overlay Not Found", f"The overlay image does not exist:\n{overlay_path}")
            return
        
        # Update UI for processing state
        self.is_processing = True
        self.process_btn.setText(" Stop Processing")
        self.process_btn.setIcon(qta.icon('fa6s.stop', color=theme.get_color('white')))
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting...")
        self.ready_label.setText("Processing...")
        
        # Apply red/danger styling for stop button using error color
        from PySide6.QtGui import QColor
        error_base = theme.get_color('error')
        error_hover = QColor(error_base).darker(115).name()
        error_pressed = QColor(error_base).darker(130).name()
        white = theme.get_color('white')
        
        self.process_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {error_base};
                color: {white};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {error_hover};
            }}
            QPushButton:pressed {{
                background-color: {error_pressed};
            }}
        """)
        
        # Disable inputs during processing
        self._set_inputs_enabled(False)
        
        # Start processing thread
        self.processor = ImageProcessor(self.image_files, overlay_path, output_path)
        self.processor.progress_updated.connect(self.on_progress_updated)
        self.processor.status_updated.connect(self.on_status_updated)
        self.processor.finished_processing.connect(self.on_processing_finished)
        self.processor.processing_stopped.connect(self.on_processing_stopped)
        self.processor.error_occurred.connect(self.on_processing_error)
        self.processor.start()
    
    def stop_processing(self):
        """Stop processing"""
        if self.processor:
            self.processor.stop()
            self.status_label.setText("Stopping...")
    
    def on_progress_updated(self, value):
        """Handle progress update"""
        self.progress_bar.setValue(value)
    
    def on_status_updated(self, status):
        """Handle status update"""
        self.status_label.setText(status)
    
    def on_processing_finished(self, output_dir):
        """Handle processing completion"""
        self.is_processing = False
        self.progress_bar.setValue(100)
        self.process_btn.setText(" Process Images")
        self.process_btn.setIcon(qta.icon('fa6s.play', color=theme.get_color('white')))
        self.process_btn.setStyleSheet(f"""
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
            QPushButton:disabled {{
                background-color: {theme.get_color('gray')};
            }}
        """)
        self.ready_label.setText("Processing complete!")
        self.ready_label.setStyleSheet(f"color: {theme.get_color('success')}; font-weight: bold; font-size: 11px;")
        
        # Re-enable inputs
        self._set_inputs_enabled(True)
        self.update_ui_state()
        
        reply = QMessageBox.question(
            self, 
            "Processing Complete", 
            f"Processing complete! Files saved to:\n{output_dir}\n\nOpen output folder?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._open_file_explorer(output_dir)
    
    def on_processing_error(self, error_message):
        """Handle processing error"""
        self.is_processing = False
        self.progress_bar.setValue(0)
        self.process_btn.setText(" Process Images")
        self.process_btn.setIcon(qta.icon('fa6s.play', color=theme.get_color('white')))
        self.process_btn.setStyleSheet(f"""
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
            QPushButton:disabled {{
                background-color: {theme.get_color('gray')};
            }}
        """)
        self.ready_label.setText("Error occurred")
        self.ready_label.setStyleSheet(f"color: {theme.get_color('error')}; font-weight: bold; font-size: 11px;")
        
        # Re-enable inputs
        self._set_inputs_enabled(True)
        self.update_ui_state()
        
        QMessageBox.critical(self, "Processing Error", error_message)
    
    def on_processing_stopped(self):
        """Handle processing being cancelled by the user"""
        self.is_processing = False
        self.progress_bar.setValue(0)
        self.status_label.setText("Stopped")
        self.process_btn.setText(" Process Images")
        self.process_btn.setIcon(qta.icon('fa6s.play', color=theme.get_color('white')))
        self.process_btn.setStyleSheet(f"""
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
            QPushButton:disabled {{
                background-color: {theme.get_color('gray')};
            }}
        """)
        self.ready_label.setText("Processing stopped")
        self.ready_label.setStyleSheet(f"color: {theme.get_color('warning')}; font-weight: bold; font-size: 11px;")
        
        # Re-enable inputs
        self._set_inputs_enabled(True)
        self.update_ui_state()
    
    def _set_inputs_enabled(self, enabled):
        """Enable or disable all input widgets"""
        self.source_input.setEnabled(enabled)
        self.source_paste_btn.setEnabled(enabled)
        self.source_browse_btn.setEnabled(enabled)
        self.source_files_btn.setEnabled(enabled)
        self.source_open_btn.setEnabled(enabled)
        
        self.overlay_input.setEnabled(enabled)
        self.overlay_paste_btn.setEnabled(enabled)
        self.overlay_browse_btn.setEnabled(enabled)
        self.overlay_open_btn.setEnabled(enabled)
        
        self.output_input.setEnabled(enabled)
        self.output_paste_btn.setEnabled(enabled)
        self.output_browse_btn.setEnabled(enabled)
        self.output_open_btn.setEnabled(enabled)
    
    def load_config(self):
        """Load saved configuration"""
        overlay_path = self.config.get('overlay_path', '')
        if overlay_path and os.path.exists(overlay_path):
            self.overlay_input.setText(overlay_path)
        
        self.update_ui_state()
