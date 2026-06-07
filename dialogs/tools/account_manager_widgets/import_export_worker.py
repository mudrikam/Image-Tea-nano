from importlib.metadata import metadata
import os
import shutil
import zipfile
import tempfile
import re
import json
from datetime import datetime
from PySide6.QtCore import QObject, Signal


class ImportExportWorkerSignals(QObject):
    """Signals for worker thread communication"""
    finished = Signal(object)  # Returns result dict
    error = Signal(str)
    progress = Signal(int, int)  # value, maximum


class ImportWorker(QObject):
    """Worker for import operations - runs in separate thread"""
    
    def __init__(self, group_id, source_path, selected_profiles, workspace_browser_type, workspace_path):
        super().__init__()
        self.signals = ImportExportWorkerSignals()
        self.group_id = group_id
        self.source_path = source_path
        self.selected_profiles = selected_profiles or []
        self.workspace_browser_type = workspace_browser_type
        self.workspace_path = workspace_path
    
    def run(self):
        """Run import operation in background thread"""
        try:
            from database.db_account_manager_operations import AccountManagerDB
            db = AccountManagerDB()
            temp_extract_path = None
            
            if self.source_path.endswith('.zip'):
                temp_extract_path = tempfile.mkdtemp()
                
                with zipfile.ZipFile(self.source_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_path)
                
                profile_folders = self._find_all_profile_folders(temp_extract_path)
                
                if profile_folders:
                    imported_count = 0
                    total = len(profile_folders)
                    skipped_browser_mismatch = []
                    
                    for idx, profile_info in enumerate(profile_folders):
                        profile_source_path, meta_src = profile_info if isinstance(profile_info, tuple) else (profile_info, 'internal')
                        if not os.path.isdir(profile_source_path):
                            continue
                        
                        detected_browser = self._detect_browser_type(profile_source_path)
                        
                        if detected_browser != self.workspace_browser_type:
                            skipped_browser_mismatch.append(os.path.basename(profile_source_path))
                            continue
                        
                        result = self._import_single_profile(
                            profile_info, self.workspace_path, self.workspace_browser_type, db
                        )
                        if result:
                            imported_count += 1
                        
                        self.signals.progress.emit(idx + 1, total)
                    
                    if temp_extract_path and os.path.exists(temp_extract_path):
                        shutil.rmtree(temp_extract_path)
                    
                    self.signals.finished.emit({
                        'success': True,
                        'imported_count': imported_count,
                        'skipped_browser_mismatch': skipped_browser_mismatch,
                        'is_multi': True
                    })
                    return
                
                extracted_items = os.listdir(temp_extract_path)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_path, extracted_items[0])):
                    profile_source_path = os.path.join(temp_extract_path, extracted_items[0])
                else:
                    profile_source_path = temp_extract_path
            else:
                profile_source_path = self.source_path
            
            if not os.path.isdir(profile_source_path):
                if temp_extract_path and os.path.exists(temp_extract_path):
                    shutil.rmtree(temp_extract_path)
                self.signals.error.emit('Source does not contain a valid profile folder')
                return
            
            result = self._import_single_profile(
                profile_source_path, self.workspace_path, self.workspace_browser_type, db
            )
            
            if temp_extract_path and os.path.exists(temp_extract_path):
                shutil.rmtree(temp_extract_path)
            
            self.signals.finished.emit({
                'success': bool(result),
                'profile_id': result,
                'is_multi': False
            })
            
        except Exception as e:
            self.signals.error.emit(str(e))
    
    def _detect_browser_type(self, profile_path):
        """Detect browser type from profile folder contents"""
        if not os.path.exists(profile_path):
            return 'chrome'
        
        chrome_indicators = ['Preferences', 'Local Storage', 'IndexedDB']
        firefox_indicators = ['prefs.js', 'places.sqlite', 'storage']
        
        has_chrome = True
        has_firefox = True
        
        for indicator in chrome_indicators:
            if not os.path.exists(os.path.join(profile_path, indicator)):
                has_chrome = False
                break
        
        for indicator in firefox_indicators:
            if not os.path.exists(os.path.join(profile_path, indicator)):
                has_firefox = False
                break
        
        if has_firefox and not has_chrome:
            return 'firefox'
        return 'chrome'
    
    def _find_all_profile_folders(self, extract_path):
        """Find all profile folders with metadata in extracted zip"""
        profile_folders = []
        processed = set()
        
        for item in os.listdir(extract_path):
            item_path = os.path.join(extract_path, item)
            if os.path.isdir(item_path):
                meta_path = os.path.join(item_path, 'account_management_profile_metadata.json')
                if os.path.exists(meta_path):
                    profile_folders.append((item_path, 'internal'))
                    processed.add(item_path)
        
        for item in os.listdir(extract_path):
            item_path = os.path.join(extract_path, item)
            if os.path.isdir(item_path) and item_path not in processed:
                meta_file = os.path.join(extract_path, f'{item}_metadata.json')
                if os.path.exists(meta_file):
                    profile_folders.append((item_path, meta_file))
        
        return profile_folders
    
    def _import_single_profile(self, profile_info, workspace_path, workspace_browser_type, db):
        if isinstance(profile_info, tuple):
            profile_source_path, meta_src = profile_info
            zip_name = os.path.basename(profile_source_path)
        else:
            profile_source_path = profile_info
            meta_src = 'internal'
            zip_name = None
        
        if not os.path.isdir(profile_source_path):
            return None
        
        detected_browser_type = self._detect_browser_type(profile_source_path)
        
        if meta_src == 'internal':
            metadata = db.load_profile_metadata(profile_source_path)
        else:
            try:
                with open(meta_src, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except:
                metadata = None
        
        if metadata:
            profile_name = metadata.get('profile_name', os.path.basename(profile_source_path))
            profile_desc = metadata.get('profile_description', '')
            profile_icon = metadata.get('profile_icon', 'fa6s.user')
            profile_color = metadata.get('profile_color', '#3b82f6')
            browser_profile_name = metadata.get('profile_browser_profile_name', os.path.basename(profile_source_path))
            metadata_browser_type = metadata.get('profile_browser_type', detected_browser_type)
            profile_settings = metadata.get('profile_settings', {}) if isinstance(metadata.get('profile_settings', {}), dict) else {}
        else:
            folder_name = os.path.basename(profile_source_path)
            profile_name = folder_name
            profile_desc = ''
            profile_icon = 'fa6s.user'
            profile_color = '#3b82f6'
            browser_profile_name = folder_name
            metadata_browser_type = detected_browser_type
            profile_settings = {}
        
        existing_profiles = db.get_profiles_by_group(self.group_id)
        existing_profile_names = [p.get('profile_name', '') for p in existing_profiles]
        
        # Preserve underscores and spaces (spaces will be converted to underscores)
        sanitized = re.sub(r'[^a-zA-Z0-9_\s]', '', browser_profile_name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        if not sanitized:
            sanitized = 'imported_profile'
        
        # Use sanitized name as base - folder and profile name start the same
        base_name = sanitized
        unique_folder_name = base_name
        profile_name_display = base_name
        
        # Check folder conflicts and adjust (keep profile name in sync with folder)
        while True:
            full_path = os.path.join(workspace_path, unique_folder_name)
            if not os.path.exists(full_path):
                break
            unique_folder_name = f"{unique_folder_name}_copy"
            profile_name_display = unique_folder_name
        
        shutil.copytree(profile_source_path, full_path)
        
        profile_id = db.create_profile(
            self.group_id,
            profile_name_display,
            profile_desc,
            profile_icon,
            profile_color,
            unique_folder_name,
            full_path,
            browser_type=metadata_browser_type,
            zip_name=zip_name
        )
        
        for setting_key, setting_value in profile_settings.items():
            db.set_profile_setting(profile_id, setting_key, setting_value)
        
        meta_data = {
            'profile_id': profile_id,
            'profile_name': profile_name_display,
            'profile_description': profile_desc,
            'profile_icon': profile_icon,
            'profile_color': profile_color,
            'profile_browser_profile_name': unique_folder_name,
            'profile_browser_profile_path': full_path,
            'group_id': self.group_id,
            'profile_order_index': 0,
            'profile_created_at': datetime.now().isoformat(),
            'profile_updated_at': datetime.now().isoformat(),
            'profile_browser_type': metadata_browser_type,
            'profile_settings': profile_settings,
        }
        db.save_profile_metadata(meta_data)
        
        return profile_id


class ExportWorker(QObject):
    """Worker for export operations - runs in separate thread"""
    
    def __init__(self, profile, export_path, is_multi=False):
        super().__init__()
        self.signals = ImportExportWorkerSignals()
        self.profile = profile
        self.export_path = export_path
        self.is_multi = is_multi
    
    def _build_profile_metadata(self, profile, db):
        profile_id = profile.get('profile_id')
        profile_settings = db.get_profile_settings(profile_id) if profile_id else {}
        return {
            'profile_id': profile.get('profile_id'),
            'profile_name': profile.get('profile_name', ''),
            'profile_description': profile.get('profile_description', ''),
            'profile_icon': profile.get('profile_icon', 'fa6s.user'),
            'profile_color': profile.get('profile_color', '#3b82f6'),
            'profile_browser_profile_name': profile.get('profile_browser_profile_name', ''),
            'profile_browser_profile_path': profile.get('profile_browser_profile_path', ''),
            'group_id': profile.get('profile_group_id'),
            'profile_order_index': profile.get('profile_order_index', 0),
            'profile_created_at': profile.get('profile_created_at'),
            'profile_updated_at': profile.get('profile_updated_at'),
            'profile_browser_type': profile.get('profile_browser_type', 'chrome'),
            'profile_settings': profile_settings,
        }
    
    def run(self):
        try:
            from database.db_account_manager_operations import AccountManagerDB
            db = AccountManagerDB()
            if self.is_multi:
                profiles = self.profile
                with zipfile.ZipFile(self.export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for idx, profile in enumerate(profiles):
                        profile_path = profile.get('profile_browser_profile_path', '')
                        if not profile_path or not os.path.exists(profile_path):
                            continue
                        
                        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', profile.get('profile_name', 'profile'))
                        
                        for root, dirs, files in os.walk(profile_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, profile_path)
                                zipf.write(file_path, os.path.join(safe_name, arcname))
                        
                        meta_data = self._build_profile_metadata(profile, db)
                        zipf.writestr(f'{safe_name}_metadata.json', json.dumps(meta_data, indent=2))
                        
                        self.signals.progress.emit(idx + 1, len(profiles))
                
                self.signals.finished.emit({
                    'success': True,
                    'exported_count': len(profiles),
                    'export_path': self.export_path
                })
            else:
                profile_path = self.profile.get('profile_browser_profile_path', '')
                profile_name = self.profile.get('profile_name', 'profile')
                
                with zipfile.ZipFile(self.export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(profile_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, profile_path)
                            zipf.write(file_path, os.path.join('profile', arcname))
                    
                    meta_data = self._build_profile_metadata(self.profile, db)
                    zipf.writestr('account_management_profile_metadata.json', json.dumps(meta_data, indent=2))
                
                self.signals.finished.emit({
                    'success': True,
                    'profile_name': profile_name,
                    'export_path': self.export_path
                })
                
        except Exception as e:
            self.signals.error.emit(str(e))