"""
Standalone test script to launch Prompted Image Sorter dialog without running main Image Tea app.
Usage: python run_prompted_image_sorter_test.py
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication
from database.db_operation import ImageTeaDB
from dialogs.tools.prompted_image_sorter.prompted_image_sorter_tool import PromptedImageSorterTool

def main():
    # Initialize Qt application
    app = QApplication(sys.argv)

    # Create a placeholder DB object (the tool will create its own)
    # No need to pass parent since we're testing standalone
    dialog = PromptedImageSorterTool(parent=None)

    # Show dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()

    # Run event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
