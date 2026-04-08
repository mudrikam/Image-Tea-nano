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
        setup_ui(self)
        self.table.refresh_table()
        self.generator_thread = None
        self.is_generating = False
        self.show_ai_unsupported_dialog.connect(self._show_ai_unsupported_dialog_slot)
        self.background_status.connect(self._on_background_status)
        self.trigger_show_update_dialog.connect(self._on_show_update_dialog)

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
        if hasattr(self, '_holiday_calendar_dialog') and self._holiday_calendar_dialog:
            self._holiday_calendar_dialog.close()
        if hasattr(self, '_vibe_video_generator_dialog') and self._vibe_video_generator_dialog:
            self._vibe_video_generator_dialog.close()
        if hasattr(self, '_vibe_video_generator_dialog') and self._vibe_video_generator_dialog:
            self._vibe_video_generator_dialog.close()
        
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
                ensure_tools_ready(reporter=lambda msg: print(f"[Tools] {msg}"), progress_reporter=lambda p: None, unit_callback=lambda: None)

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