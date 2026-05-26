import os
import json
from config import BASE_PATH


class FolderComparatorConfig:
    def __init__(self):
        self.config_path = os.path.join(BASE_PATH, 'temp', 'folder_comparator_config.json')
        self.default_config = {
            'source_path': '',
            'destination_path': ''
        }
        self.config = self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            self.save(self.default_config.copy())
            return self.default_config.copy()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for key in self.default_config:
                    if key not in loaded:
                        loaded[key] = self.default_config[key]
                return loaded
        except Exception:
            return self.default_config.copy()

    def save(self, config=None):
        if config is None:
            config = self.config
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        return self.save()
