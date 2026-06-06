import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class ExportProfileDialog(QDialog):
    """Dialog for selecting profile to export"""
    
    def __init__(self, profiles, group_name='profiles', parent=None):
        super().__init__(parent)
        self.profiles = profiles
        self.group_name = group_name
        self.selected_profile = None
        self.selected_profiles = []  # For export all
        self.is_export_all = False
        self.setWindowTitle('Export Profile')
        self.setModal(True)
        self.setMinimumWidth(400)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.file-zipper', color=theme.get_color('primary')).pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel('Select Profile to Export')
        title_label.setStyleSheet('font-size: 14px; font-weight: bold;')
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        search_icon = QLabel()
        search_icon.setPixmap(qta.icon('fa6s.magnifying-glass', color=theme.get_color('gray')).pixmap(16, 16))
        search_layout.addWidget(search_icon)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Search profiles...')
        self.search_input.textChanged.connect(self._filter_profiles)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(4)
        self._populate_list()
        
        layout.addWidget(self.list_widget)
        
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton(qta.icon('fa6s.xmark'), ' Cancel')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        export_btn = QPushButton(qta.icon('fa6s.file-zipper'), ' Export')
        export_btn.clicked.connect(self._on_export)
        export_btn.setDefault(True)
        button_layout.addWidget(export_btn)
        
        # Export All button - inline with other buttons when multiple profiles
        if len(self.profiles) > 1:
            export_all_btn = QPushButton(qta.icon('fa6s.file-zipper'), f' All ({len(self.profiles)})')
            export_all_btn.clicked.connect(self._on_export_all)
            button_layout.addWidget(export_all_btn)
        
        layout.addLayout(button_layout)
    
    def _populate_list(self):
        """Populate list with profiles"""
        self.list_widget.clear()
        search_text = self.search_input.text().lower() if hasattr(self, 'search_input') else ''
        
        for profile in self.profiles:
            name = profile.get('profile_name', 'Unnamed')
            if search_text and search_text not in name.lower():
                continue
            
            icon_value = profile.get('profile_icon', 'user')
            color = profile.get('profile_color', '#3b82f6')
            
            item = QListWidgetItem()
            item.setData(Qt.UserRole, profile)
            
            icon_pixmap = self._create_profile_icon(icon_value, color)
            item.setIcon(QIcon(icon_pixmap))
            item.setText(name)
            item.setTextAlignment(Qt.AlignVCenter)
            
            self.list_widget.addItem(item)
    
    def _on_export(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, 'No Selection', 'Please select a profile to export')
            return
        
        self.selected_profile = current_item.data(Qt.UserRole)
        self.is_export_all = False
        self.selected_profiles = []
        self.accept()
    
    def _on_export_all(self):
        self.selected_profiles = self.profiles.copy()
        self.is_export_all = True
        self.selected_profile = None
        self.accept()
    
    def _filter_profiles(self):
        """Filter profiles based on search text"""
        self._populate_list()
    
    def _create_profile_icon(self, icon_value, color):
        """Create icon pixmap for profile list item"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        r, g, b = int(color.lstrip('#')[0:2], 16), int(color.lstrip('#')[2:4], 16), int(color.lstrip('#')[4:6], 16)
        
        if icon_value.startswith('initial:'):
            initial = icon_value[8:].upper() or '?'
            circle_color = QColor(r, g, b, 40)
            painter.setBrush(circle_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 24, 24)
            painter.setPen(QColor(r, g, b))
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, initial)
        elif icon_value.startswith('image:'):
            image_path = icon_value[6:]
            if os.path.exists(image_path):
                from PySide6.QtGui import QPainterPath
                path = QPainterPath()
                path.addEllipse(0, 0, 24, 24)
                painter.setClipPath(path)
                img = QPixmap(image_path).scaled(24, 24, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.drawPixmap(0, 0, img)
                painter.setPen(QColor(r, g, b, 100))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(0, 0, 24, 24)
            else:
                icon = qta.icon('fa6s.user', color=color)
                painter.drawPixmap(0, 0, icon.pixmap(24, 24))
        else:
            try:
                if '.' in icon_value:
                    icon = qta.icon(icon_value, color=color)
                else:
                    icon = qta.icon(f'fa6s.{icon_value}', color=color)
                painter.drawPixmap(0, 0, icon.pixmap(24, 24))
            except:
                icon = qta.icon('fa6s.user', color=color)
                painter.drawPixmap(0, 0, icon.pixmap(24, 24))
        
        painter.end()
        return pixmap