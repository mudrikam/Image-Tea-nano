from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
                               QAbstractItemView)
from PySide6.QtCore import Qt
import qtawesome as qta


class DeleteConfirmationDialog(QDialog):
    """Custom delete confirmation dialog with scrollable table of items."""
    
    def __init__(self, parent=None, collection_name="", sub_collections=None, scripts=None):
        super().__init__(parent)
        self.collection_name = collection_name
        self.sub_collections = sub_collections or []
        self.scripts = scripts or []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle('Confirm Delete')
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header message
        header_label = QLabel(f'You are about to delete collection <b>"{self.collection_name}"</b>.')
        header_label.setWordWrap(True)
        header_label.setTextFormat(Qt.RichText)
        layout.addWidget(header_label)
        
        # Count labels
        if self.sub_collections:
            coll_count_label = QLabel(f'Sub-collections ({len(self.sub_collections)}):')
            layout.addWidget(coll_count_label)
        
        if self.scripts:
            script_count_label = QLabel(f'Scripts ({len(self.scripts)}):')
            layout.addWidget(script_count_label)
        
        # Create table for displaying items (has built-in scrolling)
        table = QTableWidget()
        total_items = len(self.sub_collections) + len(self.scripts)
        
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(['Name'])
        table.verticalHeader().setVisible(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setAlternatingRowColors(True)
        
        # Populate table rows
        row = 0
        table.setRowCount(total_items)
        
        # Add sub-collections
        for i, name in enumerate(self.sub_collections):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsSelectable)
            table.setItem(row, 0, name_item)
            row += 1
        
        # Add scripts
        for i, name in enumerate(self.scripts):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsSelectable)
            table.setItem(row, 0, name_item)
            row += 1
        
        # Resize columns
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(table)
        
        # Empty state if no items
        if not self.sub_collections and not self.scripts:
            empty_label = QLabel('This collection is empty.')
            empty_label.setWordWrap(True)
            layout.addWidget(empty_label)
        
        # Warning message (non-scrollable)
        warning_label = QLabel('<font color="red"><b>This action cannot be undone.</b></font>')
        warning_label.setTextFormat(Qt.RichText)
        layout.addWidget(warning_label)
        
        # Button layout
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton('Cancel')
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.clicked.connect(self.reject)
        
        yes_btn = QPushButton('Delete')
        yes_btn.setIcon(qta.icon('fa6s.trash'))
        yes_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(yes_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.resize(500, 400)
