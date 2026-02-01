import os
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QTextBrowser, QSizePolicy, QSplitter, QComboBox, QLabel, QLineEdit, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
import qtawesome as qta
from config import BASE_PATH
import re
from ui.theme_system import theme

class ReadDocumentationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Read Documentation")
        self.resize(900, 600)
        self.setWindowFlags(Qt.Window)
        if parent is not None and hasattr(parent, 'windowIcon') and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())
        else:
            icon_path = os.path.join(BASE_PATH, "res", "image_tea.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Bahasa Indonesia", "id")
        self.lang_combo.addItem("English", "en")
        lang_label = QLabel("Language:")
        lang_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search documentation...")
        self.search_icon = QLabel()
        self.search_icon.setPixmap(qta.icon('fa6s.magnifying-glass').pixmap(18, 18))
        self.search_icon.setFixedWidth(22)
        self.search_entry.textChanged.connect(self.on_search)

        lang_layout = QHBoxLayout()
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch(1)

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_entry)
        search_layout.addWidget(self.search_icon)
        search_layout.setAlignment(Qt.AlignRight)
        lang_layout.addLayout(search_layout)

        splitter = QSplitter(Qt.Horizontal, self)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        self.viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        font = QFont()
        font.setPointSize(12)
        self.viewer.setFont(font)
        self.viewer.setStyleSheet(
            "QTextBrowser {"
            "  padding: 24px;"
            "  line-height: 1.7;"
            "  white-space: pre-wrap;"
            "}"
        )
        self.viewer.setLineWrapMode(QTextBrowser.WidgetWidth)

        splitter.addWidget(self.tree)
        splitter.addWidget(self.viewer)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.close_button = QPushButton("Close")
        self.close_button.setIcon(qta.icon('fa6s.xmark'))
        self.close_button.setFixedWidth(100)
        self.close_button.clicked.connect(self.close)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addLayout(lang_layout, stretch=0)
        main_layout.addWidget(splitter, stretch=1)
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout, stretch=0)
        self.setLayout(main_layout)

        self.doc_root_id = os.path.join(BASE_PATH, "documentation", "lang_ID")
        self.doc_root_en = os.path.join(BASE_PATH, "documentation", "lang_EN")
        self.res_images_path = os.path.join(BASE_PATH, "res", "images")
        self.file_icon = qta.icon('fa6s.file', color=theme.get_color('primary'))
        self.folder_icon = qta.icon('fa6s.folder', color=theme.get_color('gray'))

        self.current_lang = "id"
        self.all_md_files = []
        self.populate_tree()
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)

        self.load_default_markdown()

    def get_doc_root(self):
        if self.current_lang == "en":
            return self.doc_root_en
        return self.doc_root_id

    def get_root_label(self):
        if self.current_lang == "en":
            return "Documentation"
        return "Dokumentasi"

    def get_lang_label(self):
        if self.current_lang == "en":
            return "English"
        return "Bahasa Indonesia"

    def natural_sort_key(self, s):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

    def populate_tree(self):
        self.tree.clear()
        self.all_md_files = []
        root_label = self.get_root_label()
        root_item = QTreeWidgetItem([root_label])
        root_item.setData(0, Qt.UserRole, None)
        root_item.setIcon(0, self.folder_icon)
        self.tree.addTopLevelItem(root_item)

        doc_root = self.get_doc_root()
        lang_label = self.get_lang_label()
        lang_item = QTreeWidgetItem([lang_label])
        lang_item.setData(0, Qt.UserRole, doc_root)
        lang_item.setIcon(0, self.folder_icon)
        root_item.addChild(lang_item)

        self.add_children(doc_root, lang_item)
        root_item.setExpanded(True)
        lang_item.setExpanded(True)

    def add_children(self, folder_path, parent_item):
        try:
            entries = os.listdir(folder_path)
        except Exception as e:
            print(f"Error reading directory {folder_path}: {e}")
            return
        files = []
        dirs = []
        for entry in entries:
            full_path = os.path.join(folder_path, entry)
            if os.path.isdir(full_path):
                dirs.append((entry, full_path))
            elif entry.lower().endswith(".md"):
                files.append((entry, full_path))
        files.sort(key=lambda x: self.natural_sort_key(x[0]))
        dirs.sort(key=lambda x: self.natural_sort_key(x[0]))
        for entry, full_path in files:
            display_name = os.path.splitext(entry)[0].replace('_', ' ').replace('-', ' ').title()
            file_item = QTreeWidgetItem([display_name])
            file_item.setData(0, Qt.UserRole, full_path)
            file_item.setIcon(0, self.file_icon)
            parent_item.addChild(file_item)
            self.all_md_files.append((display_name, full_path))
        for entry, full_path in dirs:
            dir_item = QTreeWidgetItem([entry.title()])
            dir_item.setData(0, Qt.UserRole, full_path)
            dir_item.setIcon(0, self.folder_icon)
            parent_item.addChild(dir_item)
            self.add_children(full_path, dir_item)

    def on_item_clicked(self, item, column):
        file_path = item.data(0, Qt.UserRole)
        if file_path is None:
            self.viewer.clear()
            return
        if os.path.isdir(file_path):
            item.setExpanded(True)
            if item.childCount() > 0:
                first_child = item.child(0)
                self.tree.setCurrentItem(first_child)
                self.on_item_clicked(first_child, 0)
            else:
                self.viewer.clear()
        elif os.path.isfile(file_path) and file_path.lower().endswith(".md"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    md_text = f.read()
                self.viewer.setSearchPaths([self.res_images_path])
                self.viewer.setMarkdown(md_text)
                self.viewer.setLineWrapMode(QTextBrowser.WidgetWidth)
            except Exception as e:
                self.viewer.setPlainText(f"Failed to load file:\n{file_path}\n\nError: {e}")
        else:
            self.viewer.clear()

    def on_language_changed(self, idx):
        self.current_lang = self.lang_combo.currentData()
        self.populate_tree()
        self.load_default_markdown()

    def load_default_markdown(self):
        doc_root = self.get_doc_root()
        if self.current_lang == "en":
            default_md = "1. about_image_tea.md"
        else:
            default_md = "1. tentang_image_tea.md"
        about_path = os.path.join(doc_root, default_md)
        if os.path.isfile(about_path):
            try:
                with open(about_path, "r", encoding="utf-8") as f:
                    md_text = f.read()
                self.viewer.setSearchPaths([self.res_images_path])
                self.viewer.setMarkdown(md_text)
                self.viewer.setLineWrapMode(QTextBrowser.WidgetWidth)
            except Exception as e:
                self.viewer.setPlainText(f"Failed to load file:\n{about_path}\n\nError: {e}")
        else:
            self.viewer.clear()

    def on_search(self):
        keyword = self.search_entry.text().strip()
        if not keyword:
            self.populate_tree()
            self.load_default_markdown()
            return
        matches = []
        for display_name, file_path in self.all_md_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if keyword.lower() in content.lower():
                    matches.append((display_name, file_path, content))
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        matches.sort(key=lambda x: self.natural_sort_key(os.path.basename(x[1])))
        self.tree.clear()
        search_root = QTreeWidgetItem([f"Search Results for '{keyword}'"])
        search_root.setData(0, Qt.UserRole, None)
        search_root.setIcon(0, self.folder_icon)
        self.tree.addTopLevelItem(search_root)
        for display_name, file_path, _ in matches:
            file_item = QTreeWidgetItem([display_name])
            file_item.setData(0, Qt.UserRole, file_path)
            file_item.setIcon(0, self.file_icon)
            search_root.addChild(file_item)
        search_root.setExpanded(True)
        if matches:
            first_item = search_root.child(0)
            self.tree.setCurrentItem(first_item)
            self.show_search_result(first_item, keyword)
        else:
            self.viewer.setPlainText(f"No results found for '{keyword}'.")

        self.tree.itemClicked.disconnect()
        self.tree.itemClicked.connect(lambda item, col: self.show_search_result(item, keyword))

    def show_search_result(self, item, keyword):
        file_path = item.data(0, Qt.UserRole)
        if file_path and os.path.isfile(file_path) and file_path.lower().endswith(".md"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    md_text = f.read()
                self.viewer.setSearchPaths([self.res_images_path])
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                highlighted_md = pattern.sub(lambda m: f"<span style='color:{theme.get_color('success')}'>{m.group(0)}</span>", md_text)
                self.viewer.setMarkdown(highlighted_md)
                self.viewer.setLineWrapMode(QTextBrowser.WidgetWidth)
            except Exception as e:
                self.viewer.setPlainText(f"Failed to load file:\n{file_path}\n\nError: {e}")
        else:
            self.viewer.clear()
