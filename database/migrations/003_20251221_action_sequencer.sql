-- Migration ID: 003_20251221_action_sequencer
-- Date: 2025-12-21
-- Author: Mudrikul Hikam
-- Purpose: Create tables for action sequencer tool
-- Description:
--   Creates tables to store action sequences and presets for automating
--   actions in Photoshop and Illustrator.
-- Affected Files:
--   - database/database.db (SQLite target)
--   - database/migrations/003_20251221_action_sequencer.sql
--   - dialogs/tools/action_sequencer.py
--   - helpers/tools/action_sequencer_helper.py
-- DDL Summary:
--   - CREATE TABLE action_sequencer_presets
-- Data Migration: None
-- Rollback Steps:
--   Restore the database from the migration backup created before applying
--   this migration. The migration runner creates a backup automatically.
-- Backups:
--   Migration process will create a backup file named like:
--     backup_{TIMESTAMP}_migration_003_20251221_action_sequencer.db
-- Prerequisites:
--   - Migration 001_20251204_init must be applied first
-- Testing:
--   1) Verify schema: `PRAGMA table_info('action_sequencer_presets');`
--   2) Insert a test row and verify data is stored correctly
-- Notes:
--   - Presets table stores reusable action sequence configurations
--   - config_data is stored as JSON for flexibility

CREATE TABLE IF NOT EXISTS action_sequencer_platforms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_name TEXT NOT NULL UNIQUE,
    platform_description TEXT,
    platform_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    platform_updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_sequencer_platform_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id INTEGER NOT NULL,
    executable_path TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform_id),
    FOREIGN KEY(platform_id) REFERENCES action_sequencer_platforms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS action_sequencer_action_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_set_name TEXT NOT NULL,
    action_set_description TEXT,
    action_set_platform_id INTEGER NOT NULL,
    action_set_is_active INTEGER DEFAULT 0,
    action_set_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    action_set_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(action_set_platform_id, action_set_name),
    FOREIGN KEY(action_set_platform_id) REFERENCES action_sequencer_platforms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS action_sequencer_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_set_id INTEGER NOT NULL,
    action_name TEXT NOT NULL,
    action_type TEXT DEFAULT 'action',
    action_note TEXT,
    action_color TEXT,
    action_icon TEXT,
    action_params TEXT,
    action_order INTEGER NOT NULL,
    action_delay REAL DEFAULT 0.0,
    action_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    action_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(action_set_id) REFERENCES action_sequencer_action_sets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS action_sequencer_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status_action_id INTEGER,
    status_action_set_id INTEGER,
    status_run_id TEXT,
    status_state TEXT NOT NULL,
    status_message TEXT,
    status_started_at TEXT,
    status_finished_at TEXT,
    status_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(status_action_id) REFERENCES action_sequencer_actions(id) ON DELETE SET NULL,
    FOREIGN KEY(status_action_set_id) REFERENCES action_sequencer_action_sets(id) ON DELETE CASCADE
);
