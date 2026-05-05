"""
Tools Dependency Helper - Check if required tools are installed before opening a dialog.
If missing, opens the Tools Manager dialog for the user to install them.

Usage:
    from helpers.tools_dependency_helper import check_tools_available
    
    # In your dialog or action handler:
    if not check_tools_available(["ffmpeg", "realesrgan"], parent=self):
        return  # Tools missing, Tools Manager was shown
"""
import os
from config import BASE_PATH


def check_tools_available(required_tools: list, parent=None) -> bool:
    """
    Check if all required tools are installed.
    If any are missing, show Tools Manager dialog and return False.
    
    Args:
        required_tools: List of tool names (e.g. ["ffmpeg", "realesrgan"])
        parent: Parent widget for the Tools Manager dialog
        
    Returns:
        True if all tools are available, False if any are missing.
    """
    from tools.tools_checker import get_tool_status

    missing = []
    for tool_name in required_tools:
        status = get_tool_status(tool_name)
        if not status['installed']:
            missing.append(tool_name)

    if not missing:
        return True

    # Show Tools Manager
    _show_tools_manager_for_missing(missing, parent)
    return False


def _show_tools_manager_for_missing(missing_tools: list, parent=None):
    """Open Tools Manager and inform user about missing tools."""
    from PySide6.QtWidgets import QMessageBox

    tools_list = "\n".join(f"  - {t}" for t in missing_tools)
    msg = (
        f"The following required tool(s) are not installed:\n\n"
        f"{tools_list}\n\n"
        f"Opening Tools Manager to install them."
    )
    QMessageBox.information(parent, "Missing Tools", msg)

    # Open Tools Manager
    from dialogs.tools.tools_manager.tools_manager_dialog import ToolsManagerDialog
    
    # Try to reuse existing instance on main window
    main_window = parent
    while main_window and main_window.parent():
        main_window = main_window.parent()

    if main_window and hasattr(main_window, '_tools_manager_dialog'):
        if not main_window._tools_manager_dialog:
            main_window._tools_manager_dialog = ToolsManagerDialog(main_window)
            main_window._tools_manager_dialog.destroyed.connect(
                lambda: setattr(main_window, '_tools_manager_dialog', None)
            )
        main_window._tools_manager_dialog.show()
        main_window._tools_manager_dialog.raise_()
        main_window._tools_manager_dialog.activateWindow()
    else:
        # Fallback: open as modal
        dlg = ToolsManagerDialog(parent)
        dlg.exec()
