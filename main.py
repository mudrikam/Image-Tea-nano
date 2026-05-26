import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import BASE_PATH
sys.path.insert(0, BASE_PATH)
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QDialog
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QIcon
import time
import qtawesome as qta
from ui.splash_screen_window import SplashScreen
import ui.splash_screen_window as splash_mod

def load_app_config():
    config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config

class ImageTeaMainWindow(QMainWindow):
    show_ai_unsupported_dialog = Signal(str)
    background_status = Signal(str)
    trigger_show_update_dialog = Signal()

    def __init__(self):
        super().__init__()
        config = load_app_config()
        name = config["name"]
        tagline = config["tagline"]
        version = config["version"]
        self.setWindowTitle(f"{name} - ({tagline}) - v{version}")
        icon_path = os.path.join(BASE_PATH, "res", "image_tea.ico")
        self.setWindowIcon(QIcon(icon_path))
        from database.db_operation import ImageTeaDB
        self.db = ImageTeaDB()
        self.api_key = self.db.get_api_key('gemini')
        
        # Mode tracking: 'normal' or 'tools_picker'
        self.current_mode = 'normal'
        
        # Setup main UI
        setup_ui(self)
        self.table.refresh_table()
        self.generator_thread = None
        self.is_generating = False
        self.show_ai_unsupported_dialog.connect(self._show_ai_unsupported_dialog_slot)
        self.background_status.connect(self._on_background_status)
        self.trigger_show_update_dialog.connect(self._on_show_update_dialog)
        
        # Tools picker widget will be created when needed
        self.tools_picker_widget = None

        if hasattr(self, "gen_btn"):
            self.gen_btn.clicked.disconnect()
            self.gen_btn.clicked.connect(self._on_gen_btn_clicked)

        update_token_stats_ui(self)
        
        # Remove this line - we'll store it when switching modes
        # self.main_central_widget = self.centralWidget()
        
        self.lock_file = os.path.join(BASE_PATH, "temp", "image_tea.lock")
        os.makedirs(os.path.dirname(self.lock_file), exist_ok=True)
        with open(self.lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.timeout.connect(self._check_shutdown_signal)
        self.shutdown_timer.start(500)

    def _on_show_update_dialog(self):
        from helpers.check_for_update_helper import show_update_dialog_if_available
        show_update_dialog_if_available(parent=self)

    def _show_ai_unsupported_dialog_slot(self, message):
        dialog = AIUnsuportedDialog(message, parent=self)
        dialog.exec()

    def _on_background_status(self, message):
        if hasattr(self, 'statusbar'):
            self.statusbar.set_status(message)
        if message.startswith("Image Tea Ready"):
            def _clear():
                try:
                    if hasattr(self, 'statusbar') and hasattr(self.statusbar, '_check_env_and_set_style'):
                        self.statusbar._check_env_and_set_style()
                except Exception:
                    pass
            QTimer.singleShot(3000, _clear)

    def _on_gen_btn_clicked(self):
        if self.is_generating:
            stop_generate_metadata(self)
        else:
            batch_generate_metadata(self)
    
    def switch_to_tools_picker(self):
        """Switch to tools picker mode"""
        if self.current_mode == 'tools_picker':
            return
        
        self.current_mode = 'tools_picker'
        
        # Create tools picker widget
        from ui.tools_picker_widget import ToolsPickerWidget
        self.tools_picker_widget = ToolsPickerWidget(self)
        self.tools_picker_widget.tool_selected.connect(self._on_tool_selected)
        
        # Hide toolbar
        if hasattr(self, 'toolbar'):
            self.toolbar.hide()
        
        # Switch to tools picker
        self.setCentralWidget(self.tools_picker_widget)
        self.tools_picker_widget.show()
        
        # Keep the statusbar from main UI for member status display
        if hasattr(self, 'statusbar'):
            self.statusbar.update_member_status()
        
        # Update menu bar
        self._setup_tools_picker_menu()
    
    def switch_to_normal(self):
        """Switch back to normal metadata generator mode"""
        if self.current_mode == 'normal':
            return
        
        self.current_mode = 'normal'
        
        # Delete tools picker widget
        if self.tools_picker_widget:
            self.tools_picker_widget.deleteLater()
            self.tools_picker_widget = None
        
        # Recreate main UI
        from ui.setup_ui import setup_ui
        setup_ui(self)
        
        # Refresh table
        if hasattr(self, 'table'):
            self.table.refresh_table()
        
        # Show toolbar
        if hasattr(self, 'toolbar'):
            self.toolbar.show()
        
        # Restore original menu bar
        from ui.main_menu import setup_main_menu
        setup_main_menu(self)
        # Refresh member menu actions to reflect current login state
        from helpers.members_helper.members_helper import is_logged_in
        logged_in = is_logged_in()
        if hasattr(self, 'login_member_action'):
            self.login_member_action.setVisible(not logged_in)
        if hasattr(self, 'register_member_action'):
            self.register_member_action.setVisible(True)
            if logged_in:
                self.register_member_action.setText("Renew Membership")
                self.register_member_action.setToolTip("Renew your Image Tea membership")
                self.register_member_action.setStatusTip("Renew your Image Tea membership")
            else:
                self.register_member_action.setText("Register")
                self.register_member_action.setToolTip("Register a new Image Tea membership account")
                self.register_member_action.setStatusTip("Register a new Image Tea membership account")
        if hasattr(self, 'check_limit_action'):
            self.check_limit_action.setVisible(logged_in)
        if hasattr(self, 'renew_secret_action'):
            self.renew_secret_action.setVisible(logged_in)
        if hasattr(self, 'logout_member_action'):
            self.logout_member_action.setVisible(logged_in)
        if hasattr(self, 'statusbar') and hasattr(self.statusbar, 'update_member_status'):
            self.statusbar.update_member_status()
    
    def _setup_tools_picker_menu(self):
        """Setup menu bar for tools picker mode"""
        from ui.main_menu import setup_tools_picker_menu
        setup_tools_picker_menu(self)
    
    def _on_tool_selected(self, tool_id):
        """Handle tool selection from tools picker"""
        # Open the selected tool (stay in tools_picker mode, user can click 'Back to Metadata Generator' manually)
        tool_handlers = {
            "image_upscaler": self._open_image_upscaler,
            "image_overlay_maker": self._open_image_overlay_maker,
            "prompted_image_sorter": self._open_prompted_image_sorter,
            "video_upscaler": self._open_video_upscaler,
            "batch_audio_remover": self._open_batch_audio_remover,
            "vibe_video_generator": self._open_vibe_video_generator,
            "action_sequencer": self._open_action_sequencer,
            "prompt_generator": self._open_prompt_generator,
            "prompt_injector": self._open_prompt_injector,
            "envato_elements": self._open_envato_elements,
            "pngtree_zipper": self._open_pngtree_zipper,
            "holiday_calendar": self._open_holiday_calendar,
            "psd_to_img": self._open_psd_to_img,
            "folder_comparator": self._open_folder_comparator,
            "batch_image_resizer": self._open_batch_image_resizer
        }

        handler = tool_handlers.get(tool_id)
        if handler:
            handler()
    
    def _open_image_upscaler(self):
        from helpers.tools_dependency_helper import check_tools_available
        if not check_tools_available(["realesrgan"], parent=self):
            return
        from dialogs.tools.image_upscaler_tool import ImageUpscalerDialog
        if not hasattr(self, '_image_upscaler_dialog') or not self._image_upscaler_dialog:
            self._image_upscaler_dialog = ImageUpscalerDialog(None)
            self._image_upscaler_dialog.destroyed.connect(lambda: setattr(self, '_image_upscaler_dialog', None))
        self._image_upscaler_dialog.show()
        self._image_upscaler_dialog.raise_()
        self._image_upscaler_dialog.activateWindow()
    
    def _open_image_overlay_maker(self):
        from dialogs.tools.image_overlay_maker_dialog import ImageOverlayMakerDialog
        if not hasattr(self, '_image_overlay_maker_dialog') or not self._image_overlay_maker_dialog:
            self._image_overlay_maker_dialog = ImageOverlayMakerDialog(None)
            self._image_overlay_maker_dialog.destroyed.connect(lambda: setattr(self, '_image_overlay_maker_dialog', None))
        self._image_overlay_maker_dialog.show()
        self._image_overlay_maker_dialog.raise_()
        self._image_overlay_maker_dialog.activateWindow()
    
    def _open_prompted_image_sorter(self):
        from helpers.members_helper.members_helper import is_logged_in
        if not is_logged_in():
            from dialogs.member_required_dialog import MemberRequiredDialog
            dlg = MemberRequiredDialog("Prompted Image Sorter is only accessible to logged-in members.", self)
            if dlg.exec() == MemberRequiredDialog.Accepted:
                from dialogs.members.member_login_dialog import MemberLoginDialog
                login_dlg = MemberLoginDialog(self)
                if login_dlg.exec() != MemberLoginDialog.Accepted:
                    return
                if not is_logged_in():
                    return
                if hasattr(self, '_apply_member_mode'):
                    self._apply_member_mode()
            else:
                return
        from dialogs.tools.prompted_image_sorter.prompted_image_sorter_tool import PromptedImageSorterTool
        if not hasattr(self, '_prompted_image_sorter_dialog') or not self._prompted_image_sorter_dialog:
            self._prompted_image_sorter_dialog = PromptedImageSorterTool(None)
            self._prompted_image_sorter_dialog.destroyed.connect(lambda: setattr(self, '_prompted_image_sorter_dialog', None))
        self._prompted_image_sorter_dialog.show()
        self._prompted_image_sorter_dialog.raise_()
        self._prompted_image_sorter_dialog.activateWindow()
    
    def _open_video_upscaler(self):
        from helpers.tools_dependency_helper import check_tools_available
        if not check_tools_available(["ffmpeg", "realesrgan"], parent=self):
            return
        from dialogs.tools.video_upscaler_tool import VideoUpscalerDialog
        if not hasattr(self, '_video_upscaler_dialog') or not self._video_upscaler_dialog:
            self._video_upscaler_dialog = VideoUpscalerDialog(None)
            self._video_upscaler_dialog.destroyed.connect(lambda: setattr(self, '_video_upscaler_dialog', None))
        self._video_upscaler_dialog.show()
        self._video_upscaler_dialog.raise_()
        self._video_upscaler_dialog.activateWindow()
    
    def _open_batch_audio_remover(self):
        from helpers.tools_dependency_helper import check_tools_available
        if not check_tools_available(["ffmpeg"], parent=self):
            return
        from dialogs.tools.batch_audio_remover import BatchAudioRemoverDialog
        dlg = BatchAudioRemoverDialog(self)
        dlg.exec()
    
    def _open_vibe_video_generator(self):
        from helpers.tools_dependency_helper import check_tools_available
        if not check_tools_available(["nodejs", "remotion"], parent=self):
            return
        from helpers.members_helper.members_helper import is_logged_in
        if not is_logged_in():
            from dialogs.member_required_dialog import MemberRequiredDialog
            dlg = MemberRequiredDialog("Vibe Video Generator is only accessible to logged-in members.", self)
            if dlg.exec() == MemberRequiredDialog.Accepted:
                from dialogs.members.member_login_dialog import MemberLoginDialog
                login_dlg = MemberLoginDialog(self)
                if login_dlg.exec() != MemberLoginDialog.Accepted:
                    return
                if not is_logged_in():
                    return
                if hasattr(self, '_apply_member_mode'):
                    self._apply_member_mode()
            else:
                return
        from dialogs.tools.vibe_video_generator.vibe_video_generator_dialog import VibeVideoGeneratorDialog
        if not hasattr(self, '_vibe_video_generator_dialog') or not self._vibe_video_generator_dialog:
            self._vibe_video_generator_dialog = VibeVideoGeneratorDialog(None)
            self._vibe_video_generator_dialog.destroyed.connect(lambda: setattr(self, '_vibe_video_generator_dialog', None))
        self._vibe_video_generator_dialog.show()
        self._vibe_video_generator_dialog.raise_()
        self._vibe_video_generator_dialog.activateWindow()
    
    def _open_action_sequencer(self):
        from dialogs.tools.action_sequencer_widgets.action_sequencer import ActionSequencerDialog
        if not hasattr(self, '_action_sequencer_dialog') or not self._action_sequencer_dialog:
            self._action_sequencer_dialog = ActionSequencerDialog(None)
            self._action_sequencer_dialog.destroyed.connect(lambda: setattr(self, '_action_sequencer_dialog', None))
        self._action_sequencer_dialog.show()
        self._action_sequencer_dialog.raise_()
        self._action_sequencer_dialog.activateWindow()

    def _open_psd_to_img(self):
        from dialogs.tools.psd_to_img_widgets.psd_to_img_dialog import PSDToIMGDialog
        if not hasattr(self, '_psd_to_img_dialog') or not self._psd_to_img_dialog:
            self._psd_to_img_dialog = PSDToIMGDialog(None)
            self._psd_to_img_dialog.destroyed.connect(lambda: setattr(self, '_psd_to_img_dialog', None))
        self._psd_to_img_dialog.show()
        self._psd_to_img_dialog.raise_()
        self._psd_to_img_dialog.activateWindow()

    def _open_folder_comparator(self):
        from dialogs.tools.folder_comparator_widgets.folder_comparator_dialog import FolderComparatorDialog
        if not hasattr(self, '_folder_comparator_dialog') or not self._folder_comparator_dialog:
            self._folder_comparator_dialog = FolderComparatorDialog(None)
            self._folder_comparator_dialog.destroyed.connect(lambda: setattr(self, '_folder_comparator_dialog', None))
        self._folder_comparator_dialog.show()
        self._folder_comparator_dialog.raise_()
        self._folder_comparator_dialog.activateWindow()

    def _open_batch_image_resizer(self):
        from dialogs.tools.batch_image_resizer_dialog import BatchImageResizerDialog
        if not hasattr(self, '_batch_image_resizer_dialog') or not self._batch_image_resizer_dialog:
            self._batch_image_resizer_dialog = BatchImageResizerDialog(None)
            self._batch_image_resizer_dialog.destroyed.connect(lambda: setattr(self, '_batch_image_resizer_dialog', None))
        self._batch_image_resizer_dialog.show()
        self._batch_image_resizer_dialog.raise_()
        self._batch_image_resizer_dialog.activateWindow()
    
    def _open_prompt_generator(self):
        from dialogs.tools.prompt_generator_tool import PromptGeneratorDialog
        if not hasattr(self, '_prompt_generator_dialog') or not self._prompt_generator_dialog:
            self._prompt_generator_dialog = PromptGeneratorDialog(None)
            self._prompt_generator_dialog.destroyed.connect(lambda: setattr(self, '_prompt_generator_dialog', None))
        self._prompt_generator_dialog.show()
        self._prompt_generator_dialog.raise_()
        self._prompt_generator_dialog.activateWindow()
    
    def _open_prompt_injector(self):
        from dialogs.tools.prompt_injector import PromptInjectorDialog
        if not hasattr(self, '_prompt_injector_dialog') or not self._prompt_injector_dialog:
            self._prompt_injector_dialog = PromptInjectorDialog(None)
            self._prompt_injector_dialog.destroyed.connect(lambda: setattr(self, '_prompt_injector_dialog', None))
        self._prompt_injector_dialog.show()
        self._prompt_injector_dialog.raise_()
        self._prompt_injector_dialog.activateWindow()
    
    def _open_envato_elements(self):
        from dialogs.tools.envato_elements_metadata_generator import EnvatoElementsMetadataDialog
        if not hasattr(self, '_envato_elements_dialog') or not self._envato_elements_dialog:
            self._envato_elements_dialog = EnvatoElementsMetadataDialog(None)
            self._envato_elements_dialog.destroyed.connect(lambda: setattr(self, '_envato_elements_dialog', None))
        self._envato_elements_dialog.show()
        self._envato_elements_dialog.raise_()
        self._envato_elements_dialog.activateWindow()
    
    def _open_pngtree_zipper(self):
        from dialogs.tools.pngtree_zipper_tool import PngtreeZipperDialog
        if not hasattr(self, '_pngtree_zipper_dialog') or not self._pngtree_zipper_dialog:
            self._pngtree_zipper_dialog = PngtreeZipperDialog(None)
            self._pngtree_zipper_dialog.destroyed.connect(lambda: setattr(self, '_pngtree_zipper_dialog', None))
        self._pngtree_zipper_dialog.show()
        self._pngtree_zipper_dialog.raise_()
        self._pngtree_zipper_dialog.activateWindow()
    
    def _open_holiday_calendar(self):
        from dialogs.tools.holiday_calendar.holiday_calendar_dialog import HolidayCalendarDialog
        if not hasattr(self, '_holiday_calendar_dialog') or not self._holiday_calendar_dialog:
            self._holiday_calendar_dialog = HolidayCalendarDialog(None)
            self._holiday_calendar_dialog.destroyed.connect(lambda: setattr(self, '_holiday_calendar_dialog', None))
        self._holiday_calendar_dialog.show()
        self._holiday_calendar_dialog.raise_()
        self._holiday_calendar_dialog.activateWindow()
    
    def _check_shutdown_signal(self):
        signal_file = os.path.join(BASE_PATH, "temp", "shutdown.signal")
        if os.path.exists(signal_file):
            try:
                os.remove(signal_file)
            except Exception:
                pass
            self.shutdown_timer.stop()
            self.close()
    
    def closeEvent(self, event):
        # Check if any tools are currently processing
        running_tools = []
        
        # Check Prompt Generator
        if hasattr(self, '_prompt_generator_dialog') and self._prompt_generator_dialog:
            if hasattr(self._prompt_generator_dialog, 'is_generating') and self._prompt_generator_dialog.is_generating:
                running_tools.append("Prompt Generator")
        
        # Check Image Overlay Maker
        if hasattr(self, '_image_overlay_maker_dialog') and self._image_overlay_maker_dialog:
            if hasattr(self._image_overlay_maker_dialog, 'is_processing') and self._image_overlay_maker_dialog.is_processing:
                running_tools.append("Image Overlay Maker")
        
        # Check Batch Audio Remover
        if hasattr(self, '_batch_audio_remover_dialog') and self._batch_audio_remover_dialog:
            if hasattr(self._batch_audio_remover_dialog, 'is_processing') and self._batch_audio_remover_dialog.is_processing:
                running_tools.append("Batch Audio Remover")
        
        # Check Video Upscaler
        if hasattr(self, '_video_upscaler_dialog') and self._video_upscaler_dialog:
            if hasattr(self._video_upscaler_dialog, 'worker') and self._video_upscaler_dialog.worker:
                if self._video_upscaler_dialog.worker.isRunning():
                    running_tools.append("Video Upscaler")
        
        # Check Image Upscaler
        if hasattr(self, '_image_upscaler_dialog') and self._image_upscaler_dialog:
            if hasattr(self._image_upscaler_dialog, 'worker') and self._image_upscaler_dialog.worker:
                if self._image_upscaler_dialog.worker.isRunning():
                    running_tools.append("Image Upscaler")
        
        # Check Action Sequencer
        if hasattr(self, '_action_sequencer_dialog') and self._action_sequencer_dialog:
            if hasattr(self._action_sequencer_dialog, 'batch_worker') and self._action_sequencer_dialog.batch_worker:
                if self._action_sequencer_dialog.batch_worker.isRunning():
                    running_tools.append("Action Sequencer")
        
        # Check Vibe Video Generator
        if hasattr(self, '_vibe_video_generator_dialog') and self._vibe_video_generator_dialog:
            if hasattr(self._vibe_video_generator_dialog, 'is_generating') and self._vibe_video_generator_dialog.is_generating:
                running_tools.append("Vibe Video Generator")
        
        # Check Prompted Image Sorter
        if hasattr(self, '_prompted_image_sorter_dialog') and self._prompted_image_sorter_dialog:
            if hasattr(self._prompted_image_sorter_dialog, 'worker') and self._prompted_image_sorter_dialog.worker:
                if self._prompted_image_sorter_dialog.worker.isRunning():
                    running_tools.append("Prompted Image Sorter")
        
# Check PSD to IMG
        if hasattr(self, '_psd_to_img_dialog') and self._psd_to_img_dialog:
            if hasattr(self._psd_to_img_dialog, 'worker_thread') and self._psd_to_img_dialog.worker_thread:
                if self._psd_to_img_dialog.worker_thread.isRunning():
                    running_tools.append("PSD to IMG")

        # Check Folder Comparator
        if hasattr(self, '_folder_comparator_dialog') and self._folder_comparator_dialog:
            if hasattr(self._folder_comparator_dialog, 'controller') and self._folder_comparator_dialog.controller:
                if self._folder_comparator_dialog.controller.is_running():
                    running_tools.append("Folder Comparator")

        # Check Batch Image Resizer
        if hasattr(self, '_batch_image_resizer_dialog') and self._batch_image_resizer_dialog:
            if hasattr(self._batch_image_resizer_dialog, 'worker_thread') and self._batch_image_resizer_dialog.worker_thread:
                if self._batch_image_resizer_dialog.worker_thread.isRunning():
                    running_tools.append("Batch Image Resizer")

        # If any tools are running, show confirmation dialog
        if running_tools:
            from PySide6.QtWidgets import QMessageBox
            tools_list = "\n• ".join(running_tools)
            reply = QMessageBox.question(
                self,
                "Tools Still Running",
                f"The following tools are still processing:\n\n• {tools_list}\n\nClosing Image Tea will stop all running processes. Are you sure you want to close?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
        
        # Close all tool dialogs
        if hasattr(self, '_envato_elements_dialog') and self._envato_elements_dialog:
            self._envato_elements_dialog.close()
        if hasattr(self, '_prompt_injector_dialog') and self._prompt_injector_dialog:
            self._prompt_injector_dialog.close()
        if hasattr(self, '_read_documentation_dialog') and self._read_documentation_dialog:
            self._read_documentation_dialog.close()
        if hasattr(self, '_action_sequencer_dialog') and self._action_sequencer_dialog:
            self._action_sequencer_dialog.close()
        if hasattr(self, '_video_upscaler_dialog') and self._video_upscaler_dialog:
            self._video_upscaler_dialog.close()
        if hasattr(self, '_image_upscaler_dialog') and self._image_upscaler_dialog:
            self._image_upscaler_dialog.close()
        if hasattr(self, '_pngtree_zipper_dialog') and self._pngtree_zipper_dialog:
            self._pngtree_zipper_dialog.close()
        if hasattr(self, '_holiday_calendar_dialog') and self._holiday_calendar_dialog:
            self._holiday_calendar_dialog.close()
        if hasattr(self, '_image_overlay_maker_dialog') and self._image_overlay_maker_dialog:
            self._image_overlay_maker_dialog.close()
        if hasattr(self, '_vibe_video_generator_dialog') and self._vibe_video_generator_dialog:
            self._vibe_video_generator_dialog.close()
        if hasattr(self, '_prompted_image_sorter_dialog') and self._prompted_image_sorter_dialog:
            self._prompted_image_sorter_dialog.close()
        if hasattr(self, '_tools_manager_dialog') and self._tools_manager_dialog:
            self._tools_manager_dialog.close()
        if hasattr(self, '_batch_audio_remover_dialog') and self._batch_audio_remover_dialog:
            self._batch_audio_remover_dialog.close()
        if hasattr(self, '_prompt_generator_dialog') and self._prompt_generator_dialog:
            self._prompt_generator_dialog.close()
        if hasattr(self, '_psd_to_img_dialog') and self._psd_to_img_dialog:
            self._psd_to_img_dialog.close()
        if hasattr(self, '_folder_comparator_dialog') and self._folder_comparator_dialog:
            self._folder_comparator_dialog.close()
        if hasattr(self, '_batch_image_resizer_dialog') and self._batch_image_resizer_dialog:
            self._batch_image_resizer_dialog.close()

        if hasattr(self, 'lock_file') and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
            except Exception:
                pass

        event.accept()

if __name__ == '__main__':
    from helpers.logging_helper import init_logging
    init_logging()

    if sys.platform == "win32":
        import ctypes
        app_id = u"image-tea.nano"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    
    t0 = time.time()

    app = QApplication(sys.argv)
    
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    _original_QDialog_exec = QDialog.exec
    _original_QDialog_show = QDialog.show

    def _wait_for_splash():
        while getattr(splash_mod, 'splash_active', False):
            app.processEvents()
            time.sleep(0.05)

    ALLOWED_DIALOG_CLASS_NAMES = {
        'DisclaimerDialog',
        'DonateDialog',
        'UpdateNoticeDialog',
        'ApiCallWarningDialog',
        'GetApiKeyDialog',
        'AIUnsuportedDialog'
    }

    def _is_allowed_while_splash(dialog):
        cls = getattr(dialog, '__class__', None)
        if cls is None:
            return False
        name = cls.__name__
        if name in ALLOWED_DIALOG_CLASS_NAMES:
            return True
        return bool(getattr(dialog, 'allow_while_splash', False))

    def _patched_exec(self, *args, **kwargs):
        if _is_allowed_while_splash(self):
            had_top = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
            if not had_top:
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            result = _original_QDialog_exec(self, *args, **kwargs)
            if not had_top:
                self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            return result
        _wait_for_splash()
        return _original_QDialog_exec(self, *args, **kwargs)

    def _patched_show(self, *args, **kwargs):
        if _is_allowed_while_splash(self):
            had_top = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
            if not had_top:
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
                res = _original_QDialog_show(self, *args, **kwargs)
                self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
                return res
            return _original_QDialog_show(self, *args, **kwargs)
        _wait_for_splash()
        return _original_QDialog_show(self, *args, **kwargs)

    QDialog.exec = _patched_exec
    QDialog.show = _patched_show

    _sim_stages = [
        (8,  "Initializing application..."),
        (18, "Loading configuration..."),
        (28, "Connecting to database..."),
        (38, "Loading theme system..."),
        (48, "Preparing interface..."),
    ]
    for _pct, _msg in _sim_stages:
        splash.show_message(_msg)
        splash.set_progress(_pct)
        app.processEvents()
        time.sleep(0.05)

    splash.show_message("Loading components...")
    splash.set_progress(55)
    app.processEvents()
    from ui.setup_ui import setup_ui
    from dialogs.ai_unsuported_dialog import AIUnsuportedDialog
    from helpers.batch_processing_helper import (
        batch_generate_metadata,
        stop_generate_metadata,
        update_token_stats_ui
    )
    from dialogs.disclaimer_dialog import DisclaimerDialog
    import json

    splash.set_progress(68)
    splash.show_message("Checking disclaimer...")
    app.processEvents()
    if DisclaimerDialog.check_and_show():
        splash.show_message("Starting application...")
        app.processEvents()

        for _pct in range(72, 92, 4):
            splash.set_progress(_pct)
            app.processEvents()
            time.sleep(0.04)

        window = ImageTeaMainWindow()
        splash.set_progress(95)
        app.processEvents()

        window.resize(900, 700)

        screen = app.primaryScreen().geometry()
        window_geometry = window.frameGeometry()
        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        window.move(window_geometry.topLeft())

        splash.set_progress(100)
        app.processEvents()

        t_splash_ms = int((time.time() - t0) * 1000)

        splash.finish(window)
        window.show()
        app.processEvents()
        window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        window.show()
        app.processEvents()
        window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        window.show()
        app.processEvents()
        window.raise_()
        window.activateWindow()

        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                SW_SHOW = 5
                hwnd = int(window.winId())
                user32.ShowWindow(hwnd, SW_SHOW)
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        def _run_background_init():
            import threading

            def _emit(msg):
                window.background_status.emit(msg)

            def _bg_work():
                from tools.tools_checker import ensure_tools_ready
                from tools.image_tea_health_checker import build_remote_cache, run_check
                from helpers.check_for_update_helper import check_for_update

                _emit("Checking for updates...")
                print("[Background Init] Checking for updates...")
                check_for_update()
                window.trigger_show_update_dialog.emit()

                _emit("Verifying tools...")
                print("[Background Init] Preparing tools...")
                ensure_tools_ready(reporter=lambda msg: print(f"[Tools] {msg}"), progress_reporter=lambda p: None, unit_callback=lambda: None, auto_install=False)

                _emit("Installing default tools...")
                print("[Background Init] Installing default tools if missing...")
                from tools.tools_checker import install_default_tools
                install_default_tools(reporter=lambda msg: print(f"[Tools] {msg}"), progress_reporter=lambda p: None, unit_callback=lambda: None)

                _emit("Running health check...")
                print("[Background Init] Running health check...")
                cache = build_remote_cache(force_refresh=False, progress_reporter=lambda p: None)
                run_check(repair=True, force_refresh=False, verbose=True, cache=cache, unit_callback=lambda: None, progress_reporter=lambda p: None)

                print("[Background Init] Done.")
                _emit(f"Image Tea Ready (Startup time: {t_splash_ms} ms)")

            t = threading.Thread(target=_bg_work, daemon=True)
            t.start()

        QTimer.singleShot(500, _run_background_init)

        sys.exit(app.exec())
    else:
        splash.close()
        sys.exit(0)