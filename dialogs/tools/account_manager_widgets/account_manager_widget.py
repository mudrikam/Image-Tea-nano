import os
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
import qtawesome as qta
from config import BASE_PATH

from dialogs.tools.account_manager_widgets.group_sidebar_widget import GroupSidebarWidget
from dialogs.tools.account_manager_widgets.profile_grid_widget import ProfileGridWidget
from dialogs.tools.account_manager_widgets.account_manager_stats_widget import AccountManagerStatsWidget
from database.db_account_manager_operations import AccountManagerDB


class AccountManagerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = AccountManagerDB()
        self._current_workspace_id = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Horizontal splitter: groups sidebar (with workspace) | profile grid
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        self.group_sidebar = GroupSidebarWidget()
        splitter.addWidget(self.group_sidebar)

        self.profile_grid = ProfileGridWidget()
        splitter.addWidget(self.profile_grid)

        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 800])

        layout.addWidget(splitter)
        
        # Stats bar below
        self.stats_widget = AccountManagerStatsWidget()
        layout.addWidget(self.stats_widget)
        
        # Initial stats update
        self._update_stats()

    def _connect_signals(self):
        # When workspace changes, update header and clear profiles
        # Connect workspace_changed first to ensure header updates before group selection
        self.group_sidebar.workspace_changed.connect(self._on_workspace_changed)
        self.group_sidebar.group_selected.connect(self._on_group_selected)
        self.group_sidebar.workspace_changed.connect(self._update_stats)
        self.group_sidebar.group_selected.connect(self._update_stats)
        
        # When profile changes, update stats, refresh group info, and update group counts
        self.profile_grid.profile_changed.connect(self._update_stats)
        self.profile_grid.profile_changed.connect(self._refresh_group_info)
        self.profile_grid.profile_changed.connect(self.group_sidebar.update_group_counts)
     
    def _update_stats(self):
        """Update stats bar with current counts"""
        workspaces = self.db.get_workspaces()
        groups = self.db.get_all_groups()
        profiles = self.db.get_all_profiles()
        self.stats_widget.update_stats(len(workspaces), len(groups), len(profiles))
    
    def _on_workspace_changed(self, workspace_id):
        """When workspace changes, update header and clear profiles"""
        if workspace_id is None:
            self.profile_grid.set_workspace_group_info('-', '-', 0)
            self.profile_grid.update_workspace_display('-', 'briefcase', '#3b82f6')
            self._current_workspace_id = None
            self.profile_grid.set_workspace_id(None)
            QTimer.singleShot(0, lambda: self.profile_grid.set_group(None))
            return
        
        workspace = self.db.get_workspace(workspace_id)
        if workspace:
            self._current_workspace_id = workspace_id
            self.profile_grid.set_workspace_id(workspace_id)
            self.profile_grid.set_workspace_group_info(workspace['workspace_name'], '-', 0)
            self.profile_grid.update_workspace_display(
                workspace.get('workspace_name', '-'),
                workspace.get('workspace_icon', 'briefcase'),
                workspace.get('workspace_color', '#3b82f6')
            )
            QTimer.singleShot(0, lambda: self.profile_grid.set_group(None))
    
    def _on_group_selected(self, group_id):
        """When group is selected, update profile grid with workspace/group names"""
        if group_id is None:
            self.profile_grid.set_group(None)
            return
        
        self.profile_grid.set_group(group_id)
        
        group = self.db.get_group(group_id)
        if not group:
            return
        
        workspace = self.db.get_workspace(group['group_workspace_id'])
        if not workspace:
            return
        
        profile_count = len(self.db.get_profiles_by_group(group_id))
        
        self.profile_grid.set_workspace_group_info(
            workspace['workspace_name'],
            group['group_name'],
            profile_count
        )
        
        self.profile_grid.update_workspace_display(
            workspace.get('workspace_name', '-'),
            workspace.get('workspace_icon', 'briefcase'),
            workspace.get('workspace_color', '#3b82f6')
        )
    
    def _refresh_group_info(self):
        """Refresh group info labels when profile changes"""
        if not self.profile_grid.current_group_id:
            return
        
        group_id = self.profile_grid.current_group_id
        group = self.db.get_group(group_id)
        if not group:
            return
        
        workspace = self.db.get_workspace(group['group_workspace_id'])
        if not workspace:
            return
        
        profile_count = len(self.db.get_profiles_by_group(group_id))
        
        self.profile_grid.set_workspace_group_info(
            workspace['workspace_name'],
            group['group_name'],
            profile_count
        )


class AccountManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Account Manager')
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.resize(1000, 600)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._main_widget = AccountManagerWidget()
        root_layout.addWidget(self._main_widget)

    def closeEvent(self, event):
        event.accept()
