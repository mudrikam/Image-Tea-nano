import os
import sys
import shutil
import platform
import subprocess
import traceback
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QSplitter, QWidget, QSizePolicy, QApplication, QCheckBox,
    QComboBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QObject, Slot, QThread, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QBrush
import qtawesome as qta

from config import BASE_PATH
from ui.theme_system import theme
from ui.DragDropPathMixin import DragDropPathMixin
from helpers.tools.folder_comparator_helper.folder_comparator_config_helper import FolderComparatorConfig


def stem_lower(name):
    return os.path.splitext(name)[0].lower()


def get_file_size(filepath):
    """Get file size in bytes."""
    try:
        return os.path.getsize(filepath)
    except Exception:
        return 0


def get_missing_files(src_items, dst_items, src_folder='', dst_folder='', consider_size=False, consider_ext=None):
    """Return source filenames that don't exist in destination by stem matching.
    
    Args:
        src_items: Set of source filenames
        dst_items: Set of destination filenames  
        src_folder: Source folder path (needed for size comparison)
        dst_folder: Destination folder path (needed for size comparison)
        consider_size: If True, also compare file sizes
        consider_ext: Dict of extension filters or None
    """
    dst_stems = {stem_lower(n) for n in dst_items}
    missing = set()
    
    for name in src_items:
        src_path = os.path.join(src_folder, name) if src_folder else ''
        src_size = get_file_size(src_path) if consider_size and src_folder else None
        
        if name in dst_items:
            if consider_size:
                dst_path = os.path.join(dst_folder, name) if dst_folder else ''
                dst_size = get_file_size(dst_path)
                if src_size != dst_size:
                    missing.add(name)
            continue
            
        dst_matches = [f for f in dst_items if stem_lower(f) == stem_lower(name)]
        if dst_matches:
            if consider_size and dst_folder:
                for dst_name in dst_matches:
                    dst_path = os.path.join(dst_folder, dst_name)
                    dst_size = get_file_size(dst_path)
                    if src_size != dst_size:
                        missing.add(name)
                        break
            continue
            
        if consider_ext and consider_ext.get('enabled', False):
            ext = os.path.splitext(name)[1].lower()
            ext_list = consider_ext.get('extensions', [])
            if ext_list and ext not in ext_list:
                continue
        missing.add(name)
    return missing


class DropTable(QTableWidget):
    """QTableWidget that accepts folder/file drops and emits the dropped path."""
    pathDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            super().dropEvent(event)
            return
        path = urls[0].toLocalFile()
        if os.path.isfile(path):
            path = os.path.dirname(path)
        self.pathDropped.emit(path)
        event.acceptProposedAction()


class CopyWorker(QObject):
    """Worker that copies files in a separate thread and emits progress."""
    progress = Signal(int, str, int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, src_folder, dst_folder, files):
        super().__init__()
        self.src = src_folder
        self.dst = dst_folder
        self.files = files
        self._running = True

    @Slot()
    def run(self):
        total = len(self.files)
        try:
            for idx, name in enumerate(self.files):
                if not self._running:
                    break
                src_path = os.path.join(self.src, name)
                dst_path = os.path.join(self.dst, name)
                if not os.path.isfile(src_path):
                    self.error.emit(f"Source file not found: {src_path}")
                    continue
                if not os.access(src_path, os.R_OK):
                    self.error.emit(f"No read access to source file: {src_path}")
                    continue
                parent = os.path.dirname(dst_path) or self.dst
                if not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)
                if not os.access(parent, os.W_OK):
                    self.error.emit(f"No write access to destination folder: {parent}")
                    continue
                shutil.copy2(src_path, dst_path)
                self.progress.emit(idx + 1, name, total)
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"Unhandled worker error: {e}\n{tb}")
        finally:
            self.finished.emit()

    def stop(self):
        self._running = False


class CopyController(QObject):
    progress = Signal(int, str, int)
    error = Signal(str)
    finished = Signal()
    started = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._thread = None
        self._running = False

    def start(self, src_folder, dst_folder, files):
        if self._running:
            self.error.emit("Copy already running")
            return
        if not files:
            self.error.emit("No files to copy")
            return
        worker = CopyWorker(src_folder, dst_folder, files)
        thread = QThread()
        worker.moveToThread(thread)
        worker.progress.connect(self.progress, Qt.QueuedConnection)
        worker.error.connect(self.error, Qt.QueuedConnection)
        worker.finished.connect(self._on_worker_finished, Qt.QueuedConnection)
        thread.finished.connect(self._cleanup, Qt.QueuedConnection)
        thread.started.connect(worker.run)
        self._worker = worker
        self._thread = thread
        self._running = True
        self.started.emit()
        thread.start()

    def _on_worker_finished(self):
        if self._thread is not None:
            self._thread.quit()

    def _cleanup(self):
        if self._worker is not None:
            try:
                self._worker.deleteLater()
            except Exception:
                pass
        if self._thread is not None:
            try:
                self._thread.deleteLater()
            except Exception:
                pass
        self._worker = None
        self._thread = None
        self._running = False
        self.finished.emit()

    def stop(self, wait=False, timeout=2000):
        if self._worker is not None:
            self._worker.stop()
        if self._thread is not None:
            try:
                self._thread.quit()
                if wait:
                    self._thread.wait(timeout)
            except Exception:
                pass

    def is_running(self):
        return self._running


class FolderComparatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Folder Comparator")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

        self.config = FolderComparatorConfig()
        self.controller = CopyController()

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._progress_state = {"idx": 0, "name": "", "total": 0, "dirty": False}
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._on_progress_tick)

        self.setup_ui()
        self.load_settings()
        self.resize(820, 560)

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Header
        header_layout = QHBoxLayout()
        header_icon = qta.icon('fa6s.code-compare', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(header_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)

        title_label = QLabel("Folder Comparator")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {theme.get_color('primary')};")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        subtitle_label = QLabel(
            "Compare two folders by filename and copy missing files from source to destination."
        )
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"color: {theme.get_color('gray')}; padding-top: 4px;")
        main_layout.addWidget(subtitle_label)

        main_layout.addSpacing(4)

        # Filter options row (above source)
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        self.size_checkbox = QCheckBox("Consider File Size")
        self.size_checkbox.setToolTip("Compare files by name and size")
        filter_layout.addWidget(self.size_checkbox)

        self.ext_checkbox = QCheckBox("Filter Extensions")
        self.ext_checkbox.setToolTip("Only compare specific file extensions")
        self.ext_checkbox.stateChanged.connect(self.on_ext_filter_toggled)
        filter_layout.addWidget(self.ext_checkbox)

        self.ext_combo = QComboBox()
        self.ext_combo.setMinimumWidth(200)
        self.ext_combo.setEnabled(False)
        self.ext_combo.addItems([
            ".jpg, .jpeg, .png, .gif, .bmp",
            ".psd, .ai, .eps",
            ".mp4, .avi, .mov, .mkv",
            ".pdf, .docx, .xlsx",
            ".mp3, .wav, .flac",
            "Custom"
        ])
        filter_layout.addWidget(self.ext_combo)

        filter_layout.addStretch()

        # Clear and Rescan buttons (normal size like action sequencer)
        self.rescan_button = QPushButton(qta.icon('fa6s.arrows-rotate'), " Rescan")
        self.rescan_button.setToolTip("Rescan source and destination folders")
        self.rescan_button.clicked.connect(self.on_rescan_clicked)
        filter_layout.addWidget(self.rescan_button)

        self.clear_button = QPushButton(qta.icon('fa6s.broom'), " Clear")
        self.clear_button.setToolTip("Reset all fields")
        self.clear_button.clicked.connect(self.on_clear_clicked)
        filter_layout.addWidget(self.clear_button)

        main_layout.addLayout(filter_layout)

        # Source path row
        src_layout = QHBoxLayout()
        src_layout.setSpacing(6)

        src_icon = QLabel()
        src_icon.setPixmap(qta.icon('fa6s.folder-open', color=theme.get_color('gray')).pixmap(16, 16))
        src_layout.addWidget(src_icon)

        src_label = QLabel("Source:")
        src_label.setStyleSheet("font-weight: bold;")
        src_label.setMinimumWidth(80)
        src_layout.addWidget(src_label)

        self.src_input = QLineEdit()
        self.src_input.setPlaceholderText("Drop or select source folder...")
        self.src_input.editingFinished.connect(self.on_src_edited)
        self.src_input.setAcceptDrops(True)
        self.src_input.dragEnterEvent = DragDropPathMixin.make_drag_enter_handler(self.src_input)
        self.src_input.dropEvent = DragDropPathMixin.make_drop_handler(self.src_input, 'folder', self._set_src)
        src_layout.addWidget(self.src_input, 1)

        self.src_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.src_paste_button.setToolTip("Paste from clipboard")
        self.src_paste_button.setMaximumWidth(32)
        self.src_paste_button.clicked.connect(self.on_paste_src)
        src_layout.addWidget(self.src_paste_button)

        self.src_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.src_browse_button.setToolTip("Browse folder")
        self.src_browse_button.setMaximumWidth(32)
        self.src_browse_button.clicked.connect(self.on_browse_src)
        src_layout.addWidget(self.src_browse_button)

        self.src_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.src_open_button.setToolTip("Open folder location")
        self.src_open_button.setMaximumWidth(32)
        self.src_open_button.clicked.connect(self.on_open_src)
        src_layout.addWidget(self.src_open_button)

        self.src_clear_button = QPushButton(qta.icon('fa6s.xmark'), "")
        self.src_clear_button.setToolTip("Clear source")
        self.src_clear_button.setMaximumWidth(32)
        self.src_clear_button.clicked.connect(self.on_clear_src)
        src_layout.addWidget(self.src_clear_button)

        main_layout.addLayout(src_layout)

        # Destination path row
        dst_layout = QHBoxLayout()
        dst_layout.setSpacing(6)

        dst_icon = QLabel()
        dst_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        dst_layout.addWidget(dst_icon)

        dst_label = QLabel("Destination:")
        dst_label.setStyleSheet("font-weight: bold;")
        dst_label.setMinimumWidth(80)
        dst_layout.addWidget(dst_label)

        self.dst_input = QLineEdit()
        self.dst_input.setPlaceholderText("Drop or select destination folder...")
        self.dst_input.editingFinished.connect(self.on_dst_edited)
        self.dst_input.setAcceptDrops(True)
        self.dst_input.dragEnterEvent = DragDropPathMixin.make_drag_enter_handler(self.dst_input)
        self.dst_input.dropEvent = DragDropPathMixin.make_drop_handler(self.dst_input, 'folder', self._set_dst)
        dst_layout.addWidget(self.dst_input, 1)

        self.dst_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.dst_paste_button.setToolTip("Paste from clipboard")
        self.dst_paste_button.setMaximumWidth(32)
        self.dst_paste_button.clicked.connect(self.on_paste_dst)
        dst_layout.addWidget(self.dst_paste_button)

        self.dst_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.dst_browse_button.setToolTip("Browse folder")
        self.dst_browse_button.setMaximumWidth(32)
        self.dst_browse_button.clicked.connect(self.on_browse_dst)
        dst_layout.addWidget(self.dst_browse_button)

        self.dst_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.dst_open_button.setToolTip("Open folder location")
        self.dst_open_button.setMaximumWidth(32)
        self.dst_open_button.clicked.connect(self.on_open_dst)
        dst_layout.addWidget(self.dst_open_button)

        self.dst_clear_button = QPushButton(qta.icon('fa6s.xmark'), "")
        self.dst_clear_button.setToolTip("Clear destination")
        self.dst_clear_button.setMaximumWidth(32)
        self.dst_clear_button.clicked.connect(self.on_clear_dst)
        dst_layout.addWidget(self.dst_clear_button)

        main_layout.addLayout(dst_layout)

        # Tables
        splitter = QSplitter(Qt.Horizontal)

        left_container = QWidget()
        left_v = QVBoxLayout(left_container)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(4)

        left_header = QLabel("Source Files")
        left_header.setStyleSheet("font-weight: bold;")
        left_v.addWidget(left_header)

        self.left_table = DropTable()
        self.left_table.setColumnCount(1)
        self.left_table.setHorizontalHeaderLabels(["Name"])
        self.left_table.horizontalHeader().setStretchLastSection(True)
        self.left_table.setToolTip("Drop a folder here to set Source")
        self.left_table.pathDropped.connect(self.on_src_dropped)
        left_v.addWidget(self.left_table)

        right_container = QWidget()
        right_v = QVBoxLayout(right_container)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(4)

        right_header = QLabel("Destination Files")
        right_header.setStyleSheet("font-weight: bold;")
        right_v.addWidget(right_header)

        self.right_table = DropTable()
        self.right_table.setColumnCount(1)
        self.right_table.setHorizontalHeaderLabels(["Name"])
        self.right_table.horizontalHeader().setStretchLastSection(True)
        self.right_table.setToolTip("Drop a folder here to set Destination")
        self.right_table.pathDropped.connect(self.on_dst_dropped)
        right_v.addWidget(self.right_table)

        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1, 1])
        main_layout.addWidget(splitter, 1)

        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        self.src_count_label = QLabel("Source: 0")
        self.src_count_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.src_count_label)

        self.dst_count_label = QLabel("Destination: 0")
        self.dst_count_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.dst_count_label)

        self.missing_label = QLabel("Missing: 0")
        self.missing_label.setStyleSheet(
            f"font-weight: bold; color: {theme.get_color('error')};"
        )
        stats_layout.addWidget(self.missing_label)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.status_label)

        stats_layout.addStretch()
        main_layout.addLayout(stats_layout)

        # Action row: progress + copy button
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        action_layout.addWidget(self.progress_bar, 1)

        self.copy_button = QPushButton(qta.icon('fa6s.copy'), " COPY MISSING")
        self.copy_button.clicked.connect(self.on_copy_clicked)
        self._apply_copy_button_style()
        action_layout.addWidget(self.copy_button)

        main_layout.addLayout(action_layout)

        self.setLayout(main_layout)

        # Controller signals
        self.controller.progress.connect(self.on_progress, Qt.QueuedConnection)
        self.controller.error.connect(self.on_error, Qt.QueuedConnection)
        self.controller.finished.connect(self.on_finished, Qt.QueuedConnection)
        self.controller.started.connect(lambda: self._progress_timer.start(100), Qt.QueuedConnection)

    def _apply_copy_button_style(self, mode='copy'):
        if mode == 'copy':
            bg = theme.get_color('primary')
            hover = theme.get_color('primary_hover')
            pressed = theme.get_color('primary_pressed')
        else:
            bg = theme.get_color('secondary')
            hover = theme.get_color('secondary_hover')
            pressed = theme.get_color('secondary_pressed')

        self.copy_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {pressed};
            }}
            QPushButton:disabled {{
                background-color: {theme.get_color('button_disabled_bg')};
                color: {theme.get_color('button_disabled_fg')};
            }}
        """)

    # ---- settings persistence ----

    def load_settings(self):
        src = self.config.get('source_path', '')
        dst = self.config.get('destination_path', '')
        self.size_checkbox.setChecked(self.config.get('consider_size', False))
        self.ext_checkbox.setChecked(self.config.get('ext_filter_enabled', False))
        self.ext_combo.setEnabled(self.ext_checkbox.isChecked())

        if src and os.path.isdir(src):
            self.src_input.setText(src)
            self._populate_table(src, self.left_table, self.src_count_label, "Source")
        if dst and os.path.isdir(dst):
            self.dst_input.setText(dst)
            self._populate_table(dst, self.right_table, self.dst_count_label, "Destination")

        self._update_compare_stats()

    def save_settings(self):
        self.config.set('source_path', self.src_input.text().strip())
        self.config.set('destination_path', self.dst_input.text().strip())
        self.config.set('consider_size', self.size_checkbox.isChecked())
        self.config.set('ext_filter_enabled', self.ext_checkbox.isChecked())

    def on_ext_filter_toggled(self, state):
        self.ext_combo.setEnabled(state == Qt.Checked)

    def _get_ext_filter(self):
        if not self.ext_checkbox.isChecked():
            return None
        ext_text = self.ext_combo.currentText()
        if ext_text == "Custom":
            return None
        exts = [e.strip().lower() for e in ext_text.split(',')]
        return {'enabled': True, 'extensions': set(exts)}

    # ---- file table helpers ----

    def _populate_table(self, folder, table_widget, count_label, prefix):
        if not folder:
            table_widget.setRowCount(0)
            count_label.setText(f"{prefix}: 0")
            return set()
        if not os.path.isdir(folder):
            table_widget.setRowCount(0)
            count_label.setText(f"{prefix}: 0")
            return set()
        if not os.access(folder, os.R_OK):
            QMessageBox.critical(self, "Permission denied", f"Cannot access folder:\n{folder}")
            table_widget.setRowCount(0)
            count_label.setText(f"{prefix}: 0")
            return set()

        try:
            entries = sorted(os.listdir(folder))
        except Exception as e:
            QMessageBox.warning(self, "Read error", f"Cannot list folder:\n{folder}\n\n{e}")
            table_widget.setRowCount(0)
            count_label.setText(f"{prefix}: 0")
            return set()

        files = [f for f in entries if os.path.isfile(os.path.join(folder, f))]
        table_widget.setRowCount(len(files))
        for row, name in enumerate(files):
            item = QTableWidgetItem(name)
            table_widget.setItem(row, 0, item)
        count_label.setText(f"{prefix}: {len(files)}")
        return set(files)

    def _get_table_items(self, table_widget):
        items = set()
        for row in range(table_widget.rowCount()):
            it = table_widget.item(row, 0)
            if it:
                items.add(it.text())
        return items

    def _update_compare_stats(self):
        src_items = self._get_table_items(self.left_table)
        dst_items = self._get_table_items(self.right_table)
        src_folder = self.src_input.text().strip()
        dst_folder = self.dst_input.text().strip()
        ext_filter = self._get_ext_filter()
        missing = get_missing_files(
            src_items, dst_items, 
            src_folder, dst_folder,
            self.size_checkbox.isChecked(),
            ext_filter
        )
        self.missing_label.setText(f"Missing: {len(missing)}")

        match_color = QColor(theme.get_color('success'))
        miss_color = QColor(theme.get_color('error'))

        for row in range(self.left_table.rowCount()):
            it = self.left_table.item(row, 0)
            if not it:
                continue
            it.setForeground(QBrush(miss_color if it.text() in missing else match_color))

        src_stems = {stem_lower(n) for n in src_items}
        for row in range(self.right_table.rowCount()):
            it = self.right_table.item(row, 0)
            if not it:
                continue
            name = it.text()
            present = name in src_items or stem_lower(name) in src_stems
            it.setForeground(QBrush(match_color if present else miss_color))

    # ---- source handlers ----

    def on_browse_src(self):
        start = self.src_input.text().strip() or os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", start)
        if folder:
            self._set_src(folder)

    def on_paste_src(self):
        text = QApplication.clipboard().text().strip().strip('"').strip("'")
        if text and os.path.isdir(text):
            self._set_src(text)
        else:
            QMessageBox.warning(self, "Invalid Path", "Clipboard does not contain a valid folder path.")

    def on_open_src(self):
        path = self.src_input.text().strip()
        if path and os.path.isdir(path):
            self._open_in_explorer(path)
        else:
            QMessageBox.information(self, "No Path", "Please set a valid source folder first.")

    def on_src_edited(self):
        path = self.src_input.text().strip()
        if path and os.path.isdir(path):
            self._set_src(path)

    def on_src_dropped(self, path):
        self._set_src(path)

    def _set_src(self, folder):
        self.src_input.setText(folder)
        self._populate_table(folder, self.left_table, self.src_count_label, "Source")
        self._update_compare_stats()
        self.save_settings()

    def on_clear_src(self):
        self.src_input.clear()
        self.left_table.setRowCount(0)
        self.src_count_label.setText("Source: 0")
        self._update_compare_stats()
        self.save_settings()

    # ---- destination handlers ----

    def on_browse_dst(self):
        start = self.dst_input.text().strip() or os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", start)
        if folder:
            self._set_dst(folder)

    def on_paste_dst(self):
        text = QApplication.clipboard().text().strip().strip('"').strip("'")
        if text and os.path.isdir(text):
            self._set_dst(text)
        else:
            QMessageBox.warning(self, "Invalid Path", "Clipboard does not contain a valid folder path.")

    def on_open_dst(self):
        path = self.dst_input.text().strip()
        if path and os.path.isdir(path):
            self._open_in_explorer(path)
        else:
            QMessageBox.information(self, "No Path", "Please set a valid destination folder first.")

    def on_dst_edited(self):
        path = self.dst_input.text().strip()
        if path and os.path.isdir(path):
            self._set_dst(path)

    def on_dst_dropped(self, path):
        self._set_dst(path)

    def _set_dst(self, folder):
        self.dst_input.setText(folder)
        self._populate_table(folder, self.right_table, self.dst_count_label, "Destination")
        self._update_compare_stats()
        self.save_settings()

    def on_clear_dst(self):
        self.dst_input.clear()
        self.right_table.setRowCount(0)
        self.dst_count_label.setText("Destination: 0")
        self._update_compare_stats()
        self.save_settings()

    def on_rescan_clicked(self):
        src = self.src_input.text().strip()
        dst = self.dst_input.text().strip()
        if src and os.path.isdir(src):
            self._populate_table(src, self.left_table, self.src_count_label, "Source")
        if dst and os.path.isdir(dst):
            self._populate_table(dst, self.right_table, self.dst_count_label, "Destination")
        self._update_compare_stats()

    def _open_in_explorer(self, path):
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(['explorer', os.path.normpath(path)])
            elif system == "Darwin":
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QMessageBox.warning(self, "Open folder", f"Failed to open folder:\n{e}")

    # ---- copy / clear handlers ----

    def on_copy_clicked(self):
        if self.controller.is_running():
            self._stop_copy()
        else:
            self._start_copy()

    def _start_copy(self):
        src_folder = self.src_input.text().strip()
        dst_folder = self.dst_input.text().strip()
        if not src_folder or not dst_folder:
            QMessageBox.warning(self, "Missing folder", "Please set both Source and Destination folders before copying.")
            return
        if not os.path.isdir(src_folder) or not os.access(src_folder, os.R_OK):
            QMessageBox.critical(self, "Source folder error", f"Source folder is not accessible:\n{src_folder}")
            return
        if not os.path.isdir(dst_folder) or not os.access(dst_folder, os.W_OK):
            QMessageBox.critical(self, "Destination folder error", f"Destination folder is not writable or does not exist:\n{dst_folder}")
            return

        src_items = self._get_table_items(self.left_table)
        dst_items = self._get_table_items(self.right_table)
        ext_filter = self._get_ext_filter()
        missing = sorted(list(get_missing_files(
            src_items, dst_items,
            src_folder, dst_folder,
            self.size_checkbox.isChecked(),
            ext_filter
        )))

        if not missing:
            QMessageBox.information(self, "Nothing to copy", "No missing files to copy.")
            return

        self.progress_bar.setRange(0, len(missing))
        self.progress_bar.setValue(0)
        try:
            self.progress_bar.setFormat("%v/%m")
        except Exception:
            pass

        self._progress_state.update({"idx": 0, "name": "", "total": len(missing), "dirty": True})
        self._progress_timer.start(100)

        self.status_label.setText("Status: Copying...")
        self.controller.start(src_folder, dst_folder, missing)

        self.copy_button.setText(" STOP")
        self.copy_button.setIcon(qta.icon('fa6s.stop'))
        self._apply_copy_button_style('stop')
        self.clear_button.setEnabled(False)

    def _stop_copy(self):
        self.controller.stop(wait=False)
        self.copy_button.setText(" Stopping...")
        self.copy_button.setEnabled(False)
        self.status_label.setText("Status: Stopping...")
        self._progress_timer.stop()

    def on_clear_clicked(self):
        if self.controller.is_running():
            self.controller.stop(wait=True, timeout=2000)

        self.src_input.clear()
        self.dst_input.clear()
        self.left_table.setRowCount(0)
        self.right_table.setRowCount(0)
        self.src_count_label.setText("Source: 0")
        self.dst_count_label.setText("Destination: 0")
        self.missing_label.setText("Missing: 0")
        self.status_label.setText("Status: Idle")
        self.progress_bar.setValue(0)
        try:
            self.progress_bar.setFormat("%p%")
        except Exception:
            pass
        self._progress_state.update({"idx": 0, "name": "", "total": 0, "dirty": False})
        self._progress_timer.stop()
        self.copy_button.setEnabled(True)
        self.copy_button.setText(" COPY MISSING")
        self.copy_button.setIcon(qta.icon('fa6s.copy'))
        self._apply_copy_button_style('copy')
        self.clear_button.setEnabled(True)
        self.save_settings()

    # ---- worker callbacks ----

    def on_progress(self, idx, name, total):
        self._progress_state.update({"idx": idx, "name": name, "total": total, "dirty": True})

    def on_error(self, msg):
        self._progress_state.update({"name": msg, "dirty": True})
        QMessageBox.critical(self, "Copy error", msg)

    def on_finished(self):
        # Refresh destination
        dst_folder = self.dst_input.text().strip()
        if dst_folder and os.path.isdir(dst_folder):
            self._populate_table(dst_folder, self.right_table, self.dst_count_label, "Destination")
        self._update_compare_stats()

        self.progress_bar.setValue(0)
        try:
            self.progress_bar.setFormat("%p%")
        except Exception:
            pass
        self._progress_state.update({"idx": 0, "name": "", "total": 0, "dirty": False})
        self._progress_timer.stop()

        self.status_label.setText("Status: Completed")
        self.copy_button.setEnabled(True)
        self.copy_button.setText(" COPY MISSING")
        self.copy_button.setIcon(qta.icon('fa6s.copy'))
        self._apply_copy_button_style('copy')
        self.clear_button.setEnabled(True)

        # Offer to open destination
        if dst_folder and os.path.isdir(dst_folder):
            reply = QMessageBox.question(
                self,
                "Copy Complete",
                f"Copy complete. Files saved to:\n{dst_folder}\n\nOpen destination folder?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_in_explorer(dst_folder)

    def _on_progress_tick(self):
        if not self._progress_state["dirty"]:
            return
        idx = self._progress_state["idx"]
        name = self._progress_state["name"]
        total = self._progress_state["total"]
        if total:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(idx)
            self.status_label.setText(f"Status: Copying {name} ({idx}/{total})")
        self._progress_state["dirty"] = False

    def closeEvent(self, event):
        if self.controller.is_running():
            self.controller.stop(wait=True, timeout=2000)
        super().closeEvent(event)
