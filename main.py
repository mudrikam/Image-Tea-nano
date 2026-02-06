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
        setup_ui(self)
        self.table.refresh_table()
        self.generator_thread = None
        self.is_generating = False
        self.show_ai_unsupported_dialog.connect(self._show_ai_unsupported_dialog_slot)

        if hasattr(self, "gen_btn"):
            self.gen_btn.clicked.disconnect()
            self.gen_btn.clicked.connect(self._on_gen_btn_clicked)

        update_token_stats_ui(self)
        
        self.lock_file = os.path.join(BASE_PATH, "temp", "image_tea.lock")
        os.makedirs(os.path.dirname(self.lock_file), exist_ok=True)
        with open(self.lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.timeout.connect(self._check_shutdown_signal)
        self.shutdown_timer.start(500)

    def _show_ai_unsupported_dialog_slot(self, message):
        dialog = AIUnsuportedDialog(message, parent=self)
        dialog.exec()

    def _on_gen_btn_clicked(self):
        if self.is_generating:
            stop_generate_metadata(self)
        else:
            batch_generate_metadata(self)
    
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
        
        if hasattr(self, 'lock_file') and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
            except Exception:
                pass
        
        event.accept()

if __name__ == '__main__':
    if sys.platform == "win32":
        import ctypes
        app_id = u"image-tea.nano"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    
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
    
    from tools.tools_checker import ProgressAggregator, compute_tools_work_units, ensure_tools_ready
    from tools.image_tea_health_checker import build_remote_cache

    ag = ProgressAggregator(progress_reporter=splash.set_progress)

    tools_units = sum(compute_tools_work_units().values())
    ag.add_total_units(1 + tools_units + 1 + 1 + 1 + 1)

    splash.show_message("Checking for updates...")
    app.processEvents()
    from helpers.check_for_update_helper import check_for_update
    check_for_update()
    ag.unit_completed()

    splash.show_message("Preparing tools...")
    app.processEvents()
    ensure_tools_ready(reporter=splash.show_message, progress_reporter=ag.make_unit_progress_reporter(1), unit_callback=ag.unit_completed)

    splash.show_message("Running health check...")
    app.processEvents()
    cache = build_remote_cache(force_refresh=False, progress_reporter=ag.make_unit_progress_reporter(1))
    ag.unit_completed()
    remote_count = len(cache.get('files', [])) if cache else 0
    if remote_count:
        ag.add_total_units(remote_count)
    from tools.image_tea_health_checker import run_check
    run_check(repair=True, force_refresh=False, verbose=True, cache=cache, unit_callback=ag.unit_completed, progress_reporter=ag.make_unit_progress_reporter(1))

    splash.show_message("Loading components...")
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
    ag.unit_completed()

    splash.show_message("Checking disclaimer...")
    app.processEvents()
    if DisclaimerDialog.check_and_show():
        ag.unit_completed()
        splash.show_message("Starting application...")
        app.processEvents()
        time.sleep(2)
        app.processEvents()
        window = ImageTeaMainWindow()
        window.resize(900, 700)
        
        screen = app.primaryScreen().geometry()
        window_geometry = window.frameGeometry()
        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        window.move(window_geometry.topLeft())
        
        # Final unit: starting application (1 unit)
        ag.unit_completed()

        splash.finish(window)
        window.show()
        app.processEvents()
        # Try a Qt-based trick: toggle always-on-top briefly to grab focus
        window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        window.show()
        app.processEvents()
        window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        window.show()
        app.processEvents()
        window.raise_()
        window.activateWindow()

        # On Windows, try a native call as a fallback
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

        sys.exit(app.exec())
    else:
        splash.close()
        sys.exit(0)