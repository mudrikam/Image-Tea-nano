import json
import os
from typing import Dict, Any
from config import BASE_PATH

class ThemeSystem:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(BASE_PATH, 'configs', 'app_themes.json')
        self.config_path = config_path
        self.themes: Dict[str, Dict[str, Any]] = {}
        self.current_theme: str = "default"
        self.load_themes()

    def load_themes(self):
        """Load themes from JSON file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.themes = data.get('themes', {})
                self.current_theme = data.get('current_theme', 'default')
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to default theme if file not found or invalid
            self.themes = {
                "default": {
                    "name": "Default",
                    "colors": {
                        "primary": "#4e9e20",
                        "primary_hover": "#3d7307",
                        "primary_pressed": "#1e7e34",
                        "secondary": "#cc3333",
                        "secondary_hover": "#aa2222",
                        "secondary_pressed": "#881111",
                        "success": "#4CAF50",
                        "error": "#f44336",
                        "warning": "#f0ad4e",
                        "background_dark": "#2b2b2b",
                        "background_light": "#1e1e1e",
                        "foreground": "#d4d4d4",
                        "text_light": "#cccccc",
                        "text_dark": "#808080",
                        "white": "#ffffff",
                        "black": "#000000",
                        "gray": "#888888",
                        "button_disabled_bg": "#9fbf9a",
                        "button_disabled_fg": "#f2f2f2"
                    }
                }
            }
            self.current_theme = "default"

    def get_color(self, color_name: str) -> str:
        """Get color value by name from current theme"""
        if self.current_theme in self.themes:
            colors = self.themes[self.current_theme].get('colors', {})
            return colors.get(color_name, "#000000")  # fallback to black
        return "#000000"

    def set_theme(self, theme_name: str):
        """Set current theme"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.save_config()

    def save_config(self):
        """Save current configuration to file"""
        data = {
            "themes": self.themes,
            "current_theme": self.current_theme
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # Silently fail if can't save

# Global theme instance
theme = ThemeSystem()
