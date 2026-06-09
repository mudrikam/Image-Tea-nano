from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.theme_system import theme


class AccountManagerStatsWidget(QWidget):
    """Stats bar showing workspace/group/profile counts"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        stats_layout = QHBoxLayout(self)
        stats_layout.setContentsMargins(8, 4, 8, 4)
        stats_layout.setSpacing(12)
        
        def _add_stat(icon_name, initial_text, color_key='text_dark'):
            icon_lbl = QLabel()
            icon = qta.icon(icon_name, color=theme.get_color(color_key))
            pix = icon.pixmap(12, 12)
            icon_lbl.setPixmap(pix)
            text_lbl = QLabel(initial_text)
            text_lbl.setStyleSheet(f"color: {theme.get_color(color_key)}; font-size: 11px;")
            stats_layout.addWidget(icon_lbl)
            stats_layout.addWidget(text_lbl)
            return text_lbl
        
        self.stats_workspace_lbl = _add_stat('fa6s.briefcase', 'Workspaces: 0', 'gray')
        self.stats_group_lbl = _add_stat('fa6s.users', 'Groups: 0', 'gray')
        self.stats_profile_lbl = _add_stat('fa6s.user-group', 'Profiles: 0', 'gray')
        
        stats_layout.addStretch()
        self.setFixedHeight(26)
    
    def update_stats(self, workspace_count, group_count, profile_count):
        """Update stats display"""
        self.stats_workspace_lbl.setText(f'Workspaces: {workspace_count}')
        self.stats_group_lbl.setText(f'Groups: {group_count}')
        self.stats_profile_lbl.setText(f'Profiles: {profile_count}')