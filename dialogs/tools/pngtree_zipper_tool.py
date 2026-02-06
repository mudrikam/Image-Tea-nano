import sys
import os
import subprocess
import zipfile
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy,
    QProgressBar, QFileDialog, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QColor

import qtawesome as qta

from config import BASE_PATH
from database.db_operation import ImageTeaDB
from ui.theme_system import theme

SUPPORTED_EXTENSIONS = ('.psd', '.ai', '.eps', '.png', '.jpg')


class PngtreeZipperModel:
    def __init__(self):
        self._set = set()
        self.files = []
        self.output_dir = None

    def add_files(self, files):
        added = []
        skipped = []
        for f in files:
            if f in self._set:
                skipped.append(f)
                continue
            self._set.add(f)
            self.files.append(f)
            added.append(f)
        return added, skipped

    def clear_files(self):
        self._set.clear()
        self.files.clear()

    def get_all_files(self):
        return list(self.files)

    def set_output_dir(self, path):
        self.output_dir = path

    def get_output_dir(self):
        return self.output_dir


class PngtreeZipperMainWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        primary = theme.get_color('primary')
        primary_hover = theme.get_color('primary_hover')
        white = theme.get_color('white')
        text_dark = theme.get_color('text_dark')
        error = theme.get_color('error')
        success = theme.get_color('success')

        # Build rgba colors like DragDropWidget: solid border (alpha 0.9) and subtle bg (alpha 0.06)
        primary_q = QColor(primary)
        error_q = QColor(error)
        text_dark_q = QColor(text_dark)

        accept_border_rgba = f"rgba({primary_q.red()}, {primary_q.green()}, {primary_q.blue()}, 0.9)"
        accept_bg_rgba = f"rgba({primary_q.red()}, {primary_q.green()}, {primary_q.blue()}, 0.06)"
        reject_border_rgba = f"rgba({error_q.red()}, {error_q.green()}, {error_q.blue()}, 0.9)"
        reject_bg_rgba = f"rgba({error_q.red()}, {error_q.green()}, {error_q.blue()}, 0.06)"

        self._style_drop_area = f"border: 2px dashed {text_dark}; border-radius: 12px; padding: 24px; min-height: 160px;"
        self._style_drop_area_supported = f"border: 2px dashed {accept_border_rgba}; background-color: {accept_bg_rgba}; border-radius: 12px; padding: 24px; min-height: 160px;"
        self._style_drop_area_unsupported = f"border: 2px dashed {reject_border_rgba}; background-color: {reject_bg_rgba}; border-radius: 12px; padding: 24px; min-height: 160px;"
        self._style_progress = (
            f"QProgressBar {{ background-color: rgba(0,0,0,0.2); border-radius: 6px; height: 12px; }}"
            f" QProgressBar::chunk {{ background-color: {primary}; border-radius: 6px; }}"
        )
        self._style_run_button = (
            f"QPushButton {{ background-color: {primary}; color: {white}; border-radius: 6px; padding: 6px 12px;"
            f" font-size:14px; font-weight:600; min-height:28px; }}"
            f" QPushButton:hover {{ background-color: {primary_hover}; }}"
        )

        layout = QVBoxLayout()

        drop_html = (
            "<div style='font-size:16px;font-weight:600;'>Drag and drop supported files: PSD, AI, EPS, PNG, JPG</div>"
            "<div style='margin-top:12px;font-size:10px;'>Files with the same name will be zipped into one package.</div>"
        )
        self.drop_area = QLabel(drop_html)
        self.drop_area.setAlignment(Qt.AlignCenter)
        self.drop_area.setWordWrap(True)
        self.drop_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.drop_area.setStyleSheet(self._style_drop_area)
        layout.addWidget(self.drop_area)

        self.stats_label = QLabel("Files: 0 | Size: 0B")
        self.stats_label.setAlignment(Qt.AlignLeft)
        self.stats_label.setStyleSheet("font-size:12px;")
        layout.addWidget(self.stats_label, alignment=Qt.AlignLeft)

        self.output_label = QLabel("Output: (not set)")
        self.output_label.setAlignment(Qt.AlignLeft)
        self.output_label.setStyleSheet(f"font-size:12px; color: {text_dark};")

        self.open_output_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.open_output_button.setFixedSize(28, 28)
        self.open_output_button.setFlat(True)
        self.open_output_button.setEnabled(False)
        self.open_output_button.clicked.connect(self.open_output)

        self.wa_button = QPushButton(qta.icon('fa6b.whatsapp', color='white'), "")
        self.wa_button.setFixedSize(28, 28)
        self.wa_button.setFlat(True)
        self.wa_button.setToolTip("Join WhatsApp group")
        self.wa_button.clicked.connect(self.open_whatsapp)

        self.reset_button = QPushButton(qta.icon('fa6s.broom'), "")
        self.reset_button.setFixedSize(28, 28)
        self.reset_button.setFlat(True)

        self.load_db_button = QPushButton(qta.icon('fa6s.database'), "")
        self.load_db_button.setFixedSize(28, 28)
        self.load_db_button.setFlat(True)
        self.load_db_button.setToolTip("Load files from database")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.open_output_button)
        btn_row.addWidget(self.reset_button)
        btn_row.addWidget(self.load_db_button)
        btn_row.addWidget(self.wa_button)
        btn_row.addStretch()

        col = QVBoxLayout()
        col.addWidget(self.output_label)
        col.addLayout(btn_row)
        layout.addLayout(col)

        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setTextVisible(True)
        self.overall_progress.setFormat("Overall: %p%")
        self.overall_progress.setStyleSheet(self._style_progress)
        layout.addWidget(self.overall_progress)

        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        self.file_progress.setValue(0)
        self.file_progress.setTextVisible(True)
        self.file_progress.setFormat("File: %p%")
        self.file_progress.setStyleSheet(self._style_progress)
        layout.addWidget(self.file_progress)

        layout.addStretch()

        self.run_button = QPushButton(qta.icon('fa6s.play', color='white'), "Run batch zip")
        self.run_button.setIconSize(QSize(18, 18))
        self.run_button.setStyleSheet(self._style_run_button)
        self.run_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.run_button.setMaximumHeight(28)
        layout.addWidget(self.run_button)

        self.setLayout(layout)
        self.setAcceptDrops(True)

    def _check_supported(self, urls):
        files = [url.toLocalFile() for url in urls]
        supported_files = [f for f in files if f.lower().endswith(SUPPORTED_EXTENSIONS)]
        return files, supported_files

    def dragEnterEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        files, supported_files = self._check_supported(event.mimeData().urls())
        if supported_files and len(supported_files) == len(files):
            self.drop_area.setStyleSheet(self._style_drop_area_supported)
            event.accept()
        elif supported_files:
            self.drop_area.setStyleSheet(self._style_drop_area_unsupported)
            event.accept()
        else:
            self.drop_area.setStyleSheet(self._style_drop_area_unsupported)
            event.ignore()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        files, supported_files = self._check_supported(event.mimeData().urls())
        if supported_files and len(supported_files) == len(files):
            self.drop_area.setStyleSheet(self._style_drop_area_supported)
            event.accept()
        elif supported_files:
            self.drop_area.setStyleSheet(self._style_drop_area_unsupported)
            event.accept()
        else:
            self.drop_area.setStyleSheet(self._style_drop_area_unsupported)
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_area.setStyleSheet(self._style_drop_area)
        event.accept()

    def dropEvent(self, event):
        files, supported_files = self._check_supported(event.mimeData().urls())
        print(f"Dropped supported files: {supported_files}")
        dialog = self._get_dialog()
        if dialog and hasattr(dialog, 'model'):
            added, skipped = dialog.model.add_files(supported_files)
            all_files = dialog.model.get_all_files()
            self.update_stats(all_files)
            dialog.statusBar().showMessage(f"Added {len(added)} files, skipped {len(skipped)}", 5000)
        else:
            self.update_stats(supported_files)
        self.set_overall_progress(0)
        self.set_file_progress(0)
        self.drop_area.setStyleSheet(self._style_drop_area)

    def _get_dialog(self):
        w = self.window()
        if isinstance(w, PngtreeZipperDialog):
            return w
        return None

    def _human_size(self, n):
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                if unit == "B":
                    return f"{n}{unit}"
                return f"{n:.2f}{unit}"
            n /= 1024
        return f"{n:.2f}PB"

    def update_stats(self, files):
        count = len(files)
        total = 0
        for f in files:
            try:
                total += os.path.getsize(f)
            except Exception as e:
                print(f"Error getting size for {f}: {e}")
        self.stats_label.setText(f"Files: {count} | Size: {self._human_size(total)}")

    def set_overall_progress(self, value):
        self.overall_progress.setValue(int(value))

    def set_file_progress(self, value):
        self.file_progress.setValue(int(value))

    def set_output_path(self, path):
        if path:
            self.output_label.setText(f"Output: {path}")
            self.open_output_button.setEnabled(True)
        else:
            self.output_label.setText("Output: (not set)")
            self.open_output_button.setEnabled(False)

    def open_output(self):
        dialog = self._get_dialog()
        path = None
        if dialog and hasattr(dialog, 'model'):
            path = dialog.model.get_output_dir()
        if not path:
            print("No output directory set")
            dialog_w = self._get_dialog()
            if dialog_w:
                dialog_w.statusBar().showMessage("No output directory set", 5000)
            return
        if sys.platform.startswith('win'):
            os.startfile(path)
            return
        if sys.platform.startswith('darwin'):
            subprocess.Popen(['open', path])
            return
        subprocess.Popen(['xdg-open', path])

    def open_whatsapp(self):
        import json
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        url = config["links"]["whatsapp"]
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"Error opening WhatsApp link {url}: {e}")


class PngtreeZipperDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pngtree Zipper")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        self.setMinimumSize(420, 480)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.db = ImageTeaDB()
        self.model = PngtreeZipperModel()

        self.menu_bar = self.create_menu_bar()
        self.main_widget = PngtreeZipperMainWidget(self)
        self._status_bar = QLabel("")
        self._status_bar.setStyleSheet(f"font-size:11px; color: {theme.get_color('text_dark')}; padding: 2px 4px;")

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setMenuBar(self.menu_bar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.addWidget(self.main_widget)
        main_layout.addLayout(content_layout)
        main_layout.addWidget(self._status_bar)

        self.setLayout(main_layout)

        self.main_widget.run_button.clicked.connect(self.run_batch_zip)
        self.main_widget.reset_button.clicked.connect(self.clear_data)
        self.main_widget.load_db_button.clicked.connect(self.load_from_database)

        self._status_timer = None

    def create_menu_bar(self):
        from PySide6.QtWidgets import QMenuBar
        menu_bar = QMenuBar(self)
        file_menu = menu_bar.addMenu("File")

        import_action = file_menu.addAction(qta.icon('fa6s.file-import'), "Import files")
        import_action.triggered.connect(self.import_files)

        select_folder_action = file_menu.addAction(qta.icon('fa6s.folder-open'), "Select Folder")
        select_folder_action.triggered.connect(self.select_folder)

        output_dir_action = file_menu.addAction(qta.icon('fa6s.folder'), "Output Directory")
        output_dir_action.triggered.connect(self.choose_output_directory)

        load_db_action = file_menu.addAction(qta.icon('fa6s.database'), "Load from Database")
        load_db_action.triggered.connect(self.load_from_database)

        clear_action = file_menu.addAction(qta.icon('fa6s.trash'), "Clear data")
        clear_action.triggered.connect(self.clear_data)

        exit_action = file_menu.addAction(qta.icon('fa6s.right-from-bracket'), "Exit")
        exit_action.triggered.connect(self.close)

        about_action = menu_bar.addAction("About")
        about_action.triggered.connect(self.show_about)

        return menu_bar

    def statusBar(self):
        return self

    def showMessage(self, msg, timeout=0):
        self._status_bar.setText(msg)
        if timeout > 0:
            from PySide6.QtCore import QTimer
            if self._status_timer:
                self._status_timer.stop()
            self._status_timer = QTimer(self)
            self._status_timer.setSingleShot(True)
            self._status_timer.timeout.connect(lambda: self._status_bar.setText(""))
            self._status_timer.start(timeout)

    def show_about(self):
        import json
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        msg = QMessageBox(self)
        msg.setWindowTitle("About Pngtree Zipper")
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        icon = QIcon(icon_path)
        pix = icon.pixmap(64, 64)
        msg.setIconPixmap(pix)
        msg.setWindowIcon(icon)
        html = (
            f"Pngtree Zipper v1.0.0<br><br>"
            f"Developer: {config['developer']}<br>"
            f"License: MIT<br><br>"
            f"A simple helper tool to zip asset files to submit to Pngtree.<br><br>"
            f"TikTok: <a href=\"{config['links']['tiktok']}\">@desainia</a><br>"
            f"WhatsApp: <a href=\"{config['links']['whatsapp']}\">Join group</a>"
        )
        msg.setTextFormat(Qt.RichText)
        msg.setTextInteractionFlags(Qt.TextBrowserInteraction)
        msg.setText(html)
        for lbl in msg.findChildren(QLabel):
            lbl.setOpenExternalLinks(True)
        msg.exec()

    def clear_data(self):
        self.model.clear_files()
        self.model.set_output_dir(None)
        self.main_widget.set_output_path(None)
        self.main_widget.update_stats(self.model.get_all_files())
        self.main_widget.set_overall_progress(0)
        self.main_widget.set_file_progress(0)
        self.showMessage("Cleared data and output directory", 5000)

    def import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import files", str(Path.home()),
            "Supported files (*.psd *.ai *.eps *.png *.jpg);;All files (*)"
        )
        if not files:
            return
        added, skipped = self.model.add_files(files)
        self.main_widget.update_stats(self.model.get_all_files())
        self.main_widget.set_overall_progress(0)
        self.main_widget.set_file_progress(0)
        self.showMessage(f"Imported {len(added)} files, skipped {len(skipped)}", 5000)

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select folder to import", str(Path.home()))
        if not path:
            return
        p = Path(path)
        files = [str(f) for f in p.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not files:
            self.showMessage("No supported files found in folder", 5000)
            return
        added, skipped = self.model.add_files(files)
        self.main_widget.update_stats(self.model.get_all_files())
        self.main_widget.set_overall_progress(0)
        self.main_widget.set_file_progress(0)
        self.showMessage(f"Imported {len(added)} files from folder, skipped {len(skipped)}", 5000)

    def choose_output_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Select output directory", str(Path.home()))
        if not path:
            return False
        self.model.set_output_dir(path)
        self.main_widget.set_output_path(path)
        self.showMessage(f"Output directory set: {path}", 5000)
        return True

    def load_from_database(self):
        rows = self.db.get_all_files()
        if not rows:
            self.showMessage("No files found in database", 5000)
            print("No files found in database")
            return
        db_files = []
        for row in rows:
            filepath = row[1]
            if filepath and os.path.isfile(filepath) and filepath.lower().endswith(SUPPORTED_EXTENSIONS):
                db_files.append(filepath)
        if not db_files:
            self.showMessage("No supported files (PSD/AI/EPS/PNG/JPG) found in database", 5000)
            print("No supported files found in database")
            return
        added, skipped = self.model.add_files(db_files)
        self.main_widget.update_stats(self.model.get_all_files())
        self.main_widget.set_overall_progress(0)
        self.main_widget.set_file_progress(0)
        self.showMessage(f"Loaded {len(added)} files from database, skipped {len(skipped)}", 5000)
        print(f"Loaded {len(added)} files from database, skipped {len(skipped)}")

    def run_batch_zip(self):
        files = self.model.get_all_files()
        if not files:
            print("No files to process")
            self.showMessage("No files to process", 5000)
            return
        output_dir = self.model.get_output_dir()
        parents = {Path(f).parent for f in files}
        if not output_dir:
            if len(parents) == 1:
                output_dir = parents.pop()
                self.model.set_output_dir(str(output_dir))
                self.main_widget.set_output_path(str(output_dir))
                self.showMessage(f"Using source folder as output: {output_dir}", 5000)
                print(f"Using source folder as output: {output_dir}")
            else:
                path = QFileDialog.getExistingDirectory(self, "Select output directory", str(Path.home()))
                if not path:
                    print("No output directory selected")
                    self.showMessage("No output directory selected", 5000)
                    return
                output_dir = path
                self.model.set_output_dir(output_dir)
                self.main_widget.set_output_path(output_dir)
                self.showMessage(f"Output directory set: {output_dir}", 5000)

        self.main_widget.run_button.setEnabled(False)

        groups = {}
        parents_map = {}
        for f in files:
            try:
                resolved = str(Path(f).resolve())
            except Exception:
                resolved = str(Path(f))
            stem = Path(resolved).stem
            groups.setdefault(stem, set()).add(resolved)
            parents_map.setdefault(stem, set()).add(Path(resolved).parent)

        for stem, items in list(groups.items()):
            found = set(items)
            for parent in parents_map.get(stem, set()):
                try:
                    for p in parent.iterdir():
                        try:
                            if p.is_file() and p.stem == stem and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                                found.add(str(p.resolve()))
                        except Exception:
                            try:
                                if p.is_file() and p.stem == stem and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                                    found.add(str(p))
                            except Exception as e:
                                print(f"Error checking file {p}: {e}")
                except Exception as e:
                    print(f"Error scanning directory {parent}: {e}")
            groups[stem] = list(found)

        all_included = []
        for items in groups.values():
            all_included.extend(items)
        self.main_widget.update_stats(all_included)

        total_groups = len(groups)
        completed_groups = 0

        for stem, items in groups.items():
            zip_path = Path(output_dir) / f"{stem}.zip"
            try:
                with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                    unique_items = []
                    seen_names = set()
                    for src in items:
                        name = Path(src).name
                        if name in seen_names:
                            continue
                        seen_names.add(name)
                        unique_items.append(src)
                    for idx, src in enumerate(unique_items, start=1):
                        try:
                            current_file_name = Path(src).name
                            file_pct = int((idx / len(unique_items)) * 100)
                            overall_pct = int(((completed_groups) + (idx / len(unique_items))) / total_groups * 100) if total_groups else 100
                            self.main_widget.file_progress.setFormat(f"Zipping: {current_file_name} (%p%)")
                            self.main_widget.set_file_progress(file_pct)
                            self.main_widget.overall_progress.setFormat(f"Overall: {completed_groups+1}/{total_groups} (%p%)")
                            self.main_widget.set_overall_progress(overall_pct)
                            zf.write(src, arcname=current_file_name)
                        except Exception as e:
                            print(f"Error adding {src} to {zip_path}: {e}")
                completed_groups += 1
                self.main_widget.set_overall_progress(int((completed_groups / total_groups) * 100))
                self.main_widget.overall_progress.setFormat(f"Completed: {completed_groups}/{total_groups} (%p%)")
            except Exception as e:
                print(f"Error creating {zip_path}: {e}")

        self.main_widget.set_overall_progress(100)
        self.main_widget.set_file_progress(100)
        self.showMessage(f"Completed {completed_groups} zip(s)", 5000)
        print(f"Completed {completed_groups} zip(s)")
        self.main_widget.run_button.setEnabled(True)
