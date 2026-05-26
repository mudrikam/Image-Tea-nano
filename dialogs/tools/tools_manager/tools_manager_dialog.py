"""
Tools Manager Dialog - Install, update, and remove application tools manually.
Card-based layout in a scroll area.
"""
import os
import platform
import subprocess

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QWidget, QProgressBar, QTextEdit, QMessageBox, QScrollArea,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont
import qtawesome as qta

from config import BASE_PATH
from ui.theme_system import theme


class ToolInstallWorker(QThread):
    log_message = Signal(str)
    progress_updated = Signal(int)
    finished_signal = Signal(str, bool)

    def __init__(self, tool_name):
        super().__init__()
        self.tool_name = tool_name

    def run(self):
        from tools.tools_checker import install_tool
        ok = install_tool(
            self.tool_name,
            reporter=self._report,
            progress_reporter=self._progress,
            unit_callback=lambda: None
        )
        self.finished_signal.emit(self.tool_name, ok)

    def _report(self, msg):
        self.log_message.emit(msg)

    def _progress(self, pct):
        self.progress_updated.emit(int(pct))


class BatchInstallWorker(QThread):
    log_message = Signal(str)
    progress_updated = Signal(int)
    tool_finished = Signal(str, bool)
    all_finished = Signal()

    def __init__(self, tool_names):
        super().__init__()
        self.tool_names = tool_names
        self.stop_flag = False

    def stop(self):
        self.stop_flag = True

    def run(self):
        from tools.tools_checker import install_tool
        total = len(self.tool_names)
        for i, tool_name in enumerate(self.tool_names):
            if self.stop_flag:
                break
            self.log_message.emit(f"Installing {tool_name} ({i+1}/{total})...")
            ok = install_tool(
                tool_name,
                reporter=self._report,
                progress_reporter=lambda pct: self._batch_progress(i, total, pct),
                unit_callback=lambda: None
            )
            self.tool_finished.emit(tool_name, ok)
        self.all_finished.emit()

    def _report(self, msg):
        self.log_message.emit(msg)

    def _batch_progress(self, current_idx, total, pct):
        overall = int(((current_idx + pct / 100.0) / total) * 100)
        self.progress_updated.emit(overall)


class ToolCard(QFrame):
    """A single tool card widget."""
    install_requested = Signal(str)
    reinstall_requested = Signal(str)
    remove_requested = Signal(str)
    open_folder_requested = Signal(str)

    def __init__(self, tool_info, status, parent=None):
        super().__init__(parent)
        self.tool_name = tool_info['name']
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Icon
        icon_label = QLabel()
        try:
            icon = qta.icon(tool_info['icon'])
            icon_label.setPixmap(icon.pixmap(24, 24))
        except Exception:
            icon_label.setText("?")
        icon_label.setFixedSize(28, 28)
        layout.addWidget(icon_label)

        # Info column
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(1)

        # Name + default badge
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(6)

        name_label = QLabel(tool_info['display_name'])
        name_font = name_label.font()
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_row.addWidget(name_label)

        if tool_info.get('is_default'):
            default_badge = QLabel("[DEFAULT]")
            default_badge.setStyleSheet(f"color: {theme.get_color('success')}; font-weight: bold;")
            default_badge.setToolTip("Auto-installed on startup if missing")
            badge_font = default_badge.font()
            badge_font.setPointSize(badge_font.pointSize() - 1)
            default_badge.setFont(badge_font)
            name_row.addWidget(default_badge)

        name_row.addStretch()
        info_layout.addLayout(name_row)

        # Description
        desc_label = QLabel(tool_info.get('description', ''))
        desc_font = desc_label.font()
        desc_font.setPointSize(desc_font.pointSize() - 1)
        desc_label.setFont(desc_font)
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)

        layout.addLayout(info_layout, 1)

        # Status label
        installed = status.get('installed', False)
        self.status_label = QLabel("Installed" if installed else "Missing")
        status_color = theme.get_color('success') if installed else theme.get_color('error')
        self.status_label.setStyleSheet(f"color: {status_color};")
        status_font = self.status_label.font()
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        layout.addWidget(self.status_label)

        # Buttons
        if not installed:
            install_btn = QPushButton(qta.icon('fa6s.download'), "Install")
            install_btn.clicked.connect(lambda: self.install_requested.emit(self.tool_name))
            layout.addWidget(install_btn)
        else:
            reinstall_btn = QPushButton(qta.icon('fa6s.rotate'), "Reinstall")
            reinstall_btn.clicked.connect(lambda: self.reinstall_requested.emit(self.tool_name))
            layout.addWidget(reinstall_btn)

            remove_btn = QPushButton(qta.icon('fa6s.trash'), "Remove")
            remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.tool_name))
            layout.addWidget(remove_btn)

        folder_btn = QPushButton(qta.icon('fa6s.folder-open'), "")
        folder_btn.setToolTip("Open folder")
        folder_btn.setFixedWidth(30)
        folder_btn.clicked.connect(lambda: self.open_folder_requested.emit(self.tool_name))
        layout.addWidget(folder_btn)


class ToolsManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tools Manager")
        self.resize(680, 500)
        self.setMinimumSize(500, 350)

        if parent:
            parent_rect = parent.frameGeometry()
            self_rect = self.frameGeometry()
            self_rect.moveCenter(parent_rect.center())
            self.move(self_rect.topLeft())

        if parent and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())

        self._worker = None
        self._build_ui()
        self._refresh_cards()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Stats bar
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        main_layout.addWidget(self.stats_label)

        # Scroll area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(4, 4, 4, 4)
        self.cards_layout.setSpacing(4)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_widget)
        main_layout.addWidget(self.scroll_area)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Log output (compact)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setFixedHeight(100)
        self.log_output.setPlaceholderText("Logs...")
        self.log_output.setVisible(False)
        main_layout.addWidget(self.log_output)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        self.install_all_btn = QPushButton(qta.icon('fa6s.download'), "Install All Missing")
        self.install_all_btn.clicked.connect(self._on_install_all_missing)
        bottom_row.addWidget(self.install_all_btn)

        self.refresh_btn = QPushButton(qta.icon('fa6s.arrows-rotate'), "Refresh")
        self.refresh_btn.clicked.connect(self._refresh_cards)
        bottom_row.addWidget(self.refresh_btn)

        bottom_row.addStretch()

        close_btn = QPushButton(qta.icon('fa6s.xmark'), "Close")
        close_btn.clicked.connect(self.close)
        bottom_row.addWidget(close_btn)

        main_layout.addLayout(bottom_row)

    def _refresh_cards(self):
        """Rebuild all tool cards."""
        from tools.tools_checker import get_available_tools, get_tool_status

        # Clear existing cards
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._tools_data = get_available_tools()

        installed_count = 0
        missing_count = 0
        default_count = 0
        non_default_count = 0

        for tool_info in self._tools_data:
            status = get_tool_status(tool_info['name'])
            tool_info['_status'] = status

            if status.get('installed', False):
                installed_count += 1
            else:
                missing_count += 1

            if tool_info.get('is_default'):
                default_count += 1
            else:
                non_default_count += 1

            card = ToolCard(tool_info, status)
            card.install_requested.connect(self._do_install)
            card.reinstall_requested.connect(self._do_reinstall)
            card.remove_requested.connect(self._do_remove)
            card.open_folder_requested.connect(self._open_tool_folder)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        # Update stats
        total = len(self._tools_data)
        c_success = theme.get_color('success')
        c_error = theme.get_color('error')
        c_gray = theme.get_color('gray')
        stats_text = (
            f"<b>Total:</b> {total} tools &nbsp;│&nbsp; "
            f"<span style='color:{c_success};'>Installed: {installed_count}</span> &nbsp;│&nbsp; "
            f"<span style='color:{c_error};'>Missing: {missing_count}</span> &nbsp;│&nbsp; "
            f"<span style='color:{c_success};'>Default: {default_count}</span> &nbsp;│&nbsp; "
            f"<span style='color:{c_gray};'>Optional: {non_default_count}</span>"
        )
        self.stats_label.setText(stats_text)

    # ─── Actions ───

    def _on_install_all_missing(self):
        missing = []
        for tool_info in self._tools_data:
            status = tool_info.get('_status', {})
            if not status.get('installed', False):
                missing.append(tool_info['name'])

        if not missing:
            parent_window = self.window()
            QMessageBox.information(parent_window, "Tools Manager", "All tools are already installed!")
            return

        msg = f"Install {len(missing)} missing tool(s)?\n\n" + "\n".join(f"  - {n}" for n in missing)
        parent_window = self.window()
        reply = QMessageBox.question(parent_window, "Install All Missing", msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            return
        self._start_batch_install(missing)

    def _do_install(self, tool_name):
        if self._worker and self._worker.isRunning():
            return
        self._show_log(True)
        self.log_output.clear()
        self._log(f"Installing {tool_name}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._set_busy(True)

        worker = ToolInstallWorker(tool_name)
        worker.log_message.connect(self._log)
        worker.progress_updated.connect(self._on_progress)
        worker.finished_signal.connect(self._on_single_install_done)
        self._worker = worker
        worker.start()

    def _do_reinstall(self, tool_name):
        parent_window = self.window()
        reply = QMessageBox.question(
            parent_window, "Reinstall Tool",
            f"Reinstall {tool_name}?\nThis will remove and re-download the tool.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        from tools.tools_checker import remove_tool
        self._show_log(True)
        self.log_output.clear()
        self._log(f"Removing {tool_name}...")
        remove_tool(tool_name)
        self._log(f"Re-installing {tool_name}...")
        self._do_install(tool_name)

    def _do_remove(self, tool_name):
        parent_window = self.window()
        reply = QMessageBox.warning(
            parent_window, "Remove Tool",
            f"Remove {tool_name}?\n\nThis will delete all files in tools/{tool_name} "
            f"and you will need to reinstall to use it.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        from tools.tools_checker import remove_tool
        self._show_log(True)
        self._log(f"Removing {tool_name}...")
        ok = remove_tool(tool_name)
        if ok:
            self._log(f"{tool_name} removed.")
        else:
            self._log(f"Failed to remove {tool_name}.")
        self._refresh_cards()

    def _open_tool_folder(self, tool_name):
        folder = os.path.join(BASE_PATH, 'tools', tool_name)
        if not os.path.isdir(folder):
            folder = os.path.join(BASE_PATH, 'tools')
        os.makedirs(folder, exist_ok=True)

        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(folder)
            elif system == "Darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            self._log(f"Could not open folder: {e}")

    def _start_batch_install(self, tool_names):
        if self._worker and self._worker.isRunning():
            return
        self._show_log(True)
        self.log_output.clear()
        self._log(f"Batch installing {len(tool_names)} tool(s)...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._set_busy(True)

        worker = BatchInstallWorker(tool_names)
        worker.log_message.connect(self._log)
        worker.progress_updated.connect(self._on_progress)
        worker.tool_finished.connect(self._on_batch_tool_done)
        worker.all_finished.connect(self._on_batch_all_done)
        self._worker = worker
        worker.start()

    # ─── Worker Callbacks ───

    def _on_progress(self, pct):
        self.progress_bar.setValue(pct)

    def _on_single_install_done(self, tool_name, success):
        self.progress_bar.setValue(100)
        if success:
            self._log(f"{tool_name} installed successfully!")
        else:
            self._log(f"{tool_name} installation failed.")
        self._set_busy(False)
        self._refresh_cards()
        QTimer.singleShot(3000, lambda: self.progress_bar.setVisible(False))

    def _on_batch_tool_done(self, tool_name, success):
        self._log(f"  {'OK' if success else 'FAILED'}: {tool_name}")

    def _on_batch_all_done(self):
        self.progress_bar.setValue(100)
        self._log("Batch installation complete.")
        self._set_busy(False)
        self._refresh_cards()
        QTimer.singleShot(3000, lambda: self.progress_bar.setVisible(False))

    # ─── Helpers ───

    def _log(self, msg):
        self.log_output.append(msg)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _show_log(self, visible):
        self.log_output.setVisible(visible)

    def _set_busy(self, busy):
        self.install_all_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy)
        # Disable all card buttons during operation
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ToolCard):
                item.widget().setEnabled(not busy)
