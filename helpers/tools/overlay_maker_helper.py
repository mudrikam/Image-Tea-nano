import os
import json
from config import BASE_PATH


class OverlayMakerConfig:
    """Config helper for Image Overlay Maker - stores settings in temp folder"""
    
    def __init__(self):
        self.config_path = os.path.join(BASE_PATH, 'temp', 'overlay_maker_config.json')
        self.default_config = {
            'overlay_path': '',
            'last_source_path': '',
            'last_output_path': ''
        }
        self.config = self.load()
    
    def load(self):
        """Load config from JSON file, create if doesn't exist"""
        if not os.path.exists(self.config_path):
            try:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.default_config, f, indent=4, ensure_ascii=False)
                print(f'Created overlay maker config: {self.config_path}')
            except Exception as e:
                print(f'Failed to create overlay maker config: {e}')
                return self.default_config.copy()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Merge with defaults to ensure all keys exist
                for key in self.default_config:
                    if key not in loaded:
                        loaded[key] = self.default_config[key]
                return loaded
        except Exception as e:
            print(f'Failed to load overlay maker config: {e}')
            return self.default_config.copy()
    
    def save(self):
        """Save config to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f'Failed to save overlay maker config: {e}')
            return False
    
    def get(self, key, default=None):
        """Get config value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set config value and save"""
        self.config[key] = value
        return self.save()
