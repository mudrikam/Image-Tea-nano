from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QGridLayout, QPushButton, QLabel, QMessageBox, QLineEdit, QDialog,
    QFileDialog, QMenu
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QKeyEvent
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
from dialogs.tools.account_manager_widgets.progress_dialog import ProgressDialog


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
            return
        
        self._all_profiles = self.db.get_profiles_by_group(self.current_group_id)
        self._filter_profiles()
    
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

    def _sync_selection_to_visible_rows(self):
        visible_ids = set(self._get_visible_profile_ids())
        self._selected_profile_ids = {profile_id for profile_id in self._selected_profile_ids if profile_id in visible_ids}
        if self._selection_anchor_profile_id not in visible_ids:
            self._selection_anchor_profile_id = next(iter(self._selected_profile_ids), None)

    def _clear_selection(self):
        self._selected_profile_ids.clear()
        self._selection_anchor_profile_id = None
        self._update_profile_selection()

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
            menu.addSeparator()
            export_action = menu.addAction(qta.icon('fa6s.file-zipper'), 'Export')
            menu.addSeparator()
            delete_action = menu.addAction(qta.icon('fa6s.trash'), 'Delete')

            edit_action.triggered.connect(lambda: self._on_edit_profile(profile_id))
            export_action.triggered.connect(lambda: self._on_export_profile_row(profile_id))
            delete_action.triggered.connect(lambda: self._on_delete_profile(profile_id))

        menu.exec(global_pos)
    
    def _update_profile_selection(self):
        """Update selection styling for all profile rows"""
        for row in self._get_visible_rows():
            row.set_selected(row.profile_id in self._selected_profile_ids)
    
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
        browser_type = profile.get('profile_browser_type', workspace.get('workspace_browser_type', 'chrome'))
        
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
        pid = self.browser_manager.launch(profile_id, browser_exe, profile_path, browser_type)
        
        if pid:
            # Poll until browser window is visible, then switch to Focus state
            attempts = {'count': 0}
            
            def check_launched():
                row = self._find_row(profile_id)
                if not row:
                    return
                
                if self.browser_manager.has_window(profile_id) or self.browser_manager.is_running(profile_id):
                    row.set_launching(False)
                    row.set_launched(True)
                    return
                
                attempts['count'] += 1
                if attempts['count'] >= 30:
                    row.set_launching(False)
                    row.set_launched(False)
                    return
                
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
        
        group = self.db.get_group(self.current_group_id)
        workspace = self.db.get_workspace(group['group_workspace_id']) if group else None
        workspace_browser_type = workspace.get('workspace_browser_type', 'chrome') if workspace else 'chrome'
        
        dialog = ImportProfileDialog(workspace_browser_type=workspace_browser_type, parent=self)
        if dialog.exec() == QDialog.Accepted:
            source_path = dialog.selected_source
            selected_profiles = dialog.selected_profiles
            if source_path:
                self._import_profile(source_path, selected_profiles, workspace_browser_type)
    
    def _on_export_profile(self):
        profiles = self.db.get_profiles_by_group(self.current_group_id)
        if not profiles:
            QMessageBox.information(self, 'No Profiles', 'No profiles to export in current group')
            return
        
        # Get group name for export all filename
        group = self.db.get_group(self.current_group_id)
        group_name = group.get('group_name', 'profiles') if group else 'profiles' if group else 'profiles'
        
        dialog = ExportProfileDialog(profiles, group_name=group_name, parent=self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.is_export_all:
                self._export_profiles_all(dialog.selected_profiles, group_name)
            else:
                selected_profile = dialog.selected_profile
                if selected_profile:
                    self._export_profile(selected_profile)
    
    def _on_export_profile_row(self, profile_id):
        """Handle export from context menu on profile row"""
        profile = self.db.get_profile(profile_id)
        if profile:
            self._export_profile(profile)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.childAt(event.position().toPoint()):
            self._clear_selection()
        super().mousePressEvent(event)
    
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
            return sanitized, sanitized
        
        # Use _copy suffix instead of numbers
        new_name = f"{sanitized}_copy"
        full_path = os.path.join(workspace_path, new_name)
        if not os.path.exists(full_path):
            return sanitized, new_name
        
        # If _copy also exists, keep adding _copy
        while True:
            new_name = f"{new_name}_copy"
            full_path = os.path.join(workspace_path, new_name)
            if not os.path.exists(full_path):
                return sanitized, new_name
    
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
    
    def _import_profile(self, source_path, selected_profiles=None, workspace_browser_type='chrome'):
        """Import profile(s) from zip or folder - supports single or multiple profiles"""
        if selected_profiles is None:
            selected_profiles = []
        group = self.db.get_group(self.current_group_id)
        if not group:
            return
        
        workspace = self.db.get_workspace(group['group_workspace_id'])
        if not workspace:
            return
        
        workspace_path = workspace.get('workspace_root_profile_path', '')
        workspace_browser_type = workspace.get('workspace_browser_type', 'chrome')
        if not workspace_path:
            QMessageBox.warning(self, 'No Workspace Path', 'Workspace root profile path not set')
            return
        
        # Show progress dialog
        if selected_profiles and len(selected_profiles) > 1:
            self._show_progress("Importing Profiles", f"Importing {len(selected_profiles)} profiles...", indeterminate=True)
        else:
            self._show_progress("Importing Profile", "Preparing import...", indeterminate=True)
        
        temp_extract_path = None
        
        try:
            if source_path.endswith('.zip'):
                temp_extract_path = tempfile.mkdtemp()
                
                # Extract and detect browser types
                with zipfile.ZipFile(source_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_path)
                
                profile_folders = self._find_all_profile_folders(temp_extract_path)
                
                if profile_folders:
                    # Multi-profile zip - check browser compatibility
                    imported_count = 0
                    total = len(profile_folders)
                    
                    for idx, profile_info in enumerate(profile_folders):
                        profile_source_path, meta_src = profile_info if isinstance(profile_info, tuple) else (profile_info, 'internal')
                        if not os.path.isdir(profile_source_path):
                            continue
                        
                        detected_browser = self._detect_browser_type(profile_source_path)
                        
                        if detected_browser != workspace_browser_type:
                            self._hide_progress()
                            # Show warning about browser mismatch
                            browser_names = {'chrome': 'Chrome/Chromium', 'firefox': 'Firefox'}
                            reply = QMessageBox.question(
                                self, 'Browser Type Mismatch',
                                f'The profile "{os.path.basename(profile_source_path)}" is detected as {browser_names.get(detected_browser, detected_browser)} profile, but current workspace is {browser_names.get(workspace_browser_type, workspace_browser_type)}.\n\n'
                                f'Importing this profile may cause issues. Continue anyway?',
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No
                            )
                            if reply == QMessageBox.No:
                                continue
                            self._show_progress("Importing Profile", f"Importing profile {idx + 1} of {total}...", indeterminate=True)
                        
                        result = self._import_single_profile(profile_info, workspace_path, workspace_browser_type)
                        if result:
                            imported_count += 1
                    
                    self.refresh_profiles()
                    self._hide_progress()
                    if imported_count > 0:
                        QMessageBox.information(self, 'Import Successful', f'Imported {imported_count} profile(s)')
                    return
                
                extracted_items = os.listdir(temp_extract_path)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_path, extracted_items[0])):
                    profile_source_path = os.path.join(temp_extract_path, extracted_items[0])
                else:
                    profile_source_path = temp_extract_path
            else:
                profile_source_path = source_path
            
            if not os.path.isdir(profile_source_path):
                self._hide_progress()
                QMessageBox.warning(self, 'Invalid Source', 'Source does not contain a valid profile folder')
                return
            
            result = self._import_single_profile(profile_source_path, workspace_path, workspace_browser_type)
            self._hide_progress()
            if result:
                self.refresh_profiles()
                QMessageBox.information(self, 'Import Successful', f'Profile imported successfully')
            
        except Exception as e:
            self._hide_progress()
            QMessageBox.critical(self, 'Import Failed', f'Failed to import profile:\n{str(e)}')
        finally:
            if temp_extract_path and os.path.exists(temp_extract_path):
                shutil.rmtree(temp_extract_path)
    
    def _find_all_profile_folders(self, extract_path):
        """Find all profile folders with metadata in extracted zip (supports single and all_profiles format)"""
        profile_folders = []
        processed = set()
        
        # First pass: find folders with account_management_profile_metadata.json inside
        for item in os.listdir(extract_path):
            item_path = os.path.join(extract_path, item)
            if os.path.isdir(item_path):
                meta_path = os.path.join(item_path, 'account_management_profile_metadata.json')
                if os.path.exists(meta_path):
                    profile_folders.append((item_path, 'internal'))
                    processed.add(item_path)
        
        # Second pass: find folders matching *_metadata.json in root (all_profiles format)
        for item in os.listdir(extract_path):
            item_path = os.path.join(extract_path, item)
            if os.path.isdir(item_path) and item_path not in processed:
                meta_file = os.path.join(extract_path, f'{item}_metadata.json')
                if os.path.exists(meta_file):
                    profile_folders.append((item_path, meta_file))
        
        return profile_folders
    
    def _import_single_profile(self, profile_info, workspace_path, workspace_browser_type):
        """Import a single profile folder - profile_info is (path, metadata_source)"""
        if isinstance(profile_info, tuple):
            profile_source_path, meta_src = profile_info
            zip_name = os.path.basename(profile_source_path)
        else:
            profile_source_path = profile_info
            meta_src = 'internal'
            zip_name = None
        
        if not os.path.isdir(profile_source_path):
            return False
        
        # Detect browser type from profile folder
        detected_browser_type = self._detect_browser_type(profile_source_path)
        
        # Load metadata based on source
        if meta_src == 'internal':
            metadata = self.db.load_profile_metadata(profile_source_path)
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
        else:
            folder_name = os.path.basename(profile_source_path)
            profile_name = folder_name
            profile_desc = ''
            profile_icon = 'fa6s.user'
            profile_color = '#3b82f6'
            browser_profile_name = folder_name
            metadata_browser_type = detected_browser_type
        
        # Get unique profile folder name and profile name
        original_folder_name, unique_folder_name = self._get_unique_profile_name(browser_profile_name, workspace_path)
        
        # Also ensure unique profile name (for display)
        existing_profile_names = [p.get('profile_name', '') for p in self._all_profiles]
        profile_name_display = profile_name
        if profile_name_display in existing_profile_names:
            profile_name_display = f"{profile_name}_copy"
            while profile_name_display in existing_profile_names:
                profile_name_display = f"{profile_name_display}_copy"
        
        dest_path = os.path.join(workspace_path, unique_folder_name)
        
        if os.path.exists(dest_path):
            reply = QMessageBox.question(
                self, 'Profile Exists',
                f'A profile folder named "{unique_folder_name}" already exists. Overwrite?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return None
            
            if profile_source_path == dest_path:
                return None  # Same source, skip
            
            shutil.rmtree(dest_path)
        
        shutil.copytree(profile_source_path, dest_path)
        
        profile_id = self.db.create_profile(
            self.current_group_id,
            profile_name_display,
            profile_desc,
            profile_icon,
            profile_color,
            unique_folder_name,
            dest_path,
            browser_type=metadata_browser_type,
            zip_name=zip_name
        )
        
        self._save_profile_metadata_for_import(profile_id, profile_name_display, profile_desc, 
                                                profile_icon, profile_color, unique_folder_name, dest_path, metadata_browser_type)
        
        return profile_id
    
    def _save_profile_metadata_for_import(self, profile_id, name, desc, icon, color, browser_name, browser_path, browser_type):
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
            'profile_browser_type': browser_type,
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
        
        self._show_progress("Exporting Profile", f"Exporting {profile_name}...", indeterminate=True)
        
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
                    'profile_browser_type': profile.get('profile_browser_type', 'chrome'),
                }
                zipf.writestr('account_management_profile_metadata.json', json.dumps(meta_data, indent=2))
            
            self._hide_progress()
            QMessageBox.information(self, 'Export Successful', f'Profile exported to:\n{export_path}')
            
        except Exception as e:
            self._hide_progress()
            QMessageBox.critical(self, 'Export Failed', f'Failed to export profile:\n{str(e)}')
    
    def _export_profiles_all(self, profiles, group_name):
        """Export all profiles to single zip file with group name"""
        if not profiles:
            return
        
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
        
        self._show_progress("Exporting Profiles", f"Exporting {len(profiles)} profiles...", indeterminate=True)
        
        try:
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for profile in profiles:
                    profile_path = profile.get('profile_browser_profile_path', '')
                    profile_name = profile.get('profile_name', 'profile')
                    
                    if not profile_path or not os.path.exists(profile_path):
                        continue
                    
                    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', profile_name)
                    
                    for root, dirs, files in os.walk(profile_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, profile_path)
                            zipf.write(file_path, os.path.join(safe_name, arcname))
                    
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
                    }
                    zipf.writestr(f'{safe_name}_metadata.json', json.dumps(meta_data, indent=2))
            
            self._hide_progress()
            QMessageBox.information(self, 'Export Successful', f'Exported {len(profiles)} profiles to:\n{export_path}')
            
        except Exception as e:
            self._hide_progress()
            QMessageBox.critical(self, 'Export Failed', f'Failed to export profiles:\n{str(e)}')
    
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
                'profile_browser_type': profile.get('profile_browser_type', 'chrome'),
            }
            self.db.save_profile_metadata(meta_data)