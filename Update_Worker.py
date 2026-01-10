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
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QTextEdit, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QIcon

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


class UpdateWorkerThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    log = Signal(str)
    finished_success = Signal()
    finished_error = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_path = SCRIPT_DIR
        self.temp_dir = os.path.join(self.base_path, "temp")
        
    def run(self):
        try:
            self._do_update()
        except Exception as e:
            self.finished_error.emit(str(e))
    
    def _do_update(self):
        self.status.emit("Initializing update...")
        self.progress.emit(0)
        self.log.emit("Starting Image Tea update process...")
        
        os.makedirs(self.temp_dir, exist_ok=True)
        
        owner, repo = get_repo_info()
        self.log.emit(f"Repository: {owner}/{repo}")
        
        self.status.emit("Fetching latest release info...")
        self.progress.emit(5)
        
        tag = self._fetch_latest_tag(owner, repo)
        self.log.emit(f"Latest release tag: {tag}")
        
        self.status.emit("Downloading update package...")
        self.progress.emit(10)
        
        zip_path = os.path.join(self.temp_dir, ZIP_NAME)
        self._download_release(owner, repo, tag, zip_path)
        self.log.emit(f"Downloaded to: {zip_path}")
        
        self.status.emit("Extracting update package...")
        self.progress.emit(50)
        
        extract_path = os.path.join(self.temp_dir, "Image-Tea-nano-extracted")
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        
        self._extract_zip(zip_path, extract_path)
        self.log.emit(f"Extracted to: {extract_path}")
        
        self.status.emit("Replacing files...")
        self.progress.emit(60)
        
        extracted_root = self._find_extracted_root(extract_path)
        if not extracted_root:
            raise RuntimeError("Could not find extracted content root directory")
        
        self.log.emit(f"Source root: {extracted_root}")
        
        replaced_count = self._replace_files(extracted_root)
        self.log.emit(f"Replaced {replaced_count} files")
        
        self.status.emit("Cleaning up...")
        self.progress.emit(90)
        
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
        
        self._verify_self_update(owner, repo, tag)
        
        self.status.emit("Update completed successfully!")
        self.progress.emit(100)
        self.log.emit("=" * 50)
        self.log.emit("Update finished successfully!")
        self.log.emit("=" * 50)
        
        self.finished_success.emit()
    
    def _fetch_latest_tag(self, owner, repo):
        if not HAS_REQUESTS:
            self.log.emit("requests library not available, using fallback version")
            return get_fallback_version()
        
        try:
            api_url = RELEASES_API_TEMPLATE.format(owner=owner, repo=repo)
            self.log.emit(f"Fetching from: {api_url}")
            resp = requests.get(api_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            tag = data.get("tag_name", "")
            if tag:
                return tag
        except Exception as e:
            self.log.emit(f"Failed to fetch latest tag: {e}")
        
        fallback = get_fallback_version()
        self.log.emit(f"Using fallback version: {fallback}")
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
    
    def run(self):
        try:
            self._stop_image_tea()
            self.finished.emit(True)
        except Exception as e:
            self.log.emit(f"Error stopping Image Tea: {e}")
            self.finished.emit(False)
    
    def _stop_image_tea(self):
        system = platform.system()
        
        if system == "Windows":
            self._stop_windows()
        else:
            self._stop_unix()
    
    def _stop_windows(self):
        pythonw_path = os.path.join(self.base_path, "python", "Windows", "pythonw.exe")
        exe_path = os.path.join(self.base_path, "Image Tea.exe")
        
        for target in [pythonw_path, exe_path]:
            if os.path.exists(target):
                target_escaped = target.replace('\\', '\\\\')
                cmd = f"powershell -NoProfile -Command \"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -eq '{target_escaped}' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}\""
                try:
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
                    self.log.emit(f"Stopped processes for: {os.path.basename(target)}")
                except Exception as e:
                    self.log.emit(f"Failed to stop {os.path.basename(target)}: {e}")
    
    def _stop_unix(self):
        try:
            subprocess.run(["pkill", "-f", "main.py"], capture_output=True, timeout=10)
            self.log.emit("Stopped main.py processes")
        except Exception as e:
            self.log.emit(f"Failed to stop processes: {e}")


class UpdateWorkerDialog(QDialog):
    def __init__(self, parent=None, auto_start=False):
        super().__init__(parent)
        self.setWindowTitle("Image Tea Updater")
        self.setMinimumSize(600, 450)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        self.auto_start = auto_start
        self.update_thread = None
        self.stop_thread = None
        
        self._setup_ui()
        
        if self.auto_start:
            QTimer.singleShot(500, self._show_stop_warning)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        header_layout = QHBoxLayout()
        
        if HAS_QTAWESOME:
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon('fa6s.cloud-arrow-down', color='#4e9e20').pixmap(48, 48))
            header_layout.addWidget(icon_label)
        
        title_layout = QVBoxLayout()
        title_label = QLabel("Image Tea Updater")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        
        version_label = QLabel(f"Current version: {get_current_version()}")
        version_label.setStyleSheet("color: #666;")
        title_layout.addWidget(version_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
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
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.start_button = QPushButton("Start Update")
        if HAS_QTAWESOME:
            self.start_button.setIcon(qta.icon('fa6s.play', color='#4e9e20'))
        self.start_button.setMinimumWidth(120)
        self.start_button.clicked.connect(self._show_stop_warning)
        button_layout.addWidget(self.start_button)
        
        self.relaunch_button = QPushButton("Relaunch App")
        if HAS_QTAWESOME:
            self.relaunch_button.setIcon(qta.icon('fa6s.rotate-right', color='#4e9e20'))
        self.relaunch_button.setMinimumWidth(120)
        self.relaunch_button.clicked.connect(self._relaunch_app)
        self.relaunch_button.setEnabled(False)
        self.relaunch_button.hide()
        button_layout.addWidget(self.relaunch_button)
        
        self.close_button = QPushButton("Close")
        if HAS_QTAWESOME:
            self.close_button.setIcon(qta.icon('fa6s.xmark', color='#666'))
        self.close_button.setMinimumWidth(100)
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _show_stop_warning(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Update Warning")
        msg.setText("Image Tea will be stopped for the update.")
        msg.setInformativeText(
            "Please save any ongoing work before continuing.\n\n"
            "The application will be closed and files will be replaced with the latest version.\n"
            "Do you want to continue?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if HAS_QTAWESOME:
            msg.setIconPixmap(qta.icon('fa6s.triangle-exclamation', color='#f0ad4e').pixmap(64, 64))
        
        if msg.exec() == QMessageBox.Yes:
            self._stop_and_update()
    
    def _stop_and_update(self):
        self.start_button.setEnabled(False)
        self.status_label.setText("Stopping Image Tea...")
        self._append_log("Stopping Image Tea application...")
        
        self.stop_thread = StopImageTeaThread(self)
        self.stop_thread.log.connect(self._append_log)
        self.stop_thread.finished.connect(self._on_stop_finished)
        self.stop_thread.start()
    
    def _on_stop_finished(self, success):
        if success:
            self._append_log("Image Tea stopped successfully")
        else:
            self._append_log("Warning: Could not confirm Image Tea was stopped")
        
        QTimer.singleShot(1000, self._start_update)
    
    def _start_update(self):
        self.start_button.setEnabled(False)
        self.close_button.setEnabled(False)
        
        self.update_thread = UpdateWorkerThread(self)
        self.update_thread.progress.connect(self._update_progress)
        self.update_thread.status.connect(self._update_status)
        self.update_thread.log.connect(self._append_log)
        self.update_thread.finished_success.connect(self._on_update_success)
        self.update_thread.finished_error.connect(self._on_update_error)
        self.update_thread.start()
    
    def _update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def _update_status(self, status):
        self.status_label.setText(status)
    
    def _append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_update_success(self):
        self.close_button.setEnabled(True)
        self.relaunch_button.setEnabled(True)
        self.relaunch_button.show()
        self.start_button.hide()
        
        QMessageBox.information(
            self,
            "Update Complete",
            "Image Tea has been updated successfully!\n\n"
            "Click 'Relaunch App' to start the updated application."
        )
    
    def _on_update_error(self, error):
        self.close_button.setEnabled(True)
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
            exe_path = os.path.join(SCRIPT_DIR, "Image Tea.exe")
            pythonw_path = os.path.join(SCRIPT_DIR, "python", "Windows", "pythonw.exe")
            main_py = os.path.join(SCRIPT_DIR, "main.py")
            
            if os.path.exists(exe_path):
                subprocess.Popen([exe_path], shell=False)
            elif os.path.exists(pythonw_path) and os.path.exists(main_py):
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
