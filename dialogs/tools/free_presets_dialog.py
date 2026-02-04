import os
import json
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QMessageBox, QWidget)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont
from config import BASE_PATH
import qtawesome as qta
from database.db_operation import ImageTeaDB
from helpers.tools.action_sequencer_helpers.action_sequencer_import_export_helper import ActionSequencerImportExport

from ui.theme_system import theme


class GitHubFetcherThread(QThread):
    fetch_completed = Signal(list)
    fetch_failed = Signal(str)
    
    def __init__(self, repo_url, dev_token=None):
        super().__init__()
        self.repo_url = repo_url
        self.dev_token = dev_token
    
    def run(self):
        try:
            api_url = "https://api.github.com/repos/mudrikam/Image-Tea-Action-Sequencer-Presets/contents/"
            
            request = urllib.request.Request(api_url)
            request.add_header('User-Agent', 'Image-Tea-Action-Sequencer')
            
            if self.dev_token:
                request.add_header('Authorization', f'token {self.dev_token}')
                print("Using development GitHub token for API request")
            
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            json_files = []
            for item in data:
                if item['type'] == 'file' and item['name'].endswith('.json'):
                    json_files.append({
                        'name': item['name'],
                        'download_url': item['download_url'],
                        'size': item['size']
                    })
            
            self.fetch_completed.emit(json_files)
        except Exception as e:
            self.fetch_failed.emit(str(e))


class DownloadWorkerThread(QThread):
    progress_updated = Signal(int, int)
    download_completed = Signal(str, str)
    download_failed = Signal(str, str)
    
    def __init__(self, file_name, download_url, temp_dir):
        super().__init__()
        self.file_name = file_name
        self.download_url = download_url
        self.temp_dir = temp_dir
    
    def run(self):
        try:
            temp_file_path = os.path.join(self.temp_dir, self.file_name)
            
            request = urllib.request.Request(self.download_url)
            request.add_header('User-Agent', 'Image-Tea-Action-Sequencer')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
            
            with open(temp_file_path, 'wb') as f:
                f.write(content)
            
            self.download_completed.emit(self.file_name, temp_file_path)
        except Exception as e:
            self.download_failed.emit(self.file_name, str(e))


class FreePresetsDialog(QDialog):
    preset_imported = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FREE Action Sequencer Presets")
        self.setModal(True)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.db = ImageTeaDB()
        self.import_export_helper = ActionSequencerImportExport()
        self.repo_url = "https://github.com/mudrikam/Image-Tea-Action-Sequencer-Presets"
        self.presets_data = []
        self.temp_dir = tempfile.mkdtemp(prefix='image_tea_free_presets_')
        self.cache_file = os.path.join(BASE_PATH, 'temp', 'free_presets_cache.json')
        self.install_status_cache_file = os.path.join(BASE_PATH, 'temp', 'free_presets_install_status.json')
        self.fetcher_thread = None
        self.download_threads = []
        self.dev_token = self._load_dev_token()
        self.preset_contents_cache = {}
        self.install_status_cache = self._load_install_status_cache()
        self.pending_downloads = 0
        self.completed_downloads = 0
        self.failed_downloads = 0
        self.is_batch_download = False
        
        self.setup_ui()
        self.resize(700, 500)
        self.load_presets_with_cache()
    
    def _clean_preset_name(self, filename):
        """Clean preset name for display: remove prefix, timestamp, extension, and underscores"""
        name = filename
        
        # Remove .json extension
        if name.lower().endswith('.json'):
            name = name[:-5]
        
        # Remove common prefix
        prefix = 'Image_Tea_Action_Sequencer_Preset_'
        if name.startswith(prefix):
            name = name[len(prefix):]
        
        # Remove timestamp pattern _YYYYMMDD_HHMMSS
        import re
        name = re.sub(r'_\d{8}_\d{6}$', '', name)
        
        # Replace underscores with spaces
        name = name.replace('_', ' ')
        
        # Capitalize each word
        name = ' '.join(word.capitalize() for word in name.split())
        
        return name
    
    def _load_dev_token(self):
        """Load development GitHub token if in development mode"""
        try:
            env_file = os.path.join(BASE_PATH, '.env')
            if not os.path.exists(env_file):
                return None
            
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('DEVELOPMENT='):
                        value = line.split('=', 1)[1].strip().lower()
                        if value != 'true':
                            return None
                        break
                else:
                    return None
            
            token_file = os.path.join(BASE_PATH, 'configs', 'dev_github_token.json')
            if not os.path.exists(token_file):
                print("Development mode enabled but dev_github_token.json not found")
                return None
            
            with open(token_file, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            token = token_data.get('token')
            if token:
                print("Development mode: GitHub token loaded")
            return token
        except Exception as e:
            print(f"Failed to load dev token: {e}")
            return None
    
    def _load_install_status_cache(self):
        """Load cached installation status for presets"""
        try:
            if os.path.exists(self.install_status_cache_file):
                with open(self.install_status_cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                print(f"Loaded install status cache with {len(cache)} entries")
                return cache
        except Exception as e:
            print(f"Failed to load install status cache: {e}")
        return {}
    
    def _save_install_status_cache(self):
        """Save installation status cache to file"""
        try:
            os.makedirs(os.path.dirname(self.install_status_cache_file), exist_ok=True)
            with open(self.install_status_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.install_status_cache, f, indent=2)
            print(f"Saved install status cache with {len(self.install_status_cache)} entries")
        except Exception as e:
            print(f"Failed to save install status cache: {e}")
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        dialog_icon = qta.icon('fa6s.cloud-arrow-down')
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(32, 32))
        header_layout.addWidget(icon_label)
        
        header_label = QLabel("FREE Action Sequencer Presets")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(12)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        self.info_label = QLabel(f"Browse and download free presets from:\n{self.repo_url}")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"color: {theme.get_color('gray')}; padding: 5px;")
        layout.addWidget(self.info_label)
        
        # Top controls (above table)
        top_button_layout = QHBoxLayout()
        top_button_layout.setSpacing(4)
        top_button_layout.addStretch()
        self.refresh_button = QPushButton(qta.icon('fa6s.arrows-rotate'), " Refresh")
        self.refresh_button.setToolTip("Fetch latest preset list from GitHub")
        self.refresh_button.clicked.connect(self.on_refresh_remote)
        top_button_layout.addWidget(self.refresh_button)
        layout.addLayout(top_button_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Preset Name", "Status", "Action"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.MultiSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        layout.addWidget(self.table)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        
        self.download_all_button = QPushButton(qta.icon('fa6s.download'), " Download All")
        self.download_all_button.clicked.connect(self.on_download_all)
        self.download_all_button.setEnabled(False)
        button_layout.addWidget(self.download_all_button)
        
        self.download_selected_button = QPushButton(qta.icon('fa6s.download'), " Download Selected")
        self.download_selected_button.clicked.connect(self.on_download_selected)
        self.download_selected_button.setEnabled(False)
        button_layout.addWidget(self.download_selected_button)
        
        self.remove_all_button = QPushButton(qta.icon('fa6s.trash'), " Remove All")
        self.remove_all_button.clicked.connect(self.on_remove_all)
        self.remove_all_button.setEnabled(False)
        button_layout.addWidget(self.remove_all_button)
        
        self.remove_selected_button = QPushButton(qta.icon('fa6s.trash'), " Remove Selected")
        self.remove_selected_button.clicked.connect(self.on_remove_selected)
        self.remove_selected_button.setEnabled(False)
        button_layout.addWidget(self.remove_selected_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton(qta.icon('fa6s.xmark'), " Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_presets_with_cache(self):
        """Load presets from cache if valid, otherwise fetch from GitHub"""
        cache_valid = False
        
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                fetch_date_str = cache_data.get('fetch_date')
                if fetch_date_str:
                    fetch_date = datetime.strptime(fetch_date_str, '%Y-%m-%d').date()
                    today = date.today()
                    
                    if fetch_date == today:
                        self.presets_data = cache_data.get('presets', [])
                        cache_valid = True
                        print(f"Using cached preset list from {fetch_date_str}")
            except Exception as e:
                print(f"Cache read error: {e}")
        
        if cache_valid and self.presets_data:
            self.populate_table()
            self.update_button_states()
            self.info_label.setText(
                f"Browse and download free presets from:\n{self.repo_url}\n"
                f"(Using cached list from {fetch_date_str})"
            )
        else:
            self.fetch_repo_contents()
    
    def save_cache(self, presets_data):
        """Save fetched presets to cache file"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            cache_data = {
                'fetch_date': date.today().strftime('%Y-%m-%d'),
                'presets': presets_data
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            print(f"Preset list cached to {self.cache_file}")
        except Exception as e:
            print(f"Cache save error: {e}")
    
    def fetch_repo_contents(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("Fetching presets from GitHub...")
        
        self.fetcher_thread = GitHubFetcherThread(self.repo_url, self.dev_token)
        self.fetcher_thread.fetch_completed.connect(self.on_fetch_completed)
        self.fetcher_thread.fetch_failed.connect(self.on_fetch_failed)
        self.fetcher_thread.start()
    
    def on_fetch_completed(self, json_files):
        self.progress_bar.setVisible(False)
        self.presets_data = json_files
        self.save_cache(json_files)
        self.populate_table()
        self.update_button_states()
    
    def on_fetch_failed(self, error_msg):
        self.progress_bar.setVisible(False)
        
        if 'rate limit' in error_msg.lower() or '403' in error_msg:
            QMessageBox.warning(
                self, 
                "Rate Limit Reached", 
                "GitHub API rate limit reached.\n\n"
                "The preset list will be cached for today.\n"
                "Please try again tomorrow or use cached data if available."
            )
        else:
            QMessageBox.critical(self, "Fetch Failed", f"Failed to fetch presets from GitHub:\n{error_msg}")
    
    def populate_table(self):
        self.table.setRowCount(0)
        for idx, preset_info in enumerate(self.presets_data):
            row = self.table.rowCount()
            self.table.insertRow(row)
            clean_name = self._clean_preset_name(preset_info['name'])
            name_item = QTableWidgetItem(clean_name)
            self.table.setItem(row, 0, name_item)
            
            if preset_info['name'] in self.install_status_cache:
                del self.install_status_cache[preset_info['name']]
            
            is_installed = self.check_preset_installed(preset_info['name'])
            
            status_label = QLabel()
            if is_installed:
                status_label.setPixmap(qta.icon('fa6s.circle-check', color=theme.get_color('primary')).pixmap(20, 20))
                status_label.setToolTip("Installed")
            else:
                status_label.setPixmap(qta.icon('fa6s.circle-arrow-down', color=theme.get_color('gray')).pixmap(20, 20))
                status_label.setToolTip("Not installed")
            status_label.setAlignment(Qt.AlignCenter)
            
            status_widget = QWidget()
            status_layout = QHBoxLayout()
            status_layout.addWidget(status_label)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setAlignment(Qt.AlignCenter)
            status_widget.setLayout(status_layout)
            self.table.setCellWidget(row, 1, status_widget)
            
            action_button = QPushButton()
            action_button.setFlat(True)
            action_button.setMaximumWidth(36)
            if is_installed:
                action_button.setIcon(qta.icon('fa6s.rotate-right'))
                action_button.setToolTip("Reinstall this preset")
            else:
                action_button.setIcon(qta.icon('fa6s.download'))
                action_button.setToolTip("Download this preset")
            action_button.clicked.connect(lambda checked, pi=preset_info: self.on_download_single(pi))

            action_widget = QWidget()
            action_layout = QHBoxLayout()
            action_layout.addWidget(action_button)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setAlignment(Qt.AlignCenter)
            action_widget.setLayout(action_layout)
            self.table.setCellWidget(row, 2, action_widget)
    
    def check_preset_installed(self, filename):
        """Check if preset from this file is already installed in database"""
        try:
            if filename not in self.preset_contents_cache:
                for preset in self.presets_data:
                    if preset['name'] == filename:
                        preset_info = preset
                        break
                else:
                    self.install_status_cache[filename] = False
                    return False
                
                request = urllib.request.Request(preset_info['download_url'])
                request.add_header('User-Agent', 'Image-Tea-Action-Sequencer')
                
                with urllib.request.urlopen(request, timeout=10) as response:
                    content = response.read()
                
                data = json.loads(content.decode('utf-8'))
                self.preset_contents_cache[filename] = data
            else:
                data = self.preset_contents_cache[filename]
            
            if 'presets' not in data:
                self.install_status_cache[filename] = False
                return False
            
            print(f"\n=== Checking installation for {filename} ===")
            all_installed = True
            for preset_data in data['presets']:
                preset_name = preset_data.get('preset_name')
                platform_name = preset_data.get('platform_name')
                
                print(f"Checking preset: '{preset_name}' on platform: '{platform_name}'")
                
                if not preset_name or not platform_name:
                    continue
                
                platform = self.db.get_platform_by_name(platform_name)
                if not platform:
                    print(f"  Platform '{platform_name}' not found in DB")
                    all_installed = False
                    continue
                
                platform_id = platform['id']
                existing_presets = self.db.get_presets_by_platform(platform_id)
                
                print(f"  Found {len(existing_presets)} presets in platform {platform_id}")
                for ep in existing_presets:
                    print(f"    - DB Preset: '{ep['name']}' (ID: {ep['id']})")
                
                preset_found = False
                for existing in existing_presets:
                    if existing['name'] == preset_name:
                        preset_found = True
                        print(f"  ✓ Preset '{preset_name}' found in DB (ID: {existing['id']})")
                        break
                
                if not preset_found:
                    print(f"  ✗ Preset '{preset_name}' NOT found in DB")
                    all_installed = False
                    break
            
            print(f"Final result: all_installed = {all_installed}\n")
            self.install_status_cache[filename] = all_installed
            self._save_install_status_cache()
            return all_installed
            
        except Exception as e:
            print(f"Error checking preset installation for {filename}: {e}")
            import traceback
            traceback.print_exc()
            self.install_status_cache[filename] = False
            return False
    
    def get_download_url_for_file(self, filename):
        for preset in self.presets_data:
            if preset['name'] == filename:
                return preset['download_url']
        return None
    
    def on_download_single(self, preset_info):
        self.is_batch_download = False
        self.pending_downloads = 1
        self.completed_downloads = 0
        self.failed_downloads = 0
        self.download_preset(preset_info)
    
    def on_download_all(self):
        self.is_batch_download = True
        self.pending_downloads = len(self.presets_data)
        self.completed_downloads = 0
        self.failed_downloads = 0
        
        for preset_info in self.presets_data:
            self.download_preset(preset_info)
    
    def on_download_selected(self):
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select presets to download")
            return
        
        self.is_batch_download = len(selected_rows) > 1
        self.pending_downloads = len(selected_rows)
        self.completed_downloads = 0
        self.failed_downloads = 0
        
        for row in selected_rows:
            name_item = self.table.item(row, 0)
            if name_item:
                filename = name_item.text()
                for preset_info in self.presets_data:
                    if preset_info['name'] == filename:
                        self.download_preset(preset_info)
                        break
    
    def download_preset(self, preset_info):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat(f"Downloading {preset_info['name']}...")
        
        download_thread = DownloadWorkerThread(
            preset_info['name'],
            preset_info['download_url'],
            self.temp_dir
        )
        download_thread.download_completed.connect(self.on_download_completed)
        download_thread.download_failed.connect(self.on_download_failed)
        self.download_threads.append(download_thread)
        download_thread.start()
    
    def on_download_completed(self, file_name, file_path):
        success, message, count = self.import_export_helper.import_presets(file_path)
        
        if success:
            if file_name in self.preset_contents_cache:
                del self.preset_contents_cache[file_name]
            
            self.install_status_cache[file_name] = True
            self._save_install_status_cache()
            self.completed_downloads += 1
            self.preset_imported.emit()
        else:
            self.failed_downloads += 1
        
        # Check if all downloads completed
        total_processed = self.completed_downloads + self.failed_downloads
        
        if total_processed >= self.pending_downloads:
            self.progress_bar.setVisible(False)
            self.populate_table()
            self.update_button_states()
            
            # Show summary dialog
            if self.is_batch_download:
                if self.failed_downloads > 0:
                    QMessageBox.warning(
                        self, 
                        "Batch Import Completed",
                        f"Import completed:\n\n"
                        f"✓ Successfully imported: {self.completed_downloads} preset(s)\n"
                        f"✗ Failed: {self.failed_downloads} preset(s)"
                    )
                else:
                    QMessageBox.information(
                        self, 
                        "Batch Import Successful",
                        f"Successfully imported {self.completed_downloads} preset(s)!"
                    )
            else:
                # Single download - show individual message
                if success:
                    clean_name = self._clean_preset_name(file_name)
                    QMessageBox.information(
                        self, 
                        "Import Successful", 
                        f"{clean_name}:\n{message}"
                    )
                else:
                    clean_name = self._clean_preset_name(file_name)
                    QMessageBox.warning(
                        self, 
                        "Import Failed", 
                        f"{clean_name}:\n{message}"
                    )
            
            # Reset counters
            self.is_batch_download = False
            self.pending_downloads = 0
            self.completed_downloads = 0
            self.failed_downloads = 0
        else:
            # Update progress for batch downloads
            if self.is_batch_download:
                self.progress_bar.setVisible(True)
                self.progress_bar.setFormat(f"Importing {total_processed}/{self.pending_downloads}...")
    
    def on_download_failed(self, file_name, error_msg):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Download Failed", f"Failed to download {file_name}:\n{error_msg}")
    
    def on_remove_all(self):
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            "Are you sure you want to remove ALL presets shown in this list from your database?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            removed_count = 0
            for preset_info in self.presets_data:
                if self.remove_preset(preset_info['name']):
                    removed_count += 1
            
            if removed_count > 0:
                self.preset_imported.emit()
            
            QMessageBox.information(self, "Removal Complete", f"Removed {removed_count} preset(s)")
            self.populate_table()
            self.update_button_states()
    
    def on_remove_selected(self):
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select presets to remove")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove {len(selected_rows)} selected preset(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            removed_count = 0
            for row in sorted(selected_rows):
                if row < len(self.presets_data):
                    preset_info = self.presets_data[row]
                    if self.remove_preset(preset_info['name']):
                        removed_count += 1
            
            if removed_count > 0:
                self.preset_imported.emit()
            
            QMessageBox.information(self, "Removal Complete", f"Removed {removed_count} preset(s)")
            self.populate_table()
            self.update_button_states()
    
    def remove_preset(self, filename):
        """Remove preset from database by matching name from JSON file"""
        try:
            if filename not in self.preset_contents_cache:
                for preset in self.presets_data:
                    if preset['name'] == filename:
                        preset_info = preset
                        break
                else:
                    print(f"Preset file '{filename}' not found in presets_data")
                    return False
                
                request = urllib.request.Request(preset_info['download_url'])
                request.add_header('User-Agent', 'Image-Tea-Action-Sequencer')
                
                with urllib.request.urlopen(request, timeout=10) as response:
                    content = response.read()
                
                data = json.loads(content.decode('utf-8'))
                self.preset_contents_cache[filename] = data
            else:
                data = self.preset_contents_cache[filename]
            
            if 'presets' not in data:
                print(f"No 'presets' key in {filename}")
                return False
            
            print(f"\n=== Removing presets from {filename} ===")
            removed_any = False
            for preset_data in data['presets']:
                preset_name = preset_data.get('preset_name')
                platform_name = preset_data.get('platform_name')
                
                print(f"Looking for preset: '{preset_name}' on platform: '{platform_name}'")
                
                if not preset_name or not platform_name:
                    print(f"  Skipping - missing name or platform")
                    continue
                
                platform = self.db.get_platform_by_name(platform_name)
                if not platform:
                    print(f"  Platform '{platform_name}' not found in DB")
                    continue
                
                platform_id = platform['id']
                existing_presets = self.db.get_presets_by_platform(platform_id)
                
                print(f"  Searching in {len(existing_presets)} presets...")
                for existing in existing_presets:
                    print(f"    Comparing: '{existing['name']}' == '{preset_name}' ?")
                    if existing['name'] == preset_name:
                        print(f"  ✓ MATCH FOUND! Removing preset '{preset_name}' (ID: {existing['id']})")
                        self.db.delete_preset(existing['id'])
                        removed_any = True
                        break
                else:
                    print(f"  ✗ Preset '{preset_name}' not found in DB")
            
            if removed_any:
                if filename in self.preset_contents_cache:
                    del self.preset_contents_cache[filename]
                
                self.install_status_cache[filename] = False
                self._save_install_status_cache()
                print(f"✓ Successfully removed preset(s) from '{filename}' and updated cache\n")
            else:
                print(f"✗ No presets were removed from '{filename}'\n")
            
            return removed_any
        except Exception as e:
            print(f"Error removing preset '{filename}': {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_button_states(self):
        has_presets = len(self.presets_data) > 0
        has_installed = any(self.check_preset_installed(p['name']) for p in self.presets_data)
        
        self.download_all_button.setEnabled(has_presets)
        self.download_selected_button.setEnabled(has_presets)
        self.remove_all_button.setEnabled(has_installed)
        self.remove_selected_button.setEnabled(has_installed)
    
    def closeEvent(self, event):
        if self.fetcher_thread and self.fetcher_thread.isRunning():
            self.fetcher_thread.terminate()
            self.fetcher_thread.wait()
        
        for thread in self.download_threads:
            if thread.isRunning():
                thread.terminate()
                thread.wait()
        
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Failed to cleanup temp directory: {e}")
        
        super().closeEvent(event)
    
    def on_refresh_remote(self):
        """Fetch latest preset list from GitHub, bypassing cache"""
        reply = QMessageBox.question(
            self,
            "Refresh Preset List",
            "This will fetch the latest preset list from GitHub.\nAny cached data will be cleared.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if os.path.exists(self.cache_file):
                try:
                    os.remove(self.cache_file)
                    print("Cache file removed for refresh")
                except Exception as e:
                    print(f"Failed to remove cache file: {e}")
            
            self.preset_contents_cache.clear()
            self.install_status_cache.clear()
            self._save_install_status_cache()
            
            self.fetch_repo_contents()
