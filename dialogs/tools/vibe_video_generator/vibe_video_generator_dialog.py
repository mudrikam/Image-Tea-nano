import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QShowEvent
import qtawesome as qta
from config import BASE_PATH
from ui.api_key_section import ApiKeySectionWidget
from database.db_operation import ImageTeaDB
from dialogs.tools.vibe_video_generator.prompts_widget import PromptsWidget
from dialogs.tools.vibe_video_generator.collections_widget import CollectionsWidget
from dialogs.tools.vibe_video_generator.scripts_widget import ScriptsWidget


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

        self._setup_ui()
        self._check_member_mode()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)

        self.api_key_section = ApiKeySectionWidget(self.db, self)
        main_layout.addWidget(self.api_key_section)
        self.api_key_section.api_key_changed.connect(self._on_api_key_changed)
        self.api_key = self.api_key_section.get_current_api_key()
        self.selected_service = self.api_key_section.get_current_service()
        self.selected_model_name = self.api_key_section.get_current_model()

        self.prompts_widget = PromptsWidget(self)
        prompts_tabs = QTabWidget()
        prompts_tabs.addTab(self.prompts_widget, qta.icon('fa6s.message'), 'Prompts')
        main_layout.addWidget(prompts_tabs)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.collections_widget = CollectionsWidget(self)
        left_tabs = QTabWidget()
        left_tabs.addTab(self.collections_widget, qta.icon('fa6s.folder-open'), 'Collections')
        splitter.addWidget(left_tabs)

        self.scripts_widget = ScriptsWidget(self)
        right_tabs = QTabWidget()
        right_tabs.addTab(self.scripts_widget, qta.icon('fa6s.code'), 'Scripts')
        splitter.addWidget(right_tabs)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([280, 620])

        main_layout.addWidget(splitter, 1)

    def _check_member_mode(self):
        from helpers.members_helper.members_helper import is_logged_in, get_member_api_config, is_member_secret_valid
        if not is_logged_in():
            if self._member_mode:
                self._member_mode = False
                self.api_key_section.setVisible(True)
                self.api_key = self.api_key_section.get_current_api_key()
                self.selected_service = self.api_key_section.get_current_service()
                self.selected_model_name = self.api_key_section.get_current_model()
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

    def _on_api_key_changed(self, api_key, service, model):
        if self._member_mode:
            return
        self.api_key = api_key
        self.selected_service = service
        self.selected_model_name = model
        if self.api_key_changed:
            self.api_key_changed.emit(api_key, service, model)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self._check_member_mode()
