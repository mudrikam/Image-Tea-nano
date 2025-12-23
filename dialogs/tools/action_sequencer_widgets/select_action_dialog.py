from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QListWidget, QListWidgetItem, QPushButton, QWidget)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon
import os
from config import BASE_PATH
import qtawesome as qta
from database.db_operation import ImageTeaDB

class SelectActionDialog(QDialog):
    action_selected = Signal(dict)
    
    def __init__(self, platform_id, parent=None):
        super().__init__(parent)
        self.platform_id = platform_id
        self.db = ImageTeaDB()
        self.all_actions = []
        self.action_sets = {}
        
        self.setWindowTitle("Select Action")
        self.setModal(True)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        self.load_actions_from_db()
        self.resize(500, 400)
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        dialog_icon = qta.icon('fa6s.hand-pointer', color='#3498DB')
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(32, 32))
        header_layout.addWidget(icon_label)
        
        header_label = QLabel("Select Action to Add")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(12)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)
        
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)
        
        action_set_label = QLabel("Action Set")
        action_set_font = QFont()
        action_set_font.setBold(True)
        action_set_label.setFont(action_set_font)
        left_layout.addWidget(action_set_label, 0)
        
        self.action_set_list = QListWidget()
        self.action_set_list.setAlternatingRowColors(True)
        self.action_set_list.setSpacing(2)
        self.action_set_list.setCurrentRow(0)
        self.action_set_list.currentTextChanged.connect(self.filter_actions)
        self.action_set_list.setMinimumWidth(150)
        self.action_set_list.setMaximumWidth(200)
        left_layout.addWidget(self.action_set_list, 1)
        
        content_layout.addLayout(left_layout, 0)
        
        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)
        
        action_label = QLabel("Actions")
        action_label_font = QFont()
        action_label_font.setBold(True)
        action_label.setFont(action_label_font)
        right_layout.addWidget(action_label, 0)
        
        self.action_list = QListWidget()
        self.action_list.setAlternatingRowColors(True)
        self.action_list.setSpacing(2)
        self.action_list.itemDoubleClicked.connect(self.on_action_double_clicked)
        right_layout.addWidget(self.action_list, 1)
        
        content_layout.addLayout(right_layout, 1)
        
        layout.addLayout(content_layout, 1)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        add_button = QPushButton(qta.icon('fa6s.plus'), " Add Action")
        add_button.clicked.connect(self.on_add_clicked)
        add_button.setDefault(True)
        button_layout.addWidget(add_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_actions_from_db(self):
        try:
            self.all_actions = self.db.get_all_actions_for_platform(self.platform_id)
            
            self.action_sets = {}
            for action in self.all_actions:
                action_set_name = action['action_set']
                if action_set_name not in self.action_sets:
                    self.action_sets[action_set_name] = []
                self.action_sets[action_set_name].append(action)
            
            self.action_set_list.clear()
            self.action_set_list.addItem("All")
            
            for action_set_name in sorted(self.action_sets.keys()):
                self.action_set_list.addItem(action_set_name)
            
            self.action_set_list.setCurrentRow(0)
            self.filter_actions("All")
        except Exception as e:
            print(f"Failed to load actions: {e}")
    
    def filter_actions(self, filter_text):
        self.action_list.clear()
        
        for action in self.all_actions:
            if filter_text == "All" or action["action_set"] == filter_text:
                self.add_action_to_list(action)
    
    def add_action_to_list(self, action_data):
        item = QListWidgetItem()
        
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)
        
        icon_label = QLabel()
        if "icon" in action_data:
            # Default render dengan fa6s (solid)
            icon_name = action_data["icon"]
            if "." not in icon_name:
                full_icon_name = f"fa6s.{icon_name}"
            else:
                full_icon_name = icon_name
            try:
                icon = qta.icon(full_icon_name, color=action_data.get("color", "#888888"))
                icon_label.setPixmap(icon.pixmap(20, 20))
            except:
                pass
        icon_label.setFixedWidth(24)
        layout.addWidget(icon_label)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        
        name_label = QLabel(action_data["name"])
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        content_layout.addWidget(name_label)
        
        set_label = QLabel(action_data["action_set"])
        set_label.setStyleSheet("color: #888; font-size: 10px;")
        content_layout.addWidget(set_label)
        
        layout.addLayout(content_layout)
        layout.addStretch()
        
        widget.setLayout(layout)
        
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, action_data)
        
        self.action_list.addItem(item)
        self.action_list.setItemWidget(item, widget)
    
    def on_action_double_clicked(self, item):
        action_data = item.data(Qt.UserRole)
        self.action_selected.emit(action_data)
        self.accept()
    
    def on_add_clicked(self):
        current_item = self.action_list.currentItem()
        if current_item:
            action_data = current_item.data(Qt.UserRole)
            self.action_selected.emit(action_data)
            self.accept()
