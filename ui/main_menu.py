from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox, QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QFileDialog, QWidgetAction, QWidget, QScrollArea
from PySide6.QtGui import QAction, QPixmap, QIcon
from PySide6.QtCore import Qt
import qtawesome as qta
import webbrowser
import sys
import os
import subprocess
import platform
import json
from config import BASE_PATH
from .theme_system import theme
from helpers.file_importer import import_files
from helpers.csv_importer import import_csv_interactive
from helpers.metadata_helper.metadata_operation import write_metadata_to_images, write_metadata_to_videos
from dialogs.edit_prompt_dialog import EditPromptDialog
from dialogs.csv_exporter_dialog import CSVExporterDialog
from dialogs.custom_prompt_dialog import CustomPromptDialog
from dialogs.batch_rename_dialog import BatchRenameDialog
from dialogs.metadata_writing_chunk_size_dialog import MetadataWritingChunkSizeDialog
from dialogs.read_documentation_dialog import ReadDocumentationDialog
from dialogs.donation_dialog import DonateDialog
from dialogs.add_api_key_dialog import AddApiKeyDialog
from dialogs.about_dialog import AboutDialog
from dialogs.file_metadata_dialog import FileMetadataDialog
from dialogs.update_notice_dialog import UpdateNoticeDialog
from dialogs.tools.prompt_generator_tool import PromptGeneratorDialog
from dialogs.tools.imagen_generator_tool import ImagenGeneratorDialog
from dialogs.tools.batch_audio_remover import BatchAudioRemoverDialog
from dialogs.video_proxy_prompt_settings_dialog import VideoProxyPromptSettingsDialog
from dialogs.backup_global_config_dialog import BackupGlobalConfigDialog
from dialogs.tools.envato_elements_metadata_generator import EnvatoElementsMetadataDialog
from dialogs.tools.action_sequencer import ActionSequencerDialog
from dialogs.tools.video_upscaler_tool import VideoUpscalerDialog
from dialogs.tools.image_upscaler_tool import ImageUpscalerDialog
from dialogs.tools.theme_editor_dialog import ThemeEditorDialog

# Menu tooltips dictionary
MENU_TOOLTIPS = {
    # File menu
    "import_files": "Import image and video files into the database for metadata processing",
    "relaunch": "Restart the application with current settings",
    "exit": "Close the application",
    "backup_configs": "Create and restore backups of the application's configs folder",
    
    # Edit menu
    "delete_selected": "Remove selected files from the database",
    "clear_all": "Remove ALL files from database",
    "clear_metadata": "Remove all metadata from database (not from files)",
    "clear_success": "Remove only files with Success status",
    "clear_failed": "Remove only files with Failed status",
    "batch_rename": "Rename multiple files with custom patterns",
    "edit_metadata": "Edit metadata for selected file",
    
    # Metadata menu
    "write_images": "Embed metadata into image files",
    "write_videos": "Embed metadata into video files", 
    "export_csv": "Export metadata to CSV file for external use",
    "import_csv": "Import metadata from CSV file into database",
    "chunk_size": "Configure chunk size for metadata writing operations",
    
    # Prompt menu
    "edit_prompt": "Configure AI prompt templates and settings",
    "custom_prompt": "Generate custom prompts using AI",
    
    # API menu
    "add_api_key": "Add or manage API keys for AI services",
    
    # Tools menu
    "prompt_generator": "Generate AI prompts for image/video creation",
    "imagen_generator": "Generate images using Google's Imagen AI",
    "batch_audio_remover": "Remove audio from multiple video files in batch",
    "envato_elements_metadata": "Generate metadata for Envato Elements mockups",
    "action_sequencer": "Automate actions for Photoshop and Illustrator",
    "video_upscaler": "Upscale videos using RealESRGAN AI",
    "image_upscaler": "Upscale images using RealESRGAN AI",
    "pngtree_zipper": "Zip asset files to submit to Pngtree",
    
    # Help menu
    "about": "View application information and credits",
    "update_now": "Check for and install application updates",
    "donate": "Support development with a donation",
    "whatsapp": "Join our WhatsApp community group",
    "repository": "View source code on GitHub",
    "website": "Visit our official website",
    "readme": "Read detailed documentation on GitHub",
    "tiktok": "Visit our TikTok profile",
    "telegram": "Open our Telegram bot",
    "documentation": "View built-in help and documentation"
}

def get_app_links():
    import json
    import os
    config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["links"]



def run_updater(window):
    try:
        system = platform.system()
        print(f"Detected OS: {system}")
        
        update_worker_py = os.path.join(BASE_PATH, "Update_Worker.py")
        
        if not os.path.exists(update_worker_py):
            links = get_app_links()
            repo_url = links.get('repo', 'https://github.com/mudrikam/Image-Tea-nano')
            msg = (
                "Update_Worker.py not found. "
                "Please download the latest release manually from: "
                f"{repo_url}"
            )
            print(msg)
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(window, "Update Not Available", msg)
            except Exception:
                pass
            return
        
        print(f"Running Update_Worker.py: {update_worker_py}")
        
        if system == "Windows":
            pythonw_path = os.path.join(BASE_PATH, "python", "Windows", "pythonw.exe")
            python_path = os.path.join(BASE_PATH, "python", "Windows", "python.exe")
            
            if os.path.exists(pythonw_path):
                subprocess.Popen([pythonw_path, update_worker_py, "--auto"], shell=False)
            elif os.path.exists(python_path):
                subprocess.Popen([python_path, update_worker_py, "--auto"], shell=False)
            else:
                subprocess.Popen([sys.executable, update_worker_py, "--auto"], shell=False)
        else:
            subprocess.Popen([sys.executable, update_worker_py, "--auto"], shell=False)
            
    except Exception as e:
        print(f"Failed to start update process: {e}")

def setup_main_menu(window):
    links = get_app_links()
    menubar = QMenuBar(window)
    file_menu = QMenu("File", menubar)
    file_menu.setToolTipsVisible(True)

    import_action = QAction(qta.icon('fa6s.folder-open'), "Import Files", window)
    import_action.setToolTip(MENU_TOOLTIPS["import_files"])
    import_action.setStatusTip(MENU_TOOLTIPS["import_files"])
    def do_import():
        if import_files(window, window.db):
            window.table.refresh_table()
    import_action.triggered.connect(do_import)
    file_menu.addAction(import_action)

    relaunch_action = QAction(qta.icon('fa6s.rotate-right'), "Relaunch", window)
    relaunch_action.setToolTip(MENU_TOOLTIPS["relaunch"])
    relaunch_action.setStatusTip(MENU_TOOLTIPS["relaunch"])
    def relaunch_app():
        python_exe = sys.executable
        args = [python_exe] + sys.argv
        try:
            subprocess.Popen(args)
        except Exception as e:
            print(f"Failed to relaunch: {e}")
        window.close()
    relaunch_action.triggered.connect(relaunch_app)
    file_menu.addAction(relaunch_action)

    backup_configs_action = QAction(qta.icon('fa6s.file-zipper'), "Backup Configs", window)
    backup_configs_action.setToolTip(MENU_TOOLTIPS["backup_configs"])
    backup_configs_action.setStatusTip(MENU_TOOLTIPS["backup_configs"])
    def open_backup_configs():
        dlg = BackupGlobalConfigDialog(window)
        dlg.exec()
    backup_configs_action.triggered.connect(open_backup_configs)
    file_menu.addAction(backup_configs_action)
    window.backup_configs_action = backup_configs_action

    exit_action = QAction(qta.icon('fa6s.right-from-bracket'), "Exit", window)
    exit_action.setToolTip(MENU_TOOLTIPS["exit"])
    exit_action.setStatusTip(MENU_TOOLTIPS["exit"])
    exit_action.triggered.connect(window.close)
    file_menu.addAction(exit_action)

    edit_menu = QMenu("Edit", menubar)
    edit_menu.setToolTipsVisible(True)

    delete_action = QAction(qta.icon('fa6s.trash'), "Delete Selected", window)
    delete_action.setToolTip(MENU_TOOLTIPS["delete_selected"])
    delete_action.setStatusTip(MENU_TOOLTIPS["delete_selected"])
    delete_action.triggered.connect(lambda: window.table.delete_selected())
    edit_menu.addAction(delete_action)

    clear_action = QAction(qta.icon('fa6s.broom'), "Clear All Files", window)
    clear_action.setToolTip(MENU_TOOLTIPS["clear_all"])
    clear_action.setStatusTip(MENU_TOOLTIPS["clear_all"])
    clear_action.triggered.connect(lambda: window.table.clear_all())
    edit_menu.addAction(clear_action)
    
    clear_success_action = QAction(qta.icon('fa6s.broom'), "Clear Success Only", window)
    clear_success_action.setToolTip(MENU_TOOLTIPS["clear_success"])
    clear_success_action.setStatusTip(MENU_TOOLTIPS["clear_success"])
    clear_success_action.triggered.connect(lambda: window.table.clear_success())
    edit_menu.addAction(clear_success_action)
    
    clear_failed_action = QAction(qta.icon('fa6s.broom'), "Clear Failed Only", window)
    clear_failed_action.setToolTip(MENU_TOOLTIPS["clear_failed"])
    clear_failed_action.setStatusTip(MENU_TOOLTIPS["clear_failed"])
    clear_failed_action.triggered.connect(lambda: window.table.clear_failed())
    edit_menu.addAction(clear_failed_action)

    clear_metadata_action = QAction(qta.icon('fa6s.eraser'), "Clear Existing Metadata", window)
    clear_metadata_action.setToolTip(MENU_TOOLTIPS["clear_metadata"])
    clear_metadata_action.setStatusTip(MENU_TOOLTIPS["clear_metadata"])
    clear_metadata_action.triggered.connect(lambda: window.table.clear_existing_metadata())
    edit_menu.addAction(clear_metadata_action)
    
    edit_menu.addSeparator()

    batch_rename_action = QAction(qta.icon('fa6s.i-cursor'), "Batch Rename", window)
    batch_rename_action.setToolTip(MENU_TOOLTIPS["batch_rename"])
    batch_rename_action.setStatusTip(MENU_TOOLTIPS["batch_rename"])
    def open_batch_rename():
        dialog = BatchRenameDialog(window, table_widget=window.table, db=window.db)
        dialog.exec()
    batch_rename_action.triggered.connect(open_batch_rename)
    edit_menu.addAction(batch_rename_action)

    edit_metadata_action = QAction(qta.icon('fa6s.pen-to-square'), "Edit Metadata", window)
    edit_metadata_action.setToolTip(MENU_TOOLTIPS["edit_metadata"])
    edit_metadata_action.setStatusTip(MENU_TOOLTIPS["edit_metadata"])
    def open_edit_metadata():
        selected = window.table.table.selectionModel().selectedRows()
        if selected:
            idx = selected[0].row()
            filepath_item = window.table.table.item(idx, 1)
            if filepath_item:
                filepath = filepath_item.data(Qt.UserRole)
                if not filepath:
                    filepath = filepath_item.text()
                dialog = FileMetadataDialog(filepath, parent=window)
                dialog.exec()
    edit_metadata_action.triggered.connect(open_edit_metadata)
    edit_menu.addAction(edit_metadata_action)
    
    edit_menu.addSeparator()
    
    themes_submenu = QMenu("Themes", edit_menu)
    themes_submenu.setIcon(qta.icon('fa6s.palette'))
    themes_submenu.setToolTipsVisible(True)
    
    def load_themes_menu():
        themes_submenu.clear()
        try:
            editor_action = QAction(qta.icon('fa6s.pen-to-square'), "Theme Editor...", window)
            editor_action.triggered.connect(lambda: ThemeEditorDialog(window).exec())
            themes_submenu.addAction(editor_action)
            themes_submenu.addSeparator()

            import json
            config_path = os.path.join('configs', 'app_themes.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                themes_data = json.load(f)

            current_theme = themes_data.get('current_theme', 'default')

            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(4, 4, 4, 4)
            container_layout.setSpacing(0)

            for theme_id, theme_info in themes_data['themes'].items():
                theme_name = theme_info.get('name', theme_id)
                btn = QPushButton(theme_name)
                btn.setFlat(True)
                btn.setCheckable(True)
                is_active = (theme_id == current_theme)
                btn.setChecked(is_active)
                btn.setStyleSheet(
                    "QPushButton { text-align: left; padding: 6px 12px; border: none; }"
                    f"QPushButton:checked {{ background-color: {theme.get_color('primary')}; color: {theme.get_color('white')}; }}"
                )
                if is_active:
                    try:
                        btn.setIcon(qta.icon('fa6s.check'))
                    except Exception:
                        pass
                btn.clicked.connect(lambda checked, tid=theme_id: apply_theme(tid))
                container_layout.addWidget(btn)

            container_layout.addStretch()

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(container)
            scroll.setFixedWidth(220)
            scroll.setFixedHeight(320)

            wa = QWidgetAction(window)
            wa.setDefaultWidget(scroll)
            themes_submenu.addAction(wa)

        except Exception as e:
            print(f"Error loading themes menu: {e}")
    
    def apply_theme(theme_id):
        config_path = os.path.join('configs', 'app_themes.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            themes_data = json.load(f)

        themes_data['current_theme'] = theme_id

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(themes_data, f, indent=2)

        reply = QMessageBox.question(
            window,
            "Theme Changed",
            f"Theme changed to '{themes_data['themes'][theme_id]['name']}'. Restart the application now to apply changes?",
            QMessageBox.Yes | QMessageBox.No
        )

        load_themes_menu()

        if reply == QMessageBox.Yes:
            print(f"Theme changed to '{themes_data['themes'][theme_id]['name']}' - restarting now.")
            relaunch_app()
        else:
            print(f"Theme changed to '{themes_data['themes'][theme_id]['name']}'. Restart required to apply changes.")
    
    def open_theme_editor():
        dialog = ThemeEditorDialog(window)
        dialog.theme_changed.connect(lambda theme_id: load_themes_menu())
        dialog.exec()
    
    load_themes_menu()
    edit_menu.addMenu(themes_submenu)

    metadata_menu = QMenu("Metadata", menubar)
    metadata_menu.setToolTipsVisible(True)
    write_metadata_images_action = QAction(qta.icon('fa6s.floppy-disk'), "Write Metadata to Images", window)
    write_metadata_images_action.setToolTip(MENU_TOOLTIPS["write_images"])
    write_metadata_images_action.setStatusTip(MENU_TOOLTIPS["write_images"])
    def do_write_metadata_images():
        write_metadata_to_images(window.db, window)
    write_metadata_images_action.triggered.connect(do_write_metadata_images)
    metadata_menu.addAction(write_metadata_images_action)

    write_metadata_videos_action = QAction(qta.icon('fa6s.floppy-disk'), "Write Metadata to Videos", window)
    write_metadata_videos_action.setToolTip(MENU_TOOLTIPS["write_videos"])
    write_metadata_videos_action.setStatusTip(MENU_TOOLTIPS["write_videos"])
    def do_write_metadata_videos():
        write_metadata_to_videos(window.db, window)
    write_metadata_videos_action.triggered.connect(do_write_metadata_videos)
    metadata_menu.addAction(write_metadata_videos_action)

    export_metadata_action = QAction(qta.icon('fa6s.file-csv'), "Export Metadata to CSV", window)
    export_metadata_action.setToolTip(MENU_TOOLTIPS["export_csv"])
    export_metadata_action.setStatusTip(MENU_TOOLTIPS["export_csv"])
    def show_export_dialog():
        dialog = CSVExporterDialog(window)
        dialog.exec()
    export_metadata_action.triggered.connect(show_export_dialog)
    metadata_menu.addAction(export_metadata_action)

    import_metadata_action = QAction(qta.icon('fa6s.file-csv'), "Import Metadata from CSV", window)
    import_metadata_action.setToolTip(MENU_TOOLTIPS["import_csv"])
    import_metadata_action.setStatusTip(MENU_TOOLTIPS["import_csv"])
    def do_import_csv():
        import_csv_interactive(window)
    import_metadata_action.triggered.connect(do_import_csv)
    metadata_menu.addAction(import_metadata_action)

    metadata_menu.addSeparator()

    chunk_size_action = QAction(qta.icon('fa6s.gears'), "Chunk Size Settings", window)
    chunk_size_action.setToolTip(MENU_TOOLTIPS["chunk_size"])
    chunk_size_action.setStatusTip(MENU_TOOLTIPS["chunk_size"])
    def show_chunk_size_dialog():
        dialog = MetadataWritingChunkSizeDialog(window)
        dialog.exec()
    chunk_size_action.triggered.connect(show_chunk_size_dialog)
    metadata_menu.addAction(chunk_size_action)

    prompt_menu = QMenu("Prompt", menubar)
    prompt_menu.setToolTipsVisible(True)
    edit_prompt_action = QAction(qta.icon('fa6s.pen-to-square'), "Edit Prompt", window)
    edit_prompt_action.setToolTip(MENU_TOOLTIPS["edit_prompt"])
    edit_prompt_action.setStatusTip(MENU_TOOLTIPS["edit_prompt"])
    def open_edit_prompt():
        dialog = EditPromptDialog(window)
        result = dialog.exec()
        if result == EditPromptDialog.Accepted and hasattr(window, 'prompt_section'):
            window.prompt_section.refresh_presets()
    edit_prompt_action.triggered.connect(open_edit_prompt)
    prompt_menu.addAction(edit_prompt_action)

    custom_prompt_action = QAction(qta.icon('fa6s.comment'), "Custom Prompt", window)
    custom_prompt_action.setToolTip(MENU_TOOLTIPS["custom_prompt"])
    custom_prompt_action.setStatusTip(MENU_TOOLTIPS["custom_prompt"])
    def open_custom_prompt():
        dialog = CustomPromptDialog(window)
        dialog.exec()
    custom_prompt_action.triggered.connect(open_custom_prompt)
    prompt_menu.addAction(custom_prompt_action)

    video_proxy_settings_action = QAction(qta.icon('fa6s.video'), "Video Proxy Settings", window)
    video_proxy_settings_action.setToolTip("Edit video proxy presets (bitrate, CRF, resolution)")
    video_proxy_settings_action.setStatusTip("Edit video proxy presets (bitrate, CRF, resolution)")
    def open_video_proxy_settings():
        dlg = VideoProxyPromptSettingsDialog(window)
        dlg.exec()
    video_proxy_settings_action.triggered.connect(open_video_proxy_settings)
    prompt_menu.addAction(video_proxy_settings_action)

    api_action = QAction("API Key Manager", window)
    api_action.setToolTip(MENU_TOOLTIPS["add_api_key"])
    api_action.setStatusTip(MENU_TOOLTIPS["add_api_key"])
    def show_api_dialog():
        dlg = AddApiKeyDialog(window)
        result = dlg.exec()
        if hasattr(window, 'api_key_section'):
            window.api_key_section.refresh()
    api_action.triggered.connect(show_api_dialog)
    menubar.addAction(api_action)

    purchase_menu = QMenu("Purchase", menubar)
    purchase_menu.setStyleSheet(
        f"QMenu::title {{ color: {theme.get_color('primary')}; }}"
    )
    purchase_menu.setToolTipsVisible(True)
    config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for key, url in cfg.get("purchese_links", {}).items():
        label = key.replace('_', ' ').title()
        icon = qta.icon('fa6s.cart-shopping', color=theme.get_color('primary'))
        action = QAction(icon, label, window)
        action.setToolTip(url)
        action.setStatusTip(url)
        action.triggered.connect(lambda checked, u=url: webbrowser.open(u))
        purchase_menu.addAction(action)

    help_menu = QMenu("Help", menubar)
    help_menu.setToolTipsVisible(True)

    about_action = QAction(qta.icon('fa6s.circle-info'), "About", window)
    about_action.setToolTip(MENU_TOOLTIPS["about"])
    about_action.setStatusTip(MENU_TOOLTIPS["about"])
    def show_about():
        dialog = AboutDialog(window)
        dialog.exec()
    about_action.triggered.connect(show_about)
    help_menu.addAction(about_action)

    show_guide_action = QAction(qta.icon('fa6s.lightbulb'), "Show Guide", window)
    show_guide_action.setToolTip("Reset and show the interactive guide tour")
    show_guide_action.setStatusTip("Reset and show the interactive guide tour")
    def show_guide():
        try:
            if hasattr(window, 'guide_overlay') and window.guide_overlay:
                window.guide_overlay.reset_and_show()
        except Exception as e:
            print(f"Failed to show guide overlay: {e}")
    show_guide_action.triggered.connect(show_guide)
    help_menu.addAction(show_guide_action)


    update_now_action = QAction(qta.icon('fa6s.download'), "Update Now", window)
    update_now_action.setToolTip(MENU_TOOLTIPS["update_now"])
    update_now_action.setStatusTip(MENU_TOOLTIPS["update_now"])
    update_now_action.triggered.connect(lambda: run_updater(window))
    help_menu.addAction(update_now_action)

    version_action = QAction(qta.icon('fa6s.code-branch'), "Version", window)
    version_action.setToolTip("Show version and update information")
    version_action.setStatusTip("Show version and update information")
    def show_version_dialog():
        update_cfg_path = os.path.join(BASE_PATH, "configs", "update_config.json")
        local_tag = remote_tag = remote_hash = release_notes = checked_time = None
        if os.path.exists(update_cfg_path):
            with open(update_cfg_path, "r", encoding="utf-8") as f:
                update_cfg = json.load(f)
                local_tag = update_cfg.get("tag_local")
                remote_tag = update_cfg.get("tag_remote")
                remote_hash = None
                commit_hash = update_cfg.get("commit_hash", {})
                if isinstance(commit_hash, dict):
                    remote_hash = commit_hash.get("remote")
                checked_time = update_cfg.get("update", {}).get("last_checked")
        release_notes = ""
        notes = None
        if os.path.exists(update_cfg_path):
            try:
                with open(update_cfg_path, "r", encoding="utf-8") as f:
                    update_cfg2 = json.load(f)
                    notes = update_cfg2.get("release_notes", {}).get(remote_tag)
            except Exception as e:
                print(f"Failed to load cached release notes: {e}")
        if notes:
            release_notes = notes
        dialog = UpdateNoticeDialog(parent=window, local_tag=local_tag, remote_tag=remote_tag, remote_hash=remote_hash, release_notes=release_notes, checked_time=checked_time)
        dialog.exec()
    version_action.triggered.connect(show_version_dialog)
    help_menu.addAction(version_action)

    donate_action = QAction(qta.icon('fa6s.circle-dollar-to-slot'), "Donate", window)
    donate_action.setToolTip(MENU_TOOLTIPS["donate"])
    donate_action.setStatusTip(MENU_TOOLTIPS["donate"])
    def show_donate():
        dialog = DonateDialog(window)
        dialog.exec()
    donate_action.triggered.connect(show_donate)
    help_menu.addAction(donate_action)

    wa_action = QAction(qta.icon('fa5b.whatsapp'), "WhatsApp Group", window)
    wa_action.setToolTip(MENU_TOOLTIPS["whatsapp"])
    wa_action.setStatusTip(MENU_TOOLTIPS["whatsapp"])
    def open_wa():
        webbrowser.open(links["whatsapp"])
    wa_action.triggered.connect(open_wa)
    help_menu.addAction(wa_action)

    tiktok_action = QAction(qta.icon('fa6b.tiktok'), "TikTok", window)
    tiktok_action.setToolTip(MENU_TOOLTIPS.get("tiktok"))
    tiktok_action.setStatusTip(MENU_TOOLTIPS.get("tiktok"))
    def open_tiktok():
        webbrowser.open(links.get("tiktok"))
    tiktok_action.triggered.connect(open_tiktok)
    help_menu.addAction(tiktok_action)

    telegram_action = QAction(qta.icon('fa6b.telegram'), "Telegram", window)
    telegram_action.setToolTip(MENU_TOOLTIPS.get("telegram"))
    telegram_action.setStatusTip(MENU_TOOLTIPS.get("telegram"))
    def open_telegram():
        webbrowser.open(links.get("telegram"))
    telegram_action.triggered.connect(open_telegram)
    help_menu.addAction(telegram_action)

    repo_action = QAction(qta.icon('fa5b.github'), "Repository", window)
    repo_action.setToolTip(MENU_TOOLTIPS["repository"])
    repo_action.setStatusTip(MENU_TOOLTIPS["repository"])
    def open_repo():
        webbrowser.open(links["repo"])
    repo_action.triggered.connect(open_repo)
    help_menu.addAction(repo_action)


    readme_action = QAction(qta.icon('fa6s.book'), "Open README.md (GitHub)", window)
    readme_action.setToolTip(MENU_TOOLTIPS["readme"])
    readme_action.setStatusTip(MENU_TOOLTIPS["readme"])
    def open_readme():
        webbrowser.open(links["readme"])
    readme_action.triggered.connect(open_readme)
    help_menu.addAction(readme_action)

    documentation_action = QAction(qta.icon('fa6s.book-open'), "Help", window)
    documentation_action.setToolTip(MENU_TOOLTIPS["documentation"])
    documentation_action.setStatusTip(MENU_TOOLTIPS["documentation"])
    def open_documentation():
        if not hasattr(window, '_read_documentation_dialog') or not window._read_documentation_dialog:
            window._read_documentation_dialog = ReadDocumentationDialog(None)
            window._read_documentation_dialog.destroyed.connect(lambda: setattr(window, '_read_documentation_dialog', None))
            if hasattr(window, 'windowIcon') and not window.windowIcon().isNull():
                window._read_documentation_dialog.setWindowIcon(window.windowIcon())
        window._read_documentation_dialog.show()
        window._read_documentation_dialog.raise_()
        window._read_documentation_dialog.activateWindow()
    documentation_action.triggered.connect(open_documentation)
    help_menu.addAction(documentation_action)

    # Tools menu
    tools_menu = QMenu("Tools", menubar)
    tools_menu.setToolTipsVisible(True)

    prompt_generator_action = QAction(qta.icon('fa6s.wand-magic-sparkles'), "Prompt Generator", window)
    prompt_generator_action.setToolTip(MENU_TOOLTIPS["prompt_generator"])
    prompt_generator_action.setStatusTip(MENU_TOOLTIPS["prompt_generator"])
    def open_prompt_generator():
        dlg = PromptGeneratorDialog(window)
        dlg.exec()
    prompt_generator_action.triggered.connect(open_prompt_generator)
    tools_menu.addAction(prompt_generator_action)

    from dialogs.tools.prompt_injector import PromptInjectorDialog
    prompt_injector_action = QAction(qta.icon('fa6s.bolt'), "Prompt Injector", window)
    prompt_injector_action.setToolTip("Inject prompts/clicks using points and clipboard")
    prompt_injector_action.setStatusTip("Inject prompts/clicks using points and clipboard")
    def open_prompt_injector():
        if not hasattr(window, '_prompt_injector_dialog') or not window._prompt_injector_dialog:
            window._prompt_injector_dialog = PromptInjectorDialog(None)
            window._prompt_injector_dialog.destroyed.connect(lambda: setattr(window, '_prompt_injector_dialog', None))
        window._prompt_injector_dialog.show()
        window._prompt_injector_dialog.raise_()
        window._prompt_injector_dialog.activateWindow()
    prompt_injector_action.triggered.connect(open_prompt_injector)
    tools_menu.addAction(prompt_injector_action)

    imagen_generator_action = QAction(qta.icon('fa6s.image'), "Imagen Generator", window)
    imagen_generator_action.setToolTip(MENU_TOOLTIPS["imagen_generator"])
    imagen_generator_action.setStatusTip(MENU_TOOLTIPS["imagen_generator"])
    def open_imagen_generator():
        dlg = ImagenGeneratorDialog(window)
        dlg.exec()
    imagen_generator_action.triggered.connect(open_imagen_generator)
    tools_menu.addAction(imagen_generator_action)

    batch_audio_remover_action = QAction(qta.icon('fa6s.volume-xmark'), "Batch Audio Remover", window)
    batch_audio_remover_action.setToolTip(MENU_TOOLTIPS["batch_audio_remover"])
    batch_audio_remover_action.setStatusTip(MENU_TOOLTIPS["batch_audio_remover"])
    def open_batch_audio_remover():
        dlg = BatchAudioRemoverDialog(window)
        dlg.exec()
    batch_audio_remover_action.triggered.connect(open_batch_audio_remover)
    tools_menu.addAction(batch_audio_remover_action)

    envato_elements_action = QAction(qta.icon('fa6s.tag'), "Envato Elements Metadata", window)
    envato_elements_action.setToolTip(MENU_TOOLTIPS["envato_elements_metadata"])
    envato_elements_action.setStatusTip(MENU_TOOLTIPS["envato_elements_metadata"])
    def open_envato_elements():
        if not hasattr(window, '_envato_elements_dialog') or not window._envato_elements_dialog:
            window._envato_elements_dialog = EnvatoElementsMetadataDialog(None)
            window._envato_elements_dialog.destroyed.connect(lambda: setattr(window, '_envato_elements_dialog', None))
        window._envato_elements_dialog.show()
        window._envato_elements_dialog.raise_()
        window._envato_elements_dialog.activateWindow()
    envato_elements_action.triggered.connect(open_envato_elements)
    tools_menu.addAction(envato_elements_action)

    action_sequencer_action = QAction(qta.icon('fa6s.list-check'), "Action Sequencer", window)
    action_sequencer_action.setToolTip(MENU_TOOLTIPS["action_sequencer"])
    action_sequencer_action.setStatusTip(MENU_TOOLTIPS["action_sequencer"])
    def open_action_sequencer():
        if not hasattr(window, '_action_sequencer_dialog') or not window._action_sequencer_dialog:
            window._action_sequencer_dialog = ActionSequencerDialog(None)
            window._action_sequencer_dialog.destroyed.connect(lambda: setattr(window, '_action_sequencer_dialog', None))
        window._action_sequencer_dialog.show()
        window._action_sequencer_dialog.raise_()
        window._action_sequencer_dialog.activateWindow()
    action_sequencer_action.triggered.connect(open_action_sequencer)
    tools_menu.addAction(action_sequencer_action)

    video_upscaler_action = QAction(qta.icon('fa6s.video'), "Video Upscaler", window)
    video_upscaler_action.setToolTip(MENU_TOOLTIPS["video_upscaler"])
    video_upscaler_action.setStatusTip(MENU_TOOLTIPS["video_upscaler"])
    def open_video_upscaler():
        if not hasattr(window, '_video_upscaler_dialog') or not window._video_upscaler_dialog:
            window._video_upscaler_dialog = VideoUpscalerDialog(None)
            window._video_upscaler_dialog.destroyed.connect(lambda: setattr(window, '_video_upscaler_dialog', None))
        window._video_upscaler_dialog.show()
        window._video_upscaler_dialog.raise_()
        window._video_upscaler_dialog.activateWindow()
    video_upscaler_action.triggered.connect(open_video_upscaler)
    tools_menu.addAction(video_upscaler_action)

    image_upscaler_action = QAction(qta.icon('fa6s.image'), "Image Upscaler", window)
    image_upscaler_action.setToolTip(MENU_TOOLTIPS["image_upscaler"])
    image_upscaler_action.setStatusTip(MENU_TOOLTIPS["image_upscaler"])
    def open_image_upscaler():
        if not hasattr(window, '_image_upscaler_dialog') or not window._image_upscaler_dialog:
            window._image_upscaler_dialog = ImageUpscalerDialog(None)
            window._image_upscaler_dialog.destroyed.connect(lambda: setattr(window, '_image_upscaler_dialog', None))
        window._image_upscaler_dialog.show()
        window._image_upscaler_dialog.raise_()
        window._image_upscaler_dialog.activateWindow()
    image_upscaler_action.triggered.connect(open_image_upscaler)
    tools_menu.addAction(image_upscaler_action)

    from dialogs.tools.pngtree_zipper_tool import PngtreeZipperDialog
    pngtree_zipper_action = QAction(qta.icon('fa6s.file-zipper'), "Pngtree Zipper", window)
    pngtree_zipper_action.setToolTip(MENU_TOOLTIPS["pngtree_zipper"])
    pngtree_zipper_action.setStatusTip(MENU_TOOLTIPS["pngtree_zipper"])
    def open_pngtree_zipper():
        if not hasattr(window, '_pngtree_zipper_dialog') or not window._pngtree_zipper_dialog:
            window._pngtree_zipper_dialog = PngtreeZipperDialog(None)
            window._pngtree_zipper_dialog.destroyed.connect(lambda: setattr(window, '_pngtree_zipper_dialog', None))
        window._pngtree_zipper_dialog.show()
        window._pngtree_zipper_dialog.raise_()
        window._pngtree_zipper_dialog.activateWindow()
    pngtree_zipper_action.triggered.connect(open_pngtree_zipper)
    tools_menu.addAction(pngtree_zipper_action)

    extension_menu = QMenu("Extension", menubar)
    extension_menu.setToolTipsVisible(True)
    
    def populate_extension_menu():
        extension_menu.clear()
        extensions_path = os.path.join(BASE_PATH, "tools", "extension")
        
        if not os.path.exists(extensions_path):
            no_ext_action = QAction("No extensions found", window)
            no_ext_action.setEnabled(False)
            extension_menu.addAction(no_ext_action)
            return
        
        extension_folders = [
            d for d in os.listdir(extensions_path) 
            if os.path.isdir(os.path.join(extensions_path, d))
        ]
        
        if not extension_folders:
            no_ext_action = QAction("No extensions found", window)
            no_ext_action.setEnabled(False)
            extension_menu.addAction(no_ext_action)
            return
        
        from dialogs.extension_install_dialog import ExtensionInstallDialog
        
        for folder in sorted(extension_folders):
            display_name = folder.replace('-', ' ').replace('_', ' ').title()
            ext_path = os.path.join(extensions_path, folder)
            
            action = QAction(qta.icon('fa6b.chrome'), display_name, window)
            action.setToolTip(f"Install {display_name} Chrome extension")
            action.setStatusTip(f"Install {display_name} Chrome extension")
            
            def create_open_extension_handler(name, path):
                def open_extension():
                    dlg = ExtensionInstallDialog(name, path, window)
                    dlg.exec()
                return open_extension
            
            action.triggered.connect(create_open_extension_handler(display_name, ext_path))
            extension_menu.addAction(action)
    
    extension_menu.aboutToShow.connect(populate_extension_menu)
    populate_extension_menu()

    # Add separator
    tools_menu.addSeparator()

    # Add additional tools from config
    def get_additional_tools():
        import json
        import os
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("additional_tools", {})

    additional_tools = get_additional_tools()

    for tool_key, tool_config in additional_tools.items():
        tool_name = tool_config.get("tool_name", tool_key)
        description = tool_config.get("description", "")
        tool_url = tool_config.get("tool_url", "")
        fa_icon_name = tool_config.get("fa_icon_name", "external-link")
        icon_name = fa_icon_name if '.' in fa_icon_name else f'fa6s.{fa_icon_name}'
        icon = qta.icon(icon_name)

        action = QAction(icon, tool_name, window)
        action.setToolTip(description)
        action.setStatusTip(description)
        def create_open_url_handler(url):
            def open_url():
                if url and isinstance(url, str):
                    webbrowser.open(url)
            return open_url
        action.triggered.connect(create_open_url_handler(tool_url))
        tools_menu.addAction(action)
    menubar.addMenu(file_menu)
    menubar.addMenu(edit_menu)
    menubar.addMenu(metadata_menu)
    menubar.addMenu(prompt_menu)
    menubar.addAction(api_action)
    menubar.addMenu(tools_menu)
    menubar.addMenu(extension_menu)
    menubar.addMenu(purchase_menu)
    menubar.addMenu(help_menu)
    window.setMenuBar(menubar)
