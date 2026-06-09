-- Migration ID: 009_20260605_account_manager
-- Date: 2026-06-05
-- Author: Mudrikul Hikam
-- Purpose: Create tables for Account Manager (workspace > group > profile hierarchy)

-- Workspace: top-level container
CREATE TABLE IF NOT EXISTS account_workspaces (
    workspace_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_name TEXT NOT NULL,
    workspace_description TEXT,
    workspace_icon TEXT,
    workspace_color TEXT,
    workspace_browser_exe_path TEXT,
    workspace_root_profile_path TEXT,
    workspace_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    workspace_updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Group: collection of profiles within a workspace
CREATE TABLE IF NOT EXISTS account_groups (
    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_workspace_id INTEGER NOT NULL,
    group_name TEXT NOT NULL,
    group_description TEXT,
    group_icon TEXT,
    group_color TEXT,
    group_order_index INTEGER DEFAULT 0,
    group_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    group_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(group_workspace_id) REFERENCES account_workspaces(workspace_id) ON DELETE CASCADE
);

-- Profile: individual browser profile
CREATE TABLE IF NOT EXISTS account_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_group_id INTEGER NOT NULL,
    profile_name TEXT NOT NULL,
    profile_description TEXT,
    profile_icon TEXT,
    profile_color TEXT,
    profile_browser_profile_name TEXT,
    profile_browser_profile_path TEXT,
    profile_order_index INTEGER DEFAULT 0,
    profile_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    profile_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(profile_group_id) REFERENCES account_groups(group_id) ON DELETE CASCADE
);

-- Profile settings: additional configuration per profile
CREATE TABLE IF NOT EXISTS account_profile_settings (
    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_profile_id INTEGER NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    setting_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    setting_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(setting_profile_id) REFERENCES account_profiles(profile_id) ON DELETE CASCADE,
    UNIQUE(setting_profile_id, setting_key)
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_account_groups_workspace ON account_groups(group_workspace_id);
CREATE INDEX IF NOT EXISTS idx_account_profiles_group ON account_profiles(profile_group_id);
CREATE INDEX IF NOT EXISTS idx_account_profile_settings_profile ON account_profile_settings(setting_profile_id);
