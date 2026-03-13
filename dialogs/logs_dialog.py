import json
import logging
import os
import re
import shutil
import webbrowser

import qtawesome as qta
from PySide6.QtCore import Qt, QSortFilterProxyModel, QTimer
from PySide6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import BASE_PATH
from ui.theme_system import theme

LOG_FILE = os.path.join(BASE_PATH, "temp", "image_tea.log")
PAGE_SIZE = 200

_LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(\w+)\s*\|\s*([^|]+?)\s*\|\s*(.+)$"
)

_LEVEL_COLOR_KEYS = {
    "DEBUG": "text_dark",
    "INFO": "success",
    "WARNING": "warning",
    "ERROR": "error",
    "CRITICAL": "secondary",
}


class _RowNumberProxy(QSortFilterProxyModel):
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return str(section + 1)
        return super().headerData(section, orientation, role)


class LogsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Logs")
        self.setMinimumSize(780, 480)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self._all_entries = []
        self._raw_lines = []
        self._filtered_entries = []
        self._current_page = 0
        self._last_mtime = 0
        self._build_ui()
        self._load_logs()

        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._tabs = QTabWidget(self)

        # --- Tab 1: Table ---
        tab1 = QWidget()
        t1_layout = QVBoxLayout(tab1)
        t1_layout.setContentsMargins(8, 8, 8, 8)
        t1_layout.setSpacing(6)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        search_icon = QLabel(tab1)
        search_icon.setPixmap(qta.icon("fa6s.magnifying-glass").pixmap(16, 16))
        self._search_box = QLineEdit(tab1)
        self._search_box.setPlaceholderText("Search in all columns...")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._on_search_changed)
        search_row.addWidget(search_icon)
        search_row.addWidget(self._search_box)
        t1_layout.addLayout(search_row)

        self._model = QStandardItemModel(0, 4, self)
        self._model.setHorizontalHeaderLabels(["Date", "Level", "Source", "Message"])

        self._proxy = _RowNumberProxy(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortCaseSensitivity(Qt.CaseInsensitive)

        self._table = QTableView(tab1)
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setEditTriggers(QTableView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setVisible(True)
        self._table.verticalHeader().setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)

        self._table.sortByColumn(0, Qt.DescendingOrder)
        t1_layout.addWidget(self._table)

        page_row = QHBoxLayout()
        page_row.setSpacing(6)
        self._lbl_count = QLabel("0 entries", tab1)
        page_row.addWidget(self._lbl_count)
        page_row.addStretch()
        self._prev_btn = QPushButton(qta.icon("fa6s.chevron-left"), "", tab1)
        self._prev_btn.setFixedWidth(32)
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._prev_page)
        self._page_label = QLabel("Page 1 of 1", tab1)
        self._page_label.setAlignment(Qt.AlignCenter)
        self._page_label.setMinimumWidth(110)
        self._next_btn = QPushButton(qta.icon("fa6s.chevron-right"), "", tab1)
        self._next_btn.setFixedWidth(32)
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._next_page)
        self._auto_refresh_cb = QCheckBox("Auto refresh (5s)", tab1)
        self._auto_refresh_cb.setChecked(True)
        self._auto_refresh_cb.toggled.connect(self._on_auto_refresh_toggled)
        page_row.addWidget(self._prev_btn)
        page_row.addWidget(self._page_label)
        page_row.addWidget(self._next_btn)
        page_row.addWidget(self._auto_refresh_cb)
        t1_layout.addLayout(page_row)

        self._tabs.addTab(tab1, qta.icon("fa6s.table"), "Table")

        # --- Tab 2: Raw ---
        tab2 = QWidget()
        t2_layout = QVBoxLayout(tab2)
        t2_layout.setContentsMargins(8, 8, 8, 8)
        t2_layout.setSpacing(6)

        self._raw_edit = QTextEdit(tab2)
        self._raw_edit.setReadOnly(True)
        self._raw_edit.setLineWrapMode(QTextEdit.NoWrap)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)
        mono.setPointSize(9)
        self._raw_edit.setFont(mono)
        t2_layout.addWidget(self._raw_edit)

        self._raw_status = QLabel("", tab2)
        t2_layout.addWidget(self._raw_status)

        self._tabs.addTab(tab2, qta.icon("fa6s.file-lines"), "Raw")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        refresh_btn = QPushButton(qta.icon("fa6s.arrows-rotate"), "Refresh", self)
        refresh_btn.clicked.connect(self._load_logs)
        btn_row.addWidget(refresh_btn)

        clear_btn = QPushButton(qta.icon("fa6s.trash"), "Clear Logs", self)
        clear_btn.clicked.connect(self._clear_logs)
        btn_row.addWidget(clear_btn)

        save_btn = QPushButton(qta.icon("fa6s.floppy-disk"), "Save as TXT", self)
        save_btn.clicked.connect(self._save_logs)
        btn_row.addWidget(save_btn)

        help_btn = QPushButton(qta.icon("fa5b.whatsapp"), "Get Help", self)
        help_btn.clicked.connect(self._open_help)
        btn_row.addWidget(help_btn)

        layout.addLayout(btn_row)

    def _on_tab_changed(self, index):
        if index == 1:
            self._refresh_raw()

    def _parse_file(self):
        if not os.path.exists(LOG_FILE):
            self._all_entries = []
            self._raw_lines = []
            self._last_mtime = 0
            return
        try:
            self._last_mtime = os.path.getmtime(LOG_FILE)
        except OSError:
            self._last_mtime = 0
        entries = []
        raw_lines = []
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                for line_idx, line in enumerate(f, start=1):
                    raw = line.rstrip("\n")
                    m = _LOG_PATTERN.match(raw)
                    if m:
                        level = m.group(2).strip()
                        entries.append((
                            line_idx,
                            m.group(1),
                            level,
                            m.group(3).strip(),
                            m.group(4).strip(),
                        ))
                        raw_lines.append((raw, level))
                    else:
                        if raw:
                            raw_lines.append((raw, ""))
        except Exception as e:
            print(f"[LogsDialog] Failed to read log file: {e}")
        self._all_entries = entries
        self._raw_lines = raw_lines

    def _load_logs(self):
        self._parse_file()
        self._current_page = 0
        self._apply_filter()
        if self._tabs.currentIndex() == 1:
            self._refresh_raw()

    def _auto_refresh(self):
        if not os.path.exists(LOG_FILE):
            return
        try:
            mtime = os.path.getmtime(LOG_FILE)
        except OSError:
            return
        if mtime == self._last_mtime:
            return
        saved_page = self._current_page
        self._parse_file()
        self._apply_filter_keep_page(saved_page)
        if self._tabs.currentIndex() == 1:
            self._refresh_raw()

    def _refresh_raw(self):
        scrollbar = self._raw_edit.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        self._raw_edit.clear()
        cursor = self._raw_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()

        counts = {}
        for raw, level in self._raw_lines:
            key = level if level else "OTHER"
            counts[key] = counts.get(key, 0) + 1
            fmt.setForeground(QColor(theme.get_color(
                _LEVEL_COLOR_KEYS.get(level, "foreground")
            )))
            cursor.insertText(raw + "\n", fmt)

        self._raw_edit.setTextCursor(cursor)
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())

        self._update_raw_status(counts)

    def _update_raw_status(self, counts):
        try:
            total_size = os.path.getsize(LOG_FILE)
        except Exception:
            total_size = 0

        def _format_size(n):
            if n < 1024:
                return f"{n} B"
            if n < 1024**2:
                return f"{n/1024:.1f} KB"
            if n < 1024**3:
                return f"{n/1024**2:.1f} MB"
            return f"{n/1024**3:.1f} GB"

        total_lines = len(self._raw_lines)
        total_entries = len(self._all_entries)
        import datetime
        refreshed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = [
            f"Size: {_format_size(total_size)}",
            f"Lines: {total_lines}",
            f"Entries: {total_entries}",
            f"Refreshed: {refreshed}",
        ]
        for lvl in sorted(counts.keys()):
            label = lvl if lvl else "OTHER"
            parts.append(f"{label}: {counts[lvl]}")
        self._raw_status.setText(" | ".join(parts))

    def _on_auto_refresh_toggled(self, checked):
        if checked:
            self._timer.start()
        else:
            self._timer.stop()

    def _on_search_changed(self):
        self._current_page = 0
        self._apply_filter()

    def _apply_filter(self):
        self._compute_filtered()
        self._update_model()
        self._update_pagination_controls()

    def _apply_filter_keep_page(self, page):
        self._compute_filtered()
        total_pages = max(1, (len(self._filtered_entries) + PAGE_SIZE - 1) // PAGE_SIZE)
        self._current_page = min(page, total_pages - 1)
        self._update_model()
        self._update_pagination_controls()

    def _compute_filtered(self):
        text = self._search_box.text().lower().strip()
        if not text:
            self._filtered_entries = self._all_entries
        else:
            self._filtered_entries = [
                e for e in self._all_entries
                if (text in e[1].lower()
                    or text in e[2].lower()
                    or text in e[3].lower()
                    or text in e[4].lower())
            ]

    def _update_model(self):
        self._model.removeRows(0, self._model.rowCount())
        start = self._current_page * PAGE_SIZE
        for _, date_str, level, source, message in self._filtered_entries[start: start + PAGE_SIZE]:
            color = QColor(theme.get_color(_LEVEL_COLOR_KEYS.get(level, "foreground")))
            row = [
                QStandardItem(date_str),
                QStandardItem(level),
                QStandardItem(source),
                QStandardItem(message),
            ]
            for item in row:
                item.setForeground(color)
            self._model.appendRow(row)

    def _update_pagination_controls(self):
        total = len(self._filtered_entries)
        all_total = len(self._all_entries)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page_label.setText(f"Page {self._current_page + 1} of {total_pages}")
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < total_pages - 1)
        if total == all_total:
            self._lbl_count.setText(f"{all_total} entries")
        else:
            self._lbl_count.setText(f"{total} of {all_total} entries")

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._update_model()
            self._update_pagination_controls()

    def _next_page(self):
        total_pages = max(1, (len(self._filtered_entries) + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._update_model()
            self._update_pagination_controls()

    def _clear_logs(self):
        try:
            open(LOG_FILE, "w").close()
            logging.getLogger().info("Log file cleared by user.")
        except Exception as e:
            print(f"[LogsDialog] Failed to clear log file: {e}")
        self._load_logs()

    def _save_logs(self):
        if not os.path.exists(LOG_FILE):
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            os.path.expanduser("~/image_tea_logs.txt"),
            "Text Files (*.txt)",
        )
        if not path:
            return
        try:
            shutil.copy2(LOG_FILE, path)
        except Exception as e:
            print(f"[LogsDialog] Failed to save logs: {e}")

    def _open_help(self):
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        webbrowser.open(cfg["links"]["whatsapp"])
