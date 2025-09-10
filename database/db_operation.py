import sqlite3
import json
from config import BASE_PATH
import os

DB_PATH = os.path.join(BASE_PATH, 'database', 'database.db')

class ImageTeaDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT,
                api_key TEXT,
                note TEXT,
                last_tested TEXT,
                status TEXT,
                model TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE,
                filename TEXT,
                title TEXT,
                description TEXT,
                tags TEXT,
                status TEXT,
                original_filename TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS api_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT,
                service TEXT,
                model TEXT,
                token_input INTEGER,
                token_output INTEGER,
                token_total INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS platform_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS files_type_assign (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                file_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(file_id) REFERENCES files(id)
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS category_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                platform_id INTEGER,
                category_id INTEGER,
                category_name TEXT,
                FOREIGN KEY(file_id) REFERENCES files(id),
                FOREIGN KEY(platform_id) REFERENCES platform_list(id)
            )''')
            conn.commit()

    def set_api_key(self, service, api_key, note=None, last_tested=None, status=None, model=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM api_keys WHERE service=? AND api_key=?', (service, api_key))
            row = c.fetchone()
            if row:
                c.execute('''UPDATE api_keys SET note=?, last_tested=?, status=?, model=? WHERE id=?''',
                          (note, last_tested, status, model, row[0]))
            else:
                c.execute('''INSERT INTO api_keys (service, api_key, note, last_tested, status, model)
                             VALUES (?, ?, ?, ?, ?, ?)''',
                          (service, api_key, note, last_tested, status, model))
            conn.commit()

    def get_api_key(self, service):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT api_key, note, last_tested, status, model FROM api_keys WHERE service=? ORDER BY id DESC LIMIT 1', (service,))
            row = c.fetchone()
            if row:
                return {
                    'api_key': row[0],
                    'note': row[1],
                    'last_tested': row[2],
                    'status': row[3],
                    'model': row[4]
                }
            return None

    def update_api_key_note(self, api_key, note):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE api_keys SET note=? WHERE api_key=?', (note, api_key))
            conn.commit()

    def update_api_key_last_tested(self, api_key, last_tested):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE api_keys SET last_tested=? WHERE api_key=?', (last_tested, api_key))
            conn.commit()

    def update_api_key_status(self, api_key, status):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE api_keys SET status=? WHERE api_key=?', (status, api_key))
            conn.commit()

    def update_api_key_model(self, api_key, model):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE api_keys SET model=? WHERE api_key=?', (model, api_key))
            conn.commit()

    def delete_api_key(self, service, api_key):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM api_keys WHERE service=? AND api_key=?', (service, api_key))
            conn.commit()

    def add_file(self, filepath, filename, title=None, description=None, tags=None, status=None, original_filename=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if original_filename is None:
                original_filename = filename
            c.execute('''INSERT OR IGNORE INTO files (filepath, filename, title, description, tags, status, original_filename) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (filepath, filename, title, description, tags, status, original_filename))
            conn.commit()

    def update_metadata(self, filepath, title, description, tags, status=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if status is not None:
                c.execute('''UPDATE files SET title=?, description=?, tags=?, status=? WHERE filepath=?''',
                          (title, description, tags, status, filepath))
            else:
                c.execute('''UPDATE files SET title=?, description=?, tags=? WHERE filepath=?''',
                          (title, description, tags, filepath))
            conn.commit()

    def update_file_status(self, filepath, status):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE files SET status=? WHERE filepath=?', (status, filepath))
            conn.commit()

    def delete_file(self, filepath):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM files WHERE filepath=?', (filepath,))
            conn.commit()

    def clear_files(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM files')
            file_ids = [row[0] for row in c.fetchall()]
            if file_ids:
                c.executemany('DELETE FROM category_mapping WHERE file_id=?', [(fid,) for fid in file_ids])
                c.executemany('DELETE FROM files_type_assign WHERE file_id=?', [(fid,) for fid in file_ids])
            c.execute('DELETE FROM files')
            conn.commit()

    def get_all_files(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id, filepath, filename, title, description, tags, status, original_filename FROM files')
            return c.fetchall()

    def get_files_count(self, search_text=None):
        """Get total count of files, optionally filtered by search"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if search_text and search_text.strip():
                search_pattern = f"%{search_text.strip()}%"
                c.execute('''SELECT COUNT(*) FROM files 
                           WHERE filepath LIKE ? OR filename LIKE ? OR title LIKE ? OR description LIKE ? OR tags LIKE ?''',
                         (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern))
            else:
                c.execute('SELECT COUNT(*) FROM files')
            row = c.fetchone()
            return row[0] if row else 0

    def get_files_paginated(self, page=1, page_size=20, search_text=None):
        """Get files with pagination support"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            offset = (page - 1) * page_size
            
            if search_text and search_text.strip():
                search_pattern = f"%{search_text.strip()}%"
                c.execute('''SELECT id, filepath, filename, title, description, tags, status, original_filename 
                           FROM files 
                           WHERE filepath LIKE ? OR filename LIKE ? OR title LIKE ? OR description LIKE ? OR tags LIKE ?
                           LIMIT ? OFFSET ?''',
                         (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, page_size, offset))
            else:
                c.execute('''SELECT id, filepath, filename, title, description, tags, status, original_filename 
                           FROM files 
                           LIMIT ? OFFSET ?''', (page_size, offset))
            return c.fetchall()

    def get_all_api_keys(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT service, api_key, note, last_tested, status, model FROM api_keys')
            return c.fetchall()

    def insert_api_token_stats(self, filepath, service, model, token_input, token_output, token_total):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO api_tokens (filepath, service, model, token_input, token_output, token_total)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (filepath, service, model, token_input, token_output, token_total))
            conn.commit()

    def get_token_stats_sum(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT SUM(token_input), SUM(token_output), SUM(token_total) FROM api_tokens')
            row = c.fetchone()
            if row:
                return tuple(x if x is not None else 0 for x in row)
            return (0, 0, 0)

    def update_file_path_and_name(self, old_filepath, new_filepath, new_filename):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE files SET filepath=?, filename=? WHERE filepath=?', (new_filepath, new_filename, old_filepath))
            conn.commit()

    def batch_update_file_paths(self, rename_results):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            for result in rename_results:
                old_filepath, old_filename, new_filename, new_filepath, success, error = result
                if success and new_filepath and new_filename:
                    # Check if original_filename is empty, if so save the old filename as original
                    c.execute('SELECT original_filename FROM files WHERE filepath=?', (old_filepath,))
                    row = c.fetchone()
                    if row and (not row[0] or row[0] == new_filename):
                        # Save original filename for first rename or if original was same as new
                        c.execute('UPDATE files SET filepath=?, filename=?, original_filename=? WHERE filepath=?', 
                                (new_filepath, new_filename, old_filename, old_filepath))
                    else:
                        # Keep existing original_filename
                        c.execute('UPDATE files SET filepath=?, filename=? WHERE filepath=?', 
                                (new_filepath, new_filename, old_filepath))
            conn.commit()

    def undo_rename(self, filepaths):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            for filepath in filepaths:
                c.execute('SELECT original_filename, filename, filepath FROM files WHERE filepath=? OR filename=?', (filepath, filepath))
                row = c.fetchone()
                if row:
                    original_filename, current_filename, current_filepath = row
                    
                    # Handle case where filepath/filename columns might be swapped
                    if current_filepath and os.path.exists(current_filepath):
                        actual_current_path = current_filepath
                    elif current_filename and os.path.exists(current_filename):
                        actual_current_path = current_filename
                    else:
                        continue
                    
                    # Skip if no original filename or same as current
                    if not original_filename or original_filename == os.path.basename(actual_current_path):
                        continue
                    
                    dirpath = os.path.dirname(actual_current_path)
                    original_filepath = os.path.join(dirpath, original_filename)
                    
                    if os.path.abspath(actual_current_path) == os.path.abspath(original_filepath):
                        continue
                        
                    if os.path.exists(original_filepath):
                        continue
                        
                    try:
                        os.rename(actual_current_path, original_filepath)
                        # Update database and clear original_filename since it's restored
                        c.execute('UPDATE files SET filepath=?, filename=?, original_filename=? WHERE filepath=? OR filename=?', 
                                (original_filepath, original_filename, original_filename, actual_current_path, actual_current_path))
                    except Exception as e:
                        pass
                else:
                    pass
            conn.commit()

    def clear_all_metadata(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE files SET title=NULL, description=NULL, tags=NULL, status="draft"')
            c.execute('DELETE FROM category_mapping WHERE file_id IN (SELECT id FROM files)')
            c.execute('DELETE FROM files_type_assign WHERE file_id IN (SELECT id FROM files)')
            conn.commit()

    def save_category_mapping(self, file_id, category_dict):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            for platform, category_id in category_dict.items():
                if platform == "shutterstock" and isinstance(category_id, dict):
                    for key in ["primary", "secondary"]:
                        cat_val = category_id.get(key)
                        if cat_val is not None:
                            c.execute('SELECT id FROM platform_list WHERE name=?', (platform,))
                            platform_row = c.fetchone()
                            if platform_row:
                                platform_id = platform_row[0]
                            else:
                                c.execute('INSERT INTO platform_list (name) VALUES (?)', (platform,))
                                platform_id = c.lastrowid
                            c.execute('SELECT id FROM category_mapping WHERE file_id=? AND platform_id=? AND category_id=?', (file_id, platform_id, cat_val))
                            mapping_row = c.fetchone()
                            cat_name = f"{cat_val} ({key})"
                            if mapping_row:
                                c.execute('UPDATE category_mapping SET category_id=?, category_name=? WHERE id=?',
                                          (cat_val, cat_name, mapping_row[0]))
                            else:
                                c.execute('INSERT INTO category_mapping (file_id, platform_id, category_id, category_name) VALUES (?, ?, ?, ?)',
                                          (file_id, platform_id, cat_val, cat_name))
                else:
                    c.execute('SELECT id FROM platform_list WHERE name=?', (platform,))
                    platform_row = c.fetchone()
                    if platform_row:
                        platform_id = platform_row[0]
                    else:
                        c.execute('INSERT INTO platform_list (name) VALUES (?)', (platform,))
                        platform_id = c.lastrowid
                    c.execute('SELECT id FROM category_mapping WHERE file_id=? AND platform_id=?', (file_id, platform_id))
                    mapping_row = c.fetchone()
                    if mapping_row:
                        c.execute('UPDATE category_mapping SET category_id=?, category_name=? WHERE id=?',
                                  (category_id, str(category_id), mapping_row[0]))
                    else:
                        c.execute('INSERT INTO category_mapping (file_id, platform_id, category_id, category_name) VALUES (?, ?, ?, ?)',
                                  (file_id, platform_id, category_id, str(category_id)))
            conn.commit()

    def get_category_maps(self):
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        shutterstock_map = config["shutterstock_category_map"]
        adobe_map = config["adobe_stock_category_map"]
        return shutterstock_map, adobe_map

    def get_category_mapping(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT file_id, platform_id, category_id, category_name FROM category_mapping')
            rows = c.fetchall()
            c.execute('SELECT id, name FROM platform_list')
            platform_map = {row[0]: row[1] for row in c.fetchall()}
            mapping = []
            for row in rows:
                mapping.append({
                    'file_id': row[0],
                    'platform': platform_map.get(row[1], ''),
                    'category_id': row[2],
                    'category_name': row[3]
                })
            return mapping

    def get_category_mapping_for_file(self, file_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT file_id, platform_id, category_id, category_name FROM category_mapping WHERE file_id=?', (file_id,))
            rows = c.fetchall()
            c.execute('SELECT id, name FROM platform_list')
            platform_map = {row[0]: row[1] for row in c.fetchall()}
            mapping = []
            for row in rows:
                mapping.append({
                    'file_id': row[0],
                    'platform': platform_map.get(row[1], ''),
                    'category_id': row[2],
                    'category_name': row[3]
                })
            return mapping

    def delete_all_api_tokens(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM api_tokens')
            conn.commit()

    def add_file_type(self, file_id, file_type):
        """Add a file type for a file (files_type_assign table). file_type should be 'Photo' or 'Illustration'."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO files_type_assign (file_id, file_type)
                         VALUES (?, ?)''', (file_id, file_type))
            conn.commit()

    def get_file_types(self, file_id):
        """Return all type records for a file_id (id, file_type, created_at)."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id, file_type, created_at FROM files_type_assign WHERE file_id=?', (file_id,))
            return c.fetchall()

    def delete_file_types_for_file(self, file_id):
        """Remove all type records for a given file_id."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM files_type_assign WHERE file_id=?', (file_id,))
            conn.commit()

    def clear_all_file_types(self):
        """Clear all file type assignments."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM files_type_assign')
            conn.commit()