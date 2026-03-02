-- Migration ID: 006_20260302_prompt_injector_v2
-- Date: 2026-03-02
-- Author: Mudrikul Hikam
-- Purpose: Create table for Prompt Injector v2 dynamic points

CREATE TABLE IF NOT EXISTS prompt_injector_points (
    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_name TEXT NOT NULL,
    point_icon TEXT DEFAULT 'location-crosshairs',
    point_icon_style TEXT DEFAULT 'solid',
    point_color TEXT DEFAULT '#ff4d4d',
    point_size INTEGER DEFAULT 32,
    point_pos_x INTEGER DEFAULT 0,
    point_pos_y INTEGER DEFAULT 0,
    point_delay REAL DEFAULT 1.0,
    point_enabled INTEGER DEFAULT 1,
    point_type TEXT DEFAULT 'click',
    point_shortcut TEXT,
    point_order_index INTEGER DEFAULT 0,
    point_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    point_updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
