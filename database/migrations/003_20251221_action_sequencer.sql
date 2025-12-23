-- Migration ID: 003_20251221_action_sequencer
-- Date: 2025-12-21
-- Author: Mudrikul Hikam
-- Purpose: Create tables for action sequencer tool

CREATE TABLE IF NOT EXISTS action_sequencer_platforms (
    platforms_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platforms_name TEXT NOT NULL,
    platforms_exec_path TEXT,
    platforms_note TEXT,
    platforms_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    platforms_updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_sequencer_presets (
    presets_id INTEGER PRIMARY KEY AUTOINCREMENT,
    presets_platforms_id INTEGER NOT NULL,
    presets_name TEXT NOT NULL,
    presets_description TEXT,
    presets_type TEXT,
    presets_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    presets_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(presets_platforms_id) REFERENCES action_sequencer_platforms(platforms_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS action_sequencer_preset_steps (
    preset_steps_id INTEGER PRIMARY KEY AUTOINCREMENT,
    preset_steps_presets_id INTEGER NOT NULL,
    preset_steps_actions_id INTEGER NOT NULL,
    preset_steps_order_index INTEGER NOT NULL,
    preset_steps_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    preset_steps_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(preset_steps_presets_id) REFERENCES action_sequencer_presets(presets_id) ON DELETE CASCADE,
    FOREIGN KEY(preset_steps_actions_id) REFERENCES action_sequencer_actions(actions_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS action_sequencer_action_sets (
    action_sets_id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_sets_platforms_id INTEGER NOT NULL,
    action_sets_name TEXT NOT NULL,
    action_sets_description TEXT,
    action_sets_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    action_sets_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(action_sets_platforms_id) REFERENCES action_sequencer_platforms(platforms_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS action_sequencer_actions (
    actions_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actions_action_sets_id INTEGER NOT NULL,
    actions_order_index INTEGER NOT NULL,
    actions_name TEXT NOT NULL,
    actions_type TEXT DEFAULT 'Action',
    actions_icon TEXT,
    actions_color TEXT,
    actions_delay INTEGER DEFAULT 0,
    actions_javascript_code TEXT,
    actions_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    actions_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(actions_action_sets_id) REFERENCES action_sequencer_action_sets(action_sets_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS action_sequencer_status (
    status_id INTEGER PRIMARY KEY AUTOINCREMENT,
    status_name TEXT NOT NULL,
    status_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status_updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
