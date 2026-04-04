from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QTextEdit
from PySide6.QtCore import Qt, Signal


class ScriptsWidget(QWidget):
    script_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = parent.db if parent else None
        self.current_collection_id = None
        self.scripts = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.scripts_list = QListWidget()
        self.scripts_list.setSelectionMode(QListWidget.SingleSelection)
        self.scripts_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.scripts_list)

    def load_scripts(self, collection_id):
        self.current_collection_id = collection_id
        self.scripts_list.clear()
        self.scripts = []

        if not self.db or not collection_id:
            return

        self.scripts = self.db.get_remotion_scripts(collection_id, active_only=True)
        for script in self.scripts:
            item = QListWidgetItem(f"{script['name']} (v{script['version']})")
            item.setData(Qt.UserRole, script)
            self.scripts_list.addItem(item)

    def _on_selection_changed(self):
        selected = self.scripts_list.selectedItems()
        if selected:
            script = selected[0].data(Qt.UserRole)
            self.script_selected.emit(script)
        else:
            self.script_selected.emit(None)

    def refresh(self):
        if self.current_collection_id:
            self.load_scripts(self.current_collection_id)
