import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QSplitter, QTabWidget, QWidget, QPushButton
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
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
from dialogs.tools.vibe_video_generator.vibe_video_refine_panel import RefinePanel
from helpers.members_helper.members_helper import is_logged_in, is_membership_expired
from dialogs.member_required_dialog import MemberRequiredDialog
from dialogs.membership_expired_dialog import MembershipExpiredDialog


class _RemotionUpdateWorker(QThread):
    """Background worker that reinstalls the bundled Remotion tool."""

    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import os
        from config import BASE_PATH
        from tools.tools_checker import download_and_install_remotion, _cleanup_remotion_folder

        remotion_folder = os.path.join(BASE_PATH, "tools", "remotion")

        def reporter(msg):
            if self._cancelled:
                return
            self.progress.emit(msg)

        def unit_callback():
            if self._cancelled:
                return

        try:
            # Full reinstall: wipe the existing folder first.
            _cleanup_remotion_folder(remotion_folder)
            ok = download_and_install_remotion(
                remotion_folder,
                reporter=reporter,
                progress_reporter=None,
                unit_callback=unit_callback,
            )
            if ok:
                self.finished.emit(True, "Remotion updated successfully.")
            else:
                self.finished.emit(False, "Remotion update failed. See logs for details.")
        except Exception as e:
            self.finished.emit(False, f"Remotion update error: {e}")


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
        self._remotion_update_worker = None
        self._remotion_update_progress = None
        self.selected_endpoint = ''

        self._setup_ui()

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        # Reset state only if dialog was previously closed (not just hidden)
        if self._is_closing:
            if hasattr(self, 'preview_tab_widget') and self.preview_tab_widget:
                # Clear shutdown flags and ensure clean state for fresh start
                self.preview_tab_widget._is_closing = False
                self.preview_tab_widget._server_starting = False
                self.preview_tab_widget._server_running = False
                self.preview_tab_widget._update_toggle_server_button()
            self._is_closing = False
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
        dlg = MembershipExpiredDialog(self, tool_name="Vibe Video Generator")
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

        self.refine_panel = RefinePanel(self)
        self.refine_panel.setMinimumWidth(280)
        self.refine_panel.setVisible(False)
        splitter.addWidget(self.refine_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([240, 560, 0])

        main_layout.addWidget(splitter, 1)

        self.code_actions_widget = CodeActionsWidget(self)
        main_layout.addWidget(self.code_actions_widget)

        self.code_actions_widget.set_render_settings_tab(self.render_settings_tab_widget)
        self.code_actions_widget.set_scripts_widget(self.scripts_widget)
        self.code_actions_widget.set_output_tab_widget(self.output_tab_widget)
        self.code_actions_widget.set_ai_credentials(self.api_key, self.selected_endpoint, self.selected_service, self.selected_model_name)
        self.scripts_widget.set_ai_credentials(self.api_key, self.selected_endpoint, self.selected_service, self.selected_model_name)
        self.preview_tab_widget.set_scripts_widget(self.scripts_widget)
        self.scripts_widget.set_refine_panel(self.refine_panel)
        self.refine_panel.submit_requested.connect(self.scripts_widget.refine_instruction)
        self.refine_panel.retry_requested.connect(self.scripts_widget.retry_refine)
        self.refine_panel.fix_errors_requested.connect(self._fix_preview_errors)
        self.refine_panel.interrupt_requested.connect(self.scripts_widget._on_interrupt)
        self.refine_panel.new_session_requested.connect(self.scripts_widget.clear_refine_session)
        self.refine_panel.clear_session_requested.connect(self.scripts_widget.clear_refine_session)
        self.refine_panel.hide_requested.connect(self._hide_refine_panel)
        self.preview_tab_widget.error_detected.connect(self._on_preview_error)

        # Connect signals
        self.collections_widget.collection_selected.connect(self._on_collection_selected)
        self.scripts_widget.script_updated.connect(self._on_script_updated)
        self.menu_widget.new_script_requested.connect(self._on_new_script_created)
        self.menu_widget.render_script_requested.connect(self.code_actions_widget._on_render_clicked)
        self.menu_widget.update_remotion_requested.connect(self._on_update_remotion)
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

    def show_refine_panel(self):
        self.refine_panel.setVisible(True)
        self.refine_panel.raise_()
        sizes = self.refine_panel.parentWidget().sizes()
        if sizes and sizes[-1] == 0:
            self.refine_panel.parentWidget().setSizes([sizes[0], sizes[1], 340])

    def _hide_refine_panel(self):
        self.refine_panel.setVisible(False)

    def _on_preview_error(self, error):
        error = str(error or '').strip()
        self.show_refine_panel()
        self.refine_panel.add_status(f'Remotion error: {error}', False)
        self.refine_panel.show_fix_errors(True)
        # Repair is NOT automatic: the user must click "Fix Errors" to send the
        # error to the AI. Only surface the error and enable the action button.

    def _fix_preview_errors(self):
        self.scripts_widget.fix_preview_error(self.preview_tab_widget._last_error)

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

    def _on_update_remotion(self):
        """Reinstall / update the bundled Remotion tool in a background thread."""
        if self._remotion_update_worker is not None and self._remotion_update_worker.isRunning():
            return

        self.menu_widget.update_remotion_action.setEnabled(False)
        self.menu_widget.update_remotion_action.setText('Updating...')

        from PySide6.QtWidgets import QProgressDialog
        self._remotion_update_progress = QProgressDialog('Updating Remotion...', 'Cancel', 0, 0, self)
        self._remotion_update_progress.setWindowModality(Qt.WindowModal)
        self._remotion_update_progress.setMinimumDuration(0)
        self._remotion_update_progress.setMaximum(0)
        self._remotion_update_progress.canceled.connect(self._on_remotion_update_cancelled)
        self._remotion_update_progress.show()

        self._remotion_update_worker = _RemotionUpdateWorker(self)
        self._remotion_update_worker.progress.connect(self._on_remotion_update_progress)
        self._remotion_update_worker.finished.connect(self._on_remotion_update_done)
        self._remotion_update_worker.start()

    def _on_remotion_update_progress(self, message):
        if self._remotion_update_progress:
            self._remotion_update_progress.setLabelText(message)

    def _on_remotion_update_cancelled(self):
        if self._remotion_update_worker is not None:
            self._remotion_update_worker.cancel()

    def _on_remotion_update_done(self, success, message):
        progress = self._remotion_update_progress
        self._remotion_update_progress = None
        if progress is not None:
            progress.canceled.disconnect()
            progress.close()
            progress.deleteLater()
        if self._remotion_update_worker is not None:
            self._remotion_update_worker.deleteLater()
            self._remotion_update_worker = None
        self.menu_widget.update_remotion_action.setEnabled(True)
        self.menu_widget.update_remotion_action.setText('Update Remotion')
        from PySide6.QtWidgets import QMessageBox
        if success:
            QMessageBox.information(self, 'Update Remotion', message)
        else:
            QMessageBox.critical(self, 'Update Remotion', message)

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
        # Cancel Remotion update worker if active
        if self._remotion_update_worker is not None and self._remotion_update_worker.isRunning():
            self._remotion_update_worker.cancel()
            if self._remotion_update_progress is not None:
                self._remotion_update_progress.close()
                self._remotion_update_progress.deleteLater()
            self._remotion_update_progress = None
            try:
                self._remotion_update_worker.wait(2000)
            except Exception:
                pass
        # Mark preview tab as closing before stopping its workers
        self.preview_tab_widget._is_closing = True
        self.preview_tab_widget._stop_server()
        if hasattr(self.scripts_widget, 'cleanup'):
            self.scripts_widget.cleanup()
        super().closeEvent(event)
