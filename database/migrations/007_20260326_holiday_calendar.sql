-- Migration ID: 007_20260326_holiday_calendar
-- Date: 2026-03-26
-- Author: Mudrikul Hikam
-- Purpose: Create holiday_cache and calendarific_settings tables for Microstock Holiday Calendar tool

CREATE TABLE IF NOT EXISTS holiday_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    holidays_json TEXT NOT NULL,
    cached_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country, year, month)
);

CREATE TABLE IF NOT EXISTS calendarific_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO calendarific_settings (id, api_key) VALUES (1, '');
