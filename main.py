import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import BASE_PATH
sys.path.insert(0, BASE_PATH)
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon
import time
import qtawesome as qta
from ui.splash_screen_window import SplashScreen

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

    def _show_ai_unsupported_dialog_slot(self, message):
        dialog = AIUnsuportedDialog(message, parent=self)
        dialog.exec()

    def _on_gen_btn_clicked(self):
        if self.is_generating:
            stop_generate_metadata(self)
        else:
            batch_generate_metadata(self)
    
    def closeEvent(self, event):
        if hasattr(self, '_envato_elements_dialog') and self._envato_elements_dialog:
            self._envato_elements_dialog.close()
        if hasattr(self, '_prompt_injector_dialog') and self._prompt_injector_dialog:
            self._prompt_injector_dialog.close()
        if hasattr(self, '_action_sequencer_dialog') and self._action_sequencer_dialog:
            self._action_sequencer_dialog.close()
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
    
    splash.show_message("Checking for updates...")
    app.processEvents()
    from helpers.check_for_update_helper import check_for_update
    check_for_update()
    
    splash.show_message("Preparing tools...")
    app.processEvents()
    from tools.tools_checker import ensure_tools_ready
    ensure_tools_ready()
    
    splash.show_message("Running health check...")
    app.processEvents()
    from tools.image_tea_health_checker import run_check
    run_check(repair=True, force_refresh=False, verbose=True)
    
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
    
    splash.show_message("Checking disclaimer...")
    app.processEvents()
    if DisclaimerDialog.check_and_show():
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