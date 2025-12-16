from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox, QDialog, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtGui import QAction, QPixmap, QIcon
from PySide6.QtCore import Qt
import qtawesome as qta
import webbrowser
import sys
import os
import subprocess
import json
from helpers.file_importer import import_files
from helpers.metadata_helper.metadata_operation import write_metadata_to_images, write_metadata_to_videos
from dialogs.csv_exporter_dialog import CSVExporterDialog
from dialogs.edit_prompt_dialog import EditPromptDialog
from dialogs.custom_prompt_dialog import CustomPromptDialog
from dialogs.batch_rename_dialog import BatchRenameDialog
from dialogs.read_documentation_dialog import ReadDocumentationDialog
from dialogs.donation_dialog import DonateDialog
from dialogs.add_api_key_dialog import AddApiKeyDialog
from dialogs.about_dialog import AboutDialog
from dialogs.file_metadata_dialog import FileMetadataDialog
from dialogs.update_notice_dialog import UpdateNoticeDialog
from config import BASE_PATH
from dialogs.tools.prompt_generator_tool import PromptGeneratorDialog
from dialogs.tools.imagen_generator_tool import ImagenGeneratorDialog
from dialogs.video_proxy_prompt_settings_dialog import VideoProxyPromptSettingsDialog

# Menu tooltips dictionary
MENU_TOOLTIPS = {
    # File menu
    "import_files": "Import image and video files into the database for metadata processing",
    "relaunch": "Restart the application with current settings",
    "exit": "Close the application",
    
    # Edit menu
    "delete_selected": "Remove selected files from the database",
    "clear_all": "Remove all files from the database",
    "clear_metadata": "Remove all metadata from database (not from files)",
    "batch_rename": "Rename multiple files with custom patterns",
    "edit_metadata": "Edit metadata for selected file",
    
    # Metadata menu
    "write_images": "Embed metadata into image files",
    "write_videos": "Embed metadata into video files", 
    "export_csv": "Export metadata to CSV file for external use",
    
    # Prompt menu
    "edit_prompt": "Configure AI prompt templates and settings",
    "custom_prompt": "Generate custom prompts using AI",
    
    # API menu
    "add_api_key": "Add or manage API keys for AI services",
    
    # Tools menu
    "prompt_generator": "Generate AI prompts for image/video creation",
    "imagen_generator": "Generate images using Google's Imagen AI",
    
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

def clear_existing_metadata(window):
    msg = (
        "Are you sure you want to clear all metadata (title, description, tags, status and categories)?\n\n"
        "This will NOT remove metadata embedded in the image files, only metadata stored in the database."
    )
    reply = QMessageBox.question(window, "Clear Metadata", msg, QMessageBox.Yes | QMessageBox.No)
    if reply == QMessageBox.Yes:
        window.db.clear_all_metadata()
        window.table.refresh_table()

def run_updater(window):
    updater_path = os.path.join(BASE_PATH, "Image Tea Updater.exe")
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                f'powershell -Command "Start-Process -Verb runAs -FilePath \\"{updater_path}\\""',
                shell=True
            )
        else:
            subprocess.Popen([updater_path])
    except Exception as e:
        print(f"Failed to run updater: {e}")

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

    clear_action = QAction(qta.icon('fa6s.broom'), "Clear All", window)
    clear_action.setToolTip(MENU_TOOLTIPS["clear_all"])
    clear_action.setStatusTip(MENU_TOOLTIPS["clear_all"])
    clear_action.triggered.connect(lambda: window.table.clear_all())
    edit_menu.addAction(clear_action)

    clear_metadata_action = QAction(qta.icon('fa6s.eraser'), "Clear Existing Metadata", window)
    clear_metadata_action.setToolTip(MENU_TOOLTIPS["clear_metadata"])
    clear_metadata_action.setStatusTip(MENU_TOOLTIPS["clear_metadata"])
    clear_metadata_action.triggered.connect(lambda: clear_existing_metadata(window))
    edit_menu.addAction(clear_metadata_action)

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

    prompt_menu = QMenu("Prompt", menubar)
    prompt_menu.setToolTipsVisible(True)
    edit_prompt_action = QAction(qta.icon('fa6s.pen-to-square'), "Edit Prompt", window)
    edit_prompt_action.setToolTip(MENU_TOOLTIPS["edit_prompt"])
    edit_prompt_action.setStatusTip(MENU_TOOLTIPS["edit_prompt"])
    def open_edit_prompt():
        dialog = EditPromptDialog(window)
        dialog.exec()
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

    api_menu = QMenu("API", menubar)
    api_menu.setToolTipsVisible(True)
    add_api_action = QAction(qta.icon('fa6s.key'), "Add API Key", window)
    add_api_action.setToolTip(MENU_TOOLTIPS["add_api_key"])
    add_api_action.setStatusTip(MENU_TOOLTIPS["add_api_key"])
    def show_api_dialog():
        dlg = AddApiKeyDialog(window)
        dlg.exec()
    add_api_action.triggered.connect(show_api_dialog)
    api_menu.addAction(add_api_action)

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
        dialog = ReadDocumentationDialog(window)
        dialog.exec()
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
        # open as independent non-modal tool (no parent) so it's always-on-top and doesn't block main window
        dlg = PromptInjectorDialog(None)
        dlg.show()
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
        
        # Try fa6s first, fallback to fa5b
        try:
            icon = qta.icon(f'fa6s.{fa_icon_name}')
        except:
            try:
                icon = qta.icon(f'fa5b.{fa_icon_name}')
            except:
                icon = qta.icon('fa6s.link')
        
        action = QAction(icon, tool_name, window)
        action.setToolTip(description)
        action.setStatusTip(description)
        # Use closure to capture the URL properly
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
    menubar.addMenu(api_menu)
    menubar.addMenu(tools_menu)
    menubar.addMenu(help_menu)
    window.setMenuBar(menubar)
