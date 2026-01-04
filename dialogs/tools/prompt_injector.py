
import os
import sys
import json
import threading
import time
import random
from PySide6.QtWidgets import (
	QApplication, QDialog, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QDoubleSpinBox, QMessageBox, QFileDialog, QCheckBox, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, QPoint, Signal, Slot, QTimer, QSize
from PySide6.QtGui import QGuiApplication, QCursor, QColor, QPainter, QBrush, QIcon
import qtawesome as qta
from helpers.tools import prompt_injector_helper
from config import BASE_PATH
from database.db_operation import ImageTeaDB

class PointWidget(QWidget):
	positionChanged = Signal(int, int)

	def __init_click_through_helpers(self):
		self._GWL_EXSTYLE = -20
		self._WS_EX_TRANSPARENT = 0x00000020
		self._WS_EX_LAYERED = 0x00080000

	def set_click_through(self, enable: bool):
		self.setAttribute(Qt.WA_TransparentForMouseEvents, enable)
		if sys.platform == "darwin":
			# macOS specific flag handling
			self.setWindowFlag(Qt.WindowTransparentForInput, enable)
			# Refresh window state agar perubahan flag terbaca
			if self.isVisible():
				self.hide()
				self.show()
		elif sys.platform == "win32":
			if not hasattr(self, "_GWL_EXSTYLE"):
				self.__init_click_through_helpers()
			import ctypes
			user32 = ctypes.windll.user32
			try:
				get_ex = user32.GetWindowLongPtrW
				set_ex = user32.SetWindowLongPtrW
			except AttributeError:
				get_ex = user32.GetWindowLongW
				set_ex = user32.SetWindowLongW
			hwnd = int(self.winId())
			exstyle = get_ex(hwnd, self._GWL_EXSTYLE)
			if enable:
				new = exstyle | self._WS_EX_LAYERED | self._WS_EX_TRANSPARENT
			else:
				new = exstyle & ~self._WS_EX_TRANSPARENT
			set_ex(hwnd, self._GWL_EXSTYLE, new)
		elif sys.platform.startswith("linux"):
			# Linux (X11/Wayland) handling
			self.setWindowFlag(Qt.WindowTransparentForInput, enable)
			# Refresh window state untuk X11/Wayland
			if self.isVisible():
				self.hide()
				self.show()

	def __init__(self, color_name: str, number: int | None = None, size: int = 32, parent=None):
		flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
		super().__init__(parent, flags)
		q = QColor(color_name)
		if not q.isValid():
			raise ValueError(f"Invalid color: {color_name}")
		self._color = q
		self._label = str(number) if number is not None else ""
		self._size = size
		self.setAttribute(Qt.WA_TranslucentBackground, True)
		self.setFixedSize(size, size)
		
		# Default False agar bisa digeser mouse saat awal
		self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
		
		self._drag_offset = None

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.Antialiasing)
		painter.setBrush(QBrush(self._color))
		painter.setPen(Qt.NoPen)
		painter.drawEllipse(0, 0, self._size, self._size)
		if self._label:
			painter.setPen(Qt.white)
			font = painter.font()
			font.setBold(True)
			font.setPointSize(int(self._size / 2.5))
			painter.setFont(font)
			painter.drawText(self.rect(), Qt.AlignCenter, self._label)

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			try:
				self._drag_offset = event.position().toPoint()
			except Exception:
				self._drag_offset = event.pos()

	def mouseMoveEvent(self, event):
		if self._drag_offset is None:
			return
		cursor = QCursor.pos()
		new_top_left = cursor - self._drag_offset
		self.move(new_top_left)
		center = self.frameGeometry().center()
		self.positionChanged.emit(center.x(), center.y())

	def mouseReleaseEvent(self, event):
		self._drag_offset = None


class PromptInjectorDialog(QDialog):
	setClipboardRequested = Signal(str)
	automationFinished = Signal()
	countdownUpdated = Signal(float, int)
	progressUpdated = Signal(int, int)
	# Emitted when the worker starts processing a prompt: (file_idx, total_files, file_type, file_pos_in_file, file_count)
	currentFileUpdated = Signal(int, int, str, int, int)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Prompt Injector Tool")
		self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
		self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)

		icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
		if os.path.exists(icon_path):
			self.setWindowIcon(QIcon(icon_path))

		self.db = ImageTeaDB()

		self.btn_action = QPushButton("Run Action")
		self.btn_action.clicked.connect(self.on_run_automation)
		self.btn_action.setIcon(qta.icon('fa6s.play'))
		self.btn_action.setIconSize(QSize(16, 16))
		self.btn_action.setToolTip("Start the automation sequence: markers will be clicked and texts pasted according to configured delays.")

		self.btn_pause = QPushButton("Pause")
		self.btn_pause.setEnabled(False)
		self.btn_pause.clicked.connect(self.on_pause_toggle)
		self.btn_pause.setIcon(qta.icon('fa6s.pause'))
		self.btn_pause.setIconSize(QSize(16, 16))
		self.btn_pause.setToolTip("Pause or resume the automation. While paused, countdowns freeze.")
		self.btn_stop = QPushButton("Stop")
		self.btn_stop.setEnabled(False)
		self.btn_stop.clicked.connect(self.on_stop)
		self.btn_stop.setIcon(qta.icon('fa6s.stop'))
		self.btn_stop.setIconSize(QSize(16, 16))
		self.btn_stop.setToolTip("Stop the automation immediately.")


		self.btn_reset = QPushButton("Reset Points")
		self.btn_reset.setEnabled(True)
		self.btn_reset.clicked.connect(self.on_reset_points)
		self.btn_reset.setIcon(qta.icon('fa6s.arrows-rotate'))
		self.btn_reset.setIconSize(QSize(16, 16))

		self.btn_help = QPushButton("")
		self.btn_help.setEnabled(True)
		self.btn_help.setToolTip("Help: explain Point 1 / 2 / 3 / 4 and buttons")
		self.btn_help.clicked.connect(self.show_help_dialog)
		self.btn_help.setIcon(qta.icon('fa6s.question'))
		self.btn_help.setIconSize(QSize(14, 14))

		self.delay_spinboxes = []
		layout = QVBoxLayout()
		layout.setSpacing(8)
		layout.setContentsMargins(8, 8, 8, 8)
		from PySide6.QtWidgets import QLayout
		layout.setSizeConstraint(QLayout.SetFixedSize)
		colors = ["red", "green", "blue", "orange", "magenta"]
		self.color_map = {
			"red": "#ff4d4d",
			"green": "#00b050",
			"blue": "#1e90ff",
			"orange": "#ff8800",
			"magenta": "#e040fb",
		}
		self.point_notes = [" (select all & paste)", " (click)", " (click)", " (click)", " (refresh)"]
		self.point_enabled = []
		self.delay_spinboxes = []
		for i, color in enumerate(colors, start=1):
			note = self.point_notes[i-1] if (i-1) < len(self.point_notes) else ""
			h = QHBoxLayout()
			if color == "magenta":
				chk = QCheckBox(f"Point {i} ({color}){note}: X=0 Y=0")
				chk.setChecked(True)
				chk.setProperty("color_name", color)
				chk.setStyleSheet(f"color: {self.color_map.get(color, color)};")
				chk.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
				chk.setToolTip("Enable/disable this point. Point 5 is a refresh trigger, executed every N prompts.")
				spin = QDoubleSpinBox()
				spin.setRange(0.0, 600.0)
				spin.setSingleStep(0.05)
				spin.setDecimals(2)
				spin.setValue(15.0)
				spin.setSuffix(" s")
				spin.setToolTip("Delay after refresh action at this point in seconds.")
				spin.setFixedWidth(110)
				h.addWidget(chk)
				h.addWidget(spin)
				layout.addLayout(h)
				# Spinner interval refresh rata kanan dan lebar seragam
				h2 = QHBoxLayout()
				lbl_every = QLabel("Trigger Point 5 Every:")
				lbl_every.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
				self.refresh_every_spin = QDoubleSpinBox()
				self.refresh_every_spin.setRange(1, 100000)
				self.refresh_every_spin.setSingleStep(1)
				self.refresh_every_spin.setDecimals(0)
				self.refresh_every_spin.setValue(100)
				self.refresh_every_spin.setSuffix(" prompts")
				self.refresh_every_spin.setToolTip("Trigger refresh (Point 5) every N prompts.")
				self.refresh_every_spin.setFixedWidth(110)
				h2.addWidget(lbl_every)
				h2.addStretch(1)
				h2.addWidget(self.refresh_every_spin)
				layout.addLayout(h2)
				self.delay_spinboxes.append(spin)
				self.point_enabled.append(chk)
				chk.toggled.connect(lambda state, idx=i-1: self._on_point_toggle(idx, state))
				self.refresh_delay_spin = spin
			else:
				chk = QCheckBox(f"Point {i} ({color}){note}: X=0 Y=0")
				chk.setChecked(True)
				chk.setProperty("color_name", color)
				chk.setStyleSheet(f"color: {self.color_map.get(color, color)};")
				chk.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
				chk.setToolTip("Enable/disable this point. Disabled points are skipped during automation.")
				spin = QDoubleSpinBox()
				spin.setRange(0.0, 600.0)
				spin.setSingleStep(0.05)
				spin.setDecimals(2)
				spin.setValue(0.0)
				spin.setSuffix(" s")
				spin.setToolTip("Delay before the action at this point in seconds. Use decimals for fine control.")
				spin.setFixedWidth(110)
				h.addWidget(chk)
				h.addWidget(spin)
				layout.addLayout(h)
				self.delay_spinboxes.append(spin)
				self.point_enabled.append(chk)
				chk.toggled.connect(lambda state, idx=i-1: self._on_point_toggle(idx, state))

		h = QHBoxLayout()
		self.rand_lbl = QLabel("Random extra delay (s):")
		self.rand_spin = QDoubleSpinBox()
		self.rand_spin.setRange(0.0, 60.0)
		self.rand_spin.setSingleStep(0.05)
		self.rand_spin.setDecimals(2)
		self.rand_spin.setValue(0.0)
		self.rand_spin.setSuffix(" s")
		self.rand_spin.setToolTip("Random extra delay added to each base delay (0 disables randomness).")
		self.rand_spin.setFixedWidth(110)
		h.addWidget(self.rand_lbl)
		h.addWidget(self.rand_spin)
		layout.addLayout(h)
		for sb in self.delay_spinboxes:
			sb.valueChanged.connect(lambda v, s=sb: self.save_settings())
		self.rand_spin.valueChanged.connect(lambda v: self.save_settings())

		self.btn_load_csv = QPushButton("Load CSV/TXT")
		self.btn_load_csv.clicked.connect(self.on_load_csv)
		self.btn_load_csv.setIcon(qta.icon('fa6s.file-csv'))
		self.btn_load_csv.setIconSize(QSize(16, 16))
		self.btn_load_csv.setToolTip("Load CSV or TXT files. TXT: each non-empty line is treated as one prompt (commas preserved).")
		self.btn_load_prompt = QPushButton("Load Prompt")
		self.btn_load_prompt.clicked.connect(self.on_load_prompt)
		self.btn_load_prompt.setIcon(qta.icon('fa6s.database'))
		self.btn_load_prompt.setIconSize(QSize(16, 16))
		self.btn_load_prompt.setToolTip("Load stored prompts from the database as the source for automation.")
		self.csv_label = QLabel("CSV/Prompt: (none)")
		self.csv_label.setToolTip("Shows currently loaded CSV or prompt source.")
		self.progress_bar = QProgressBar()
		self.progress_bar.setMinimum(0)
		self.progress_bar.setMaximum(1)
		self.progress_bar.setValue(0)
		self.progress_bar.setTextVisible(True)
		self.progress_bar.setFormat("0 / 0")
		self.progress_bar.setToolTip("Automation progress: processed / total.")
		h_files = QHBoxLayout()
		h_files.setSpacing(8)
		h_files.addWidget(self.btn_load_csv)
		h_files.addWidget(self.btn_load_prompt)
		self.btn_clear_data = QPushButton("Clear")
		self.btn_clear_data.setIcon(qta.icon('fa6s.trash-can'))
		self.btn_clear_data.setIconSize(QSize(16, 16))
		self.btn_clear_data.setToolTip("Clear loaded CSV/Prompt data from this dialog")
		self.btn_clear_data.setCursor(Qt.PointingHandCursor)
		self.btn_clear_data.clicked.connect(self.on_clear_data)
		h_files.addWidget(self.btn_clear_data)
		self.btn_prompt_help = QPushButton()
		self.btn_prompt_help.setIcon(qta.icon('fa6s.question'))
		self.btn_prompt_help.setFixedWidth(28)
		self.btn_prompt_help.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
		self.btn_prompt_help.setIconSize(QSize(14, 14))
		self.btn_prompt_help.setToolTip("Help about prompts: shows what 'Load Prompt' does")
		self.btn_prompt_help.setCursor(Qt.PointingHandCursor)
		self.btn_prompt_help.clicked.connect(self.show_help_dialog)
		h_files.addWidget(self.btn_prompt_help)
		layout.addLayout(h_files)
		layout.addWidget(self.csv_label)
		layout.addWidget(self.progress_bar)

		h_stats = QHBoxLayout()
		left_v = QVBoxLayout()
		right_v = QVBoxLayout()
		self.stats_eta_lbl = QLabel("ETA: -")
		self.stats_remaining_lbl = QLabel("Remaining: -")
		self.stats_elapsed_lbl = QLabel("Elapsed: -")
		self.stats_progress_lbl = QLabel("Progress: 0/0")
		self.stats_speed_lbl = QLabel("Speed: 0.00/m")
		for lbl in (self.stats_eta_lbl, self.stats_remaining_lbl, self.stats_elapsed_lbl, self.stats_progress_lbl, self.stats_speed_lbl):
			lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
			lbl.setToolTip("Estimated stats (dynamic and approximate due to random delays).")
		left_v.addWidget(self.stats_eta_lbl)
		left_v.addWidget(self.stats_remaining_lbl)
		left_v.addWidget(self.stats_elapsed_lbl)
		right_v.addWidget(self.stats_progress_lbl)
		right_v.addWidget(self.stats_speed_lbl)
		h_stats.addLayout(left_v)
		h_stats.addLayout(right_v)
		layout.addLayout(h_stats)

		h_top = QHBoxLayout()
		h_top.addWidget(self.btn_action)
		h_top.addWidget(self.btn_pause)
		h_top.addWidget(self.btn_stop)
		h_top.addWidget(self.btn_reset)
		layout.addLayout(h_top)


		self.btn_reset.setToolTip("Reset Points: Move the four markers back to their default centered positions and save them to settings.")

		self.delay_label = QLabel("")
		self.delay_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
		self.delay_label.setFixedHeight(0)
		layout.addWidget(self.delay_label)


		self.setLayout(layout)
		self.setMinimumWidth(360)
		QTimer.singleShot(0, self.adjustSize)
		# Allow drag-and-drop of a CSV file onto this dialog
		self.setAcceptDrops(True)

		self.points = []
		screen = QGuiApplication.primaryScreen().availableGeometry()
		center = screen.center()
		offsets = [QPoint(0, 0), QPoint(40, 0), QPoint(-40, 0), QPoint(0, 40), QPoint(0, -40)]
		for idx, (color, off) in enumerate(zip(colors, offsets)):
			hex_color = self.color_map.get(color, color)
			p = PointWidget(hex_color, idx + 1)
			p.setParent(None)
			# Hapus Qt.Tool agar tidak hilang saat pindah tab/app di macOS
			p.setWindowFlag(Qt.Window, True)
			p.setWindowFlag(Qt.FramelessWindowHint, True)
			p.setWindowFlag(Qt.WindowStaysOnTopHint, True)
			top_left = center - QPoint(p.width() // 2, p.height() // 2) + off
			p.move(top_left)
			# Tampilkan dulu untuk inisialisasi, nanti di-hide kalau setting off
			p.show()
			p.raise_()
			p.positionChanged.connect(self._make_updater(idx, color))
			c = p.frameGeometry().center()
			note = self.point_notes[idx] if idx < len(self.point_notes) else ""
			self.point_enabled[idx].setText(f"Point {idx+1} ({color}){note}: X={c.x()} Y={c.y()}")
			self.points.append(p)

		self.loaded_paste_texts = None
		self.loaded_from_db = False
		self._copied_count = 0
		self._loaded_prompt_ids = []
		# Track loaded files (path, type, count)
		self._loaded_files = []

		self.setClipboardRequested.connect(self._set_clipboard)
		self.automationFinished.connect(self._on_automation_finished)
		self.progressUpdated.connect(self._on_progress_updated)
		self.countdownUpdated.connect(self._on_countdown_updated)
		self.currentFileUpdated.connect(self._on_current_file_updated)
		# Lock to protect the prompt queue when loading files during a running automation
		self._queue_lock = threading.Lock()

		self._stats_timer = QTimer(self)
		self._stats_timer.setInterval(1000)
		self._stats_timer.timeout.connect(lambda: self._update_stats(getattr(self, '_current_done', 0), getattr(self, '_total', 0)))
		self._run_start_time = None
		self._pause_start = None
		self._pause_accum = 0.0
		self._current_done = 0
		self._total = 0

		def _on_key_press(key):
			from pynput import keyboard
			if key == keyboard.Key.esc or getattr(key, 'char', None) == '\x1b':
				QTimer.singleShot(0, self.on_pause_toggle)

		from pynput import keyboard
		self._pynput_listener = keyboard.Listener(on_press=_on_key_press)
		self._pynput_listener.daemon = True
		self._pynput_listener.start()

		self.load_settings()

	def _make_updater(self, idx: int, color: str):
		def updater(x: int, y: int):
			note = self.point_notes[idx] if idx < len(self.point_notes) else ""
			self.point_enabled[idx].setText(f"Point {idx+1} ({color}){note}: X={x} Y={y}")
			self.save_settings()
		return updater

	def _on_point_toggle(self, idx: int, enabled: bool):
		if idx < 0 or idx >= len(self.points):
			return
		p = self.points[idx]
		chk = self.point_enabled[idx]
		if enabled:
			p.show()
			p.raise_()
			color = chk.property("color_name") or "black"
			chk.setStyleSheet(f"color: {self.color_map.get(color, color)};")
		else:
			p.hide()
			chk.setStyleSheet("color: gray;")
		self.save_settings()

	def on_run_automation(self):
		coords = []
		base_delays = []
		for idx, p in enumerate(self.points):
			coords.append((p.frameGeometry().center().x(), p.frameGeometry().center().y()))
			base_delays.append(self.delay_spinboxes[idx].value())
		random_delay = float(self.rand_spin.value())
		# Start automation using the shared prompt queue so new files can be queued while running
		with self._queue_lock:
			current_queue = list(self.loaded_paste_texts) if self.loaded_paste_texts else []
		if not current_queue:
			QMessageBox.warning(self, "No Data", "No records to process (CSV/Prompt is empty)")
			return
		self.progress_bar.setMaximum(len(current_queue))
		self.progress_bar.setValue(0)
		self.progress_bar.setFormat(f"0 / {len(current_queue)}")
		self._stop_event = threading.Event()
		self._pause_event = threading.Event()
		self._clipboard_set_event = threading.Event()
		self._last_set_clipboard = None
		self._set_run_mode(True)
		self.btn_pause.setEnabled(True)
		self.btn_stop.setEnabled(True)
		self.btn_pause.setText("Pause")
		refresh_every = int(self.refresh_every_spin.value()) if hasattr(self, 'refresh_every_spin') else 100
		refresh_enabled = self.point_enabled[4].isChecked() if len(self.point_enabled) > 4 else False
		refresh_delay = self.delay_spinboxes[4].value() if len(self.delay_spinboxes) > 4 else 0.0
		# Initialize dynamic counters
		self._current_done = 0
		with self._queue_lock:
			self._total = len(self.loaded_paste_texts) if self.loaded_paste_texts else 0
		self._worker_thread = threading.Thread(
			target=self._run_sequence, args=(coords, base_delays, random_delay, refresh_every, refresh_enabled, refresh_delay), daemon=True
		)
		self._worker_thread.start()
		self._run_start_time = time.time()
		self._pause_accum = 0.0
		self._pause_start = None
		self._refresh_countdown = refresh_every
		self._refresh_every = refresh_every
		self._refresh_enabled = refresh_enabled
		self._refresh_delay = refresh_delay
		self._stats_timer.start()
		self._update_stats(0, self._total)

	def _set_run_mode(self, enable: bool):
		for p in self.points:
			p.set_click_through(enable)
		self.btn_action.setEnabled(not enable)
		try:
			if enable:
				self.btn_reset.setEnabled(False)
				self.btn_reset.setToolTip("Reset disabled while automation is running")
			else:
				self.btn_reset.setEnabled(True)
				self.btn_reset.setToolTip("Reset Points: Move the four markers back to their default centered positions and save them to settings.")
		except Exception:
			pass
		self.btn_action.setText("Running..." if enable else "Run Action")

	@Slot()
	def _on_automation_finished(self):
		self._set_run_mode(False)
		self.btn_pause.setEnabled(False)
		self.btn_stop.setEnabled(False)
		self._stop_event.set()
		self._pause_event.clear()
		self._set_delay_text("")
		self.progress_bar.setValue(self.progress_bar.maximum())
		self.progress_bar.setFormat(f"{self.progress_bar.maximum()} / {self.progress_bar.maximum()}")
		self._stats_timer.stop()
		self._update_stats(self.progress_bar.maximum(), self.progress_bar.maximum())
		self._last_set_clipboard = None

	@Slot(int, int)
	def _on_progress_updated(self, done: int, total: int):
		self.progress_bar.setMaximum(total)
		self.progress_bar.setValue(done)
		self.progress_bar.setFormat(f"{done} / {total}")
		self._current_done = done
		self._total = total
		self._update_stats(done, total)

	def on_pause_toggle(self):
		if not getattr(self, '_pause_event', None):
			self._set_delay_text("Not running")
			QTimer.singleShot(1000, lambda: self._set_delay_text(""))
			return
		if self._pause_event.is_set():
			self._pause_event.clear()
			if getattr(self, "_pause_start", None):
				self._pause_accum += time.time() - self._pause_start
				self._pause_start = None
			self.btn_pause.setText("Pause")
		else:
			self._pause_event.set()
			self._pause_start = time.time()
			self.btn_pause.setText("Resume")
		self._update_stats(getattr(self, "_current_done", 0), getattr(self, "_total", 0))

	def on_stop(self):
		self._stop_event.set()
		self._pause_event.clear()
		self._set_run_mode(False)
		self.btn_pause.setEnabled(False)
		self.btn_stop.setEnabled(False)
		self.btn_pause.setText("Pause")
		self._stats_timer.stop()
		self._update_stats(getattr(self, "_current_done", 0), getattr(self, "_total", 0))

	def on_reset_points(self):
		screen = QGuiApplication.primaryScreen().availableGeometry()
		center = screen.center()
		offsets = [QPoint(0, 0), QPoint(40, 0), QPoint(-40, 0), QPoint(0, 40)]
		for i, (p, off) in enumerate(zip(self.points, offsets)):
			top_left = center - QPoint(p.width() // 2, p.height() // 2) + off
			p.move(top_left)
			c = p.frameGeometry().center()
			prefix = self.point_enabled[i].text().split(":" , 1)[0]
			self.point_enabled[i].setText(f"{prefix}: X={c.x()} Y={c.y()}")
		self.save_settings()

	def show_help_dialog(self):
		c = lambda name: self.color_map.get(name, name)
		note = lambda idx: self.point_notes[idx] if idx < len(self.point_notes) else ""
		html = (
			"<div>"
			f"<p><span style='color:{c('red')}; font-weight:bold;'>Point 1 (red){note(0)}:</span> After the first delay the cursor moves here, clicks, does <b>Ctrl+A</b>, sets the clipboard to the current text and pastes it with <b>Ctrl+V</b>.</p>"
			f"<p><span style='color:{c('green')}; font-weight:bold;'>Point 2 (green){note(1)}:</span> After the second delay the cursor moves here and clicks, typically used to confirm or advance the UI element.</p>"
			f"<p><span style='color:{c('blue')}; font-weight:bold;'>Point 3 (blue){note(2)}:</span> After the third delay the cursor moves here and clicks, often used for final actions like Submit or Next.</p>"
			f"<p><span style='color:{c('orange')}; font-weight:bold;'>Point 4 (orange){note(3)}:</span> Optional extra action after the third point.</p>"
			f"<p><span style='color:{c('magenta')}; font-weight:bold;'>Point 5 (magenta){note(4)}:</span> Refresh trigger. After every N prompts (see 'Trigger Point 5 Every'), the cursor moves here, clicks, and waits for the specified delay before continuing. All other points are paused during this refresh.</p>"
			"<p><b>Reset Points:</b> Move the four markers back to their default centered positions and save them to settings.</p>"
			"</div>"
		)
		QMessageBox.information(self, "Help Points and Buttons", html)

	def _on_countdown_updated(self, remaining: float, refresh_countdown: int = 0):
		# Only show seconds, no ms, and show refresh countdown if available
		if remaining > 0:
			s = int(round(remaining))
			txt = f"Waiting: {s} s"
			if refresh_countdown > 0:
				txt += f" | Refresh After: {refresh_countdown} Prompts"
			self._set_delay_text(txt)
		else:
			self._set_delay_text("")

	def _on_current_file_updated(self, file_idx: int, total_files: int, file_type: str, file_pos: int, file_count: int):
		"""Update `csv_label` to show which file and which prompt inside that file is being processed.

		Example: "Loaded 235 prompts (1/3 csv: 12/80)"
		"""
		total = len(self.loaded_paste_texts) if self.loaded_paste_texts else 0
		if total == 0 or total_files == 0:
			self._update_loaded_label()
			return
		# Keep the existing 'Loaded X prompts' info and append file progress
		self.csv_label.setText(f"Loaded {total} prompts ({file_idx}/{total_files} {file_type}: {file_pos}/{file_count})")

	def _set_delay_text(self, text: str):
		"""Set the delay label text and collapse the label when empty to avoid layout gaps."""
		if not text:
			self.delay_label.setText("")
			self.delay_label.setFixedHeight(0)
		else:
			self.delay_label.setText(text)
			h = self.delay_label.sizeHint().height()
			self.delay_label.setFixedHeight(h)
		QTimer.singleShot(0, self.adjustSize)

	def _format_duration(self, seconds):
		if seconds is None:
			return "-"
		try:
			seconds = int(round(seconds))
		except Exception:
			return "-"
		h, rem = divmod(seconds, 3600)
		m, s = divmod(rem, 60)
		if h:
			return f"{h:d}:{m:02d}:{s:02d}"
		return f"{m:d}:{s:02d}"

	def _update_stats(self, done, total):
		if total <= 0:
			self.stats_eta_lbl.setText("ETA: -")
			self.stats_remaining_lbl.setText("Remaining: -")
			self.stats_elapsed_lbl.setText("Elapsed: -")
			self.stats_progress_lbl.setText("Progress: 0/0")
			self.stats_speed_lbl.setText("Speed: 0.00/m")
			return
		now = time.time()
		start = getattr(self, "_run_start_time", None)
		if not start:
			elapsed = 0.0
		else:
			elapsed = now - start - getattr(self, "_pause_accum", 0.0)
			if getattr(self, "_pause_start", None):
				elapsed -= (now - self._pause_start)
			if elapsed < 0:
				elapsed = 0.0
		remaining_items = max(0, total - done)
		avg = (elapsed / done) if done > 0 and elapsed > 0 else None
		if avg:
			remaining_time = avg * remaining_items
			eta_str = time.strftime("%H:%M:%S", time.localtime(now + remaining_time))
		else:
			remaining_time = None
			eta_str = "-"
		speed = (done / elapsed * 60.0) if elapsed > 0 else 0.0
		percent = int(done / total * 100) if total > 0 else 0
		paused = " (paused)" if getattr(self, "_pause_event", None) and self._pause_event.is_set() else ""
		self.stats_eta_lbl.setText(f"ETA: {eta_str}")
		self.stats_remaining_lbl.setText(f"Remaining: {self._format_duration(remaining_time)}")
		self.stats_elapsed_lbl.setText(f"Elapsed: {self._format_duration(elapsed)}{paused}")
		self.stats_progress_lbl.setText(f"Progress: {done}/{total} ({percent}%)")
		self.stats_speed_lbl.setText(f"Speed: {speed:.2f}/m")

	def on_load_csv(self):
		# Allow selecting multiple CSV or TXT files
		paths, _ = QFileDialog.getOpenFileNames(self, "Select CSV/TXT files", os.path.dirname(__file__), "CSV or TXT Files (*.csv *.txt);;All Files (*)")
		if not paths:
			return
		aggregated = []
		successful_files = 0
		new_files = []
		for path in paths:
			if not path:
				continue
			ok, ftype, texts = self._process_file(path)
			if ok and texts:
				aggregated.extend(texts)
				new_files.append({"path": path, "type": ftype, "count": len(texts)})
				successful_files += 1
			elif ok and not texts:
				QMessageBox.warning(self, "No Data", f"File {os.path.basename(path)} contains no records to process.")
			else:
				QMessageBox.warning(self, "Load Error", f"Could not load file: {os.path.basename(path)}")
		if not aggregated:
			return
		# Append new prompts to current list so multiple file loads accumulate
		if getattr(self, '_worker_thread', None) and getattr(self._worker_thread, 'is_alive', lambda: False)():
			# Automation running: append under lock and update totals so worker picks them up
			with self._queue_lock:
				self.loaded_paste_texts = (self.loaded_paste_texts or []) + aggregated
				self._loaded_files.extend(new_files)
				# update total and progress bar instantly
				self._total = len(self.loaded_paste_texts)
				self.progress_bar.setMaximum(self._total)
				self.progress_bar.setFormat(f"{self._current_done} / {self._total}")
				self._update_loaded_label()
			# keep GUI counters consistent
			self._update_stats(getattr(self, '_current_done', 0), self._total)
		else:
			self.loaded_paste_texts = (self.loaded_paste_texts or []) + aggregated
			self._loaded_files.extend(new_files)
			self._update_loaded_label()
		self.loaded_from_db = False
		self._copied_count = 0
		self.save_settings()

	def on_load_prompt(self):
		# Loading from DB is not queued into a running automation (single-use load)
		if getattr(self, '_worker_thread', None) and getattr(self._worker_thread, 'is_alive', lambda: False)():
			QMessageBox.information(self, "Load Disabled", "Loading prompts from database is disabled while automation is running.")
			return
		if not self.db:
			self.db = ImageTeaDB()
		prompts = prompt_injector_helper.load_prompts_from_db(self.db)
		if not prompts:
			QMessageBox.warning(self, "No Data", "No prompts found in database.")
			return
		self._loaded_prompt_ids = [p[0] for p in prompts]
		self.loaded_paste_texts = [p[1] for p in prompts]
		self.loaded_from_db = True
		self._copied_count = 0
		self.csv_label.setText(f"Prompt DB: {len(prompts)} records (copied: 0)")
		self.save_settings()

	def on_clear_data(self):
		"""Clear any loaded CSV or prompt data from the dialog and reset UI state."""
		self.loaded_paste_texts = None
		self.loaded_from_db = False
		self._loaded_prompt_ids = []
		self._copied_count = 0
		self._loaded_files = []
		self.csv_label.setText("CSV/Prompt: (none)")
		self.progress_bar.setMaximum(1)
		self.progress_bar.setValue(0)
		self.progress_bar.setFormat("0 / 0")
		self.btn_reset.setEnabled(True)
		self.btn_reset.setToolTip("Reset Points: Move the four markers back to their default centered positions and save them to settings.")
		self.save_settings()

	def dragEnterEvent(self, event):
		"""Accept drag enter events that contain at least one local .csv or .txt file."""
		md = event.mimeData()
		if md and md.hasUrls():
			for url in md.urls():
				if url.isLocalFile() and os.path.splitext(url.toLocalFile())[1].lower() in (".csv", ".txt"):
					event.acceptProposedAction()
					return
		# otherwise ignore
		event.ignore()

	def dropEvent(self, event):
		"""Handle dropped file(s). Load all local CSV/TXT files dropped onto the dialog."""
		urls = event.mimeData().urls()
		if not urls:
			return
		aggregated = []
		loaded_any = False
		new_files = []
		for url in urls:
			path = url.toLocalFile()
			if not path or not os.path.isfile(path):
				continue
			ext = os.path.splitext(path)[1].lower()
			if ext not in ('.csv', '.txt'):
				continue
			ok, ftype, texts = self._process_file(path)
			if ok and texts:
				aggregated.extend(texts)
				new_files.append({"path": path, "type": ftype, "count": len(texts)})
				loaded_any = True
			elif ok and not texts:
				QMessageBox.warning(self, "No Data", f"File {os.path.basename(path)} contains no records to process.")
			else:
				QMessageBox.warning(self, "Load Error", f"Could not load file: {os.path.basename(path)}")
		if not loaded_any:
			QMessageBox.warning(self, "Drop Error", "No valid CSV or TXT files were dropped.")
			return
		# If automation is running, append under lock and update totals so the worker will pick them up
		if getattr(self, '_worker_thread', None) and getattr(self._worker_thread, 'is_alive', lambda: False)():
			with self._queue_lock:
				self.loaded_paste_texts = (self.loaded_paste_texts or []) + aggregated
				self._loaded_files.extend(new_files)
				self._total = len(self.loaded_paste_texts)
				self.progress_bar.setMaximum(self._total)
				self.progress_bar.setFormat(f"{self._current_done} / {self._total}")
				self._update_loaded_label()
			self._update_stats(getattr(self, '_current_done', 0), self._total)
		else:
			self.loaded_paste_texts = (self.loaded_paste_texts or []) + aggregated
			self._loaded_files.extend(new_files)
			self._update_loaded_label()
		self.loaded_from_db = False
		self._copied_count = 0
		self.save_settings()
		event.acceptProposedAction()

	def _process_file(self, path):
		"""Load a single file (csv or txt). Returns (ok:bool, type:str, texts:list).
		ok False means unreadable; ok True with empty texts means file had no prompts.
		"""
		try:
			ext = os.path.splitext(path)[1].lower()
			if ext == '.csv':
				texts = prompt_injector_helper.load_csv_texts(path)
				ftype = 'csv'
			elif ext == '.txt':
				texts = prompt_injector_helper.load_text_texts(path)
				ftype = 'txt'
			else:
				return False, None, None
			return True, ftype, texts
		except Exception:
			return False, None, None

	def _update_loaded_label(self):
		total = len(self.loaded_paste_texts) if self.loaded_paste_texts else 0
		n_files = len(self._loaded_files)
		if n_files == 0:
			self.csv_label.setText("CSV/Prompt: (none)")
			return
		last_index = n_files
		last_type = self._loaded_files[-1].get('type', '')
		self.csv_label.setText(f"Loaded {total} prompts ({last_index}/{n_files}) ({last_type})")

	def _set_clipboard(self, text: str):
		cb = QApplication.clipboard()
		cb.setText(str(text))
		time.sleep(0.08)
		self._last_set_clipboard = str(text)
		self._clipboard_set_event.set()

	def closeEvent(self, event):
		self.save_settings()
		for p in list(self.points):
			p.close()
		if getattr(self, '_pynput_listener', None):
			self._pynput_listener.stop()
		super().closeEvent(event)

	def settings_path(self):
		return os.path.join(BASE_PATH, "configs", "prompt_injector_settings.json")

	def save_settings(self):
		data = {}
		data["base_delays"] = [float(s.value()) for s in self.delay_spinboxes]
		data["random_delay"] = float(self.rand_spin.value())
		data["enabled_points"] = [bool(chk.isChecked()) for chk in self.point_enabled]
		data["csv_path"] = None
		if getattr(self, "loaded_paste_texts", None) and getattr(self, "csv_label", None):
			text = self.csv_label.text()
			fname = text.split(":", 1)[1].strip().split(" (")[0]
			data["csv_path"] = fname
		pts = []
		for p in self.points:
			pos = p.pos()
			pts.append([int(pos.x()), int(pos.y())])
		data["point_positions"] = pts
		if hasattr(self, 'refresh_every_spin'):
			data["refresh_every"] = int(self.refresh_every_spin.value())
		# Persist loaded files (path, type, count)
		try:
			data["loaded_files"] = list(self._loaded_files)
		except Exception:
			data["loaded_files"] = []
		path = self.settings_path()
		try:
			os.makedirs(os.path.dirname(path), exist_ok=True)
			with open(path, "w", encoding="utf-8") as fh:
				json.dump(data, fh, indent=2)
		except Exception:
			pass

	def load_settings(self):
		path = self.settings_path()
		if not os.path.exists(path):
			default = {
				"base_delays": [3.0, 3.0, 3.0, 3.0, 15.0],
				"random_delay": 3.0,
				"enabled_points": [True, True, True, True, True],
				"csv_path": None,
				"point_positions": [],
				"refresh_every": 100
			}
			try:
				os.makedirs(os.path.dirname(path), exist_ok=True)
				with open(path, "w", encoding="utf-8") as fh:
					json.dump(default, fh, indent=2)
			except Exception:
				pass
			bd = default.get("base_delays") or []
			for i, val in enumerate(bd):
				if i < len(self.delay_spinboxes):
					self.delay_spinboxes[i].setValue(float(val))
			rd = default.get("random_delay")
			if rd is not None:
				self.rand_spin.setValue(float(rd))
			if hasattr(self, 'refresh_every_spin'):
				self.refresh_every_spin.setValue(default.get("refresh_every", 100))
		try:
			with open(path, encoding="utf-8") as fh:
				data = json.load(fh)
		except Exception:
			return
		bd = data.get("base_delays") or []
		for i, val in enumerate(bd):
			if i < len(self.delay_spinboxes):
				self.delay_spinboxes[i].setValue(float(val))
		en = data.get("enabled_points") or []
		for i, chk in enumerate(self.point_enabled):
			if i < len(en):
				chk.setChecked(bool(en[i]))
		for i, chk in enumerate(self.point_enabled):
			self._on_point_toggle(i, chk.isChecked())
		rd = data.get("random_delay")
		if rd is not None:
			self.rand_spin.setValue(float(rd))
		if hasattr(self, 'refresh_every_spin'):
			val = data.get("refresh_every", 100)
			self.refresh_every_spin.setValue(val)
		# Load previously saved files (supports multiple files)
		loaded_files = data.get("loaded_files") or []
		if loaded_files:
			aggregated = []
			self._loaded_files = []
			for entry in loaded_files:
				p = entry.get("path")
				if not p or not os.path.exists(p):
					continue
				ok, ftype, texts = self._process_file(p)
				if ok and texts:
					aggregated.extend(texts)
					self._loaded_files.append({"path": p, "type": ftype, "count": len(texts)})
			if aggregated:
				self.loaded_paste_texts = aggregated
				self.loaded_from_db = False
				self._copied_count = 0
				self._update_loaded_label()
		else:
			# Backwards compatibility with older single csv_path setting
			csvp = data.get("csv_path")
			if csvp:
				full = os.path.join(os.path.dirname(self.settings_path()), csvp)
				if os.path.exists(full):
					texts = prompt_injector_helper.load_csv_texts(full)
					if texts:
						self.loaded_paste_texts = texts
						self.csv_label.setText(f"CSV: {os.path.basename(full)} ({len(texts)} records)")
		pts = data.get('point_positions') or data.get('points')
		if pts:
			for i, ppos in enumerate(pts):
				if i >= len(self.points):
					break
				x = int(ppos[0])
				y = int(ppos[1])
				w = self.points[i].width()
				h = self.points[i].height()
				top_left = QPoint(x, y)
				self.points[i].move(top_left)
				prefix = self.point_enabled[i].text().split(":", 1)[0]
				self.point_enabled[i].setText(f"{prefix}: X={x + w//2} Y={y + h//2}")

	def _run_sequence(self, coords, base_delays, random_delay, refresh_every, refresh_enabled, refresh_delay):
		import pyautogui
		import random
		pyautogui.FAILSAFE = True
		copied_count = 0
		refresh_countdown = refresh_every
		# We'll iterate over the shared queue using an index so newly queued items are processed too
		idx = 0
		while True:
			with self._queue_lock:
				total = len(self.loaded_paste_texts) if self.loaded_paste_texts else 0
				files = list(self._loaded_files)
				cumulative = []
				running = 0
				for f in files:
					running += int(f.get('count', 0))
					cumulative.append(running)
			# Allow a short wait at the end of the queue for files dropped immediately after finishing
			# This gives the UI a brief grace period so very quick drops are still processed
			if idx >= total:
				waited = 0
				while idx >= total and not getattr(self, '_stop_event', None) and waited < 20:
					time.sleep(0.05)
					waited += 1
					with self._queue_lock:
						total = len(self.loaded_paste_texts) if self.loaded_paste_texts else 0
				if idx >= total:
					break
			# If there is no item at current index, we are done
			if idx >= total:
				break
			# 1-based index for UI
			ui_idx = idx + 1
			with self._queue_lock:
				text_to_paste = self.loaded_paste_texts[idx]
			# Emit current-file info (if we have file meta)
			if files and cumulative:
				file_idx = 0
				for i, cum in enumerate(cumulative):
					if ui_idx <= cum:
						file_idx = i
						break
				if file_idx < len(files):
					file_pos = ui_idx - (cumulative[file_idx-1] if file_idx > 0 else 0)
					file_count = int(files[file_idx].get('count', 0))
					file_type = files[file_idx].get('type', '')
					self.currentFileUpdated.emit(file_idx + 1, len(files), file_type, file_pos, file_count)
			# Refresh logic: if enabled and interval tercapai, trigger point 5
			if refresh_enabled and refresh_every > 0 and (ui_idx > 1) and ((ui_idx-1) % refresh_every == 0):
				x, y = coords[4]
				pyautogui.moveTo(x, y)
				pyautogui.click()
				for t in range(int(refresh_delay), 0, -1):
					self.countdownUpdated.emit(t, refresh_every)
					time.sleep(1)
				if refresh_delay > 0 and refresh_delay % 1 != 0:
					# Untuk pecahan detik
					time.sleep(refresh_delay - int(refresh_delay))
				refresh_countdown = refresh_every
			# Sequence untuk points 1-4 (skip jika tidak enabled)
			pasted = False
			for i in range(4):
				if not self.point_enabled[i].isChecked():
					continue
				d = float(base_delays[i]) + random.uniform(0, float(random_delay))
				remaining = float(d)
				step = 0.05
				while remaining > 0:
					if self._stop_event.is_set():
						return
					while self._pause_event.is_set():
						self.countdownUpdated.emit(remaining, refresh_countdown)
						time.sleep(0.1)
						if self._stop_event.is_set():
							return
					self.countdownUpdated.emit(remaining, refresh_countdown)
					time.sleep(min(step, remaining))
					remaining -= step
				self.countdownUpdated.emit(0.0, refresh_countdown)
				x, y = coords[i]
				pyautogui.moveTo(x, y, duration=0.2)
				pyautogui.click()
				if i == 0:
					# Tentukan tombol modifier (Mac=Command, Win=Ctrl)
					mod_key = 'command' if sys.platform == 'darwin' else 'ctrl'
					
					# Tunggu sebentar agar fokus masuk
					time.sleep(0.5)
					
					# Select All
					pyautogui.hotkey(mod_key, 'a')
					time.sleep(0.5)
					
					# Set Clipboard
					self._clipboard_set_event.clear()
					self._last_set_clipboard = None
					self.setClipboardRequested.emit(text_to_paste)
					ok = self._clipboard_set_event.wait(2.0)
					if not ok or (self._last_set_clipboard is None) or (str(self._last_set_clipboard).strip() != str(text_to_paste).strip()):
						# Recompute total for progress emit
						with self._queue_lock:
							current_total = len(self.loaded_paste_texts)
						self.progressUpdated.emit(ui_idx, current_total)
						idx += 1
						continue
					time.sleep(0.5)
					
					# Paste
					pyautogui.hotkey(mod_key, 'v')
					pasted = True
			if pasted and self.loaded_from_db:
				copied_count += 1
				self._copied_count = copied_count
				self.csv_label.setText(f"Prompt DB: {len(self.loaded_paste_texts)} records (copied: {copied_count})")
				try:
					if self.db and len(self._loaded_prompt_ids) >= ui_idx:
						prompt_id = self._loaded_prompt_ids[ui_idx - 1]
						self.db.add_prompt_status(prompt_id, status='copied')
				except Exception:
					pass
			refresh_countdown -= 1
			# Update counters and emit progress with up-to-date total
			with self._queue_lock:
				self._current_done = ui_idx
				self._total = len(self.loaded_paste_texts)
				current_total = self._total
			self.progressUpdated.emit(ui_idx, current_total)
			idx += 1
		# Worker done (no more items at this moment)
		self.automationFinished.emit()
