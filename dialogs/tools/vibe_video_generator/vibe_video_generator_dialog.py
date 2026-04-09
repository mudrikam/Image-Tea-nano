import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QSplitter, QTabWidget, QWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QShowEvent
import qtawesome as qta
from config import BASE_PATH
from ui.api_key_section import ApiKeySectionWidget
from database.db_operation import ImageTeaDB
from dialogs.tools.vibe_video_generator.vibe_video_menu_widget import MenuWidget
from dialogs.tools.vibe_video_generator.vibe_video_collections_widget import CollectionsWidget
from dialogs.tools.vibe_video_generator.vibe_video_scripts_widget import ScriptsWidget
from dialogs.tools.vibe_video_generator.vibe_code_actions_widget import CodeActionsWidget
from dialogs.tools.vibe_video_generator.vibe_video_output_tab import OutputTabWidget
from dialogs.tools.vibe_video_generator.vibe_video_render_settings_tab import RenderSettingsTabWidget
from dialogs.tools.vibe_video_generator.vibe_video_preview_tab import PreviewTabWidget
from helpers.members_helper.members_helper import is_logged_in, get_member_api_config, is_member_secret_valid


class VibeVideoGeneratorDialog(QDialog):
    api_key_changed = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Vibe Video Generator')
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.resize(900, 650)
        self.setMinimumSize(700, 500)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.db = ImageTeaDB()
        self._member_mode = False
        self.api_key = ''
        self.selected_service = ''
        self.selected_model_name = ''
        self.selected_endpoint = ''

        self._setup_ui()
        QTimer.singleShot(100, self._check_member_mode)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self._check_member_mode()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)

        self.menu_widget = MenuWidget(self)
        main_layout.addWidget(self.menu_widget)

        self.api_key_section = ApiKeySectionWidget(self.db, self)
        main_layout.addWidget(self.api_key_section)
        self.api_key_section.api_key_changed.connect(self._on_api_key_changed)
        self.api_key = self.api_key_section.get_current_api_key()
        self.selected_service = self.api_key_section.get_current_service()
        self.selected_model_name = self.api_key_section.get_current_model()
        self.selected_endpoint = self.api_key_section.api_key_map.get(self.api_key, {}).get('endpoint', '') if self.api_key else ''

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.collections_widget = CollectionsWidget(self)
        left_tabs = QTabWidget()
        left_tabs.addTab(self.collections_widget, qta.icon('fa6s.folder-open'), 'Collections')
        splitter.addWidget(left_tabs)

        self.scripts_widget = ScriptsWidget(self)
        self.output_tab_widget = OutputTabWidget(self)
        self.render_settings_tab_widget = RenderSettingsTabWidget(self)
        self.preview_tab_widget = PreviewTabWidget(self)
        right_tabs = QTabWidget()
        right_tabs.addTab(self.scripts_widget, qta.icon('fa6s.code'), 'TypeScript')
        right_tabs.addTab(self.preview_tab_widget, qta.icon('fa6s.circle-play'), 'Preview')
        right_tabs.addTab(self.output_tab_widget, qta.icon('fa6s.folder'), 'Output')
        right_tabs.addTab(self.render_settings_tab_widget, qta.icon('fa6s.gear'), 'Render Settings')
        splitter.addWidget(right_tabs)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([280, 620])

        main_layout.addWidget(splitter, 1)

        self.code_actions_widget = CodeActionsWidget(self)
        main_layout.addWidget(self.code_actions_widget)

        self.code_actions_widget.set_render_settings_tab(self.render_settings_tab_widget)
        self.code_actions_widget.set_scripts_widget(self.scripts_widget)
        self.code_actions_widget.set_output_tab_widget(self.output_tab_widget)
        self.code_actions_widget.set_ai_credentials(self.api_key, self.selected_endpoint, self.selected_service, self.selected_model_name)
        self.scripts_widget.set_ai_credentials(self.api_key, self.selected_endpoint, self.selected_service, self.selected_model_name)
        self.preview_tab_widget.set_scripts_widget(self.scripts_widget)

        # Connect signals
        self.collections_widget.collection_selected.connect(self._on_collection_selected)
        self.scripts_widget.script_updated.connect(self._on_script_updated)
        self.menu_widget.new_script_requested.connect(self._on_new_script_created)

        # Provide references
        self.menu_widget.collections_widget = self.collections_widget
        self.menu_widget.scripts_widget = self.scripts_widget

    def _check_member_mode(self):
        if not is_logged_in():
            if self._member_mode:
                self._member_mode = False
                self.api_key_section.setVisible(True)
                self.api_key = self.api_key_section.get_current_api_key()
                self.selected_service = self.api_key_section.get_current_service()
                self.selected_model_name = self.api_key_section.get_current_model()
                self.selected_endpoint = self.api_key_section.api_key_map.get(self.api_key, {}).get('endpoint', '') if self.api_key else ''
            return
        if not is_member_secret_valid():
            if self._member_mode:
                self._member_mode = False
                self.api_key_section.setVisible(True)
            return
        if not self._member_mode:
            self._member_mode = True
            self.api_key_section.setVisible(False)
            member_cfg = get_member_api_config()
            self.api_key = member_cfg['api_key']
            self.selected_service = member_cfg['service_type'] or 'custom'
            self.selected_model_name = member_cfg['model']
            self.selected_endpoint = member_cfg.get('endpoint', '')

    def _on_new_script_created(self, collection_id):
        self.collections_widget.load_collections()

    def _on_collection_selected(self, data):
        if not data:
            self.scripts_widget.display_script(None)
            return
        if data.get('type') == 'script':
            self.scripts_widget.display_script(data)

    def _on_script_updated(self, script_data):
        self.collections_widget.load_collections()
        if script_data:
            self.scripts_widget.display_script(script_data)

    def _on_api_key_changed(self, api_key, service, model):
        if self._member_mode:
            return
        self.api_key = api_key
        self.selected_service = service
        self.selected_model_name = model
        self.selected_endpoint = self.api_key_section.api_key_map.get(api_key, {}).get('endpoint', '') if api_key else ''
        self.code_actions_widget.set_ai_credentials(self.api_key, self.selected_endpoint, self.selected_service, self.selected_model_name)
        self.scripts_widget.set_ai_credentials(self.api_key, self.selected_endpoint, self.selected_service, self.selected_model_name)
        if self.api_key_changed:
            self.api_key_changed.emit(api_key, service, model)

    def closeEvent(self, event):
        self.preview_tab_widget._stop_server()
        super().closeEvent(event)
