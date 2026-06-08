import json
import os
import shutil
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from database.db_operation import get_db_path


class AccountManagerDB:
    """Database operations for Account Manager (workspace > group > profile hierarchy)"""
    
    def __init__(self):
        self.db_path = get_db_path()
    
    def _get_connection(self):
        """Create sqlite connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
    
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
        with self._get_connection() as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute('''
                INSERT INTO account_workspaces 
                (workspace_name, workspace_description, workspace_icon, workspace_color, 
                 workspace_browser_exe_path, workspace_root_profile_path, workspace_browser_type,
                 workspace_created_at, workspace_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, icon, color, browser_exe_path, root_profile_path, browser_type, now, now))
            conn.commit()
            return c.lastrowid
    
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
                params.append(root_profile_path)
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
            return c.rowcount > 0
    
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
            
            groups = self.get_groups_by_workspace(workspace_id)
            profiles = self._collect_workspace_profiles(workspace_id, conn)
            warnings = self._delete_profile_folders(profiles)
            c = conn.cursor()
            c.execute('DELETE FROM account_workspaces WHERE workspace_id = ?', (workspace_id,))
            deleted = c.rowcount > 0
            conn.commit()
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
            conn.commit()
            return c.lastrowid
    
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
            return c.rowcount > 0
    
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
            
            profiles = self._collect_group_profiles(group_id, conn)
            warnings = self._delete_profile_folders(profiles)
            c = conn.cursor()
            c.execute('DELETE FROM account_groups WHERE group_id = ?', (group_id,))
            deleted = c.rowcount > 0
            conn.commit()
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
            for update in group_updates:
                c.execute('''
                    UPDATE account_groups 
                    SET group_order_index = ?, group_updated_at = ?
                    WHERE group_id = ?
                ''', (update['order_index'], now, update['group_id']))
            conn.commit()
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
                       order_index: int = 0, browser_type: str = "chrome", zip_name: str = None) -> int:
        """Create new profile and return profile_id"""
        with self._get_connection() as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute('''
                INSERT INTO account_profiles 
                (profile_group_id, profile_name, profile_description, profile_icon, 
                 profile_color, profile_browser_profile_name, profile_browser_profile_path,
                 profile_order_index, profile_created_at, profile_updated_at, 
                 profile_browser_type, profile_zip_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (group_id, name, description, icon, color, browser_profile_name, 
                  browser_profile_path, order_index, now, now, browser_type, zip_name))
            conn.commit()
            return c.lastrowid
    
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
                params.append(browser_profile_path)
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
            return c.rowcount > 0
    
    def delete_profile(self, profile_id: int) -> bool:
        """Delete profile (cascade deletes settings)"""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM account_profiles WHERE profile_id = ?', (profile_id,))
            conn.commit()
            return c.rowcount > 0
    
    def save_profile_metadata(self, profile_data: Dict[str, Any]) -> bool:
        """Save profile metadata to JSON file in profile folder"""
        profile_path = profile_data.get('profile_browser_profile_path', '')
        if not profile_path:
            return False
        
        try:
            os.makedirs(profile_path, exist_ok=True)
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
            metadata_path = os.path.join(profile_path, 'account_management_profile_metadata.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            return True
        except Exception:
            return False
    
    def load_profile_metadata(self, profile_path: str) -> Optional[Dict[str, Any]]:
        """Load profile metadata from JSON file if exists"""
        metadata_path = os.path.join(profile_path, 'account_management_profile_metadata.json')
        if not os.path.exists(metadata_path):
            return None
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def reorder_profiles(self, profile_updates: List[Dict[str, int]]) -> bool:
        """Update order_index for multiple profiles. profile_updates format: [{'profile_id': 1, 'order_index': 0}, ...]"""
        with self._get_connection() as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            for update in profile_updates:
                c.execute('''
                    UPDATE account_profiles 
                    SET profile_order_index = ?, profile_updated_at = ?
                    WHERE profile_id = ?
                ''', (update['order_index'], now, update['profile_id']))
            conn.commit()
            return True
    
    # ========== Profile Settings Operations ==========
    
    def set_profile_setting(self, profile_id: int, key: str, value: str) -> bool:
        """Set or update a profile setting"""
        with self._get_connection() as conn:
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
