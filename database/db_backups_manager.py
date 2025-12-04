import os
import json
import sqlite3
import shutil
from datetime import datetime, timedelta
from config import BASE_PATH

class DBBackupsManager:
    def __init__(self):
        self.config_path = os.path.join(BASE_PATH, 'configs', 'db_config.json')
        self._load_config()
        self._ensure_backup_folder()
    
    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.db_path = os.path.join(BASE_PATH, config['db_path'])
        self.backups_folder = os.path.join(BASE_PATH, config['backups_folder'])
        self.retention_days = config.get('backup_retention_days', 30)
    
    def _ensure_backup_folder(self):
        if not os.path.exists(self.backups_folder):
            os.makedirs(self.backups_folder)
    
    def create_backup(self, reason='manual'):
        if not os.path.exists(self.db_path):
            print(f"Database not found at {self.db_path}, skipping backup")
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}_{reason}.db"
        backup_path = os.path.join(self.backups_folder, backup_filename)
        
        try:
            shutil.copy2(self.db_path, backup_path)
            print(f"Database backup created successfully: {backup_filename}")
            return backup_path
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    def create_migration_backup(self, migration_name):
        return self.create_backup(f"migration_{migration_name}")
    
    def list_backups(self):
        if not os.path.exists(self.backups_folder):
            return []
        
        backups = []
        for filename in os.listdir(self.backups_folder):
            if filename.endswith('.db'):
                filepath = os.path.join(self.backups_folder, filename)
                stat = os.stat(filepath)
                backups.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime)
                })
        
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups
    
    def restore_backup(self, backup_filename):
        backup_path = os.path.join(self.backups_folder, backup_filename)
        
        if not os.path.exists(backup_path):
            print(f"Backup not found: {backup_filename}")
            return False
        
        try:
            self.create_backup('before_restore')
            
            shutil.copy2(backup_path, self.db_path)
            print(f"Database restored successfully from: {backup_filename}")
            return True
        except Exception as e:
            print(f"Error restoring backup: {e}")
            return False
    
    def cleanup_old_backups(self):
        if self.retention_days <= 0:
            return
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        backups = self.list_backups()
        
        deleted_count = 0
        for backup in backups:
            if backup['created'] < cutoff_date:
                try:
                    os.remove(backup['filepath'])
                    print(f"Old backup deleted: {backup['filename']}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting backup {backup['filename']}: {e}")
        
        if deleted_count > 0:
            print(f"Total {deleted_count} old backups deleted successfully")
    
    def delete_backup(self, backup_filename):
        backup_path = os.path.join(self.backups_folder, backup_filename)
        
        if not os.path.exists(backup_path):
            print(f"Backup not found: {backup_filename}")
            return False
        
        try:
            os.remove(backup_path)
            print(f"Backup deleted successfully: {backup_filename}")
            return True
        except Exception as e:
            print(f"Error deleting backup: {e}")
            return False
