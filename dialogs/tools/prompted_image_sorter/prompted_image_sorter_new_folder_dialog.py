import os
import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class PromptedImageSorterNewFolderDialog(QDialog):
    """Dialog for creating or editing a sorting folder with sanitized name and prompt."""

    def __init__(self, parent=None, edit_mode=False, initial_folder='', initial_prompt=''):
        super().__init__(parent)
        self.edit_mode = edit_mode
        self.setFixedWidth(480)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setModal(True)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()

        if edit_mode:
            self.setWindowTitle('Edit Folder Rule')
            self.create_button.setText(" Update")
            # Set initial values
            self.folder_name_input.setText(initial_folder)
            self.prompt_input.setText(initial_prompt)
        else:
            self.setWindowTitle('New Sorting Folder')

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- Folder name row ---
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(6)

        folder_icon = QLabel()
        folder_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        folder_layout.addWidget(folder_icon)

        folder_label = QLabel("Folder Name:")
        folder_label.setMinimumWidth(80)
        folder_layout.addWidget(folder_label)

        self.folder_name_input = QLineEdit()
        self.folder_name_input.setPlaceholderText("e.g. cat or animal\\cat (subfolder)")
        self.folder_name_input.setToolTip("Folder name or path (e.g. 'cat' or 'animal\\cat' for subfolder)")
        folder_layout.addWidget(self.folder_name_input, 1)

        layout.addLayout(folder_layout)

        # --- Prompt row ---
        prompt_layout = QHBoxLayout()
        prompt_layout.setSpacing(6)

        prompt_icon = QLabel()
        prompt_icon.setPixmap(qta.icon('fa6s.keyboard', color=theme.get_color('gray')).pixmap(16, 16))
        prompt_layout.addWidget(prompt_icon)

        prompt_label = QLabel("Prompt:")
        prompt_label.setMinimumWidth(80)
        prompt_layout.addWidget(prompt_label)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter AI prompt description for this folder...")
        self.prompt_input.setToolTip("Description of what images should be sorted into this folder")
        prompt_layout.addWidget(self.prompt_input, 1)

        layout.addLayout(prompt_layout)

        # --- Button row ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
        self.cancel_button.setToolTip("Cancel folder creation")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.create_button = QPushButton(qta.icon('fa6s.check'), " Create")
        self.create_button.setToolTip("Create new folder with these settings")
        self.create_button.clicked.connect(self._on_create)
        button_layout.addWidget(self.create_button)

        layout.addLayout(button_layout)

        # Connect input validation
        self.folder_name_input.textChanged.connect(self._validate_folder_name)
        self.folder_name_input.setFocus()

    def _validate_folder_name(self, text):
        """Validate and sanitize folder name input in real-time."""
        if not text:
            return
        # Allow alphanumeric, spaces, and backslash for subfolders
        sanitized = re.sub(r'[^a-zA-Z0-9 \\]', '', text)
        if sanitized != text:
            cursor_pos = self.folder_name_input.cursorPosition()
            self.folder_name_input.setText(sanitized)
            self.folder_name_input.setCursorPosition(max(0, cursor_pos - 1))

    def _sanitize_folder_name(self, name):
        """Sanitize folder name: keep alphanumeric, spaces, backslash (subfolders), strip whitespace."""
        name = re.sub(r'[^a-zA-Z0-9 \\]', '', name)
        # Collapse multiple spaces, strip leading/trailing
        name = ' '.join(name.strip().split())
        # But preserve backslash structure - only collapse spaces around it
        name = name.replace(' \\ ', '\\').replace(' \\', '\\').replace('\\ ', '\\')
        return name

    def _on_create(self):
        """Handle Create button click."""
        raw_folder_name = self.folder_name_input.text().strip()
        folder_name = self._sanitize_folder_name(raw_folder_name)
        prompt = self.prompt_input.text().strip()

        # Validation
        if not folder_name:
            QMessageBox.warning(
                self,
                "Invalid Folder Name",
                "Folder name cannot be empty.\n\nPlease enter a valid folder name using only letters, numbers, and spaces."
            )
            self.folder_name_input.setFocus()
            return

        if not prompt:
            QMessageBox.warning(
                self,
                "Missing Prompt",
                "Prompt description cannot be empty.\n\nPlease enter a prompt describing what images should be sorted into this folder."
            )
            self.prompt_input.setFocus()
            return

        # Store results and accept
        self.folder_name = folder_name
        self.prompt = prompt
        self.accept()

    def get_data(self):
        """Return the sanitized folder name and prompt."""
        return getattr(self, 'folder_name', ''), getattr(self, 'prompt', '')
