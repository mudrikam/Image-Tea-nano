#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Image Tea Update Worker
=======================
Centralized update worker for Image Tea application.
This script is independent and can run with embedded Python.
It handles downloading, extracting, and replacing application files.

Author: Mudrikul Hikam
License: MIT
"""

import os
import sys
import json
import platform
import subprocess
import tempfile
import zipfile
import shutil
import time
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QPushButton, QProgressBar, QTextEdit, QMessageBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QIcon, QPalette

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

from dialogs.backup_global_config_dialog import create_backup_with_prefix, find_latest_backup_with_prefix, restore_backup_by_path


ZIP_NAME = "Image-Tea-nano.zip"
RELEASES_API_TEMPLATE = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
DOWNLOAD_URL_TEMPLATE = "https://github.com/{owner}/{repo}/releases/download/{tag}/{zip_name}"
SELF_SCRIPT = "Update_Worker.py"
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


def get_fallback_version():
    config = load_app_config()
    version = config.get("fallback_version", config.get("version", "1.0.64"))
    if not version.startswith("v"):
        version = "v" + version
    return version


def get_current_version():
    config = load_app_config()
    version = config.get("version", "")
    if not version.startswith("v"):
        version = "v" + version
    return version


def get_cached_remote_tag():
    """Return cached remote tag from configs/update_config.json, or None if not available."""
    try:
        update_cfg = os.path.join(SCRIPT_DIR, "configs", "update_config.json")
        if os.path.exists(update_cfg):
            with open(update_cfg, "r", encoding="utf-8") as f:
                uc = json.load(f)
            tag_remote = uc.get("tag_remote")
            if tag_remote:
                tag = str(tag_remote)
                if not tag.startswith("v"):
                    tag = "v" + tag
                return tag
    except Exception:
        pass
    return None


def get_latest_tag(owner, repo):
    """Return the latest release tag. Prefer cached tag; fall back to GitHub API and then fallback config."""
    cached = get_cached_remote_tag()
    if cached:
        return cached

    if not HAS_REQUESTS:
        return get_fallback_version()

    try:
        api_url = RELEASES_API_TEMPLATE.format(owner=owner, repo=repo)
        resp = requests.get(api_url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        tag = data.get("tag_name", "")
        if tag:
            return tag
    except Exception:
        pass

    return get_fallback_version()


class UpdateWorkerThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    log = Signal(str)
    finished_success = Signal()
    finished_error = Signal(str)
    update_info = Signal(str, str, str)
    time_info = Signal(str, str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_path = SCRIPT_DIR
        self.temp_dir = os.path.join(self.base_path, "temp")
        self.start_time = None
        
    def run(self):
        try:
            self._do_update()
        except Exception as e:
            self.finished_error.emit(str(e))
    
    def _do_update(self):
        self.start_time = datetime.now()
        self.status.emit("Initializing update...")
        self.progress.emit(0)
        self.log.emit("Starting Image Tea update process...")
        
        os.makedirs(self.temp_dir, exist_ok=True)
        
        self.status.emit("Backing up configs before update...")
        self.progress.emit(2)
        self.log.emit("Creating pre-update backup with prefix 'backup_configs_on_update'...")
        backup_zip = create_backup_with_prefix('backup_configs_on_update', base_path=self.base_path)
        self.log.emit(f"Backup created: {backup_zip}")
        last_backup_file = os.path.join(self.base_path, 'temp', 'last_update_backup_on_update.txt')
        with open(last_backup_file, 'w', encoding='utf-8') as f:
            f.write(backup_zip)
        
        owner, repo = get_repo_info()
        self.log.emit(f"Repository: {owner}/{repo}")
        
        self.status.emit("Fetching latest release info...")
        self.progress.emit(5)
        
        tag = self._fetch_latest_tag(owner, repo)
        self.log.emit(f"Latest release tag: {tag}")
        
        current_version = get_current_version()
        self.update_info.emit(current_version, tag, owner)
        
        self._update_time_info(5)
        
        self.status.emit("Downloading update package...")
        self.progress.emit(10)
        self._update_time_info(10)
        
        zip_path = os.path.join(self.temp_dir, ZIP_NAME)
        self._download_release(owner, repo, tag, zip_path)
        self.log.emit(f"Downloaded to: {zip_path}")
        
        self.status.emit("Extracting update package...")
        self.progress.emit(50)
        self._update_time_info(50)
        
        extract_path = os.path.join(self.temp_dir, "Image-Tea-nano-extracted")
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        
        self._extract_zip(zip_path, extract_path)
        self.log.emit(f"Extracted to: {extract_path}")
        
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
        
        self.status.emit("Cleaning up...")
        self.progress.emit(90)
        self._update_time_info(90)
        
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
        
        self.status.emit("Verifying Update_Worker.py...")
        self.progress.emit(95)
        self._update_time_info(95)
        
        self._verify_self_update(owner, repo, tag)
        
        self.status.emit("Update completed successfully!")
        self.progress.emit(100)
        self._update_time_info(100)
        self.log.emit("=" * 50)
        self.log.emit("Update finished successfully!")
        self.log.emit("=" * 50)
        
        self.finished_success.emit()
    
    def _update_time_info(self, progress):
        if not self.start_time:
            return
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split('.')[0]
        
        if progress > 0:
            total_estimated = elapsed.total_seconds() * (100 / progress)
            remaining_seconds = total_estimated - elapsed.total_seconds()
            remaining = timedelta(seconds=int(remaining_seconds))
            remaining_str = str(remaining).split('.')[0]
            eta = self.start_time + timedelta(seconds=total_estimated)
            eta_str = eta.strftime("%H:%M:%S")
        else:
            remaining_str = "Calculating..."
            eta_str = "Calculating..."
        
        self.time_info.emit(elapsed_str, remaining_str, eta_str)
    
    def _fetch_latest_tag(self, owner, repo):
        try:
            tag = get_latest_tag(owner, repo)
            self.log.emit(f"Latest tag resolved: {tag}")
            return tag
        except Exception as e:
            self.log.emit(f"Failed to resolve latest tag: {e}")
            fallback = get_fallback_version()
            return fallback
    
    def _download_release(self, owner, repo, tag, dest_path):
        if not HAS_REQUESTS:
            raise RuntimeError("requests library is required for downloading updates")
        
        url = DOWNLOAD_URL_TEMPLATE.format(owner=owner, repo=repo, tag=tag, zip_name=ZIP_NAME)
        self.log.emit(f"Downloading from: {url}")
        
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        dl_progress = int(10 + (downloaded / total_size) * 40)
                        self.progress.emit(dl_progress)
        
        self.log.emit(f"Download complete: {downloaded} bytes")
    
    def _extract_zip(self, zip_path, extract_path):
        with zipfile.ZipFile(zip_path, 'r') as z:
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
    
    def _verify_self_update(self, owner, repo, tag):
        self.log.emit("Checking if Update_Worker.py needs updating...")
        
        try:
            tmp_zip = os.path.join(tempfile.gettempdir(), f"verify_{tag}.zip")
            
            if not os.path.exists(tmp_zip):
                url = DOWNLOAD_URL_TEMPLATE.format(owner=owner, repo=repo, tag=tag, zip_name=ZIP_NAME)
                resp = requests.get(url, stream=True, timeout=60)
                resp.raise_for_status()
                with open(tmp_zip, 'wb') as f:
                    for chunk in resp.iter_content(1024 * 64):
                        if chunk:
                            f.write(chunk)
            
            with zipfile.ZipFile(tmp_zip, 'r') as z:
                allnames = [n for n in z.namelist() if not n.endswith('/')]
                top = ''
                if allnames and '/' in allnames[0]:
                    top = allnames[0].split('/')[0] + '/'
                
                remote_worker_path = top + SELF_SCRIPT
                if remote_worker_path in z.namelist():
                    with z.open(remote_worker_path) as remote_file:
                        remote_content = remote_file.read()
                    
                    local_worker_path = os.path.join(self.base_path, SELF_SCRIPT)
                    if os.path.exists(local_worker_path):
                        with open(local_worker_path, 'rb') as local_file:
                            local_content = local_file.read()
                        
                        if remote_content != local_content:
                            self.log.emit("Update_Worker.py is outdated, updating...")
                            with open(local_worker_path, 'wb') as f:
                                f.write(remote_content)
                            self.log.emit("Update_Worker.py has been updated!")
                        else:
                            self.log.emit("Update_Worker.py is already up to date")
                    else:
                        with open(local_worker_path, 'wb') as f:
                            f.write(remote_content)
                        self.log.emit("Update_Worker.py created")
                else:
                    self.log.emit("Update_Worker.py not found in release archive")
            
            try:
                os.remove(tmp_zip)
            except Exception:
                pass
                
        except Exception as e:
            self.log.emit(f"Self-verification failed: {e}")


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
        with open(signal_file, 'w') as f:
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
                    'taskkill /F /IM pythonw.exe',
                    shell=True, check=False, capture_output=True, timeout=10,
                    startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception as e:
                self.log.emit(f"Force stop failed: {e}")
        else:
            try:
                subprocess.run(['pkill', '-9', '-f', 'main.py'], check=False, timeout=10)
            except Exception as e:
                self.log.emit(f"Force stop failed: {e}")


class UpdateWorkerDialog(QDialog):
    def __init__(self, parent=None, auto_start=False):
        super().__init__(parent)
        self.setWindowTitle("Image Tea Updater")
        self.setMinimumSize(600, 450)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        if HAS_QTAWESOME:
            self.setWindowIcon(qta.icon('fa6s.mug-hot', color='#4e9e20'))
        
        self.auto_start = auto_start
        self.update_thread = None
        self.stop_thread = None
        self.image_tea_stopped = False
        self._pending_logs = []
        
        self._setup_ui()
        
        if self.auto_start:
            QTimer.singleShot(500, self._show_stop_warning)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)
        
        if HAS_QTAWESOME:
            icon_container = QWidget()
            icon_container.setFixedSize(64, 64)
            icon_container_layout = QHBoxLayout(icon_container)
            icon_container_layout.setContentsMargins(0, 0, 0, 0)
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon('fa6s.download', color='#4e9e20').pixmap(56, 56))
            icon_label.setAlignment(Qt.AlignCenter)
            icon_container_layout.addWidget(icon_label)
            header_layout.addWidget(icon_container, alignment=Qt.AlignTop)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_label = QLabel("Image Tea Updater")
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
        developer_label.setStyleSheet("color: #666; font-size: 10pt;")
        title_layout.addWidget(developer_label)
        
        header_layout.addLayout(title_layout, 1)
        layout.addLayout(header_layout)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        info_grid = QVBoxLayout()
        info_grid.setSpacing(8)
        
        version_line_layout = QHBoxLayout()
        version_line_layout.setSpacing(10)
        version_line_layout.addWidget(QLabel("<b>Current:</b>"))
        self.current_version_label = QLabel(get_current_version())
        self.current_version_label.setStyleSheet("color: #666; font-weight: bold; font-size: 11pt;")
        version_line_layout.addWidget(self.current_version_label)
        version_line_layout.addSpacing(20)
        version_line_layout.addWidget(QLabel("<b>Update:</b>"))
        self.update_version_label = QLabel("Fetching...")
        self.update_version_label.setStyleSheet("color: #4e9e20; font-weight: bold; font-size: 11pt;")
        version_line_layout.addWidget(self.update_version_label)
        version_line_layout.addStretch()
        info_grid.addLayout(version_line_layout)
        try:
            tag = get_cached_remote_tag()
            if tag:
                self.update_version_label.setText(tag)
                self._append_log(f"Using cached remote tag: {tag}")
        except Exception as e:
            self._append_log(f"Could not read cached update tag: {e}")
        
        time_line_layout = QHBoxLayout()
        time_line_layout.setSpacing(10)
        self.time_info_label = QLabel("Elapsed: 00:00:00   Remaining: 00:00:00   ETA: 00:00:00")
        self.time_info_label.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-size: 10pt; color: #666;")
        time_line_layout.addWidget(self.time_info_label)
        time_line_layout.addStretch()
        info_grid.addLayout(time_line_layout)
        layout.addLayout(info_grid)
        
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)
        
        self.status_label = QLabel("Ready to update")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4e9e20;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        log_label = QLabel("Update Log:")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #333;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.log_text, 1)
        if hasattr(self, '_pending_logs') and self._pending_logs:
            for pending in self._pending_logs:
                self.log_text.append(pending)
            self._pending_logs.clear()
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.start_button = QPushButton("Update Now")
        if HAS_QTAWESOME:
            self.start_button.setIcon(qta.icon('fa6s.download', color='#ffffff'))
        self.start_button.setMinimumHeight(36)
        self.start_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_button.clicked.connect(self._show_stop_warning)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4e9e20;
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d8e1a;
            }
            QPushButton:pressed {
                background-color: #2f6b13;
            }
            QPushButton:disabled {
                background-color: #9fc79b;
                color: #eee;
            }
        """)
        button_layout.addWidget(self.start_button, 1)
        
        self.relaunch_button = QPushButton("Relaunch App")
        if HAS_QTAWESOME:
            self.relaunch_button.setIcon(qta.icon('fa6s.rotate-right', color='#ffffff'))
        self.relaunch_button.setMinimumHeight(36)
        self.relaunch_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.relaunch_button.clicked.connect(self._relaunch_app)
        self.relaunch_button.setEnabled(False)
        self.relaunch_button.hide()
        self.relaunch_button.setStyleSheet("""
            QPushButton {
                background-color: #4e9e20;
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d8e1a;
            }
            QPushButton:pressed {
                background-color: #2f6b13;
            }
        """)
        button_layout.addWidget(self.relaunch_button, 1)
        
        self.close_button = QPushButton("Cancel Update")
        if HAS_QTAWESOME:
            self.close_button.setIcon(qta.icon('fa6s.xmark'))
        self.close_button.setMinimumHeight(36)
        self.close_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.close_button.clicked.connect(self.close)
        # adaptive grey style for both dark and light themes
        is_dark = self.palette().color(QPalette.Window).lightness() < 128
        if is_dark:
            close_style = """
                QPushButton {
                    background-color: rgba(255,255,255,0.06);
                    color: #ffffff;
                    border-radius: 6px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: rgba(255,255,255,0.09);
                }
                QPushButton:pressed {
                    background-color: rgba(255,255,255,0.12);
                }
            """
        else:
            close_style = """
                QPushButton {
                    background-color: rgba(0,0,0,0.06);
                    color: #222;
                    border-radius: 6px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: rgba(0,0,0,0.08);
                }
                QPushButton:pressed {
                    background-color: rgba(0,0,0,0.10);
                }
            """
        self.close_button.setStyleSheet(close_style)
        button_layout.addWidget(self.close_button, 1)
        
        layout.addLayout(button_layout)
    
    def _show_stop_warning(self):
        if self.image_tea_stopped:
            self._start_update()
            return
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Update Warning")
        msg.setText("Image Tea will stop running processes for the update.")
        msg.setInformativeText(
            "Please terminate any ongoing work (generations, automations, or other tasks) before continuing.\n\n"
            "The application will be closed and running tasks will be stopped.\n"
            "Do you want to continue?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if HAS_QTAWESOME:
            msg.setIconPixmap(qta.icon('fa6s.triangle-exclamation', color='#f0ad4e').pixmap(64, 64))
        
        result = msg.exec()
        
        if result == QMessageBox.Yes:
            self._stop_image_tea()
        else:
            self.close()
    
    def _stop_image_tea(self):
        self.status_label.setText("Stopping Image Tea...")
        self._append_log("Stopping Image Tea application...")
        
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
        
        self.status_label.setText("Please click 'Update Now' to start the update.")
        self._append_log("Please click 'Update Now' to start the update.")
    
    def _start_update(self):
        self.status_label.setText("Starting update...")
        self._append_log("Starting update process...")
        
        self.update_thread = UpdateWorkerThread(self)
        self.update_thread.progress.connect(self._update_progress)
        self.update_thread.status.connect(self._update_status)
        self.update_thread.log.connect(self._append_log)
        self.update_thread.update_info.connect(self._update_version_info)
        self.update_thread.time_info.connect(self._update_time_info)
        self.update_thread.finished_success.connect(self._on_update_success)
        self.update_thread.finished_error.connect(self._on_update_error)
        self.update_thread.start()
    
    def _update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def _update_status(self, status):
        self.status_label.setText(status)
    
    def _update_version_info(self, current, update, developer):
        self.current_version_label.setText(current)
        self.update_version_label.setText(update)
    
    def _update_time_info(self, elapsed, remaining, eta):
        try:
            self.time_info_label.setText(f"Elapsed: {elapsed}   Remaining: {remaining}   ETA: {eta}")
        except Exception:
            pass
    
    def _append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.append(formatted)
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        else:
            if not hasattr(self, '_pending_logs'):
                self._pending_logs = []
            self._pending_logs.append(formatted)
    
    def _on_update_success(self):
        self.close_button.setEnabled(True)
        self.close_button.setText("Close")
        self.relaunch_button.setEnabled(True)
        self.relaunch_button.show()
        self.start_button.hide()
        
        reply = QMessageBox.question(
            self,
            "Update Complete",
            "Image Tea has been updated successfully!\n\nDo you want to relaunch the application now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            last_backup_file = os.path.join(SCRIPT_DIR, 'temp', 'last_update_backup_on_update.txt')
            if os.path.exists(last_backup_file):
                try:
                    with open(last_backup_file, 'r', encoding='utf-8') as f:
                        zip_path = f.read().strip()
                    self._append_log(f"Restoring configs from pre-update backup: {zip_path}")
                    restore_backup_by_path(zip_path)
                    self._append_log("Config restore completed.")
                except Exception as e:
                    print(f"Error restoring update backup: {e}")
                    self._append_log(f"ERROR: Failed to restore update backup: {e}")
            else:
                self._append_log("No pre-update backup found to restore.")
            self._relaunch_app()
            return
        else:
            self._append_log("You can relaunch Image Tea later using the 'Relaunch App' button.")
            self.relaunch_button.setEnabled(True)
            self.relaunch_button.show()
            return
    
    def _on_update_error(self, error):
        self.close_button.setEnabled(True)
        self.close_button.setText("Close")
        self.start_button.setEnabled(True)
        self.status_label.setText("Update failed!")
        self._append_log(f"ERROR: {error}")
        
        QMessageBox.critical(
            self,
            "Update Failed",
            f"The update failed with the following error:\n\n{error}\n\n"
            "Please check your internet connection and try again."
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
                        "Could not find the application launcher.\n"
                        "Please start Image Tea manually."
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
                        "Could not find the application launcher.\n"
                        "Please start Image Tea manually."
                    )
                    return
        
        self.close()


def run_updater_gui(auto_start=False):
    app = QApplication.instance()
    standalone = False
    
    if app is None:
        app = QApplication(sys.argv)
        standalone = True
    
    dialog = UpdateWorkerDialog(auto_start=auto_start)
    
    if standalone:
        dialog.show()
        sys.exit(app.exec())
    else:
        dialog.exec()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Image Tea Update Worker")
    parser.add_argument("--auto", action="store_true", help="Auto-start update process")
    parser.add_argument("--no-gui", action="store_true", help="Run without GUI (headless mode)")
    args = parser.parse_args()
    
    if args.no_gui:
        print("Running in headless mode...")
        print("This feature is not yet implemented for headless mode.")
        print("Please run without --no-gui flag.")
        sys.exit(1)
    
    run_updater_gui(auto_start=args.auto)


if __name__ == "__main__":
    main()
