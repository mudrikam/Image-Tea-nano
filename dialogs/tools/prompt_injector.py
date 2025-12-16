
import os
import sys
import json
import threading
import time
import random
from PySide6.QtWidgets import (
	QApplication, QDialog, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QDoubleSpinBox, QMessageBox, QFileDialog, QCheckBox, QSizePolicy
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
		if sys.platform != "win32":
			raise NotImplementedError("Click-through only supported on Windows")
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
		self.setAttribute(Qt.WA_TransparentForMouseEvents, enable)

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
	countdownUpdated = Signal(float)
	progressUpdated = Signal(int, int)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Prompt Injector Tool")
		self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

		# window icon should match main app
		icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
		if os.path.exists(icon_path):
			self.setWindowIcon(QIcon(icon_path))

		# database instance for prompt status updates
		self.db = ImageTeaDB()

		self.btn_action = QPushButton("Run Action")
		self.btn_action.clicked.connect(self.on_run_automation)
		self.btn_action.setIcon(qta.icon('fa6s.play'))
		self.btn_action.setIconSize(QSize(16, 16))

		self.btn_pause = QPushButton("Pause")
		self.btn_pause.setEnabled(False)
		self.btn_pause.clicked.connect(self.on_pause_toggle)
		self.btn_pause.setIcon(qta.icon('fa6s.pause'))
		self.btn_pause.setIconSize(QSize(16, 16))
		self.btn_stop = QPushButton("Stop")
		self.btn_stop.setEnabled(False)
		self.btn_stop.clicked.connect(self.on_stop)
		self.btn_stop.setIcon(qta.icon('fa6s.stop'))
		self.btn_stop.setIconSize(QSize(16, 16))

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
		colors = ["red", "green", "blue", "orange"]
		# explicit color hex codes for consistent rendering (ensures orange looks orange)
		self.color_map = {
			"red": "#ff4d4d",
			"green": "#00b050",
			"blue": "#1e90ff",
			"orange": "#ff8800",
		}
		# per-point extra notes
		self.point_notes = [" (select all & paste)", " (click)", " (click)", " (click)"]
		for i, color in enumerate(colors, start=1):
			h = QHBoxLayout()
			lbl = QLabel(f"Point {i} ({color}) delay (s):")
			# use explicit color codes to avoid platform-dependent color rendering
			lbl.setStyleSheet(f"color: {self.color_map.get(color, color)};")
			spin = QDoubleSpinBox()
			spin.setRange(0.0, 600.0)
			spin.setSingleStep(0.05)
			spin.setDecimals(2)
			spin.setValue(0.0)
			spin.setSuffix(" s")
			h.addWidget(lbl)
			h.addWidget(spin)
			layout.addLayout(h)
			self.delay_spinboxes.append(spin)

		h = QHBoxLayout()
		self.rand_lbl = QLabel("Random extra delay (s):")
		self.rand_spin = QDoubleSpinBox()
		self.rand_spin.setRange(0.0, 60.0)
		self.rand_spin.setSingleStep(0.05)
		self.rand_spin.setDecimals(2)
		self.rand_spin.setValue(0.0)
		self.rand_spin.setSuffix(" s")
		h.addWidget(self.rand_lbl)
		h.addWidget(self.rand_spin)
		layout.addLayout(h)
		# auto-save delay changes so user edits persist immediately
		for sb in self.delay_spinboxes:
			sb.valueChanged.connect(lambda v, s=sb: self.save_settings())
		self.rand_spin.valueChanged.connect(lambda v: self.save_settings())

		self.btn_load_csv = QPushButton("Load CSV")
		self.btn_load_csv.clicked.connect(self.on_load_csv)
		self.btn_load_csv.setIcon(qta.icon('fa6s.file-csv'))
		self.btn_load_csv.setIconSize(QSize(16, 16))
		self.btn_load_prompt = QPushButton("Load Prompt")
		self.btn_load_prompt.clicked.connect(self.on_load_prompt)
		self.btn_load_prompt.setIcon(qta.icon('fa6s.database'))
		self.btn_load_prompt.setIconSize(QSize(16, 16))
		self.csv_label = QLabel("CSV/Prompt: (none)")
		self.progress_label = QLabel("Progress: 0 / 0")
		layout.addWidget(self.btn_load_csv)
		layout.addWidget(self.btn_load_prompt)
		layout.addWidget(self.csv_label)
		layout.addWidget(self.progress_label)

		h_top = QHBoxLayout()
		h_top.addWidget(self.btn_action)
		h_top.addWidget(self.btn_pause)
		h_top.addWidget(self.btn_stop)
		layout.addLayout(h_top)

		h_bottom = QHBoxLayout()
		h_bottom.addWidget(self.btn_help)
		h_bottom.addWidget(self.btn_reset)
		layout.addLayout(h_bottom)

		# Put reset explanation into the Reset button tooltip instead of a visible label
		self.btn_reset.setToolTip("Reset Points: Move the four markers back to their default centered positions and save them to settings.")

		self.delay_label = QLabel("")
		layout.addWidget(self.delay_label)

		self.point_enabled = []
		for i, color in enumerate(colors, start=1):
			h2 = QHBoxLayout()
			# single checkbox with the label text included
			note = self.point_notes[i-1] if (i-1) < len(self.point_notes) else ""
			chk = QCheckBox(f"Point {i} ({color}){note}: X=0 Y=0")
			chk.setChecked(True)
			# store color for toggling visual state later (color_name is the logical color name)
			chk.setProperty("color_name", color)
			# apply explicit color code for consistent display
			chk.setStyleSheet(f"color: {self.color_map.get(color, color)};")
			chk.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
			self.point_enabled.append(chk)
			# compact layout
			h2.setContentsMargins(0, 0, 0, 0)
			h2.setSpacing(6)
			h2.addWidget(chk, 0, Qt.AlignLeft)
			layout.addLayout(h2)
			# connect toggle to handler
			chk.toggled.connect(lambda state, idx=i-1: self._on_point_toggle(idx, state))

		self.setLayout(layout)
		self.setFixedWidth(380)

		self.points = []
		screen = QGuiApplication.primaryScreen().availableGeometry()
		center = screen.center()
		offsets = [QPoint(0, 0), QPoint(40, 0), QPoint(-40, 0), QPoint(0, 40)]
		for idx, (color, off) in enumerate(zip(colors, offsets)):
			# create PointWidget using explicit hex color from the color_map so the visual marker matches the checkbox
			hex_color = self.color_map.get(color, color)
			p = PointWidget(hex_color, idx + 1)
			# Ensure point widgets are independent top-level tool windows
			p.setParent(None)
			p.setWindowFlag(Qt.Tool, True)
			p.setWindowFlag(Qt.WindowStaysOnTopHint, True)
			top_left = center - QPoint(p.width() // 2, p.height() // 2) + off
			p.move(top_left)
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

		self.setClipboardRequested.connect(self._set_clipboard)
		self.automationFinished.connect(self._on_automation_finished)
		self.progressUpdated.connect(self._on_progress_updated)
		self.countdownUpdated.connect(self._on_countdown_updated)

		def _on_key_press(key):
			from pynput import keyboard
			if key == keyboard.Key.esc or getattr(key, 'char', None) == '\x1b':
				QTimer.singleShot(0, self.on_pause_toggle)

		from pynput import keyboard
		self._pynput_listener = keyboard.Listener(on_press=_on_key_press)
		self._pynput_listener.daemon = True
		self._pynput_listener.start()

		# load persisted settings (create defaults if missing)
		self.load_settings()

	def _make_updater(self, idx: int, color: str):
		def updater(x: int, y: int):
			note = self.point_notes[idx] if idx < len(self.point_notes) else ""
			self.point_enabled[idx].setText(f"Point {idx+1} ({color}){note}: X={x} Y={y}")
			self.save_settings()
		return updater

	def _on_point_toggle(self, idx: int, enabled: bool):
		# show/hide the point widget, keep saved position intact
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
			# visually dim the checkbox text but keep it interactive
			chk.setStyleSheet("color: gray;")
		# persist enabled/disabled immediately
		self.save_settings()

	def on_run_automation(self):
		# only use enabled points
		coords = []
		base_delays = []
		for idx, p in enumerate(self.points):
			if idx < len(self.point_enabled) and not self.point_enabled[idx].isChecked():
				continue
			coords.append((p.frameGeometry().center().x(), p.frameGeometry().center().y()))
			base_delays.append(self.delay_spinboxes[idx].value())
		random_delay = float(self.rand_spin.value())
		paste_texts = self.loaded_paste_texts
		if not paste_texts:
			QMessageBox.warning(self, "No Data", "No records to process (CSV/Prompt is empty)")
			return
		total = len(paste_texts)
		self.progress_label.setText(f"Progress: 0 / {total}")
		self._stop_event = threading.Event()
		self._pause_event = threading.Event()
		self._clipboard_set_event = threading.Event()
		self._last_set_clipboard = None
		self._set_run_mode(True)
		self.btn_pause.setEnabled(True)
		self.btn_stop.setEnabled(True)
		self.btn_pause.setText("Pause")
		self._worker_thread = threading.Thread(
			target=self._run_sequence, args=(coords, base_delays, random_delay, paste_texts), daemon=True
		)
		self._worker_thread.start()

	def _set_run_mode(self, enable: bool):
		for p in self.points:
			p.set_click_through(enable)
		self.btn_action.setEnabled(not enable)
		try:
			self.btn_reset.setEnabled(not enable)
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
		self.delay_label.setText("")
		self._last_set_clipboard = None

	@Slot(int, int)
	def _on_progress_updated(self, done: int, total: int):
		self.progress_label.setText(f"Progress: {done} / {total}")

	def on_pause_toggle(self):
		if not getattr(self, '_pause_event', None):
			self.delay_label.setText("Not running")
			QTimer.singleShot(1000, lambda: self.delay_label.setText(""))
			return
		if self._pause_event.is_set():
			self._pause_event.clear()
			self.btn_pause.setText("Pause")
		else:
			self._pause_event.set()
			self.btn_pause.setText("Resume")

	def on_stop(self):
		self._stop_event.set()
		self._pause_event.clear()

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
		# build HTML using the color map and per-point notes so the help dialog matches current settings
		c = lambda name: self.color_map.get(name, name)
		note = lambda idx: self.point_notes[idx] if idx < len(self.point_notes) else ""
		html = (
			"<div>"
			f"<p><span style='color:{c('red')}; font-weight:bold;'>Point 1 (red){note(0)}:</span> After the first delay the cursor moves here, clicks, does <b>Ctrl+A</b>, sets the clipboard to the current text and pastes it with <b>Ctrl+V</b>.</p>"
			f"<p><span style='color:{c('green')}; font-weight:bold;'>Point 2 (green){note(1)}:</span> After the second delay the cursor moves here and clicks, typically used to confirm or advance the UI element.</p>"
			f"<p><span style='color:{c('blue')}; font-weight:bold;'>Point 3 (blue){note(2)}:</span> After the third delay the cursor moves here and clicks, often used for final actions like Submit or Next.</p>"
			f"<p><span style='color:{c('orange')}; font-weight:bold;'>Point 4 (orange){note(3)}:</span> Optional extra action after the third point.</p>"
			"<p><b>Reset Points:</b> Move the four markers back to their default centered positions and save them to settings.</p>"
			"</div>"
		)
		QMessageBox.information(self, "Help Points and Buttons", html)

	def _on_countdown_updated(self, remaining: float):
		self.delay_label.setText(f"Waiting: {remaining:.2f} s")

	def on_load_csv(self):
		path, _ = QFileDialog.getOpenFileName(self, "Select CSV", os.path.dirname(__file__), "CSV Files (*.csv);;All Files (*)")
		if not path:
			return
		texts = prompt_injector_helper.load_csv_texts(path)
		if not texts:
			QMessageBox.warning(self, "No Data", "CSV contains no records to process.")
			return
		self.loaded_paste_texts = texts
		self.loaded_from_db = False
		self._copied_count = 0
		self.csv_label.setText(f"CSV: {os.path.basename(path)} ({len(texts)} records)")
		self.save_settings()

	def on_load_prompt(self):
		if not self.db:
			self.db = ImageTeaDB()
		prompts = prompt_injector_helper.load_prompts_from_db(self.db)
		if not prompts:
			QMessageBox.warning(self, "No Data", "No prompts found in database.")
			return
		# prompts: list of (id, text)
		self._loaded_prompt_ids = [p[0] for p in prompts]
		self.loaded_paste_texts = [p[1] for p in prompts]
		self.loaded_from_db = True
		self._copied_count = 0
		self.csv_label.setText(f"Prompt DB: {len(prompts)} records (copied: 0)")
		self.save_settings()

	def _set_clipboard(self, text: str):
		cb = QApplication.clipboard()
		cb.setText(str(text))
		time.sleep(0.08)
		self._last_set_clipboard = str(text)
		self._clipboard_set_event.set()

	def closeEvent(self, event):
		# persist state on close
		self.save_settings()
		for p in list(self.points):
			p.close()
		if getattr(self, '_pynput_listener', None):
			self._pynput_listener.stop()
		super().closeEvent(event)

	def settings_path(self):
		# persist settings to global configs folder
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
		path = self.settings_path()
		try:
			os.makedirs(os.path.dirname(path), exist_ok=True)
			with open(path, "w", encoding="utf-8") as fh:
				json.dump(data, fh, indent=2)
		except Exception:
			# do not crash; persistence is best-effort
			pass

	def load_settings(self):
		path = self.settings_path()
		# create default config if missing
		if not os.path.exists(path):
			default = {
				"base_delays": [3.0, 3.0, 3.0, 3.0],
				"random_delay": 3.0,
				"enabled_points": [True, True, True, True],
				"csv_path": None,
				"point_positions": []
			}
			try:
				os.makedirs(os.path.dirname(path), exist_ok=True)
				with open(path, "w", encoding="utf-8") as fh:
					json.dump(default, fh, indent=2)
			except Exception:
				pass
			# Apply defaults to UI even if subsequent load fails
			bd = default.get("base_delays") or []
			for i, val in enumerate(bd):
				if i < len(self.delay_spinboxes):
					self.delay_spinboxes[i].setValue(float(val))
			rd = default.get("random_delay")
			if rd is not None:
				self.rand_spin.setValue(float(rd))
		try:
			with open(path, encoding="utf-8") as fh:
				data = json.load(fh)
		except Exception:
			return
		bd = data.get("base_delays") or []
		for i, val in enumerate(bd):
			if i < len(self.delay_spinboxes):
				self.delay_spinboxes[i].setValue(float(val))
		# load enabled points
		en = data.get("enabled_points") or []
		for i, chk in enumerate(self.point_enabled):
			if i < len(en):
				chk.setChecked(bool(en[i]))
		# apply visible states based on enabled flags
		for i, chk in enumerate(self.point_enabled):
			self._on_point_toggle(i, chk.isChecked())
		rd = data.get("random_delay")
		if rd is not None:
			self.rand_spin.setValue(float(rd))
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

	def _run_sequence(self, coords, base_delays, random_delay, paste_texts):
		import pyautogui
		pyautogui.FAILSAFE = True
		total = len(paste_texts)
		copied_count = 0
		for idx, text_to_paste in enumerate(paste_texts, start=1):
			pasted = False
			for i in range(min(4, len(coords))):
				d = float(base_delays[i]) + random.uniform(0, float(random_delay))
				remaining = float(d)
				step = 0.05
				while remaining > 0:
					if self._stop_event.is_set():
						return
					while self._pause_event.is_set():
						self.countdownUpdated.emit(remaining)
						time.sleep(0.1)
						if self._stop_event.is_set():
							return
					self.countdownUpdated.emit(remaining)
					time.sleep(min(step, remaining))
					remaining -= step
				self.countdownUpdated.emit(0.0)
				x, y = coords[i]
				pyautogui.moveTo(x, y, duration=0.2)
				pyautogui.click()
				if i == 0:
					time.sleep(0.06)
					pyautogui.hotkey("ctrl", "a")
					self._clipboard_set_event.clear()
					self._last_set_clipboard = None
					self.setClipboardRequested.emit(text_to_paste)
					ok = self._clipboard_set_event.wait(2.0)
					if not ok or (self._last_set_clipboard is None) or (str(self._last_set_clipboard).strip() != str(text_to_paste).strip()):
						self.progressUpdated.emit(idx, total)
						continue
					time.sleep(0.25)
					pyautogui.hotkey("ctrl", "v")
					pasted = True
			if pasted and self.loaded_from_db:
				copied_count += 1
				self._copied_count = copied_count
				self.csv_label.setText(f"Prompt DB: {total} records (copied: {copied_count})")
				# update DB status for this prompt if we have ids
				try:
					if self.db and len(self._loaded_prompt_ids) >= idx:
						prompt_id = self._loaded_prompt_ids[idx - 1]
						self.db.add_prompt_status(prompt_id, status='copied')
				except Exception:
					pass
			self.progressUpdated.emit(idx, total)
		self.automationFinished.emit()
