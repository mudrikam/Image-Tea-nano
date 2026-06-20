import sqlite3
import json
from config import BASE_PATH
import os
import re
from database.db_migration_manager import DBMigrationManager

from ui.theme_system import theme

def sanitize_metadata_text(text, allow_commas=False):
    """
    Sanitize metadata text by removing special characters.
    Only allows: letters, numbers, spaces.
    For tags, also allows commas if allow_commas=True
    """
    if not text:
        return text
    
    if allow_commas:
        pattern = r'[^a-zA-Z0-9\s,]'
    else:
        pattern = r'[^a-zA-Z0-9\s]'
    
    sanitized = re.sub(pattern, '', text)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    return sanitized

def get_db_path():
    config_path = os.path.join(BASE_PATH, 'configs', 'db_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return os.path.join(BASE_PATH, config['db_path'])

DB_PATH = get_db_path()

class ImageTeaDB:
    def __init__(self):
        self.config_path = os.path.join(BASE_PATH, 'configs', 'db_config.json')
        self._load_config()
        self._ensure_database()
    
    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.db_path = os.path.join(BASE_PATH, config['db_path'])
    
    def _ensure_database(self):
        migration_manager = DBMigrationManager()
        migration_manager.initialize_database()

    def set_api_key(self, service, api_key, note=None, last_tested=None, status=None, model=None, provider_endpoint=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM api_keys WHERE service=? AND api_key=?', (service, api_key))
            row = c.fetchone()
            if row:
                c.execute('''UPDATE api_keys SET note=?, last_tested=?, status=?, model=?, provider_endpoint=? WHERE id=?''',
                          (note, last_tested, status, model, provider_endpoint, row[0]))
            else:
                c.execute('''INSERT INTO api_keys (service, api_key, note, last_tested, status, model, provider_endpoint)
                             VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (service, api_key, note, last_tested, status, model, provider_endpoint))
            conn.commit()

    def get_api_key(self, service):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT api_key, note, last_tested, status, model, provider_endpoint FROM api_keys WHERE service=? ORDER BY id DESC LIMIT 1', (service,))
            row = c.fetchone()
            if row:
                return {
                    'api_key': row[0],
                    'note': row[1],
                    'last_tested': row[2],
                    'status': row[3],
                    'model': row[4],
                    'provider_endpoint': row[5]
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

    def update_api_key_provider_endpoint(self, api_key, provider_endpoint):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE api_keys SET provider_endpoint=? WHERE api_key=?', (provider_endpoint, api_key))
            conn.commit()

    def delete_api_key(self, service, api_key):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM api_keys WHERE service=? AND api_key=?', (service, api_key))
            conn.commit()

    def delete_all_api_keys(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM api_keys')
            conn.commit()

    def add_file(self, filepath, filename, title=None, description=None, tags=None, status=None, original_filename=None):
        title_clean = sanitize_metadata_text(title, allow_commas=False) if title else title
        description_clean = sanitize_metadata_text(description, allow_commas=False) if description else description
        tags_clean = sanitize_metadata_text(tags, allow_commas=True) if tags else tags
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if original_filename is None:
                original_filename = filename
            c.execute('''INSERT OR IGNORE INTO files (filepath, filename, title, description, tags, status, original_filename) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (filepath, filename, title_clean, description_clean, tags_clean, status, original_filename))
            conn.commit()

    def update_metadata(self, filepath, title, description, tags, status=None):
        title_clean = sanitize_metadata_text(title, allow_commas=False) if title else title
        description_clean = sanitize_metadata_text(description, allow_commas=False) if description else description
        tags_clean = sanitize_metadata_text(tags, allow_commas=True) if tags else tags
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if status is not None:
                c.execute('''UPDATE files SET title=?, description=?, tags=?, status=? WHERE filepath=?''',
                          (title_clean, description_clean, tags_clean, status, filepath))
            else:
                c.execute('''UPDATE files SET title=?, description=?, tags=? WHERE filepath=?''',
                          (title_clean, description_clean, tags_clean, filepath))
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
    
    def clear_files_by_status(self, status):
        """Delete all files with specific status"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM files WHERE LOWER(status) = ?', (status.lower(),))
            file_ids = [row[0] for row in c.fetchall()]
            if file_ids:
                c.executemany('DELETE FROM category_mapping WHERE file_id=?', [(fid,) for fid in file_ids])
                c.executemany('DELETE FROM files_type_assign WHERE file_id=?', [(fid,) for fid in file_ids])
            c.execute('DELETE FROM files WHERE LOWER(status) = ?', (status.lower(),))
            conn.commit()
            return len(file_ids)

    def get_all_files(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id, filepath, filename, title, description, tags, status, original_filename FROM files ORDER BY filename COLLATE NOCASE ASC, filepath ASC')
            return c.fetchall()

    def get_file_by_path(self, filepath):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id, filepath, filename, title, description, tags, status, original_filename FROM files WHERE filepath=? LIMIT 1', (filepath,))
            return c.fetchone()

    def get_files_count(self, search_text=None, status_filter=None):
        """Get total count of files, optionally filtered by search and status"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            conditions = []
            params = []
            
            if search_text and search_text.strip():
                search_pattern = f"%{search_text.strip()}%"
                conditions.append('(filepath LIKE ? OR filename LIKE ? OR title LIKE ? OR description LIKE ? OR tags LIKE ?)')
                params.extend([search_pattern] * 5)
            
            if status_filter:
                conditions.append('LOWER(status) = ?')
                params.append(status_filter.lower())
            
            if conditions:
                query = f"SELECT COUNT(*) FROM files WHERE {' AND '.join(conditions)}"
                c.execute(query, params)
            else:
                c.execute('SELECT COUNT(*) FROM files')
            
            row = c.fetchone()
            return row[0] if row else 0

    def get_files_paginated(self, page=1, page_size=20, search_text=None, status_filter=None):
        """Get files with pagination support and optional status filter"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            offset = (page - 1) * page_size
            
            conditions = []
            params = []
            
            if search_text and search_text.strip():
                search_pattern = f"%{search_text.strip()}%"
                conditions.append('(filepath LIKE ? OR filename LIKE ? OR title LIKE ? OR description LIKE ? OR tags LIKE ?)')
                params.extend([search_pattern] * 5)
            
            if status_filter:
                conditions.append('LOWER(status) = ?')
                params.append(status_filter.lower())
            
            query = 'SELECT id, filepath, filename, title, description, tags, status, original_filename FROM files'
            if conditions:
                query += f" WHERE {' AND '.join(conditions)}"
            query += ' ORDER BY filename COLLATE NOCASE ASC, filepath ASC'
            query += ' LIMIT ? OFFSET ?'
            
            params.extend([page_size, offset])
            c.execute(query, params)
            return c.fetchall()

    def get_all_api_keys(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT service, api_key, note, last_tested, status, model, provider_endpoint FROM api_keys')
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
                c.execute('SELECT id FROM platform_list WHERE name=?', (platform,))
                platform_row = c.fetchone()
                if platform_row:
                    platform_id = platform_row[0]
                else:
                    c.execute('INSERT INTO platform_list (name) VALUES (?)', (platform,))
                    platform_id = c.lastrowid

                if platform == "shutterstock" and isinstance(category_id, dict):
                    c.execute('DELETE FROM category_mapping WHERE file_id=? AND platform_id=?', (file_id, platform_id))
                    for key in ["primary", "secondary"]:
                        cat_val = category_id.get(key)
                        if cat_val is not None:
                            cat_name = f"{cat_val} ({key})"
                            c.execute('INSERT INTO category_mapping (file_id, platform_id, category_id, category_name) VALUES (?, ?, ?, ?)',
                                      (file_id, platform_id, cat_val, cat_name))
                else:
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
        shutterstock_image_map = config["shutterstock_category_map"]
        shutterstock_video_map = config.get("shutterstock_video_category_map", {})
        adobe_map = config["adobe_stock_category_map"]
        return shutterstock_image_map, shutterstock_video_map, adobe_map

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

    # --- Generated prompts helpers ---
    def add_generated_prompt(self, file_id, prompt):
        """Insert a generated prompt for a file."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO generated_prompts (file_id, prompt) VALUES (?, ?)''', (file_id, prompt))
            conn.commit()
    
    def add_external_prompt(self, prompt):
        """Insert a generated prompt without file association (for external imports)."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO generated_prompts (file_id, prompt) VALUES (NULL, ?)''', (prompt,))
            conn.commit()
            return c.lastrowid

    def get_generated_prompts_for_file(self, file_id):
        """Return all generated prompts for a given file_id ordered by created_at desc."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id, file_id, prompt, created_at FROM generated_prompts WHERE file_id=? ORDER BY created_at DESC', (file_id,))
            return c.fetchall()

    def get_all_generated_prompts(self):
        """Return all generated prompts (id, file_id, prompt, created_at)."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT id, file_id, prompt, created_at FROM generated_prompts ORDER BY id DESC')
            return c.fetchall()

    def delete_generated_prompts_for_file(self, file_id):
        """Delete all generated prompts for a given file_id."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM generated_prompts WHERE file_id=?', (file_id,))
            conn.commit()
    
    def clear_all_generated_prompts(self):
        """Delete all generated prompts."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM generated_prompt_status')
            c.execute('DELETE FROM generated_prompts')
            conn.commit()
    
    def clear_copied_prompts(self):
        """Delete generated prompts that have status 'copied'."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT prompt_id FROM generated_prompt_status WHERE status = 'copied'")
            copied_prompt_ids = [row[0] for row in c.fetchall()]
            
            if copied_prompt_ids:
                c.execute("DELETE FROM generated_prompt_status WHERE status = 'copied'")
                placeholders = ','.join('?' * len(copied_prompt_ids))
                c.execute(f"DELETE FROM generated_prompts WHERE id IN ({placeholders})", copied_prompt_ids)
                conn.commit()

    def get_copied_prompts_count(self):
        """Return the number of prompts that currently have status 'copied'."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM generated_prompt_status WHERE status = 'copied' AND prompt_id IS NOT NULL")
            row = c.fetchone()
            return row[0] if row else 0

    def get_generated_prompts_paginated(self, page=1, page_size=20):
        """Get generated prompts with pagination support including status"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            offset = (page - 1) * page_size
            c.execute('''SELECT gp.id, gp.file_id, gp.prompt, gp.created_at, 
                       COALESCE(gps.status, 'pending') as status
                       FROM generated_prompts gp 
                       LEFT JOIN generated_prompt_status gps ON gp.id = gps.prompt_id
                       ORDER BY gp.id DESC 
                       LIMIT ? OFFSET ?''', (page_size, offset))
            return c.fetchall()
    
    def get_generated_prompts_count(self):
        """Get total count of generated prompts"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM generated_prompts')
            row = c.fetchone()
            return row[0] if row else 0
    
    def update_generated_prompt(self, prompt_id, new_prompt_text):
        """Update a generated prompt text"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE generated_prompts SET prompt=? WHERE id=?', (new_prompt_text, prompt_id))
            conn.commit()
    
    def get_generated_prompt_by_id(self, prompt_id):
        """Get a single generated prompt by ID"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''SELECT gp.id, gp.file_id, gp.prompt, gp.created_at 
                       FROM generated_prompts gp 
                       WHERE gp.id = ?''', (prompt_id,))
            return c.fetchone()

    # --- Generated prompt status methods ---
    def add_prompt_status(self, prompt_id, status='pending'):
        """Add or update prompt status"""
        # Do not insert a status row for a null prompt_id
        if prompt_id is None:
            # nothing to do
            return
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # Check if status already exists
            c.execute('SELECT id FROM generated_prompt_status WHERE prompt_id=?', (prompt_id,))
            row = c.fetchone()
            if row:
                # Update existing status
                c.execute('''UPDATE generated_prompt_status 
                           SET status=?, updated_at=CURRENT_TIMESTAMP 
                           WHERE prompt_id=?''', (status, prompt_id))
            else:
                # Insert new status
                c.execute('''INSERT INTO generated_prompt_status 
                           (prompt_id, status) VALUES (?, ?)''', (prompt_id, status))
            conn.commit()

    def get_prompt_status(self, prompt_id):
        """Get prompt status"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''SELECT status, created_at, updated_at 
                       FROM generated_prompt_status 
                       WHERE prompt_id=?''', (prompt_id,))
            row = c.fetchone()
            return row[0] if row else 'pending'

    def get_prompts_with_status_paginated(self, page=1, page_size=20):
        """Get generated prompts with status using pagination"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            offset = (page - 1) * page_size
            c.execute('''SELECT gp.id, gp.file_id, gp.prompt, gp.created_at,
                       COALESCE(gps.status, 'pending') as status
                       FROM generated_prompts gp 
                       LEFT JOIN generated_prompt_status gps ON gp.id = gps.prompt_id
                       ORDER BY gp.id DESC 
                       LIMIT ? OFFSET ?''', (page_size, offset))
            return c.fetchall()

    def clear_all_prompt_status(self):
        """Clear all prompt status records"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM generated_prompt_status')
            conn.commit()

    def remove_null_prompt_statuses(self):
        """Remove generated_prompt_status rows with NULL prompt_id to clean up bad entries."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM generated_prompt_status WHERE prompt_id IS NULL')
            conn.commit()

    def save_batch_audio_status(self, source_path, destination_path, status, error_message=None):
        """Save batch audio remover status to database"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO batch_audio_remover (source_path, destination_path, status, error_message)
                VALUES (?, ?, ?, ?)
            ''', (source_path, destination_path, status, error_message))
            conn.commit()

    def get_batch_audio_status(self, source_path):
        """Get batch audio remover status from database"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT status, error_message FROM batch_audio_remover 
                WHERE source_path = ? 
                ORDER BY processed_at DESC LIMIT 1
            ''', (source_path,))
            row = c.fetchone()
            if row:
                return {'status': row[0], 'error_message': row[1]}
        return None

    def clear_batch_audio_status(self, source_path):
        """Clear batch audio remover status for specific file"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM batch_audio_remover WHERE source_path = ?', (source_path,))
            conn.commit()

    def clear_all_batch_audio_status(self):
        """Clear all batch audio remover status"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM batch_audio_remover')
            conn.commit()

    def get_all_batch_audio_sources(self):
        """Get all distinct source paths from batch audio remover table"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT DISTINCT source_path FROM batch_audio_remover ORDER BY processed_at DESC')
            return [row[0] for row in c.fetchall()]

    # --- Action Sequencer Platform methods ---
    def get_all_platforms(self):
        """Get all platforms from action_sequencer_platforms table"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT platforms_id, platforms_name, platforms_exec_path, platforms_note FROM action_sequencer_platforms ORDER BY platforms_name')
            return [{
                'id': row[0],
                'name': row[1],
                'exec_path': row[2],
                'note': row[3] if row[3] else ''
            } for row in c.fetchall()]

    def add_platform(self, name, exec_path, note=''):
        """Add a new platform to action_sequencer_platforms table"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO action_sequencer_platforms (platforms_name, platforms_exec_path, platforms_note) VALUES (?, ?, ?)',
                (name, exec_path, note)
            )
            conn.commit()
            return c.lastrowid

    def update_platform(self, platform_id, name, exec_path, note=''):
        """Update an existing platform in action_sequencer_platforms table"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'UPDATE action_sequencer_platforms SET platforms_name = ?, platforms_exec_path = ?, platforms_note = ? WHERE platforms_id = ?',
                (name, exec_path, note, platform_id)
            )
            conn.commit()

    def delete_platform(self, platform_id):
        """Delete a platform from action_sequencer_platforms table"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM action_sequencer_platforms WHERE platforms_id = ?', (platform_id,))
            conn.commit()
    
    def get_platform_by_id(self, platform_id):
        """Get a single platform by ID"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT platforms_id, platforms_name, platforms_exec_path, platforms_note FROM action_sequencer_platforms WHERE platforms_id = ?', (platform_id,))
            row = c.fetchone()
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'exec_path': row[2],
                    'note': row[3] if row[3] else ''
                }
            return None
    
    def get_platform_by_name(self, platform_name):
        """Get a single platform by name"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT platforms_id, platforms_name, platforms_exec_path, platforms_note FROM action_sequencer_platforms WHERE platforms_name = ?', (platform_name,))
            row = c.fetchone()
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'exec_path': row[2],
                    'note': row[3] if row[3] else ''
                }
            return None

    # --- Action Sequencer Action Set methods ---
    def get_action_sets_by_platform(self, platform_id):
        """Get all action sets for a specific platform"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT action_sets_id, action_sets_name, action_sets_description,
                       (SELECT COUNT(*) FROM action_sequencer_actions WHERE actions_action_sets_id = action_sets_id) as action_count
                FROM action_sequencer_action_sets 
                WHERE action_sets_platforms_id = ? 
                ORDER BY action_sets_name
            ''', (platform_id,))
            return [{
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'action_count': row[3]
            } for row in c.fetchall()]

    def add_action_set(self, platform_id, name, description=''):
        """Add a new action set"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO action_sequencer_action_sets (action_sets_platforms_id, action_sets_name, action_sets_description) VALUES (?, ?, ?)',
                (platform_id, name, description)
            )
            conn.commit()
            return c.lastrowid

    def update_action_set(self, action_set_id, name, description=''):
        """Update an existing action set"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'UPDATE action_sequencer_action_sets SET action_sets_name = ?, action_sets_description = ? WHERE action_sets_id = ?',
                (name, description, action_set_id)
            )
            conn.commit()

    def delete_action_set(self, action_set_id):
        """Delete an action set (cascade will delete all actions in the set)"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM action_sequencer_action_sets WHERE action_sets_id = ?', (action_set_id,))
            conn.commit()
    
    def get_action_set_by_id(self, action_set_id):
        """Get action set by ID"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT action_sets_id, action_sets_platforms_id, action_sets_name, action_sets_description
                FROM action_sequencer_action_sets 
                WHERE action_sets_id = ?
            ''', (action_set_id,))
            row = c.fetchone()
            if row:
                return {
                    'id': row[0],
                    'platform_id': row[1],
                    'name': row[2],
                    'description': row[3]
                }
            return None

    # --- Action Sequencer Action methods ---
    def get_actions_by_action_set(self, action_set_id):
        """Get all actions for a specific action set"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT actions_id, actions_name, actions_icon, actions_color, actions_order_index,
                       actions_type, actions_delay, actions_javascript_code, actions_export_format, actions_export_setting
                FROM action_sequencer_actions 
                WHERE actions_action_sets_id = ? 
                ORDER BY actions_order_index
            ''', (action_set_id,))
            return [{
                'id': row[0],
                'name': row[1],
                'icon': row[2],
                'color': row[3],
                'order_index': row[4],
                'type': row[5],
                'delay': row[6],
                'javascript_code': row[7],
                'export_format': row[8],
                'export_setting': row[9]
            } for row in c.fetchall()]

    def add_action(self, action_set_id, name, icon='', color=theme.get_color('gray'), action_type='Action', delay=0, javascript_code='', export_format=None, export_setting=100, order_index=None):
        """Add a new action to an action set"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            if order_index is None:
                c.execute('SELECT MAX(actions_order_index) FROM action_sequencer_actions WHERE actions_action_sets_id = ?', (action_set_id,))
                max_order = c.fetchone()[0]
                order_index = (max_order or 0) + 1
            
            c.execute(
                'INSERT INTO action_sequencer_actions (actions_action_sets_id, actions_name, actions_icon, actions_color, actions_type, actions_delay, actions_javascript_code, actions_export_format, actions_export_setting, actions_order_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (action_set_id, name, icon, color, action_type, delay, javascript_code, export_format, export_setting, order_index)
            )
            conn.commit()
            return c.lastrowid

    def update_action(self, action_id, name, icon='', color=theme.get_color('gray'), action_type='Action', delay=0, javascript_code='', export_format=None, export_setting=100):
        """Update an existing action"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'UPDATE action_sequencer_actions SET actions_name = ?, actions_icon = ?, actions_color = ?, actions_type = ?, actions_delay = ?, actions_javascript_code = ?, actions_export_format = ?, actions_export_setting = ? WHERE actions_id = ?',
                (name, icon, color, action_type, delay, javascript_code, export_format, export_setting, action_id)
            )
            conn.commit()

    def delete_action(self, action_id):
        """Delete an action"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM action_sequencer_actions WHERE actions_id = ?', (action_id,))
            conn.commit()
    
    def get_action_by_id(self, action_id):
        """Get a single action by ID"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT actions_id, actions_action_sets_id, actions_name, actions_icon, 
                       actions_color, actions_order_index, actions_javascript_code,
                       actions_type, actions_delay, actions_export_format, actions_export_setting
                FROM action_sequencer_actions
                WHERE actions_id = ?
            ''', (action_id,))
            row = c.fetchone()
            if row:
                return {
                    'id': row[0],
                    'action_set_id': row[1],
                    'name': row[2],
                    'icon': row[3],
                    'color': row[4],
                    'order_index': row[5],
                    'javascript_code': row[6],
                    'type': row[7],
                    'delay': row[8],
                    'export_format': row[9],
                    'export_setting': row[10]
                }
            return None

    # --- Action Sequencer Preset methods ---
    def get_presets_by_platform(self, platform_id):
        """Get all presets for a specific platform"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT presets_id, presets_platforms_id, presets_name, presets_description, presets_type,
                       (SELECT COUNT(*) FROM action_sequencer_preset_steps WHERE preset_steps_presets_id = presets_id) as step_count
                FROM action_sequencer_presets 
                WHERE presets_platforms_id = ? 
                ORDER BY presets_name
            ''', (platform_id,))
            return [{
                'id': row[0],
                'platform_id': row[1],
                'name': row[2],
                'description': row[3],
                'type': row[4],
                'steps': row[5]
            } for row in c.fetchall()]

    def add_preset(self, platform_id, name, description='', preset_type=''):
        """Add a new preset"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO action_sequencer_presets (presets_platforms_id, presets_name, presets_description, presets_type) VALUES (?, ?, ?, ?)',
                (platform_id, name, description, preset_type)
            )
            conn.commit()
            return c.lastrowid

    def update_preset(self, preset_id, name, description='', preset_type=''):
        """Update an existing preset"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'UPDATE action_sequencer_presets SET presets_name = ?, presets_description = ?, presets_type = ? WHERE presets_id = ?',
                (name, description, preset_type, preset_id)
            )
            conn.commit()

    def delete_preset(self, preset_id):
        """Delete a preset (cascade will delete all preset steps)"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM action_sequencer_presets WHERE presets_id = ?', (preset_id,))
            conn.commit()
    
    def get_preset_by_id(self, preset_id):
        """Get preset by ID"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT presets_id, presets_platforms_id, presets_name, presets_description, presets_type
                FROM action_sequencer_presets 
                WHERE presets_id = ?
            ''', (preset_id,))
            row = c.fetchone()
            if row:
                return {
                    'id': row[0],
                    'platform_id': row[1],
                    'name': row[2],
                    'description': row[3],
                    'type': row[4]
                }
            return None

    # --- Action Sequencer Preset Steps methods ---
    def get_preset_steps(self, preset_id):
        """Get all steps for a specific preset (steps reference actions)"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT ps.preset_steps_id, ps.preset_steps_order_index,
                       a.actions_name, a.actions_icon, a.actions_color, a.actions_id,
                       ast.action_sets_name
                FROM action_sequencer_preset_steps ps
                INNER JOIN action_sequencer_actions a ON ps.preset_steps_actions_id = a.actions_id
                INNER JOIN action_sequencer_action_sets ast ON a.actions_action_sets_id = ast.action_sets_id
                WHERE ps.preset_steps_presets_id = ?
                ORDER BY ps.preset_steps_order_index
            ''', (preset_id,))
            return [{
                'id': row[0],
                'order_index': row[1],
                'name': row[2],
                'icon': row[3],
                'color': row[4],
                'action_id': row[5],
                'action_set': row[6]
            } for row in c.fetchall()]

    def add_preset_step(self, preset_id, action_id, insert_at=None):
        """Add an action to preset steps (stores reference, not copy).

        Args:
            preset_id: Preset id
            action_id: Action id
            insert_at: Optional 1-based position to insert the step. If None, appends to the end.
        """
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()

            if insert_at is None:
                c.execute('SELECT MAX(preset_steps_order_index) FROM action_sequencer_preset_steps WHERE preset_steps_presets_id = ?', (preset_id,))
                max_order = c.fetchone()[0]
                order_index = (max_order or 0) + 1
            else:
                # Shift existing steps at or after insert_at
                c.execute(
                    'UPDATE action_sequencer_preset_steps SET preset_steps_order_index = preset_steps_order_index + 1 WHERE preset_steps_presets_id = ? AND preset_steps_order_index >= ?',
                    (preset_id, insert_at)
                )
                order_index = insert_at

            c.execute(
                '''INSERT INTO action_sequencer_preset_steps 
                   (preset_steps_presets_id, preset_steps_actions_id, preset_steps_order_index) 
                   VALUES (?, ?, ?)''',
                (preset_id, action_id, order_index)
            )
            conn.commit()
            return c.lastrowid

    def update_preset_step_action(self, preset_step_id, new_action_id):
        """Update the action referenced by a preset step."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE action_sequencer_preset_steps SET preset_steps_actions_id = ? WHERE preset_steps_id = ?', (new_action_id, preset_step_id))
            conn.commit()

    def update_preset_step_order(self, preset_id, step_orders):
        """Update order_index for multiple preset steps
        step_orders: list of tuples (step_id, new_order_index)
        """
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            for step_id, new_order in step_orders:
                c.execute(
                    '''UPDATE action_sequencer_preset_steps 
                       SET preset_steps_order_index = ? 
                       WHERE preset_steps_id = ? AND preset_steps_presets_id = ?''',
                    (new_order, step_id, preset_id)
                )
            conn.commit()
    
    def delete_preset_step(self, preset_step_id):
        """Delete a preset step"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM action_sequencer_preset_steps WHERE preset_steps_id = ?', (preset_step_id,))
            conn.commit()

    def get_all_actions_for_platform(self, platform_id):
        """Get all actions from all action sets for a specific platform"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT a.actions_id, a.actions_name, a.actions_icon, a.actions_color,
                       ast.action_sets_name, ast.action_sets_id, a.actions_type, a.actions_export_format
                FROM action_sequencer_actions a
                JOIN action_sequencer_action_sets ast ON a.actions_action_sets_id = ast.action_sets_id
                WHERE ast.action_sets_platforms_id = ?
                ORDER BY ast.action_sets_name, a.actions_order_index
            ''', (platform_id,))
            return [{
                'id': row[0],
                'name': row[1],
                'icon': row[2],
                'color': row[3],
                'action_set': row[4],
                'action_set_id': row[5],
                'type': row[6],
                'export_format': row[7]
            } for row in c.fetchall()]
    
    # --- Action Sequencer Status methods ---
    def add_action_status(self, preset_id, file_id=None, source_file_path=None, status='pending', current_step=0, total_steps=0, error_message=None):
        """Add action sequencer execution status
        Args:
            preset_id: ID of the preset being executed
            file_id: Optional FK to files table (if loaded from database)
            source_file_path: Path to source file being processed
            status: Current status (pending, running, completed, failed)
            current_step: Current step number being executed
            total_steps: Total number of steps in preset
            error_message: Error message if failed
        """
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO action_sequencer_status 
                (status_preset_id, status_file_id, status_source_file_path, status_name, 
                 status_current_step, status_total_steps, status_error_message) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (preset_id, file_id, source_file_path, status, current_step, total_steps, error_message))
            conn.commit()
            return c.lastrowid
    
    def update_action_status(self, status_id, status=None, current_step=None, error_message=None, output_file_path=None):
        """Update action sequencer execution status"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            updates = []
            params = []
            
            if status is not None:
                updates.append('status_name = ?')
                params.append(status)
            if current_step is not None:
                updates.append('status_current_step = ?')
                params.append(current_step)
            if error_message is not None:
                updates.append('status_error_message = ?')
                params.append(error_message)
            if output_file_path is not None:
                updates.append('status_output_file_path = ?')
                params.append(output_file_path)
            
            if updates:
                updates.append('status_updated_at = CURRENT_TIMESTAMP')
                params.append(status_id)
                query = f"UPDATE action_sequencer_status SET {', '.join(updates)} WHERE status_id = ?"
                c.execute(query, params)
                conn.commit()
    
    def get_action_status(self, status_id):
        """Get action sequencer status by ID"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT status_id, status_preset_id, status_file_id, status_source_file_path,
                       status_name, status_current_step, status_total_steps, status_error_message,
                       status_output_file_path, status_created_at, status_updated_at
                FROM action_sequencer_status
                WHERE status_id = ?
            ''', (status_id,))
            row = c.fetchone()
            if row:
                return {
                    'id': row[0],
                    'preset_id': row[1],
                    'file_id': row[2],
                    'source_file_path': row[3],
                    'status': row[4],
                    'current_step': row[5],
                    'total_steps': row[6],
                    'error_message': row[7],
                    'output_file_path': row[8],
                    'created_at': row[9],
                    'updated_at': row[10]
                }
            return None
    
    def get_action_statuses_by_preset(self, preset_id, limit=None):
        """Get all action statuses for a preset"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            query = '''
                SELECT status_id, status_preset_id, status_file_id, status_source_file_path,
                       status_name, status_current_step, status_total_steps, status_error_message,
                       status_output_file_path, status_created_at, status_updated_at
                FROM action_sequencer_status
                WHERE status_preset_id = ?
                ORDER BY status_created_at DESC
            '''
            if limit:
                query += f' LIMIT {limit}'
            
            c.execute(query, (preset_id,))
            return [{
                'id': row[0],
                'preset_id': row[1],
                'file_id': row[2],
                'source_file_path': row[3],
                'status': row[4],
                'current_step': row[5],
                'total_steps': row[6],
                'error_message': row[7],
                'output_file_path': row[8],
                'created_at': row[9],
                'updated_at': row[10]
            } for row in c.fetchall()]
    
    def get_pending_action_statuses(self):
        """Get all pending/running action statuses"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT status_id, status_preset_id, status_file_id, status_source_file_path,
                       status_name, status_current_step, status_total_steps, status_error_message,
                       status_output_file_path, status_created_at, status_updated_at
                FROM action_sequencer_status
                WHERE status_name IN ('pending', 'running')
                ORDER BY status_created_at ASC
            ''')
            return [{
                'id': row[0],
                'preset_id': row[1],
                'file_id': row[2],
                'source_file_path': row[3],
                'status': row[4],
                'current_step': row[5],
                'total_steps': row[6],
                'error_message': row[7],
                'output_file_path': row[8],
                'created_at': row[9],
                'updated_at': row[10]
            } for row in c.fetchall()]
    
    def clear_action_statuses(self, preset_id=None):
        """Clear action statuses (all or for specific preset)"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if preset_id:
                c.execute('DELETE FROM action_sequencer_status WHERE status_preset_id = ?', (preset_id,))
            else:
                c.execute('DELETE FROM action_sequencer_status')
            conn.commit()

    def get_all_prompt_injector_points(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''SELECT point_id, point_name, point_icon, point_icon_style, point_color,
                                point_size, point_pos_x, point_pos_y, point_delay, point_enabled,
                                point_type, point_shortcut, point_order_index,
                                point_created_at, point_updated_at
                         FROM prompt_injector_points
                         ORDER BY point_order_index ASC, point_id ASC''')
            rows = c.fetchall()
            return [self._map_point_row(row) for row in rows]

    def add_prompt_injector_point(self, name, icon='location-dot', icon_style='solid',
                                   color='#ff4d4d', size=32, pos_x=0, pos_y=0,
                                   delay=1.0, enabled=True, point_type='click',
                                   shortcut=None, order_index=0):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO prompt_injector_points
                         (point_name, point_icon, point_icon_style, point_color, point_size,
                          point_pos_x, point_pos_y, point_delay, point_enabled, point_type,
                          point_shortcut, point_order_index)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (name, icon, icon_style, color, size, pos_x, pos_y,
                       delay, 1 if enabled else 0, point_type, shortcut, order_index))
            conn.commit()
            return c.lastrowid

    def update_prompt_injector_point(self, point_id, name, icon, icon_style, color, size,
                                      delay, enabled, point_type, shortcut, order_index):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''UPDATE prompt_injector_points
                         SET point_name=?, point_icon=?, point_icon_style=?, point_color=?,
                             point_size=?, point_delay=?, point_enabled=?, point_type=?,
                             point_shortcut=?, point_order_index=?,
                             point_updated_at=CURRENT_TIMESTAMP
                         WHERE point_id=?''',
                      (name, icon, icon_style, color, size, delay,
                       1 if enabled else 0, point_type, shortcut, order_index, point_id))
            conn.commit()

    def update_prompt_injector_point_position(self, point_id, pos_x, pos_y):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''UPDATE prompt_injector_points
                         SET point_pos_x=?, point_pos_y=?, point_updated_at=CURRENT_TIMESTAMP
                         WHERE point_id=?''',
                      (pos_x, pos_y, point_id))
            conn.commit()

    def update_prompt_injector_point_enabled(self, point_id, enabled):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''UPDATE prompt_injector_points
                         SET point_enabled=?, point_updated_at=CURRENT_TIMESTAMP
                         WHERE point_id=?''',
                      (1 if enabled else 0, point_id))
            conn.commit()

    def delete_prompt_injector_point(self, point_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM prompt_injector_points WHERE point_id=?', (point_id,))
            conn.commit()

    def reorder_prompt_injector_points(self, ordered_ids):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            for idx, point_id in enumerate(ordered_ids):
                c.execute('UPDATE prompt_injector_points SET point_order_index=?, point_updated_at=CURRENT_TIMESTAMP WHERE point_id=?',
                          (idx, point_id))
            conn.commit()

    def _map_point_row(self, row):
        return {
            'id': row[0],
            'name': row[1],
            'icon': row[2],
            'icon_style': row[3],
            'color': row[4],
            'size': row[5],
            'pos_x': row[6],
            'pos_y': row[7],
            'delay': row[8],
            'enabled': bool(row[9]),
            'type': row[10],
            'shortcut': row[11],
            'order_index': row[12],
            'created_at': row[13],
            'updated_at': row[14],
        }

    # --- Holiday Calendar cache methods ---
    def holiday_cache_fetch(self, country: str, year: int, month: int, expire_days: int = 7):
        import json as _json
        from datetime import datetime as _dt
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                'SELECT holidays_json, cached_at FROM holiday_cache WHERE country=? AND year=? AND month=?',
                (country.upper(), year, month)
            )
            row = c.fetchone()
        if row is None:
            return None
        cached_at = _dt.fromisoformat(row['cached_at'])
        age = (_dt.utcnow() - cached_at).days
        if age > expire_days:
            return None
        return _json.loads(row['holidays_json'])

    def holiday_cache_store(self, country: str, year: int, month: int, holidays: list):
        import json as _json
        from datetime import datetime as _dt
        now = _dt.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                '''INSERT OR REPLACE INTO holiday_cache (country, year, month, holidays_json, cached_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (country.upper(), year, month, _json.dumps(holidays), now)
            )
            conn.commit()

    def holiday_cache_clear_expired(self, expire_days: int = 7):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                "DELETE FROM holiday_cache WHERE (julianday('now') - julianday(cached_at)) > ?",
                (expire_days,)
            )
            conn.commit()

    def holiday_cache_clear_all(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM holiday_cache')
            conn.commit()

    def calendarific_get_api_key(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT api_key FROM calendarific_settings ORDER BY id LIMIT 1')
            row = c.fetchone()
            return row[0] if row else ''

    def calendarific_set_api_key(self, api_key: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM calendarific_settings')
            c.execute('INSERT INTO calendarific_settings (api_key) VALUES (?)', (api_key,))
            conn.commit()

    # --- Remotion Collections methods ---
    def add_remotion_collection(self, name, description=None, parent_collection_id=None, icon='folder', color=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO remotion_collections (name, description, parent_collection_id, icon, color) VALUES (?, ?, ?, ?, ?)',
                (name, description, parent_collection_id, icon, color)
            )
            conn.commit()
            return c.lastrowid

    def get_remotion_collection(self, collection_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'SELECT id, name, description, parent_collection_id, icon, color, created_at, updated_at FROM remotion_collections WHERE id = ?',
                (collection_id,)
            )
            row = c.fetchone()
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'parent_collection_id': row[3],
                    'icon': row[4] or 'folder',
                    'color': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                }
            return None

    def get_remotion_collections(self, parent_collection_id=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if parent_collection_id is None:
                c.execute(
                    'SELECT id, name, description, parent_collection_id, icon, color, created_at, updated_at FROM remotion_collections WHERE parent_collection_id IS NULL ORDER BY created_at DESC'
                )
            else:
                c.execute(
                    'SELECT id, name, description, parent_collection_id, icon, color, created_at, updated_at FROM remotion_collections WHERE parent_collection_id = ? ORDER BY created_at DESC',
                    (parent_collection_id,)
                )
            return [{
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'parent_collection_id': row[3],
                'icon': row[4] or 'folder',
                'color': row[5],
                'created_at': row[6],
                'updated_at': row[7]
            } for row in c.fetchall()]

    def get_remotion_collection_tree(self):
        def build_tree(parent_id=None):
            children = self.get_remotion_collections(parent_id)
            result = []
            for child in children:
                child['children'] = build_tree(child['id'])
                child['script_count'] = self.get_collection_script_count(child['id'])
                result.append(child)
            return result
        return build_tree()

    def get_all_scripts_in_collection_tree(self, collection_id, active_only=True):
        """
        Recursively get all scripts in a collection and all its sub-collections.
        Returns a flat list of script dicts with collection hierarchy information.
        """
        scripts = []

        # Get direct scripts in this collection
        direct_scripts = self.get_remotion_scripts(collection_id, active_only=active_only)
        for script in direct_scripts:
            # Add collection context to script
            script['_collection_path'] = [collection_id]
            scripts.append(script)

        # Recursively get scripts from sub-collections
        sub_collections = self.get_remotion_collections(collection_id)
        for sub_col in sub_collections:
            sub_scripts = self.get_all_scripts_in_collection_tree(sub_col['id'], active_only=active_only)
            for s in sub_scripts:
                # Store the full path from root to leaf
                if '_collection_path' not in s:
                    s['_collection_path'] = []
                s['_collection_path'] = [collection_id] + s.get('_collection_path', [])
            scripts.extend(sub_scripts)

        return scripts

    def update_remotion_collection(self, collection_id, name=None, description=None, parent_collection_id=None, icon=None, color=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            updates = []
            params = []
            if name is not None:
                updates.append('name = ?')
                params.append(name)
            if description is not None:
                updates.append('description = ?')
                params.append(description)
            if parent_collection_id is not None:
                updates.append('parent_collection_id = ?')
                params.append(parent_collection_id)
            if icon is not None:
                updates.append('icon = ?')
                params.append(icon)
            if color is not None:
                updates.append('color = ?')
                params.append(color)
            if updates:
                updates.append('updated_at = CURRENT_TIMESTAMP')
                params.append(collection_id)
                query = f"UPDATE remotion_collections SET {', '.join(updates)} WHERE id = ?"
                c.execute(query, params)
                conn.commit()

    def get_remotion_collection_delete_preview(self, collection_id):
        collections = []
        scripts = []

        def collect(cid, visited=None, depth=0):
            if visited is None:
                visited = set()
            if cid in visited:
                return  # cycle detected, skip
            if depth > 100:
                return  # depth limit to prevent stack overflow on circular refs
            visited.add(cid)

            direct_scripts = self.get_remotion_scripts(cid, active_only=False)
            print(f"[DEBUG DB] Collection {cid} has {len(direct_scripts)} direct scripts")
            for s in direct_scripts:
                scripts.append(s.get('name', 'Unnamed'))
            sub_cols = self.get_remotion_collections(cid)
            print(f"[DEBUG DB] Collection {cid} has {len(sub_cols)} sub-collections")
            for col in sub_cols:
                collections.append(col.get('name', 'Unnamed'))
                collect(col['id'], visited, depth + 1)

        print(f"[DEBUG DB] get_remotion_collection_delete_preview called for collection_id={collection_id}")
        collect(collection_id)
        print(f"[DEBUG DB] Returning preview: {len(collections)} sub-collections, {len(scripts)} scripts")
        return {'collections': collections, 'scripts': scripts}

    def delete_remotion_collection(self, collection_id):
        """Delete a collection and all its sub-collections and scripts recursively."""
        def collect_all_ids(cid, visited=None, depth=0):
            if visited is None:
                visited = set()
            if cid in visited:
                return []  # cycle detected, skip to avoid infinite loop
            if depth > 100:
                raise ValueError("Collection hierarchy exceeds safe depth (possible circular reference)")
            visited.add(cid)
            ids = [cid]
            sub_cols = self.get_remotion_collections(cid)
            for col in sub_cols:
                if col['id'] not in visited:
                    ids.extend(collect_all_ids(col['id'], visited, depth + 1))
            return ids

        all_ids = collect_all_ids(collection_id)
        print(f"[DEBUG DB] delete_remotion_collection: collection_id={collection_id}, all_ids={all_ids}")
        if not all_ids:
            print("[DEBUG DB] Nothing to delete, returning early")
            return  # nothing to delete

        with sqlite3.connect(self.db_path) as conn:
            try:
                c = conn.cursor()
                placeholders = ','.join('?' * len(all_ids))
                # Delete scripts first
                c.execute(f'DELETE FROM remotion_scripts WHERE collection_id IN ({placeholders})', all_ids)
                deleted_scripts = c.rowcount
                print(f"[DEBUG DB] Deleted {deleted_scripts} scripts from collections {all_ids}")
                # Delete collections
                for cid in reversed(all_ids):
                    c.execute('DELETE FROM remotion_collections WHERE id = ?', (cid,))
                deleted_collections = len(all_ids)
                print(f"[DEBUG DB] Deleted {deleted_collections} collections: {all_ids}")
                conn.commit()
                print("[DEBUG DB] Transaction committed")
            except sqlite3.Error as e:
                conn.rollback()
                print(f"[DEBUG DB] Database error: {e}")
                raise RuntimeError(f"Database error during delete: {e}") from e

    def get_collection_script_count(self, collection_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM remotion_scripts WHERE collection_id = ?', (collection_id,))
            row = c.fetchone()
            return row[0] if row else 0

    # --- Remotion Scripts methods ---
    def add_remotion_script(self, collection_id, name, script_content, description=None, version='1.0.0', tags=None, author=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                '''INSERT INTO remotion_scripts (collection_id, name, script_content, description, version, tags, author)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (collection_id, name, script_content, description, version, tags, author)
            )
            conn.commit()
            return c.lastrowid

    def get_remotion_script(self, script_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                '''SELECT id, collection_id, name, description, script_content, version, tags,
                          is_active, author, created_at, updated_at, last_used_at
                   FROM remotion_scripts WHERE id = ?''',
                (script_id,)
            )
            row = c.fetchone()
            if row:
                return {
                    'id': row[0],
                    'collection_id': row[1],
                    'name': row[2],
                    'description': row[3],
                    'script_content': row[4],
                    'version': row[5],
                    'tags': row[6],
                    'is_active': bool(row[7]),
                    'author': row[8],
                    'created_at': row[9],
                    'updated_at': row[10],
                    'last_used_at': row[11]
                }
            return None

    def get_remotion_scripts(self, collection_id, active_only=True):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if active_only:
                c.execute(
                    '''SELECT id, collection_id, name, description, script_content, version, tags,
                              is_active, author, created_at, updated_at, last_used_at
                       FROM remotion_scripts WHERE collection_id = ? AND is_active = 1 ORDER BY created_at ASC''',
                    (collection_id,)
                )
            else:
                c.execute(
                    '''SELECT id, collection_id, name, description, script_content, version, tags,
                              is_active, author, created_at, updated_at, last_used_at
                       FROM remotion_scripts WHERE collection_id = ? ORDER BY created_at ASC''',
                    (collection_id,)
                )
            return [self._map_script_row(row) for row in c.fetchall()]

    def get_all_remotion_scripts(self, active_only=True):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if active_only:
                c.execute(
                    '''SELECT id, collection_id, name, description, script_content, version, tags,
                              is_active, author, created_at, updated_at, last_used_at
                       FROM remotion_scripts WHERE is_active = 1 ORDER BY name COLLATE NOCASE'''
                )
            else:
                c.execute(
                    '''SELECT id, collection_id, name, description, script_content, version, tags,
                              is_active, author, created_at, updated_at, last_used_at
                       FROM remotion_scripts ORDER BY name COLLATE NOCASE'''
                )
            return [self._map_script_row(row) for row in c.fetchall()]

    def search_remotion_scripts(self, search_text, active_only=True):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            pattern = f"%{search_text}%"
            if active_only:
                c.execute(
                    '''SELECT id, collection_id, name, description, script_content, version, tags,
                              is_active, author, created_at, updated_at, last_used_at
                       FROM remotion_scripts
                       WHERE is_active = 1 AND (name LIKE ? OR description LIKE ? OR tags LIKE ? OR script_content LIKE ?)
                       ORDER BY name COLLATE NOCASE''',
                    (pattern, pattern, pattern, pattern)
                )
            else:
                c.execute(
                    '''SELECT id, collection_id, name, description, script_content, version, tags,
                              is_active, author, created_at, updated_at, last_used_at
                       FROM remotion_scripts
                       WHERE name LIKE ? OR description LIKE ? OR tags LIKE ? OR script_content LIKE ?
                       ORDER BY name COLLATE NOCASE''',
                    (pattern, pattern, pattern, pattern)
                )
            return [self._map_script_row(row) for row in c.fetchall()]

    def update_remotion_script(self, script_id, name=None, script_content=None, description=None, version=None, tags=None, is_active=None, author=None):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            updates = []
            params = []
            if name is not None:
                updates.append('name = ?')
                params.append(name)
            if script_content is not None:
                updates.append('script_content = ?')
                params.append(script_content)
            if description is not None:
                updates.append('description = ?')
                params.append(description)
            if version is not None:
                updates.append('version = ?')
                params.append(version)
            if tags is not None:
                updates.append('tags = ?')
                params.append(tags)
            if is_active is not None:
                updates.append('is_active = ?')
                params.append(1 if is_active else 0)
            if author is not None:
                updates.append('author = ?')
                params.append(author)
            if updates:
                updates.append('updated_at = CURRENT_TIMESTAMP')
                params.append(script_id)
                query = f"UPDATE remotion_scripts SET {', '.join(updates)} WHERE id = ?"
                c.execute(query, params)
                conn.commit()

    def delete_remotion_script(self, script_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM remotion_scripts WHERE id = ?', (script_id,))
            conn.commit()

    def update_script_last_used(self, script_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('UPDATE remotion_scripts SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?', (script_id,))
            conn.commit()

    def _map_script_row(self, row):
        return {
            'id': row[0],
            'collection_id': row[1],
            'name': row[2],
            'description': row[3],
            'script_content': row[4],
            'version': row[5],
            'tags': row[6],
            'is_active': bool(row[7]),
            'author': row[8],
            'created_at': row[9],
            'updated_at': row[10],
            'last_used_at': row[11]
        }