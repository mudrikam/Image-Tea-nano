import os
import json
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFileDialog, QWidget, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QPushButton, QLineEdit, QProgressBar, QSizePolicy, QSpinBox
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication
from config import BASE_PATH
from database.db_operation import ImageTeaDB
import subprocess
import qtawesome as qta
from ui.theme_system import theme
from ui.DragDropPathMixin import DragDropPathMixin
from helpers.tools.psd_to_img_helper.psd_to_img_config_helper import PSDToIMGConfig


class PSDWorkerThread(QThread):
    progress_updated = Signal(int, int)
    status_updated = Signal(str, str)
    completed = Signal(int, int)
    stopped = Signal(int, int)
    error_occurred = Signal(str)

    def __init__(self, files, output_path, output_format, quality, dpi, db):
        super().__init__()
        self.files = files
        self.output_path = output_path
        self.output_format = output_format
        self.quality = quality
        self.dpi = dpi
        self.db = db
        self.should_stop = False

    def run(self):
        try:
            total_files = len(self.files)
            processed = 0

            for idx, file_path in enumerate(self.files):
                if self.should_stop:
                    break

                filename = os.path.basename(file_path)
                self.status_updated.emit(filename, "Converting")

                try:
                    success = self.convert_psd(file_path)
                    if success:
                        processed += 1
                        self.status_updated.emit(filename, "Completed")
                    else:
                        self.status_updated.emit(filename, "Failed")
                except Exception as e:
                    self.status_updated.emit(filename, f"Error: {str(e)[:80]}")

                self.progress_updated.emit(idx + 1, total_files)

            if self.should_stop:
                self.stopped.emit(processed, total_files)
            else:
                self.completed.emit(processed, total_files)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _load_psd_image(self, psd_path):
        """Load a PSD file as a PIL Image, trying PIL first then psd-tools as fallback."""
        from PIL import Image

        # Try PIL first (fast, works for simple PSD files)
        try:
            img = Image.open(psd_path)
            img.load()
            return img
        except Exception as pil_error:
            pil_msg = str(pil_error)

        # Fallback to psd-tools (handles modern/complex PSD files)
        try:
            from psd_tools import PSDImage
            psd = PSDImage.open(psd_path)
            composite = psd.composite()
            if composite is None:
                raise RuntimeError("psd-tools could not composite the PSD (empty or unsupported)")
            return composite
        except ImportError:
            raise RuntimeError(
                f"PIL failed to read PSD ({pil_msg}) and psd-tools is not installed. "
                f"Install with: pip install psd-tools"
            )
        except Exception as psd_error:
            raise RuntimeError(
                f"Failed to read PSD. PIL: {pil_msg} | psd-tools: {psd_error}"
            )

    def convert_psd(self, psd_path):
        try:
            img = self._load_psd_image(psd_path)

            # Normalize to RGB / RGBA depending on output format
            target_format = self.output_format.lower()
            if target_format in ['jpg', 'jpeg', 'bmp']:
                # These don't support alpha
                if img.mode != 'RGB':
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        # Flatten on white background
                        from PIL import Image as PILImage
                        bg = PILImage.new('RGB', img.size, (255, 255, 255))
                        rgba = img.convert('RGBA')
                        bg.paste(rgba, mask=rgba.split()[-1])
                        img = bg
                    else:
                        img = img.convert('RGB')
            else:
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA')

            base_name = os.path.splitext(os.path.basename(psd_path))[0]
            output_file = os.path.join(self.output_path, f"{base_name}.{target_format}")

            save_kwargs = {}
            if target_format in ['jpg', 'jpeg']:
                if self.quality > 0:
                    save_kwargs['quality'] = self.quality
                save_kwargs['optimize'] = True
            if self.dpi > 0:
                save_kwargs['dpi'] = (self.dpi, self.dpi)

            output_ext = 'jpeg' if target_format in ['jpg', 'jpeg'] else target_format
            img.save(output_file, format=output_ext.upper(), **save_kwargs)
            return True
        except Exception as e:
            print(f"Error converting {psd_path}: {e}")
            return False

    def stop(self):
        self.should_stop = True


class PSDToIMGDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PSD to IMG Converter")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

        self.db = ImageTeaDB()
        self.loaded_files = []
        self.worker_thread = None
        self.config = PSDToIMGConfig()

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setup_ui()
        self.load_settings()
        self.resize(700, 600)
    
    def load_settings(self):
        output_path = self.config.get('output_path', '')
        output_format = self.config.get('output_format', 'PNG')
        quality = self.config.get('quality', 90)
        dpi = self.config.get('dpi', 300)
        
        self.format_combo.blockSignals(True)
        self.quality_slider.blockSignals(True)
        self.dpi_spin.blockSignals(True)
        try:
            if output_path:
                self.output_path_input.setText(output_path)
            
            self.format_combo.setCurrentText(output_format)
            self.quality_slider.setEnabled(output_format.upper() in ['JPG', 'JPEG'])
            
            self.quality_slider.setValue(quality)
            self.quality_label.setText(str(quality))
            
            self.dpi_spin.setValue(dpi)
        finally:
            self.format_combo.blockSignals(False)
            self.quality_slider.blockSignals(False)
            self.dpi_spin.blockSignals(False)

    def save_settings(self):
        self.config.set('output_path', self.output_path_input.text())
        self.config.set('output_format', self.format_combo.currentText())
        self.config.set('quality', self.quality_slider.value())
        self.config.set('dpi', self.dpi_spin.value())

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        header_layout = QHBoxLayout()
        header_icon = qta.icon('fa6s.file-image', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(header_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)

        title_label = QLabel("PSD to IMG Converter")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {theme.get_color('primary')};")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        subtitle_label = QLabel("Convert Photoshop PSD files to common image formats (JPG, PNG, etc.)")
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"color: {theme.get_color('gray')}; padding-top: 4px;")
        main_layout.addWidget(subtitle_label)

        main_layout.addSpacing(8)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.load_db_button = QPushButton(qta.icon('fa6s.database'), " Load Database")
        self.load_db_button.clicked.connect(self.on_load_from_database)
        toolbar_layout.addWidget(self.load_db_button)

        self.clear_source_button = QPushButton(qta.icon('fa6s.broom'), " Clear Source")
        self.clear_source_button.clicked.connect(self.on_clear_source)
        toolbar_layout.addWidget(self.clear_source_button)

        self.clear_all_button = QPushButton(qta.icon('fa6s.trash-can'), " Clear All")
        self.clear_all_button.clicked.connect(self.on_clear_all)
        toolbar_layout.addWidget(self.clear_all_button)
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        source_icon = QLabel()
        source_icon.setPixmap(qta.icon('fa6s.folder-open', color=theme.get_color('gray')).pixmap(16, 16))
        path_layout.addWidget(source_icon)

        source_label = QLabel("Source:")
        source_label.setStyleSheet("font-weight: bold;")
        source_label.setMinimumWidth(50)
        path_layout.addWidget(source_label)

        self.source_path_input = QLineEdit()
        self.source_path_input.setPlaceholderText("Select source folder or PSD file...")
        self.source_path_input.editingFinished.connect(self.on_source_edited)
        self.source_path_input.setAcceptDrops(True)
        self.source_path_input.dragEnterEvent = DragDropPathMixin.make_drag_enter_handler(self.source_path_input)
        self.source_path_input.dropEvent = DragDropPathMixin.make_drop_handler(self.source_path_input, 'source', self.on_source_dropped)
        path_layout.addWidget(self.source_path_input, 1)

        self.source_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.source_paste_button.setToolTip("Paste from clipboard")
        self.source_paste_button.setMaximumWidth(32)
        self.source_paste_button.clicked.connect(self.on_paste_source)
        path_layout.addWidget(self.source_paste_button)

        self.source_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.source_browse_button.setToolTip("Browse folder")
        self.source_browse_button.setMaximumWidth(32)
        self.source_browse_button.clicked.connect(self.on_browse_source)
        path_layout.addWidget(self.source_browse_button)

        self.source_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.source_open_button.setToolTip("Open folder location")
        self.source_open_button.setMaximumWidth(32)
        self.source_open_button.clicked.connect(self.on_open_source)
        path_layout.addWidget(self.source_open_button)

        main_layout.addLayout(path_layout)

        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)

        output_icon = QLabel()
        output_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        output_layout.addWidget(output_icon)

        output_label = QLabel("Output:")
        output_label.setStyleSheet("font-weight: bold;")
        output_label.setMinimumWidth(50)
        output_layout.addWidget(output_label)

        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Select output folder...")
        self.output_path_input.editingFinished.connect(self.on_output_edited)
        self.output_path_input.setAcceptDrops(True)
        self.output_path_input.dragEnterEvent = DragDropPathMixin.make_drag_enter_handler(self.output_path_input)
        self.output_path_input.dropEvent = DragDropPathMixin.make_drop_handler(self.output_path_input, 'output', self.on_output_dropped)
        output_layout.addWidget(self.output_path_input, 1)

        self.output_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.output_paste_button.setToolTip("Paste from clipboard")
        self.output_paste_button.setMaximumWidth(32)
        self.output_paste_button.clicked.connect(self.on_paste_output)
        output_layout.addWidget(self.output_paste_button)

        self.output_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.output_browse_button.setToolTip("Browse folder")
        self.output_browse_button.setMaximumWidth(32)
        self.output_browse_button.clicked.connect(self.on_browse_output)
        output_layout.addWidget(self.output_browse_button)

        self.output_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.output_open_button.setToolTip("Open folder location")
        self.output_open_button.setMaximumWidth(32)
        self.output_open_button.clicked.connect(self.on_open_output)
        output_layout.addWidget(self.output_open_button)

        main_layout.addLayout(output_layout)
        
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)
        
        # Format
        self.format_combo = QComboBox()
        self.format_combo.addItems(['PNG', 'JPG', 'BMP', 'TIFF', 'WEBP'])
        self.format_combo.setCurrentText('PNG')
        self.format_combo.setMinimumWidth(100)
        options_layout.addWidget(QLabel("Output Format:"))
        options_layout.addWidget(self.format_combo)
        
        # Quality
        quality_label = QLabel("Quality (JPG only):")
        options_layout.addWidget(quality_label)
        
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setMinimum(1)
        self.quality_slider.setMaximum(100)
        self.quality_slider.setMaximumWidth(150)
        self.quality_slider.setEnabled(False)
        self.quality_slider.valueChanged.connect(self.on_quality_changed)
        options_layout.addWidget(self.quality_slider)
        
        self.quality_label = QLabel("90")
        options_layout.addWidget(self.quality_label)
        
        # DPI
        dpi_label = QLabel("DPI:")
        options_layout.addWidget(dpi_label)
        
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setMinimum(1)
        self.dpi_spin.setMaximum(1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setMaximumWidth(80)
        options_layout.addWidget(self.dpi_spin)
        
        options_layout.addStretch()
        
        main_layout.addLayout(options_layout)
        
        self.format_combo.currentTextChanged.connect(self.on_format_changed)

        files_label = QLabel("Loaded Files:")
        files_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(files_label)

        self.files_table = QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["File Name", "Path", "Status"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.files_table.setMinimumHeight(200)
        main_layout.addWidget(self.files_table)

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        self.files_count_label = QLabel("Files: 0")
        self.files_count_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.files_count_label)

        self.processed_label = QLabel("Processed: 0/0")
        self.processed_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.processed_label)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.status_label)

        stats_layout.addStretch()
        main_layout.addLayout(stats_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)

        button_layout.addWidget(self.progress_bar, 1)

        self.convert_button = QPushButton(qta.icon('fa6s.play'), " CONVERT")
        self.convert_button.setMinimumHeight(40)
        self.convert_button.setMinimumWidth(180)
        self.convert_button.clicked.connect(self.on_convert_clicked)
        self._apply_convert_button_style()
        button_layout.addWidget(self.convert_button)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _apply_convert_button_style(self):
        self.convert_button.setStyleSheet(f"""
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

    def _apply_stop_button_style(self):
        """Apply red/danger styling for stop button using error color"""
        from PySide6.QtGui import QColor
        error_base = theme.get_color('error')
        error_hover = QColor(error_base).darker(115).name()
        error_pressed = QColor(error_base).darker(130).name()
        white = theme.get_color('white')
        
        self.convert_button.setStyleSheet(f"""
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

    def _set_convert_button_to_stop(self):
        self.convert_button.setText(" STOP")
        self.convert_button.setIcon(qta.icon('fa6s.stop', color=theme.get_color('white')))
        self._apply_stop_button_style()

    def _set_convert_button_to_convert(self):
        self.convert_button.setText(" CONVERT")
        self.convert_button.setIcon(qta.icon('fa6s.play', color=theme.get_color('white')))
        self.convert_button.setEnabled(True)
        self._apply_convert_button_style()

    def on_format_changed(self, fmt):
        self.quality_slider.setEnabled(fmt.upper() in ['JPG', 'JPEG'])
        self.save_settings()

    def on_quality_changed(self, value):
        self.quality_label.setText(str(value))
        self.save_settings()

    def on_load_from_database(self):
        all_files = self.db.get_all_files()
        self.loaded_files = []

        for file_row in all_files:
            filepath = file_row[1]
            if os.path.exists(filepath) and filepath.lower().endswith('.psd'):
                self.loaded_files.append(filepath)

        self.update_files_table()
        self.update_stats()

    def on_clear_source(self):
        self.loaded_files = []
        self.source_path_input.clear()
        self.update_files_table()
        self.update_stats()

    def on_clear_all(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.worker_thread.wait()

        self.loaded_files = []
        self.source_path_input.clear()
        self.output_path_input.clear()
        self.files_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Idle")
        self.update_stats()

    def on_browse_source(self):
        home_dir = os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", home_dir)
        if folder:
            self.loaded_files = []
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith('.psd'):
                        self.loaded_files.append(os.path.join(root, f))
            if self.loaded_files:
                self.source_path_input.setText(folder)
                self.update_files_table()
                self.update_stats()
            else:
                QMessageBox.information(self, "No PSD Files", f"No PSD files found in:\n{folder}")

    def on_paste_source(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text and os.path.exists(text):
            self.loaded_files = []
            if os.path.isfile(text) and text.lower().endswith('.psd'):
                self.loaded_files = [text]
            elif os.path.isdir(text):
                for root, dirs, files in os.walk(text):
                    for f in files:
                        if f.lower().endswith('.psd'):
                            self.loaded_files.append(os.path.join(root, f))
            
            if self.loaded_files:
                self.source_path_input.setText(text)
                self.update_files_table()
                self.update_stats()
            elif os.path.isdir(text):
                QMessageBox.information(self, "No PSD Files", f"No PSD files found in:\n{text}")
            else:
                QMessageBox.warning(self, "Invalid File", "The pasted path is not a PSD file or folder.")

    def on_open_source(self):
        path = self.source_path_input.text()
        if path and os.path.exists(path):
            import platform
            import subprocess
            if platform.system() == "Windows":
                os.startfile(os.path.dirname(path) if os.path.isfile(path) else path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", os.path.dirname(path) if os.path.isfile(path) else path])
            else:
                subprocess.run(["xdg-open", os.path.dirname(path) if os.path.isfile(path) else path])
        else:
            QMessageBox.information(self, "No Path", "Please enter a valid source path first.")

    def on_source_edited(self):
        path = self.source_path_input.text().strip()
        if not path or not os.path.exists(path):
            return
        
        self.loaded_files = []
        if os.path.isfile(path) and path.lower().endswith('.psd'):
            self.loaded_files = [path]
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    if f.lower().endswith('.psd'):
                        self.loaded_files.append(os.path.join(root, f))
        
        if self.loaded_files:
            self.update_files_table()
            self.update_stats()
        else:
            QMessageBox.information(self, "No PSD Files", f"No PSD files found in:\n{path}")

    def on_source_dropped(self, path):
        """Handle folder dropped onto source field."""
        self.loaded_files = []
        if os.path.isfile(path) and path.lower().endswith('.psd'):
            self.loaded_files = [path]
            self.source_path_input.setText(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    if f.lower().endswith('.psd'):
                        self.loaded_files.append(os.path.join(root, f))
            if self.loaded_files:
                self.source_path_input.setText(path)
            else:
                QMessageBox.information(self, "No PSD Files", f"No PSD files found in:\n{path}")
        self.update_files_table()
        self.update_stats()

    def on_output_dropped(self, path):
        """Handle folder dropped onto output field."""
        self.save_settings()

    def on_browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", os.path.expanduser('~'))
        if folder:
            self.output_path_input.setText(folder)
            self.save_settings()

    def on_paste_output(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text and os.path.exists(text):
            self.output_path_input.setText(text)

    def on_open_output(self):
        path = self.output_path_input.text()
        if path:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            import platform
            import subprocess
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        else:
            QMessageBox.information(self, "No Path", "Please enter an output path first.")

    def on_output_edited(self):
        self.save_settings()

    def update_files_table(self):
        self.files_table.setRowCount(len(self.loaded_files))
        for idx, filepath in enumerate(self.loaded_files):
            name_item = QTableWidgetItem(os.path.basename(filepath))
            path_item = QTableWidgetItem(filepath)
            status_item = QTableWidgetItem("Ready")
            status_item.setIcon(qta.icon('fa6s.circle', color=theme.get_color('gray')))

            self.files_table.setItem(idx, 0, name_item)
            self.files_table.setItem(idx, 1, path_item)
            self.files_table.setItem(idx, 2, status_item)

    def update_stats(self):
        self.files_count_label.setText(f"Files: {len(self.loaded_files)}")
        self.processed_label.setText("Processed: 0/0")

    def on_convert_clicked(self):
        # If processing, this button acts as STOP
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.status_label.setText("Status: Stopping...")
            self.convert_button.setEnabled(False)
            return

        if not self.loaded_files:
            QMessageBox.warning(self, "No Files", "Please load PSD files first.")
            return

        for filepath in self.loaded_files:
            if not filepath.lower().endswith('.psd'):
                QMessageBox.warning(self, "Invalid File", f"Source file must be PSD.\nFile: {os.path.basename(filepath)}")
                return

        output_path = self.output_path_input.text().strip()
        if not output_path:
            QMessageBox.warning(self, "No Output Path", "Please specify an output folder before converting.")
            return

        if not os.path.exists(output_path):
            os.makedirs(output_path, exist_ok=True)

        output_format = self.format_combo.currentText()
        quality = self.quality_slider.value() if self.quality_slider.isEnabled() else 90
        dpi = self.dpi_spin.value()

        self._set_convert_button_to_stop()
        self.status_label.setText("Status: Converting...")
        self.progress_bar.setValue(0)

        self.worker_thread = PSDWorkerThread(
            self.loaded_files, output_path, output_format, quality, dpi, self.db
        )
        self.worker_thread.progress_updated.connect(self.on_progress_updated)
        self.worker_thread.status_updated.connect(self.on_status_updated)
        self.worker_thread.completed.connect(self.on_conversion_completed)
        self.worker_thread.stopped.connect(self.on_conversion_stopped)
        self.worker_thread.error_occurred.connect(self.on_conversion_error)
        self.worker_thread.start()

    def on_progress_updated(self, current, total):
        self.progress_bar.setValue(int((current / total) * 100))
        self.processed_label.setText(f"Processed: {current}/{total}")

    def on_status_updated(self, filename, status):
        for row in range(self.files_table.rowCount()):
            if self.files_table.item(row, 0).text() == filename:
                status_item = self.files_table.item(row, 2)
                status_item.setText(status)
                if status == "Completed":
                    status_item.setIcon(qta.icon('fa6s.circle-check', color=theme.get_color('success')))
                    status_item.setForeground(QColor(theme.get_color('success')))
                elif status == "Failed":
                    status_item.setIcon(qta.icon('fa6s.circle-xmark', color=theme.get_color('error')))
                    status_item.setForeground(QColor(theme.get_color('error')))
                elif status == "Converting":
                    status_item.setIcon(qta.icon('fa6s.spinner', color=theme.get_color('warning'), spin=1.2))
                    status_item.setForeground(QColor(theme.get_color('warning')))
                elif status.startswith("Error"):
                    status_item.setIcon(qta.icon('fa6s.circle-xmark', color=theme.get_color('error')))
                    status_item.setForeground(QColor(theme.get_color('error')))
                break

    def on_conversion_completed(self, processed, total):
        self.status_label.setText(f"Status: Completed ({processed}/{total})")
        self._set_convert_button_to_convert()

        output_path = self.output_path_input.text().strip()
        if output_path and os.path.exists(output_path):
            reply = QMessageBox.question(
                self,
                "Conversion Complete",
                f"Conversion complete! {processed}/{total} files saved to:\n{output_path}\n\nOpen output folder?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_file_explorer(output_path)

    def on_conversion_stopped(self, processed, total):
        """Handle conversion being stopped by user"""
        self.status_label.setText(f"Status: Stopped ({processed}/{total} processed)")
        self._set_convert_button_to_convert()

    def _open_file_explorer(self, path):
        import platform
        import subprocess
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(['explorer', os.path.normpath(path)])
        elif system == "Darwin":
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def on_conversion_error(self, error_msg):
        self.status_label.setText("Status: Error")
        self._set_convert_button_to_convert()
        QMessageBox.critical(self, "Conversion Error", error_msg)

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.worker_thread.wait(3000)
        super().closeEvent(event)