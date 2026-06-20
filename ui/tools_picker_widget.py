from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                 QLabel, QScrollArea, QTabWidget, QGridLayout, QFrame)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import qtawesome as qta
import json
import os
import webbrowser
from config import BASE_PATH
from ui.theme_system import theme
from database.db_account_manager_operations import AccountManagerDB


class ToolCardWidget(QFrame):
    """Widget untuk menampilkan satu tool dengan ikon, nama, deskripsi, dan tombol"""
    clicked = Signal(str)  # tool_id
    help_clicked = Signal(str)  # tool_id

    def __init__(self, tool_id, tool_name, description, icon_name, color, url=None, is_extension=False, tool_path=None, parent=None):
        super().__init__(parent)
        self.tool_id = tool_id
        self.tool_name = tool_name
        self.description = description
        self.icon_name = icon_name
        self.color = color
        self.url = url
        self.is_extension = is_extension
        self.tool_path = tool_path
        self._hover = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)

        # Layout utama
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header: Icon dan Help button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Icon
        self.icon_label = QLabel()
        icon = qta.icon(icon_name, color=color)
        self.icon_label.setPixmap(icon.pixmap(32, 32))
        header_layout.addWidget(self.icon_label)

        header_layout.addStretch()

        # Help button
        self.help_btn = QPushButton("?")
        self.help_btn.setFixedSize(24, 24)
        self.help_btn.setToolTip("View documentation for this tool")
        self.help_btn.clicked.connect(lambda: self.help_clicked.emit(self.tool_id))
        header_layout.addWidget(self.help_btn)

        layout.addLayout(header_layout)

        # Tool name
        name_label = QLabel(tool_name)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(name_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setMinimumHeight(40)
        desc_label.setStyleSheet(f"font-size: 11px; color: {theme.get_color('gray')};")
        layout.addWidget(desc_label)

        layout.addStretch()

        # Launch button with tool-specific color
        
        # Compute hover/pressed colors inline to avoid method reference issues
        c = QColor(color)
        hover_r = min(255, int(c.red() + 30))
        hover_g = min(255, int(c.green() + 30))
        hover_b = min(255, int(c.blue() + 30))
        hover_color = QColor(hover_r, hover_g, hover_b).name()
        
        pressed_r = max(0, int(c.red() * 0.85))
        pressed_g = max(0, int(c.green() * 0.85))
        pressed_b = max(0, int(c.blue() * 0.85))
        pressed_color = QColor(pressed_r, pressed_g, pressed_b).name()
        
        self.launch_btn = QPushButton(qta.icon('fa6s.rocket', color=theme.get_color('white')), " Launch")
        self.launch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {theme.get_color('white')};
                border: none;
                padding: 6px 14px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
                min-width: 90px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
            }}
        """)
        self.launch_btn.clicked.connect(self._on_launch_clicked)
        
        # Right-align button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.launch_btn)
        layout.addLayout(btn_layout)

        self._update_style()

    def _update_style(self):
        """Update style berdasarkan hover state"""
        if self._hover:
            # Konversi hex color ke rgba dengan opacity
            color = QColor(self.color)
            rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, 0.1)"
            self.setStyleSheet(f"""
                ToolCardWidget {{
                    background-color: {rgba};
                    border: 2px solid {self.color};
                }}
            """)
        else:
            self.setStyleSheet("")
    
    def _lighten_color(self, hex_color, factor=1.2):
        """Lighten a hex color by mixing with white"""
        c = QColor(hex_color)
        r = min(255, int(c.red() + (255 - c.red()) * (factor - 1) / factor))
        g = min(255, int(c.green() + (255 - c.green()) * (factor - 1) / factor))
        b = min(255, int(c.blue() + (255 - c.blue()) * (factor - 1) / factor))
        return QColor(r, g, b).name()
    
    def _darken_color(self, hex_color, factor=0.85):
        """Darken a hex color by mixing with black"""
        c = QColor(hex_color)
        r = max(0, int(c.red() * factor))
        g = max(0, int(c.green() * factor))
        b = max(0, int(c.blue() * factor))
        return QColor(r, g, b).name()
    
    def enterEvent(self, event):
        """Mouse enter event"""
        self._hover = True
        self._update_style()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Mouse leave event"""
        self._hover = False
        self._update_style()
        super().leaveEvent(event)
    
    def _on_launch_clicked(self):
        """Handle launch button click"""
        if self.is_extension and self.tool_path:
            from dialogs.extension_install_dialog import ExtensionInstallDialog
            main_window = self.window()
            dlg = ExtensionInstallDialog(self.tool_name, self.tool_path, main_window)
            dlg.exec()
        elif self.url:
            webbrowser.open(self.url)
        else:
            self.clicked.emit(self.tool_id)

    def mousePressEvent(self, event):
        """Mouse press event - launch tool saat klik area manapun"""
        if event.button() == Qt.LeftButton:
            # Cek apakah klik pada help button atau launch button
            if not (self.help_btn.geometry().contains(event.pos()) or 
                    self.launch_btn.geometry().contains(event.pos())):
                if self.is_extension and self.tool_path:
                    from dialogs.extension_install_dialog import ExtensionInstallDialog
                    main_window = self.window()
                    dlg = ExtensionInstallDialog(self.tool_name, self.tool_path, main_window)
                    dlg.exec()
                elif self.url:
                    webbrowser.open(self.url)
                else:
                    self.clicked.emit(self.tool_id)
        super().mousePressEvent(event)


class ToolsPickerWidget(QWidget):
    """Widget utama untuk memilih tools dengan tab dan grid layout"""
    tool_selected = Signal(str)  # tool_id
    back_to_main = Signal()  # Signal untuk kembali ke mode normal

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_tools()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header dengan style sederhana
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        title_label = QLabel("<b>Tools Launcher</b>")
        title_label.setStyleSheet("font-size: 16px;")
        title_layout.addWidget(title_label)

        subtitle_label = QLabel("Tools are easily accessible here. Click on a tool card to launch it or view documentation.")
        subtitle_label.setStyleSheet(f"font-size: 11px; color: {theme.get_color('gray')};")
        title_layout.addWidget(subtitle_label)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Stats bar with visual chips
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)
        stats_layout.setContentsMargins(0, 0, 0, 0)

        self.stat_total = self._make_stat_chip('fa6s.toolbox', "Total", theme.get_color('primary'))
        self.stat_image = self._make_stat_chip('fa6s.images', "Image", '#2196F3')
        self.stat_video = self._make_stat_chip('fa6s.video', "Video", '#9C27B0')
        self.stat_extension = self._make_stat_chip('fa6b.chrome', "Extensions", '#FF9800')
        self.stat_other = self._make_stat_chip('fa6s.ellipsis', "Others", theme.get_color('gray'))
        self.stat_profiles = self._make_stat_chip('fa6s.user', "Profiles", '#4CAF50')

        stats_layout.addWidget(self.stat_total['frame'])
        stats_layout.addWidget(self.stat_image['frame'])
        stats_layout.addWidget(self.stat_video['frame'])
        stats_layout.addWidget(self.stat_extension['frame'])
        stats_layout.addWidget(self.stat_other['frame'])
        stats_layout.addWidget(self.stat_profiles['frame'])
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        # Tab widget
        self.tab_widget = QTabWidget()
        self._tab_ids = {}

        # Create tabs
        self.image_processing_tab = self._create_tab_content()
        self.video_processing_tab = self._create_tab_content()
        self.extensions_tab = self._create_tab_content()
        self.others_tab = self._create_tab_content()
        self.account_manager_tab = self._create_account_manager_tab()
        self.tools_manager_tab = self._create_tools_manager_tab()

        self._add_tab("image_processing", self.image_processing_tab, qta.icon('fa6s.images'), "Image Processing")
        self._add_tab("video_processing", self.video_processing_tab, qta.icon('fa6s.video'), "Video Processing")
        self._add_tab("extensions", self.extensions_tab, qta.icon('fa6b.chrome'), "Chrome Extensions")
        self._add_tab("others", self.others_tab, qta.icon('fa6s.ellipsis'), "Others")
        self._add_tab("account_manager", self.account_manager_tab, qta.icon('fa6s.user-gear'), "Account Manager")
        self._add_tab("tools_manager", self.tools_manager_tab, qta.icon('fa6s.screwdriver-wrench'), "Tools Manager")

        layout.addWidget(self.tab_widget)

    def _add_tab(self, tab_id, widget, icon, label):
        index = self.tab_widget.addTab(widget, icon, label)
        self._tab_ids[tab_id] = index

    def set_active_tab(self, tab_id):
        """Set active tab by logical tab id"""
        index = self._tab_ids.get(tab_id)
        if index is not None:
            self.tab_widget.setCurrentIndex(index)

    def _create_tab_content(self):
        """Create scroll area content for a tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setContentsMargins(12, 12, 12, 12)
        grid_layout.setSpacing(12)

        scroll.setWidget(container)
        return scroll
    
    def _create_account_manager_tab(self):
        """Create Account Manager tab content - embed the widget content"""
        from dialogs.tools.account_manager_widgets.account_manager_widget import AccountManagerWidget

        main_window = self.window()
        self._account_manager_instance = AccountManagerWidget(main_window)

        return self._account_manager_instance

    def _create_tools_manager_tab(self):
        """Create Tools Manager tab content - embed the dialog content"""
        from dialogs.tools.tools_manager.tools_manager_dialog import ToolsManagerDialog
        
        # Create container widget
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create Tools Manager dialog instance with main window as parent
        # so self.window() returns the correct top-level window
        main_window = self.window()
        self._tools_manager_instance = ToolsManagerDialog(main_window)
        
        # Get the main content from the dialog
        # ToolsManagerDialog should have its content in a layout
        if self._tools_manager_instance.layout():
            # Create a new widget to hold the dialog's content
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            content_layout.setContentsMargins(12, 12, 12, 12)
            
            # Move all widgets from dialog to our tab
            dialog_layout = self._tools_manager_instance.layout()
            while dialog_layout.count():
                item = dialog_layout.takeAt(0)
                if item.widget():
                    content_layout.addWidget(item.widget())
                elif item.layout():
                    content_layout.addLayout(item.layout())
            
            layout.addWidget(content_widget)
        
        return container
    
    def _make_stat_chip(self, icon_name, label_text, color):
        """Create a visual stats chip with icon, label, and count badge"""
        frame = QFrame()
        frame.setFrameShape(QFrame.NoFrame)

        c = QColor(color)
        bg_rgba = f"rgba({c.red()}, {c.green()}, {c.blue()}, 0.08)"

        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_rgba};
                border: none;
                border-radius: 4px;
                padding: 2px;
            }}
        """)

        chip_layout = QHBoxLayout(frame)
        chip_layout.setContentsMargins(8, 4, 8, 4)
        chip_layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon_name, color=color).pixmap(14, 14))
        icon_label.setStyleSheet("background: transparent; border: none;")
        chip_layout.addWidget(icon_label)

        text_label = QLabel(label_text)
        text_label.setStyleSheet(
            f"background: transparent; border: none; font-size: 10px; color: {color};"
        )
        chip_layout.addWidget(text_label)

        count_label = QLabel("0")
        count_label.setStyleSheet(
            f"background: transparent; border: none; font-size: 11px; "
            f"font-weight: bold; color: {color};"
        )
        chip_layout.addWidget(count_label)

        return {'frame': frame, 'count': count_label}

    def _load_tools(self):
        """Load tools configuration and populate tabs"""
        config_path = os.path.join(BASE_PATH, "configs", "tools_config.json")

        # Load from JSON config
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                tools_config = json.load(f)
            # Cache for documentation lookup
            self._tools_config_cache = tools_config
        except Exception:
            tools_config = {"image_processing": [], "video_processing": [], "others": []}
            self._tools_config_cache = {}

        image_tools = tools_config.get("image_processing", [])
        video_tools = tools_config.get("video_processing", [])
        other_tools = tools_config.get("others", [])

        # Populate Image Processing and Video Processing tabs from config
        self._populate_tab(self.image_processing_tab, image_tools)
        self._populate_tab(self.video_processing_tab, video_tools)

        # Populate Extensions tab dynamically from tools/extension directory
        extensions_path = os.path.join(BASE_PATH, "tools", "extension")
        extension_tools = self._load_extensions_from_directory(extensions_path)
        self._populate_tab(self.extensions_tab, extension_tools)

        # Populate Others tab from config
        self._populate_tab(self.others_tab, other_tools)

        # Get profile count from Account Manager database
        try:
            db = AccountManagerDB()
            all_profiles = db.get_all_profiles()
            profile_count = len(all_profiles)
        except Exception:
            profile_count = 0

        # Update tab labels and stats with counts
        self._update_counts(
            image_count=len(image_tools),
            video_count=len(video_tools),
            extension_count=len(extension_tools),
            other_count=len(other_tools),
            profile_count=profile_count,
        )

    def _update_counts(self, image_count, video_count, extension_count, other_count, profile_count=0):
        """Update tab labels and stats summary with tool counts"""
        self.tab_widget.setTabText(0, f"Image Processing ({image_count})")
        self.tab_widget.setTabText(1, f"Video Processing ({video_count})")
        self.tab_widget.setTabText(2, f"Chrome Extensions ({extension_count})")
        self.tab_widget.setTabText(3, f"Others ({other_count})")

        total = image_count + video_count + extension_count + other_count
        self.stat_total['count'].setText(str(total))
        self.stat_image['count'].setText(str(image_count))
        self.stat_video['count'].setText(str(video_count))
        self.stat_extension['count'].setText(str(extension_count))
        self.stat_other['count'].setText(str(other_count))
        self.stat_profiles['count'].setText(str(profile_count))
    
    def _load_extensions_from_directory(self, extensions_path):
        """Load extension tools from tools/extension directory"""
        extensions = []
        
        # Define order for extensions
        order_map = {
            "auto-flow-batcher": 1,
            "mockup-prompt-generator": 2,
            "prompt-injector-tool": 3,
            "sotong-hd-lite": 4
        }
        
        if not os.path.exists(extensions_path):
            return extensions
        
        found_extensions = []
        for ext_folder in sorted(os.listdir(extensions_path)):
            ext_path = os.path.join(extensions_path, ext_folder)
            manifest_path = os.path.join(ext_path, "manifest.json")
            
            if os.path.isdir(ext_path) and os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    
                    found_extensions.append({
                        "id": ext_folder,
                        "name": manifest.get("name", ext_folder.title()),
                        "description": manifest.get("description", ""),
                        "icon": "fa6b.chrome",
                        "color": "#2196F3",
                        "path": ext_path,
                        "order": order_map.get(ext_folder, 99)
                    })
                except Exception:
                    pass
        
        # Sort by order
        found_extensions.sort(key=lambda x: x["order"])
        
        # Remove order key from output
        for ext in found_extensions:
            del ext["order"]
            extensions.append(ext)
        
        return extensions
    
    def _populate_tab(self, tab_widget, tools_list):
        """Populate a tab with tool cards"""
        scroll = tab_widget
        container = scroll.widget()
        grid_layout = container.layout()
        
        # Clear existing widgets
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add tool cards in grid (3 columns)
        row = 0
        col = 0
        for tool in tools_list:
            is_extension = "path" in tool
            card = ToolCardWidget(
                tool_id=tool["id"],
                tool_name=tool["name"],
                description=tool["description"],
                icon_name=tool["icon"],
                color=tool["color"],
                url=tool.get("url"),
                is_extension=is_extension,
                tool_path=tool.get("path")
            )
            card.clicked.connect(self._on_tool_clicked)
            card.help_clicked.connect(self._on_help_clicked)
            
            grid_layout.addWidget(card, row, col)
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        # Add stretch to push cards to top
        if row >= 0:
            grid_layout.setRowStretch(row + 1, 1)
    
    def _on_tool_clicked(self, tool_id):
        """Handle tool card click"""
        print(f"Tool clicked: {tool_id}")
        self.tool_selected.emit(tool_id)
    
    def _on_help_clicked(self, tool_id):
        """Handle help button click - open documentation"""
        print(f"Help clicked for: {tool_id}")
        
        # Load documentation mapping from config
        tools_config = getattr(self, '_tools_config_cache', None)
        if tools_config is None:
            config_path = os.path.join(BASE_PATH, "configs", "tools_config.json")
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    tools_config = json.load(f)
                self._tools_config_cache = tools_config
            except Exception:
                tools_config = {}
        
        doc_mapping = tools_config.get("documentation", {})
        doc_file = doc_mapping.get(tool_id)
        
        if doc_file:
            self._open_documentation(doc_file)
        else:
            print(f"No documentation available for: {tool_id}")
    
    def _open_documentation(self, doc_file):
        """Open documentation dialog and focus on specific file"""
        from dialogs.read_documentation_dialog import ReadDocumentationDialog
        
        # Get main window
        main_window = self.window()
        
        if not hasattr(main_window, '_read_documentation_dialog') or not main_window._read_documentation_dialog:
            main_window._read_documentation_dialog = ReadDocumentationDialog(None)
            main_window._read_documentation_dialog.destroyed.connect(
                lambda: setattr(main_window, '_read_documentation_dialog', None)
            )
            if hasattr(main_window, 'windowIcon') and not main_window.windowIcon().isNull():
                main_window._read_documentation_dialog.setWindowIcon(main_window.windowIcon())
        
        # Show dialog
        main_window._read_documentation_dialog.show()
        main_window._read_documentation_dialog.raise_()
        main_window._read_documentation_dialog.activateWindow()
        
        # Focus on specific file if possible
        if hasattr(main_window._read_documentation_dialog, 'focus_on_file'):
            main_window._read_documentation_dialog.focus_on_file(doc_file)
    
    def _open_tools_manager(self):
        """Open Tools Manager dialog"""
        from dialogs.tools.tools_manager.tools_manager_dialog import ToolsManagerDialog
        
        main_window = self.window()
        
        if not hasattr(main_window, '_tools_manager_dialog') or not main_window._tools_manager_dialog:
            main_window._tools_manager_dialog = ToolsManagerDialog(main_window)
            main_window._tools_manager_dialog.destroyed.connect(
                lambda: setattr(main_window, '_tools_manager_dialog', None)
            )
        
        main_window._tools_manager_dialog.show()
        main_window._tools_manager_dialog.raise_()
        main_window._tools_manager_dialog.activateWindow()
