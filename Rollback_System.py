#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Image Tea Rollback System
=========================
Independent rollback system for Image Tea application.
This script is independent and can run with embedded Python.
It rolls back to a previous version using cached release notes from update_config.json.

Author: Mudrikul Hikam
License: MIT
"""

import os
import sys
import json
import platform
import subprocess
import zipfile
import shutil
import time
import traceback
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QPushButton, QProgressBar, QTextEdit, QMessageBox, QFrame, QSizePolicy,
    QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QPalette, QColor

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from dialogs.backup_global_config_dialog import (
    create_backup_with_prefix, find_latest_backup_with_prefix,
    restore_backup_by_path, parse_backup_filename, set_version_to
)
from ui.theme_system import theme


ZIP_NAME = "Image-Tea-nano.zip"
DOWNLOAD_URL_TEMPLATE = "https://github.com/{owner}/{repo}/releases/download/{tag}/{zip_name}"
SELF_SCRIPT = "Rollback_System.py"
IGNORE_FILES = {SELF_SCRIPT}


def load_app_config():
    config_path = os.path.join(SCRIPT_DIR, "configs", "app_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_repo_info():
    config = load_app_config()
    repo_url = config.get("links", {}).get("repo", "")
    if repo_url.endswith("/"):
        repo_url = repo_url[:-1]
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        raise RuntimeError("Invalid repo URL in config")
    return parts[-2], parts[-1]


def get_current_version():
    config = load_app_config()
    version = config.get("version", "")
    if not version.startswith("v"):
        version = "v" + version
    return version


def get_rollback_versions():
    """Return dict of {tag: release_notes} from update_config.json."""
    update_cfg = os.path.join(SCRIPT_DIR, "configs", "update_config.json")
    with open(update_cfg, "r", encoding="utf-8") as f:
        uc = json.load(f)
    release_notes = uc.get("release_notes", {})
    return release_notes


def _norm_tag(tag):
    return tag[1:] if tag and tag.startswith("v") else (tag or "unknown")


class RollbackThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    log = Signal(str)
    finished_success = Signal()
    finished_error = Signal(str)
    finished_aborted = Signal(str)
    time_info = Signal(str, str, str)

    def __init__(self, target_tag, parent=None):
        super().__init__(parent)
        self.target_tag = target_tag
        self.base_path = SCRIPT_DIR
        self.temp_dir = os.path.join(self.base_path, "temp")
        self.start_time = None

    def run(self):
        try:
            self._do_rollback()
        except Exception as e:
            self.finished_error.emit(str(e) + "\n\n" + traceback.format_exc())

    def _do_rollback(self):
        self.start_time = datetime.now()
        tag = self.target_tag

        self.status.emit("Initializing rollback...")
        self.progress.emit(0)
        self.log.emit(f"Starting rollback to {tag}...")

        os.makedirs(self.temp_dir, exist_ok=True)

        owner, repo = get_repo_info()
        self.log.emit(f"Repository: {owner}/{repo}")

        current_version = get_current_version()
        curr_norm = _norm_tag(current_version)
        tag_norm = _norm_tag(tag)

        # Step 0: Check restore point BEFORE touching anything
        self.status.emit("Checking config restore point...")
        self.progress.emit(1)
        restore_prefix = f"backup_configs_on_update_{tag_norm}_to_"
        self.log.emit(f"Searching for restore point with prefix: {restore_prefix}")
        try:
            restore_backup = find_latest_backup_with_prefix(restore_prefix, base_path=self.base_path)
        except FileNotFoundError:
            restore_backup = None

        restore_ref_file = os.path.join(self.base_path, "temp", "last_rollback_restore_point.txt")

        if not restore_backup:
            self.log.emit(f"No restore point found for prefix: {restore_prefix}")
            abort_msg = (
                f"No config restore point found for version {tag}.\n\n"
                f"The config backup that should have been created when you updated from {tag} "
                f"to a later version could not be found. Without it, there is no safe way to restore "
                f"the configuration to the state it was in while running {tag}.\n\n"
                f"Rollback has been cancelled. No files have been modified."
            )
            self.finished_aborted.emit(abort_msg)
            return

        self.log.emit(f"Restore point found: {restore_backup}")
        with open(restore_ref_file, "w", encoding="utf-8") as f:
            f.write(restore_backup)

        # Step 1: Backup current configs before rollback
        self.status.emit("Creating backup before rollback...")
        self.progress.emit(2)
        prefix = f"backup_configs_on_rollback_{curr_norm}_to_{tag_norm}"
        self.log.emit(f"Creating backup with prefix: {prefix}")
        backup_zip = create_backup_with_prefix(prefix, base_path=self.base_path)
        self.log.emit(f"Backup created: {backup_zip}")

        last_backup_file = os.path.join(self.base_path, "temp", "last_rollback_backup.txt")
        with open(last_backup_file, "w", encoding="utf-8") as f:
            f.write(backup_zip)

        self._update_time_info(5)

        # Step 2: Download the target version release
        self.status.emit(f"Downloading version {tag}...")
        self.progress.emit(10)
        self._update_time_info(10)

        if not HAS_REQUESTS:
            raise RuntimeError("requests library is required for downloading")

        zip_path = os.path.join(self.temp_dir, ZIP_NAME)
        self._download_release(owner, repo, tag, zip_path)
        self.log.emit(f"Downloaded to: {zip_path}")

        # Step 3: Extract
        self.status.emit("Extracting package...")
        self.progress.emit(50)
        self._update_time_info(50)

        extract_path = os.path.join(self.temp_dir, "Image-Tea-nano-rollback-extracted")
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)

        self._extract_zip(zip_path, extract_path)
        self.log.emit(f"Extracted to: {extract_path}")

        # Step 4: Replace application files
        self.status.emit("Replacing files...")
        self.progress.emit(60)
        self._update_time_info(60)

        cache_file = os.path.join(self.base_path, "temp", "health_checker_cache.json")
        flag_file = os.path.join(self.base_path, "temp", ".is_health_verified")
        for p in (cache_file, flag_file):
            if os.path.exists(p):
                try:
                    os.remove(p)
                    self.log.emit(f"Removed stale health file: {p}")
                except Exception as e:
                    self.log.emit(f"Could not remove stale health file {p}: {e}")

        extracted_root = self._find_extracted_root(extract_path)
        if not extracted_root:
            raise RuntimeError("Could not find extracted content root directory")

        self.log.emit(f"Source root: {extracted_root}")
        replaced_count = self._replace_files(extracted_root)
        self.log.emit(f"Replaced {replaced_count} files")

        # Step 5: Cleanup temp files
        self.status.emit("Cleaning up...")
        self.progress.emit(85)
        self._update_time_info(85)

        try:
            os.remove(zip_path)
            self.log.emit("Removed downloaded ZIP")
        except Exception:
            pass

        try:
            shutil.rmtree(extract_path)
            self.log.emit("Removed extraction folder")
        except Exception:
            pass

        # Step 6: Set version in app_config and update_config
        self.status.emit("Setting version...")
        self.progress.emit(90)
        self._update_time_info(90)
        set_version_to(tag, base_path=self.base_path)
        self.log.emit(f"Version set to {tag}")

        self.status.emit("Rollback completed successfully!")
        self.progress.emit(100)
        self._update_time_info(100)
        self.log.emit("=" * 50)
        self.log.emit(f"Rollback to {tag} finished successfully!")
        self.log.emit("=" * 50)

        self.finished_success.emit()

    def _update_time_info(self, progress):
        if not self.start_time:
            return
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split(".")[0]

        if progress > 0:
            total_estimated = elapsed.total_seconds() * (100 / progress)
            remaining_seconds = total_estimated - elapsed.total_seconds()
            remaining = timedelta(seconds=int(remaining_seconds))
            remaining_str = str(remaining).split(".")[0]
            eta = self.start_time + timedelta(seconds=total_estimated)
            eta_str = eta.strftime("%H:%M:%S")
        else:
            remaining_str = "Calculating..."
            eta_str = "Calculating..."

        self.time_info.emit(elapsed_str, remaining_str, eta_str)

    def _download_release(self, owner, repo, tag, dest_path):
        url = DOWNLOAD_URL_TEMPLATE.format(owner=owner, repo=repo, tag=tag, zip_name=ZIP_NAME)
        self.log.emit(f"Downloading from: {url}")

        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()

        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        dl_progress = int(10 + (downloaded / total_size) * 40)
                        self.progress.emit(dl_progress)

        self.log.emit(f"Download complete: {downloaded} bytes")

    def _extract_zip(self, zip_path, extract_path):
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_path)
        self.log.emit("Extraction complete")

    def _find_extracted_root(self, extract_path):
        items = os.listdir(extract_path)
        if len(items) == 1:
            candidate = os.path.join(extract_path, items[0])
            if os.path.isdir(candidate):
                return candidate
        return extract_path

    def _replace_files(self, source_root):
        replaced = 0
        for root, dirs, files in os.walk(source_root):
            for filename in files:
                src_file = os.path.join(root, filename)
                rel_path = os.path.relpath(src_file, source_root)

                if rel_path in IGNORE_FILES or os.path.basename(rel_path) in IGNORE_FILES:
                    self.log.emit(f"Skipping: {rel_path}")
                    continue

                dst_file = os.path.join(self.base_path, rel_path)
                dst_dir = os.path.dirname(dst_file)
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir, exist_ok=True)

                try:
                    shutil.copy2(src_file, dst_file)
                    replaced += 1
                except Exception as e:
                    self.log.emit(f"Failed to copy {rel_path}: {e}")

        return replaced


class StopImageTeaThread(QThread):
    finished = Signal(bool)
    log = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_path = SCRIPT_DIR
        self.max_wait_time = 15

    def run(self):
        try:
            self._stop_image_tea()
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"Error stopping Image Tea: {e}")
            self.finished.emit(False)

    def _stop_image_tea(self):
        signal_file = os.path.join(self.base_path, "temp", "shutdown.signal")
        os.makedirs(os.path.dirname(signal_file), exist_ok=True)

        self.log.emit("Sending shutdown request...")
        with open(signal_file, "w") as f:
            f.write("shutdown")

        self.log.emit("Waiting for Image Tea to close cleanly...")

        start_time = time.time()
        check_interval = 0.5

        while time.time() - start_time < self.max_wait_time:
            time.sleep(check_interval)
            if not self._is_image_tea_running():
                elapsed = time.time() - start_time
                self.log.emit(f"Image Tea closed successfully after {elapsed:.1f}s")
                return

        self.log.emit("Timeout waiting for shutdown to complete, forcing stop...")
        self._force_stop()

        time.sleep(2)
        if not self._is_image_tea_running():
            self.log.emit("Image Tea stopped (forced)")
        else:
            self.log.emit("Warning: Image Tea may still be running")

    def _is_image_tea_running(self):
        lock_file = os.path.join(self.base_path, "temp", "image_tea.lock")
        return os.path.exists(lock_file)

    def _force_stop(self):
        system = platform.system()
        if system == "Windows":
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                subprocess.run(
                    "taskkill /F /IM pythonw.exe",
                    shell=True, check=False, capture_output=True, timeout=10,
                    startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception as e:
                self.log.emit(f"Force stop failed: {e}")
        else:
            try:
                subprocess.run(["pkill", "-9", "-f", "main.py"], check=False, timeout=10)
            except Exception as e:
                self.log.emit(f"Force stop failed: {e}")


class RollbackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Tea Rollback System")
        self.setMinimumSize(600, 450)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        if HAS_QTAWESOME:
            self.setWindowIcon(qta.icon("fa6s.mug-hot", color=theme.get_color("primary")))

        self.rollback_thread = None
        self.stop_thread = None
        self.image_tea_stopped = False
        self._pending_logs = []
        self._target_tag = None

        self._setup_ui()

        QTimer.singleShot(500, self._show_stop_warning)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)

        if HAS_QTAWESOME:
            icon_container = QWidget()
            icon_container.setFixedSize(64, 64)
            icon_container_layout = QHBoxLayout(icon_container)
            icon_container_layout.setContentsMargins(0, 0, 0, 0)
            icon_label = QLabel()
            icon_label.setPixmap(
                qta.icon("fa6s.clock-rotate-left", color=theme.get_color("primary")).pixmap(56, 56)
            )
            icon_label.setAlignment(Qt.AlignCenter)
            icon_container_layout.addWidget(icon_label)
            header_layout.addWidget(icon_container, alignment=Qt.AlignTop)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_label = QLabel("Image Tea Rollback System")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)

        try:
            config = load_app_config()
            developer = config.get("developer", "Unknown")
        except Exception:
            developer = "Desainia Studio"

        developer_label = QLabel(f"Developer: {developer}")
        developer_label.setStyleSheet(
            f"color: {theme.get_color('text_dark')}; font-size: 10pt;"
        )
        title_layout.addWidget(developer_label)

        header_layout.addLayout(title_layout, 1)
        layout.addLayout(header_layout)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep1)

        # Version info row
        version_line = QHBoxLayout()
        version_line.setSpacing(10)
        version_line.addWidget(QLabel("<b>Current:</b>"))
        self.current_version_label = QLabel(get_current_version())
        self.current_version_label.setStyleSheet(
            f"color: {theme.get_color('text_dark')}; font-weight: bold; font-size: 11pt;"
        )
        version_line.addWidget(self.current_version_label)
        version_line.addSpacing(20)
        version_line.addWidget(QLabel("<b>Rollback to:</b>"))
        self.rollback_version_label = QLabel("-")
        self.rollback_version_label.setStyleSheet(
            f"color: {theme.get_color('primary')}; font-weight: bold; font-size: 11pt;"
        )
        version_line.addWidget(self.rollback_version_label)
        version_line.addStretch()
        layout.addLayout(version_line)

        self.time_info_label = QLabel("Elapsed: 00:00:00   Remaining: 00:00:00   ETA: 00:00:00")
        self.time_info_label.setStyleSheet(
            f"font-family: 'Consolas', 'Courier New', monospace; font-size: 10pt; "
            f"color: {theme.get_color('text_dark')};"
        )
        layout.addWidget(self.time_info_label)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        # Version selector
        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(10)
        selector_layout.addWidget(QLabel("<b>Select version to rollback to:</b>"))

        self.version_combo = QComboBox()
        self.version_combo.setMinimumWidth(160)
        self._populate_version_combo()
        self.version_combo.currentIndexChanged.connect(self._on_version_selected)
        selector_layout.addWidget(self.version_combo)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # Release notes
        notes_label = QLabel("Release Notes:")
        layout.addWidget(notes_label)

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setFixedHeight(130)
        self.notes_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme.get_color('background_light')};
                color: {theme.get_color('foreground')};
                font-size: 11px;
                border: 1px solid {theme.get_color('text_dark')};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.notes_text)

        self.status_label = QLabel("Select a version to rollback to.")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {theme.get_color('gray')};
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }}
            QProgressBar::chunk {{
                background-color: {theme.get_color('primary')};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        log_label = QLabel("Rollback Log:")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme.get_color('background_light')};
                color: {theme.get_color('foreground')};
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid {theme.get_color('text_dark')};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.log_text, 1)

        if hasattr(self, "_pending_logs") and self._pending_logs:
            for pending in self._pending_logs:
                self.log_text.append(pending)
            self._pending_logs.clear()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.start_button = QPushButton("Rollback Now")
        if HAS_QTAWESOME:
            self.start_button.setIcon(
                qta.icon("fa6s.clock-rotate-left", color=theme.get_color("white"))
            )
        self.start_button.setMinimumHeight(36)
        self.start_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_button.clicked.connect(self._start_rollback)
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
            QPushButton:disabled {{
                background-color: {theme.get_color('button_disabled_bg')};
                color: {theme.get_color('button_disabled_fg')};
            }}
        """)
        button_layout.addWidget(self.start_button, 1)

        self.relaunch_button = QPushButton("Relaunch App")
        if HAS_QTAWESOME:
            self.relaunch_button.setIcon(
                qta.icon("fa6s.rotate-right", color=theme.get_color("white"))
            )
        self.relaunch_button.setMinimumHeight(36)
        self.relaunch_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.relaunch_button.clicked.connect(self._relaunch_app)
        self.relaunch_button.setEnabled(False)
        self.relaunch_button.hide()
        self.relaunch_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
        """)
        button_layout.addWidget(self.relaunch_button, 1)

        self.close_button = QPushButton("Cancel")
        if HAS_QTAWESOME:
            self.close_button.setIcon(qta.icon("fa6s.xmark"))
        self.close_button.setMinimumHeight(36)
        self.close_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.close_button.clicked.connect(self.close)

        is_dark = self.palette().color(QPalette.Window).lightness() < 128
        if is_dark:
            _white_q = QColor(theme.get_color("white"))
            _white_rgb = f"{_white_q.red()},{_white_q.green()},{_white_q.blue()}"
            close_style = f"""
                QPushButton {{
                    background-color: rgba({_white_rgb},0.06);
                    color: {theme.get_color('white')};
                    border-radius: 6px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    background-color: rgba({_white_rgb},0.09);
                }}
                QPushButton:pressed {{
                    background-color: rgba({_white_rgb},0.12);
                }}
            """
        else:
            _black_q = QColor(theme.get_color("black"))
            _black_rgb = f"{_black_q.red()},{_black_q.green()},{_black_q.blue()}"
            close_style = f"""
                QPushButton {{
                    background-color: rgba({_black_rgb},0.06);
                    color: {theme.get_color('text_dark')};
                    border-radius: 6px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    background-color: rgba({_black_rgb},0.08);
                }}
                QPushButton:pressed {{
                    background-color: rgba({_black_rgb},0.10);
                }}
            """
        self.close_button.setStyleSheet(close_style)
        button_layout.addWidget(self.close_button, 1)

        layout.addLayout(button_layout)

    def _populate_version_combo(self):
        self.version_combo.clear()
        self.version_combo.addItem("-- Select version --", None)

        try:
            rollback_versions = get_rollback_versions()
            current = get_current_version()

            def version_sort_key(v):
                parts = v.lstrip("v").split(".")
                return [int(x) if x.isdigit() else 0 for x in parts]

            sorted_tags = sorted(rollback_versions.keys(), key=version_sort_key, reverse=True)
            for tag in sorted_tags:
                if tag != current:
                    self.version_combo.addItem(tag, tag)
        except Exception as e:
            self._append_log(f"Failed to load versions: {e}")

    def _on_version_selected(self, index):
        tag = self.version_combo.currentData()
        if tag is None:
            self.notes_text.clear()
            self.rollback_version_label.setText("-")
            self.start_button.setEnabled(False)
            self._target_tag = None
            return

        self._target_tag = tag
        self.rollback_version_label.setText(tag)
        self.start_button.setEnabled(self.image_tea_stopped)

        try:
            rollback_versions = get_rollback_versions()
            notes = rollback_versions.get(tag, "No release notes available.")
            self.notes_text.setMarkdown(notes)
        except Exception as e:
            self.notes_text.setPlainText(f"Could not load release notes: {e}")

    def _show_stop_warning(self):
        if self.image_tea_stopped:
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Rollback Warning")
        msg.setText("Image Tea will stop running processes for the rollback.")
        msg.setInformativeText(
            "Please terminate any ongoing work (generations, automations, or other tasks) before continuing.\n\n"
            "The application will be closed and a backup of your current configs will be created before rollback.\n"
            "Do you want to continue?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if HAS_QTAWESOME:
            msg.setIconPixmap(
                qta.icon("fa6s.triangle-exclamation", color=theme.get_color("warning")).pixmap(64, 64)
            )

        result = msg.exec()

        if result == QMessageBox.Yes:
            self._stop_image_tea()
        else:
            self.close()

    def _stop_image_tea(self):
        self.status_label.setText("Stopping Image Tea...")
        self._append_log("Stopping Image Tea application...")
        self.start_button.setEnabled(False)

        self.stop_thread = StopImageTeaThread(self)
        self.stop_thread.log.connect(self._append_log)
        self.stop_thread.finished.connect(self._on_stop_finished)
        self.stop_thread.start()

    def _on_stop_finished(self, success):
        self.image_tea_stopped = True

        if success:
            self._append_log("Image Tea stopped successfully")
        else:
            self._append_log("Warning: Could not confirm Image Tea was stopped")

        self.status_label.setText("Please select a version and click 'Rollback Now' to start the rollback.")
        self._append_log("Please select a version and click 'Rollback Now' to start the rollback.")
        self.version_combo.setEnabled(True)
        self.start_button.setEnabled(self._target_tag is not None)

    def _start_rollback(self):
        if self._target_tag is None:
            return

        self.status_label.setText("Starting rollback...")
        self._append_log(f"Starting rollback to {self._target_tag}...")
        self.start_button.setEnabled(False)
        self.version_combo.setEnabled(False)

        self.rollback_thread = RollbackThread(self._target_tag, self)
        self.rollback_thread.progress.connect(self._update_progress)
        self.rollback_thread.status.connect(self._update_status)
        self.rollback_thread.log.connect(self._append_log)
        self.rollback_thread.time_info.connect(self._update_time_info)
        self.rollback_thread.finished_success.connect(self._on_rollback_success)
        self.rollback_thread.finished_aborted.connect(self._on_rollback_aborted)
        self.rollback_thread.finished_error.connect(self._on_rollback_error)
        self.rollback_thread.start()

    def _update_progress(self, value):
        self.progress_bar.setValue(value)

    def _update_status(self, status):
        self.status_label.setText(status)

    def _update_time_info(self, elapsed, remaining, eta):
        try:
            self.time_info_label.setText(
                f"Elapsed: {elapsed}   Remaining: {remaining}   ETA: {eta}"
            )
        except Exception:
            pass

    def _append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        if hasattr(self, "log_text") and self.log_text is not None:
            self.log_text.append(formatted)
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        else:
            if not hasattr(self, "_pending_logs"):
                self._pending_logs = []
            self._pending_logs.append(formatted)

    def _on_rollback_success(self):
        self.close_button.setEnabled(True)
        self.close_button.setText("Close")
        self.relaunch_button.setEnabled(True)
        self.relaunch_button.show()
        self.start_button.hide()

        target_tag = self._target_tag
        restore_ref_file = os.path.join(SCRIPT_DIR, "temp", "last_rollback_restore_point.txt")
        restore_point_path = None

        if os.path.exists(restore_ref_file):
            with open(restore_ref_file, "r", encoding="utf-8") as f:
                restore_point_path = f.read().strip()

        if restore_point_path and os.path.exists(restore_point_path):
            reply = QMessageBox.question(
                self,
                "Rollback Complete",
                f"Image Tea has been rolled back to {target_tag} successfully!\n\n"
                f"A config restore point was found from when you were running {target_tag}.\n"
                f"Restore point: {os.path.basename(restore_point_path)}\n\n"
                "Do you want to restore configs from this restore point?\n\n"
                "Yes: restore configs from the restore point (settings from when you ran this version).\n"
                "No: keep your current configs.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                print(f"Restoring configs from restore point: {restore_point_path}")
                restore_backup_by_path(restore_point_path, base_path=SCRIPT_DIR, skip_app_config=True)
                set_version_to(target_tag, base_path=SCRIPT_DIR)
                print(f"Config restore completed. Version set to {target_tag}")
            else:
                print("Config restore skipped by user.")

            self._relaunch_app()
        else:
            QMessageBox.information(
                self,
                "Rollback Complete",
                f"Image Tea has been successfully rolled back to {target_tag}!\n\n"
                "No config restore point was found for this version.\n"
                "You can restore configs manually from the Backup Configs dialog.\n\n"
                "Click OK to relaunch.",
            )
            self._relaunch_app()

    def _on_rollback_aborted(self, reason):
        self.close_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.version_combo.setEnabled(True)
        self.status_label.setText("Rollback cancelled.")
        self._append_log(f"ABORTED: {reason}")

        msg = QMessageBox(self)
        msg.setWindowTitle("Rollback Cancelled")
        msg.setText("Rollback cannot proceed.")
        msg.setInformativeText(reason)
        msg.setStandardButtons(QMessageBox.Ok)
        if HAS_QTAWESOME:
            msg.setIconPixmap(
                qta.icon("fa6s.triangle-exclamation", color=theme.get_color("warning")).pixmap(64, 64)
            )
        msg.exec()

    def _on_rollback_error(self, error):
        self.close_button.setEnabled(True)
        self.close_button.setText("Close")
        self.start_button.setEnabled(True)
        self.version_combo.setEnabled(True)
        self.status_label.setText("Rollback failed!")
        self._append_log(f"ERROR: {error}")

        QMessageBox.critical(
            self,
            "Rollback Failed",
            f"The rollback failed with the following error:\n\n{error}\n\n"
            "Please check your internet connection and try again.",
        )

    def _relaunch_app(self):
        system = platform.system()

        if system == "Windows":
            launcher_bat = os.path.join(SCRIPT_DIR, "Launcher.bat")
            if os.path.exists(launcher_bat):
                subprocess.Popen([launcher_bat], shell=False)
            else:
                pythonw_path = os.path.join(SCRIPT_DIR, "python", "Windows", "pythonw.exe")
                main_py = os.path.join(SCRIPT_DIR, "main.py")
                if os.path.exists(pythonw_path) and os.path.exists(main_py):
                    subprocess.Popen([pythonw_path, main_py], shell=False)
                else:
                    QMessageBox.warning(
                        self,
                        "Cannot Relaunch",
                        "Could not find the application launcher.\nPlease start Image Tea manually.",
                    )
                    return
        else:
            launcher_path = os.path.join(SCRIPT_DIR, "Launcher.sh")
            if os.path.exists(launcher_path):
                os.chmod(launcher_path, 0o755)
                subprocess.Popen(["/bin/bash", launcher_path], shell=False)
            else:
                main_py = os.path.join(SCRIPT_DIR, "main.py")
                if os.path.exists(main_py):
                    subprocess.Popen([sys.executable, main_py], shell=False)
                else:
                    QMessageBox.warning(
                        self,
                        "Cannot Relaunch",
                        "Could not find the application launcher.\nPlease start Image Tea manually.",
                    )
                    return

        self.close()


def run_rollback_gui():
    app = QApplication.instance()
    standalone = False

    if app is None:
        app = QApplication(sys.argv)
        standalone = True

    dialog = RollbackDialog()

    if standalone:
        dialog.show()
        sys.exit(app.exec())
    else:
        dialog.exec()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Image Tea Rollback System")
    parser.parse_args()

    run_rollback_gui()


if __name__ == "__main__":
    main()
