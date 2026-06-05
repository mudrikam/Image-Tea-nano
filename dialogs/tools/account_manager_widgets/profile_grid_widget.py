from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QGridLayout, QPushButton, QLabel, QMessageBox, QLineEdit, QDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
import os
import qtawesome as qta
from ui.theme_system import theme
from database.db_account_manager_operations import AccountManagerDB
from dialogs.tools.account_manager_widgets.profile_row_widget import ProfileRowWidget
from dialogs.tools.account_manager_widgets.delete_confirmation_dialog import DeleteConfirmationDialog
from dialogs.tools.account_manager_widgets.browser_manager import BrowserManager


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
        
        # Header with workspace/group info and New Profile button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Workspace/Group info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        self.workspace_label = QLabel('Workspace: -')
        self.workspace_label.setStyleSheet(f'font-size: 10px; color: {theme.get_color("text_dark")};')
        info_layout.addWidget(self.workspace_label)
        
        self.group_label = QLabel('Group: -')
        self.group_label.setStyleSheet('font-size: 12px; font-weight: bold;')
        info_layout.addWidget(self.group_label)
        
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        primary = theme.get_color('primary')
        primary_hover = theme.get_color('primary_hover')
        
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
    
    def set_workspace_group_info(self, workspace_name, group_name):
        """Update header with current workspace and group names"""
        self.workspace_label.setText(f'Workspace: {workspace_name}')
        self.group_label.setText(f'Group: {group_name}')
    
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
        
        # Get workspace for auto-generating profile path
        group = self.db.get_group(self.current_group_id)
        workspace = self.db.get_workspace(group['group_workspace_id']) if group else None
        
        from dialogs.tools.account_manager_widgets.add_profile_dialog import AddProfileDialog
        dialog = AddProfileDialog(workspace_data=workspace, parent=self)
        dialog.profile_saved.connect(self._on_profile_saved)
        dialog.exec()
    
    def _on_edit_profile(self, profile_id):
        profile = self.db.get_profile(profile_id)
        if not profile:
            return
        
        # Get workspace for auto-generating profile path
        group = self.db.get_group(profile['profile_group_id'])
        workspace = self.db.get_workspace(group['group_workspace_id']) if group else None
        
        from dialogs.tools.account_manager_widgets.add_profile_dialog import AddProfileDialog
        dialog = AddProfileDialog(profile_data=profile, workspace_data=workspace, parent=self)
        dialog.profile_saved.connect(self._on_profile_saved)
        dialog.exec()
    
    def _on_delete_profile(self, profile_id):
        profile = self.db.get_profile(profile_id)
        if not profile:
            return
        
        profile_name = profile["profile_name"]
        
        # Use new confirmation dialog
        dialog = DeleteConfirmationDialog('Profile', profile_name, self)
        if dialog.exec() == QDialog.Accepted:
            self.db.delete_profile(profile_id)
            self.refresh_profiles()
    
    def _on_profile_saved(self, data):
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
            # Create mode
            self.db.create_profile(
                self.current_group_id,
                data['profile_name'],
                data['profile_description'],
                data['profile_icon'],
                data['profile_color'],
                data['profile_browser_profile_name'],
                data['profile_browser_profile_path']
            )
        
        self.refresh_profiles()
    
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
