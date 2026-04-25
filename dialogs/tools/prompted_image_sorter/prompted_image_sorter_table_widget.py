from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton, QHBoxLayout, QWidget, QMessageBox
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QColor
import qtawesome as qta
import re


class PromptedImageSorterTableWidget(QTableWidget):
    """Table widget for displaying sorted images with Folder, Rule Description, and Actions columns."""

    # Signals to notify parent of data changes
    row_added = Signal()
    row_renamed = Signal(int, str, str)  # row, old_name, new_name
    row_deleted = Signal(int, str)       # row, folder_name
    data_changed = Signal()  # emitted when any cell changes (for auto-save)
    edit_row_requested = Signal(int)     # emitted when edit button clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlight_rows = {}  # {row: {'color': QColor, 'timer': QTimer}}
        self._setup_table()

    def _setup_table(self):
        """Configure table columns and behavior."""
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Folder", "Rule Description", "Actions"])

        # Column sizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        # Vanilla editable table – auto-save on change
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setTabKeyNavigation(True)

        # Vertical header with row numbers
        self.verticalHeader().setVisible(True)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(22)

        # Use default Qt styling (grid lines visible) like prompt generator
        # Vanilla table – no custom stylesheet
        self.cellChanged.connect(self._on_cell_changed)

    def _on_cell_changed(self, row, col):
        """Handle cell edit – sanitize and emit signal for parent to save."""
        if row < 0 or col < 0:
            return
        fitem = self.item(row, 0)
        if not fitem:
            return
        # Sanitize folder name on the fly (col 0 = folder name)
        if col == 0:
            raw = fitem.text()
            sanitized = self._sanitize_folder_name(raw)
            if sanitized != raw:
                fitem.setText(sanitized)
        # Emit signal so parent handles save
        self.data_changed.emit()

    def _sanitize_folder_name(self, name):
        """Sanitize folder name: keep alphanumeric, spaces, backslash for subfolders."""
        name = re.sub(r'[^a-zA-Z0-9 \\]', '', name)
        name = ' '.join(name.strip().split())
        # Collapse spaces around backslash
        name = name.replace(' \\ ', '\\').replace(' \\', '\\').replace('\\ ', '\\')
        return name

    # --- Row highlight during processing ---
    def highlight_row(self, row, color, duration_ms=2000):
        """Highlight a row with given color for duration_ms, then clear it."""
        if row < 0 or row >= self.rowCount():
            return

        # Stop existing timer for this row
        if row in self._highlight_rows and self._highlight_rows[row].get('timer'):
            self._highlight_rows[row]['timer'].stop()

        # Apply highlight
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setBackground(color)

        # Set timer to clear
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._clear_row_highlight(row))
        timer.start(duration_ms)
        self._highlight_rows[row] = {'color': color, 'timer': timer}

    def _clear_row_highlight(self, row):
        """Remove highlight from a row."""
        if row < 0 or row >= self.rowCount():
            return
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setBackground(QColor(0, 0, 0, 0))
        if row in self._highlight_rows:
            del self._highlight_rows[row]

    def clear_all_highlights(self):
        """Clear all row highlights."""
        for row in list(self._highlight_rows.keys()):
            self._clear_row_highlight(row)

    def get_folder_data(self):
        """Return all folder data as list of dicts."""
        folders = []
        for r in range(self.rowCount()):
            fitem = self.item(r, 0)
            pitem = self.item(r, 1)
            if fitem:
                folders.append({
                    'folder_name': fitem.text().strip(),
                    'prompt': pitem.text().strip() if pitem else ''
                })
        return folders

    # --- Action buttons ---
    def _create_action_buttons(self, row):
        """Create delete and rename buttons for the Actions column."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)

        rename_btn = QPushButton(qta.icon('fa6s.pen'), "")
        rename_btn.setToolTip("Rename this folder")
        rename_btn.setFixedSize(20, 20)
        rename_btn.setIconSize(QSize(12, 12))
        rename_btn.clicked.connect(lambda: self._on_rename_clicked(row))
        layout.addWidget(rename_btn)

        delete_btn = QPushButton(qta.icon('fa6s.trash'), "")
        delete_btn.setToolTip("Delete this folder")
        delete_btn.setFixedSize(20, 20)
        delete_btn.setIconSize(QSize(12, 12))
        delete_btn.clicked.connect(lambda: self._on_delete_clicked(row))
        layout.addWidget(delete_btn)

        layout.addStretch()
        return widget

    def _on_rename_clicked(self, row):
        """Emit signal for parent to open edit dialog for this folder rule."""
        self.edit_row_requested.emit(row)

    def _on_delete_clicked(self, row):
        """Handle delete button click."""
        fitem = self.item(row, 0)
        if not fitem:
            return
        folder_name = fitem.text()

        mb = QMessageBox(self)
        mb.setWindowTitle("Delete Folder")
        mb.setText(f"Delete folder rule '{folder_name}'?")
        mb.setIcon(QMessageBox.Warning)
        mb.addButton(QMessageBox.Yes)
        mb.addButton(QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)
        if mb.exec() == QMessageBox.Yes:
            self.removeRow(row)
            for r in range(self.rowCount()):
                w = self.cellWidget(r, 2)
                if w:
                    for btn in w.findChildren(QPushButton):
                        btn.setProperty('row', r)
            self.row_deleted.emit(row, folder_name)
            self.data_changed.emit()

    def add_folder_row(self, folder_name, prompt):
        """Add a new row with folder name and prompt."""
        row = self.rowCount()
        self.insertRow(row)

        folder_item = QTableWidgetItem(folder_name)
        self.setItem(row, 0, folder_item)

        prompt_item = QTableWidgetItem(prompt)
        self.setItem(row, 1, prompt_item)

        action_widget = self._create_action_buttons(row)
        self.setCellWidget(row, 2, action_widget)

        self.row_added.emit()