import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from database.db_operation import get_db_path


class AccountManagerDB:
    """Database operations for Account Manager (workspace > group > profile hierarchy)"""
    
    def __init__(self):
        self.db_path = get_db_path()
    
    # ========== Workspace Operations ==========
    
    def create_workspace(self, name: str, description: str = "", icon: str = "fa6s.briefcase", 
                        color: str = "#3b82f6", browser_exe_path: str = "", 
                        root_profile_path: str = "") -> int:
        """Create new workspace and return workspace_id"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute('''
                INSERT INTO account_workspaces 
                (workspace_name, workspace_description, workspace_icon, workspace_color, 
                 workspace_browser_exe_path, workspace_root_profile_path, 
                 workspace_created_at, workspace_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, icon, color, browser_exe_path, root_profile_path, now, now))
            conn.commit()
            return c.lastrowid
    
    def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get all workspaces"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_workspaces ORDER BY workspace_created_at DESC')
            rows = c.fetchall()
            return [dict(row) for row in rows]
    
    def get_workspace(self, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get single workspace by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_workspaces WHERE workspace_id = ?', (workspace_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def update_workspace(self, workspace_id: int, name: str = None, description: str = None,
                        icon: str = None, color: str = None, browser_exe_path: str = None,
                        root_profile_path: str = None) -> bool:
        """Update workspace fields (only provided fields are updated)"""
        with sqlite3.connect(self.db_path) as conn:
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
            
            if not updates:
                return False
            
            updates.append('workspace_updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(workspace_id)
            
            query = f"UPDATE account_workspaces SET {', '.join(updates)} WHERE workspace_id = ?"
            c.execute(query, params)
            conn.commit()
            return c.rowcount > 0
    
    def delete_workspace(self, workspace_id: int) -> bool:
        """Delete workspace (cascade deletes groups and profiles)"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM account_workspaces WHERE workspace_id = ?', (workspace_id,))
            conn.commit()
            return c.rowcount > 0
    
    # ========== Group Operations ==========
    
    def create_group(self, workspace_id: int, name: str, description: str = "",
                    icon: str = "fa6s.users", color: str = "#3b82f6",
                    order_index: int = 0) -> int:
        """Create new group and return group_id"""
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_groups WHERE group_id = ?', (group_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def update_group(self, group_id: int, name: str = None, description: str = None,
                    icon: str = None, color: str = None, order_index: int = None) -> bool:
        """Update group fields (only provided fields are updated)"""
        with sqlite3.connect(self.db_path) as conn:
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
    
    def delete_group(self, group_id: int) -> bool:
        """Delete group (cascade deletes profiles)"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM account_groups WHERE group_id = ?', (group_id,))
            conn.commit()
            return c.rowcount > 0
    
    def reorder_groups(self, group_updates: List[Dict[str, int]]) -> bool:
        """Update order_index for multiple groups. group_updates format: [{'group_id': 1, 'order_index': 0}, ...]"""
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_groups ORDER BY group_order_index, group_created_at')
            rows = c.fetchall()
            return [dict(row) for row in rows]
    
    # ========== Profile Operations ==========
    
    def create_profile(self, group_id: int, name: str, description: str = "",
                      icon: str = "fa6s.user", color: str = "#3b82f6",
                      browser_profile_name: str = "", browser_profile_path: str = "",
                      order_index: int = 0) -> int:
        """Create new profile and return profile_id"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute('''
                INSERT INTO account_profiles 
                (profile_group_id, profile_name, profile_description, profile_icon, 
                 profile_color, profile_browser_profile_name, profile_browser_profile_path,
                 profile_order_index, profile_created_at, profile_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (group_id, name, description, icon, color, browser_profile_name, 
                  browser_profile_path, order_index, now, now))
            conn.commit()
            return c.lastrowid
    
    def get_profiles_by_group(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all profiles for a group ordered by order_index"""
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_profiles WHERE profile_id = ?', (profile_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all profiles"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM account_profiles ORDER BY profile_order_index, profile_created_at')
            rows = c.fetchall()
            return [dict(row) for row in rows]
    
    def update_profile(self, profile_id: int, name: str = None, description: str = None,
                      icon: str = None, color: str = None, browser_profile_name: str = None,
                      browser_profile_path: str = None, order_index: int = None) -> bool:
        """Update profile fields (only provided fields are updated)"""
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM account_profiles WHERE profile_id = ?', (profile_id,))
            conn.commit()
            return c.rowcount > 0
    
    def save_profile_metadata(self, profile_data: Dict[str, Any]) -> bool:
        """Save profile metadata to JSON file in profile folder"""
        import os
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
                'group_id': profile_data.get('profile_group_id'),
                'profile_order_index': profile_data.get('profile_order_index', 0),
                'profile_created_at': profile_data.get('profile_created_at'),
                'profile_updated_at': profile_data.get('profile_updated_at'),
            }
            metadata_path = os.path.join(profile_path, 'account_management_profile_metadata.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            return True
        except Exception:
            return False

    def load_profile_metadata(self, profile_path: str) -> Optional[Dict[str, Any]]:
        """Load profile metadata from JSON file if exists"""
        import os
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT setting_value 
                FROM account_profile_settings 
                WHERE setting_profile_id = ? AND setting_key = ?
            ''', (profile_id, key))
            row = c.fetchone()
            return row[0] if row else None
