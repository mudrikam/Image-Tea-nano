from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QPushButton, QScrollArea, 
    QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QComboBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import qtawesome as qta


class ClearableLineEdit(QLineEdit):
    """QLineEdit that clears on Delete key when focused"""
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.clear()
            event.accept()
            return
        super().keyPressEvent(event)
from ui.theme_system import theme
from database.db_account_manager_operations import AccountManagerDB
from dialogs.tools.account_manager_widgets.delete_confirmation_dialog import DeleteConfirmationDialog


class GroupItemWidget(QWidget):
    """Individual group item in sidebar"""
    clicked = Signal(int)  # group_id
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    
    def __init__(self, group_data, parent=None):
        super().__init__(parent)
        self.group_data = group_data
        self.group_id = group_data['group_id']
        self._hover = False
        self._selected = False
        self._setup_ui()
    
    def get_group_name(self):
        """Return group name for external use"""
        return self.group_data.get('group_name', 'Unnamed')
    
    def _setup_ui(self):
        icon_name = self.group_data.get('group_icon', 'users')
        color = self.group_data.get('group_color', '#3b82f6')
        name = self.group_data.get('group_name', 'Unnamed')
        desc = self.group_data.get('group_description', '')
        
        r_hex, g_hex, b_hex = color.lstrip('#')[0:2], color.lstrip('#')[2:4], color.lstrip('#')[4:6]
        r, g, b = int(r_hex, 16), int(g_hex, 16), int(b_hex, 16)
        
        self.setObjectName(f'groupItem_{self.group_id}')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setCursor(Qt.PointingHandCursor)
        
        self._hover_style = f'''
            #groupItem_{self.group_id} {{
                background-color: rgba({r}, {g}, {b}, 0.2);
                border: 1px solid rgba({r}, {g}, {b}, 0.6);
                border-radius: 4px;
            }}
        '''
        self._selected_style = f'''
            #groupItem_{self.group_id} {{
                background-color: rgba({r}, {g}, {b}, 0.25);
                border: 1px solid rgba({r}, {g}, {b}, 0.8);
                border-radius: 4px;
            }}
        '''
        self._update_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        
        icon_label = QLabel()
        try:
            if '.' not in icon_name:
                icon = qta.icon(f'fa6s.{icon_name}', color=color)
            else:
                icon = qta.icon(icon_name, color=color)
            icon_label.setPixmap(icon.pixmap(16, 16))
        except:
            icon = qta.icon('fa6s.users', color=color)
            icon_label.setPixmap(icon.pixmap(16, 16))
        icon_label.setFixedSize(18, 18)
        layout.addWidget(icon_label)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        
        name_label = QLabel(name)
        name_label.setStyleSheet('font-weight: bold; font-size: 11px;')
        content_layout.addWidget(name_label)
        
        if desc:
            desc_label = QLabel(desc)
            desc_label.setStyleSheet(f'color: {theme.get_color("gray")}; font-size: 9px;')
            desc_label.setWordWrap(True)
            content_layout.addWidget(desc_label)
        
        layout.addLayout(content_layout, 1)
        
        # Edit button
        edit_btn = QPushButton(qta.icon('fa6s.pen'), '')
        edit_btn.setFixedSize(30, 30)
        edit_btn.setFlat(True)
        edit_btn.setStyleSheet('background: transparent; border: none;')
        edit_btn.setFocusPolicy(Qt.NoFocus)
        edit_btn.setToolTip('Edit Group')
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.group_id))
        layout.addWidget(edit_btn)
        
        # Delete button
        delete_btn = QPushButton(qta.icon('fa6s.trash'), '')
        delete_btn.setFixedSize(30, 30)
        delete_btn.setFlat(True)
        delete_btn.setStyleSheet('background: transparent; border: none;')
        delete_btn.setFocusPolicy(Qt.NoFocus)
        delete_btn.setToolTip('Delete Group')
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.group_id))
        layout.addWidget(delete_btn)
    
    def set_selected(self, selected):
        """Set selected state - shows selected style"""
        self._selected = selected
        self._update_style()
    
    def _update_style(self):
        """Update style based on hover and selected state"""
        if self._selected:
            self.setStyleSheet(self._selected_style)
        elif self._hover:
            self.setStyleSheet(self._hover_style)
        else:
            # Use gray background like profile row when not selected/hovered
            gray = QColor(theme.get_color('gray'))
            self.setStyleSheet(f'''
                #groupItem_{self.group_id} {{
                    background-color: rgba({gray.red()}, {gray.green()}, {gray.blue()}, 0.05);
                    border: 1px solid rgba({gray.red()}, {gray.green()}, {gray.blue()}, 0.2);
                    border-radius: 4px;
                }}
            ''')
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.group_id)
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        self._hover = True
        self._update_style()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._hover = False
        self._update_style()
        super().leaveEvent(event)
    
    def _show_context_menu(self, pos):
        menu = QMenu(self)
        
        edit_action = menu.addAction(qta.icon('fa6s.pen'), 'Edit')
        menu.addSeparator()
        delete_action = menu.addAction(qta.icon('fa6s.trash'), 'Delete')
        
        edit_action.triggered.connect(lambda: self.edit_requested.emit(self.group_id))
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.group_id))
        
        menu.exec(self.mapToGlobal(pos))


class GroupSidebarWidget(QWidget):
    """Sidebar with workspace selector and groups"""
    group_selected = Signal(int)  # group_id
    workspace_changed = Signal(int)  # workspace_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = AccountManagerDB()
        self.current_workspace_id = None
        self.selected_group_id = None
        self._all_groups = []  # Store all groups for filtering
        self._setup_ui()
        self.refresh_workspaces()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        primary = theme.get_color('primary')
        primary_hover = theme.get_color('primary_hover')
        
        # Workspace selector section
        ws_label = QLabel('Workspace')
        ws_label.setStyleSheet(f'font-size: 10px; color: {theme.get_color("gray")}; font-weight: bold;')
        layout.addWidget(ws_label)
        
        ws_selector_layout = QHBoxLayout()
        ws_selector_layout.setSpacing(4)
        
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumHeight(28)
        self.workspace_combo.currentIndexChanged.connect(self._on_workspace_selected)
        ws_selector_layout.addWidget(self.workspace_combo, 1)
        
        self.ws_new_btn = QPushButton(qta.icon('fa6s.plus'), '')
        self.ws_new_btn.setFixedSize(28, 28)
        self.ws_new_btn.setToolTip('New Workspace')
        self.ws_new_btn.clicked.connect(self._on_new_workspace)
        ws_selector_layout.addWidget(self.ws_new_btn)
        
        self.ws_edit_btn = QPushButton(qta.icon('fa6s.pen'), '')
        self.ws_edit_btn.setFixedSize(28, 28)
        self.ws_edit_btn.setToolTip('Edit Workspace')
        self.ws_edit_btn.clicked.connect(self._on_edit_workspace)
        ws_selector_layout.addWidget(self.ws_edit_btn)
        
        self.ws_delete_btn = QPushButton(qta.icon('fa6s.trash'), '')
        self.ws_delete_btn.setFixedSize(28, 28)
        self.ws_delete_btn.setToolTip('Delete Workspace')
        self.ws_delete_btn.clicked.connect(self._on_delete_workspace)
        ws_selector_layout.addWidget(self.ws_delete_btn)
        
        layout.addLayout(ws_selector_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Groups section
        groups_label = QLabel('Groups')
        groups_label.setStyleSheet(f'font-size: 10px; color: {theme.get_color("gray")}; font-weight: bold;')
        layout.addWidget(groups_label)
        
        # New Group + Search in one row
        action_layout = QHBoxLayout()
        action_layout.setSpacing(6)
        
        # New Group button (folder icon)
        self.new_group_btn = QPushButton(qta.icon('fa6s.folder-plus'), ' New Group')
        self.new_group_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {primary};
                color: white;
                border: none;
                padding: 6px 10px;
                border-radius: 3px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {primary_hover}; }}
        ''')
        self.new_group_btn.clicked.connect(self._on_new_group)
        action_layout.addWidget(self.new_group_btn)
        
        # Search bar
        search_icon = QLabel()
        search_icon.setPixmap(qta.icon('fa6s.magnifying-glass', color=theme.get_color('gray')).pixmap(16, 16))
        action_layout.addWidget(search_icon)
        self.groups_search_input = ClearableLineEdit()
        self.groups_search_input.setPlaceholderText('Search groups...')
        self.groups_search_input.textChanged.connect(self._filter_groups)
        self.groups_search_input.setClearButtonEnabled(True)
        self.groups_search_input.setToolTip('Delete key clears search')
        action_layout.addWidget(self.groups_search_input)
        
        layout.addLayout(action_layout)
        
        # Scroll area for groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.groups_container = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_container)
        self.groups_layout.setContentsMargins(4, 4, 4, 4)
        self.groups_layout.setSpacing(4)
        self.groups_layout.addStretch()
        
        scroll.setWidget(self.groups_container)
        layout.addWidget(scroll)
    
    def refresh_workspaces(self):
        """Reload workspace list"""
        self.workspace_combo.blockSignals(True)
        self.workspace_combo.clear()
        
        workspaces = self.db.get_workspaces()
        for ws in workspaces:
            self.workspace_combo.addItem(ws['workspace_name'], ws['workspace_id'])
        
        if workspaces:
            self.workspace_combo.setCurrentIndex(0)
            self.current_workspace_id = workspaces[0]['workspace_id']
            self._update_workspace_buttons(True)
        else:
            self._update_workspace_buttons(False)
        
        self.workspace_combo.blockSignals(False)
        
        if self.current_workspace_id:
            self.refresh_groups()
    
    def _update_workspace_buttons(self, has_workspace):
        self.ws_edit_btn.setEnabled(has_workspace)
        self.ws_delete_btn.setEnabled(has_workspace)
        self.new_group_btn.setEnabled(has_workspace)
    
    def _on_workspace_selected(self, index):
        if index >= 0:
            workspace_id = self.workspace_combo.itemData(index)
            self.current_workspace_id = workspace_id
            self.selected_group_id = None  # Reset selected group when workspace changes
            self.refresh_groups()
            self.workspace_changed.emit(workspace_id)
            self.group_selected.emit(None)  # Clear profile rows when workspace changes
    
    def _on_new_workspace(self):
        from dialogs.tools.account_manager_widgets.add_workspace_dialog import AddWorkspaceDialog
        dialog = AddWorkspaceDialog(parent=self)
        dialog.workspace_saved.connect(self._on_workspace_saved)
        dialog.exec()
    
    def _on_edit_workspace(self):
        if not self.current_workspace_id:
            return
        
        workspace = self.db.get_workspace(self.current_workspace_id)
        if not workspace:
            return
        
        from dialogs.tools.account_manager_widgets.add_workspace_dialog import AddWorkspaceDialog
        dialog = AddWorkspaceDialog(workspace_data=workspace, parent=self)
        dialog.workspace_saved.connect(self._on_workspace_saved)
        dialog.exec()
    
    def _on_delete_workspace(self):
        if not self.current_workspace_id:
            return
        
        workspace = self.db.get_workspace(self.current_workspace_id)
        if not workspace:
            return
        
        workspace_name = workspace["workspace_name"]
        
        # Use new confirmation dialog
        dialog = DeleteConfirmationDialog('Workspace', workspace_name, self)
        if dialog.exec() == QDialog.Accepted:
            self.db.delete_workspace(self.current_workspace_id)
            self.refresh_workspaces()
    
    def _on_workspace_saved(self, data):
        if 'workspace_id' in data:
            self.db.update_workspace(
                data['workspace_id'],
                name=data['workspace_name'],
                description=data['workspace_description'],
                icon=data['workspace_icon'],
                color=data['workspace_color'],
                browser_exe_path=data['workspace_browser_exe_path'],
                root_profile_path=data['workspace_root_profile_path'],
                browser_type=data.get('workspace_browser_type', 'chrome')
            )
        else:
            workspace_id = self.db.create_workspace(
                data['workspace_name'],
                data['workspace_description'],
                data['workspace_icon'],
                data['workspace_color'],
                data['workspace_browser_exe_path'],
                data['workspace_root_profile_path'],
                browser_type=data.get('workspace_browser_type', 'chrome')
            )
            self.current_workspace_id = workspace_id
        
        self.refresh_workspaces()
        # Emit workspace_changed to refresh header in parent
        if self.current_workspace_id:
            self.workspace_changed.emit(self.current_workspace_id)
    
    def refresh_groups(self):
        """Reload groups from database"""
        while self.groups_layout.count() > 1:
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.current_workspace_id:
            self._all_groups = []
            return
        
        self._all_groups = self.db.get_groups_by_workspace(self.current_workspace_id)
        self._filter_groups()
        
        # Do NOT auto-select first group - user must manually select group to populate profiles
        # Header is updated by workspace_changed signal in account_manager_widget.py
        if not self._all_groups:
            self.selected_group_id = None
            self.group_selected.emit(None)
    
    def _filter_groups(self):
        """Filter groups based on search text"""
        while self.groups_layout.count() > 1:
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        search_text = self.groups_search_input.text().lower() if hasattr(self, 'groups_search_input') else ''
        
        for group in self._all_groups:
            group_name = group.get('group_name', '').lower()
            if search_text and search_text not in group_name:
                continue
            
            item = GroupItemWidget(group)
            item.clicked.connect(self._on_group_clicked)
            item.edit_requested.connect(self._on_edit_group)
            item.delete_requested.connect(self._on_delete_group)
            self.groups_layout.insertWidget(self.groups_layout.count() - 1, item)
    
    def _on_group_clicked(self, group_id):
        self.selected_group_id = group_id
        self._update_group_selection()
        self.group_selected.emit(group_id)
    
    def _update_group_selection(self):
        """Update selection styling for all group items"""
        for i in range(self.groups_layout.count() - 1):
            item = self.groups_layout.itemAt(i)
            if item and item.widget():
                item.widget().set_selected(item.widget().group_id == self.selected_group_id)
    
    def _on_new_group(self):
        if not self.current_workspace_id:
            QMessageBox.warning(self, 'No Workspace', 'Please select a workspace first')
            return
        
        from dialogs.tools.account_manager_widgets.add_group_dialog import AddGroupDialog
        dialog = AddGroupDialog(parent=self)
        dialog.group_saved.connect(self._on_group_saved)
        dialog.exec()
    
    def _on_edit_group(self, group_id):
        group = self.db.get_group(group_id)
        if not group:
            return
        
        from dialogs.tools.account_manager_widgets.add_group_dialog import AddGroupDialog
        dialog = AddGroupDialog(group_data=group, parent=self)
        dialog.group_saved.connect(self._on_group_saved)
        dialog.exec()
    
    def _on_delete_group(self, group_id):
        group = self.db.get_group(group_id)
        if not group:
            return
        
        group_name = group["group_name"]
        
        # Use new confirmation dialog
        dialog = DeleteConfirmationDialog('Group', group_name, self)
        if dialog.exec() == QDialog.Accepted:
            self.db.delete_group(group_id)
            self.refresh_groups()
    
    def _on_group_saved(self, data):
        if 'group_id' in data:
            self.db.update_group(
                data['group_id'],
                name=data['group_name'],
                description=data['group_description'],
                icon=data['group_icon'],
                color=data['group_color']
            )
        else:
            group_id = self.db.create_group(
                self.current_workspace_id,
                data['group_name'],
                data['group_description'],
                data['group_icon'],
                data['group_color']
            )
            self.selected_group_id = group_id
        
        self.refresh_groups()
