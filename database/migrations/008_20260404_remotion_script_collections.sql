-- Migration ID: 008_20260404_remotion_script_collections
-- Date: 2026-04-04
-- Author: Mudrikul Hikam
-- Purpose: Add tables for Remotion script collections and TypeScript scripts
-- Description:
--   Creates two tables to store Remotion video script collections and their
--   associated TypeScript code. Collections support hierarchical nesting via
--   parent_collection_id self-reference. Scripts store full TSX source code
--   as TEXT and include metadata like version, tags, and usage tracking.
-- Affected Files:
--   - database/migrations/008_20260404_remotion_script_collections.sql
--   - database/db_operation.py (add CRUD methods)
--   - dialogs/tools/vibe_video_generator/collections_widget.py (implement UI)
--   - dialogs/tools/vibe_video_generator/scripts_widget.py (implement UI)
-- DDL Summary:
--   - CREATE TABLE remotion_collections (id, name, description, parent_collection_id, created_at, updated_at)
--   - CREATE TABLE remotion_scripts (id, collection_id, name, description, script_content, version, tags, is_active, author, created_at, updated_at, last_used_at)
--   - CREATE INDEX idx_scripts_collection ON remotion_scripts(collection_id)
--   - CREATE INDEX idx_collections_parent ON remotion_collections(parent_collection_id)
--   - CREATE INDEX idx_scripts_name ON remotion_scripts(name)
--   - CREATE INDEX idx_scripts_tags ON remotion_scripts(tags)
--   - CREATE INDEX idx_scripts_active ON remotion_scripts(is_active)
-- Data Migration: None
-- Rollback Steps:
--   Restore the database from the migration backup created before applying
--   this migration.
-- Backups:
--   Migration process will create a backup file named like:
--     backup_{TIMESTAMP}_migration_008_20260404_remotion_script_collections.db
-- Prerequisites:
--   - None (new tables, no dependencies on other migrations)
-- Testing:
--   1) Verify tables exist: `sqlite3 database/database.db ".tables"`
--   2) Verify schema: `PRAGMA table_info(remotion_collections);` and `PRAGMA table_info(remotion_scripts);`
--   3) Insert sample collection and script, verify CRUD operations
-- Notes:
--   - script_content stores full TSX code as TEXT; consider size limits for very large scripts
--   - tags stored as comma-separated string for simplicity; can be normalized later if needed
--   - parent_collection_id enables unlimited nesting depth

-- Collections table (supports nested folders via self-referencing FK)
CREATE TABLE IF NOT EXISTS remotion_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    parent_collection_id INTEGER,
    icon TEXT DEFAULT 'folder',
    color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parent_collection_id) REFERENCES remotion_collections(id) ON DELETE CASCADE
);

-- Scripts table (one-to-many: each script belongs to exactly one collection)
CREATE TABLE IF NOT EXISTS remotion_scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    script_content TEXT NOT NULL,
    version TEXT DEFAULT '1.0.0',
    tags TEXT,
    is_active INTEGER DEFAULT 1,
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    FOREIGN KEY(collection_id) REFERENCES remotion_collections(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_scripts_collection ON remotion_scripts(collection_id);
CREATE INDEX IF NOT EXISTS idx_collections_parent ON remotion_collections(parent_collection_id);
CREATE INDEX IF NOT EXISTS idx_scripts_name ON remotion_scripts(name);
CREATE INDEX IF NOT EXISTS idx_scripts_tags ON remotion_scripts(tags);
CREATE INDEX IF NOT EXISTS idx_scripts_active ON remotion_scripts(is_active);
