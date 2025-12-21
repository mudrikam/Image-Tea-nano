-- Migration ID: 002_20251221_batch_audio_remover
-- Date: 2025-12-21
-- Author: Mudrikul Hikam
-- Purpose: Create table for batch audio remover tool status tracking
-- Description:
--   Creates a new table to track processing status for the batch audio
--   remover tool. Stores status per processed file (failed, success, stopped).
-- Affected Files:
--   - database/database.db (SQLite target)
--   - database/migrations/002_20251221_batch_audio_remover.sql
--   - dialogs/tools/batch_audio_remover.py
--   - helpers/tools/batch_audio_remover_helper.py
-- DDL Summary:
--   - CREATE TABLE batch_audio_remover
-- Data Migration: None
-- Rollback Steps:
--   Restore the database from the migration backup created before applying
--   this migration. The migration runner creates a backup automatically.
-- Backups:
--   Migration process will create a backup file named like:
--     backup_{TIMESTAMP}_migration_002_20251221_batch_audio_remover.db
-- Prerequisites:
--   - Migration 001_20251204_init must be applied first
-- Testing:
--   1) Verify schema: `PRAGMA table_info('batch_audio_remover');`
--   2) Insert a test row and verify status is stored correctly
-- Notes:
--   - Status field stores: 'failed', 'success', 'stopped'
--   - source_path is the input file path
--   - destination_path is the output file path

CREATE TABLE IF NOT EXISTS batch_audio_remover (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    destination_path TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
