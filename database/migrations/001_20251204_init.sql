-- Migration ID: 001_20251204_init
-- Date: 2025-12-04
-- Author: Mudrikul Hikam
-- Purpose: Initial database schema (create core application tables)
-- Description:
--   Creates the core schema required by Image Tea application. This migration
--   defines tables for API keys, files metadata, token accounting, platform
--   mappings, generated prompts and generation status tracking.
-- Affected Files:
--   - database/database.db (SQLite target)
--   - database/migrations/001_20251204_init.sql
-- DDL Summary:
--   - CREATE TABLE api_keys
--   - CREATE TABLE files
--   - CREATE TABLE api_tokens
--   - CREATE TABLE platform_list
--   - CREATE TABLE files_type_assign
--   - CREATE TABLE category_mapping
--   - CREATE TABLE generated_prompts
--   - CREATE TABLE imagen_generation_status
--   - CREATE TABLE generated_prompt_status
-- Data Migration: None
-- Rollback Steps:
--   Restore the database from the migration backup created before applying
--   this migration. The migration runner creates a backup automatically.
-- Backups:
--   Migration process will create a backup file named like:
--     backup_{TIMESTAMP}_migration_001_20251204_init.db
-- Prerequisites:
--   - Ensure no concurrent writers are operating on the database while
--     applying migrations.
--   - Recommended to stop the application or perform migration in maintenance
--     mode for production deployments.
-- Testing:
--   1) Verify schema was applied: `sqlite3 database/database.db ".tables"` or
--      `PRAGMA table_info('<table>');` for each table.
--   2) Insert and read a small sample row into each table to confirm basic
--      CRUD functionality.
-- Notes:
--   - This initial schema uses TEXT fields and default timestamps; consider
--     adding indexes for high-volume queries in a later migration.

-- Suggested SQL Migration Header Documentation (fill when creating a new migration)
--  - Migration ID:       <numeric_prefix>_<YYYYMMDDHHMMSS>_<short_name>.sql
--  - Date:               YYYY-MM-DD
--  - Author:             Full Name <email@example.com>
--  - Purpose:            One-line summary of the change
--  - Description:        Short paragraph describing schema and/or data changes
--  - Affected Files:     Code/config files that need updates or attention
--  - DDL Summary:        List of tables/columns/indexes created, altered, or dropped
--  - Data Migration:     Any data transform/cleanup steps (if applicable)
--  - Rollback Steps:     How to undo this migration (if reversible) or notes about restore
--  - Backups:            Which backup(s) are created before applying (migration backup file name)
--  - Prerequisites:      Other migrations or environment conditions required
--  - Testing:            Minimal verification steps to confirm success after apply
--  - Notes:              Performance, locking, or compatibility considerations

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
