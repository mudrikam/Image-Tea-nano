from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QGridLayout, QPushButton, QLabel, QMessageBox, QLineEdit, QDialog,
    QFileDialog, QMenu
)
from PySide6.QtCore import Qt, Signal, QTimer, Slot, QThread
from PySide6.QtGui import QPixmap, QPainter, QColor, QKeyEvent
import os
import shutil
import zipfile
import tempfile
import re
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
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
from dialogs.tools.account_manager_widgets.progress_dialog import ProgressDialog
from dialogs.tools.account_manager_widgets.import_export_worker import ImportWorker, ExportWorker


class ClearableLineEdit(QLineEdit):
    """QLineEdit that clears on Delete key when focused"""
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.clear()
            event.accept()
            return
        super().keyPressEvent(event)


class ProfileGridWidget(QWidget):
    """Grid display of profile cards for selected group"""
    profile_launched = Signal(int)  # profile_id
    profile_changed = Signal()  # Notify when profile is created/updated/deleted
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = AccountManagerDB()
        self.browser_manager = BrowserManager()
        self.current_workspace_id = None
        self.current_group_id = None
        self._all_profiles = []  # Store all profiles for filtering
        self._selected_profile_ids = set()
        self._selection_anchor_profile_id = None
        self._progress_dialog = None
        self._worker = None
        self._thread = None
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
        
        # New Profile button - separate row at top, primary style
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
        
        # Search + Import + Export in one row
        action_layout = QHBoxLayout()
        action_layout.setSpacing(6)
        
        # Search bar
        search_icon = QLabel()
        search_icon.setPixmap(qta.icon('fa6s.magnifying-glass', color=theme.get_color('gray')).pixmap(16, 16))
        action_layout.addWidget(search_icon)
        self.profile_search_input = ClearableLineEdit()
        self.profile_search_input.setPlaceholderText('Search profiles...')
        self.profile_search_input.textChanged.connect(self._filter_profiles)
        self.profile_search_input.setClearButtonEnabled(True)
        action_layout.addWidget(self.profile_search_input)
        
        # Import button
        self.import_btn = QPushButton(qta.icon('fa6s.file-import'), ' Import')
        self.import_btn.setToolTip('Import Profile')
        self.import_btn.clicked.connect(self._on_import_profile)
        action_layout.addWidget(self.import_btn)
        
        # Export button
        self.export_btn = QPushButton(qta.icon('fa6s.file-zipper'), ' Export')
        self.export_btn.setToolTip('Export Profile')
        self.export_btn.clicked.connect(self._on_export_profile)
        action_layout.addWidget(self.export_btn)

        # Launch selected button
        self.launch_selected_btn = QPushButton(qta.icon('fa6s.play'), ' Launch Selected')
        self.launch_selected_btn.setToolTip('Launch selected profiles')
        self.launch_selected_btn.clicked.connect(self._launch_selected_profiles)
        self.launch_selected_btn.setEnabled(False)
        action_layout.addWidget(self.launch_selected_btn)

        # Launch all button
        self.launch_all_btn = QPushButton(qta.icon('fa6s.rocket'), ' Launch All')
        self.launch_all_btn.setToolTip('Launch all profiles in the current group')
        self.launch_all_btn.clicked.connect(self._on_launch_all_button_clicked)
        self.launch_all_btn.setEnabled(False)
        action_layout.addWidget(self.launch_all_btn)
        
        layout.addLayout(action_layout)
        
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
            if '.' in icon_value:
                icon = qta.icon(icon_value, color=color)
            else:
                icon = qta.icon(f'fa6s.{icon_value}', color=color)
            self.workspace_icon_label.setPixmap(icon.pixmap(16, 16))
        except:
            self.workspace_icon_label.setPixmap(qta.icon('fa6s.briefcase', color=color).pixmap(16, 16))
    
    def set_group(self, group_id):
        """Load profiles for group"""
        self.current_group_id = group_id
        self._clear_selection()
        # Get workspace from group
        if group_id:
            group = self.db.get_group(group_id)
            if group:
                self.current_workspace_id = group.get('group_workspace_id')
        self.refresh_profiles()
        self._update_action_buttons()
    
    def set_workspace_id(self, workspace_id):
        """Set workspace id for browser type fallback"""
        self.current_workspace_id = workspace_id
    
    def refresh_profiles(self):
        """Reload profiles from database"""
        # Clear existing rows
        while self.rows_layout.count() > 1:
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.current_group_id:
            self._all_profiles = []
            self._clear_selection()
            self._update_action_buttons()
            return
        
        self._all_profiles = self.db.get_profiles_by_group(self.current_group_id)
        self._filter_profiles()
        self._update_action_buttons()
    
    def _filter_profiles(self):
        """Filter profiles based on search text"""
        while self.rows_layout.count() > 1:
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        search_text = self.profile_search_input.text().lower() if hasattr(self, 'profile_search_input') else ''
        
        # Get workspace browser type for fallback
        workspace = self.db.get_workspace(self.current_workspace_id) if self.current_workspace_id else None
        workspace_browser_type = workspace.get('workspace_browser_type', 'chrome') if workspace else 'chrome'
        
        for profile in self._all_profiles:
            profile_name = profile.get('profile_name', '').lower()
            if search_text and search_text not in profile_name:
                continue
            
            # Ensure browser_type is set (fallback to workspace type or default)
            if not profile.get('profile_browser_type'):
                profile['profile_browser_type'] = workspace_browser_type
            
            row = ProfileRowWidget(profile)
            row.launch_clicked.connect(self._on_launch_profile)
            row.focus_clicked.connect(self._on_focus_profile)
            row.close_clicked.connect(self._on_close_profile)
            row.edit_clicked.connect(self._on_edit_profile)
            row.delete_clicked.connect(self._on_delete_profile)
            row.export_clicked.connect(self._on_export_profile_row)
            row.clicked.connect(self._on_profile_clicked)
            row.context_menu_requested.connect(self._on_profile_context_menu_requested)
            
            # Restore launched state if browser is still running
            if self.browser_manager.is_running(profile['profile_id']):
                row.set_launched(True)
            
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
        
        self._sync_selection_to_visible_rows()
        self._update_profile_selection()
        self._update_action_buttons()
    
    def _get_visible_rows(self):
        rows = []
        for i in range(self.rows_layout.count() - 1):
            item = self.rows_layout.itemAt(i)
            if item and item.widget():
                rows.append(item.widget())
        return rows
    
    def _get_visible_profile_ids(self):
        return [row.profile_id for row in self._get_visible_rows()]
    
    def _get_selected_profile_ids(self):
        visible_ids = set(self._get_visible_profile_ids())
        return [profile_id for profile_id in self._get_visible_profile_ids() if profile_id in self._selected_profile_ids and profile_id in visible_ids]
    
    def _get_selected_profiles(self):
        profiles = []
        for profile_id in self._get_selected_profile_ids():
            profile = self.db.get_profile(profile_id)
            if profile:
                profiles.append(profile)
        return profiles

    def _update_action_buttons(self):
        has_group = self.current_group_id is not None
        selected_count = len(self._get_selected_profile_ids())
        has_profiles_in_group = bool(self._all_profiles)
        group_profile_ids = [profile.get('profile_id') for profile in self._all_profiles if profile.get('profile_id') is not None]
        running_group_count = sum(1 for profile_id in group_profile_ids if self.browser_manager.is_running(profile_id))
        all_group_profiles_running = bool(group_profile_ids) and running_group_count == len(group_profile_ids)

        if hasattr(self, 'launch_selected_btn'):
            self.launch_selected_btn.setEnabled(selected_count > 1)
        if hasattr(self, 'launch_all_btn'):
            self.launch_all_btn.setEnabled(has_group and has_profiles_in_group)
            if all_group_profiles_running:
                self.launch_all_btn.setText(' Close All')
                self.launch_all_btn.setIcon(qta.icon('fa6s.xmark'))
                self.launch_all_btn.setToolTip('Close all running profiles in the current group')
            else:
                self.launch_all_btn.setText(' Launch All')
                self.launch_all_btn.setIcon(qta.icon('fa6s.rocket'))
                self.launch_all_btn.setToolTip('Launch all profiles in the current group')
    
    def _sync_selection_to_visible_rows(self):
        visible_ids = set(self._get_visible_profile_ids())
        self._selected_profile_ids = {profile_id for profile_id in self._selected_profile_ids if profile_id in visible_ids}
        if self._selection_anchor_profile_id not in visible_ids:
            self._selection_anchor_profile_id = next(iter(self._selected_profile_ids), None)
    
    def _clear_selection(self):
        self._selected_profile_ids.clear()
        self._selection_anchor_profile_id = None
        self._update_profile_selection()
        self._update_action_buttons()
    
    def _set_single_selection(self, profile_id):
        self._selected_profile_ids = {profile_id}
        self._selection_anchor_profile_id = profile_id
        self._update_profile_selection()
    
    def _toggle_profile_selection(self, profile_id):
        if profile_id in self._selected_profile_ids:
            self._selected_profile_ids.remove(profile_id)
            if self._selection_anchor_profile_id == profile_id:
                self._selection_anchor_profile_id = next(iter(self._selected_profile_ids), None)
        else:
            self._selected_profile_ids.add(profile_id)
            self._selection_anchor_profile_id = profile_id
        self._update_profile_selection()
    
    def _select_range_to(self, profile_id, additive=False):
        visible_ids = self._get_visible_profile_ids()
        if not visible_ids or profile_id not in visible_ids:
            return
        if self._selection_anchor_profile_id not in visible_ids:
            self._selection_anchor_profile_id = profile_id
        start_index = visible_ids.index(self._selection_anchor_profile_id)
        end_index = visible_ids.index(profile_id)
        if start_index > end_index:
            start_index, end_index = end_index, start_index
        range_ids = set(visible_ids[start_index:end_index + 1])
        if additive:
            self._selected_profile_ids.update(range_ids)
        else:
            self._selected_profile_ids = range_ids
        self._update_profile_selection()
    
    def _ensure_context_selection(self, profile_id):
        if profile_id not in self._selected_profile_ids:
            self._set_single_selection(profile_id)
        else:
            self._update_profile_selection()
    
    def _on_profile_clicked(self, profile_id, modifiers):
        modifier_value = modifiers.value if hasattr(modifiers, 'value') else int(modifiers)
        ctrl_value = Qt.ControlModifier.value if hasattr(Qt.ControlModifier, 'value') else int(Qt.ControlModifier)
        shift_value = Qt.ShiftModifier.value if hasattr(Qt.ShiftModifier, 'value') else int(Qt.ShiftModifier)
        is_ctrl = bool(modifier_value & ctrl_value)
        is_shift = bool(modifier_value & shift_value)
        
        if is_shift:
            self._select_range_to(profile_id, additive=is_ctrl)
        elif is_ctrl:
            self._toggle_profile_selection(profile_id)
        else:
            self._set_single_selection(profile_id)
    
    def _on_profile_context_menu_requested(self, profile_id, global_pos):
        self._ensure_context_selection(profile_id)
        self._show_profile_context_menu(profile_id, global_pos)
    
    def _show_profile_context_menu(self, profile_id, global_pos):
        selected_ids = self._get_selected_profile_ids()
        menu = QMenu(self)
        
        if len(selected_ids) > 1:
            running_selected_ids = [selected_id for selected_id in selected_ids if self.browser_manager.is_running(selected_id)]
            
            launch_selected_action = menu.addAction(qta.icon('fa6s.play'), 'Launch Selected')
            launch_selected_action.triggered.connect(self._launch_selected_profiles)
            
            if running_selected_ids:
                focus_selected_action = menu.addAction(qta.icon('fa6s.arrow-up-right-from-square'), 'Focus Selected')
                close_selected_action = menu.addAction(qta.icon('fa6s.xmark'), 'Close Selected')
                focus_selected_action.triggered.connect(self._focus_selected_profiles)
                close_selected_action.triggered.connect(self._close_selected_profiles)
            
            menu.addSeparator()
            delete_selected_action = menu.addAction(qta.icon('fa6s.trash'), 'Delete Selected')
            delete_selected_action.triggered.connect(self._on_delete_selected_profiles)
        else:
            edit_action = menu.addAction(qta.icon('fa6s.pen'), 'Edit')
            duplicate_action = menu.addAction(qta.icon('fa6s.copy'), 'Duplicate')
            menu.addSeparator()
            export_action = menu.addAction(qta.icon('fa6s.file-zipper'), 'Export')
            menu.addSeparator()
            delete_action = menu.addAction(qta.icon('fa6s.trash'), 'Delete')
            
            edit_action.triggered.connect(lambda: self._on_edit_profile(profile_id))
            duplicate_action.triggered.connect(lambda: self._on_duplicate_profile(profile_id))
            export_action.triggered.connect(lambda: self._on_export_profile_row(profile_id))
            delete_action.triggered.connect(lambda: self._on_delete_profile(profile_id))
        
        menu.exec(global_pos)
    
    def _update_profile_selection(self):
        """Update selection styling for all profile rows"""
        for row in self._get_visible_rows():
            row.set_selected(row.profile_id in self._selected_profile_ids)
        self._update_action_buttons()
    
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
        profile = dict(profile)
        profile.update(self.db.get_profile_settings(profile_id))
        
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

    def _build_duplicate_profile_names(self, profile_name, browser_profile_name, workspace_path):
        sanitized = re.sub(r'[^a-zA-Z0-9_\s]', '', browser_profile_name or '')
        sanitized = re.sub(r'\s+', '_', sanitized).strip('_')
        if not sanitized:
            sanitized = 'duplicated_profile'

        duplicate_profile_name = f'{profile_name}_copy'
        duplicate_folder_name = f'{sanitized}_copy'

        while os.path.exists(os.path.join(workspace_path, duplicate_folder_name)):
            duplicate_profile_name = f'{duplicate_profile_name}_copy'
            duplicate_folder_name = f'{duplicate_folder_name}_copy'

        return duplicate_profile_name, duplicate_folder_name

    def _on_duplicate_profile(self, profile_id):
        profile = self.db.get_profile(profile_id)
        if not profile:
            return

        group = self.db.get_group(profile['profile_group_id'])
        workspace = self.db.get_workspace(group['group_workspace_id']) if group else None
        workspace_path = workspace.get('workspace_root_profile_path', '') if workspace else ''
        source_profile_path = profile.get('profile_browser_profile_path', '')

        if not source_profile_path or not os.path.exists(source_profile_path):
            QMessageBox.warning(self, 'Profile Not Found', 'Source profile folder not found')
            return

        if not workspace_path or not os.path.exists(workspace_path):
            QMessageBox.warning(self, 'Workspace Not Found', 'Workspace root profile path not found')
            return

        if self.browser_manager.is_running(profile_id):
            reply = QMessageBox.question(
                self,
                'Profile Running',
                'This profile is currently running. Duplicating will close the browser first.\n\nContinue?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            self.browser_manager.close(profile_id)

        duplicate_profile_name, duplicate_folder_name = self._build_duplicate_profile_names(
            profile.get('profile_name', 'Profile'),
            profile.get('profile_browser_profile_name', profile.get('profile_name', 'profile')),
            workspace_path
        )
        duplicate_profile_path = os.path.join(workspace_path, duplicate_folder_name)
        profile_settings = self.db.get_profile_settings(profile_id)
        browser_type = profile.get('profile_browser_type') or (workspace.get('workspace_browser_type', 'chrome') if workspace else 'chrome')

        try:
            shutil.copytree(source_profile_path, duplicate_profile_path)

            new_profile_id = self.db.create_profile(
                profile['profile_group_id'],
                duplicate_profile_name,
                profile.get('profile_description', ''),
                profile.get('profile_icon', 'fa6s.user'),
                profile.get('profile_color', '#3b82f6'),
                duplicate_folder_name,
                duplicate_profile_path,
                browser_type=browser_type,
                zip_name=profile.get('profile_zip_name')
            )

            for setting_key, setting_value in profile_settings.items():
                self.db.set_profile_setting(new_profile_id, setting_key, setting_value)

            self._save_profile_metadata({'profile_id': new_profile_id})
            self.refresh_profiles()
            self._set_single_selection(new_profile_id)
            self.profile_changed.emit()
            QMessageBox.information(self, 'Duplicate Successful', f'Profile duplicated as {duplicate_profile_name}')
        except Exception as e:
            if os.path.exists(duplicate_profile_path):
                try:
                    shutil.rmtree(duplicate_profile_path)
                except Exception:
                    pass
            QMessageBox.critical(self, 'Duplicate Failed', f'Failed to duplicate profile:\n{e}')
    
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
            self._selected_profile_ids.discard(profile_id)
            if self._selection_anchor_profile_id == profile_id:
                self._selection_anchor_profile_id = next(iter(self._selected_profile_ids), None)
            self.refresh_profiles()
            self.profile_changed.emit()
    
    def _launch_selected_profiles(self):
        selected_ids = self._get_selected_profile_ids()
        if not selected_ids:
            QMessageBox.information(self, 'No Profiles Selected', 'Select one or more profiles first')
            return
        
        launchable_ids = []
        for profile_id in selected_ids:
            row = self._find_row(profile_id)
            if row and not getattr(row, '_launching', False) and not self.browser_manager.is_running(profile_id):
                launchable_ids.append(profile_id)
        
        if not launchable_ids:
            QMessageBox.information(self, 'No Launchable Profiles', 'All selected profiles are already running or launching')
            return
        
        for profile_id in launchable_ids:
            self._on_launch_profile(profile_id)

    def _launch_all_profiles(self):
        if not self.current_group_id:
            QMessageBox.warning(self, 'No Group', 'Please select a group first')
            return

        if not self._all_profiles:
            QMessageBox.information(self, 'No Profiles', 'There are no profiles in the selected group')
            return

        launchable_ids = []
        for profile in self._all_profiles:
            profile_id = profile.get('profile_id')
            if profile_id is None:
                continue

            row = self._find_row(profile_id)
            is_launching = getattr(row, '_launching', False) if row else False
            if not is_launching and not self.browser_manager.is_running(profile_id):
                launchable_ids.append(profile_id)

        if not launchable_ids:
            QMessageBox.information(self, 'No Launchable Profiles', 'All profiles in this group are already running or launching')
            return

        for profile_id in launchable_ids:
            self._on_launch_profile(profile_id)

        self._update_action_buttons()

    def _close_all_profiles(self):
        if not self.current_group_id:
            QMessageBox.warning(self, 'No Group', 'Please select a group first')
            return

        if not self._all_profiles:
            QMessageBox.information(self, 'No Profiles', 'There are no profiles in the selected group')
            return

        running_profile_ids = [
            profile.get('profile_id')
            for profile in self._all_profiles
            if profile.get('profile_id') is not None and self.browser_manager.is_running(profile.get('profile_id'))
        ]

        if not running_profile_ids:
            QMessageBox.information(self, 'No Running Profiles', 'There are no running profiles in the selected group')
            return

        for profile_id in running_profile_ids:
            self._on_close_profile(profile_id)

        self._update_action_buttons()

    def _on_launch_all_button_clicked(self):
        group_profile_ids = [profile.get('profile_id') for profile in self._all_profiles if profile.get('profile_id') is not None]
        all_group_profiles_running = bool(group_profile_ids) and all(
            self.browser_manager.is_running(profile_id) for profile_id in group_profile_ids
        )

        if all_group_profiles_running:
            self._close_all_profiles()
        else:
            self._launch_all_profiles()
    
    def _focus_selected_profiles(self):
        selected_ids = self._get_selected_profile_ids()
        if not selected_ids:
            QMessageBox.information(self, 'No Profiles Selected', 'Select one or more profiles first')
            return
        
        focused_count = 0
        for profile_id in selected_ids:
            if self.browser_manager.is_running(profile_id):
                self._on_focus_profile(profile_id)
                focused_count += 1
        
        if focused_count == 0:
            QMessageBox.information(self, 'No Running Profiles', 'None of the selected profiles are currently running')
    
    def _close_selected_profiles(self):
        selected_ids = self._get_selected_profile_ids()
        if not selected_ids:
            QMessageBox.information(self, 'No Profiles Selected', 'Select one or more profiles first')
            return
        
        closed_count = 0
        for profile_id in selected_ids:
            if self.browser_manager.is_running(profile_id):
                self._on_close_profile(profile_id)
                closed_count += 1
        
        if closed_count == 0:
            QMessageBox.information(self, 'No Running Profiles', 'None of the selected profiles are currently running')
    
    def _on_delete_selected_profiles(self):
        selected_profiles = self._get_selected_profiles()
        if len(selected_profiles) < 2:
            if len(selected_profiles) == 1:
                self._on_delete_profile(selected_profiles[0]['profile_id'])
            return
        
        running_profiles = [profile for profile in selected_profiles if self.browser_manager.is_running(profile['profile_id'])]
        if running_profiles:
            reply = QMessageBox.question(
                self,
                'Profiles Running',
                f'{len(running_profiles)} selected profile(s) are currently running. Deleting will close their browsers.\n\nContinue?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            for profile in running_profiles:
                self.browser_manager.close(profile['profile_id'])
        
        dialog = DeleteConfirmationDialog(
            'Profile',
            f'{len(selected_profiles)} profiles',
            self,
            bulk_items=selected_profiles
        )
        if dialog.exec() != QDialog.Accepted:
            return
        
        warnings = []
        deleted_ids = []
        for profile in selected_profiles:
            profile_id = profile['profile_id']
            profile_name = profile.get('profile_name', f'Profile {profile_id}')
            profile_path = profile.get('profile_browser_profile_path', '')
            
            if profile_path and os.path.exists(profile_path):
                try:
                    shutil.rmtree(profile_path)
                except Exception as e:
                    warnings.append(
                        f'{profile_name}: Could not delete profile folder:\n{e}\n\nProfile was deleted from database but folder remains.'
                    )
            
            self.db.delete_profile(profile_id)
            deleted_ids.append(profile_id)
        
        for profile_id in deleted_ids:
            self._selected_profile_ids.discard(profile_id)
        self._selection_anchor_profile_id = next(iter(self._selected_profile_ids), None)
        
        self.refresh_profiles()
        self.profile_changed.emit()
        
        if warnings:
            QMessageBox.warning(
                self,
                'Delete Warning',
                'Some profile folders could not be deleted, but the profiles were removed from the database.\n\n' + '\n\n'.join(warnings)
            )
    
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
            profile_id = data['profile_id']
        else:
            # Create mode - get the new profile_id
            group = self.db.get_group(self.current_group_id)
            workspace = self.db.get_workspace(group['group_workspace_id']) if group else None
            browser_type = workspace.get('workspace_browser_type', 'chrome') if workspace else 'chrome'
            
            profile_id = self.db.create_profile(
                self.current_group_id,
                data['profile_name'],
                data['profile_description'],
                data['profile_icon'],
                data['profile_color'],
                data['profile_browser_profile_name'],
                data['profile_browser_profile_path'],
                browser_type=browser_type
            )
            data['profile_id'] = profile_id

        self.db.set_profile_setting(
            profile_id,
            'launch_window_mode',
            data.get('launch_window_mode', 'windowed')
        )
        self.db.set_profile_setting(
            profile_id,
            'launch_additional_parameters',
            json.dumps(data.get('launch_additional_parameters', []))
        )
        self._save_proxy_settings(profile_id, data.get('proxy_settings'))
        
        # Save metadata file to profile folder
        self._save_profile_metadata(data)
        
        self.refresh_profiles()
        self.profile_changed.emit()
    
    def _save_profile_metadata(self, data):
        """Save profile metadata JSON to profile folder"""
        profile_id = data.get('profile_id')
        if not profile_id:
            return
        
        profile = self.db.get_profile(profile_id)
        if profile:
            profile_settings = self.db.get_profile_settings(profile_id)
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
                'profile_browser_type': profile.get('profile_browser_type', 'chrome'),
                'profile_settings': profile_settings,
            }
            self.db.save_profile_metadata(meta_data)

    def _save_proxy_settings(self, profile_id, proxy_settings):
        if not profile_id:
            return
        proxy_settings = proxy_settings or {}
        for key in AddProfileDialog.PROXY_SETTING_KEYS:
            default_value = '[]' if key == 'proxy_bypass_list' else ''
            if key == 'proxy_enabled':
                default_value = 'false'
            elif key == 'proxy_mode':
                default_value = 'system'
            elif key == 'proxy_scheme':
                default_value = 'http'
            elif key == 'proxy_dns_remote':
                default_value = 'false'
            elif key == 'proxy_share_all_protocols':
                default_value = 'true'
            elif key == 'proxy_socks_version':
                default_value = '5'
            self.db.set_profile_setting(profile_id, key, str(proxy_settings.get(key, default_value)))
    
    def _parse_launch_additional_parameters(self, value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            try:
                decoded = json.loads(value)
                if isinstance(decoded, list):
                    return [str(item).strip() for item in decoded if str(item).strip()]
            except json.JSONDecodeError:
                return [line.strip() for line in value.splitlines() if line.strip()]
        return []
    
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
        browser_type = profile.get('profile_browser_type', workspace.get('workspace_browser_type', 'chrome'))
        launch_window_mode = self.db.get_profile_setting(profile_id, 'launch_window_mode') or 'windowed'
        launch_additional_parameters = self._parse_launch_additional_parameters(
            self.db.get_profile_setting(profile_id, 'launch_additional_parameters')
        )
        proxy_settings = {
            key: self.db.get_profile_setting(profile_id, key)
            for key in AddProfileDialog.PROXY_SETTING_KEYS
        }
        
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
                    self._update_action_buttons()
                    break
        
        # Launch browser
        pid = self.browser_manager.launch(
            profile_id,
            browser_exe,
            profile_path,
            browser_type,
            launch_window_mode,
            launch_additional_parameters,
            proxy_settings
        )
        
        if pid:
            # Poll until browser window is visible, then switch to Focus state
            attempts = {'count': 0}
            
            def check_launched():
                row = self._find_row(profile_id)
                if not row:
                    self._update_action_buttons()
                    return
                
                if self.browser_manager.has_window(profile_id) or self.browser_manager.is_running(profile_id):
                    row.set_launching(False)
                    row.set_launched(True)
                    self._update_action_buttons()
                    return
                
                attempts['count'] += 1
                if attempts['count'] >= 30:
                    row.set_launching(False)
                    row.set_launched(False)
                    self._update_action_buttons()
                    return
                
                QTimer.singleShot(200, check_launched)
            
            QTimer.singleShot(500, check_launched)
        else:
            row = self._find_row(profile_id)
            if row:
                row.set_launching(False)
            self._update_action_buttons()
    
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
        self._update_action_buttons()
    
    def _check_external_closes(self):
        """Periodically check if any launched browsers were closed externally"""
        state_changed = False
        for i in range(self.rows_layout.count() - 1):
            item = self.rows_layout.itemAt(i)
            if item and item.widget():
                row = item.widget()
                if hasattr(row, 'profile_id') and hasattr(row, '_is_launched') and row._is_launched:
                    if not self.browser_manager.is_running(row.profile_id):
                        row.set_launched(False)
                        state_changed = True
        if state_changed:
            self._update_action_buttons()
    
    def _find_row(self, profile_id):
        """Find ProfileRowWidget by profile_id"""
        for i in range(self.rows_layout.count() - 1):
            item = self.rows_layout.itemAt(i)
            if item and item.widget():
                row = item.widget()
                if hasattr(row, 'profile_id') and row.profile_id == profile_id:
                    return row
        return None
    
    # ========== THREADING IMPORT/EXPORT METHODS ==========
    
    def _on_import_profile(self):
        """Handle import button click - starts threaded import"""
        if not self.current_group_id:
            QMessageBox.warning(self, 'No Group', 'Please select a group first')
            return
        
        group = self.db.get_group(self.current_group_id)
        workspace = self.db.get_workspace(group['group_workspace_id']) if group else None
        workspace_browser_type = workspace.get('workspace_browser_type', 'chrome') if workspace else 'chrome'
        workspace_path = workspace.get('workspace_root_profile_path', '') if workspace else ''
        
        if not workspace_path:
            QMessageBox.warning(self, 'No Workspace Path', 'Workspace root profile path not set')
            return
        
        dialog = ImportProfileDialog(workspace_browser_type=workspace_browser_type, parent=self)
        if dialog.exec() == QDialog.Accepted:
            source_path = dialog.selected_source
            selected_profiles = dialog.selected_profiles
            if source_path:
                self._run_import_thread(source_path, selected_profiles, workspace_browser_type, workspace_path)
    
    def _run_import_thread(self, source_path, selected_profiles, workspace_browser_type, workspace_path):
        """Start import operation in background thread"""
        self._worker = ImportWorker(
            self.current_group_id, 
            source_path, 
            selected_profiles, 
            workspace_browser_type,
            workspace_path
        )
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        
        self._worker.signals.progress.connect(self._on_progress_update)
        self._worker.signals.finished.connect(self._on_import_finished)
        self._worker.signals.error.connect(self._on_import_error)
        self._thread.started.connect(self._worker.run)
        self._thread.start()
        
        if selected_profiles and len(selected_profiles) > 1:
            self._show_progress("Importing Profiles", f"Importing {len(selected_profiles)} profiles...", indeterminate=True)
        else:
            self._show_progress("Importing Profile", "Preparing import...", indeterminate=True)
    
    @Slot(int, int)
    def _on_progress_update(self, value, total):
        """Update progress dialog from thread"""
        if self._progress_dialog:
            self._progress_dialog.update_progress(value, total)
    
    @Slot(object)
    def _on_import_finished(self, result):
        """Handle import completion"""
        self._hide_progress()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
        
        if result.get('success'):
            if result.get('is_multi'):
                imported_count = result.get('imported_count', 0)
                skipped = result.get('skipped_browser_mismatch', [])
                self.refresh_profiles()
                self.profile_changed.emit()
                if imported_count > 0:
                    msg = f'Imported {imported_count} profile(s)'
                    if skipped:
                        msg += f'\n\nSkipped (browser mismatch): {", ".join(skipped)}'
                    QMessageBox.information(self, 'Import Successful', msg)
            else:
                self.refresh_profiles()
                self.profile_changed.emit()
                QMessageBox.information(self, 'Import Successful', 'Profile imported successfully')
    
    @Slot(str)
    def _on_import_error(self, error_msg):
        """Handle import error"""
        self._hide_progress()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
        QMessageBox.critical(self, 'Import Failed', f'Failed to import profile:\n{error_msg}')
    
    def _on_export_profile(self):
        """Handle export button click - starts threaded export"""
        profiles = self.db.get_profiles_by_group(self.current_group_id)
        if not profiles:
            QMessageBox.information(self, 'No Profiles', 'No profiles to export in current group')
            return
        
        group = self.db.get_group(self.current_group_id)
        dialog = ExportProfileDialog(profiles, group_name=group.get('group_name', 'profiles') if group else 'profiles', parent=self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.is_export_all:
                self._run_export_all_thread(dialog.selected_profiles)
            else:
                selected_profile = dialog.selected_profile
                if selected_profile:
                    self._run_export_single_thread(selected_profile)
    
    def _run_export_single_thread(self, profile):
        """Start single export operation in background thread"""
        profile_name = profile.get('profile_name', 'profile')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"{re.sub(r'[^a-zA-Z0-9]', '_', profile_name)}_{timestamp}.zip"
        
        home_path = os.path.expanduser('~')
        default_path = os.path.join(home_path, default_filename)
        
        export_path, _ = QFileDialog.getSaveFileName(
            self,
            'Export Profile',
            default_path,
            'ZIP Files (*.zip);;All Files (*.*)'
        )
        
        if not export_path:
            return
        
        self._worker = ExportWorker(profile, export_path, is_multi=False)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        
        self._worker.signals.progress.connect(self._on_progress_update)
        self._worker.signals.finished.connect(self._on_export_finished)
        self._worker.signals.error.connect(self._on_export_error)
        self._thread.started.connect(self._worker.run)
        self._thread.start()
        
        self._show_progress("Exporting Profile", f"Exporting {profile_name}...", indeterminate=True)
    
    def _run_export_all_thread(self, profiles):
        """Start export all operation in background thread"""
        if not profiles:
            return
        
        group = self.db.get_group(self.current_group_id)
        group_name = group.get('group_name', 'profiles') if group else 'profiles'
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_group_name = re.sub(r'[^a-zA-Z0-9]', '_', group_name)
        default_filename = f"{safe_group_name}_{timestamp}.zip"
        
        home_path = os.path.expanduser('~')
        default_path = os.path.join(home_path, default_filename)
        
        export_path, _ = QFileDialog.getSaveFileName(
            self,
            'Export All Profiles',
            default_path,
            'ZIP Files (*.zip);;All Files (*.*)'
        )
        
        if not export_path:
            return
        
        self._worker = ExportWorker(profiles, export_path, is_multi=True)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        
        self._worker.signals.progress.connect(self._on_progress_update)
        self._worker.signals.finished.connect(self._on_export_finished)
        self._worker.signals.error.connect(self._on_export_error)
        self._thread.started.connect(self._worker.run)
        self._thread.start()
        
        self._show_progress("Exporting Profiles", f"Exporting {len(profiles)} profiles...", indeterminate=True)
    
    def _on_export_profile_row(self, profile_id):
        """Handle export from context menu on profile row"""
        profile = self.db.get_profile(profile_id)
        if profile:
            self._run_export_single_thread(profile)
    
    @Slot(object)
    def _on_export_finished(self, result):
        """Handle export completion"""
        self._hide_progress()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
        
        if result.get('success'):
            if result.get('is_multi'):
                exported_count = result.get('exported_count', 0)
                QMessageBox.information(self, 'Export Successful', f'Exported {exported_count} profiles to:\n{result.get("export_path")}')
            else:
                QMessageBox.information(self, 'Export Successful', f'Profile exported to:\n{result.get("export_path")}')
    
    @Slot(str)
    def _on_export_error(self, error_msg):
        """Handle export error"""
        self._hide_progress()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
        QMessageBox.critical(self, 'Export Failed', f'Failed to export profile:\n{error_msg}')
    
    # ========== PROGRESS DIALOG METHODS ==========
    
    def _show_progress(self, title, detail, indeterminate=False):
        """Show progress dialog"""
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        
        self._progress_dialog = ProgressDialog(title=title, parent=self)
        self._progress_dialog.set_title(title)
        self._progress_dialog.set_detail(detail)
        if indeterminate:
            self._progress_dialog.set_indeterminate(True)
        else:
            self._progress_dialog.set_progress(0)
        self._progress_dialog.show()
        self._progress_dialog.raise_()
        self._progress_dialog.activateWindow()
    
    def _hide_progress(self):
        """Hide progress dialog"""
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
    
def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.childAt(event.position().toPoint()):
            self._clear_selection()
        super().mousePressEvent(event)