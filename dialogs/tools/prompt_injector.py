
import os
import sys
import json
import threading
import time
import random
import datetime
import math
from PySide6.QtWidgets import (
	QApplication, QDialog, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
	QDoubleSpinBox, QMessageBox, QFileDialog, QCheckBox, QSizePolicy, QProgressBar,
	QScrollArea, QFrame, QLineEdit, QComboBox, QColorDialog, QSpinBox,
	QListWidget, QListWidgetItem, QStatusBar, QMenu
)
from PySide6.QtCore import Qt, QPoint, Signal, Slot, QTimer, QSize, QEvent
from PySide6.QtGui import QGuiApplication, QCursor, QColor, QPainter, QBrush, QPen, QIcon, QFont, QPixmap, QDrag, QKeySequence
import qtawesome as qta
from helpers.tools import prompt_injector_helper
from config import BASE_PATH
from ui.theme_system import theme
from database.db_operation import ImageTeaDB
from dialogs.tools.icon_picker_dialog import IconPickerDialog

USE_QTIMER_MODE = (sys.platform == "darwin")
print(f"DEBUG: Automation mode = {'QTimer' if USE_QTIMER_MODE else 'Threading'} (Platform: {sys.platform})")

POINT_TYPES = ["paste", "key_action", "move", "click", "monitor"]
POINT_TYPE_ICONS = {
	"paste": "fa6s.paste",
	"key_action": "fa6s.keyboard",
	"move": "fa6s.arrows-up-down-left-right",
	"click": "fa6s.arrow-pointer",
	"monitor": "fa6s.eye",
}
POINT_TYPE_DESC = {
	"paste": "Click, select all, paste clipboard text",
	"key_action": "Move to point, then run stored keyboard shortcut",
	"move": "Move cursor to this point only (no click)",
	"click": "Move cursor to this point and left-click",
	"monitor": "Wait until pixel color changes at this point, then continue",
}


class PointWidget(QWidget):
	positionChanged = Signal(int, int, int)  # point_id, center_x, center_y

	def __init_click_through_helpers(self):
		self._GWL_EXSTYLE = -20
		self._WS_EX_TRANSPARENT = 0x00000020
		self._WS_EX_LAYERED = 0x00080000

	def set_click_through(self, enable: bool):
		self.setAttribute(Qt.WA_TransparentForMouseEvents, enable)
		if sys.platform == "darwin":
			self.setWindowFlag(Qt.WindowTransparentForInput, enable)
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
			self.setWindowFlag(Qt.WindowTransparentForInput, enable)
			if self.isVisible():
				self.hide()
				self.show()

	def __init__(self, point_id: int, color_hex: str, icon_name: str = "location-crosshairs",
				 icon_style: str = "solid", size: int = 32, name: str = "Point", parent=None):
		flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
		super().__init__(parent, flags)
		icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
		if os.path.exists(icon_path):
			self.setWindowIcon(QIcon(icon_path))
		self.setWindowTitle(name)
		self._point_id = point_id
		q = QColor(color_hex)
		if not q.isValid():
			q = QColor("#ff4d4d")
		self._color = q
		self._icon_name = icon_name
		self._icon_style = icon_style
		self._size = size
		self._is_dragging = False
		self._is_selected = False
		self.setAttribute(Qt.WA_TranslucentBackground, True)
		self.setFixedSize(size, size)
		self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
		self._drag_offset = None

	def update_appearance(self, color_hex: str, icon_name: str, icon_style: str, size: int):
		q = QColor(color_hex)
		if not q.isValid():
			q = QColor("#ff4d4d")
		self._color = q
		self._icon_name = icon_name
		self._icon_style = icon_style
		self._size = size
		self.setFixedSize(size, size)
		self.update()

	def set_selected(self, selected: bool):
		self._is_selected = selected
		self.update()

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.Antialiasing)
		bg = QColor(self._color)
		bg.setAlpha(170)
		painter.setBrush(QBrush(bg))
		painter.setPen(Qt.NoPen)
		painter.drawEllipse(0, 0, self._size, self._size)
		if self._is_selected:
			pen = QPen(QColor("#2196F3"))
			pen.setWidth(3)
			painter.setPen(pen)
			painter.setBrush(Qt.NoBrush)
			painter.drawEllipse(2, 2, self._size - 4, self._size - 4)
		try:
			if self._is_dragging:
				full_icon = "fa6s.crosshairs"
			else:
				prefix_map = {"solid": "fa6s", "regular": "fa6r", "brands": "fa6b"}
				prefix = prefix_map.get(self._icon_style, "fa6s")
				icon_n = self._icon_name if "." in self._icon_name else f"{prefix}.{self._icon_name}"
				full_icon = icon_n
			icon = qta.icon(full_icon, color="white")
			icon_size = max(self._size - 12, 12)
			pix = icon.pixmap(icon_size, icon_size)
			offset = (self._size - icon_size) // 2
			painter.drawPixmap(offset, offset, pix)
		except Exception:
			pass

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			self._is_dragging = True
			self.update()
			self.setWindowOpacity(0.6)
			half = QPoint(self._size // 2, self._size // 2)
			self._drag_offset = half

	def mouseMoveEvent(self, event):
		if self._drag_offset is None:
			return
		cursor = QCursor.pos()
		new_top_left = cursor - self._drag_offset
		self.move(new_top_left)
		center = self.frameGeometry().center()
		self.positionChanged.emit(self._point_id, center.x(), center.y())

	def mouseReleaseEvent(self, event):
		self._is_dragging = False
		self.update()
		self._drag_offset = None
		self.setWindowOpacity(1.0)
		# send final coords for database update
		center = self.frameGeometry().center()
		self.positionChanged.emit(self._point_id, center.x(), center.y())


class DraggablePointListWidget(QListWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self._click_item = None
		self._click_was_selected = False
		self._mouse_moved = False

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			item = self.itemAt(event.pos())
			self._click_item = item
			self._click_was_selected = item is not None and item.isSelected()
			self._mouse_moved = False
		super().mousePressEvent(event)

	def mouseMoveEvent(self, event):
		self._mouse_moved = True
		super().mouseMoveEvent(event)

	def mouseReleaseEvent(self, event):
		super().mouseReleaseEvent(event)
		if event.button() == Qt.LeftButton and not self._mouse_moved:
			modifiers = event.modifiers()
			item = self.itemAt(event.pos())
			if (item is not None and item is self._click_item
					and self._click_was_selected
					and not (modifiers & (Qt.ControlModifier | Qt.ShiftModifier))):
				item.setSelected(False)
		self._click_item = None
		self._click_was_selected = False

	def startDrag(self, supportedActions):
		item = self.currentItem()
		if not item:
			return
		widget = self.itemWidget(item)
		try:
			pixmap = widget.grab() if widget else QPixmap(200, 36)
			if not widget:
				pixmap.fill(Qt.lightGray)
		except Exception:
			pixmap = QPixmap(200, 36)
			pixmap.fill(Qt.lightGray)
		drag = QDrag(self)
		mime = self.model().mimeData(self.selectedIndexes())
		drag.setMimeData(mime)
		try:
			translucent = QPixmap(pixmap.size())
			translucent.fill(Qt.transparent)
			painter = QPainter(translucent)
			painter.setOpacity(0.65)
			painter.drawPixmap(0, 0, pixmap)
			painter.end()
			drag.setPixmap(translucent)
		except Exception:
			drag.setPixmap(pixmap)
		drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
		drag.exec(Qt.MoveAction)


_SHORTCUT_KEY_MAP = {
	Qt.Key_Return: "enter",
	Qt.Key_Enter: "enter",
	Qt.Key_Tab: "tab",
	Qt.Key_Backspace: "backspace",
	Qt.Key_Delete: "delete",
	Qt.Key_Escape: "esc",
	Qt.Key_Space: "space",
	Qt.Key_Left: "left",
	Qt.Key_Right: "right",
	Qt.Key_Up: "up",
	Qt.Key_Down: "down",
	Qt.Key_Home: "home",
	Qt.Key_End: "end",
	Qt.Key_PageUp: "pageup",
	Qt.Key_PageDown: "pagedown",
	Qt.Key_Insert: "insert",
	Qt.Key_Print: "printscreen",
	Qt.Key_ScrollLock: "scrolllock",
	Qt.Key_Pause: "pause",
	Qt.Key_CapsLock: "capslock",
	Qt.Key_NumLock: "numlock",
	Qt.Key_F1: "f1", Qt.Key_F2: "f2", Qt.Key_F3: "f3", Qt.Key_F4: "f4",
	Qt.Key_F5: "f5", Qt.Key_F6: "f6", Qt.Key_F7: "f7", Qt.Key_F8: "f8",
	Qt.Key_F9: "f9", Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
}
_SHORTCUT_MODIFIER_KEYS = {
	Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta,
	Qt.Key_AltGr, Qt.Key_Super_L, Qt.Key_Super_R,
}


class AddEditPointDialog(QDialog):
	def __init__(self, point_data=None, parent=None):
		super().__init__(parent)
		self._is_edit = point_data is not None
		self._point_data = point_data or {}
		self._selected_icon = self._point_data.get("icon", "location-crosshairs")
		self._selected_icon_style = self._point_data.get("icon_style", "solid")
		self._selected_color = self._point_data.get("color", "#ff4d4d")
		self._recording_shortcut = False
		self.setWindowTitle("Edit Point" if self._is_edit else "Add New Point")
		self.setModal(True)
		icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
		if os.path.exists(icon_path):
			self.setWindowIcon(QIcon(icon_path))
		self._build_ui()
		self.setMinimumWidth(400)

	def _build_ui(self):
		layout = QVBoxLayout()
		layout.setSpacing(5)
		layout.setContentsMargins(10, 10, 10, 10)

		name_type_row = QHBoxLayout()
		# icon + name label
		name_icon_lbl = QLabel()
		name_icon_lbl.setPixmap(qta.icon('fa6s.tag', color=theme.get_color('gray')).pixmap(16,16))
		name_type_row.addWidget(name_icon_lbl)
		name_type_row.addWidget(QLabel("Name:"))
		self.name_edit = QLineEdit()
		self.name_edit.setPlaceholderText("e.g. Paste Prompt")
		self.name_edit.setText(self._point_data.get("name", ""))
		self.name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		name_type_row.addWidget(self.name_edit)
		name_type_row.addSpacing(8)
		# type combo with icon
		self.type_combo = QComboBox()
		type_icon_lbl = QLabel()
		type_icon_lbl.setPixmap(qta.icon('fa6s.list', color=theme.get_color('gray')).pixmap(16,16))
		name_type_row.addWidget(type_icon_lbl)
		name_type_row.addWidget(self.type_combo)
		self.type_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		for pt in POINT_TYPES:
			self.type_combo.addItem(pt)
		cur_type = self._point_data.get("type", "click")
		if cur_type in POINT_TYPES:
			self.type_combo.setCurrentIndex(POINT_TYPES.index(cur_type))
		self.type_combo.currentIndexChanged.connect(self._on_type_changed)
		layout.addLayout(name_type_row)

		self.type_desc_lbl = QLabel()
		self.type_desc_lbl.setWordWrap(True)
		self.type_desc_lbl.setStyleSheet("color: gray; font-size: 9px; margin: 0;")
		layout.addWidget(self.type_desc_lbl)

		shortcut_row = QHBoxLayout()
		shortcut_row.setContentsMargins(0, 0, 0, 0)
		shortcut_row.setSpacing(4)
		self.shortcut_lbl = QLabel("Shortcut:")
		self.shortcut_edit = QLineEdit()
		self.shortcut_edit.setPlaceholderText("e.g. ctrl+c  or  ctrl+shift+z")
		self.shortcut_edit.setToolTip(
			"Key combination to execute. Separate keys with '+'. Example: ctrl+c, ctrl+shift+z, enter, tab"
		)
		self.shortcut_edit.setText(self._point_data.get("shortcut") or "")
		self.btn_record_shortcut = QPushButton()
		self.btn_record_shortcut.setFixedSize(26, 26)
		self.btn_record_shortcut.setToolTip("Record shortcut: click to start, press your key combo, click again to stop")
		self.btn_record_shortcut.setCursor(Qt.PointingHandCursor)
		self.btn_record_shortcut.clicked.connect(self._toggle_shortcut_recording)
		self._set_record_btn_idle()
		shortcut_row.addWidget(self.shortcut_lbl)
		shortcut_row.addWidget(self.shortcut_edit)
		shortcut_row.addWidget(self.btn_record_shortcut)
		self.shortcut_container = QWidget()
		self.shortcut_container.setLayout(shortcut_row)
		self.shortcut_container.layout().setContentsMargins(0,0,0,0)
		layout.addWidget(self.shortcut_container)

		icon_color_row = QHBoxLayout()
		icon_color_row.setSpacing(6)
		# icon label with icon
		icon_label_lbl = QLabel()
		icon_label_lbl.setPixmap(qta.icon('fa6s.icons', color=theme.get_color('gray')).pixmap(16,16))
		icon_color_row.addWidget(icon_label_lbl)
		icon_color_row.addWidget(QLabel("Icon:"))
		self.icon_preview = QLabel()
		self.icon_preview.setFixedSize(24, 24)
		icon_color_row.addWidget(self.icon_preview)
		self.icon_name_lbl = QLabel(self._selected_icon)
		icon_color_row.addWidget(self.icon_name_lbl)
		self.btn_pick_icon = QPushButton(qta.icon('fa6s.icons'), "")
		self.btn_pick_icon.setToolTip("Pick icon")
		self.btn_pick_icon.setFixedSize(28,28)
		self.btn_pick_icon.clicked.connect(self._pick_icon)
		icon_color_row.addWidget(self.btn_pick_icon)
		icon_color_row.addSpacing(12)
		# color label with icon
		color_label_lbl = QLabel()
		color_label_lbl.setPixmap(qta.icon('fa6s.palette', color=theme.get_color('gray')).pixmap(16,16))
		icon_color_row.addWidget(color_label_lbl)
		icon_color_row.addWidget(QLabel("Color:"))
		self.color_swatch = QPushButton()
		self.color_swatch.setFixedSize(24, 24)
		self.color_swatch.clicked.connect(self._pick_color)
		icon_color_row.addWidget(self.color_swatch)
		self.color_hex_lbl = QLabel(self._selected_color)
		icon_color_row.addWidget(self.color_hex_lbl)
		icon_color_row.addStretch()
		layout.addLayout(icon_color_row)

		size_delay_row = QHBoxLayout()
		# size icon
		size_icon_lbl = QLabel()
		size_icon_lbl.setPixmap(qta.icon('fa6s.arrows-up-down', color=theme.get_color('gray')).pixmap(16,16))
		size_delay_row.addWidget(size_icon_lbl)
		size_delay_row.addWidget(QLabel("Size:"))
		self.size_spin = QSpinBox()
		self.size_spin.setRange(16, 96)
		self.size_spin.setValue(self._point_data.get("size", 32))
		self.size_spin.setSuffix(" px")
		self.size_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		size_delay_row.addWidget(self.size_spin)
		size_delay_row.addSpacing(8)
		# delay icon
		delay_icon_lbl = QLabel()
		delay_icon_lbl.setPixmap(qta.icon('fa6s.hourglass-half', color=theme.get_color('gray')).pixmap(16,16))
		size_delay_row.addWidget(delay_icon_lbl)
		size_delay_row.addWidget(QLabel("Delay:"))
		self.delay_spin = QDoubleSpinBox()
		self.delay_spin.setRange(0.0, 600.0)
		self.delay_spin.setSingleStep(0.05)
		self.delay_spin.setDecimals(2)
		self.delay_spin.setValue(self._point_data.get("delay", 1.0))
		self.delay_spin.setSuffix(" s")
		self.delay_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		self.delay_spin.setToolTip(
			"Wait before this point's action.\nFor monitor type: maximum wait time before continuing regardless."
		)
		size_delay_row.addWidget(self.delay_spin)
		size_delay_row.addStretch()
		layout.addLayout(size_delay_row)

		bot_row = QHBoxLayout()
		self.enabled_chk = QCheckBox("Enabled")
		self.enabled_chk.setChecked(self._point_data.get("enabled", True))
		bot_row.addWidget(self.enabled_chk)
		bot_row.addStretch()
		cancel_btn = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
		cancel_btn.clicked.connect(self.reject)
		bot_row.addWidget(cancel_btn)
		ok_btn = QPushButton(qta.icon('fa6s.check'), " OK")
		ok_btn.setDefault(True)
		ok_btn.clicked.connect(self._on_ok)
		bot_row.addWidget(ok_btn)
		layout.addLayout(bot_row)

		self.setLayout(layout)
		self._refresh_color_swatch()
		self._refresh_icon_preview()
		self._on_type_changed()

	def _set_record_btn_idle(self):
		self.btn_record_shortcut.setStyleSheet(
			"QPushButton {"
			"  border-radius: 13px;"
			"  border: 2px solid #888;"
			"  background-color: transparent;"
			"}"
			"QPushButton:hover {"
			"  border-color: #aaa;"
			"  background-color: rgba(180,180,180,40);"
			"}"
		)
		self.btn_record_shortcut.setText("")
		self.btn_record_shortcut.setIcon(qta.icon('fa6s.circle', color='#888'))
		self.btn_record_shortcut.setIconSize(QSize(12, 12))

	def _set_record_btn_active(self):
		try:
			red = theme.get_color('error')
		except Exception:
			red = '#f44336'
		self.btn_record_shortcut.setStyleSheet(
			f"QPushButton {{"
			f"  border-radius: 13px;"
			f"  border: 2px solid {red};"
			f"  background-color: {red};"
			f"}}"
			f"QPushButton:hover {{"
			f"  background-color: {red};"
			f"}}"
		)
		self.btn_record_shortcut.setText("")
		self.btn_record_shortcut.setIcon(qta.icon('fa6s.circle', color='white'))
		self.btn_record_shortcut.setIconSize(QSize(10, 10))

	def _toggle_shortcut_recording(self):
		self._recording_shortcut = not self._recording_shortcut
		if self._recording_shortcut:
			self._set_record_btn_active()
			self.shortcut_edit.setPlaceholderText("Press your shortcut now...")
			self.shortcut_edit.clear()
			self.shortcut_edit.setReadOnly(True)
			self.setFocus()
		else:
			self._set_record_btn_idle()
			self.shortcut_edit.setPlaceholderText("e.g. ctrl+c  or  ctrl+shift+z")
			self.shortcut_edit.setReadOnly(False)

	def keyPressEvent(self, event):
		if self._recording_shortcut:
			key = event.key()
			if key in _SHORTCUT_MODIFIER_KEYS:
				event.accept()
				return
			parts = []
			modifiers = event.modifiers()
			if modifiers & Qt.ControlModifier:
				parts.append("ctrl")
			if modifiers & Qt.AltModifier:
				parts.append("alt")
			if modifiers & Qt.ShiftModifier:
				parts.append("shift")
			if modifiers & Qt.MetaModifier:
				parts.append("win")
			key_name = _SHORTCUT_KEY_MAP.get(key)
			if key_name is None:
				text = event.text()
				if text and text.isprintable() and not text.isspace():
					key_name = text.lower()
				else:
					key_name = QKeySequence(key).toString().lower()
			if key_name:
				parts.append(key_name)
				combo = "+".join(parts)
				self.shortcut_edit.setReadOnly(False)
				self.shortcut_edit.setText(combo)
				self.shortcut_edit.setReadOnly(True)
				self._recording_shortcut = False
				self._set_record_btn_idle()
				self.shortcut_edit.setPlaceholderText("e.g. ctrl+c  or  ctrl+shift+z")
				self.shortcut_edit.setReadOnly(False)
			event.accept()
			return
		super().keyPressEvent(event)

	def _on_type_changed(self):
		t = self.type_combo.currentText()
		self.type_desc_lbl.setText(POINT_TYPE_DESC.get(t, ""))
		self.shortcut_container.setVisible(t == "key_action")
		if t != "key_action" and self._recording_shortcut:
			self._recording_shortcut = False
			self._set_record_btn_idle()
			self.shortcut_edit.setReadOnly(False)

	def _pick_icon(self):
		dlg = IconPickerDialog(current_icon=self._selected_icon, parent=self)
		dlg.icon_selected.connect(self._on_icon_selected)
		dlg.exec()

	def _on_icon_selected(self, icon_name):
		self._selected_icon = icon_name
		self._selected_icon_style = "solid"
		self.icon_name_lbl.setText(icon_name)
		self._refresh_icon_preview()

	def _pick_color(self):
		initial = QColor(self._selected_color)
		col = QColorDialog.getColor(initial, self, "Pick Point Color")
		if col.isValid():
			self._selected_color = col.name()
			self.color_hex_lbl.setText(self._selected_color)
			self._refresh_color_swatch()

	def _refresh_color_swatch(self):
		self.color_swatch.setStyleSheet(
			f"background-color: {self._selected_color}; border: 1px solid #555; border-radius: 3px;"
		)

	def _refresh_icon_preview(self):
		try:
			prefix_map = {"solid": "fa6s", "regular": "fa6r", "brands": "fa6b"}
			prefix = prefix_map.get(self._selected_icon_style, "fa6s")
			full = f"{prefix}.{self._selected_icon}" if "." not in self._selected_icon else self._selected_icon
			icon = qta.icon(full, color=self._selected_color)
			self.icon_preview.setPixmap(icon.pixmap(20, 20))
		except Exception:
			self.icon_preview.clear()

	def _on_ok(self):
		if not self.name_edit.text().strip():
			QMessageBox.warning(self, "Missing Name", "Please enter a name for this point.")
			return
		self.accept()

	def get_data(self):
		return {
			"name": self.name_edit.text().strip(),
			"type": self.type_combo.currentText(),
			"icon": self._selected_icon,
			"icon_style": self._selected_icon_style,
			"color": self._selected_color,
			"size": self.size_spin.value(),
			"delay": self.delay_spin.value(),
			"enabled": self.enabled_chk.isChecked(),
			"shortcut": self.shortcut_edit.text().strip() if self.type_combo.currentText() == "key_action" else None,
		}


class PointItemWidget(QWidget):
	edit_requested = Signal(dict)
	delete_requested = Signal(dict)
	toggle_enabled = Signal(dict, bool)

	def __init__(self, point_data: dict, parent=None):
		super().__init__(parent)
		self._point_data = point_data
		self._build_ui()

	def _build_ui(self):
		color = self._point_data.get("color", "#ff4d4d")
		hex_color = color.lstrip('#')
		try:
			r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
		except Exception:
			r, g, b = 255, 77, 77
		self._r, self._g, self._b = r, g, b

		container = QWidget()
		self._container = container
		container.setObjectName(f"piItem_{self._point_data['id']}")
		container.setStyleSheet(
			f"QWidget#piItem_{self._point_data['id']} {{"
			f"background-color: rgba({r},{g},{b},25);"
			f"border-radius: 4px;"
			f"border: 1px solid rgba({r},{g},{b},0);}}"
			f"QWidget#piItem_{self._point_data['id']}:hover {{"
			f"background-color: rgba({r},{g},{b},70);"
			f"border: 1px solid rgba({r},{g},{b},180);}}"
		)

		main = QHBoxLayout(container)
		main.setContentsMargins(8, 6, 8, 6)
		main.setSpacing(6)

		prefix_map = {"solid": "fa6s", "regular": "fa6r", "brands": "fa6b"}
		icon_style = self._point_data.get("icon_style", "solid")
		prefix = prefix_map.get(icon_style, "fa6s")
		icon_name = self._point_data.get("icon", "location-crosshairs")
		full_icon = f"{prefix}.{icon_name}" if "." not in icon_name else icon_name

		icon_lbl = QLabel()
		try:
			ico = qta.icon(full_icon, color=color)
			icon_lbl.setPixmap(ico.pixmap(22, 22))
		except Exception:
			pass
		icon_lbl.setFixedWidth(24)
		icon_lbl.setStyleSheet("background: transparent;")
		main.addWidget(icon_lbl)

		info_col = QVBoxLayout()
		info_col.setSpacing(1)

		name_lbl = QLabel(self._point_data.get("name", "Unnamed"))
		name_font = QFont()
		name_font.setBold(True)
		name_font.setPointSize(9)
		name_lbl.setFont(name_font)
		name_lbl.setStyleSheet("background: transparent;")
		info_col.addWidget(name_lbl)

		pt = self._point_data.get("type", "click")
		sc = self._point_data.get("shortcut") or ""
		sc_part = f"  [{sc}]" if sc and pt == "key_action" else ""
		detail_text = (
			f"{pt}{sc_part}  \u00b7  delay {self._point_data.get('delay', 0):.2f}s"
			f"  \u00b7  pos ({self._point_data.get('pos_x', 0)}, {self._point_data.get('pos_y', 0)})"
		)
		detail_lbl = QLabel(detail_text)
		detail_lbl.setStyleSheet("font-size: 9px; background: transparent;")
		info_col.addWidget(detail_lbl)

		main.addLayout(info_col)
		main.addStretch()

		self._enabled_state = self._point_data.get("enabled", True)
		self.toggle_btn = QPushButton()
		self.toggle_btn.setFixedSize(30, 26)
		self.toggle_btn.setFlat(True)
		self.toggle_btn.setFocusPolicy(Qt.NoFocus)
		self.toggle_btn.setStyleSheet("background: transparent; border: none;")
		self.toggle_btn.setToolTip("Enable / disable this point")
		self._refresh_toggle_icon()
		self.toggle_btn.clicked.connect(self._on_toggle_clicked)
		main.addWidget(self.toggle_btn)

		edit_btn = QPushButton(qta.icon('fa6s.pen'), "")
		edit_btn.setFixedSize(26, 26)
		edit_btn.setFlat(True)
		edit_btn.setStyleSheet("background: transparent; border: none;")
		edit_btn.setFocusPolicy(Qt.NoFocus)
		edit_btn.setToolTip("Edit point")
		edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._point_data))
		main.addWidget(edit_btn)

		del_btn = QPushButton(qta.icon('fa6s.trash'), "")
		del_btn.setFixedSize(26, 26)
		del_btn.setFlat(True)
		del_btn.setStyleSheet("background: transparent; border: none;")
		del_btn.setFocusPolicy(Qt.NoFocus)
		del_btn.setToolTip("Delete point")
		del_btn.clicked.connect(lambda: self.delete_requested.emit(self._point_data))
		main.addWidget(del_btn)

		outer = QVBoxLayout(self)
		outer.setContentsMargins(2, 2, 2, 2)
		outer.setSpacing(0)
		outer.addWidget(container)
		self.setLayout(outer)

	def _refresh_toggle_icon(self):
		if self._enabled_state:
			ico = qta.icon('fa6s.toggle-on', color='#4caf50')
		else:
			ico = qta.icon('fa6s.toggle-off', color='#888888')
		self.toggle_btn.setIcon(ico)
		self.toggle_btn.setIconSize(QSize(22, 22))

	def _on_toggle_clicked(self):
		self._enabled_state = not self._enabled_state
		self._refresh_toggle_icon()
		self.toggle_enabled.emit(self._point_data, self._enabled_state)

	def set_selected(self, selected: bool):
		r, g, b = self._r, self._g, self._b
		pid = self._point_data['id']
		if selected:
			self._container.setStyleSheet(
				f"QWidget#piItem_{pid} {{"
				f"background-color: rgba({r},{g},{b},90);"
				f"border-radius: 4px;"
				f"border: 1px solid rgba({r},{g},{b},220);}}"
				f"QWidget#piItem_{pid}:hover {{"
				f"background-color: rgba({r},{g},{b},110);"
				f"border: 1px solid rgba({r},{g},{b},255);}}"
			)
		else:
			self._container.setStyleSheet(
				f"QWidget#piItem_{pid} {{"
				f"background-color: rgba({r},{g},{b},25);"
				f"border-radius: 4px;"
				f"border: 1px solid rgba({r},{g},{b},0);}}"
				f"QWidget#piItem_{pid}:hover {{"
				f"background-color: rgba({r},{g},{b},70);"
				f"border: 1px solid rgba({r},{g},{b},180);}}"
			)


class PromptInjectorDialog(QDialog):
	setClipboardRequested = Signal(str)
	automationFinished = Signal()
	countdownUpdated = Signal(float)
	progressUpdated = Signal(int, int)
	currentFileUpdated = Signal(int, int, str, int, int)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Prompt Injector v2")
		self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
		self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)

		icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
		if os.path.exists(icon_path):
			self.setWindowIcon(QIcon(icon_path))

		self.db = ImageTeaDB()

		self._point_widgets = {}
		self._drag_last_centers = {}
		self._loaded_paste_texts = None
		self._loaded_from_db = False
		self._copied_count = 0
		self._loaded_prompt_ids = []
		self._loaded_files = []
		self._last_csv_dir = None
		self._queue_lock = threading.Lock()
		self._current_done = 0
		self._total = 0
		self._run_start_time = None
		self._pause_start = None
		self._pause_accum = 0.0

		if USE_QTIMER_MODE:
			self._automation_timer = QTimer(self)
			self._automation_timer.timeout.connect(self._automation_tick)
			self._automation_running = False
			self._automation_paused = False
			self._prompt_index = 0
			self._state = "IDLE"
			self._wait_start = 0
			self._wait_dur = 0
			self._pt_idx = 0
			self._run_points = []
			self._monitor_init_color = None
			self._monitor_timeout = 0
			self._monitor_start = 0
		else:
			self._worker_thread = None
			self._stop_event = None
			self._pause_event = None
			self._clipboard_set_event = None
			self._last_set_clipboard = None

		self._stats_timer = QTimer(self)
		self._stats_timer.setInterval(1000)
		self._stats_timer.timeout.connect(
			lambda: self._update_stats(getattr(self, '_current_done', 0), getattr(self, '_total', 0))
		)

		self._build_ui()

		self.setAcceptDrops(True)
		self.setMinimumWidth(380)

		from pynput import keyboard

		def _on_key_press(key):
			if key == keyboard.Key.esc or getattr(key, 'char', None) == '\x1b':
				QTimer.singleShot(0, self.on_pause_toggle)

		self._pynput_listener = keyboard.Listener(on_press=_on_key_press)
		self._pynput_listener.daemon = True
		self._pynput_listener.start()

		self.load_settings()
		self._load_points_from_db()

	def _build_ui(self):
		layout = QVBoxLayout()
		layout.setSpacing(6)
		layout.setContentsMargins(8, 8, 8, 8)

		self.points_list = DraggablePointListWidget()
		self.points_list.setObjectName("pointsList")
		self.points_list.setAlternatingRowColors(False)
		self.points_list.setSpacing(2)
		self.points_list.setDragEnabled(True)
		self.points_list.setAcceptDrops(True)
		self.points_list.setDropIndicatorShown(True)
		self.points_list.setDragDropMode(QListWidget.InternalMove)
		self.points_list.setDefaultDropAction(Qt.MoveAction)
		self.points_list.setSelectionMode(QListWidget.ExtendedSelection)
		self.points_list.itemSelectionChanged.connect(self._on_selection_changed)
		self.points_list.setMinimumHeight(120)
		self.points_list.setMaximumHeight(320)
		self.points_list.model().rowsMoved.connect(self._on_rows_moved)
		self.points_list.setContextMenuPolicy(Qt.CustomContextMenu)
		self.points_list.customContextMenuRequested.connect(self._on_point_context_menu)
		self.points_list.itemDoubleClicked.connect(self._on_point_double_clicked)
		layout.addWidget(self.points_list)

		h_preset = QHBoxLayout()
		h_preset.setSpacing(4)
		self.btn_import_preset = QPushButton(qta.icon('fa6s.file-import'), " Import Preset")
		self.btn_import_preset.setIconSize(QSize(14, 14))
		self.btn_import_preset.setToolTip("Import points from a JSON preset file (replaces current points).")
		self.btn_import_preset.clicked.connect(self.on_import_preset)
		h_preset.addWidget(self.btn_import_preset)
		self.btn_export_preset = QPushButton(qta.icon('fa6s.file-export'), " Export Preset")
		self.btn_export_preset.setIconSize(QSize(14, 14))
		self.btn_export_preset.setToolTip("Export current points to a JSON preset file.")
		self.btn_export_preset.clicked.connect(self.on_export_preset)
		h_preset.addWidget(self.btn_export_preset)
		self.btn_clear_points = QPushButton(qta.icon('fa6s.trash'), " Clear Points")
		self.btn_clear_points.setIconSize(QSize(14, 14))
		self.btn_clear_points.setToolTip("Delete all points (this action cannot be undone).")
		self.btn_clear_points.clicked.connect(self.on_clear_points)
		h_preset.addWidget(self.btn_clear_points)
		h_preset.addStretch()
		layout.addLayout(h_preset)

		sep2 = QFrame()
		sep2.setFrameShape(QFrame.HLine)
		sep2.setFrameShadow(QFrame.Sunken)
		layout.addWidget(sep2)

		rand_row = QHBoxLayout()
		rand_row.addWidget(QLabel("Random extra delay (s):"))
		self.rand_spin = QDoubleSpinBox()
		self.rand_spin.setRange(0.0, 60.0)
		self.rand_spin.setSingleStep(0.05)
		self.rand_spin.setDecimals(2)
		self.rand_spin.setValue(0.0)
		self.rand_spin.setSuffix(" s")
		self.rand_spin.setToolTip("Random extra delay added on top of each point's base delay (0 = disabled).")
		self.rand_spin.setFixedWidth(110)
		self.rand_spin.valueChanged.connect(lambda v: self.save_settings())
		rand_row.addStretch()
		rand_row.addWidget(self.rand_spin)
		layout.addLayout(rand_row)

		h_shutdown = QHBoxLayout()
		h_shutdown.setSpacing(6)
		self.shutdown_chk = QCheckBox("Shutdown on complete")
		self.shutdown_chk.setChecked(False)
		self.shutdown_chk.setToolTip("Shut down the computer when automation finishes.")
		h_shutdown.addWidget(self.shutdown_chk)
		h_shutdown.addStretch()
		layout.addLayout(h_shutdown)

		h_files = QHBoxLayout()
		h_files.setSpacing(6)
		self.btn_load_csv = QPushButton(qta.icon('fa6s.file-csv'), " Load CSV/TXT")
		self.btn_load_csv.setIconSize(QSize(16, 16))
		self.btn_load_csv.setToolTip("Load prompts from CSV or TXT files. TXT: one prompt per non-empty line.")
		self.btn_load_csv.clicked.connect(self.on_load_csv)
		h_files.addWidget(self.btn_load_csv)

		self.btn_load_prompt = QPushButton(qta.icon('fa6s.database'), " Load Prompt")
		self.btn_load_prompt.setIconSize(QSize(16, 16))
		self.btn_load_prompt.setToolTip("Load prompts from the Image Tea database.")
		self.btn_load_prompt.clicked.connect(self.on_load_prompt)
		h_files.addWidget(self.btn_load_prompt)

		self.btn_clear_data = QPushButton(qta.icon('fa6s.trash-can'), " Clear")
		self.btn_clear_data.setIconSize(QSize(16, 16))
		self.btn_clear_data.setToolTip("Clear loaded CSV / Prompt data.")
		self.btn_clear_data.clicked.connect(self.on_clear_data)
		h_files.addWidget(self.btn_clear_data)

		self.btn_help = QPushButton(qta.icon('fa6s.question'), "")
		self.btn_help.setFixedWidth(28)
		self.btn_help.setIconSize(QSize(14, 14))
		self.btn_help.setToolTip("Help: how to use Prompt Injector v2")
		self.btn_help.clicked.connect(self.show_help_dialog)
		h_files.addWidget(self.btn_help)
		layout.addLayout(h_files)

		self.csv_label = QLabel("CSV/Prompt: (none)")
		layout.addWidget(self.csv_label)

		self.progress_bar = QProgressBar()
		self.progress_bar.setMinimum(0)
		self.progress_bar.setMaximum(1)
		self.progress_bar.setValue(0)
		self.progress_bar.setTextVisible(True)
		self.progress_bar.setFormat("0 / 0")
		layout.addWidget(self.progress_bar)

		h_stats = QHBoxLayout()
		left_v = QVBoxLayout()
		right_v = QVBoxLayout()
		self.stats_eta_lbl = QLabel("ETA: -")
		self.stats_remaining_lbl = QLabel("Remaining: -")
		self.stats_elapsed_lbl = QLabel("Elapsed: -")
		self.stats_progress_lbl = QLabel("Progress: 0/0")
		self.stats_speed_lbl = QLabel("Speed: 0.00/m")
		for lbl in (self.stats_eta_lbl, self.stats_remaining_lbl, self.stats_elapsed_lbl,
					self.stats_progress_lbl, self.stats_speed_lbl):
			lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
		left_v.addWidget(self.stats_eta_lbl)
		left_v.addWidget(self.stats_remaining_lbl)
		left_v.addWidget(self.stats_elapsed_lbl)
		right_v.addWidget(self.stats_progress_lbl)
		right_v.addWidget(self.stats_speed_lbl)
		h_stats.addLayout(left_v)
		h_stats.addLayout(right_v)
		layout.addLayout(h_stats)

		self.delay_label = QLabel("")
		self.delay_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
		self.delay_label.setMinimumHeight(18)
		self.delay_label.setAlignment(Qt.AlignCenter)
		self.delay_label.setStyleSheet("font-size: 10px; color: gray;")
		layout.addWidget(self.delay_label)

		h_btns = QHBoxLayout()
		self.btn_action = QPushButton(qta.icon('fa6s.play', color=theme.get_color('primary')), " Run Action")
		self.btn_action.setIconSize(QSize(16, 16))
		self.btn_action.setToolTip("Start the automation: all enabled points run in order for each prompt.")
		self.btn_action.clicked.connect(self.on_run_automation)
		h_btns.addWidget(self.btn_action)

		self.btn_pause = QPushButton(qta.icon('fa6s.pause', color=theme.get_color('warning')), " Pause")
		self.btn_pause.setIconSize(QSize(16, 16))
		self.btn_pause.setEnabled(False)
		self.btn_pause.setToolTip("Pause or resume automation. Esc key also pauses.")
		self.btn_pause.clicked.connect(self.on_pause_toggle)
		h_btns.addWidget(self.btn_pause)

		self.btn_stop = QPushButton(qta.icon('fa6s.stop', color=theme.get_color('error')), " Stop")
		self.btn_stop.setIconSize(QSize(16, 16))
		self.btn_stop.setEnabled(False)
		self.btn_stop.setToolTip("Stop automation immediately.")
		self.btn_stop.clicked.connect(self.on_stop)
		h_btns.addWidget(self.btn_stop)

		self.btn_reset = QPushButton(qta.icon('fa6s.arrows-rotate'), " Reset Points")
		self.btn_reset.setIconSize(QSize(16, 16))
		self.btn_reset.setToolTip("Move all point markers back to screen center.")
		self.btn_reset.clicked.connect(self.on_reset_points)
		h_btns.addWidget(self.btn_reset)

		layout.addLayout(h_btns)

		self.status_bar = QStatusBar()
		self.status_bar.setSizeGripEnabled(False)
		self.status_bar.setMaximumHeight(22)
		self.status_bar.setStyleSheet("font-size: 10px;")
		layout.addWidget(self.status_bar)
		self.status_bar.showMessage("Ready")

		self.setLayout(layout)

		self.setClipboardRequested.connect(self._set_clipboard)
		self.automationFinished.connect(self._on_automation_finished)
		self.progressUpdated.connect(self._on_progress_updated)
		self.countdownUpdated.connect(self._on_countdown_updated)
		self.currentFileUpdated.connect(self._on_current_file_updated)

	# ───── Point Management ─────────────────────────────────────────────────

	def _load_points_from_db(self):
		scroll_val = self.points_list.verticalScrollBar().value()
		try:
			points = self.db.get_all_prompt_injector_points()
		except Exception as e:
			print(f"Failed to load points from DB: {e}")
			points = []
		self._rebuild_points_ui(points)
		QTimer.singleShot(0, lambda: self.points_list.verticalScrollBar().setValue(scroll_val))

	def _rebuild_points_ui(self, points: list):
		for pw in list(self._point_widgets.values()):
			pw.close()
		self._point_widgets.clear()
		self.points_list.clear()

		for point_data in points:
			self._add_point_item_widget(point_data)
			self._create_point_widget(point_data)

		self._add_new_point_button_item()

	def _add_new_point_button_item(self):
		item = QListWidgetItem()
		item.setFlags(Qt.NoItemFlags)
		item.setData(Qt.UserRole + 1, '_add_button')
		btn = QPushButton(qta.icon('fa6s.plus'), " Add New Point")
		btn.setFlat(True)
		btn.setIconSize(QSize(14, 14))
		btn.setStyleSheet("text-align: left; padding-left: 8px;")
		btn.setToolTip("Add a new automation point")
		btn.clicked.connect(self.on_add_point)
		self.btn_add_point = btn
		item.setSizeHint(QSize(200, 30))
		self.points_list.addItem(item)
		self.points_list.setItemWidget(item, btn)

	def _add_point_item_widget(self, point_data: dict):
		item_w = PointItemWidget(point_data)
		item_w.edit_requested.connect(self.on_edit_point)
		item_w.delete_requested.connect(self.on_delete_point)
		item_w.toggle_enabled.connect(self._on_point_toggle_enabled)
		list_item = QListWidgetItem()
		list_item.setData(Qt.UserRole, point_data)
		list_item.setSizeHint(item_w.sizeHint())
		self.points_list.addItem(list_item)
		self.points_list.setItemWidget(list_item, item_w)

	def _create_point_widget(self, point_data: dict):
		pw = PointWidget(
			point_id=point_data['id'],
			color_hex=point_data.get('color', '#ff4d4d'),
			icon_name=point_data.get('icon', 'location-crosshairs'),
			icon_style=point_data.get('icon_style', 'solid'),
			size=point_data.get('size', 32),
			name=point_data.get('name', 'Point'),
		)
		pw.setWindowFlag(Qt.Window, True)
		pw.setWindowFlag(Qt.FramelessWindowHint, True)
		pw.setWindowFlag(Qt.WindowStaysOnTopHint, True)
		px = point_data.get('pos_x', 0)
		py = point_data.get('pos_y', 0)
		if px == 0 and py == 0:
			screen = QGuiApplication.primaryScreen().availableGeometry()
			center = screen.center()
			px = center.x()
			py = center.y()
		half = pw.width() // 2
		pw.move(QPoint(px - half, py - half))
		pw.positionChanged.connect(self._on_point_position_changed)
		if point_data.get('enabled', True):
			pw.show()
			pw.raise_()
		self._point_widgets[point_data['id']] = pw

	def _get_selected_point_widget_ids(self) -> set:
		ids = set()
		for item in self.points_list.selectedItems():
			d = item.data(Qt.UserRole)
			if d and d.get('id'):
				ids.add(d['id'])
		return ids

	def _update_list_item_pos(self, point_id: int, cx: int, cy: int):
		for i in range(self.points_list.count()):
			list_item = self.points_list.item(i)
			if list_item:
				w = self.points_list.itemWidget(list_item)
				if w and isinstance(w, PointItemWidget) and w._point_data.get('id') == point_id:
					w._point_data['pos_x'] = cx
					w._point_data['pos_y'] = cy
					break

	def _on_point_position_changed(self, point_id: int, cx: int, cy: int):
		pw = self._point_widgets.get(point_id)
		is_dragging = pw and getattr(pw, '_is_dragging', False)

		if is_dragging:
			last = self._drag_last_centers.get(point_id)
			if last is not None:
				dx = cx - last[0]
				dy = cy - last[1]
				selected_ids = self._get_selected_point_widget_ids()
				for pid, gpw in self._point_widgets.items():
					if pid == point_id:
						continue
					if pid not in selected_ids:
						continue
					gpw.move(gpw.pos().x() + dx, gpw.pos().y() + dy)
			self._drag_last_centers[point_id] = (cx, cy)
			return

		self._drag_last_centers.pop(point_id, None)
		try:
			self.db.update_prompt_injector_point_position(point_id, cx, cy)
		except Exception as e:
			print(f"Failed to save point position to DB: {e}")
		self._update_list_item_pos(point_id, cx, cy)

		selected_ids = self._get_selected_point_widget_ids()
		for pid, gpw in self._point_widgets.items():
			if pid == point_id:
				continue
			if pid not in selected_ids:
				continue
			gcenter = gpw.frameGeometry().center()
			try:
				self.db.update_prompt_injector_point_position(pid, gcenter.x(), gcenter.y())
			except Exception as e:
				print(f"Failed to save group point position to DB: {e}")
			self._update_list_item_pos(pid, gcenter.x(), gcenter.y())

	def _on_point_toggle_enabled(self, point_data: dict, enabled: bool):
		pid = point_data['id']
		try:
			self.db.update_prompt_injector_point_enabled(pid, enabled)
		except Exception as e:
			print(f"Failed to update point enabled state: {e}")
		pw = self._point_widgets.get(pid)
		if pw:
			if enabled:
				pw.show()
				pw.raise_()
			else:
				pw.hide()

	def _on_selection_changed(self):
		selected_ids = set()
		for item in self.points_list.selectedItems():
			d = item.data(Qt.UserRole)
			if d and d.get('id'):
				selected_ids.add(d['id'])
		for i in range(self.points_list.count()):
			list_item = self.points_list.item(i)
			if not list_item:
				continue
			w = self.points_list.itemWidget(list_item)
			if w and isinstance(w, PointItemWidget):
				w.set_selected(w._point_data.get('id') in selected_ids)
		for pid, pw in self._point_widgets.items():
			pw.set_selected(pid in selected_ids)

	def _get_selected_point_data_list(self) -> list:
		result = []
		for item in self.points_list.selectedItems():
			if item.data(Qt.UserRole + 1) == '_add_button':
				continue
			d = item.data(Qt.UserRole)
			if d and d.get('id'):
				result.append(d)
		result.sort(key=lambda p: p.get('order_index', 0))
		return result

	def on_add_point(self):
		dlg = AddEditPointDialog(parent=self)
		if dlg.exec() != QDialog.Accepted:
			return
		data = dlg.get_data()
		all_points = self.db.get_all_prompt_injector_points()
		next_order = len(all_points)
		screen = QGuiApplication.primaryScreen().availableGeometry()
		center = screen.center()
		new_id = self.db.add_prompt_injector_point(
			name=data['name'],
			icon=data['icon'],
			icon_style=data['icon_style'],
			color=data['color'],
			size=data['size'],
			pos_x=center.x(),
			pos_y=center.y(),
			delay=data['delay'],
			enabled=data['enabled'],
			point_type=data['type'],
			shortcut=data['shortcut'],
			order_index=next_order,
		)
		new_point_data = {
			'id': new_id,
			'name': data['name'],
			'icon': data['icon'],
			'icon_style': data['icon_style'],
			'color': data['color'],
			'size': data['size'],
			'pos_x': center.x(),
			'pos_y': center.y(),
			'delay': data['delay'],
			'enabled': data['enabled'],
			'type': data['type'],
			'shortcut': data['shortcut'],
			'order_index': next_order,
		}
		self._load_points_from_db()

	def on_edit_point(self, point_data: dict):
		dlg = AddEditPointDialog(point_data=point_data, parent=self)
		if dlg.exec() != QDialog.Accepted:
			return
		data = dlg.get_data()
		self.db.update_prompt_injector_point(
			point_id=point_data['id'],
			name=data['name'],
			icon=data['icon'],
			icon_style=data['icon_style'],
			color=data['color'],
			size=data['size'],
			delay=data['delay'],
			enabled=data['enabled'],
			point_type=data['type'],
			shortcut=data['shortcut'],
			order_index=point_data.get('order_index', 0),
		)
		pw = self._point_widgets.get(point_data['id'])
		if pw:
			pw.update_appearance(data['color'], data['icon'], data['icon_style'], data['size'])
			if data['enabled']:
				pw.show()
				pw.raise_()
			else:
				pw.hide()
		self._load_points_from_db()

	def on_delete_point(self, point_data_or_list):
		if isinstance(point_data_or_list, list):
			points_to_delete = point_data_or_list
		else:
			points_to_delete = [point_data_or_list]
		if len(points_to_delete) == 1:
			msg = f"Delete point '{points_to_delete[0].get('name', '')}'?"
		else:
			msg = f"Delete {len(points_to_delete)} selected points?"
		reply = QMessageBox.question(self, "Delete Point", msg, QMessageBox.Yes | QMessageBox.No)
		if reply != QMessageBox.Yes:
			return
		for pd in points_to_delete:
			pid = pd['id']
			self.db.delete_prompt_injector_point(pid)
			pw = self._point_widgets.pop(pid, None)
			if pw:
				pw.close()
		self._load_points_from_db()

	def on_clear_points(self):
		all_points = self.db.get_all_prompt_injector_points()
		if not all_points:
			QMessageBox.information(self, "No Points", "There are no points to clear.")
			return
		msg = f"Clear all {len(all_points)} points? This action cannot be undone."
		reply = QMessageBox.question(self, "Clear All Points", msg, QMessageBox.Yes | QMessageBox.No)
		if reply != QMessageBox.Yes:
			return
		for pd in all_points:
			pid = pd['id']
			self.db.delete_prompt_injector_point(pid)
			pw = self._point_widgets.pop(pid, None)
			if pw:
				pw.close()
		self._load_points_from_db()

	def on_reset_points(self):
		resp = QMessageBox.question(
			self, "Reset Points",
			"Resetting all point markers will move them back to screen center.\nThis action cannot be undone.\nContinue?",
			QMessageBox.Yes | QMessageBox.No
		)
		if resp != QMessageBox.Yes:
			return
		screen = QGuiApplication.primaryScreen().availableGeometry()
		center = screen.center()
		all_points = self.db.get_all_prompt_injector_points()
		count = len(all_points)
		if count == 0:
			return
		# determine grid size: cols x rows
		cols = int(math.ceil(math.sqrt(count)))
		rows = int(math.ceil(count / cols))
		spacing = 50
		for idx, pt in enumerate(all_points):
			row = idx // cols
			col = idx % cols
			# center grid around screen center
			cx = center.x() + (col - (cols - 1) / 2) * spacing
			cy = center.y() + (row - (rows - 1) / 2) * spacing
			pw = self._point_widgets.get(pt['id'])
			if pw:
				half = pw.width() // 2
				pw.move(QPoint(int(cx - half), int(cy - half)))
			self.db.update_prompt_injector_point_position(pt['id'], int(cx), int(cy))

	def _get_enabled_points(self):
		try:
			return [p for p in self.db.get_all_prompt_injector_points() if p.get('enabled', True)]
		except Exception as e:
			print(f"Failed to load enabled points: {e}")
			return []

	# ───── Automation ────────────────────────────────────────────────────────

	def on_run_automation(self):
		enabled_pts = self._get_enabled_points()
		if not enabled_pts:
			QMessageBox.warning(self, "No Points",
				"No enabled points configured.\nAdd and enable at least one point before running.")
			return
		with self._queue_lock:
			current_queue = list(self._loaded_paste_texts) if self._loaded_paste_texts else []
		if not current_queue:
			QMessageBox.warning(self, "No Data",
				"No records to process. Load a CSV/TXT or prompt first.")
			return

		self.progress_bar.setMaximum(len(current_queue))
		self.progress_bar.setValue(0)
		self.progress_bar.setFormat(f"0 / {len(current_queue)}")
		self._set_run_mode(True)
		self.btn_pause.setEnabled(True)
		self.btn_stop.setEnabled(True)
		self.btn_pause.setText("Pause")
		self._current_done = 0
		with self._queue_lock:
			self._total = len(self._loaded_paste_texts) if self._loaded_paste_texts else 0
		self._run_start_time = time.time()
		self._pause_accum = 0.0
		self._pause_start = None
		self._stats_timer.start()
		self._update_stats(0, self._total)

		if USE_QTIMER_MODE:
			self._run_points = enabled_pts
			self._prompt_index = 0
			self._pt_idx = 0
			self._automation_running = True
			self._automation_paused = False
			self._state = "INIT_DELAY"
			self._wait_start = 0
			self._wait_dur = 0
			self._automation_timer.start(50)
		else:
			self._stop_event = threading.Event()
			self._pause_event = threading.Event()
			self._clipboard_set_event = threading.Event()
			self._last_set_clipboard = None
			rand_delay = float(self.rand_spin.value())
			self._worker_thread = threading.Thread(
				target=self._run_sequence,
				args=(enabled_pts, rand_delay),
				daemon=True
			)
			self._worker_thread.start()

	def _automation_tick(self):
		if not self._automation_running:
			self._automation_timer.stop()
			return
		if self._automation_paused:
			self._set_delay_text("Paused")
			return

		if self._prompt_index >= self._total:
			self.automationFinished.emit()
			return

		if self._state == "INIT_DELAY":
			if self._pt_idx >= len(self._run_points):
				self._prompt_index += 1
				self._pt_idx = 0
				self._update_progress_qtimer()
				if self._prompt_index >= self._total:
					self.automationFinished.emit()
				return
			pt = self._run_points[self._pt_idx]
			base = float(pt.get('delay', 0))
			rnd = random.uniform(0, float(self.rand_spin.value())) if self.rand_spin.value() > 0 else 0
			self._wait_dur = 0 if pt.get('type') == 'monitor' else base + rnd
			self._wait_start = time.time()
			self._state = "WAITING"

		elif self._state == "WAITING":
			rem = self._wait_dur - (time.time() - self._wait_start)
			if rem <= 0:
				self._set_delay_text("")
				pt = self._run_points[self._pt_idx]
				self._state = "MONITOR_INIT" if pt.get('type') == 'monitor' else "EXECUTE"
			else:
				self._set_delay_text(f"Wait: {int(rem) + 1}s")
				self.countdownUpdated.emit(rem)

		elif self._state == "MONITOR_INIT":
			try:
				import pyautogui
				pt = self._run_points[self._pt_idx]
				x, y = self._get_live_pos(pt)
				shot = pyautogui.screenshot(region=(x, y, 1, 1))
				self._monitor_init_color = shot.getpixel((0, 0))
				self._monitor_timeout = float(pt.get('delay', 10.0))
				self._monitor_start = time.time()
				self._state = "MONITOR_WAIT"
			except Exception:
				self._state = "NEXT_POINT"

		elif self._state == "MONITOR_WAIT":
			pt = self._run_points[self._pt_idx]
			elapsed = time.time() - self._monitor_start
			remaining = self._monitor_timeout - elapsed
			if remaining <= 0:
				self._state = "NEXT_POINT"
				return
			self._set_delay_text(f"Monitoring: {int(remaining) + 1}s")
			try:
				import pyautogui
				x, y = self._get_live_pos(pt)
				shot = pyautogui.screenshot(region=(x, y, 1, 1))
				if shot.getpixel((0, 0)) != self._monitor_init_color:
					self._state = "NEXT_POINT"
			except Exception:
				self._state = "NEXT_POINT"

		elif self._state == "EXECUTE":
			import pyautogui
			pt = self._run_points[self._pt_idx]
			x, y = self._get_live_pos(pt)
			pt_type = pt.get('type', 'click')
			if pt_type == 'paste':
				pyautogui.moveTo(x, y, duration=0.2)
				pyautogui.click()
				mod_key = 'command' if sys.platform == 'darwin' else 'ctrl'
				QApplication.processEvents()
				time.sleep(0.5)
				pyautogui.hotkey(mod_key, 'a')
				time.sleep(0.5)
				with self._queue_lock:
					txt = self._loaded_paste_texts[self._prompt_index]
				QApplication.clipboard().setText(str(txt))
				time.sleep(0.5)
				pyautogui.hotkey(mod_key, 'v')
			elif pt_type == 'key_action':
				pyautogui.moveTo(x, y, duration=0.1)
				self._execute_shortcut(pt.get('shortcut') or '')
			elif pt_type == 'move':
				pyautogui.moveTo(x, y, duration=0.2)
			elif pt_type == 'click':
				pyautogui.moveTo(x, y, duration=0.2)
				pyautogui.click()
			self._state = "NEXT_POINT"

		elif self._state == "NEXT_POINT":
			self._pt_idx += 1
			self._state = "INIT_DELAY"

	def _get_live_pos(self, pt_data: dict):
		pid = pt_data.get('id')
		pw = self._point_widgets.get(pid)
		if pw:
			c = pw.frameGeometry().center()
			return c.x(), c.y()
		return pt_data.get('pos_x', 0), pt_data.get('pos_y', 0)

	def _execute_shortcut(self, shortcut: str):
		if not shortcut:
			return
		try:
			import pyautogui
			parts = [k.strip().lower() for k in shortcut.split('+') if k.strip()]
			if len(parts) == 1:
				pyautogui.press(parts[0])
			else:
				pyautogui.hotkey(*parts)
		except Exception as e:
			print(f"Shortcut execution error: {e}")

	def _update_progress_qtimer(self):
		self.progress_bar.setValue(self._prompt_index)
		self.progress_bar.setFormat(f"{self._prompt_index} / {self._total}")
		with self._queue_lock:
			self._current_done = self._prompt_index
			current_total = len(self._loaded_paste_texts) if self._loaded_paste_texts else 0
			self._total = current_total
		self.progressUpdated.emit(self._prompt_index, current_total)

	def _run_sequence(self, points, rand_delay):
		import pyautogui
		pyautogui.FAILSAFE = True
		mod_key = 'command' if sys.platform == 'darwin' else 'ctrl'
		idx = 0
		while True:
			with self._queue_lock:
				total = len(self._loaded_paste_texts) if self._loaded_paste_texts else 0
				files = list(self._loaded_files)
				cumulative = []
				running = 0
				for f in files:
					running += int(f.get('count', 0))
					cumulative.append(running)
			if idx >= total:
				waited = 0
				while idx >= total and not (self._stop_event and self._stop_event.is_set()) and waited < 20:
					time.sleep(0.05)
					waited += 1
					with self._queue_lock:
						total = len(self._loaded_paste_texts) if self._loaded_paste_texts else 0
				if idx >= total:
					break
			if idx >= total:
				break

			ui_idx = idx + 1
			with self._queue_lock:
				text_to_paste = self._loaded_paste_texts[idx]

			if files and cumulative:
				file_idx = 0
				for i, cum in enumerate(cumulative):
					if ui_idx <= cum:
						file_idx = i
						break
				if file_idx < len(files):
					file_pos = ui_idx - (cumulative[file_idx - 1] if file_idx > 0 else 0)
					file_count = int(files[file_idx].get('count', 0))
					file_type = files[file_idx].get('type', '')
					self.currentFileUpdated.emit(file_idx + 1, len(files), file_type, file_pos, file_count)

			pasted = False
			for pt in points:
				if self._stop_event and self._stop_event.is_set():
					return
				pt_type = pt.get('type', 'click')
				base = float(pt.get('delay', 0))
				rnd = random.uniform(0, rand_delay) if rand_delay > 0 else 0
				wait_dur = base + rnd

				if pt_type == 'monitor':
					self._wait_monitor(pt, base)
				else:
					remaining = wait_dur
					step = 0.05
					while remaining > 0:
						if self._stop_event and self._stop_event.is_set():
							return
						while self._pause_event and self._pause_event.is_set():
							self.countdownUpdated.emit(remaining)
							time.sleep(0.1)
							if self._stop_event and self._stop_event.is_set():
								return
						self.countdownUpdated.emit(remaining)
						time.sleep(min(step, remaining))
						remaining -= step
					self.countdownUpdated.emit(0.0)

				if self._stop_event and self._stop_event.is_set():
					return

				x, y = self._get_live_pos(pt)

				if pt_type == 'paste':
					pyautogui.moveTo(x, y, duration=0.2)
					pyautogui.click()
					time.sleep(0.5)
					pyautogui.hotkey(mod_key, 'a')
					time.sleep(0.5)
					self._clipboard_set_event.clear()
					self._last_set_clipboard = None
					self.setClipboardRequested.emit(text_to_paste)
					ok = self._clipboard_set_event.wait(2.0)
					if not ok or (self._last_set_clipboard is None) or \
					   (str(self._last_set_clipboard).strip() != str(text_to_paste).strip()):
						with self._queue_lock:
							current_total = len(self._loaded_paste_texts)
						self.progressUpdated.emit(ui_idx, current_total)
						idx += 1
						break
					time.sleep(0.5)
					pyautogui.hotkey(mod_key, 'v')
					pasted = True
				elif pt_type == 'key_action':
					pyautogui.moveTo(x, y, duration=0.1)
					self._execute_shortcut(pt.get('shortcut') or '')
				elif pt_type == 'move':
					pyautogui.moveTo(x, y, duration=0.2)
				elif pt_type == 'click':
					pyautogui.moveTo(x, y, duration=0.2)
					pyautogui.click()

			if pasted and self._loaded_from_db:
				self._copied_count += 1
				self.csv_label.setText(
					f"Prompt DB: {len(self._loaded_paste_texts)} records (copied: {self._copied_count})"
				)
				try:
					if self.db and len(self._loaded_prompt_ids) >= ui_idx:
						self.db.add_prompt_status(self._loaded_prompt_ids[ui_idx - 1], status='copied')
				except Exception:
					pass

			with self._queue_lock:
				self._current_done = ui_idx
				self._total = len(self._loaded_paste_texts)
				current_total = self._total
			self.progressUpdated.emit(ui_idx, current_total)
			idx += 1
		self.automationFinished.emit()

	def _wait_monitor(self, pt: dict, timeout: float):
		try:
			import pyautogui
			x, y = self._get_live_pos(pt)
			shot = pyautogui.screenshot(region=(x, y, 1, 1))
			init_color = shot.getpixel((0, 0))
			start = time.time()
			while time.time() - start < timeout:
				if self._stop_event and self._stop_event.is_set():
					return
				while self._pause_event and self._pause_event.is_set():
					time.sleep(0.1)
					if self._stop_event and self._stop_event.is_set():
						return
				cur = pyautogui.screenshot(region=(x, y, 1, 1))
				if cur.getpixel((0, 0)) != init_color:
					return
				time.sleep(0.1)
		except Exception as e:
			print(f"Monitor wait error: {e}")

	def _set_run_mode(self, enable: bool):
		for pw in self._point_widgets.values():
			pw.set_click_through(enable)
		self.btn_action.setEnabled(not enable)
		self.btn_reset.setEnabled(not enable)
		self.btn_add_point.setEnabled(not enable)
		self.btn_action.setText("Running..." if enable else "Run Action")
		self._set_status("Running automation..." if enable else "Ready")

	@Slot()
	def _on_automation_finished(self):
		self._set_run_mode(False)
		self.btn_pause.setEnabled(False)
		self.btn_stop.setEnabled(False)
		if USE_QTIMER_MODE:
			self._automation_running = False
			self._automation_timer.stop()
		else:
			if self._stop_event:
				self._stop_event.set()
			if self._pause_event:
				self._pause_event.clear()
			self._last_set_clipboard = None
		self._set_delay_text("")
		self.progress_bar.setValue(self.progress_bar.maximum())
		self.progress_bar.setFormat(f"{self.progress_bar.maximum()} / {self.progress_bar.maximum()}")
		self._stats_timer.stop()
		self._update_stats(self.progress_bar.maximum(), self.progress_bar.maximum())
		if self.shutdown_chk.isChecked():
			self._execute_shutdown()
		else:
			QMessageBox.information(self, "Done", "Sequence completed.")

	def _execute_shutdown(self):
		try:
			if sys.platform == "win32":
				os.system("shutdown /s /t 60")
				QMessageBox.information(self, "Shutdown Scheduled",
					"Sequence completed. System will shut down in 60 seconds.\n"
					"Run 'shutdown /a' in Command Prompt to cancel.")
			elif sys.platform == "darwin":
				os.system("osascript -e 'tell application \"System Events\" to shut down'")
				QMessageBox.information(self, "Shutdown Initiated",
					"Sequence completed. System is shutting down.")
			else:
				os.system("systemctl poweroff")
				QMessageBox.information(self, "Shutdown Initiated",
					"Sequence completed. System is shutting down.")
		except Exception as e:
			QMessageBox.critical(self, "Shutdown Error", f"Failed to initiate shutdown: {e}")

	@Slot(int, int)
	def _on_progress_updated(self, done: int, total: int):
		self.progress_bar.setMaximum(total)
		self.progress_bar.setValue(done)
		self.progress_bar.setFormat(f"{done} / {total}")
		self._current_done = done
		self._total = total
		self._update_stats(done, total)

	def on_pause_toggle(self):
		if USE_QTIMER_MODE:
			if not self._automation_running:
				return
			self._automation_paused = not self._automation_paused
			if self._automation_paused:
				self._pause_start = time.time()
				self.btn_pause.setText("Resume")
				for pw in self._point_widgets.values():
					pw.set_click_through(False)
			else:
				if self._pause_start:
					self._pause_accum += time.time() - self._pause_start
					self._pause_start = None
				self.btn_pause.setText("Pause")
				for pw in self._point_widgets.values():
					pw.set_click_through(True)
		else:
			if not self._pause_event:
				return
			if self._pause_event.is_set():
				self._pause_event.clear()
				if self._pause_start:
					self._pause_accum += time.time() - self._pause_start
					self._pause_start = None
				self.btn_pause.setText("Pause")
				for pw in self._point_widgets.values():
					pw.set_click_through(True)
			else:
				self._pause_event.set()
				self._pause_start = time.time()
				self.btn_pause.setText("Resume")
				for pw in self._point_widgets.values():
					pw.set_click_through(False)
		self._update_stats(getattr(self, '_current_done', 0), getattr(self, '_total', 0))

	def on_stop(self):
		if USE_QTIMER_MODE:
			self._automation_running = False
			self._automation_timer.stop()
			self._automation_paused = False
		else:
			if self._stop_event:
				self._stop_event.set()
			if self._pause_event:
				self._pause_event.clear()
		self._set_run_mode(False)
		self.btn_pause.setEnabled(False)
		self.btn_stop.setEnabled(False)
		self.btn_pause.setText("Pause")
		self._stats_timer.stop()
		self._update_stats(getattr(self, '_current_done', 0), getattr(self, '_total', 0))
		self._set_delay_text("")
		self._set_status("Stopped")

	def show_help_dialog(self):
		html = (
			"<div>"
			"<h3>Prompt Injector v2 &mdash; How to Use</h3>"
			"<p><b>1. Add Points</b><br>"
			"Click <i>Add New Point</i> at the top. Set name, type, icon, color, size, and delay. "
			"For <b>key_action</b> type, also enter the shortcut (e.g. <code>ctrl+enter</code>).</p>"
			"<p><b>2. Position Points</b><br>"
			"After creating a point, its marker appears on screen. Drag it to the exact target location "
			"in your other application. While dragging, the icon changes to a crosshair to help you aim. "
			"Positions are saved to the database automatically.</p>"
			"<p><b>3. Point Types</b></p>"
			"<ul>"
			"<li><b>paste</b> &mdash; Moves to the point, clicks, selects all (Ctrl+A), then pastes the current prompt (Ctrl+V).</li>"
			"<li><b>key_action</b> &mdash; Moves to the point, then fires the stored keyboard shortcut.</li>"
			"<li><b>move</b> &mdash; Moves the cursor to the point without clicking.</li>"
			"<li><b>click</b> &mdash; Moves to the point and left-clicks.</li>"
			"<li><b>monitor</b> &mdash; Waits until the pixel color at this location changes. "
			"The <i>Delay</i> field sets the maximum wait; the sequence continues regardless after timeout.</li>"
			"</ul>"
			"<p><b>4. Order</b><br>"
			"Points execute top-to-bottom for every loaded prompt.</p>"
			"<p><b>5. Load Data</b><br>"
			"<i>Load CSV/TXT</i>: load prompt files (TXT: one prompt per line).<br>"
			"<i>Load Prompt</i>: pull prompts from the Image Tea database.</p>"
			"<p><b>6. Run / Control</b><br>"
			"<i>Run Action</i> starts automation. <i>Pause</i> (or press <b>Esc</b>) pauses. "
			"<i>Stop</i> stops immediately. <i>Reset Points</i> centers all markers.</p>"
			"<p><b>7. Random Extra Delay</b><br>"
			"Adds a random extra wait on top of each point's base delay for more natural timing.</p>"
			"</div>"
		)
		QMessageBox.information(self, "Prompt Injector v2 \u2014 Help", html)

	@Slot(float)
	def _on_countdown_updated(self, remaining: float):
		if remaining > 0:
			self._set_delay_text(f"Waiting: {int(round(remaining))} s")
		else:
			self._set_delay_text("")

	@Slot(int, int, str, int, int)
	def _on_current_file_updated(self, file_idx, total_files, file_type, file_pos, file_count):
		total = len(self._loaded_paste_texts) if self._loaded_paste_texts else 0
		if total == 0:
			return
		file_name = ""
		if 0 < file_idx <= len(self._loaded_files):
			fp = self._loaded_files[file_idx - 1].get('path', '')
			if fp:
				file_name = os.path.basename(fp)
				if len(file_name) > 35:
					file_name = file_name[:20] + "..." + file_name[-10:]
		if file_name:
			self.csv_label.setText(
				f"Loaded {total} prompts ({file_idx}/{total_files} {file_type}: {file_pos}/{file_count} - {file_name})"
			)
		else:
			self.csv_label.setText(
				f"Loaded {total} prompts ({file_idx}/{total_files} {file_type}: {file_pos}/{file_count})"
			)

	def _set_delay_text(self, text: str):
		self.delay_label.setText(text)

	def _set_status(self, msg: str):
		self.status_bar.showMessage(msg)

	def _on_rows_moved(self, parent, start, end, destination, row):
		ordered_ids = []
		for i in range(self.points_list.count()):
			list_item = self.points_list.item(i)
			if list_item:
				if list_item.data(Qt.UserRole + 1) == '_add_button':
					continue
				data = list_item.data(Qt.UserRole)
				if data and data.get('id'):
					ordered_ids.append(data['id'])
		if ordered_ids:
			try:
				self.db.reorder_prompt_injector_points(ordered_ids)
				self._set_status("Point order saved.")
			except Exception as e:
				print(f"Failed to save point order to DB: {e}")

	def _on_point_context_menu(self, pos):
		list_item = self.points_list.itemAt(pos)
		if not list_item:
			return
		if list_item.data(Qt.UserRole + 1) == '_add_button':
			return
		point_data = list_item.data(Qt.UserRole)
		if not point_data:
			return

		selected = self._get_selected_point_data_list()
		selected_ids = {p['id'] for p in selected}
		if point_data['id'] not in selected_ids:
			selected = [point_data]
		is_multi = len(selected) > 1
		count_label = f" ({len(selected)})" if is_multi else ""

		menu = QMenu(self)
		if not is_multi:
			act_edit = menu.addAction(qta.icon('fa6s.pen'), "Edit Point")
			menu.addSeparator()
			act_above = menu.addAction(qta.icon('fa6s.plus'), "Add Point Above")
			act_below = menu.addAction(qta.icon('fa6s.plus'), "Add Point Below")
		act_dup = menu.addAction(qta.icon('fa6s.clone'), f"Duplicate{count_label}")
		menu.addSeparator()
		act_top = menu.addAction(qta.icon('fa6s.angles-up'), "To Top")
		act_up = menu.addAction(qta.icon('fa6s.arrow-up'), "Move Up")
		act_down = menu.addAction(qta.icon('fa6s.arrow-down'), "Move Down")
		act_bottom = menu.addAction(qta.icon('fa6s.angles-down'), "To Bottom")
		menu.addSeparator()
		act_del = menu.addAction(qta.icon('fa6s.trash'), f"Delete{count_label}")
		act_clear = menu.addAction(qta.icon('fa6s.broom'), "Remove All Points")

		all_pts = self.db.get_all_prompt_injector_points()
		total = len(all_pts)
		orders = [p.get('order_index', 0) for p in selected]
		min_order = min(orders)
		max_order = max(orders)
		act_top.setEnabled(min_order > 0)
		act_up.setEnabled(min_order > 0)
		act_down.setEnabled(max_order < total - 1)
		act_bottom.setEnabled(max_order < total - 1)

		if not is_multi:
			act_edit.triggered.connect(lambda: self.on_edit_point(point_data))
			act_above.triggered.connect(lambda: self._ctx_add_adjacent(point_data, above=True))
			act_below.triggered.connect(lambda: self._ctx_add_adjacent(point_data, above=False))
		act_dup.triggered.connect(lambda: self._ctx_duplicate(selected))
		act_top.triggered.connect(lambda: self._ctx_move_to_top(selected))
		act_up.triggered.connect(lambda: self._ctx_move_up(selected))
		act_down.triggered.connect(lambda: self._ctx_move_down(selected))
		act_bottom.triggered.connect(lambda: self._ctx_move_to_bottom(selected))
		act_del.triggered.connect(lambda: self.on_delete_point(selected))
		act_clear.triggered.connect(self._ctx_remove_all)

		menu.exec(self.points_list.viewport().mapToGlobal(pos))

	def _ctx_add_adjacent(self, ref_point: dict, above: bool):
		dlg = AddEditPointDialog(parent=self)
		if dlg.exec() != QDialog.Accepted:
			return
		data = dlg.get_data()
		all_pts = self.db.get_all_prompt_injector_points()
		ref_order = ref_point.get('order_index', 0)
		insert_at = ref_order if above else ref_order + 1
		for pt in all_pts:
			if pt['order_index'] >= insert_at:
				self.db.update_prompt_injector_point(
					point_id=pt['id'], name=pt['name'], icon=pt['icon'],
					icon_style=pt['icon_style'], color=pt['color'], size=pt['size'],
					delay=pt['delay'], enabled=pt['enabled'], point_type=pt['type'],
					shortcut=pt['shortcut'], order_index=pt['order_index'] + 1,
				)
		screen = QGuiApplication.primaryScreen().availableGeometry().center()
		self.db.add_prompt_injector_point(
			name=data['name'], icon=data['icon'], icon_style=data['icon_style'],
			color=data['color'], size=data['size'], pos_x=screen.x(), pos_y=screen.y(),
			delay=data['delay'], enabled=data['enabled'], point_type=data['type'],
			shortcut=data['shortcut'], order_index=insert_at,
		)
		self._load_points_from_db()

	def _ctx_duplicate(self, points_input):
		if isinstance(points_input, dict):
			points_input = [points_input]
		points = sorted(points_input, key=lambda p: p.get('order_index', 0))
		all_pts = self.db.get_all_prompt_injector_points()
		insert_after = max(p.get('order_index', 0) for p in points)
		shift = len(points)
		for pt in all_pts:
			if pt['order_index'] > insert_after:
				self.db.update_prompt_injector_point(
					point_id=pt['id'], name=pt['name'], icon=pt['icon'],
					icon_style=pt['icon_style'], color=pt['color'], size=pt['size'],
					delay=pt['delay'], enabled=pt['enabled'], point_type=pt['type'],
					shortcut=pt['shortcut'], order_index=pt['order_index'] + shift,
				)
		for i, pd in enumerate(points):
			self.db.add_prompt_injector_point(
				name=f"Copy of {pd['name']}", icon=pd['icon'],
				icon_style=pd['icon_style'], color=pd['color'],
				size=pd['size'], pos_x=pd['pos_x'], pos_y=pd['pos_y'],
				delay=pd['delay'], enabled=pd['enabled'],
				point_type=pd['type'], shortcut=pd['shortcut'],
				order_index=insert_after + 1 + i,
			)
		self._load_points_from_db()

	def _ctx_move_to_top(self, points_input):
		if isinstance(points_input, dict):
			points_input = [points_input]
		selected_ids = {p['id'] for p in points_input}
		all_pts = self.db.get_all_prompt_injector_points()
		selected_sorted = sorted(points_input, key=lambda p: p.get('order_index', 0))
		others = sorted([p for p in all_pts if p['id'] not in selected_ids], key=lambda p: p.get('order_index', 0))
		new_order = selected_sorted + others
		new_orders = [(p['id'], i) for i, p in enumerate(new_order)]
		self._apply_order(new_orders)

	def _ctx_move_up(self, points_input):
		if isinstance(points_input, dict):
			points_input = [points_input]
		selected_ids = {p['id'] for p in points_input}
		all_pts = sorted(self.db.get_all_prompt_injector_points(), key=lambda p: p.get('order_index', 0))
		ids_ordered = [p['id'] for p in all_pts]
		if ids_ordered[0] in selected_ids:
			return
		for i in range(1, len(ids_ordered)):
			if ids_ordered[i] in selected_ids and ids_ordered[i - 1] not in selected_ids:
				ids_ordered[i - 1], ids_ordered[i] = ids_ordered[i], ids_ordered[i - 1]
		new_orders = [(pid, idx) for idx, pid in enumerate(ids_ordered)]
		self._apply_order(new_orders)

	def _ctx_move_down(self, points_input):
		if isinstance(points_input, dict):
			points_input = [points_input]
		selected_ids = {p['id'] for p in points_input}
		all_pts = sorted(self.db.get_all_prompt_injector_points(), key=lambda p: p.get('order_index', 0))
		ids_ordered = [p['id'] for p in all_pts]
		if ids_ordered[-1] in selected_ids:
			return
		for i in range(len(ids_ordered) - 2, -1, -1):
			if ids_ordered[i] in selected_ids and ids_ordered[i + 1] not in selected_ids:
				ids_ordered[i], ids_ordered[i + 1] = ids_ordered[i + 1], ids_ordered[i]
		new_orders = [(pid, idx) for idx, pid in enumerate(ids_ordered)]
		self._apply_order(new_orders)

	def _ctx_move_to_bottom(self, points_input):
		if isinstance(points_input, dict):
			points_input = [points_input]
		selected_ids = {p['id'] for p in points_input}
		all_pts = self.db.get_all_prompt_injector_points()
		selected_sorted = sorted(points_input, key=lambda p: p.get('order_index', 0))
		others = sorted([p for p in all_pts if p['id'] not in selected_ids], key=lambda p: p.get('order_index', 0))
		new_order = others + selected_sorted
		new_orders = [(p['id'], i) for i, p in enumerate(new_order)]
		self._apply_order(new_orders)

	def _apply_order(self, new_orders: list):
		for pid, new_idx in new_orders:
			all_pts = self.db.get_all_prompt_injector_points()
			pt = next((p for p in all_pts if p['id'] == pid), None)
			if pt:
				self.db.update_prompt_injector_point(
					point_id=pt['id'], name=pt['name'], icon=pt['icon'],
					icon_style=pt['icon_style'], color=pt['color'], size=pt['size'],
					delay=pt['delay'], enabled=pt['enabled'], point_type=pt['type'],
					shortcut=pt['shortcut'], order_index=new_idx,
				)
		self._load_points_from_db()

	def _ctx_remove_all(self):
		reply = QMessageBox.question(
			self, "Remove All Points",
			"Remove all points? This cannot be undone.",
			QMessageBox.Yes | QMessageBox.No
		)
		if reply != QMessageBox.Yes:
			return
		all_pts = self.db.get_all_prompt_injector_points()
		for pt in all_pts:
			pw = self._point_widgets.pop(pt['id'], None)
			if pw:
				pw.close()
			self.db.delete_prompt_injector_point(pt['id'])
		self._load_points_from_db()

	def on_export_preset(self):
		pts = self.db.get_all_prompt_injector_points()
		if not pts:
			QMessageBox.information(self, "Export Preset", "No points to export.")
			return
		stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
		default = f"Prompt_Injector_v2_Preset_{stamp}.json"
		home = os.path.expanduser("~")
		initial = os.path.join(home, default)
		path, _ = QFileDialog.getSaveFileName(self, "Export Points Preset", initial, "JSON Files (*.json)")
		if not path:
			return
		export_data = {"version": 1, "points": []}
		for pt in pts:
			export_data["points"].append({
				"name": pt["name"],
				"type": pt["type"],
				"icon": pt["icon"],
				"icon_style": pt["icon_style"],
				"color": pt["color"],
				"size": pt["size"],
				"pos_x": pt["pos_x"],
				"pos_y": pt["pos_y"],
				"delay": pt["delay"],
				"enabled": pt["enabled"],
				"shortcut": pt.get("shortcut"),
				"order_index": pt["order_index"],
			})
		try:
			with open(path, "w", encoding="utf-8") as f:
				json.dump(export_data, f, indent=2)
			self._set_status(f"Preset exported: {os.path.basename(path)}")
		except Exception as e:
			QMessageBox.critical(self, "Export Failed", str(e))

	def on_import_preset(self):
		home = os.path.expanduser("~")
		path, _ = QFileDialog.getOpenFileName(self, "Import Points Preset", home, "JSON Files (*.json)")
		if not path:
			return
		try:
			with open(path, "r", encoding="utf-8") as f:
				data = json.load(f)
		except Exception as e:
			QMessageBox.critical(self, "Import Failed", f"Cannot read file:\n{e}")
			return
		if not isinstance(data, dict) or "points" not in data:
			QMessageBox.critical(self, "Import Failed", "Invalid preset file format.")
			return
		reply = QMessageBox.question(
			self, "Import Preset",
			"This will replace all current points with the imported preset.\nContinue?",
			QMessageBox.Yes | QMessageBox.No
		)
		if reply != QMessageBox.Yes:
			return
		all_pts = self.db.get_all_prompt_injector_points()
		for pw in list(self._point_widgets.values()):
			pw.close()
		self._point_widgets.clear()
		for pt in all_pts:
			self.db.delete_prompt_injector_point(pt["id"])
		for i, pt in enumerate(data["points"]):
			self.db.add_prompt_injector_point(
				name=pt.get("name", "Point"),
				icon=pt.get("icon", "location-crosshairs"),
				icon_style=pt.get("icon_style", "solid"),
				color=pt.get("color", "#ff4d4d"),
				size=pt.get("size", 32),
				pos_x=pt.get("pos_x", 0),
				pos_y=pt.get("pos_y", 0),
				delay=pt.get("delay", 1.0),
				enabled=pt.get("enabled", True),
				point_type=pt.get("type", "click"),
				shortcut=pt.get("shortcut"),
				order_index=pt.get("order_index", i),
			)
		self._load_points_from_db()
		self._set_status(f"Preset imported: {len(data['points'])} points loaded.")

	def _on_point_double_clicked(self, item):
		if not item:
			return
		if item.data(Qt.UserRole + 1) == '_add_button':
			return
		data = item.data(Qt.UserRole)
		if data:
			self.on_edit_point(data)

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
			return f"{h}:{m:02d}:{s:02d}"
		return f"{m}:{s:02d}"

	def _update_stats(self, done, total):
		if total <= 0:
			self.stats_eta_lbl.setText("ETA: -")
			self.stats_remaining_lbl.setText("Remaining: -")
			self.stats_elapsed_lbl.setText("Elapsed: -")
			self.stats_progress_lbl.setText("Progress: 0/0")
			self.stats_speed_lbl.setText("Speed: 0.00/m")
			return
		now = time.time()
		start = getattr(self, '_run_start_time', None)
		elapsed = 0.0
		if start:
			elapsed = now - start - getattr(self, '_pause_accum', 0.0)
			if getattr(self, '_pause_start', None):
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
		paused = " (paused)" if getattr(self, '_pause_event', None) and self._pause_event.is_set() else ""
		self.stats_eta_lbl.setText(f"ETA: {eta_str}")
		self.stats_remaining_lbl.setText(f"Remaining: {self._format_duration(remaining_time)}")
		self.stats_elapsed_lbl.setText(f"Elapsed: {self._format_duration(elapsed)}{paused}")
		self.stats_progress_lbl.setText(f"Progress: {done}/{total} ({percent}%)")
		self.stats_speed_lbl.setText(f"Speed: {speed:.2f}/m")

	def on_load_csv(self):
		start_dir = getattr(self, '_last_csv_dir', None)
		if not start_dir or not os.path.isdir(start_dir):
			start_dir = os.path.expanduser("~")
		paths, _ = QFileDialog.getOpenFileNames(
			self, "Select CSV/TXT files", start_dir,
			"CSV or TXT Files (*.csv *.txt);;All Files (*)"
		)
		if not paths:
			return
		try:
			self._last_csv_dir = os.path.dirname(paths[0])
		except Exception:
			pass
		aggregated = []
		new_files = []
		for path in paths:
			if not path:
				continue
			ok, ftype, texts = self._process_file(path)
			if ok and texts:
				aggregated.extend(texts)
				new_files.append({"path": path, "type": ftype, "count": len(texts)})
			elif ok and not texts:
				QMessageBox.warning(self, "No Data", f"File {os.path.basename(path)} contains no records.")
			else:
				QMessageBox.warning(self, "Load Error", f"Could not load: {os.path.basename(path)}")
		if not aggregated:
			return
		if getattr(self, '_worker_thread', None) and getattr(self._worker_thread, 'is_alive', lambda: False)():
			with self._queue_lock:
				self._loaded_paste_texts = (self._loaded_paste_texts or []) + aggregated
				self._loaded_files.extend(new_files)
				self._total = len(self._loaded_paste_texts)
				self.progress_bar.setMaximum(self._total)
				self.progress_bar.setFormat(f"{self._current_done} / {self._total}")
				self._update_loaded_label()
			self._update_stats(getattr(self, '_current_done', 0), self._total)
		else:
			self._loaded_paste_texts = (self._loaded_paste_texts or []) + aggregated
			self._loaded_files.extend(new_files)
			self._update_loaded_label()
		self._loaded_from_db = False
		self._copied_count = 0
		self.save_settings()

	def on_load_prompt(self):
		if getattr(self, '_worker_thread', None) and getattr(self._worker_thread, 'is_alive', lambda: False)():
			QMessageBox.information(self, "Load Disabled",
				"Cannot load from database while automation is running.")
			return
		if not self.db:
			self.db = ImageTeaDB()
		prompts = prompt_injector_helper.load_prompts_from_db(self.db)
		if not prompts:
			QMessageBox.warning(self, "No Data", "No prompts found in database.")
			return
		self._loaded_prompt_ids = [p[0] for p in prompts]
		self._loaded_paste_texts = [p[1] for p in prompts]
		self._loaded_from_db = True
		self._copied_count = 0
		self.csv_label.setText(f"Prompt DB: {len(prompts)} records (copied: 0)")
		self.save_settings()

	def on_clear_data(self):
		self._loaded_paste_texts = None
		self._loaded_from_db = False
		self._loaded_prompt_ids = []
		self._copied_count = 0
		self._loaded_files = []
		self.csv_label.setText("CSV/Prompt: (none)")
		self.progress_bar.setMaximum(1)
		self.progress_bar.setValue(0)
		self.progress_bar.setFormat("0 / 0")
		self.save_settings()

	def dragEnterEvent(self, event):
		md = event.mimeData()
		if md and md.hasUrls():
			for url in md.urls():
				if url.isLocalFile() and os.path.splitext(url.toLocalFile())[1].lower() in (".csv", ".txt"):
					event.acceptProposedAction()
					return
		event.ignore()

	def dropEvent(self, event):
		urls = event.mimeData().urls()
		if not urls:
			return
		aggregated = []
		new_files = []
		loaded_any = False
		for url in urls:
			path = url.toLocalFile()
			if not path or not os.path.isfile(path):
				continue
			if os.path.splitext(path)[1].lower() not in ('.csv', '.txt'):
				continue
			ok, ftype, texts = self._process_file(path)
			if ok and texts:
				aggregated.extend(texts)
				new_files.append({"path": path, "type": ftype, "count": len(texts)})
				loaded_any = True
		if not loaded_any:
			QMessageBox.warning(self, "Drop Error", "No valid CSV/TXT files were dropped.")
			return
		self._loaded_paste_texts = (self._loaded_paste_texts or []) + aggregated
		self._loaded_files.extend(new_files)
		self._update_loaded_label()
		self._loaded_from_db = False
		self._copied_count = 0
		self.save_settings()
		event.acceptProposedAction()

	def _process_file(self, path):
		try:
			ext = os.path.splitext(path)[1].lower()
			if ext == '.csv':
				return True, 'csv', prompt_injector_helper.load_csv_texts(path)
			if ext == '.txt':
				return True, 'txt', prompt_injector_helper.load_text_texts(path)
			return False, None, None
		except Exception:
			return False, None, None

	def _update_loaded_label(self):
		total = len(self._loaded_paste_texts) if self._loaded_paste_texts else 0
		n = len(self._loaded_files)
		if n == 0:
			self.csv_label.setText("CSV/Prompt: (none)")
			return
		last = self._loaded_files[-1]
		name = os.path.basename(last.get('path', ''))
		if len(name) > 35:
			name = name[:20] + "..." + name[-10:]
		self.csv_label.setText(
			f"Loaded {total} prompts ({n} file(s) - {name})" if name
			else f"Loaded {total} prompts ({n} file(s))"
		)

	def _set_clipboard(self, text: str):
		QApplication.clipboard().setText(str(text))
		time.sleep(0.08)
		self._last_set_clipboard = str(text)
		self._clipboard_set_event.set()

	def settings_path(self):
		return os.path.join(BASE_PATH, "configs", "prompt_injector_settings.json")

	def save_settings(self):
		data = {
			"random_delay": float(self.rand_spin.value()),
			"loaded_files": list(self._loaded_files),
			"last_csv_dir": getattr(self, '_last_csv_dir', None),
		}
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
			return
		try:
			with open(path, encoding="utf-8") as fh:
				data = json.load(fh)
		except Exception:
			return
		rd = data.get("random_delay")
		if rd is not None:
			self.rand_spin.setValue(float(rd))
		loaded_files = data.get("loaded_files") or []
		self._last_csv_dir = data.get("last_csv_dir")
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
				self._loaded_paste_texts = aggregated
				self._loaded_from_db = False
				self._copied_count = 0
				self._update_loaded_label()

	def changeEvent(self, event):
		if event.type() == QEvent.WindowStateChange:
			if self.windowState() & Qt.WindowMinimized:
				for pw in self._point_widgets.values():
					pw.hide()
			else:
				QTimer.singleShot(50, self._restore_point_widgets)
		super().changeEvent(event)

	def _restore_point_widgets(self):
		all_pts = {p['id']: p for p in self.db.get_all_prompt_injector_points()}
		for pid, pw in self._point_widgets.items():
			pt = all_pts.get(pid)
			if pt and pt.get('enabled', True):
				pw.show()
				pw.raise_()

	def showEvent(self, event):
		super().showEvent(event)
		self._load_points_from_db()

	def closeEvent(self, event):
		self.save_settings()
		for pw in list(self._point_widgets.values()):
			pw.close()
		if getattr(self, '_pynput_listener', None):
			self._pynput_listener.stop()
		super().closeEvent(event)
