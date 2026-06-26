from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QApplication, QScrollArea, QWidget, QToolTip
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
import qtawesome as qta
import os
from ui.theme_system import theme


class ExtensionInstallDialog(QDialog):
    def __init__(self, extension_name: str, extension_path: str, parent=None):
        super().__init__(parent)
        self.extension_name = extension_name
        self.extension_path = extension_path
        
        self.setWindowTitle(f"Install Extension: {extension_name}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        fg = theme.get_color('foreground')
        self.setStyleSheet(f"QDialog {{ color: {fg}; }}")
        
        title_label = QLabel(f"How to Install: {self.extension_name}")
        title_label.setStyleSheet(f"color: {theme.get_color('primary')};")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        subtitle_label = QLabel("Follow these steps to install the Chrome extension using Developer Mode")
        subtitle_label.setStyleSheet(f"color: {theme.get_color('gray')}; margin-bottom: 10px;")
        layout.addWidget(subtitle_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(20)
        
        step1 = self.create_step(
            step_number=1,
            title="Open Chrome Extensions Page",
            description="Copy the URL below and open Chrome browser, then paste it in the address bar to navigate to the Extensions management page.",
            button_text="Copy Extension URL",
            button_action=self.copy_extensions_url
        )
        scroll_layout.addWidget(step1)
        
        step2 = self.create_step(
            step_number=2,
            title="Enable Developer Mode",
            description="In the top-right corner of the Extensions page, toggle ON the 'Developer mode' switch. This allows you to load unpacked extensions.",
            button_text=None,
            button_action=None,
            has_image=False
        )
        scroll_layout.addWidget(step2)
        
        step3 = self.create_step(
            step_number=3,
            title="Click 'Load Unpacked'",
            description="After enabling Developer Mode, click the 'Load unpacked' button that appears in the top-left area of the page.",
            button_text=None,
            button_action=None
        )
        scroll_layout.addWidget(step3)
        
        path_frame = QFrame()
        # Make path frame borderless so it visually belongs to the step card
        path_frame.setStyleSheet(f"""
            QFrame {{
                border: none;
                border-radius: 6px;
                padding: 8px 0px;
            }}
            QFrame QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        path_layout = QVBoxLayout(path_frame)
        path_layout.setContentsMargins(6, 4, 6, 4)
        
        path_label = QLabel("Extension Path:")
        path_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 11px; background: transparent; border: none;")
        path_layout.addWidget(path_label)
        
        path_value = QLabel(self.extension_path)
        path_value.setStyleSheet(f"color: {theme.get_color('primary')}; font-family: monospace; font-size: 12px; background: transparent; border: none; padding-left: 6px;")
        path_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_value.setWordWrap(True)
        path_layout.addWidget(path_value)
        
        step4 = self.create_step(
            step_number=4,
            title="Select Extension Folder",
            description=f"In the folder dialog, paste the extension path and select the folder. The extension will be loaded into Chrome.",
            button_text="Copy Extension Path",
            button_action=self.copy_extension_path,
            extra_widget=path_frame
        )
        scroll_layout.addWidget(step4)
        
        step5 = self.create_step(
            step_number=5,
            title="Verify Installation",
            description="The extension should now appear in your Chrome extensions list. You may need to pin it to the toolbar for easy access.",
            button_text="Open Extension Folder",
            button_action=self.open_extension_folder
        )
        scroll_layout.addWidget(step5)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        self.instructions_label = QLabel("chrome://extensions/")
        self.instructions_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-family: monospace; font-size: 12px; margin-top: 10px;")
        self.instructions_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.instructions_label.setCursor(Qt.CursorShape.IBeamCursor)
        layout.addWidget(self.instructions_label)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {theme.get_color('text_dark')}; height: 1px; border: none;")
        layout.addWidget(separator)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.setStyleSheet(f"color: {theme.get_color('foreground')}; background: transparent;")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def create_step(self, step_number: int, title: str, description: str, 
                    button_text: str = None, button_action=None, extra_widget=None, has_image: bool = False):
        frame = QFrame()
        obj_name = f"extension_step_{step_number}"
        frame.setObjectName(obj_name)
        frame.setStyleSheet(f"""
            #{obj_name} {{
                border: none;
                border-radius: 8px;
            }}
            #{obj_name} QLabel {{
                background: transparent;
                border: none;
                margin: 0;
                padding: 0;
                color: {theme.get_color('foreground')};
            }}
        """)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        
        number_label = QLabel(str(step_number))
        number_label.setFixedSize(32, 32)
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setStyleSheet(f"""
            QLabel {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                font-weight: bold;
                font-size: 14px;
                border-radius: 16px;
                border: none;
            }}
        """)
        layout.addWidget(number_label)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(6)
        
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {theme.get_color('primary')}; background: transparent; border: none;")
        content_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {theme.get_color('gray')}; background: transparent; border: none;")
        content_layout.addWidget(desc_label)
        
        if button_text and button_action:
            icon_name = 'fa6s.copy' if 'Copy' in button_text else 'fa6s.link'
            emphasized = any(k in button_text for k in ('Open', 'Copy'))
            if emphasized:
                btn = QPushButton(qta.icon(icon_name, color=theme.get_color('white')), button_text)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {theme.get_color('primary')};
                        color: {theme.get_color('white')};
                        border: none;
                        padding: 8px 16px;
                        border-radius: 6px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {theme.get_color('primary_hover')};
                    }}
                    QPushButton:pressed {{
                        background-color: {theme.get_color('primary_pressed')};
                    }}
                """)
            else:
                btn = QPushButton(qta.icon(icon_name, color=theme.get_color('primary')), button_text)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {theme.get_color('primary')};
                        border: none;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        color: {theme.get_color('primary_hover')};
                    }}
                    QPushButton:pressed {{
                        color: {theme.get_color('primary_pressed')};
                    }}
                """)
            if 'Copy' in button_text:
                btn.setToolTip('Copy URL to clipboard')
            elif 'Open' in button_text:
                btn.setToolTip('Open extension folder in file explorer')
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(button_action)
            content_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # If an extra widget (like the extension path frame) is passed, include it as part of this step
        if extra_widget is not None:
            content_layout.addWidget(extra_widget)
        
        layout.addLayout(content_layout, stretch=1)
        
        return frame
    
    def copy_extensions_url(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("chrome://extensions/")
        try:
            btn = self.sender()
            if btn:
                pos = btn.mapToGlobal(btn.rect().center())
            else:
                pos = self.mapToGlobal(self.rect().center())
            QToolTip.showText(pos, "Copied: chrome://extensions/", self)
        except Exception as e:
            print(f"[Extension Install] Tooltip error: {e}")
        print("[Extension Install] Copied chrome://extensions/ to clipboard - paste in Chrome address bar")
        
    def copy_extension_path(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.extension_path)
        try:
            btn = self.sender()
            if btn:
                pos = btn.mapToGlobal(btn.rect().center())
            else:
                pos = self.mapToGlobal(self.rect().center())
            QToolTip.showText(pos, f"Copied: {self.extension_path}", self)
        except Exception as e:
            print(f"[Extension Install] Tooltip error: {e}")
        print(f"[Extension Install] Extension path copied to clipboard: {self.extension_path}")
    
    def open_extension_folder(self):
        if os.path.exists(self.extension_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.extension_path))
            print(f"[Extension Install] Opened extension folder: {self.extension_path}")
        else:
            print(f"[Extension Install] Extension folder not found: {self.extension_path}")
