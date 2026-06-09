import json
import os
import shutil
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from database.db_operation import get_db_path


class AccountManagerDB:
    """Database operations for Account Manager (workspace > group > profile hierarchy)"""
    
    WORKSPACE_METADATA_FILENAME = 'account_management_workspace_metadata.json'
    PROFILE_METADATA_FILENAME = 'account_management_profile_metadata.json'
    
    def __init__(self):
        self.db_path = get_db_path()
    
    def _get_connection(self):
        """Create sqlite connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
    
    def _normalize_path(self, path: str) -> str:
        """Normalize filesystem path for comparisons on Windows."""
        if not path:
            return ''
        try:
            return os.path.normcase(os.path.abspath(os.path.normpath(path.strip())))
        except Exception:
            return os.path.normcase(path.strip())
    
    def get_workspace_metadata_path(self, root_profile_path: str) -> str:
        """Return workspace metadata file path for a root workspace directory."""
        normalized_root = self._normalize_path(root_profile_path)
        if not normalized_root:
            return ''
        return os.path.join(normalized_root, self.WORKSPACE_METADATA_FILENAME)
    
    def _load_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Safely load a JSON object from disk."""
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    
    def _write_json_file(self, file_path: str, data: Dict[str, Any]) -> bool:
        """Safely write a JSON object to disk."""
        if not file_path:
            return False
        try:
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def workspace_metadata_exists(self, root_profile_path: str) -> bool:
        """Return True when a workspace metadata file exists in the root directory."""
        metadata_path = self.get_workspace_metadata_path(root_profile_path)
        return bool(metadata_path and os.path.exists(metadata_path))
    
    def load_workspace_metadata(self, root_profile_path: str) -> Optional[Dict[str, Any]]:
        """Load workspace metadata JSON from root directory."""
        return self._load_json_file(self.get_workspace_metadata_path(root_profile_path))
    
    def get_workspace_by_root_path(self, root_profile_path: str) -> Optional[Dict[str, Any]]:
        """Find a workspace by normalized root profile path."""
        normalized_target = self._normalize_path(root_profile_path)
        if not normalized_target:
            return None
        for workspace in self.get_workspaces():
            if self._normalize_path(workspace.get('workspace_root_profile_path', '')) == normalized_target:
                return workspace
        return None
    
    def _get_workspace_id_by_group_id(self, group_id: int, conn=None) -> Optional[int]:
        """Resolve workspace id from a group id."""
        owns_connection = conn is None
        if owns_connection:
            conn = self._get_connection()
        try:
            c = conn.cursor()
            c.execute('SELECT group_workspace_id FROM account_groups WHERE group_id = ?', (group_id,))
            row = c.fetchone()
            return row[0] if row else None
        finally:
            if owns_connection:
                conn.close()
    
    def _get_workspace_id_by_profile_id(self, profile_id: int, conn=None) -> Optional[int]:
        """Resolve workspace id from a profile id."""
        owns_connection = conn is None
        if owns_connection:
            conn = self._get_connection()
        try:
            c = conn.cursor()
            c.execute('''
                SELECT g.group_workspace_id
                FROM account_profiles p
                INNER JOIN account_groups g ON g.group_id = p.profile_group_id
                WHERE p.profile_id = ?
            ''', (profile_id,))
            row = c.fetchone()
            return row[0] if row else None
        finally:
            if owns_connection:
                conn.close()
    
    def _build_workspace_metadata(self, workspace_id: int, conn=None) -> Optional[Dict[str, Any]]:
        """Build a full workspace metadata snapshot from database state."""
        owns_connection = conn is None
        if owns_connection:
            conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_workspaces WHERE workspace_id = ?', (workspace_id,))
            workspace_row = c.fetchone()
            if not workspace_row:
                return None
            workspace = dict(workspace_row)
            workspace_root_path = workspace.get('workspace_root_profile_path', '')
            workspace_metadata_path = self.get_workspace_metadata_path(workspace_root_path)
    
            c.execute('''
                SELECT *
                FROM account_groups
                WHERE group_workspace_id = ?
                ORDER BY group_order_index, group_created_at, group_id
            ''', (workspace_id,))
            group_rows = [dict(row) for row in c.fetchall()]
            group_ids = [group['group_id'] for group in group_rows]
    
            profiles_by_group = {group_id: [] for group_id in group_ids}
            profile_settings_map = {}
            if group_ids:
                placeholders = ','.join('?' for _ in group_ids)
                c.execute(f'''
                    SELECT *
                    FROM account_profiles
                    WHERE profile_group_id IN ({placeholders})
                    ORDER BY profile_group_id, profile_order_index, profile_created_at, profile_id
                ''', group_ids)
                profile_rows = [dict(row) for row in c.fetchall()]
                profile_ids = [profile['profile_id'] for profile in profile_rows]
    
                if profile_ids:
                    setting_placeholders = ','.join('?' for _ in profile_ids)
                    c.execute(f'''
                        SELECT setting_profile_id, setting_key, setting_value
                        FROM account_profile_settings
                        WHERE setting_profile_id IN ({setting_placeholders})
                        ORDER BY setting_profile_id, setting_key
                    ''', profile_ids)
                    for profile_id, setting_key, setting_value in c.fetchall():
                        profile_settings_map.setdefault(profile_id, {})[setting_key] = setting_value
    
                for profile in profile_rows:
                    profile_path = profile.get('profile_browser_profile_path', '')
                    profile_metadata_path = os.path.join(profile_path, self.PROFILE_METADATA_FILENAME) if profile_path else ''
                    profile_copy = dict(profile)
                    profile_copy['profile_settings'] = profile_settings_map.get(profile['profile_id'], {})
                    profile_copy['profile_metadata_path'] = profile_metadata_path
                    profiles_by_group.setdefault(profile['profile_group_id'], []).append(profile_copy)
    
            groups_payload = []
            for group in group_rows:
                group_copy = dict(group)
                group_copy['profiles'] = profiles_by_group.get(group['group_id'], [])
                groups_payload.append(group_copy)
    
            return {
                'metadata_type': 'account_manager_workspace',
                'metadata_version': 1,
                'workspace': workspace,
                'groups': groups_payload,
                'workspace_root_profile_path': workspace_root_path,
                'workspace_metadata_path': workspace_metadata_path,
                'exported_at': datetime.now().isoformat(),
            }
        finally:
            if owns_connection:
                conn.close()
    
    def sync_workspace_metadata(self, workspace_id: int, conn=None) -> bool:
        """Persist current workspace structure to workspace metadata JSON."""
        metadata = self._build_workspace_metadata(workspace_id, conn=conn)
        if not metadata:
            return False
        metadata_path = metadata.get('workspace_metadata_path') or self.get_workspace_metadata_path(
            metadata.get('workspace_root_profile_path', '')
        )
        if not metadata_path:
            return False
        return self._write_json_file(metadata_path, metadata)
    
    def delete_workspace_metadata_file(self, root_profile_path: str) -> bool:
        """Delete workspace metadata JSON from disk if it exists."""
        metadata_path = self.get_workspace_metadata_path(root_profile_path)
        if not metadata_path or not os.path.exists(metadata_path):
            return True
        try:
            os.remove(metadata_path)
            return True
        except Exception:
            return False
    
    def restore_workspace_from_metadata(self, root_profile_path: str) -> Dict[str, Any]:
        """Restore a workspace, groups, and profiles from workspace metadata on disk."""
        normalized_root_path = self._normalize_path(root_profile_path)
        if not normalized_root_path:
            return {
                'success': False,
                'workspace_id': None,
                'restored_group_count': 0,
                'restored_profile_count': 0,
                'error': 'Workspace root path is required'
            }
    
        existing_workspace = self.get_workspace_by_root_path(normalized_root_path)
        if existing_workspace:
            return {
                'success': False,
                'workspace_id': existing_workspace.get('workspace_id'),
                'restored_group_count': 0,
                'restored_profile_count': 0,
                'error': 'Workspace already exists'
            }
    
        metadata = self.load_workspace_metadata(normalized_root_path)
        if not metadata:
            return {
                'success': False,
                'workspace_id': None,
                'restored_group_count': 0,
                'restored_profile_count': 0,
                'error': 'Workspace metadata not found or invalid'
            }
    
        workspace_data = metadata.get('workspace') if isinstance(metadata.get('workspace'), dict) else {}
        groups_data = metadata.get('groups') if isinstance(metadata.get('groups'), list) else []
        now = datetime.now().isoformat()
    
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO account_workspaces
                (workspace_name, workspace_description, workspace_icon, workspace_color,
                 workspace_browser_exe_path, workspace_root_profile_path, workspace_browser_type,
                 workspace_created_at, workspace_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                workspace_data.get('workspace_name', os.path.basename(normalized_root_path) or 'Restored Workspace'),
                workspace_data.get('workspace_description', ''),
                workspace_data.get('workspace_icon', 'briefcase'),
                workspace_data.get('workspace_color', '#3b82f6'),
                workspace_data.get('workspace_browser_exe_path', ''),
                normalized_root_path,
                workspace_data.get('workspace_browser_type', 'chrome'),
                workspace_data.get('workspace_created_at', now),
                workspace_data.get('workspace_updated_at', now),
            ))
            workspace_id = c.lastrowid
    
            restored_group_count = 0
            restored_profile_count = 0
            for group_index, group_data in enumerate(groups_data):
                if not isinstance(group_data, dict):
                    continue
                c.execute('''
                    INSERT INTO account_groups
                    (group_workspace_id, group_name, group_description, group_icon,
                     group_color, group_order_index, group_created_at, group_updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    workspace_id,
                    group_data.get('group_name', f'Group {group_index + 1}'),
                    group_data.get('group_description', ''),
                    group_data.get('group_icon', 'fa6s.users'),
                    group_data.get('group_color', '#3b82f6'),
                    group_data.get('group_order_index', group_index),
                    group_data.get('group_created_at', now),
                    group_data.get('group_updated_at', now),
                ))
                new_group_id = c.lastrowid
                restored_group_count += 1
    
                group_profiles = group_data.get('profiles') if isinstance(group_data.get('profiles'), list) else []
                for profile_index, profile_entry in enumerate(group_profiles):
                    if not isinstance(profile_entry, dict):
                        continue
                    profile_path = self._normalize_path(
                        profile_entry.get('profile_browser_profile_path')
                        or os.path.join(
                            normalized_root_path,
                            profile_entry.get('profile_browser_profile_name', '')
                        )
                    )
                    profile_metadata = self.load_profile_metadata(profile_path) if profile_path else None
                    profile_data = profile_metadata if isinstance(profile_metadata, dict) else dict(profile_entry)
                    profile_settings = profile_data.get('profile_settings', {})
                    if not isinstance(profile_settings, dict):
                        profile_settings = {}
    
                    browser_profile_name = profile_data.get('profile_browser_profile_name')
                    if not browser_profile_name and profile_path:
                        browser_profile_name = os.path.basename(profile_path)
                    final_profile_path = profile_path or os.path.join(normalized_root_path, browser_profile_name or '')
    
                    c.execute('''
                        INSERT INTO account_profiles
                        (profile_group_id, profile_name, profile_description, profile_icon,
                         profile_color, profile_browser_profile_name, profile_browser_profile_path,
                         profile_order_index, profile_created_at, profile_updated_at,
                         profile_browser_type, profile_zip_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        new_group_id,
                        profile_data.get('profile_name', browser_profile_name or f'Profile {profile_index + 1}'),
                        profile_data.get('profile_description', ''),
                        profile_data.get('profile_icon', 'fa6s.user'),
                        profile_data.get('profile_color', '#3b82f6'),
                        browser_profile_name or f'profile_{profile_index + 1}',
                        final_profile_path,
                        profile_data.get('profile_order_index', profile_index),
                        profile_data.get('profile_created_at', now),
                        profile_data.get('profile_updated_at', now),
                        profile_data.get('profile_browser_type', workspace_data.get('workspace_browser_type', 'chrome')),
                        profile_data.get('profile_zip_name'),
                    ))
                    new_profile_id = c.lastrowid
                    restored_profile_count += 1
    
                    for setting_key, setting_value in profile_settings.items():
                        c.execute('''
                            INSERT INTO account_profile_settings
                            (setting_profile_id, setting_key, setting_value, setting_created_at, setting_updated_at)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(setting_profile_id, setting_key)
                            DO UPDATE SET setting_value = excluded.setting_value,
                                         setting_updated_at = excluded.setting_updated_at
                        ''', (new_profile_id, setting_key, str(setting_value), now, now))
    
            conn.commit()
            self.sync_workspace_metadata(workspace_id, conn=conn)
            return {
                'success': True,
                'workspace_id': workspace_id,
                'restored_group_count': restored_group_count,
                'restored_profile_count': restored_profile_count,
                'error': None
            }
    
    def _collect_workspace_profiles(self, workspace_id: int, conn=None) -> List[Dict[str, Any]]:
        """Collect all profiles belonging to a workspace."""
        owns_connection = conn is None
        if owns_connection:
            conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT p.*
                FROM account_profiles p
                INNER JOIN account_groups g ON g.group_id = p.profile_group_id
                WHERE g.group_workspace_id = ?
                ORDER BY p.profile_id
            ''', (workspace_id,))
            rows = c.fetchall()
            return [dict(row) for row in rows]
        finally:
            if owns_connection:
                conn.close()
    
    def _collect_group_profiles(self, group_id: int, conn=None) -> List[Dict[str, Any]]:
        """Collect all profiles belonging to a group."""
        owns_connection = conn is None
        if owns_connection:
            conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT *
                FROM account_profiles
                WHERE profile_group_id = ?
                ORDER BY profile_id
            ''', (group_id,))
            rows = c.fetchall()
            return [dict(row) for row in rows]
        finally:
            if owns_connection:
                conn.close()
    
    def _delete_profile_folders(self, profiles: List[Dict[str, Any]]) -> List[str]:
        """Delete profile folders and return warnings for failures."""
        warnings = []
        deleted_paths = set()
        
        for profile in profiles:
            profile_name = profile.get('profile_name', f"Profile {profile.get('profile_id', '')}")
            profile_path = (profile.get('profile_browser_profile_path') or '').strip()
            
            if not profile_path or profile_path in deleted_paths or not os.path.exists(profile_path):
                continue
            
            try:
                shutil.rmtree(profile_path)
                deleted_paths.add(profile_path)
            except Exception as e:
                warnings.append(f'{profile_name}: Could not delete profile folder: {e}')
        
        return warnings
    
    # ========== Workspace Operations ==========
    
    def create_workspace(self, name: str, description: str = "", icon: str = "fa6s.briefcase", 
                         color: str = "#3b82f6", browser_exe_path: str = "", 
                         root_profile_path: str = "", browser_type: str = "chrome") -> int:
        """Create new workspace and return workspace_id"""
        normalized_root = self._normalize_path(root_profile_path)
        with self._get_connection() as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute('''
                INSERT INTO account_workspaces 
                (workspace_name, workspace_description, workspace_icon, workspace_color, 
                 workspace_browser_exe_path, workspace_root_profile_path, workspace_browser_type,
                 workspace_created_at, workspace_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, icon, color, browser_exe_path, normalized_root, browser_type, now, now))
            workspace_id = c.lastrowid
            conn.commit()
            self.sync_workspace_metadata(workspace_id, conn=conn)
            return workspace_id
    
    def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get all workspaces"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_workspaces ORDER BY workspace_created_at DESC')
            rows = c.fetchall()
            return [dict(row) for row in rows]
    
    def get_workspace(self, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get single workspace by ID"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_workspaces WHERE workspace_id = ?', (workspace_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def update_workspace(self, workspace_id: int, name: str = None, description: str = None,
                        icon: str = None, color: str = None, browser_exe_path: str = None,
                        root_profile_path: str = None, browser_type: str = None) -> bool:
        """Update workspace fields (only provided fields are updated)"""
        with self._get_connection() as conn:
            existing_workspace = self.get_workspace(workspace_id)
            if not existing_workspace:
                return False
            old_root_path = existing_workspace.get('workspace_root_profile_path', '')
            c = conn.cursor()
            updates = []
            params = []
            
            if name is not None:
                updates.append('workspace_name = ?')
                params.append(name)
            if description is not None:
                updates.append('workspace_description = ?')
                params.append(description)
            if icon is not None:
                updates.append('workspace_icon = ?')
                params.append(icon)
            if color is not None:
                updates.append('workspace_color = ?')
                params.append(color)
            if browser_exe_path is not None:
                updates.append('workspace_browser_exe_path = ?')
                params.append(browser_exe_path)
            if root_profile_path is not None:
                updates.append('workspace_root_profile_path = ?')
                params.append(self._normalize_path(root_profile_path))
            if browser_type is not None:
                updates.append('workspace_browser_type = ?')
                params.append(browser_type)
            
            if not updates:
                return False
            
            updates.append('workspace_updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(workspace_id)
            
            query = f"UPDATE account_workspaces SET {', '.join(updates)} WHERE workspace_id = ?"
            c.execute(query, params)
            conn.commit()
            updated = c.rowcount > 0
            if updated:
                updated_workspace = self.get_workspace(workspace_id)
                new_root_path = updated_workspace.get('workspace_root_profile_path', '') if updated_workspace else ''
                if self._normalize_path(old_root_path) != self._normalize_path(new_root_path):
                    self.delete_workspace_metadata_file(old_root_path)
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return updated
    
    def delete_workspace(self, workspace_id: int) -> Dict[str, Any]:
        """Delete workspace, all nested profiles, and their folders."""
        with self._get_connection() as conn:
            workspace = self.get_workspace(workspace_id)
            if not workspace:
                return {
                    'success': False,
                    'deleted': False,
                    'warnings': [],
                    'deleted_profile_count': 0,
                    'deleted_group_count': 0,
                    'error': 'Workspace not found'
                }
            
            workspace_root_path = workspace.get('workspace_root_profile_path', '')
            groups = self.get_groups_by_workspace(workspace_id)
            profiles = self._collect_workspace_profiles(workspace_id, conn)
            warnings = self._delete_profile_folders(profiles)
            c = conn.cursor()
            c.execute('DELETE FROM account_workspaces WHERE workspace_id = ?', (workspace_id,))
            deleted = c.rowcount > 0
            conn.commit()
            if deleted and not self.delete_workspace_metadata_file(workspace_root_path):
                warnings.append(f'Workspace metadata could not be deleted: {self.get_workspace_metadata_path(workspace_root_path)}')
            return {
                'success': deleted,
                'deleted': deleted,
                'warnings': warnings,
                'deleted_profile_count': len(profiles),
                'deleted_group_count': len(groups),
                'error': None if deleted else 'Workspace delete failed'
            }
    
    # ========== Group Operations ==========
    
    def create_group(self, workspace_id: int, name: str, description: str = "",
                     icon: str = "fa6s.users", color: str = "#3b82f6",
                     order_index: int = 0) -> int:
        """Create new group and return group_id"""
        with self._get_connection() as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute('''
                INSERT INTO account_groups 
                (group_workspace_id, group_name, group_description, group_icon, 
                 group_color, group_order_index, group_created_at, group_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (workspace_id, name, description, icon, color, order_index, now, now))
            group_id = c.lastrowid
            conn.commit()
            self.sync_workspace_metadata(workspace_id, conn=conn)
            return group_id
    
    def get_groups_by_workspace(self, workspace_id: int) -> List[Dict[str, Any]]:
        """Get all groups for a workspace ordered by order_index"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT * FROM account_groups 
                WHERE group_workspace_id = ? 
                ORDER BY group_order_index, group_created_at
            ''', (workspace_id,))
            rows = c.fetchall()
            return [dict(row) for row in rows]
    
    def get_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """Get single group by ID"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_groups WHERE group_id = ?', (group_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def update_group(self, group_id: int, name: str = None, description: str = None,
                     icon: str = None, color: str = None, order_index: int = None) -> bool:
        """Update group fields (only provided fields are updated)"""
        with self._get_connection() as conn:
            workspace_id = self._get_workspace_id_by_group_id(group_id, conn=conn)
            c = conn.cursor()
            updates = []
            params = []
            
            if name is not None:
                updates.append('group_name = ?')
                params.append(name)
            if description is not None:
                updates.append('group_description = ?')
                params.append(description)
            if icon is not None:
                updates.append('group_icon = ?')
                params.append(icon)
            if color is not None:
                updates.append('group_color = ?')
                params.append(color)
            if order_index is not None:
                updates.append('group_order_index = ?')
                params.append(order_index)
            
            if not updates:
                return False
            
            updates.append('group_updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(group_id)
            
            query = f"UPDATE account_groups SET {', '.join(updates)} WHERE group_id = ?"
            c.execute(query, params)
            conn.commit()
            updated = c.rowcount > 0
            if updated and workspace_id:
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return updated
    
    def delete_group(self, group_id: int) -> Dict[str, Any]:
        """Delete group, nested profiles, and their folders."""
        with self._get_connection() as conn:
            group = self.get_group(group_id)
            if not group:
                return {
                    'success': False,
                    'deleted': False,
                    'warnings': [],
                    'deleted_profile_count': 0,
                    'error': 'Group not found'
                }
            
            workspace_id = group.get('group_workspace_id')
            profiles = self._collect_group_profiles(group_id, conn)
            warnings = self._delete_profile_folders(profiles)
            c = conn.cursor()
            c.execute('DELETE FROM account_groups WHERE group_id = ?', (group_id,))
            deleted = c.rowcount > 0
            conn.commit()
            if deleted and workspace_id:
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return {
                'success': deleted,
                'deleted': deleted,
                'warnings': warnings,
                'deleted_profile_count': len(profiles),
                'error': None if deleted else 'Group delete failed'
            }
    
    def reorder_groups(self, group_updates: List[Dict[str, int]]) -> bool:
        """Update order_index for multiple groups. group_updates format: [{'group_id': 1, 'order_index': 0}, ...]"""
        with self._get_connection() as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            workspace_ids = set()
            for update in group_updates:
                group_id = update['group_id']
                workspace_id = self._get_workspace_id_by_group_id(group_id, conn=conn)
                if workspace_id:
                    workspace_ids.add(workspace_id)
                c.execute('''
                    UPDATE account_groups 
                    SET group_order_index = ?, group_updated_at = ?
                    WHERE group_id = ?
                ''', (update['order_index'], now, group_id))
            conn.commit()
            for workspace_id in workspace_ids:
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return True
    
    def get_all_groups(self) -> List[Dict[str, Any]]:
        """Get all groups"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_groups ORDER BY group_order_index, group_created_at')
            rows = c.fetchall()
            return [dict(row) for row in rows]
    
    # ========== Profile Operations ==========
    
    def create_profile(self, group_id: int, name: str, description: str = "",
                       icon: str = "fa6s.user", color: str = "#3b82f6",
                       browser_profile_name: str = "", browser_profile_path: str = "",
                       order_index: Optional[int] = None, browser_type: str = "chrome", zip_name: str = None) -> int:
        """Create new profile and return profile_id"""
        normalized_profile_path = self._normalize_path(browser_profile_path)
        with self._get_connection() as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            if order_index is None:
                c.execute('SELECT COALESCE(MAX(profile_order_index), -1) + 1 FROM account_profiles WHERE profile_group_id = ?', (group_id,))
                order_index = c.fetchone()[0]
            c.execute('''
                INSERT INTO account_profiles 
                (profile_group_id, profile_name, profile_description, profile_icon, 
                 profile_color, profile_browser_profile_name, profile_browser_profile_path,
                 profile_order_index, profile_created_at, profile_updated_at, 
                 profile_browser_type, profile_zip_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (group_id, name, description, icon, color, browser_profile_name, 
                  normalized_profile_path, order_index, now, now, browser_type, zip_name))
            profile_id = c.lastrowid
            conn.commit()
            workspace_id = self._get_workspace_id_by_group_id(group_id, conn=conn)
            if workspace_id:
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return profile_id
    
    def get_profiles_by_group(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all profiles for a group ordered by order_index"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT * FROM account_profiles 
                WHERE profile_group_id = ? 
                ORDER BY profile_order_index, profile_created_at
            ''', (group_id,))
            rows = c.fetchall()
            return [dict(row) for row in rows]
    
    def get_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get single profile by ID"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_profiles WHERE profile_id = ?', (profile_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all profiles"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_profiles ORDER BY profile_order_index, profile_created_at')
            rows = c.fetchall()
            return [dict(row) for row in rows]
    
    def update_profile(self, profile_id: int, name: str = None, description: str = None,
                       icon: str = None, color: str = None, browser_profile_name: str = None,
                       browser_profile_path: str = None, order_index: int = None,
                       browser_type: str = None, zip_name: str = None) -> bool:
        """Update profile fields (only provided fields are updated)"""
        with self._get_connection() as conn:
            workspace_id = self._get_workspace_id_by_profile_id(profile_id, conn=conn)
            c = conn.cursor()
            updates = []
            params = []
            
            if name is not None:
                updates.append('profile_name = ?')
                params.append(name)
            if description is not None:
                updates.append('profile_description = ?')
                params.append(description)
            if icon is not None:
                updates.append('profile_icon = ?')
                params.append(icon)
            if color is not None:
                updates.append('profile_color = ?')
                params.append(color)
            if browser_profile_name is not None:
                updates.append('profile_browser_profile_name = ?')
                params.append(browser_profile_name)
            if browser_profile_path is not None:
                updates.append('profile_browser_profile_path = ?')
                params.append(self._normalize_path(browser_profile_path))
            if order_index is not None:
                updates.append('profile_order_index = ?')
                params.append(order_index)
            if browser_type is not None:
                updates.append('profile_browser_type = ?')
                params.append(browser_type)
            if zip_name is not None:
                updates.append('profile_zip_name = ?')
                params.append(zip_name)
            
            if not updates:
                return False
            
            updates.append('profile_updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(profile_id)
            
            query = f"UPDATE account_profiles SET {', '.join(updates)} WHERE profile_id = ?"
            c.execute(query, params)
            conn.commit()
            updated = c.rowcount > 0
            if updated and workspace_id:
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return updated
    
    def delete_profile(self, profile_id: int) -> bool:
        """Delete profile (cascade deletes settings)"""
        with self._get_connection() as conn:
            workspace_id = self._get_workspace_id_by_profile_id(profile_id, conn=conn)
            c = conn.cursor()
            c.execute('DELETE FROM account_profiles WHERE profile_id = ?', (profile_id,))
            conn.commit()
            deleted = c.rowcount > 0
            if deleted and workspace_id:
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return deleted
    
    def save_profile_metadata(self, profile_data: Dict[str, Any]) -> bool:
        """Save profile metadata to JSON file in profile folder"""
        profile_path = self._normalize_path(profile_data.get('profile_browser_profile_path', ''))
        if not profile_path:
            return False
        
        metadata = {
            'profile_id': profile_data.get('profile_id'),
            'profile_name': profile_data.get('profile_name', ''),
            'profile_description': profile_data.get('profile_description', ''),
            'profile_icon': profile_data.get('profile_icon', 'fa6s.user'),
            'profile_color': profile_data.get('profile_color', '#3b82f6'),
            'profile_browser_profile_name': profile_data.get('profile_browser_profile_name', ''),
            'profile_browser_profile_path': profile_path,
            'group_id': profile_data.get('profile_group_id') or profile_data.get('group_id'),
            'profile_order_index': profile_data.get('profile_order_index', 0),
            'profile_created_at': profile_data.get('profile_created_at'),
            'profile_updated_at': profile_data.get('profile_updated_at'),
            'profile_browser_type': profile_data.get('profile_browser_type', 'chrome'),
            'profile_settings': profile_data.get('profile_settings', {}),
        }
        metadata_path = os.path.join(profile_path, self.PROFILE_METADATA_FILENAME)
        return self._write_json_file(metadata_path, metadata)
    
    def load_profile_metadata(self, profile_path: str) -> Optional[Dict[str, Any]]:
        """Load profile metadata from JSON file if exists"""
        normalized_profile_path = self._normalize_path(profile_path)
        metadata_path = os.path.join(normalized_profile_path, self.PROFILE_METADATA_FILENAME)
        return self._load_json_file(metadata_path)
    
    def reorder_profiles(self, profile_updates: List[Dict[str, int]]) -> bool:
        """Update order_index for multiple profiles. profile_updates format: [{'profile_id': 1, 'order_index': 0}, ...]"""
        with self._get_connection() as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            workspace_ids = set()
            for update in profile_updates:
                profile_id = update['profile_id']
                workspace_id = self._get_workspace_id_by_profile_id(profile_id, conn=conn)
                if workspace_id:
                    workspace_ids.add(workspace_id)
                c.execute('''
                    UPDATE account_profiles 
                    SET profile_order_index = ?, profile_updated_at = ?
                    WHERE profile_id = ?
                ''', (update['order_index'], now, profile_id))
            conn.commit()
            for workspace_id in workspace_ids:
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return True
    
    # ========== Profile Settings Operations ==========
    
    def set_profile_setting(self, profile_id: int, key: str, value: str) -> bool:
        """Set or update a profile setting"""
        with self._get_connection() as conn:
            workspace_id = self._get_workspace_id_by_profile_id(profile_id, conn=conn)
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute('''
                INSERT INTO account_profile_settings 
                (setting_profile_id, setting_key, setting_value, setting_created_at, setting_updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(setting_profile_id, setting_key) 
                DO UPDATE SET setting_value = excluded.setting_value, 
                             setting_updated_at = excluded.setting_updated_at
            ''', (profile_id, key, value, now, now))
            conn.commit()
            if workspace_id:
                self.sync_workspace_metadata(workspace_id, conn=conn)
            return True
    
    def get_profile_settings(self, profile_id: int) -> Dict[str, str]:
        """Get all settings for a profile as key-value dict"""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT setting_key, setting_value 
                FROM account_profile_settings 
                WHERE setting_profile_id = ?
            ''', (profile_id,))
            rows = c.fetchall()
            return {row[0]: row[1] for row in rows}
    
    def get_profile_setting(self, profile_id: int, key: str) -> Optional[str]:
        """Get single profile setting value"""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT setting_value 
                FROM account_profile_settings 
                WHERE setting_profile_id = ? AND setting_key = ?
            ''', (profile_id, key))
            row = c.fetchone()
            return row[0] if row else None
