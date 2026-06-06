-- Migration ID: 010_20260606_browser_type_support
-- Date: 2026-06-06
-- Author: Mudrikul Hikam
-- Purpose: Add browser_type field to workspaces and profiles

-- Add browser_type column to account_workspaces
ALTER TABLE account_workspaces 
ADD COLUMN workspace_browser_type TEXT DEFAULT 'chrome';

-- Add browser_type column to account_profiles
ALTER TABLE account_profiles 
ADD COLUMN profile_browser_type TEXT DEFAULT 'chrome';

-- Add profile_zip_name to store original profile name in multi-profile zips
ALTER TABLE account_profiles 
ADD COLUMN profile_zip_name TEXT;