import os
import platform
import subprocess
import time
from pathlib import Path
from typing import List, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit,
    QPushButton, QProgressBar, QFileDialog, QMessageBox, QApplication,
    QSpacerItem, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QComboBox, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QDragEnterEvent, QDropEvent, QFont, QColor

import qtawesome as qta
from PIL import Image, UnidentifiedImageError

from config import BASE_PATH
from database.db_operation import ImageTeaDB
from ui.theme_system import theme
from ui.DragDropPathMixin import DragDropPathMixin
from helpers.tools.batch_image_resizer_helper import BatchImageResizerConfig


class ImageResizeWorker(QThread):
    progress_updated = Signal(int, int)
    status_updated = Signal(str, str)
    completed = Signal(int, int)
    error_occurred = Signal(str)

    def __init__(self, image_list: List[Tuple[str, int, int, str]], output_dir: str, resize_mode: str, size_value: int):
        super().__init__()
        self.image_list = image_list
        self.output_dir = output_dir
        self.resize_mode = resize_mode
        self.size_value = size_value
        self.should_stop = False

    def run(self):
        try:
            total_images = len(self.image_list)
            successful_count = 0

            for i, (filepath, width, height, ext) in enumerate(self.image_list):
                if self.should_stop:
                    break

                try:
                    filename = os.path.basename(filepath)
                    self.status_updated.emit(filename, "Resizing")

                    with Image.open(filepath) as img:
                        if img.mode in ('RGBA', 'LA'):
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                            img = background
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')

                        original_width, original_height = img.size

                        if self.resize_mode == "Width":
                            new_width = self.size_value
                            new_height = int((original_height * new_width) / original_width)
                        else:
                            new_height = self.size_value
                            new_width = int((original_width * new_height) / original_height)

                        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                        output_filename = Path(filepath).stem + ".png"
                        output_path = Path(self.output_dir) / output_filename
                        os.makedirs(self.output_dir, exist_ok=True)

                        resized_img.save(output_path, "PNG", quality=95)
                        successful_count += 1
                        self.status_updated.emit(filename, "Completed")

                except Exception as e:
                    filename = os.path.basename(filepath)
                    self.status_updated.emit(filename, f"Error: {str(e)}")

                self.progress_updated.emit(i + 1, total_images)

            self.completed.emit(successful_count, total_images)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.should_stop = True


class DropTableWidget(QTableWidget):
    files_dropped = Signal(list)

    def __init__(self, parent_dialog, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent_dialog
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            file_paths = []
            seen = set()
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                file_path = self.parent_dialog._sanitize_path(file_path)
                if os.path.isdir(file_path):
                    for ext in ['*.png', '*.jpg', '*.jpeg']:
                        for f in Path(file_path).glob(f"**/{ext}"):
                            fp = str(f)
                            if fp not in seen:
                                seen.add(fp)
                                file_paths.append(fp)
                elif os.path.isfile(file_path) and self.parent_dialog._is_image_file(file_path):
                    if file_path not in seen:
                        seen.add(file_path)
                        file_paths.append(file_path)

            if file_paths:
                self.files_dropped.emit(file_paths)
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() == 0:
            from PySide6.QtGui import QPainter
            painter = QPainter(self.viewport())
            painter.save()
            painter.setPen(QColor(120, 120, 120))
            vp = self.viewport()
            cx = vp.width() // 2
            cy = vp.height() // 2
            icon_pix = qta.icon('fa6s.file-arrow-up', color=theme.get_color('text_dark')).pixmap(36, 36)
            painter.drawPixmap(cx - 18, cy - 36, icon_pix)
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(0, cy + 8, vp.width(), 20, Qt.AlignCenter, "Drag and drop images here")
            painter.restore()


class BatchImageResizerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Image Resizer")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.db = ImageTeaDB()
        self.config = BatchImageResizerConfig()
        self.image_list = []
        self.worker_thread = None

        self.setup_ui()
        self.load_settings()
        self.resize(700, 550)

    def load_settings(self):
        last_source = self.config.get('last_source_path', '')
        if last_source:
            self.source_path_input.setText(last_source)

        resize_mode = self.config.get('resize_mode', 'Width')
        self.resize_mode_combo.setCurrentText(resize_mode)

        size_value = self.config.get('size_value', 1500)
        self.size_spin.setValue(size_value)

    def save_settings(self):
        self.config.set('last_source_path', self.source_path_input.text())
        self.config.set('resize_mode', self.resize_mode_combo.currentText())
        self.config.set('size_value', int(self.size_spin.value()))

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        header_layout = QHBoxLayout()
        header_icon = qta.icon('fa6s.crop', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(header_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)

        title_label = QLabel("Batch Image Resizer")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {theme.get_color('primary')};")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        subtitle_label = QLabel("Resize multiple images to specific dimensions in batch")
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
        self.source_path_input.setPlaceholderText("Select source folder or image files...")
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
        self.output_path_input.setPlaceholderText("Output folder (auto-generated from source)...")
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

        self.resize_mode_combo = QComboBox()
        self.resize_mode_combo.addItems(["Height", "Width"])
        self.resize_mode_combo.setCurrentText("Height")
        options_layout.addWidget(QLabel("Resize Mode:"))
        options_layout.addWidget(self.resize_mode_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setMinimum(1)
        self.size_spin.setMaximum(10000)
        self.size_spin.setValue(1500)
        self.size_spin.setMaximumWidth(100)
        options_layout.addWidget(QLabel("Size (pixels):"))
        options_layout.addWidget(self.size_spin)

        options_layout.addStretch()
        main_layout.addLayout(options_layout)

        files_label = QLabel("Image Files:")
        files_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(files_label)

        self.files_table = DropTableWidget(self)
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["File Name", "Original Size", "Status"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.files_table.setMinimumHeight(200)
        self.files_table.setAlternatingRowColors(True)
        self.files_table.files_dropped.connect(self.add_dropped_files)
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

        self.resize_button = QPushButton(qta.icon('fa6s.play'), " RESIZE")
        self.resize_button.setMinimumHeight(40)
        self.resize_button.setMinimumWidth(180)
        self.resize_button.clicked.connect(self.on_resize_clicked)
        self.resize_button.setStyleSheet(f"""
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
        button_layout.addWidget(self.resize_button)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _sanitize_path(self, text):
        if not isinstance(text, str):
            return text
        t = text.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t

    def _is_image_file(self, filepath):
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
        return Path(filepath).suffix.lower() in image_extensions

    def on_load_from_database(self):
        all_files = self.db.get_all_files()
        self.image_list = []
        seen = set()

        for file_row in all_files:
            filepath = file_row[1]
            if os.path.exists(filepath) and self._is_image_file(filepath) and filepath not in seen:
                seen.add(filepath)
                self.image_list.append(filepath)

        self.update_files_table()
        self.update_stats()

    def on_clear_source(self):
        self.image_list = []
        self.source_path_input.clear()
        self.output_path_input.clear()
        self.files_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Idle")
        self.update_stats()

    def on_clear_all(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.worker_thread.wait()

        self.image_list = []
        self.source_path_input.clear()
        self.output_path_input.clear()
        self.files_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.processed_label.setText("Processed: 0/0")
        self.status_label.setText("Status: Idle")
        self.update_stats()

    def on_browse_source(self):
        last_path = self.config.get('last_source_path', '') or os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", last_path)
        if folder:
            self.load_images_from_folder(folder)
            self.source_path_input.setText(folder)
            self.config.set('last_source_path', folder)

    def on_paste_source(self):
        clipboard = QApplication.clipboard()
        text = self._sanitize_path(clipboard.text())
        if text and os.path.exists(text):
            if os.path.isdir(text):
                self.load_images_from_folder(text)
                self.source_path_input.setText(text)
                self.config.set('last_source_path', text)
            elif os.path.isfile(text) and self._is_image_file(text):
                self.image_list = [text]
                self.source_path_input.setText(f"1 file selected")
                self.update_files_table()
                self.update_stats()
            self.update_output_path(text)

    def on_open_source(self):
        path = self._sanitize_path(self.source_path_input.text())
        if path and os.path.exists(path):
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        else:
            QMessageBox.information(self, "No Path", "Please select a source path first.")

    def on_source_edited(self):
        path = self._sanitize_path(self.source_path_input.text())
        if not path or not os.path.exists(path):
            return

        if os.path.isdir(path):
            self.load_images_from_folder(path)
            self.config.set('last_source_path', path)
        elif os.path.isfile(path) and self._is_image_file(path):
            self.image_list = [path]
            self.update_files_table()
            self.update_stats()

        self.update_output_path(path)

    def on_source_dropped(self, path):
        if os.path.isdir(path):
            self.load_images_from_folder(path)
            self.source_path_input.setText(path)
            self.config.set('last_source_path', path)
        elif os.path.isfile(path) and self._is_image_file(path):
            self.image_list = [path]
            self.source_path_input.setText(f"1 file selected")
            self.update_files_table()
            self.update_stats()

        self.update_output_path(path)

    def on_output_dropped(self, path):
        self.save_settings()

    def on_browse_output(self):
        last_output = self.config.get('output_path', '') or os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", last_output)
        if folder:
            self.output_path_input.setText(folder)
            self.config.set('output_path', folder)

    def on_paste_output(self):
        clipboard = QApplication.clipboard()
        text = self._sanitize_path(clipboard.text())
        if text and os.path.exists(text):
            self.output_path_input.setText(text if os.path.isdir(text) else os.path.dirname(text))

    def on_open_output(self):
        path = self._sanitize_path(self.output_path_input.text())
        if path:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
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

    def load_images_from_folder(self, folder):
        self.image_list = []
        seen = set()
        for ext in ['*.png', '*.jpg', '*.jpeg']:
            for f in Path(folder).glob(f"**/{ext}"):
                fp = str(f)
                if fp not in seen:
                    seen.add(fp)
                    self.image_list.append(fp)

        self.update_files_table()
        self.update_stats()

    def add_dropped_files(self, file_paths):
        for file_path in file_paths:
            file_path = self._sanitize_path(file_path)
            if file_path not in self.image_list and self._is_image_file(file_path):
                self.image_list.append(file_path)

        if file_paths:
            folder = os.path.dirname(file_paths[0])
            self.source_path_input.setText(f"{len(self.image_list)} files selected")
            self.config.set('last_source_path', folder)
            self.update_output_path(folder)

        self.update_files_table()
        self.update_stats()

    def update_files_table(self):
        self.files_table.setRowCount(len(self.image_list))
        for idx, filepath in enumerate(self.image_list):
            filename = os.path.basename(filepath)

            try:
                with Image.open(filepath) as img:
                    width, height = img.size
                    size_text = f"{width}x{height}"
            except Exception:
                size_text = "?"

            name_item = QTableWidgetItem(filename)
            size_item = QTableWidgetItem(size_text)
            status_item = QTableWidgetItem("Ready")
            status_item.setIcon(qta.icon('fa6s.circle', color=theme.get_color('gray')))

            self.files_table.setItem(idx, 0, name_item)
            self.files_table.setItem(idx, 1, size_item)
            self.files_table.setItem(idx, 2, status_item)

    def update_output_path(self, source):
        if os.path.isdir(source):
            output_dir = os.path.join(source, "RESIZED")
        else:
            output_dir = os.path.join(os.path.dirname(source), "RESIZED")
        self.output_path_input.setText(output_dir)
        self.config.set('output_path', output_dir)

    def update_stats(self):
        self.files_count_label.setText(f"Files: {len(self.image_list)}")
        self.processed_label.setText("Processed: 0/0")

    def on_resize_clicked(self):
        output_path = self._sanitize_path(self.output_path_input.text())
        if not output_path:
            output_path = self.config.get('output_path', '')
        if not output_path:
            QMessageBox.warning(self, "No Output Path", "Please specify an output folder.")
            return

        if not self.image_list:
            QMessageBox.warning(self, "No Files", "Please add images to resize.")
            return

        size_value = self.size_spin.value()

        self.resize_button.setEnabled(False)
        self.status_label.setText("Status: Resizing...")
        self.progress_bar.setValue(0)

        image_list = []
        for filepath in self.image_list:
            try:
                with Image.open(filepath) as img:
                    width, height = img.size
                ext = Path(filepath).suffix
                image_list.append((filepath, width, height, ext))
            except Exception:
                pass

        self.worker_thread = ImageResizeWorker(image_list, output_path, self.resize_mode_combo.currentText(), size_value)
        self.worker_thread.progress_updated.connect(self.on_progress_updated)
        self.worker_thread.status_updated.connect(self.on_status_updated)
        self.worker_thread.completed.connect(self.on_resize_completed)
        self.worker_thread.error_occurred.connect(self.on_resize_error)
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
                elif status.startswith("Error"):
                    status_item.setIcon(qta.icon('fa6s.circle-xmark', color=theme.get_color('error')))
                    status_item.setForeground(QColor(theme.get_color('error')))
                elif status == "Resizing":
                    status_item.setIcon(qta.icon('fa6s.spinner', color=theme.get_color('warning'), spin=1.2))
                    status_item.setForeground(QColor(theme.get_color('warning')))

    def on_resize_completed(self, processed, total):
        self.status_label.setText(f"Status: Completed ({processed}/{total})")
        self.resize_button.setEnabled(True)

        output_path = self._sanitize_path(self.output_path_input.text())
        if output_path and os.path.exists(output_path):
            reply = QMessageBox.question(
                self,
                "Resize Complete",
                f"Resize complete! {processed}/{total} images saved to:\n{output_path}\n\nOpen output folder?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                if platform.system() == "Windows":
                    subprocess.Popen(['explorer', os.path.normpath(output_path)])
                elif platform.system() == "Darwin":
                    subprocess.Popen(['open', output_path])
                else:
                    subprocess.Popen(['xdg-open', output_path])

    def on_resize_error(self, error_msg):
        self.status_label.setText("Status: Error")
        self.resize_button.setEnabled(True)
        QMessageBox.critical(self, "Resize Error", error_msg)

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.worker_thread.wait(3000)
        super().closeEvent(event)


__all__ = ['BatchImageResizerDialog']