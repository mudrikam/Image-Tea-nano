import os
from datetime import datetime
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QPainter, QFont
import qtawesome as qta
from ui.theme_system import theme


def format_human_datetime(dt_string):
    """Format datetime string to compact d/m/y format"""
    if not dt_string:
        return '-'
    try:
        dt = datetime.fromisoformat(dt_string)
        return dt.strftime('%d/%m/%y')
    except:
        return '-'


class ProfileRowWidget(QFrame):
    """Row widget for single profile (like action sequencer step)"""
    launch_clicked = Signal(int)  # profile_id
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    focus_clicked = Signal(int)  # profile_id
    close_clicked = Signal(int)  # profile_id
    export_clicked = Signal(int)  # profile_id
    clicked = Signal(int)  # profile_id - for selection

    def __init__(self, profile_data, parent=None):
        super().__init__(parent)
        self.profile_data = profile_data
        self.profile_id = profile_data['profile_id']
        self._hover = False
        self._launching = False
        self._is_launched = False
        self._selected = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        icon_value = self.profile_data.get('profile_icon', 'user')
        color = self.profile_data.get('profile_color', '#3b82f6')
        name = self.profile_data.get('profile_name', 'Unnamed')
        desc = self.profile_data.get('profile_description', '')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Launch/Focus button - icon only, at left
        c = QColor(color)
        hover_color = QColor(min(255, c.red() + 30), min(255, c.green() + 30), min(255, c.blue() + 30)).name()

        self.launch_btn = QPushButton(qta.icon('fa6s.play', color=theme.get_color('white')), '')
        self.launch_btn.setObjectName(f'launchBtn_{self.profile_id}')
        self.launch_btn.setStyleSheet(f'''
            QPushButton#launchBtn_{self.profile_id} {{
                background-color: {color};
                border: none;
                padding: 8px;
                border-radius: 4px;
                min-width: 20px;
            }}
            QPushButton#launchBtn_{self.profile_id}:hover {{
                background-color: {hover_color};
            }}
        ''')
        self.launch_btn.clicked.connect(lambda: self._on_button_clicked())
        layout.addWidget(self.launch_btn)

        # Close button (X) - visible when launched, icon-only square button
        error_color = theme.get_color('error')
        r, g, b = int(error_color[1:3], 16), int(error_color[3:5], 16), int(error_color[5:7], 16)
        error_hover_brighter = QColor(min(255, r + 30), min(255, g + 30), min(255, b + 30)).name()

        self.close_btn = QPushButton(qta.icon('fa6s.xmark', color=theme.get_color('white')), '')
        self.close_btn.setObjectName(f'closeBtn_{self.profile_id}')
        self.close_btn.setStyleSheet(f'''
            QPushButton#closeBtn_{self.profile_id} {{
                background-color: {error_color};
                border: none;
                padding: 8px;
                border-radius: 4px;
            }}
            QPushButton#closeBtn_{self.profile_id}:hover {{
                background-color: {error_hover_brighter};
            }}
        ''')
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        self.close_btn.setToolTip('Close Browser')
        self.close_btn.clicked.connect(lambda: self.close_clicked.emit(self.profile_id))
        self.close_btn.hide()
        layout.addWidget(self.close_btn)

        # Icon with support for icon, image, and initial modes
        self.icon_label = QLabel()
        self._setup_icon_display(icon_value, color)
        self.icon_label.setFixedSize(28, 28)
        layout.addWidget(self.icon_label)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)

        name_label = QLabel(name)
        name_label.setStyleSheet('font-size: 14px; font-weight: bold;')
        content_layout.addWidget(name_label)

        if desc:
            desc_label = QLabel(desc)
            desc_label.setStyleSheet(f'font-size: 12px; color: {theme.get_color("gray")};')
            desc_label.setWordWrap(False)
            desc_label.setMaximumHeight(18)
            content_layout.addWidget(desc_label)

        layout.addLayout(content_layout, 1)

        # Edit button - vanilla style
        pen_icon = qta.icon('fa6s.pen')
        pen_button = QPushButton(pen_icon, '')
        pen_button.setMaximumWidth(30)
        pen_button.setMaximumHeight(30)
        pen_button.setFlat(True)
        pen_button.setStyleSheet('background: transparent; border: none;')
        pen_button.setFocusPolicy(Qt.NoFocus)
        pen_button.setToolTip('Edit')
        pen_button.clicked.connect(lambda: self.edit_clicked.emit(self.profile_id))
        layout.addWidget(pen_button)

        # Delete button - vanilla style
        trash_icon = qta.icon('fa6s.trash')
        trash_button = QPushButton(trash_icon, '')
        trash_button.setMaximumWidth(30)
        trash_button.setMaximumHeight(30)
        trash_button.setFlat(True)
        trash_button.setStyleSheet('background: transparent; border: none;')
        trash_button.setFocusPolicy(Qt.NoFocus)
        trash_button.setToolTip('Delete')
        trash_button.clicked.connect(lambda: self.delete_clicked.emit(self.profile_id))
        layout.addWidget(trash_button)

        # Timestamp labels - vertical stack after delete button
        created_at = self.profile_data.get('profile_created_at')
        updated_at = self.profile_data.get('profile_updated_at')
        time_layout = QVBoxLayout()
        time_layout.setSpacing(0)
        time_layout.setContentsMargins(0, 0, 0, 0)
        created_label = QLabel(f'C: {format_human_datetime(created_at)}')
        created_label.setStyleSheet(f'font-size: 9px; color: {theme.get_color("gray")};')
        time_layout.addWidget(created_label)
        updated_label = QLabel(f'U: {format_human_datetime(updated_at)}')
        updated_label.setStyleSheet(f'font-size: 9px; color: {theme.get_color("gray")};')
        time_layout.addWidget(updated_label)
        layout.addLayout(time_layout)

    def _setup_icon_display(self, icon_value, color):
        """Setup icon display based on mode (icon, image, or initial)"""
        pixmap = QPixmap(28, 28)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        r_hex, g_hex, b_hex = color.lstrip('#')[0:2], color.lstrip('#')[2:4], color.lstrip('#')[4:6]
        r, g, b = int(r_hex, 16), int(g_hex, 16), int(b_hex, 16)

        if icon_value.startswith('initial:'):
            # Initial mode - show letter in circle bg with gradient tint
            initial = icon_value[8:].upper() or '?'
            circle_color = QColor(r, g, b, 40)  # Light tint for bg
            painter.setBrush(circle_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 28, 28)

            painter.setPen(QColor(r, g, b))
            font = QFont()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, initial)

        elif icon_value.startswith('image:'):
            # Image mode - load and display image in circle
            image_path = icon_value[6:]
            if os.path.exists(image_path):
                # Create circular clip path
                from PySide6.QtGui import QPainterPath
                path = QPainterPath()
                path.addEllipse(0, 0, 28, 28)
                painter.setClipPath(path)
                
                # Draw image filling the circle
                img = QPixmap(image_path).scaled(28, 28, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.drawPixmap(0, 0, img)
                
                # Draw circle border
                painter.setPen(QColor(r, g, b, 100))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(0, 0, 28, 28)
            else:
                # Fallback to user icon
                icon = qta.icon('fa6s.user', color=color)
                painter.drawPixmap(2, 2, icon.pixmap(24, 24))

        else:
            # Icon mode - show FontAwesome icon, no border
            try:
                if '.' not in icon_value:
                    icon = qta.icon(f'fa6s.{icon_value}', color=color)
                else:
                    icon = qta.icon(icon_value, color=color)
                icon_pixmap = icon.pixmap(24, 24)
                painter.drawPixmap(2, 2, icon_pixmap)
            except:
                icon = qta.icon('fa6s.user', color=color)
                painter.drawPixmap(2, 2, icon.pixmap(24, 24))

        painter.end()
        self.icon_label.setPixmap(pixmap)

    def _on_button_clicked(self):
        """Handle launch button click - emits launch or focus signal"""
        if self._is_launched:
            self.focus_clicked.emit(self.profile_id)
        else:
            self.launch_clicked.emit(self.profile_id)

    def set_launching(self, launching):
        """Set launching state - shows spinner icon only"""
        self._launching = launching
        if launching:
            spinner_icon = qta.icon('fa6s.spinner', color=theme.get_color('white'), animation=qta.Spin(self.launch_btn))
            self.launch_btn.setIcon(spinner_icon)
            self.launch_btn.setEnabled(False)
        else:
            self.launch_btn.setIcon(qta.icon('fa6s.play', color=theme.get_color('white')))
            self.launch_btn.setEnabled(True)

    def set_launched(self, launched):
        """Set launched state - shows focus icon and close X"""
        self._is_launched = launched
        self._update_style()
        if launched:
            self.launch_btn.setIcon(qta.icon('fa6s.arrow-up-right-from-square', color=theme.get_color('white')))
            self.close_btn.show()
        else:
            self.launch_btn.setIcon(qta.icon('fa6s.play', color=theme.get_color('white')))
            self.close_btn.hide()

    def set_selected(self, selected):
        """Set selected state - shows selected style"""
        self._selected = selected
        self._update_style()

    def _update_style(self):
        color = self.profile_data.get('profile_color', '#3b82f6')
        gray = QColor(theme.get_color('gray'))
        r_hex, g_hex, b_hex = color.lstrip('#')[0:2], color.lstrip('#')[2:4], color.lstrip('#')[4:6]
        r, g, b = int(r_hex, 16), int(g_hex, 16), int(b_hex, 16)

        # Selected state gets strongest styling, then launched, then hover
        if self._selected:
            self.setStyleSheet(f'''
                ProfileRowWidget {{
                    background-color: rgba({r}, {g}, {b}, 0.25);
                    border: 1px solid {color};
                    border-radius: 4px;
                }}
            ''')
        elif self._is_launched or self._hover:
            self.setStyleSheet(f'''
                ProfileRowWidget {{
                    background-color: rgba({r}, {g}, {b}, 0.12);
                    border: 1px solid {color};
                    border-radius: 4px;
                }}
            ''')
        else:
            self.setStyleSheet(f'''
                ProfileRowWidget {{
                    background-color: rgba({gray.red()}, {gray.green()}, {gray.blue()}, 0.05);
                    border: 1px solid rgba({gray.red()}, {gray.green()}, {gray.blue()}, 0.2);
                    border-radius: 4px;
                }}
            ''')

    def enterEvent(self, event):
        self._hover = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._update_style()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click launches profile"""
        if not self._is_launched and not self._launching:
            self.launch_clicked.emit(self.profile_id)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        """Single click selects profile"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.profile_id)
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        
        edit_action = menu.addAction(qta.icon('fa6s.pen'), 'Edit')
        menu.addSeparator()
        export_action = menu.addAction(qta.icon('fa6s.file-zipper'), 'Export')
        menu.addSeparator()
        delete_action = menu.addAction(qta.icon('fa6s.trash'), 'Delete')
        
        edit_action.triggered.connect(lambda: self.edit_clicked.emit(self.profile_id))
        export_action.triggered.connect(lambda: self.export_clicked.emit(self.profile_id))
        delete_action.triggered.connect(lambda: self.delete_clicked.emit(self.profile_id))
        
        menu.exec(self.mapToGlobal(pos))