import os
import re
import csv
import io

from PySide6.QtWidgets import (
	QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
	QRadioButton, QButtonGroup, QCheckBox, QGroupBox,
	QProgressBar, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, QThread, Signal
import qtawesome as qta


class ExportSettingsDialog(QDialog):
	"""Compact dialog for configuring prompt export settings (CSV or TXT)."""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Export Settings")
		self.setModal(True)
		self.setFixedWidth(320)
		self.settings = None

		layout = QVBoxLayout(self)
		layout.setSpacing(8)
		layout.setContentsMargins(12, 12, 12, 12)

		# --- Format group ---
		fmt_group = QGroupBox("Format")
		fmt_layout = QHBoxLayout(fmt_group)
		fmt_layout.setSpacing(16)
		self._fmt_group = QButtonGroup(self)
		self.rb_csv = QRadioButton("CSV")
		self.rb_txt = QRadioButton("TXT")
		self.rb_csv.setChecked(True)
		self._fmt_group.addButton(self.rb_csv, 0)
		self._fmt_group.addButton(self.rb_txt, 1)
		fmt_layout.addWidget(self.rb_csv)
		fmt_layout.addWidget(self.rb_txt)
		layout.addWidget(fmt_group)

		# --- CSV options ---
		self._csv_group = QGroupBox("CSV Options")
		csv_layout = QVBoxLayout(self._csv_group)
		csv_layout.setSpacing(6)

		sep_row = QHBoxLayout()
		sep_row.addWidget(QLabel("Separator:"))
		self._sep_btn_group = QButtonGroup(self)
		self.rb_comma = QRadioButton("Comma  ,")
		self.rb_semicolon = QRadioButton("Semicolon  ;")
		self.rb_comma.setChecked(True)
		self._sep_btn_group.addButton(self.rb_comma, 0)
		self._sep_btn_group.addButton(self.rb_semicolon, 1)
		sep_row.addWidget(self.rb_comma)
		sep_row.addWidget(self.rb_semicolon)
		csv_layout.addLayout(sep_row)

		quote_row = QHBoxLayout()
		quote_row.addWidget(QLabel("Quote:"))
		self._quote_btn_group = QButtonGroup(self)
		self.rb_no_quote = QRadioButton("None")
		self.rb_single_quote = QRadioButton("Single '")
		self.rb_double_quote = QRadioButton('Double "')
		self.rb_no_quote.setChecked(True)
		self._quote_btn_group.addButton(self.rb_no_quote, 0)
		self._quote_btn_group.addButton(self.rb_single_quote, 1)
		self._quote_btn_group.addButton(self.rb_double_quote, 2)
		quote_row.addWidget(self.rb_no_quote)
		quote_row.addWidget(self.rb_single_quote)
		quote_row.addWidget(self.rb_double_quote)
		csv_layout.addLayout(quote_row)

		layout.addWidget(self._csv_group)

		# --- TXT options ---
		self._txt_group = QGroupBox("TXT Options")
		txt_layout = QVBoxLayout(self._txt_group)
		txt_layout.setSpacing(6)
		self.cb_numbering = QCheckBox("Add numbering (1. 2. 3. …)")
		self.cb_empty_line = QCheckBox("Empty line between prompts")
		txt_layout.addWidget(self.cb_numbering)
		txt_layout.addWidget(self.cb_empty_line)
		self._txt_group.setVisible(False)
		layout.addWidget(self._txt_group)

		# --- Buttons ---
		btn_row = QHBoxLayout()
		btn_row.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
		self.btn_cancel = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
		self.btn_export = QPushButton(qta.icon('fa6s.file-export'), " Export")
		self.btn_cancel.clicked.connect(self.reject)
		self.btn_export.clicked.connect(self._on_export)
		btn_row.addWidget(self.btn_cancel)
		btn_row.addWidget(self.btn_export)
		layout.addLayout(btn_row)

		# Wire format toggle
		self.rb_csv.toggled.connect(self._on_format_toggled)
		self.rb_txt.toggled.connect(self._on_format_toggled)

	def _on_format_toggled(self):
		is_csv = self.rb_csv.isChecked()
		self._csv_group.setVisible(is_csv)
		self._txt_group.setVisible(not is_csv)
		self.adjustSize()

	def _on_export(self):
		if self.rb_csv.isChecked():
			separator = ',' if self.rb_comma.isChecked() else ';'
			if self.rb_double_quote.isChecked():
				quote_char = '"'
			elif self.rb_single_quote.isChecked():
				quote_char = "'"
			else:
				quote_char = None
			self.settings = {
				'format': 'csv',
				'separator': separator,
				'quote_char': quote_char,
				'sanitize_commas': separator == ',',
			}
		else:
			self.settings = {
				'format': 'txt',
				'numbering': self.cb_numbering.isChecked(),
				'empty_line': self.cb_empty_line.isChecked(),
			}
		self.accept()


def build_export_content(prompts, settings):
	"""
	Build the string content for export based on settings dict.
	prompts: list of prompt strings.
	Returns (content_str, file_extension).
	"""
	fmt = settings['format']

	if fmt == 'csv':
		separator = settings['separator']
		quote_char = settings['quote_char']
		sanitize = settings.get('sanitize_commas', False)
		lines = []
		for p in prompts:
			text = p.strip()
			if sanitize:
				text = text.replace(',', '')
			if quote_char:
				text = f"{quote_char}{text}{quote_char}"
			lines.append(text)
		content = '\n'.join(lines)
		return content, 'csv'

	else:
		numbering = settings['numbering']
		empty_line = settings['empty_line']
		lines = []
		for i, p in enumerate(prompts, 1):
			text = p.strip()
			if numbering:
				text = f"{i}. {text}"
			lines.append(text)
		sep = '\n\n' if empty_line else '\n'
		content = sep.join(lines)
		return content, 'txt'


class SmartImportWorker(QThread):
	"""Worker thread that smart-parses CSV and TXT files for prompt import."""
	progress_updated = Signal(str)
	progress_value_changed = Signal(int)
	finished = Signal(int)
	error_occurred = Signal(str)

	def __init__(self, db, filename):
		super().__init__()
		self.db = db
		self.filename = filename

	def run(self):
		try:
			self.progress_updated.emit("Reading file...")
			self.progress_value_changed.emit(10)

			with open(self.filename, 'r', encoding='utf-8', errors='replace') as f:
				raw = f.read()

			if not raw.strip():
				self.error_occurred.emit("File is empty.")
				return

			self.progress_updated.emit("Parsing file...")
			self.progress_value_changed.emit(25)

			prompts = _smart_parse(raw)

			if not prompts:
				self.error_occurred.emit("No valid prompts found in the file.")
				return

			self.progress_updated.emit(f"Saving {len(prompts)} prompts to database...")
			self.progress_value_changed.emit(60)

			# Insert in reverse so that prompt #1 from the file gets the highest ID
			# and appears first in the table (which shows newest/highest ID first).
			imported_count = 0
			for i, text in enumerate(reversed(prompts)):
				try:
					self.db.add_external_prompt(text)
					imported_count += 1
					progress = 60 + int((i / len(prompts)) * 35)
					self.progress_value_changed.emit(progress)
					self.progress_updated.emit(f"Saving prompt {i + 1}/{len(prompts)}...")
				except Exception as e:
					print(f"Failed to import prompt: {text[:50]}... - {e}")

			self.progress_updated.emit("Import completed!")
			self.progress_value_changed.emit(100)
			self.finished.emit(imported_count)

		except Exception as e:
			self.error_occurred.emit(str(e))


def _smart_parse(raw: str) -> list:
	"""
	Auto-detect and parse prompts from raw text.
	Handles all formats produced by the export dialog:
	- TXT with numbering (1. 2. 3. …) and/or empty lines between prompts
	- CSV / TXT where each prompt is on its own line, optionally quoted
	- Multi-column CSV (semicolon-separated) where only the first column matters
	"""
	raw = raw.strip()

	# Try semicolon-delimited genuine multi-column CSV first (each line has multiple ;-separated fields)
	prompts = _try_semicolon_csv(raw)
	if prompts:
		return _finalize(prompts)

	# Everything else: line / block based (handles our own CSV and TXT exports)
	prompts = _parse_lines_smart(raw)
	return _finalize(prompts)


def _finalize(prompts: list) -> list:
	result = []
	for p in prompts:
		p = _strip_quotes(p.strip())
		p = p.strip()
		if len(p) >= 5:
			result.append(p)
	return result


def _try_semicolon_csv(raw: str) -> list:
	"""
	Only treat input as multi-column CSV when lines consistently have >= 2 semicolon-separated fields.
	This avoids false-positives on plain TXT prompts that happen to contain semicolons.
	"""
	lines = [l for l in raw.splitlines() if l.strip()]
	if not lines:
		return []
	sample = lines[:min(5, len(lines))]
	multi_field_count = sum(1 for l in sample if l.count(';') >= 1)
	if multi_field_count < len(sample):
		return []
	# Looks like semicolon CSV — take the first field of each row
	prompts = []
	try:
		reader = csv.reader(io.StringIO(raw), delimiter=';')
		for row in reader:
			if row:
				cell = _strip_numbering(row[0].strip())
				cell = _strip_quotes(cell).strip()
				if len(cell) >= 5:
					prompts.append(cell)
	except Exception:
		pass
	return prompts


def _looks_like_csv(raw: str) -> bool:
	"""Heuristic: does the text look like a CSV (first lines have consistent delimiters)?"""
	lines = raw.splitlines()[:10]
	for line in lines:
		stripped = line.strip()
		if not stripped:
			continue
		if ',' in stripped or ';' in stripped:
			return True
	return False


def _parse_csv_smart(raw: str) -> list:
	"""Try parsing as CSV with comma or semicolon delimiter, respecting quotes."""
	prompts = []
	for delimiter in (',', ';'):
		try:
			reader = csv.reader(io.StringIO(raw), delimiter=delimiter)
			rows = list(reader)
			# Collect first non-empty column of each non-empty row
			candidates = []
			for row in rows:
				if row:
					cell = row[0].strip()
					if cell:
						cell = _strip_numbering(cell)
						cell = _strip_quotes(cell)
						cell = cell.strip()
						if len(cell) >= 5:
							candidates.append(cell)
			if candidates:
				prompts = candidates
				break
		except Exception:
			continue
	return prompts


def _parse_lines_smart(raw: str) -> list:
	"""
	Line-based smart parser.
	Handles:
	- Blocks separated by empty lines (each block = one prompt)
	- Lines with leading number + dot (1. prompt text)
	- Plain lines (one prompt per line)
	"""
	# Check if there are blank-line separators
	blocks = re.split(r'\n\s*\n', raw)

	if len(blocks) > 1:
		# Empty-line separated blocks
		prompts = []
		for block in blocks:
			block = block.strip()
			if not block:
				continue
			# Each block might still start with a number
			block = _strip_numbering(block)
			prompts.append(block)
		if prompts:
			return prompts

	# Fall back: one prompt per line
	prompts = []
	for line in raw.splitlines():
		line = line.strip()
		if not line:
			continue
		line = _strip_numbering(line)
		prompts.append(line)
	return prompts


def _strip_numbering(text: str) -> str:
	"""Remove leading numbering like '1. ', '12. ', '1) ', '1: ' etc."""
	return re.sub(r'^\d+[\.\)\:\-]\s*', '', text)


def _strip_quotes(text: str) -> str:
	"""Strip matching surrounding quotes (single or double, one level)."""
	if len(text) >= 2:
		if (text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'"):
			return text[1:-1]
	return text
