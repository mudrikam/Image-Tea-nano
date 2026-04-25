import os
import json
import shutil
import re
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QApplication, QSplitter,
    QSpinBox, QComboBox, QProgressBar, QMessageBox, QSizePolicy,
    QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QColor
import qtawesome as qta
from config import BASE_PATH
from ui.api_key_section import ApiKeySectionWidget
from ui.theme_system import theme
from .prompted_image_sorter_table_widget import PromptedImageSorterTableWidget
from .prompted_image_sorter_preview_widget import PromptedImageSorterPreviewWidget
from .prompted_image_sorter_stats_widget import PromptedImageSorterStatsWidget
from .prompted_image_sorter_new_folder_dialog import PromptedImageSorterNewFolderDialog
from helpers.tools.prompted_image_sorter_helper import classify_image


class PromptedImageSorterTool(QDialog):
    """Tool for sorting images based on a prompt. Standalone window that closes with main app."""

    # Persistence file path in temp directory (single JSON for all settings)
    SETTINGS_FILE = os.path.join(BASE_PATH, 'temp', 'prompted_image_sorter_user_settings.json')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Prompted Image Sorter')
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setMinimumSize(800, 500)
        self.resize(800, 500)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI with API key section, source, and output."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # --- API Key Section (top) ---
        from database.db_operation import ImageTeaDB
        self.db = ImageTeaDB()
        self.api_key_section = ApiKeySectionWidget(self.db, self)
        main_layout.addWidget(self.api_key_section)

        # Ensure temp directory exists
        self._ensure_temp_dir()

        # --- Source section ---
        source_layout = QHBoxLayout()
        source_layout.setSpacing(8)

        source_icon = QLabel()
        source_icon.setPixmap(qta.icon('fa6s.folder-open', color=theme.get_color('gray')).pixmap(16, 16))
        source_layout.addWidget(source_icon)

        source_label = QLabel("Source:")
        source_label.setStyleSheet("font-weight: bold;")
        source_label.setMinimumWidth(50)
        source_layout.addWidget(source_label)

        self.source_path_input = QLineEdit()
        self.source_path_input.setPlaceholderText("Select source folder containing images...")
        source_layout.addWidget(self.source_path_input, 1)

        self.source_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.source_paste_button.setToolTip("Paste path from clipboard")
        self.source_paste_button.setMaximumWidth(32)
        self.source_paste_button.clicked.connect(self.on_paste_source)
        source_layout.addWidget(self.source_paste_button)

        self.source_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.source_browse_button.setToolTip("Browse source folder")
        self.source_browse_button.setMaximumWidth(32)
        self.source_browse_button.clicked.connect(self.on_browse_source)
        source_layout.addWidget(self.source_browse_button)

        self.source_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.source_open_button.setToolTip("Open source folder")
        self.source_open_button.setMaximumWidth(32)
        self.source_open_button.clicked.connect(self.on_open_source)
        source_layout.addWidget(self.source_open_button)

        main_layout.addLayout(source_layout)

        # --- Output section ---
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
        self.output_path_input.setPlaceholderText("Select output folder for sorted images...")
        output_layout.addWidget(self.output_path_input, 1)

        self.output_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.output_paste_button.setToolTip("Paste path from clipboard")
        self.output_paste_button.setMaximumWidth(32)
        self.output_paste_button.clicked.connect(self.on_paste_output)
        output_layout.addWidget(self.output_paste_button)

        self.output_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.output_browse_button.setToolTip("Browse output folder")
        self.output_browse_button.setMaximumWidth(32)
        self.output_browse_button.clicked.connect(self.on_browse_output)
        output_layout.addWidget(self.output_browse_button)

        self.output_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.output_open_button.setToolTip("Open output folder")
        self.output_open_button.setMaximumWidth(32)
        self.output_open_button.clicked.connect(self.on_open_output)
        output_layout.addWidget(self.output_open_button)

        main_layout.addLayout(output_layout)

        # --- Table controls bar ---
        table_controls = QHBoxLayout()
        table_controls.setSpacing(6)

        # Left side: New Folder + Import/Export
        self.new_folder_button = QPushButton(qta.icon('fa6s.folder-plus'), " New Folder")
        self.new_folder_button.setToolTip("Create new folder for sorted images")
        self.new_folder_button.clicked.connect(self.on_new_folder)
        table_controls.addWidget(self.new_folder_button)

        self.import_button = QPushButton(qta.icon('fa6s.file-import'), "")
        self.import_button.setToolTip("Import folder structure from JSON file")
        self.import_button.setMaximumWidth(32)
        self.import_button.clicked.connect(self.on_import_structure)
        table_controls.addWidget(self.import_button)

        self.export_button = QPushButton(qta.icon('fa6s.file-export'), "")
        self.export_button.setToolTip("Export folder structure to JSON file")
        self.export_button.setMaximumWidth(32)
        self.export_button.clicked.connect(self.on_export_structure)
        table_controls.addWidget(self.export_button)

        table_controls.addSpacing(16)

        # Middle: Batch size spinner
        batch_label = QLabel("Batch:")
        batch_label.setStyleSheet("font-size: 11px;")
        table_controls.addWidget(batch_label)

        self.batch_spinner = QSpinBox()
        self.batch_spinner.setMinimum(1)
        self.batch_spinner.setMaximum(20)
        self.batch_spinner.setValue(3)
        self.batch_spinner.setToolTip("Number of concurrent AI requests")
        self.batch_spinner.valueChanged.connect(self._on_settings_changed)
        table_controls.addWidget(self.batch_spinner)

        # Max retries spinner
        retry_label = QLabel("Retry:")
        retry_label.setStyleSheet("font-size: 11px;")
        table_controls.addWidget(retry_label)

        self.max_retries_spinner = QSpinBox()
        self.max_retries_spinner.setMinimum(1)
        self.max_retries_spinner.setMaximum(10)
        self.max_retries_spinner.setValue(3)
        self.max_retries_spinner.setToolTip("Max retries on AI failure")
        table_controls.addWidget(self.max_retries_spinner)

        # Mode combobox (move/copy)
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("font-size: 11px;")
        table_controls.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["copy", "move"])
        self.mode_combo.setToolTip("File operation mode: copy (keep original) or move (delete original)")
        table_controls.addWidget(self.mode_combo)

        # Rename checkbox (default true)
        self.rename_checkbox = QCheckBox("Rename")
        self.rename_checkbox.setChecked(True)

        # Load max reason words from AI instructions config for tooltip
        try:
            config_path = os.path.join(BASE_PATH, 'configs', 'prompted_image_sorter_ai_instructions.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            folder_instructions = config.get('folder_instructions', '')
            match = re.search(r'maximum (\d+) words', folder_instructions)
            max_words = match.group(1) if match else None
        except Exception:
            max_words = None
        self.max_reason_words = int(max_words) if max_words is not None else None

        if self.max_reason_words is not None:
            self.rename_checkbox.setToolTip(f"Rename files using AI reason ({max_words} words max) + timestamp")
        else:
            self.rename_checkbox.setToolTip("Rename files using AI reason + timestamp")
        self.rename_checkbox.stateChanged.connect(self._on_settings_changed)
        table_controls.addWidget(self.rename_checkbox)

        table_controls.addStretch()
        main_layout.addLayout(table_controls)

        # --- Table with preview (splitter) ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        self.table = PromptedImageSorterTableWidget(self)
        self.table.row_added.connect(self._on_folders_changed)
        self.table.row_deleted.connect(self._on_folders_changed)
        self.table.row_renamed.connect(self._on_folders_changed)
        self.table.data_changed.connect(self._on_folders_changed)
        self.table.edit_row_requested.connect(self.edit_folder_row)
        splitter.addWidget(self.table)

        # Set preview widget to match sort button width
        self.preview_widget = PromptedImageSorterPreviewWidget(self)
        self.preview_widget.setFixedWidth(220)
        splitter.addWidget(self.preview_widget)

        main_layout.addWidget(splitter, 1)

        # --- Bottom bar: stats on left, pause & sort buttons on right ---
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        bottom_bar.setSpacing(8)

        self.stats_widget = PromptedImageSorterStatsWidget(self)
        self.stats_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bottom_bar.addWidget(self.stats_widget, 1)  # stretch factor 1

        bottom_bar.addStretch()

        # Initialize state flags before button creation
        self._is_sorting = False
        self._is_paused = False
        self._stopped_early = False
        self._stop_message_shown = False  # guard against double dialog

        # Pause button (initially disabled)
        self.pause_button = QPushButton(qta.icon('fa6s.pause'), " Pause")
        self.pause_button.setToolTip("Pause sorting")
        self.pause_button.setEnabled(False)
        self.pause_button.setMinimumHeight(40)
        self.pause_button.setMinimumWidth(80)
        self.pause_button.setIconSize(QSize(14, 14))
        self.pause_button.clicked.connect(self.on_pause_resume)
        self._update_pause_button_style()
        bottom_bar.addWidget(self.pause_button)

        # Sort button (big, toggle Start/Stop)
        self.run_sort_button = QPushButton(qta.icon('fa6s.play'), " Sort Images")
        self.run_sort_button.setToolTip("Start sorting images using AI")
        self.run_sort_button.setMinimumHeight(40)
        self.run_sort_button.setMinimumWidth(220)
        self.run_sort_button.setIconSize(QSize(16, 16))
        self._update_sort_button_style()
        self.run_sort_button.clicked.connect(self.on_toggle_sort)
        bottom_bar.addWidget(self.run_sort_button)

        main_layout.addLayout(bottom_bar)

        # Load persisted data AFTER all widgets are created
        self._load_all()

    def _update_sort_button_style(self):
        """Update run_sort_button appearance based on sorting state."""
        if self._is_sorting:
            # Stop state: red/danger color
            self.run_sort_button.setText(" Stop")
            self.run_sort_button.setIcon(qta.icon('fa6s.stop'))
            self.run_sort_button.setToolTip("Stop sorting process")
            self.run_sort_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('error')};
                    color: {theme.get_color('white')};
                    font-weight: bold;
                    border-radius: 5px;
                    padding: 5px 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('secondary_hover')};
                }}
            """)
        else:
            # Sort state: primary color
            self.run_sort_button.setText(" Sort Images")
            self.run_sort_button.setIcon(qta.icon('fa6s.play'))
            self.run_sort_button.setToolTip("Start sorting images using AI")
            self.run_sort_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('primary')};
                    color: {theme.get_color('white')};
                    font-weight: bold;
                    border-radius: 5px;
                    padding: 5px 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('primary_hover')};
                }}
            """)

    def _update_pause_button_style(self):
        """Update pause_button appearance based on pause state."""
        if not self._is_sorting:
            # Disabled when not sorting
            self.pause_button.setEnabled(False)
            self.pause_button.setText(" Pause")
            self.pause_button.setIcon(qta.icon('fa6s.pause'))
            self.pause_button.setStyleSheet("")
            return

        # Enable always when sorting
        self.pause_button.setEnabled(True)

        if self._is_paused:
            # Resume state: primary color
            self.pause_button.setText(" Resume")
            self.pause_button.setIcon(qta.icon('fa6s.play'))
            self.pause_button.setToolTip("Resume sorting")
            self.pause_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('primary')};
                    color: {theme.get_color('white')};
                    font-weight: bold;
                    border-radius: 5px;
                    padding: 5px 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('primary_hover')};
                }}
            """)
        else:
            # Pause state: warning color (yellow) with dark text for readability
            self.pause_button.setText(" Pause")
            self.pause_button.setIcon(qta.icon('fa6s.pause'))
            self.pause_button.setToolTip("Pause sorting")
            self.pause_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('warning')};
                    color: black;
                    font-weight: bold;
                    border-radius: 5px;
                    padding: 5px 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('warning')};
                }}
            """)

    def _reset_stats(self):
        """Reset stats to initial state (called on stop)."""
        self.stats_widget.reset_progress()
        self.table.clear_all_highlights()

    # --- Persistence: Temp directory & file management ---
    def _ensure_temp_dir(self):
        """Create temp directory if it doesn't exist."""
        temp_dir = os.path.join(BASE_PATH, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

    def _sanitize_path_text(self, text):
        """Strip surrounding quotes and whitespace from path text."""
        if not isinstance(text, str):
            return text
        t = text.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t

    def _get_start_path(self, path_text):
        """Get valid start directory for file dialog, fallback to home."""
        path = self._sanitize_path_text(path_text)
        if path and os.path.exists(path) and os.path.isdir(path):
            return path
        return os.path.expanduser('~')

    def _load_all(self):
        """Load source/output paths, batch size, retries, folder list, and rename flag from single JSON config file."""
        try:
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Load paths
                    src = data.get('source_path', '')
                    dst = data.get('output_path', '')
                    self.source_path_input.setText(src)
                    self.output_path_input.setText(dst)
                    # Load batch size and max retries
                    batch_size = data.get('batch_size', 3)
                    max_retries = data.get('max_retries', 3)
                    self.batch_spinner.setValue(batch_size)
                    self.max_retries_spinner.setValue(max_retries)
                    # Load rename flag
                    rename = data.get('rename', True)
                    self.rename_checkbox.setChecked(rename)
                    # Load folder list
                    folders = data.get('folders', [])
                    if isinstance(folders, list):
                        self.table.setRowCount(0)
                        for item in folders:
                            fname = item.get('folder_name', '')
                            prompt = item.get('prompt', '')
                            if fname:
                                self.table.add_folder_row(fname, prompt)
        except Exception as e:
            print(f"[PromptedImageSorter] Failed to load config: {e}")
        finally:
            self._update_stats()

    def _save_all(self):
        """Save source/output paths, batch size, retries, folder list, and rename flag to single JSON config file."""
        try:
            src = self._sanitize_path_text(self.source_path_input.text())
            dst = self._sanitize_path_text(self.output_path_input.text())
            batch_size = self.batch_spinner.value()
            max_retries = self.max_retries_spinner.value()
            rename = self.rename_checkbox.isChecked()
            # Collect folder list from table
            rows = self.table.rowCount()
            folders = []
            for r in range(rows):
                fitem = self.table.item(r, 0)
                pitem = self.table.item(r, 1)
                if fitem:
                    fname = fitem.text().strip()
                    prompt = pitem.text().strip() if pitem else ''
                    folders.append({'folder_name': fname, 'prompt': prompt})
            data = {
                'source_path': src,
                'output_path': dst,
                'batch_size': batch_size,
                'max_retries': max_retries,
                'rename': rename,
                'folders': folders
            }
            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[PromptedImageSorter] Failed to save config: {e}")

    def _update_stats(self):
        """Calculate and display real stats from source path."""
        src = self._sanitize_path_text(self.source_path_input.text())
        if not src or not os.path.exists(src):
            self.stats_widget.set_stats(0, 0, "—", "—", "—")
            return

        # Count images in source
        image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
        try:
            files = [f for f in os.listdir(src)
                     if os.path.isfile(os.path.join(src, f)) and os.path.splitext(f)[1].lower() in image_exts]
            source_count = len(files)
        except Exception:
            source_count = 0

        # Count target folders (from table)
        target_folders = self.table.rowCount()
        
        # Get current batch size
        batch_size = self.batch_spinner.value()

        # Only reset elapsed/ETA when not actively sorting (let _on_sort_progress handle them during sort)
        if not self._is_sorting:
            self.stats_widget.set_stats(source_count, target_folders, "—", "—", "—", batch_size=batch_size)
        else:
            # Preserve elapsed/ETA if sorting is in progress
            self.stats_widget.set_stats(source_count, target_folders, "—", "—", "—", batch_size=batch_size)

    def _on_path_changed(self):
        """Handle any path change: save and update stats."""
        self._save_all()
        if not self._is_sorting:
            self._update_stats()

    def _on_settings_changed(self):
        """Handle settings change (batch size, retries): save and update stats."""
        self._save_all()
        # Update stats to show current batch size
        if not self._is_sorting:
            self._update_stats()

    def _on_folders_changed(self, *args):
        """Folder table changed – save and refresh stats."""
        self._save_all()
        # Only update source count if not actively sorting (preserve elapsed/ETA)
        if not self._is_sorting:
            self._update_stats()

    def on_browse_source(self):
        """Open folder dialog to select source folder."""
        start_path = self._get_start_path(self.source_path_input.text())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Source Folder", start_path
        )
        if folder:
            folder = self._sanitize_path_text(folder)
            self.source_path_input.setText(folder)
            self._on_path_changed()

    def on_paste_source(self):
        """Paste path from clipboard with sanitization."""
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            text = self._sanitize_path_text(text)
            self.source_path_input.setText(text)
            self._on_path_changed()

    def on_open_source(self):
        """Open the source folder in file explorer."""
        path = self._sanitize_path_text(self.source_path_input.text())
        if path and os.path.exists(path):
            os.startfile(path)

    def on_browse_output(self):
        """Open folder dialog to select output folder."""
        start_path = self._get_start_path(self.output_path_input.text())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", start_path
        )
        if folder:
            folder = self._sanitize_path_text(folder)
            self.output_path_input.setText(folder)
            self._on_path_changed()

    def on_paste_output(self):
        """Paste path from clipboard with sanitization."""
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            text = self._sanitize_path_text(text)
            self.output_path_input.setText(text)
            self._on_path_changed()

    def on_open_output(self):
        """Open the output folder in file explorer."""
        path = self._sanitize_path_text(self.output_path_input.text())
        if path and os.path.exists(path):
            os.startfile(path)

    def on_new_folder(self):
        """Open dialog to create a new sorting folder."""
        dialog = PromptedImageSorterNewFolderDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            folder_name, prompt = dialog.get_data()
            if folder_name and prompt:
                self.table.add_folder_row(folder_name, prompt)

    # --- Import / Export folder structure ---
    def on_import_structure(self):
        """Import folder structure from JSON file."""
        default_home = os.path.expanduser('~')
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Folder Structure", default_home,
            "JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            folders = data if isinstance(data, list) else data.get('folders', [])
            if not folders:
                QMessageBox.information(self, "Import", "No folder data found in file.")
                return
            # Clear existing and add imported
            self.table.setRowCount(0)
            for item in folders:
                fname = item.get('folder_name', '')
                prompt = item.get('prompt', '')
                if fname:
                    self.table.add_folder_row(fname, prompt)
            self._save_all()
        except Exception as e:
            QMessageBox.warning(self, "Import Error", f"Failed to import: {e}")

    def on_export_structure(self):
        """Export folder structure to JSON file."""
        default_home = os.path.expanduser('~')
        default_name = f"Image_Tea_Sort_Preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Folder Structure", os.path.join(default_home, default_name),
            "JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return
        try:
            folders = self.table.get_folder_data()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(folders, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Export", f"Exported {len(folders)} folders to:\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Failed to export: {e}")

    # --- Sorting worker thread ---
    def on_toggle_sort(self):
        """Toggle between start and stop sorting."""
        if self._is_sorting:
            self._stop_sorting()
        else:
            self._start_sorting()

    def _start_sorting(self):
        """Validate and start the sort worker thread."""
        src = self._sanitize_path_text(self.source_path_input.text())
        dst = self._sanitize_path_text(self.output_path_input.text())

        if not src or not os.path.exists(src):
            QMessageBox.warning(self, "Invalid Source", "Please select a valid source folder.")
            return
        if not dst:
            QMessageBox.warning(self, "Invalid Output", "Please select a valid output folder.")
            return
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Folders", "Please add at least one folder rule.")
            return

        # Get API key and model from api_key_section
        api_key = self.api_key_section.get_current_api_key()
        service = self.api_key_section.get_current_service()
        model = self.api_key_section.get_current_model()
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please select an API key.")
            return

        # Collect image files from source
        image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
        try:
            image_files = [
                os.path.join(src, f) for f in os.listdir(src)
                if os.path.isfile(os.path.join(src, f)) and os.path.splitext(f)[1].lower() in image_exts
            ]
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot read source folder: {e}")
            return

        if not image_files:
            QMessageBox.information(self, "No Images", "No images found in source folder.")
            return

        batch_size = self.batch_spinner.value()
        max_retries = self.max_retries_spinner.value()
        mode = self.mode_combo.currentText()
        rename = self.rename_checkbox.isChecked()
        folders = self.table.get_folder_data()

        # Set sorting state and update UI
        self._is_sorting = True
        self._is_paused = False
        self._stopped_early = False
        self._update_sort_button_style()
        self._update_pause_button_style()
        self.pause_button.setEnabled(True)
        self.stats_widget.set_progress_max(len(image_files))
        self.table.clear_all_highlights()

        # Start worker
        self._worker = PromptedImageSorterWorker(
            api_key=api_key, service=service, model=model,
            image_files=image_files, output_path=dst,
            folders=folders, batch_size=batch_size,
            max_retries=max_retries, mode=mode, db=self.db,
            table=self.table, rename=rename,
            max_reason_words=self.max_reason_words
        )
        # Initialize batch display
        self.stats_widget.set_current_batch(0, batch_size)
        self._worker.progress_updated.connect(self._on_sort_progress)
        self._worker.retry_updated.connect(self._on_retry_updated)
        self._worker.retry_cleared.connect(self._on_retry_cleared)
        self._worker.image_processed.connect(self._on_image_processed)
        self._worker.finished.connect(self._on_sort_finished)
        self._worker.start()

    def _stop_sorting(self):
        """Stop the running sort worker."""
        self._stopped_early = True
        if hasattr(self, '_worker') and self._worker:
            self._worker.stop()
            # Do NOT wait here — _on_sort_finished will be called by worker's finished signal

    def on_pause_resume(self):
        """Toggle pause/resume of sorting."""
        if not self._is_sorting:
            return
        if self._is_paused:
            # Resume
            if hasattr(self, '_worker') and self._worker:
                self._worker.resume()
            self._is_paused = False
        else:
            # Pause
            if hasattr(self, '_worker') and self._worker:
                self._worker.pause()
            self._is_paused = True
        self._update_pause_button_style()

    def _on_sort_progress(self, current, total, elapsed, remaining, retry_current=0, retry_max=0, last_retry=0):
        """Update stats during sorting. last_retry param is used to show concurrent processing count."""
        self.stats_widget.set_progress_value(current)
        remaining_files = total - current
        self.stats_widget.set_stats(
            source_count=total,
            target_count=self.table.rowCount(),
            elapsed=elapsed,
            remaining_time=remaining,
            remaining_files=str(remaining_files)
        )
        # Show concurrent batch count in batch_label
        self.stats_widget.set_current_batch(last_retry, self._worker.batch_size)

    def _on_retry_updated(self, current, maximum):
        """Called when a retry occurs during sorting."""
        print(f"[Tool] _on_retry_updated called: {current}/{maximum}")
        self.stats_widget.set_retry(current, maximum)

    def _on_retry_cleared(self):
        """Called when file processing is done to clear retry display."""
        self.stats_widget.set_retry(0, self._worker.max_retries if hasattr(self, '_worker') and self._worker else 0)

    def _on_image_processed(self, original_path, compressed_path, target_folder, duration_ms, reason):
        """Called when an image has been processed."""
        # Highlight the target folder row in table with opacity (like prompt generator's 'copied' style)
        folders = self.table.get_folder_data()
        for idx, fdata in enumerate(folders):
            if fdata['folder_name'] == target_folder:
                highlight_color = QColor(theme.get_color('warning'))
                highlight_color.setAlpha(int(0.3 * 255))  # 30% opacity
                self.table.highlight_row(idx, highlight_color, duration_ms=3000)
                break
        # Update preview with compressed image and output folder
        self.preview_widget.load_image(compressed_path, target_folder, duration_ms)

    def _on_sort_finished(self):
        """Called when sorting is complete (or stopped)."""
        # Guard: only run once
        if getattr(self, '_finish_handling', False):
            return
        self._finish_handling = True

        self._is_sorting = False
        self._is_paused = False
        self._update_sort_button_style()
        self._update_pause_button_style()

        if self._stopped_early:
            self._reset_stats()
            QMessageBox.information(self, "Stopped", "Sorting process was stopped.")

        self._stopped_early = False
        # Reset concurrent batch display, then update stats to show static config
        self.stats_widget.reset_batch()
        self._update_stats()
        self._finish_handling = False

    def edit_folder_row(self, row):
        """Open dialog to edit folder name and prompt for the given row."""
        if row < 0 or row >= self.table.rowCount():
            return
        fitem = self.table.item(row, 0)
        pitem = self.table.item(row, 1)
        if not fitem:
            return
        current_folder = fitem.text()
        current_prompt = pitem.text() if pitem else ''
        dlg = PromptedImageSorterNewFolderDialog(
            self,
            edit_mode=True,
            initial_folder=current_folder,
            initial_prompt=current_prompt
        )
        if dlg.exec():
            new_folder, new_prompt = dlg.get_data()
            fitem.setText(new_folder)
            pitem.setText(new_prompt)
            # Emit data_changed for auto-save
            self.table.data_changed.emit()

    def closeEvent(self, event):
        if hasattr(self, '_worker') and self._worker:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(3000)
        event.accept()


# =============================================================================
# Worker thread for image sorting with AI
# =============================================================================
class PromptedImageSorterWorker(QThread):
    """Background worker that sorts images using AI."""

    progress_updated = Signal(int, int, str, str, int, int, int)  # current, total, elapsed, remaining, retry_current, retry_max, last_retry
    image_processed = Signal(str, str, str, int, str)  # original_path, compressed_path, target_folder, duration_ms, reason
    retry_updated = Signal(int, int)  # current_retry, max_retries
    retry_cleared = Signal()  # signal to clear retry display
    finished = Signal()

    def __init__(self, api_key, service, model, image_files, output_path,
                 folders, batch_size, max_retries, mode, db, max_reason_words,
                 table=None, rename=False):
        super().__init__()
        self.api_key = api_key
        self.service = service
        self.model = model
        self.image_files = image_files
        self.output_path = output_path
        self.folders = folders
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.mode = mode
        self.db = db
        self.table = table  # reference to table for realtime folder data
        self.rename = rename  # whether to rename files using AI reason
        self.max_reason_words = max_reason_words
        self._stop_flag = {'stop': False}
        self._pause_flag = {'pause': False}
        self._elapsed_start = None
        self._current_retry = 0  # track retry for current image

    def stop(self):
        self._stop_flag['stop'] = True

    def pause(self):
        self._pause_flag['pause'] = True

    def resume(self):
        self._pause_flag['pause'] = False

    def run(self):
        import time
        import json
        import re
        import threading
        from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
        from helpers.image_compression_helper import compress_and_save_image
        from config import BASE_PATH

        self._elapsed_start = time.time()
        total = len(self.image_files)
        processed = 0
        processed_lock = threading.Lock()
        # No shared _current_retry — each task uses its own local retry count
        self._current_retry = 0  # just for stats reset fallback

        # --- Helper: load system prompt from config JSON ---
        def load_system_prompt():
            config_path = os.path.join(BASE_PATH, 'configs', 'prompted_image_sorter_ai_instructions.json')
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return (
                    config.get('system_instructions', ''),
                    config.get('folder_instructions', ''),
                    config.get('response_format', '{"folder": "name"}')
                )
            except Exception as e:
                print(f"[SortWorker] Failed to load config: {e}")
                return (
                    "Classify this image into one of the folders.",
                    "",
                    '{"folder": "name"}'
                )

        # Reload config JSON and folder data
        system_instructions, folder_instructions, response_format = load_system_prompt()
        current_folders = self.table.get_folder_data() if hasattr(self, 'table') else self.folders

        # Build folder list for AI with clearer descriptions
        folder_list_lines = []
        for idx, f in enumerate(current_folders, 1):
            folder_list_lines.append(f"{idx}. {f['folder_name']}")
            folder_list_lines.append(f"   → {f['prompt']}")
        folder_list_text = "\n".join(folder_list_lines)

        # Build full system prompt
        system_prompt = (
            f"{system_instructions}\n\n"
            f"{folder_instructions}\n\n"
            f"AVAILABLE FOLDERS:\n{folder_list_text}\n\n"
            f"{response_format}"
        )

        # Track currently processing count for batch display
        currently_processing = 0
        batch_lock = threading.Lock()

        def process_single_image(file_path):
            nonlocal processed, currently_processing
            if self._stop_flag['stop']:
                return None

            # Pause handling
            while self._pause_flag.get('pause', False) and not self._stop_flag['stop']:
                time.sleep(0.1)
            if self._stop_flag['stop']:
                return None

            start_time = time.time()
            target_folder = None
            compressed_path = None
            reason = ""
            last_retry_value = 0

            # Update "currently processing" count
            with batch_lock:
                currently_processing += 1
                self.progress_updated.emit(processed, total, "—", "—", 0, self.max_retries, currently_processing)

            # Compress image
            try:
                compressed_path = compress_and_save_image(file_path)
            except Exception as e:
                print(f"[SortWorker] Compression failed: {e}")

            # Classify with retries
            retry_count = 0
            success = False
            while retry_count < self.max_retries and not success and not self._stop_flag['stop']:
                try:
                    folder, reason_str = classify_image(
                        image_path=compressed_path or file_path,
                        api_key=self.api_key,
                        service=self.service,
                        model=self.model,
                        system_prompt=system_prompt,
                        valid_folders=current_folders,
                        db=self.db
                    )
                    if folder:
                        target_folder = folder
                        reason = reason_str or ""
                        success = True
                    else:
                        retry_count += 1
                        self.retry_updated.emit(retry_count, self.max_retries)
                        if retry_count < self.max_retries:
                            time.sleep(1)
                except Exception as e:
                    retry_count += 1
                    self.retry_updated.emit(retry_count, self.max_retries)
                    if retry_count < self.max_retries:
                        time.sleep(1)

            last_retry_value = retry_count

            # Move/copy if successful
            if target_folder:
                self._move_or_copy_file(file_path, target_folder, reason)

            # Increment processed counter FIRST, then emit with correct count
            with processed_lock:
                processed += 1
                processed_local = processed

            # Calculate elapsed/remaining based on actual processed count
            elapsed_s = int(time.time() - self._elapsed_start)
            remaining_s = int((elapsed_s / processed_local) * (total - processed_local)) if processed_local > 0 else 0
            elapsed_str = f"{elapsed_s // 60:02d}:{elapsed_s % 60:02d}"
            remaining_str = f"{remaining_s // 60:02d}:{remaining_s % 60:02d}"

            # Emit progress with correct processed count and current batch size (before decrement)
            self.progress_updated.emit(processed_local, total, elapsed_str, remaining_str, 0, self.max_retries, currently_processing)

            # Decrement currently processing
            with batch_lock:
                currently_processing -= 1
                self.progress_updated.emit(processed_local, total, elapsed_str, remaining_str, 0, self.max_retries, currently_processing)

            # Cleanup retry display
            self.retry_cleared.emit()

            return (file_path, compressed_path, target_folder, int((time.time() - start_time) * 1000), reason)

        # Process all images with concurrent batch size
        with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
            futures = {executor.submit(process_single_image, fp): fp for fp in self.image_files}
            pending = set(futures.keys())
            
            # Poll for completed futures with timeout to check stop flag frequently
            while pending and not self._stop_flag['stop']:
                done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
                for future in done:
                    try:
                        result = future.result()
                        if result:
                            file_path, compressed_path, target_folder, duration_ms, reason = result
                            if target_folder:
                                self.image_processed.emit(file_path, compressed_path or file_path, target_folder, duration_ms, reason)
                    except Exception as e:
                        # Only log if not stopped (to avoid spam during shutdown)
                        if not self._stop_flag['stop']:
                            print(f"[SortWorker] Task exception: {e}")
            
            # If stop was requested, cancel any remaining pending futures (won't stop already-running threads)
            if self._stop_flag['stop']:
                for future in pending:
                    future.cancel()

        self.finished.emit()

    def _fallback_classify(self, image_path):
        if self.folders:
            return self.folders[0]['folder_name']
        return None

    def _move_or_copy_file(self, src_path, folder_name, reason=""):
        """Move or copy the file to the target folder inside output path."""
        import os
        import shutil
        import re
        # Handle subfolders with backslash
        target_dir = os.path.join(self.output_path, folder_name)
        os.makedirs(target_dir, exist_ok=True)

        original_filename = os.path.basename(src_path)
        base, ext = os.path.splitext(original_filename)

        # Determine destination filename
        if self.rename and reason:
            # Sanitize reason: limit to max_reason_words if set, remove commas and unsafe chars, spaces -> hyphens
            words = reason.strip().split()
            if self.max_reason_words is not None:
                words = words[:self.max_reason_words]
            short_reason = " ".join(words)
            # Remove commas and other unsafe filename characters
            safe_reason = re.sub(r'[<>:"/\\|?*]', '', short_reason).replace(',', '-').replace(' ', '-')
            safe_reason = safe_reason.strip('-')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"{safe_reason}-{timestamp}{ext}"
            dest_path = os.path.join(target_dir, new_filename)
        else:
            dest_path = os.path.join(target_dir, original_filename)

        # Handle duplicate filename
        if os.path.exists(dest_path):
            if self.mode == 'copy' and not self.rename:
                # Copy mode with rename disabled: skip if already exists
                return 'skipped'
            # Otherwise (move mode or rename=True), add counter to avoid overwrite
            base_dest, ext_dest = os.path.splitext(dest_path)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = f"{base_dest}_{counter}{ext_dest}"
                counter += 1

        if self.mode == 'move':
            shutil.move(src_path, dest_path)
        else:
            shutil.copy2(src_path, dest_path)
        return 'ok'
