import sqlite3
import json
from config import BASE_PATH
import os
from database.db_migration_manager import DBMigrationManager

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

    def delete_all_api_keys(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM api_keys')
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
            # Clear related status first to avoid orphans
            c.execute('DELETE FROM generated_prompt_status')
            c.execute('DELETE FROM generated_prompts')
            conn.commit()
    
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

    # --- Imagen generation status methods ---
    def add_imagen_generation_status(self, prompt_id, images_requested=4):
        """Add imagen generation status for a prompt"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO imagen_generation_status 
                       (prompt_id, images_requested, status) 
                       VALUES (?, ?, 'pending')''', (prompt_id, images_requested))
            conn.commit()
            return c.lastrowid

    def update_imagen_generation_status(self, prompt_id, status, images_generated=None, error_message=None):
        """Update imagen generation status"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if images_generated is not None:
                if error_message:
                    c.execute('''UPDATE imagen_generation_status 
                               SET status=?, images_generated=?, error_message=?, generated_at=CURRENT_TIMESTAMP 
                               WHERE prompt_id=?''', (status, images_generated, error_message, prompt_id))
                else:
                    c.execute('''UPDATE imagen_generation_status 
                               SET status=?, images_generated=?, generated_at=CURRENT_TIMESTAMP 
                               WHERE prompt_id=?''', (status, images_generated, prompt_id))
            else:
                if error_message:
                    c.execute('''UPDATE imagen_generation_status 
                               SET status=?, error_message=? 
                               WHERE prompt_id=?''', (status, error_message, prompt_id))
                else:
                    c.execute('''UPDATE imagen_generation_status 
                               SET status=? 
                               WHERE prompt_id=?''', (status, prompt_id))
            conn.commit()

    def get_imagen_generation_status(self, prompt_id):
        """Get imagen generation status for a prompt"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''SELECT id, prompt_id, status, images_generated, images_requested, 
                       error_message, generated_at, created_at 
                       FROM imagen_generation_status 
                       WHERE prompt_id=?''', (prompt_id,))
            return c.fetchone()

    def get_pending_imagen_prompts(self):
        """Get all prompts that are pending image generation"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''SELECT gp.id, gp.prompt, igs.status, igs.images_generated, igs.images_requested
                       FROM generated_prompts gp
                       LEFT JOIN imagen_generation_status igs ON gp.id = igs.prompt_id
                       WHERE igs.status IS NULL OR igs.status IN ('pending', 'stopped', 'failed')
                       ORDER BY gp.created_at DESC''')
            return c.fetchall()

    def get_imagen_generation_stats(self):
        """Get overall imagen generation statistics"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            # Total prompts
            c.execute('SELECT COUNT(*) FROM generated_prompts')
            total_prompts = c.fetchone()[0]
            
            # Prompts with status
            c.execute('''SELECT 
                       COUNT(CASE WHEN igs.status = 'generated' THEN 1 END) as completed,
                       COUNT(CASE WHEN igs.status = 'pending' THEN 1 END) as pending,
                       COUNT(CASE WHEN igs.status = 'stopped' THEN 1 END) as stopped,
                       COUNT(CASE WHEN igs.status = 'failed' THEN 1 END) as failed,
                       SUM(CASE WHEN igs.status = 'generated' THEN igs.images_generated ELSE 0 END) as total_images
                       FROM generated_prompts gp
                       LEFT JOIN imagen_generation_status igs ON gp.id = igs.prompt_id''')
            stats = c.fetchone()
            
            return {
                'total_prompts': total_prompts,
                'completed': stats[0] if stats[0] else 0,
                'pending': stats[1] if stats[1] else 0,
                'stopped': stats[2] if stats[2] else 0,
                'failed': stats[3] if stats[3] else 0,
                'total_images': stats[4] if stats[4] else 0,
                'no_status': total_prompts - (stats[0] or 0) - (stats[1] or 0) - (stats[2] or 0) - (stats[3] or 0)
            }

    def clear_all_imagen_generation_status(self):
        """Clear all imagen generation status records"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM imagen_generation_status')
            conn.commit()

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
                       actions_type, actions_delay, actions_javascript_code, actions_export_format
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
                'export_format': row[8]
            } for row in c.fetchall()]

    def add_action(self, action_set_id, name, icon='', color='#888888', action_type='Action', delay=0, javascript_code='', export_format=None, order_index=None):
        """Add a new action to an action set"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            if order_index is None:
                c.execute('SELECT MAX(actions_order_index) FROM action_sequencer_actions WHERE actions_action_sets_id = ?', (action_set_id,))
                max_order = c.fetchone()[0]
                order_index = (max_order or 0) + 1
            
            c.execute(
                'INSERT INTO action_sequencer_actions (actions_action_sets_id, actions_name, actions_icon, actions_color, actions_type, actions_delay, actions_javascript_code, actions_export_format, actions_order_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (action_set_id, name, icon, color, action_type, delay, javascript_code, export_format, order_index)
            )
            conn.commit()
            return c.lastrowid

    def update_action(self, action_id, name, icon='', color='#888888', action_type='Action', delay=0, javascript_code='', export_format=None):
        """Update an existing action"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                'UPDATE action_sequencer_actions SET actions_name = ?, actions_icon = ?, actions_color = ?, actions_type = ?, actions_delay = ?, actions_javascript_code = ?, actions_export_format = ? WHERE actions_id = ?',
                (name, icon, color, action_type, delay, javascript_code, export_format, action_id)
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
                       actions_type, actions_delay, actions_export_format
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
                    'export_format': row[9]
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
                       ast.action_sets_name, ast.action_sets_id
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
                'action_set_id': row[5]
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