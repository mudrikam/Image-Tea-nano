import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QSplitter, QTabWidget, QWidget, QPushButton
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
from helpers.members_helper.members_helper import is_logged_in, is_membership_expired
from dialogs.member_required_dialog import MemberRequiredDialog
from dialogs.membership_expired_dialog import MembershipExpiredDialog


class VibeVideoGeneratorDialog(QDialog):
    api_key_changed = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Vibe Video Generator (Remotion)')
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.resize(1000, 650)
        self.setMinimumSize(700, 500)
        self._is_closing = False

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.db = ImageTeaDB()
        self.api_key = ''
        self.selected_service = ''
        self.selected_model_name = ''
        self.selected_endpoint = ''

        self._setup_ui()

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        # Reset closing flag and ensure server state is clean when dialog is shown again
        if hasattr(self, 'preview_tab_widget') and self.preview_tab_widget:
            self.preview_tab_widget._is_closing = False
            self.preview_tab_widget._server_starting = False
            self.preview_tab_widget._server_running = False
            self.preview_tab_widget._update_toggle_server_button()
        if not is_logged_in():
            QTimer.singleShot(0, self._show_member_required)
        elif is_membership_expired():
            QTimer.singleShot(0, self._show_membership_expired)

    def _show_member_required(self):
        dlg = MemberRequiredDialog("Vibe Video Generator is only accessible to logged-in members.", self)
        if dlg.exec() == MemberRequiredDialog.Accepted:
            from dialogs.members.member_login_dialog import MemberLoginDialog
            login_dlg = MemberLoginDialog(self)
            if login_dlg.exec() != MemberLoginDialog.Accepted:
                self.close()
        else:
            self.close()

    def _show_membership_expired(self):
        dlg = MembershipExpiredDialog(self)
        dlg.exec()
        self.close()

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
        self.render_settings_tab_widget.settings_changed.connect(self._refresh_preview_after_save)
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
        self.scripts_widget.api_key_changed_from_dialog.connect(self._sync_api_key_from_dialog)
        self.menu_widget.new_script_requested.connect(self._on_new_script_created)
        self.menu_widget.render_script_requested.connect(self.code_actions_widget._on_render_clicked)
        # Batch render: collection render request
        self.collections_widget.render_collection_requested.connect(self.code_actions_widget.start_batch_render)

        # Lock UI during rendering
        self.code_actions_widget.rendering_started.connect(self._on_rendering_started)
        self.code_actions_widget.rendering_finished.connect(self._on_rendering_finished)

        # Provide references using setter methods to connect signals
        self.menu_widget.set_collections_widget(self.collections_widget)
        self.menu_widget.set_scripts_widget(self.scripts_widget)

        # Connect duration change in Actions tab to auto-refresh preview
        self.code_actions_widget.duration_changed.connect(self._on_actions_duration_changed)

    def _on_new_script_created(self, collection_id):
        self.collections_widget.load_collections()

    def _on_collection_selected(self, data):
        if not data:
            self.scripts_widget.display_script(None)
            return
        if data.get('type') == 'script':
            self.scripts_widget.display_script(data)

    def _on_script_updated(self, script_data):
        try:
            self.collections_widget.load_collections()
        except Exception as e:
            print(f"[Vibe Video] Error reloading collections: {e}")
        # ScriptsWidget has already updated its own UI (content & label) before emitting this signal
        
        # Automatically refresh Remotion preview by re-selecting the current script
        self._refresh_preview_after_save()

    def _sync_api_key_from_dialog(self, api_key, service, model):
        # Update the main api_key_section quietly (blocks recursive signals if needed)
        self.api_key_section.set_current_api_by_details(api_key, service, model, skip_refresh=False)

    def _on_api_key_changed(self, api_key, service, model):
        self.api_key = api_key
        self.selected_service = service
        self.selected_model_name = model
        self.selected_endpoint = self.api_key_section.api_key_map.get(api_key, {}).get('endpoint', '') if api_key else ''
        self.code_actions_widget.set_ai_credentials(self.api_key, self.selected_endpoint, self.selected_service, self.selected_model_name)
        self.scripts_widget.set_ai_credentials(self.api_key, self.selected_endpoint, self.selected_service, self.selected_model_name)
        if self.api_key_changed:
            self.api_key_changed.emit(api_key, service, model)

    def _refresh_preview_after_save(self):
        """Refresh Remotion preview after script save by re-selecting current script."""
        preview_tab = self.preview_tab_widget
        if not preview_tab or not preview_tab._scripts_widget:
            return
        preview_tab._process_pending_script_selection()

    def _on_actions_duration_changed(self, new_duration):
        """Auto-refresh preview when duration seconds spinner changes (on Enter or mouse wheel)."""
        # Re-select the currently displayed script to trigger preview refresh
        current_script_id = self.scripts_widget.current_script_id
        if current_script_id and self.scripts_widget.db:
            script_data = self.scripts_widget.db.get_remotion_script(current_script_id)
            if script_data:
                self.scripts_widget.display_script(script_data)

    def _on_rendering_started(self):
        """Disable interactive UI elements during rendering."""
        if self._is_closing:
            return
        self.collections_widget.setEnabled(False)
        self.scripts_widget.setEnabled(False)
        self.code_actions_widget.enter_render_mode()
        self.preview_tab_widget.setEnabled(False)
        self.output_tab_widget.setEnabled(False)
        self.render_settings_tab_widget.setEnabled(False)
        if hasattr(self.menu_widget, 'new_script_action'):
            self.menu_widget.new_script_action.setEnabled(False)

    def _on_rendering_finished(self):
        """Re-enable UI elements after rendering completes."""
        if self._is_closing:
            return
        self.collections_widget.setEnabled(True)
        self.scripts_widget.setEnabled(True)
        self.code_actions_widget.exit_render_mode()
        self.preview_tab_widget.setEnabled(True)
        self.output_tab_widget.setEnabled(True)
        self.render_settings_tab_widget.setEnabled(True)
        if hasattr(self.menu_widget, 'new_script_action'):
            self.menu_widget.new_script_action.setEnabled(True)
        # Refresh preview tab button states based on current selection
        self.preview_tab_widget._process_pending_script_selection()

    def closeEvent(self, event):
        self._is_closing = True
        # Cancel rendering if active to prevent stray threads
        if hasattr(self.code_actions_widget, '_render_worker') and self.code_actions_widget._render_worker:
            worker = self.code_actions_widget._render_worker
            if worker.isRunning():
                worker.cancel()
                worker.wait(2000)  # wait up to 2s for clean termination
        # Cancel batch rendering if active
        if hasattr(self.code_actions_widget, '_batch_render_worker') and self.code_actions_widget._batch_render_worker:
            worker = self.code_actions_widget._batch_render_worker
            if worker.isRunning():
                worker.cancel()
                worker.wait(2000)
        # Mark preview tab as closing before stopping its workers
        self.preview_tab_widget._is_closing = True
        self.preview_tab_widget._stop_server()
        if hasattr(self.scripts_widget, 'cleanup'):
            self.scripts_widget.cleanup()
        super().closeEvent(event)
