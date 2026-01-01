-- Migration ID: 004_20260101_export_settings
-- Date: 2026-01-01
-- Purpose: Add export settings field for compression and EPS version

ALTER TABLE action_sequencer_actions 
ADD COLUMN actions_export_setting INTEGER DEFAULT 100;
