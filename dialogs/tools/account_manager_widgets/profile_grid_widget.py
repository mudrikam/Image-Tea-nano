from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QGridLayout, QPushButton, QLabel, QMessageBox, QLineEdit, QDialog,
    QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor
import os
import shutil
import zipfile
import tempfile
import re
import json
from datetime import datetime
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme
from database.db_account_manager_operations import AccountManagerDB
from dialogs.tools.account_manager_widgets.profile_row_widget import ProfileRowWidget
from dialogs.tools.account_manager_widgets.delete_confirmation_dialog import DeleteConfirmationDialog
from dialogs.tools.account_manager_widgets.browser_manager import BrowserManager
from dialogs.tools.account_manager_widgets.add_profile_dialog import AddProfileDialog
from dialogs.tools.account_manager_widgets.import_profile_dialog import ImportProfileDialog
from dialogs.tools.account_manager_widgets.export_profile_dialog import ExportProfileDialog


class ProfileGridWidget(QWidget):
    """Grid display of profile cards for selected group"""
    profile_launched = Signal(int)  # profile_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = AccountManagerDB()
        self.browser_manager = BrowserManager()
        self.current_group_id = None
        self._setup_ui()
        self._setup_timer()
    
    def _setup_timer(self):
        """Setup timer to check for externally closed browsers"""
        self._check_timer = QTimer(self)
        self._check_timer.timeout.connect(self._check_external_closes)
        self._check_timer.start(1000)  # Check every second
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        
        # Header with workspace/group info and action buttons
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Workspace/Group info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # Workspace label with icon
        ws_layout = QHBoxLayout()
        ws_layout.setSpacing(6)
        self.workspace_icon_label = QLabel()
        self.workspace_icon_label.setPixmap(qta.icon('fa6s.briefcase', color=theme.get_color('primary')).pixmap(16, 16))
        ws_layout.addWidget(self.workspace_icon_label)
        self.workspace_label = QLabel('Workspace: -')
        self.workspace_label.setStyleSheet(f'font-size: 14px; color: {theme.get_color("text_dark")};')
        ws_layout.addWidget(self.workspace_label)
        info_layout.addLayout(ws_layout)
        
        self.group_label = QLabel('Group: -')
        self.group_label.setStyleSheet(f'font-size: 12px; font-weight: bold; color: {theme.get_color("gray")};')
        info_layout.addWidget(self.group_label)
        
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        primary = theme.get_color('primary')
        primary_hover = theme.get_color('primary_hover')
        
        # Import button (left of New Profile) - vanilla style
        self.import_btn = QPushButton(qta.icon('fa6s.file-import'), ' Import')
        self.import_btn.setToolTip('Import Profile')
        self.import_btn.clicked.connect(self._on_import_profile)
        header_layout.addWidget(self.import_btn)
        
        # Export button - vanilla style
        self.export_btn = QPushButton(qta.icon('fa6s.file-zipper'), ' Export')
        self.export_btn.setToolTip('Export Profile')
        self.export_btn.clicked.connect(self._on_export_profile)
        header_layout.addWidget(self.export_btn)
        
        # New Profile button - primary style for distinction
        self.new_profile_btn = QPushButton(qta.icon('fa6s.plus', color='white'), ' New Profile')
        self.new_profile_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {primary};
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {primary_hover}; }}
        ''')
        self.new_profile_btn.clicked.connect(self._on_new_profile)
        header_layout.addWidget(self.new_profile_btn)
        
        layout.addLayout(header_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(4, 4, 4, 4)
        self.rows_layout.setSpacing(6)
        self.rows_layout.addStretch()
        
        scroll.setWidget(self.rows_container)
        layout.addWidget(scroll)
      
    def set_workspace_group_info(self, workspace_name, group_name, profile_count=0):
        """Update header with current workspace and group names"""
        self.workspace_label.setText(f'Workspace: {workspace_name}')
        self.group_label.setText(f'Group: {group_name} | {profile_count}')
    
    def update_workspace_display(self, workspace_name, icon_value, color):
        """Update workspace label with icon and color styling"""
        self.workspace_label.setText(f'Workspace: {workspace_name}')
        self.workspace_label.setStyleSheet(f'font-size: 14px; color: {color};')
        try:
            self.workspace_icon_label.setPixmap(qta.icon(f'fa6s.{icon_value}', color=color).pixmap(16, 16))
        except:
            self.workspace_icon_label.setPixmap(qta.icon('fa6s.briefcase', color=color).pixmap(16, 16))
      
    def set_group(self, group_id):
        """Load profiles for group"""
        self.current_group_id = group_id
        self.refresh_profiles()
    
    def refresh_profiles(self):
        """Reload profiles from database"""
        # Clear existing rows
        while self.rows_layout.count() > 1:
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.current_group_id:
            return
        
        profiles = self.db.get_profiles_by_group(self.current_group_id)
        
        # Add rows
        for profile in profiles:
            row = ProfileRowWidget(profile)
            row.launch_clicked.connect(self._on_launch_profile)
            row.focus_clicked.connect(self._on_focus_profile)
            row.close_clicked.connect(self._on_close_profile)
            row.edit_clicked.connect(self._on_edit_profile)
            row.delete_clicked.connect(self._on_delete_profile)
            
            # Restore launched state if browser is still running
            if self.browser_manager.is_running(profile['profile_id']):
                row.set_launched(True)
            
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
    
    def _on_new_profile(self):
        if not self.current_group_id:
            QMessageBox.warning(self, 'No Group', 'Please select a group first')
            return
        
        group = self.db.get_group(self.current_group_id)
        workspace = self.db.get_workspace(group['group_workspace_id']) if group else None
        
        dialog = AddProfileDialog(workspace_data=workspace, parent=self)
        dialog.profile_saved.connect(self._on_profile_saved)
        dialog.exec()
    
    def _on_edit_profile(self, profile_id):
        profile = self.db.get_profile(profile_id)
        if not profile:
            return
        
        if self.browser_manager.is_running(profile_id):
            reply = QMessageBox.question(
                self, 'Profile Running',
                'This profile is currently running. Editing will close the browser.\n\nContinue?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            self.browser_manager.close(profile_id)
        
        group = self.db.get_group(profile['profile_group_id'])
        workspace = self.db.get_workspace(group['group_workspace_id']) if group else None
        
        dialog = AddProfileDialog(profile_data=profile, workspace_data=workspace, parent=self)
        dialog.profile_saved.connect(self._on_profile_saved)
        dialog.exec()
    
    def _on_delete_profile(self, profile_id):
        profile = self.db.get_profile(profile_id)
        if not profile:
            return
        
        profile_name = profile["profile_name"]
        profile_path = profile.get("profile_browser_profile_path", "")
        
        # Check if profile is running
        if self.browser_manager.is_running(profile_id):
            reply = QMessageBox.question(
                self, 'Profile Running',
                'This profile is currently running. Deleting will close the browser.\n\nContinue?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            self.browser_manager.close(profile_id)
        
# Use new confirmation dialog
        dialog = DeleteConfirmationDialog('Profile', profile_name, self)
        if dialog.exec() == QDialog.Accepted:
            # Delete profile folder if exists
            if profile_path and os.path.exists(profile_path):
                try:
                    shutil.rmtree(profile_path)
                except Exception as e:
                    QMessageBox.warning(self, 'Delete Warning', 
                        f'Could not delete profile folder:\n{e}\n\nProfile will be deleted from database but folder remains.')
            
            self.db.delete_profile(profile_id)
            self.refresh_profiles()
    
    def _on_profile_saved(self, data):
        profile_id = data.get('profile_id')
        is_edit = profile_id is not None
        
        # Get old profile data for folder rename logic
        old_profile = None
        if is_edit:
            old_profile = self.db.get_profile(profile_id)
        
        # Handle folder rename if profile is running or name/path changed
        if is_edit and old_profile:
            old_browser_name = old_profile.get('profile_browser_profile_name', '')
            old_browser_path = old_profile.get('profile_browser_profile_path', '')
            new_browser_name = data.get('profile_browser_profile_name', '')
            new_browser_path = data.get('profile_browser_profile_path', '')
            
            # Check if profile is running
            was_running = self.browser_manager.is_running(profile_id)
            
            if was_running:
                # Close the browser first before renaming
                self.browser_manager.close(profile_id)
            
            # Rename folder if browser profile name changed and old path exists
            if old_browser_name and new_browser_name and old_browser_name != new_browser_name:
                if os.path.exists(old_browser_path):
                    try:
                        # Rename the folder
                        parent_dir = os.path.dirname(old_browser_path)
                        new_full_path = os.path.join(parent_dir, new_browser_name)
                        if old_browser_path != new_full_path:
                            shutil.move(old_browser_path, new_full_path)
                            # Update the path in data
                            data['profile_browser_profile_path'] = new_full_path
                    except Exception as e:
                        QMessageBox.warning(self, 'Rename Warning', 
                            f'Could not rename profile folder:\n{e}\n\nProfile will be saved with new path but old folder remains.')
        
        if 'profile_id' in data:
            # Edit mode
            self.db.update_profile(
                data['profile_id'],
                name=data['profile_name'],
                description=data['profile_description'],
                icon=data['profile_icon'],
                color=data['profile_color'],
                browser_profile_name=data['profile_browser_profile_name'],
                browser_profile_path=data['profile_browser_profile_path']
            )
        else:
            # Create mode - get the new profile_id
            profile_id = self.db.create_profile(
                self.current_group_id,
                data['profile_name'],
                data['profile_description'],
                data['profile_icon'],
                data['profile_color'],
                data['profile_browser_profile_name'],
                data['profile_browser_profile_path']
            )
            data['profile_id'] = profile_id
        
        # Save metadata file to profile folder
        self._save_profile_metadata(data)
        
        self.refresh_profiles()
    
    def _save_profile_metadata(self, data):
        """Save profile metadata JSON to profile folder"""
        profile_id = data.get('profile_id')
        if not profile_id:
            return
        
        profile = self.db.get_profile(profile_id)
        if profile:
            meta_data = {
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
            }
            self.db.save_profile_metadata(meta_data)
    
    def _on_launch_profile(self, profile_id):
        """Launch browser with profile"""
        self.profile_launched.emit(profile_id)
        
        profile = self.db.get_profile(profile_id)
        if not profile:
            return
        
        # Get workspace to find browser exe
        group = self.db.get_group(profile['profile_group_id'])
        if not group:
            return
        
        workspace = self.db.get_workspace(group['group_workspace_id'])
        if not workspace:
            return
        
        browser_exe = workspace.get('workspace_browser_exe_path', '')
        profile_path = profile.get('profile_browser_profile_path', '')
        
        if not browser_exe:
            QMessageBox.warning(self, 'No Browser', 'Browser executable not set in workspace')
            return
        
        if not os.path.exists(browser_exe):
            QMessageBox.warning(self, 'Browser Not Found', f'Browser executable not found:\n{browser_exe}')
            return
        
        # Find row and set launching state
        for i in range(self.rows_layout.count() - 1):
            item = self.rows_layout.itemAt(i)
            if item and item.widget():
                row = item.widget()
                if hasattr(row, 'profile_id') and row.profile_id == profile_id:
                    row.set_launching(True)
                    break
        
        # Launch browser
        pid = self.browser_manager.launch(profile_id, browser_exe, profile_path)
        
        if pid:
            # Poll for process to be ready, then switch to Focus state
            def check_launched():
                row = self._find_row(profile_id)
                if row and self.browser_manager.is_running(profile_id):
                    row.set_launching(False)
                    row.set_launched(True)
                    return
                if row:
                    QTimer.singleShot(200, check_launched)
            
            QTimer.singleShot(500, check_launched)
    
    def _on_focus_profile(self, profile_id):
        """Focus already launched browser"""
        if self.browser_manager.focus(profile_id):
            row = self._find_row(profile_id)
            if row:
                row.set_launched(True)
    
    def _on_close_profile(self, profile_id):
        """Close launched browser"""
        if self.browser_manager.close(profile_id):
            row = self._find_row(profile_id)
            if row:
                row.set_launched(False)
    
    def _check_external_closes(self):
        """Periodically check if any launched browsers were closed externally"""
        for i in range(self.rows_layout.count() - 1):
            item = self.rows_layout.itemAt(i)
            if item and item.widget():
                row = item.widget()
                if hasattr(row, 'profile_id') and hasattr(row, '_is_launched') and row._is_launched:
                    if not self.browser_manager.is_running(row.profile_id):
                        row.set_launched(False)
    
    def _find_row(self, profile_id):
        """Find ProfileRowWidget by profile_id"""
        for i in range(self.rows_layout.count() - 1):
            item = self.rows_layout.itemAt(i)
            if item and item.widget():
                row = item.widget()
                if hasattr(row, 'profile_id') and row.profile_id == profile_id:
                    return row
        return None

    def _on_import_profile(self):
        if not self.current_group_id:
            QMessageBox.warning(self, 'No Group', 'Please select a group first')
            return
        
        dialog = ImportProfileDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            source_path = dialog.selected_source
            if source_path:
                self._import_profile(source_path)

    def _on_export_profile(self):
        profiles = self.db.get_profiles_by_group(self.current_group_id)
        if not profiles:
            QMessageBox.information(self, 'No Profiles', 'No profiles to export in current group')
            return
        
        dialog = ExportProfileDialog(profiles, parent=self)
        if dialog.exec() == QDialog.Accepted:
            selected_profile = dialog.selected_profile
            if selected_profile:
                self._export_profile(selected_profile)

    def _detect_browser_type(self, profile_path):
        """Detect browser type from profile folder contents"""
        if not os.path.exists(profile_path):
            return 'chrome'  # default
        
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
        return 'chrome'  # default to chrome

    def _get_unique_profile_name(self, base_name, workspace_path):
        """Generate unique profile name with _copy suffix if exists"""
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', base_name)
        sanitized = re.sub(r'\s+', '_', sanitized).strip('_')
        
        if not sanitized:
            sanitized = 'imported_profile'
        
        full_path = os.path.join(workspace_path, sanitized)
        if not os.path.exists(full_path):
            return sanitized
        
        counter = 1
        while True:
            new_name = f"{sanitized}_{counter}"
            full_path = os.path.join(workspace_path, new_name)
            if not os.path.exists(full_path):
                return new_name
            counter += 1

    def _import_profile(self, source_path):
        """Import profile from zip or folder"""
        group = self.db.get_group(self.current_group_id)
        if not group:
            return
        
        workspace = self.db.get_workspace(group['group_workspace_id'])
        if not workspace:
            return
        
        workspace_path = workspace.get('workspace_root_profile_path', '')
        if not workspace_path:
            QMessageBox.warning(self, 'No Workspace Path', 'Workspace root profile path not set')
            return
        
        temp_extract_path = None
        
        try:
            if source_path.endswith('.zip'):
                temp_extract_path = tempfile.mkdtemp()
                with zipfile.ZipFile(source_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_path)
                
                extracted_items = os.listdir(temp_extract_path)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_path, extracted_items[0])):
                    profile_source_path = os.path.join(temp_extract_path, extracted_items[0])
                else:
                    profile_source_path = temp_extract_path
            else:
                profile_source_path = source_path
            
            if not os.path.isdir(profile_source_path):
                QMessageBox.warning(self, 'Invalid Source', 'Source does not contain a valid profile folder')
                return
            
            metadata = self.db.load_profile_metadata(profile_source_path)
            
            if metadata:
                profile_name = metadata.get('profile_name', os.path.basename(profile_source_path))
                profile_desc = metadata.get('profile_description', '')
                profile_icon = metadata.get('profile_icon', 'fa6s.user')
                profile_color = metadata.get('profile_color', '#3b82f6')
                browser_profile_name = metadata.get('profile_browser_profile_name', os.path.basename(profile_source_path))
            else:
                folder_name = os.path.basename(profile_source_path)
                profile_name = folder_name
                profile_desc = ''
                profile_icon = 'fa6s.user'
                profile_color = '#3b82f6'
                browser_profile_name = folder_name
            
            browser_profile_name = self._get_unique_profile_name(browser_profile_name, workspace_path)
            dest_path = os.path.join(workspace_path, browser_profile_name)
            
            if os.path.exists(dest_path):
                reply = QMessageBox.question(
                    self, 'Profile Exists',
                    f'A profile folder named "{browser_profile_name}" already exists. Overwrite?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
                shutil.rmtree(dest_path)
            
            shutil.copytree(profile_source_path, dest_path)
            
            profile_id = self.db.create_profile(
                self.current_group_id,
                profile_name,
                profile_desc,
                profile_icon,
                profile_color,
                browser_profile_name,
                dest_path
            )
            
            self._save_profile_metadata_for_import(profile_id, profile_name, profile_desc, 
                                                  profile_icon, profile_color, browser_profile_name, dest_path)
            
            self.refresh_profiles()
            QMessageBox.information(self, 'Import Successful', f'Profile "{profile_name}" imported successfully')
            
        except Exception as e:
            QMessageBox.critical(self, 'Import Failed', f'Failed to import profile:\n{str(e)}')
        finally:
            if temp_extract_path and os.path.exists(temp_extract_path):
                shutil.rmtree(temp_extract_path)

    def _save_profile_metadata_for_import(self, profile_id, name, desc, icon, color, browser_name, browser_path):
        """Save metadata for imported profile"""
        meta_data = {
            'profile_id': profile_id,
            'profile_name': name,
            'profile_description': desc,
            'profile_icon': icon,
            'profile_color': color,
            'profile_browser_profile_name': browser_name,
            'profile_browser_profile_path': browser_path,
            'group_id': self.current_group_id,
            'profile_order_index': 0,
            'profile_created_at': datetime.now().isoformat(),
            'profile_updated_at': datetime.now().isoformat(),
        }
        self.db.save_profile_metadata(meta_data)
    
    def _export_profile(self, profile):
        """Export profile to zip file"""
        profile_path = profile.get('profile_browser_profile_path', '')
        profile_name = profile.get('profile_name', 'profile')
        
        if not os.path.exists(profile_path):
            QMessageBox.warning(self, 'Export Failed', f'Profile folder not found:\n{profile_path}')
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"{re.sub(r'[^a-zA-Z0-9]', '_', profile_name)}_{timestamp}.zip"
        
        export_path, _ = QFileDialog.getSaveFileName(
            self,
            'Export Profile',
            default_filename,
            'ZIP Files (*.zip);;All Files (*.*)'
        )
        
        if not export_path:
            return
        
        try:
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(profile_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, profile_path)
                        zipf.write(file_path, os.path.join('profile', arcname))
                
                meta_data = {
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
                }
                zipf.writestr('account_management_profile_metadata.json', json.dumps(meta_data, indent=2))
            
            QMessageBox.information(self, 'Export Successful', f'Profile exported to:\n{export_path}')
            
        except Exception as e:
            QMessageBox.critical(self, 'Export Failed', f'Failed to export profile:\n{str(e)}')

    def _save_profile_metadata(self, data):
        """Save profile metadata JSON to profile folder"""
        profile_id = data.get('profile_id')
        if not profile_id:
            return
        
        profile = self.db.get_profile(profile_id)
        if profile:
            meta_data = {
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
            }
            self.db.save_profile_metadata(meta_data)
