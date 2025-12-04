import os
import json
import sqlite3
from datetime import datetime
from config import BASE_PATH
from database.db_backups_manager import DBBackupsManager

class DBMigrationManager:
    def __init__(self):
        self.config_path = os.path.join(BASE_PATH, 'configs', 'db_config.json')
        self._load_config()
        self.backup_manager = DBBackupsManager()
        self._ensure_migration_table()
    
    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.db_path = os.path.join(BASE_PATH, config['db_path'])
        self.migrations_folder = os.path.join(BASE_PATH, config['migrations_folder'])
        self.auto_backup = config.get('auto_backup_on_migration', True)
    
    def _ensure_db_folder(self):
        db_folder = os.path.dirname(self.db_path)
        if not os.path.exists(db_folder):
            os.makedirs(db_folder)
    
    def _ensure_migration_table(self):
        self._ensure_db_folder()
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()
    
    def _get_applied_migrations(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT migration_name FROM schema_migrations ORDER BY migration_name')
            return [row[0] for row in c.fetchall()]
    
    def _get_pending_migrations(self):
        if not os.path.exists(self.migrations_folder):
            return []
        
        applied = set(self._get_applied_migrations())
        all_migrations = []
        
        for filename in os.listdir(self.migrations_folder):
            if filename.endswith('.sql'):
                migration_name = filename[:-4]
                if migration_name not in applied:
                    all_migrations.append(filename)
        
        all_migrations.sort()
        return all_migrations
    
    def _execute_migration(self, migration_file):
        migration_path = os.path.join(self.migrations_folder, migration_file)
        migration_name = migration_file[:-4]
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        if self.auto_backup:
            print(f"Creating backup before running migration: {migration_name}")
            self.backup_manager.create_migration_backup(migration_name)
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            try:
                c.executescript(sql_content)
                
                c.execute('INSERT INTO schema_migrations (migration_name) VALUES (?)', 
                         (migration_name,))
                conn.commit()
                
                print(f"Migration executed successfully: {migration_name}")
                return True
                
            except Exception as e:
                print(f"Error executing migration {migration_name}: {e}")
                conn.rollback()
                return False
    
    def run_migrations(self):
        pending = self._get_pending_migrations()
        if not pending:
            return True
        print(f"Found {len(pending)} migration(s) to execute:")
        for migration in pending:
            print(f"  - {migration}")
        success_count = 0
        for migration_file in pending:
            if self._execute_migration(migration_file):
                success_count += 1
            else:
                print(f"Migration stopped due to error in: {migration_file}")
                break
        print(f"\nTotal {success_count} of {len(pending)} migration(s) executed successfully")
        if self.auto_backup:
            self.backup_manager.cleanup_old_backups()
        return success_count == len(pending)
    
    def get_migration_status(self):
        applied = self._get_applied_migrations()
        pending = self._get_pending_migrations()
        
        return {
            'applied': applied,
            'pending': pending,
            'total_applied': len(applied),
            'total_pending': len(pending)
        }
    
    def initialize_database(self):
        if os.path.exists(self.db_path):
            pending = self._get_pending_migrations()
            if pending:
                print(f"Database already exists at: {self.db_path}")
            return self.run_migrations()
        print("Creating new database and running all migrations...")
        self._ensure_db_folder()
        return self.run_migrations()
