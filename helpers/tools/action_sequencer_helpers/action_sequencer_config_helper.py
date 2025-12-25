import os
import json
from config import BASE_PATH


class ActionSequencerConfig:
    def __init__(self):
        self.config_path = os.path.join(BASE_PATH, 'configs', 'action_sequencer_config.json')
        self.default_config = {
            'output_path': '',
            'output_prefix': '',
            'output_suffix': '',
            'enable_file_watcher': True,
            'watch_timeout': 30
        }
        self.config = self.load()
    
    def load(self):
        if not os.path.exists(self.config_path):
            try:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.default_config, f, indent=4, ensure_ascii=False)
                print(f'Created action sequencer config: {self.config_path}')
            except Exception as e:
                print(f'Failed to create config: {e}')
                return self.default_config.copy()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for key in self.default_config:
                    if key not in loaded:
                        loaded[key] = self.default_config[key]
                return loaded
        except Exception as e:
            print(f'Failed to load config: {e}')
            return self.default_config.copy()
    
    def save(self):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f'Failed to save config: {e}')
            return False
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        return self.save()
