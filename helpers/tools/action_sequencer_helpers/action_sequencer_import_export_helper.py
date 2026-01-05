import json
import os
from datetime import datetime
from database.db_operation import ImageTeaDB


class ActionSequencerImportExport:
    IDENTIFIER = "IMAGE_TEA_ACTION_SEQUENCER"
    
    def __init__(self):
        self.db = ImageTeaDB()
    
    def export_preset(self, preset_id, output_path):
        """Export single preset to JSON file
        
        Args:
            preset_id: Preset ID to export
            output_path: Path to save JSON file
        
        Returns:
            bool: True if successful
        """
        try:
            preset_data = self._collect_preset_data(preset_id)
            if not preset_data:
                return False
            
            export_data = {
                "identifier": self.IDENTIFIER,
                "file_type": "preset",
                "export_date": datetime.now().isoformat(),
                "version": "1.0",
                "presets": [preset_data]
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Export preset error: {e}")
            return False
    
    def export_presets(self, preset_ids, output_path):
        """Export multiple presets to JSON file
        
        Args:
            preset_ids: List of preset IDs to export
            output_path: Path to save JSON file
        
        Returns:
            bool: True if successful
        """
        try:
            presets_data = []
            for preset_id in preset_ids:
                preset_data = self._collect_preset_data(preset_id)
                if preset_data:
                    presets_data.append(preset_data)
            
            if not presets_data:
                return False
            
            export_data = {
                "identifier": self.IDENTIFIER,
                "file_type": "preset",
                "export_date": datetime.now().isoformat(),
                "version": "1.0",
                "presets": presets_data
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Export presets error: {e}")
            return False
    
    def _collect_preset_data(self, preset_id):
        """Collect all data needed to rebuild a preset
        
        Args:
            preset_id: Preset ID
        
        Returns:
            dict: Complete preset data including platform, actions, steps
        """
        try:
            preset = self.db.get_preset_by_id(preset_id)
            if not preset:
                return None
            
            platform = self.db.get_platform_by_id(preset['platform_id'])
            if not platform:
                return None
            
            preset_steps = self.db.get_preset_steps(preset_id)
            
            action_sets_map = {}
            actions_data = []
            
            for step in preset_steps:
                action = self.db.get_action_by_id(step['action_id'])
                if action:
                    action_set_id = action['action_set_id']
                    
                    if action_set_id not in action_sets_map:
                        action_set = self.db.get_action_set_by_id(action_set_id)
                        if action_set:
                            action_sets_map[action_set_id] = {
                                'name': action_set['name'],
                                'description': action_set['description']
                            }
                    
                    actions_data.append({
                        'action_set_name': action_sets_map.get(action_set_id, {}).get('name', ''),
                        'name': action.get('name', 'Action'),
                        'type': action.get('type', 'Action'),
                        'icon': action.get('icon', ''),
                        'color': action.get('color', '#888888'),
                        'delay': action.get('delay', 0),
                        'javascript_code': action.get('javascript_code', ''),
                        'export_format': action.get('export_format', ''),
                        'export_setting': action.get('export_setting', 100),
                        'order_in_preset': step['order_index']
                    })
            
            return {
                'preset_name': preset['name'],
                'preset_description': preset['description'],
                'preset_type': preset['type'],
                'platform_name': platform['name'],
                'platform_note': platform.get('note', ''),
                'action_sets': list(action_sets_map.values()),
                'actions': actions_data
            }
        except Exception as e:
            print(f"Collect preset data error: {e}")
            return None
    
    def export_action_set(self, action_set_id, output_path):
        """Export single action set to JSON file
        
        Args:
            action_set_id: Action set ID to export
            output_path: Path to save JSON file
        
        Returns:
            bool: True if successful
        """
        try:
            action_set_data = self._collect_action_set_data(action_set_id)
            if not action_set_data:
                return False
            
            export_data = {
                "identifier": self.IDENTIFIER,
                "file_type": "action_set",
                "export_date": datetime.now().isoformat(),
                "version": "1.0",
                "action_sets": [action_set_data]
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Export action set error: {e}")
            return False
    
    def export_action_sets(self, action_set_ids, output_path):
        """Export multiple action sets to JSON file
        
        Args:
            action_set_ids: List of action set IDs to export
            output_path: Path to save JSON file
        
        Returns:
            bool: True if successful
        """
        try:
            action_sets_data = []
            for action_set_id in action_set_ids:
                action_set_data = self._collect_action_set_data(action_set_id)
                if action_set_data:
                    action_sets_data.append(action_set_data)
            
            if not action_sets_data:
                return False
            
            export_data = {
                "identifier": self.IDENTIFIER,
                "file_type": "action_set",
                "export_date": datetime.now().isoformat(),
                "version": "1.0",
                "action_sets": action_sets_data
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Export action sets error: {e}")
            return False
    
    def _collect_action_set_data(self, action_set_id):
        """Collect all data needed to rebuild an action set
        
        Args:
            action_set_id: Action set ID
        
        Returns:
            dict: Complete action set data including platform and actions
        """
        try:
            action_set = self.db.get_action_set_by_id(action_set_id)
            if not action_set:
                return None
            
            platform = self.db.get_platform_by_id(action_set['platform_id'])
            if not platform:
                return None
            
            actions = self.db.get_actions_by_action_set(action_set_id)
            
            actions_data = []
            for action in actions:
                actions_data.append({
                    'name': action.get('name', 'Action'),
                    'type': action.get('type', 'Action'),
                    'icon': action.get('icon', ''),
                    'color': action.get('color', '#888888'),
                    'delay': action.get('delay', 0),
                    'javascript_code': action.get('javascript_code', ''),
                    'export_format': action.get('export_format', ''),
                    'export_setting': action.get('export_setting', 100),
                    'order_index': action.get('order_index', 0)
                })
            
            return {
                'action_set_name': action_set['name'],
                'action_set_description': action_set['description'],
                'platform_name': platform['name'],
                'platform_note': platform.get('note', ''),
                'actions': actions_data
            }
        except Exception as e:
            print(f"Collect action set data error: {e}")
            return None
    
    def import_action_sets(self, json_path):
        """Import action sets from JSON file
        
        Args:
            json_path: Path to JSON file
        
        Returns:
            tuple: (success: bool, message: str, imported_count: int)
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data.get('identifier') != self.IDENTIFIER:
                return False, "Invalid JSON file. This file is not from Image Tea Action Sequencer.", 0

            file_type = data.get('file_type')
            if not file_type:
                return False, "Missing 'file_type' in JSON. Use a valid Action Sequencer export.", 0

            if file_type != 'action_set':
                shown_type = (file_type or 'unknown').replace('_', ' ').title()
                return False, f"This file contains '{shown_type}' data. Please import it from the Action Sets tab.", 0
            
            action_sets = data.get('action_sets', [])
            if not action_sets:
                return False, "No action sets found in JSON file.", 0
            
            imported_count = 0
            for action_set_data in action_sets:
                if self._import_single_action_set(action_set_data):
                    imported_count += 1
            
            if imported_count > 0:
                return True, f"Successfully imported {imported_count} action set(s).", imported_count
            else:
                return False, "Failed to import any action sets.", 0
        
        except json.JSONDecodeError:
            return False, "Invalid JSON format.", 0
        except Exception as e:
            return False, f"Import error: {str(e)}", 0
    
    def _import_single_action_set(self, action_set_data):
        """Import single action set data to database
        
        Args:
            action_set_data: Action set data dict from JSON
        
        Returns:
            bool: True if successful
        """
        try:
            platform_name = action_set_data.get('platform_name')
            if not platform_name:
                return False
            
            platform = self._get_or_create_platform(
                platform_name,
                action_set_data.get('platform_note', '')
            )
            if not platform:
                return False
            
            platform_id = platform['id']
            
            action_set_name = action_set_data.get('action_set_name', 'Imported Action Set')
            action_set = self._get_or_create_action_set(platform_id, action_set_name)
            
            if not action_set:
                return False
            
            action_set_id = action_set['id']
            
            actions_data = action_set_data.get('actions', [])
            actions_data.sort(key=lambda x: x.get('order_index', 0))
            
            for action_data in actions_data:
                self._get_or_create_action(
                    action_set_id,
                    action_data.get('name', 'Action'),
                    action_data.get('icon', ''),
                    action_data.get('color', '#888888'),
                    action_data.get('type', 'Action'),
                    action_data.get('delay', 0),
                    action_data.get('javascript_code', ''),
                    action_data.get('export_format', None),
                    action_data.get('export_setting', 100)
                )
            
            return True
        except Exception as e:
            print(f"Import single action set error: {e}")
            return False
    
    def import_presets(self, json_path):
        """Import presets from JSON file
        
        Args:
            json_path: Path to JSON file
        
        Returns:
            tuple: (success: bool, message: str, imported_count: int)
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data.get('identifier') != self.IDENTIFIER:
                return False, "Invalid JSON file. This file is not from Image Tea Action Sequencer.", 0

            file_type = data.get('file_type')
            if not file_type:
                return False, "Missing 'file_type' in JSON. Use a valid Action Sequencer export.", 0

            if file_type != 'preset':
                shown_type = (file_type or 'unknown').replace('_', ' ').title()
                return False, f"This file contains '{shown_type}' data. Please import it from the Presets tab.", 0
            
            presets = data.get('presets', [])
            if not presets:
                return False, "No presets found in JSON file.", 0
            
            imported_count = 0
            for preset_data in presets:
                if self._import_single_preset(preset_data):
                    imported_count += 1
            
            if imported_count > 0:
                return True, f"Successfully imported {imported_count} preset(s).", imported_count
            else:
                return False, "Failed to import any presets.", 0
        
        except json.JSONDecodeError:
            return False, "Invalid JSON format.", 0
        except Exception as e:
            return False, f"Import error: {str(e)}", 0
    
    def _import_single_preset(self, preset_data):
        """Import single preset data to database
        
        Args:
            preset_data: Preset data dict from JSON
        
        Returns:
            bool: True if successful
        """
        try:
            platform_name = preset_data.get('platform_name')
            if not platform_name:
                return False
            
            platform = self._get_or_create_platform(
                platform_name, 
                preset_data.get('platform_note', '')
            )
            if not platform:
                return False
            
            platform_id = platform['id']
            
            preset_name = self._get_unique_preset_name(
                preset_data.get('preset_name', 'Imported Preset'),
                platform_id
            )
            
            preset_id = self.db.add_preset(
                platform_id,
                preset_name,
                preset_data.get('preset_description', ''),
                preset_data.get('preset_type', 'Batch')
            )
            
            actions_data = preset_data.get('actions', [])
            actions_data.sort(key=lambda x: x.get('order_in_preset', 0))
            
            for idx, action_data in enumerate(actions_data):
                action_set_name = action_data.get('action_set_name', 'Imported Actions')
                
                action_set = self._get_or_create_action_set(
                    platform_id,
                    action_set_name
                )
                if not action_set:
                    continue
                
                action_set_id = action_set['id']
                
                action = self._get_or_create_action(
                    action_set_id,
                    action_data.get('name', 'Action'),
                    action_data.get('icon', ''),
                    action_data.get('color', '#888888'),
                    action_data.get('type', 'Action'),
                    action_data.get('delay', 0),
                    action_data.get('javascript_code', ''),
                    action_data.get('export_format', None),
                    action_data.get('export_setting', 100)
                )
                
                if action:
                    # Place non-export actions before any Export step; Export actions append to end
                    if action.get('type') == 'Export':
                        self.db.add_preset_step(preset_id, action['id'])
                    else:
                        existing_steps = self.db.get_preset_steps(preset_id)
                        insert_pos = None
                        for s in existing_steps:
                            existing_action = self.db.get_action_by_id(s['action_id'])
                            if existing_action and existing_action.get('type') == 'Export':
                                insert_pos = s['order_index']
                                break
                        if insert_pos:
                            self.db.add_preset_step(preset_id, action['id'], insert_at=insert_pos)
                        else:
                            self.db.add_preset_step(preset_id, action['id'])
            
            return True
        except Exception as e:
            print(f"Import single preset error: {e}")
            return False
    
    def _get_or_create_platform(self, platform_name, platform_note=''):
        """Get existing platform or create if not exists
        
        Args:
            platform_name: Platform name
            platform_note: Platform note
        
        Returns:
            dict: Platform data
        """
        platforms = self.db.get_all_platforms()
        for platform in platforms:
            if platform['name'] == platform_name:
                return platform
        
        platform_id = self.db.add_platform(platform_name, '', platform_note)
        return self.db.get_platform_by_id(platform_id)
    
    def _get_or_create_action_set(self, platform_id, action_set_name):
        """Get existing action set or create if not exists
        
        Args:
            platform_id: Platform ID
            action_set_name: Action set name
        
        Returns:
            dict: Action set data
        """
        action_sets = self.db.get_action_sets_by_platform(platform_id)
        for action_set in action_sets:
            if action_set['name'] == action_set_name:
                return action_set
        
        action_set_id = self.db.add_action_set(platform_id, action_set_name, '')
        return self.db.get_action_set_by_id(action_set_id)
    
    def _get_or_create_action(self, action_set_id, name, icon, color, action_type, delay, javascript_code, export_format, export_setting=100):
        """Get existing action or create if not exists
        
        Args:
            action_set_id: Action set ID
            name: Action name
            icon: Icon string
            color: Color hex
            action_type: Action type
            delay: Delay ms
            javascript_code: JS code
            export_format: Export format
            export_setting: Export setting (compression or version)
        
        Returns:
            dict: Action data
        """
        if export_format == 'EPS':
            if isinstance(export_setting, str):
                try:
                    export_setting = int(export_setting)
                except (ValueError, TypeError):
                    export_setting = 8
            if not isinstance(export_setting, int) or export_setting < 0 or export_setting > 12:
                export_setting = 8
        
        actions = self.db.get_actions_by_action_set(action_set_id)
        for action in actions:
            if action['name'] == name and action['type'] == action_type:
                return action
        
        action_id = self.db.add_action(
            action_set_id,
            name,
            icon,
            color,
            action_type,
            delay,
            javascript_code,
            export_format,
            export_setting
        )
        return self.db.get_action_by_id(action_id)
    
    def _get_unique_preset_name(self, base_name, platform_id):
        """Generate unique preset name by adding _n suffix if needed
        
        Args:
            base_name: Base preset name
            platform_id: Platform ID
        
        Returns:
            str: Unique preset name
        """
        existing_presets = self.db.get_presets_by_platform(platform_id)
        existing_names = [p['name'] for p in existing_presets]
        
        if base_name not in existing_names:
            return base_name
        
        counter = 1
        while f"{base_name}_{counter}" in existing_names:
            counter += 1
        
        return f"{base_name}_{counter}"
