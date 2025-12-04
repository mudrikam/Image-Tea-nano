-- Initial database schema
-- Created: 2025-12-04

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT,
    api_key TEXT,
    note TEXT,
    last_tested TEXT,
    status TEXT,
    model TEXT
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE,
    filename TEXT,
    title TEXT,
    description TEXT,
    tags TEXT,
    status TEXT,
    original_filename TEXT
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT,
    service TEXT,
    model TEXT,
    token_input INTEGER,
    token_output INTEGER,
    token_total INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS platform_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS files_type_assign (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER,
    file_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(file_id) REFERENCES files(id)
);

CREATE TABLE IF NOT EXISTS category_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER,
    platform_id INTEGER,
    category_id INTEGER,
    category_name TEXT,
    FOREIGN KEY(file_id) REFERENCES files(id),
    FOREIGN KEY(platform_id) REFERENCES platform_list(id)
);

CREATE TABLE IF NOT EXISTS generated_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER,
    prompt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(file_id) REFERENCES files(id)
);

CREATE TABLE IF NOT EXISTS imagen_generation_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER,
    status TEXT DEFAULT 'pending',
    images_generated INTEGER DEFAULT 0,
    images_requested INTEGER DEFAULT 4,
    error_message TEXT,
    generated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(prompt_id) REFERENCES generated_prompts(id)
);

CREATE TABLE IF NOT EXISTS generated_prompt_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(prompt_id) REFERENCES generated_prompts(id)
);
