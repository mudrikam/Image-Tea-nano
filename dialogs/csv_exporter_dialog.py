from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QLabel, QGridLayout, QWidget, QPushButton, QHBoxLayout, QLineEdit, QFileDialog, QProgressDialog, QApplication, QSizePolicy, QScrollArea, QFrame, QGroupBox
from PySide6.QtCore import Qt, QFileSystemWatcher
import json
import os
import sys
import datetime
from config import BASE_PATH
from helpers.csv_exporter import export_csv_for_platforms, get_next_index
import qtawesome as qta
from ui.theme_system import theme

class CSVExporterDialog(QDialog):
    CONFIG_PATH = os.path.join(BASE_PATH, "configs", "csv_config.json")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Metadata to CSV")
        self.setFixedWidth(680)
        self.setMinimumHeight(400)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        self.setLayout(main_layout)

        self.config = self.load_config()

        self.fs_watcher = QFileSystemWatcher()
        try:
            if os.path.exists(self.CONFIG_PATH):
                self.fs_watcher.addPath(self.CONFIG_PATH)
            self.fs_watcher.fileChanged.connect(self.on_config_file_changed)
        except Exception as e:
            print(f"[CSVExporterDialog] Error setting up QFileSystemWatcher: {e}")

        self.platforms = [
            "Freepik", "Adobe Stock", "Shutterstock", "iStock",
            "123RF", "Vecteezy", "Pond5", "Depositphotos", "Canva", "MiriCanvas"
        ]
        self.platform_colors = {
            "Freepik": "#1C7AF5", "Adobe Stock": "#CC1818",
            "Shutterstock": "#D12222", "iStock": "#2178C0",
            "123RF": "#FFB20D", "Vecteezy": "#DB621C",
            "Pond5": "#0EA4D6", "Depositphotos": "#19B9CE",
            "Canva": "#007CCF", "MiriCanvas": "#00B2C6",
        }

        # --- split layout: left checkboxes, right csv list ---
        split_layout = QHBoxLayout()
        split_layout.setSpacing(8)
        split_layout.setStretch(0, 0)
        split_layout.setStretch(1, 1)
        main_layout.addLayout(split_layout, 1)

        # LEFT: checkboxes in QGroupBox
        left_group = QGroupBox("Platforms")
        left_v = QVBoxLayout(left_group)
        left_v.setContentsMargins(8, 8, 8, 8)
        left_v.setSpacing(6)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(4)
        self.check_all_btn = QPushButton(qta.icon('fa6s.check'), " Check All")
        self.check_all_btn.setToolTip("Check all platforms")
        self.check_all_btn.clicked.connect(self.check_all)
        ctrl_layout.addWidget(self.check_all_btn)
        self.uncheck_all_btn = QPushButton(qta.icon('fa6s.xmark'), " Uncheck All")
        self.uncheck_all_btn.setToolTip("Uncheck all platforms")
        self.uncheck_all_btn.clicked.connect(self.uncheck_all)
        ctrl_layout.addWidget(self.uncheck_all_btn)
        left_v.addLayout(ctrl_layout)

        cb_scroll = QScrollArea()
        cb_scroll.setWidgetResizable(True)
        cb_scroll.setFrameShape(QFrame.NoFrame)
        cb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cb_inner = QWidget()
        cb_inner_layout = QVBoxLayout(cb_inner)
        cb_inner_layout.setContentsMargins(4, 4, 4, 4)
        cb_inner_layout.setSpacing(6)
        cb_scroll.setWidget(cb_inner)
        left_v.addWidget(cb_scroll)

        self.platform_checkboxes = []
        self.checkbox_map = {}
        for platform in self.platforms:
            color = self.platform_colors.get(platform, theme.get_color('foreground'))
            checkbox = QCheckBox(platform)
            checkbox.setStyleSheet(f"color: {color};")
            checkbox.setChecked(self.config.get(platform, False))
            checkbox.toggled.connect(lambda checked, p=platform: self.on_platform_toggled(p, checked))
            cb_inner_layout.addWidget(checkbox)
            self.platform_checkboxes.append(checkbox)
            self.checkbox_map[platform] = checkbox
        cb_inner_layout.addStretch()

        left_group.setFixedWidth(210)
        split_layout.addWidget(left_group)

        # RIGHT: csv filename list in QGroupBox
        right_group = QGroupBox("Output Filenames")
        right_v = QVBoxLayout(right_group)
        right_v.setContentsMargins(8, 8, 8, 8)
        right_v.setSpacing(4)

        csv_scroll = QScrollArea()
        csv_scroll.setWidgetResizable(True)
        csv_scroll.setFrameShape(QFrame.NoFrame)
        csv_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rename_container = QWidget()
        self.rename_layout = QVBoxLayout(self.rename_container)
        self.rename_layout.setContentsMargins(4, 4, 4, 4)
        self.rename_layout.setSpacing(6)
        csv_scroll.setWidget(self.rename_container)
        right_v.addWidget(csv_scroll)
        split_layout.addWidget(right_group, 1)

        self.rename_rows = {}
        for platform in self.platforms:
            color = self.platform_colors.get(platform, theme.get_color('foreground'))
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon('fa6s.file-csv', color=color).pixmap(16, 16))
            icon_lbl.setFixedWidth(20)
            row_layout.addWidget(icon_lbl)

            entry = QLineEdit()
            entry.setText(self.default_base_name(platform))
            entry.setToolTip("Edit base filename (no index/extension)")
            entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            entry.textChanged.connect(lambda text, p=platform: (self.update_suffixes(), self.validate_output_and_buttons()))
            row_layout.addWidget(entry, 1)

            suffix_label = QLabel("_001.CSV")
            suffix_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
            suffix_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            row_layout.addWidget(suffix_label)

            export_btn = QPushButton(qta.icon('fa6s.file-export', color=theme.get_color('primary')), "")
            export_btn.setToolTip(f"Export {platform} CSV only")
            export_btn.setFixedWidth(28)
            export_btn.setFixedHeight(24)
            export_btn.clicked.connect(lambda _, p=platform: self.export_single_platform(p))
            row_layout.addWidget(export_btn)

            self.rename_layout.addWidget(row_widget)
            self.rename_rows[platform] = (row_widget, entry, suffix_label, export_btn)
            row_widget.setVisible(bool(self.config.get(platform, False)))
        self.rename_layout.addStretch()

        # output path row
        output_layout = QHBoxLayout()
        self.output_lineedit = QLineEdit()
        self.output_lineedit.setPlaceholderText("Select output folder...")
        output_layout.addWidget(self.output_lineedit)

        self.paste_output_btn = QPushButton(qta.icon('fa6s.paste'), "")
        self.paste_output_btn.setToolTip("Paste path from clipboard")
        self.paste_output_btn.setFixedWidth(32)
        self.paste_output_btn.clicked.connect(self.paste_output_path)
        output_layout.addWidget(self.paste_output_btn)

        self.select_output_btn = QPushButton(qta.icon('fa6s.folder-open'), "Select Output")
        self.select_output_btn.setToolTip("Select output folder")
        self.select_output_btn.clicked.connect(self.select_output_path)
        output_layout.addWidget(self.select_output_btn)
        main_layout.addLayout(output_layout)

        bottom_row = QHBoxLayout()
        self.open_folder_checkbox = QCheckBox("Open folder on export")
        self.open_folder_checkbox.setChecked(bool(self.config.get("open_folder_on_export", True)))
        self.open_folder_checkbox.toggled.connect(self.save_config_realtime)
        bottom_row.addWidget(self.open_folder_checkbox)
        bottom_row.addStretch()
        self.ok_btn = QPushButton(qta.icon('fa6s.file-csv', color=theme.get_color('success')), "Export All CSV")
        self.ok_btn.setToolTip("Export metadata to CSV")
        self.ok_btn.clicked.connect(self.export_csv)
        self.ok_btn.setFixedHeight(32)
        bottom_row.addWidget(self.ok_btn)
        main_layout.addLayout(bottom_row)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet(f'color: {theme.get_color("error")}; font-size: 11px')
        self.validation_label.setVisible(False)
        main_layout.addWidget(self.validation_label)

        self.output_lineedit.textChanged.connect(self.on_output_path_changed)
        self.validate_output_and_buttons()

    def paste_output_path(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            sanitized = self._sanitize_path_text(text)
            self.output_lineedit.setText(sanitized)
            self.update_suffixes()

    def select_output_path(self):
        home_dir = os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder", home_dir)
        if path:
            self.output_lineedit.setText(path)
            self.update_suffixes()

    def load_config(self):
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[CSVExporterDialog] Error loading config {self.CONFIG_PATH}: {e}")
                return {}
        else:
            print(f"[CSVExporterDialog] Config file does not exist: {self.CONFIG_PATH}")
            return {}

    def save_config_realtime(self):
        config = {}
        for platform, checkbox in self.checkbox_map.items():
            config[platform] = checkbox.isChecked()
        try:
            config["open_folder_on_export"] = bool(self.open_folder_checkbox.isChecked())
        except Exception:
            config["open_folder_on_export"] = True
        try:
            try:
                if self.fs_watcher and self.fs_watcher.files():
                    if self.CONFIG_PATH in self.fs_watcher.files():
                        self.fs_watcher.removePath(self.CONFIG_PATH)
            except Exception as e:
                print(f"[CSVExporterDialog] Error removing watcher path: {e}")
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            try:
                if os.path.exists(self.CONFIG_PATH):
                    self.fs_watcher.addPath(self.CONFIG_PATH)
            except Exception as e:
                print(f"[CSVExporterDialog] Error adding watcher path: {e}")
        except Exception:
            print(f"[CSVExporterDialog] Error saving config to {self.CONFIG_PATH}")

    def on_config_file_changed(self, path):
        try:
            print(f"[CSVExporterDialog] Config file changed externally: {path}")
            new_config = self.load_config()
            for platform, checkbox in self.checkbox_map.items():
                try:
                    val = bool(new_config.get(platform, False))
                    checkbox.blockSignals(True)
                    checkbox.setChecked(val)
                    checkbox.blockSignals(False)
                    row_widget, entry, suffix, _btn = self.rename_rows[platform]
                    row_widget.setVisible(val)
                except Exception as e:
                    print(f"[CSVExporterDialog] Error applying config for {platform}: {e}")
            try:
                of = bool(new_config.get("open_folder_on_export", True))
                self.open_folder_checkbox.blockSignals(True)
                self.open_folder_checkbox.setChecked(of)
                self.open_folder_checkbox.blockSignals(False)
            except Exception as e:
                print(f"[CSVExporterDialog] Error applying open_folder_on_export: {e}")
            self.update_suffixes()
        except Exception as e:
            print(f"[CSVExporterDialog] Error reloading config file: {e}")

    def default_base_name(self, platform):
        try:
            today = datetime.datetime.now()
            p = platform.replace(" ", "_")
            return f"{p}_Image_Tea_Metadata_{today.year}_{today.strftime('%B')}_{today.day:02d}_"
        except Exception as e:
            print(f"[CSVExporterDialog] Error building default base name for {platform}: {e}")
            return platform.replace(" ", "_") + "_Image_Tea_Metadata_"

    def on_platform_toggled(self, platform, checked):
        try:
            checked_bool = bool(checked)
            self.save_config_realtime()
            row_widget, entry, suffix, _btn = self.rename_rows[platform]
            row_widget.setVisible(checked_bool)
            self.update_suffixes()
            self.validate_output_and_buttons()
        except Exception as e:
            print(f"[CSVExporterDialog] Error toggling platform {platform}: {e}")

    def _sanitize_path_text(self, text):
        if not isinstance(text, str):
            return text
        t = text.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t

    def on_output_path_changed(self, text):
        sanitized = self._sanitize_path_text(text)
        if sanitized != text:
            self.output_lineedit.blockSignals(True)
            self.output_lineedit.setText(sanitized)
            self.output_lineedit.blockSignals(False)
            text = sanitized
        self.update_suffixes()
        self.validate_output_and_buttons()

    def _name_validation(self):
        illegal = '/\\:*?"<>|'
        illegal_set = set(illegal)
        empty = []
        illegal_found = {}
        for p, (w, e, s, _btn) in self.rename_rows.items():
            if not w.isVisible():
                continue
            text = e.text().strip()
            if text == "":
                empty.append(p)
            found = [c for c in text if c in illegal_set]
            if found:
                illegal_found[p] = ''.join(sorted(set(found)))
        if empty:
            names = ', '.join(empty)
            return False, f"A file name is empty for: {names}"
        if illegal_found:
            parts = [f"{plat} ({chars})" for plat, chars in illegal_found.items()]
            return False, "Illegal characters prevent export: " + '; '.join(parts)
        return True, ""

    def check_all(self):
        try:
            for p, cb in self.checkbox_map.items():
                cb.blockSignals(True)
                cb.setChecked(True)
                cb.blockSignals(False)
                row_widget, entry, suffix, _btn = self.rename_rows[p]
                row_widget.setVisible(True)
            self.save_config_realtime()
            self.update_suffixes()
            self.validate_output_and_buttons()
        except Exception as e:
            print(f"[CSVExporterDialog] Error in check_all: {e}")

    def uncheck_all(self):
        try:
            for p, cb in self.checkbox_map.items():
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
                row_widget, entry, suffix, _btn = self.rename_rows[p]
                row_widget.setVisible(False)
            self.save_config_realtime()
            self.update_suffixes()
            self.validate_output_and_buttons()
        except Exception as e:
            print(f"[CSVExporterDialog] Error in uncheck_all: {e}")

    def validate_output_and_buttons(self):
        path = self._sanitize_path_text(self.output_lineedit.text())
        valid = False
        try:
            valid = os.path.isdir(path)
        except Exception as e:
            print(f"[CSVExporterDialog] validate path error: {e}")
            valid = False
        any_selected = any(cb.isChecked() for cb in self.platform_checkboxes)
        names_ok, msg = self._name_validation()
        enabled = valid and any_selected and names_ok
        self.ok_btn.setEnabled(enabled)
        if not names_ok and any_selected:
            self.validation_label.setText(msg)
            self.validation_label.setVisible(True)
        else:
            self.validation_label.setVisible(False)

    def open_folder_windows(self, folder_path):
        if sys.platform.startswith("win"):
            os.startfile(folder_path)

    def export_csv(self):
        selected = [p for p, cb in self.checkbox_map.items() if cb.isChecked()]
        output_path = self._sanitize_path_text(self.output_lineedit.text())
        if not selected:
            print("[CSVExporterDialog] No platforms selected for export")
            return
        if not output_path or not os.path.isdir(output_path):
            print(f"[CSVExporterDialog] Invalid output path: {output_path}")
            return

        name_map = {}
        for p in selected:
            try:
                _, entry, _, _btn = self.rename_rows[p]
                name_map[p] = entry.text()
            except Exception as e:
                print(f"[CSVExporterDialog] Error reading name entry for {p}: {e}")

        from database.db_operation import ImageTeaDB
        db = ImageTeaDB()
        files = db.get_all_files()
        total_files = len(files) * len(selected)
        progress = QProgressDialog("Exporting CSV...", "Cancel", 0, total_files, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        def progress_callback():
            value = progress.value() + 1
            progress.setValue(value)
        export_csv_for_platforms(selected, output_path, progress_callback, name_map)
        progress.setValue(total_files)
        try:
            if bool(self.open_folder_checkbox.isChecked()):
                self.open_folder_windows(output_path)
        except Exception as e:
            print(f"[CSVExporterDialog] Error opening output folder (open_folder_checkbox): {e}")
            try:
                if bool(self.config.get("open_folder_on_export", True)):
                    self.open_folder_windows(output_path)
            except Exception as e2:
                print(f"[CSVExporterDialog] Error opening output folder (config fallback): {e2}")
        self.accept()

    def export_single_platform(self, platform):
        output_path = self._sanitize_path_text(self.output_lineedit.text())
        if not output_path or not os.path.isdir(output_path):
            print(f"[CSVExporterDialog] Invalid output path for single export: {output_path}")
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(
                self.select_output_btn.mapToGlobal(self.select_output_btn.rect().center()),
                "Please select a valid output folder first.",
                self.select_output_btn,
                self.select_output_btn.rect(),
                3000
            )
            return
        try:
            _, entry, _, _btn = self.rename_rows[platform]
            name_map = {platform: entry.text()}
        except Exception as e:
            print(f"[CSVExporterDialog] Error reading name entry for {platform}: {e}")
            return
        from database.db_operation import ImageTeaDB
        db = ImageTeaDB()
        files = db.get_all_files()
        progress = QProgressDialog(f"Exporting {platform} CSV...", "Cancel", 0, len(files), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        def progress_callback():
            progress.setValue(progress.value() + 1)
        export_csv_for_platforms([platform], output_path, progress_callback, name_map)
        progress.setValue(len(files))
        print(f"[CSVExporterDialog] Single export done: {platform}")
        try:
            if bool(self.open_folder_checkbox.isChecked()):
                self.open_folder_windows(output_path)
        except Exception as e:
            print(f"[CSVExporterDialog] Error opening folder after single export: {e}")
        self.update_suffixes()

    def update_suffixes(self):
        path = self._sanitize_path_text(self.output_lineedit.text())
        if not path or not os.path.isdir(path):
            for p, (w, e, s, _btn) in self.rename_rows.items():
                if w.isVisible():
                    s.setText("_001.CSV")
            return
        for p, (w, e, s, _btn) in self.rename_rows.items():
            if not w.isVisible():
                continue
            base = e.text()
            try:
                idx = get_next_index(base, path)
                s.setText(f"_{idx:03d}.CSV")
            except Exception as ex:
                print(f"[CSVExporterDialog] Error computing next index for {p}: {ex}")
