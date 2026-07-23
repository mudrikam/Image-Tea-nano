import pyexiv2
from database.db_operation import ImageTeaDB, DB_PATH
from ui.theme_system import theme

from PySide6.QtCore import QThread, Signal, Qt, QObject, QTimer, QCoreApplication
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar, QSizePolicy, 
							   QTextEdit, QPushButton, QHBoxLayout, QTableWidget, QAbstractItemView,
				   QTableWidgetItem, QHeaderView, QFileDialog, QGroupBox, QMessageBox, QApplication)
from PySide6.QtGui import QIcon, QColor, QBrush
import os
import re
import shutil
import platform
import exiftool
from config import BASE_PATH
import time
import csv
import subprocess
from datetime import datetime
import qtawesome as qta

try:
	from lxml import etree as _etree
	_LXML_AVAILABLE = True
except Exception:
	_etree = None
	_LXML_AVAILABLE = False

SVG_EXTS = {'.svg'}

_SVG_NS = 'http://www.w3.org/2000/svg'
_RDF_NS = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
_DC_NS = 'http://purl.org/dc/elements/1.1/'
_CC_NS = 'http://creativecommons.org/ns#'

try:
	_etree.register_namespace('svg', _SVG_NS)
	_etree.register_namespace('rdf', _RDF_NS)
	_etree.register_namespace('dc', _DC_NS)
	_etree.register_namespace('cc', _CC_NS)
except Exception:
	pass

def _get_chunk_size():
	with open(os.path.join(BASE_PATH, "configs", "app_config.json"), encoding="utf-8") as f:
		app_config = json.load(f)
	return app_config['chunk_size']


def _sanitize_keyword(keyword):
	if not keyword:
		return keyword
	sanitized = re.sub(r'[^\w\s]', '', str(keyword)).strip()
	return sanitized if sanitized else None


def _truncate_text(text: str, max_len: int = 60) -> str:
	"""Return a shortened version of *text* suitable for UI display.
	If the string is longer than *max_len* characters the middle will be
	replaced with an ellipsis and the file extension (if any) will be
	preserved. The full text is left intact in the item's tooltip so it can
	still be viewed by hovering.
	"""
	if text is None:
		return ""
	if len(text) <= max_len:
		return text
	base, ext = os.path.splitext(text)
	# reserve space for ellipsis and the extension
	keep = max_len - 3 - len(ext)
	if keep < 1:
		return text[: max_len - 3] + "..."
	return base[:keep] + "..." + ext

def _extract_xmp_value(val):
	if isinstance(val, dict):
		return next(iter(val.values()), '')
	return val if isinstance(val, str) else ''

class ProgressDialog(QDialog):
	def __init__(self, parent, total, title):
		super().__init__(parent)
		self.setWindowTitle(title)
		self.setMinimumWidth(640)
		self.setMinimumHeight(520)
		self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
		self.setModal(True)
		
		layout = QVBoxLayout()
		
		info_group = QGroupBox("Progress Information")
		info_layout = QVBoxLayout()
		_icon_size = 12

		chunk_row = QHBoxLayout()
		chunk_icon_lbl = QLabel()
		chunk_icon_lbl.setPixmap(qta.icon('fa6s.layer-group', color=theme.get_color('text_dark')).pixmap(_icon_size, _icon_size))
		self.chunk_label = QLabel("Chunk: 0 / 0")
		chunk_row.addWidget(chunk_icon_lbl)
		chunk_row.addWidget(self.chunk_label)
		chunk_row.addStretch()
		info_layout.addLayout(chunk_row)

		status_row = QHBoxLayout()
		status_icon_lbl = QLabel()
		status_icon_lbl.setPixmap(qta.icon('fa6s.chart-simple', color=theme.get_color('text_dark')).pixmap(_icon_size, _icon_size))
		self.status_label = QLabel("Success: 0 | Failed: 0")
		status_row.addWidget(status_icon_lbl)
		status_row.addWidget(self.status_label)
		status_row.addStretch()
		info_layout.addLayout(status_row)

		file_row = QHBoxLayout()
		file_icon_lbl = QLabel()
		file_icon_lbl.setPixmap(qta.icon('fa6s.file-image', color=theme.get_color('text_dark')).pixmap(_icon_size, _icon_size))
		self.file_label = QLabel("")
		self.file_label.setWordWrap(True)
		self.file_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		file_row.addWidget(file_icon_lbl)
		file_row.addWidget(self.file_label)
		info_layout.addLayout(file_row)

		info_group.setLayout(info_layout)
		layout.addWidget(info_group)
		
		chunk_table_group = QGroupBox("Current Chunk Files")
		chunk_table_layout = QVBoxLayout()
		self.chunk_table = QTableWidget()
		self.chunk_table.setColumnCount(3)
		self.chunk_table.setHorizontalHeaderLabels(["#", "Filename", "Status"])
		self.chunk_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
		self.chunk_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
		self.chunk_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
		self.chunk_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.chunk_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.chunk_table.setSelectionMode(QAbstractItemView.NoSelection)
		chunk_table_layout.addWidget(self.chunk_table)
		chunk_table_group.setLayout(chunk_table_layout)
		layout.addWidget(chunk_table_group)
		
		global_h = QHBoxLayout()
		self.global_progress = QProgressBar()
		self.global_progress.setRange(0, 100)
		self.global_progress.setTextVisible(False)
		self.global_count_label = QLabel("")
		self.global_count_label.setMinimumWidth(120)
		global_h.addWidget(self.global_progress)
		global_h.addWidget(self.global_count_label)
		layout.addLayout(global_h)
		
		chunk_h = QHBoxLayout()
		self.chunk_progress = QProgressBar()
		self.chunk_progress.setRange(0, 100)
		self.chunk_progress.setTextVisible(False)
		self.chunk_count_label = QLabel("")
		self.chunk_count_label.setMinimumWidth(120)
		chunk_h.addWidget(self.chunk_progress)
		chunk_h.addWidget(self.chunk_count_label)
		layout.addLayout(chunk_h)
		
		self._total = total

		button_layout = QHBoxLayout()
		self.cancel_btn = QPushButton("Cancel")
		self.cancel_btn.setIcon(qta.icon('fa6s.xmark'))
		self.cancel_btn.clicked.connect(self._cancel_thread)
		self.close_btn = QPushButton("Close")
		self.close_btn.setIcon(qta.icon('fa6s.xmark'))
		self.close_btn.clicked.connect(self.accept)
		self.close_btn.setVisible(False)
		button_layout.addStretch()
		button_layout.addWidget(self.cancel_btn)
		button_layout.addWidget(self.close_btn)
		layout.addLayout(button_layout)
		
		self.setLayout(layout)
		self._thread = None

	def set_thread(self, thread):
		self._thread = thread

	def update_progress(self, value, filename, chunk_pos, chunk_current, chunk_total, success_count, failed_count):
		# value = global index, chunk_pos = position within current chunk
		short = _truncate_text(filename)
		self.file_label.setText(f"Processing: {short}")
		# keep full filename available on hover
		self.file_label.setToolTip(filename)
		# overall percent
		if self._total > 0:
			percent_global = int((value / self._total) * 100)
		else:
			percent_global = 100
		self.global_progress.setValue(percent_global)
		self.global_count_label.setText(f"{value} / {self._total} (Overall)")
		# chunk percent
		if chunk_total > 0:
			percent_chunk = int((chunk_pos / chunk_total) * 100)
		else:
			percent_chunk = 100
		self.chunk_progress.setValue(percent_chunk)
		self.chunk_count_label.setText(f"{chunk_pos} / {chunk_total} (Chunk)")
		self.chunk_label.setText(f"Chunk: {chunk_current} / {chunk_total} (file {chunk_pos})")
		self.status_label.setText(f"Success: {success_count} | Failed: {failed_count}")

	def setup_chunk_table(self, chunk_idx, total_chunks, filenames):
		self.chunk_table.clearContents()
		self.chunk_table.setRowCount(len(filenames))
		for i, fname in enumerate(filenames):
			num_item = QTableWidgetItem(str(i + 1))
			num_item.setTextAlignment(Qt.AlignCenter)
			self.chunk_table.setItem(i, 0, num_item)
			# display truncated filename and preserve full name as tooltip
			short = _truncate_text(fname)
			fname_item = QTableWidgetItem(short)
			fname_item.setToolTip(fname)
			self.chunk_table.setItem(i, 1, fname_item)
			status_item = QTableWidgetItem()
			status_item.setTextAlignment(Qt.AlignCenter)
			status_item.setIcon(qta.icon('fa6s.circle-exclamation', color=theme.get_color('warning')))
			self.chunk_table.setItem(i, 2, status_item)

	def update_file_row_status(self, row_idx, success, error=""):
		if row_idx < 0 or row_idx >= self.chunk_table.rowCount():
			return
		icon = None
		if success:
			icon = qta.icon('fa6s.circle-check', color=theme.get_color('success'))
			bg_color = QColor(theme.get_color('success'))
			bg_color.setAlpha(int(0.45 * 255))
		else:
			icon = qta.icon('fa6s.circle-xmark', color=theme.get_color('error'))
			bg_color = QColor(theme.get_color('error'))
			bg_color.setAlpha(int(0.18 * 255))
		# apply background to entire row
		bg_brush = QBrush(bg_color)
		for col in range(self.chunk_table.columnCount()):
			item = self.chunk_table.item(row_idx, col)
			if item:
				item.setBackground(bg_brush)
		status_item = self.chunk_table.item(row_idx, 2)
		if status_item:
			status_item.setIcon(icon)
			status_item.setText("")

	def _cancel_thread(self):
		if self._thread is not None and self._thread.isRunning():
			self._thread.requestInterruption()
			self._thread.quit()
			self._thread.wait()
		self.reject()

	def closeEvent(self, event):
		if self._thread is not None and self._thread.isRunning():
			self._thread.requestInterruption()
			self._thread.quit()
			self._thread.wait()
		super().closeEvent(event)

class ResultDialog(QDialog):
	def __init__(self, parent, total_files, success_count, failed_count, elapsed_time, failed_files, operation_type="Image", chunk_size=20):
		super().__init__(parent)
		self.setWindowTitle("Metadata Embed Result")
		self.setMinimumWidth(500)
		self.setMinimumHeight(400)
		self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
		self.failed_files = failed_files
		self.operation_type = operation_type
		
		layout = QVBoxLayout()
		layout.setSpacing(10)
		
		summary_group = QGroupBox("Summary")
		summary_layout = QVBoxLayout()
		summary_layout.setSpacing(8)

		total_chunks = (total_files + chunk_size - 1) // chunk_size
		total_lbl = QLabel(f"Total Files: {total_files}  |  Chunks: {total_chunks}  ({chunk_size} files/chunk)")
		total_lbl.setStyleSheet(f"font-size: 12px; color: {theme.get_color('foreground')};")
		summary_layout.addWidget(total_lbl)

		result_row = QHBoxLayout()
		result_row.setSpacing(16)

		success_icon = QLabel()
		success_icon.setPixmap(qta.icon('fa6s.check', color=theme.get_color('success')).pixmap(16, 16))
		success_text = QLabel(f"Success: {success_count}")
		success_text.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {theme.get_color('success')};")

		failed_color = theme.get_color('error') if failed_count > 0 else theme.get_color('gray')
		failed_icon = QLabel()
		failed_icon.setPixmap(qta.icon('fa6s.xmark', color=failed_color).pixmap(16, 16))
		failed_text = QLabel(f"Failed: {failed_count}")
		failed_text.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {failed_color};")

		result_row.addWidget(success_icon)
		result_row.addWidget(success_text)
		result_row.addSpacing(8)
		result_row.addWidget(failed_icon)
		result_row.addWidget(failed_text)
		result_row.addStretch()
		summary_layout.addLayout(result_row)

		elapsed_lbl = QLabel(f"Elapsed Time: {elapsed_time:.2f} seconds")
		elapsed_lbl.setStyleSheet(f"font-size: 11px; color: {theme.get_color('gray')};")
		summary_layout.addWidget(elapsed_lbl)

		summary_group.setLayout(summary_layout)
		layout.addWidget(summary_group)
		
		failed_group = QGroupBox(f"Failed Files ({len(failed_files)})")
		failed_layout = QVBoxLayout()
		
		self.failed_table = QTableWidget()
		self.failed_table.setColumnCount(2)
		self.failed_table.setHorizontalHeaderLabels(["Filename", "Error"])
		self.failed_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
		self.failed_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
		self.failed_table.setRowCount(len(failed_files))
		
		if failed_files:
			for idx, (filename, error) in enumerate(failed_files):
				name_item = QTableWidgetItem(_truncate_text(filename))
				name_item.setToolTip(filename)
				self.failed_table.setItem(idx, 0, name_item)
				self.failed_table.setItem(idx, 1, QTableWidgetItem(error))
		
		failed_layout.addWidget(self.failed_table)
		
		export_btn = QPushButton("Export to CSV")
		export_btn.setIcon(qta.icon('fa6s.file-export'))
		export_btn.clicked.connect(self._export_csv)
		export_btn.setEnabled(len(failed_files) > 0)
		failed_layout.addWidget(export_btn)
		
		failed_group.setLayout(failed_layout)
		layout.addWidget(failed_group)
		
		button_layout = QHBoxLayout()
		button_layout.addStretch()
		close_btn = QPushButton("Close")
		close_btn.setIcon(qta.icon('fa6s.xmark'))
		close_btn.clicked.connect(self.accept)
		button_layout.addWidget(close_btn)
		layout.addLayout(button_layout)
		
		self.setLayout(layout)
	
	def _export_csv(self):
		home_dir = os.path.expanduser("~")
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		default_filename = f"Image_Tea_Metadata_Embed_Failure_Reports_{timestamp}.csv"
		default_path = os.path.join(home_dir, default_filename)
		
		filepath, _ = QFileDialog.getSaveFileName(
			self,
			"Export Failed Files to CSV",
			default_path,
			"CSV Files (*.csv)"
		)
		
		if filepath:
			try:
				with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
					writer = csv.writer(csvfile)
					writer.writerow(["Filename", "Error"])
					for filename, error in self.failed_files:
						writer.writerow([filename, error])
				
				QMessageBox.information(self, "Export Success", f"Failed files exported to:\n{filepath}")
			except Exception as e:
				QMessageBox.critical(self, "Export Error", f"Failed to export CSV:\n{str(e)}")

class ImageTeaGeneratorThread(QThread):
	progress = Signal(int, int)
	finished = Signal(list)
	row_status = Signal(int, str)

	def __init__(self, api_key, model, rows, row_map=None, generate_metadata_func=None):
		super().__init__()
		self.api_key = api_key
		self.model = model
		self.rows = rows
		self.errors = []
		self.row_map = row_map or {}
		self.generate_metadata_func = generate_metadata_func

	def run(self):
		db = ImageTeaDB()
		total = len(self.rows)
		for idx, row in enumerate(self.rows):
			if self.isInterruptionRequested():
				break
			id_, filepath, filename, title, description, tags, status, *_ = row
			visual_idx = self.row_map.get(id_, idx)
			self.row_status.emit(visual_idx, "processing")
			try:
				result = self.generate_metadata_func(self.api_key, self.model, filepath)
				if isinstance(result, tuple) and len(result) >= 3:
					t, d, tg = result[0], result[1], result[2]
				else:
					t, d, tg = '', '', ''
				t = _extract_xmp_value(t)
				d = _extract_xmp_value(d)
				if not t:
					db.update_file_status(filepath, "failed")
					self.errors.append(f"{filename}: Failed to generate metadata")
					self.row_status.emit(visual_idx, "failed")
				else:
					db.update_metadata(filepath, t, d, tg, status="success")
					self.row_status.emit(visual_idx, "success")
			except Exception as e:
				db.update_file_status(filepath, "failed")
				self.errors.append(f"{filename}: {e}")
				self.row_status.emit(visual_idx, "failed")
			self.progress.emit(idx + 1, total)
		self.finished.emit(self.errors)

def write_metadata_pyexiv2(file_path, title, description, tag_list):
	try:
		title = _extract_xmp_value(title)
		description = _extract_xmp_value(description)
		if isinstance(tag_list, str):
			tag_list = [t.strip() for t in tag_list.split(',') if t.strip()]
		elif not isinstance(tag_list, list):
			tag_list = []
		tag_list = [_sanitize_keyword(t) for t in tag_list]
		tag_list = [t for t in tag_list if t]
		subject_str = ', '.join(tag_list)
		xmp_update = {}
		iptc_update = {}
		exif_update = {}

		if not title:
			xmp_update['Xmp.dc.title'] = ''
			iptc_update['Iptc.Application2.ObjectName'] = ''
			exif_update['Exif.Image.ImageDescription'] = ''
		else:
			xmp_update['Xmp.dc.title'] = title
			iptc_update['Iptc.Application2.ObjectName'] = title
			if not description:
				exif_update['Exif.Image.ImageDescription'] = title

		if not description:
			xmp_update['Xmp.dc.description'] = ''
			iptc_update['Iptc.Application2.Caption'] = ''
			if 'Exif.Image.ImageDescription' not in exif_update:
				exif_update['Exif.Image.ImageDescription'] = ''
		else:
			xmp_update['Xmp.dc.description'] = description
			iptc_update['Iptc.Application2.Caption'] = description
			exif_update['Exif.Image.ImageDescription'] = description

		if not tag_list:
			xmp_update['Xmp.dc.subject'] = []
			iptc_update['Iptc.Application2.Keywords'] = []
			exif_update['Exif.Photo.UserComment'] = ''
			exif_update['Exif.Image.XPSubject'] = ''
		else:
			xmp_update['Xmp.dc.subject'] = tag_list
			iptc_update['Iptc.Application2.Keywords'] = tag_list
			exif_update['Exif.Photo.UserComment'] = ', '.join(tag_list)
			exif_update['Exif.Image.XPSubject'] = subject_str

		xmp_update['Xmp.xmp.CreatorTool'] = "Image Tea"
		exif_update['Exif.Image.Software'] = "Image Tea"

		with pyexiv2.Image(file_path) as metadata:
			metadata.modify_xmp(xmp_update)
			metadata.modify_iptc(iptc_update)
			metadata.modify_exif(exif_update)
	except Exception as e:
		print(f"[pyexiv2 ERROR] {file_path}: {e}")

def read_metadata_pyexiv2(file_path):
    try:
        metadata = pyexiv2.Image(file_path)
        xmp = metadata.read_xmp()
        iptc = metadata.read_iptc()
        exif = metadata.read_exif()

        title = _extract_xmp_value(xmp.get('Xmp.dc.title')) if 'Xmp.dc.title' in xmp else None
        description = _extract_xmp_value(xmp.get('Xmp.dc.description')) if 'Xmp.dc.description' in xmp else None
        tags = xmp.get('Xmp.dc.subject') if 'Xmp.dc.subject' in xmp else None

        if not title:
            title = iptc.get('Iptc.Application2.ObjectName')
            if isinstance(title, list):
                title = title[0] if title else None
        if not title:
            title = exif.get('Exif.Image.ImageDescription')

        if not description:
            description = iptc.get('Iptc.Application2.Caption')
            if isinstance(description, list):
                description = description[0] if description else None
        if not description:
            description = exif.get('Exif.Image.ImageDescription')
        if not description:
            description = exif.get('Exif.Photo.UserComment')

        if not tags:
            tags = iptc.get('Iptc.Application2.Keywords')
        if not tags:
            user_comment = exif.get('Exif.Photo.UserComment')
            if user_comment and not description:
                tags = [t.strip() for t in user_comment.split(',')]
        if not tags and 'Exif.Image.XPSubject' in exif:
            try:
                xpsubject = exif['Exif.Image.XPSubject']
                if isinstance(xpsubject, bytes):
                    xpsubject = xpsubject.decode('utf-16le').rstrip('\x00')
                tags = [t.strip() for t in xpsubject.split(',')]
            except Exception as e:
                print(f"[pyexiv2] Error decoding Exif.Image.XPSubject for {file_path}: {e}")
        
        # Fallback: For PNG files, try reading Description field via exiftool
        if not description:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.png':
                try:
                    exiftool_path = os.path.join(BASE_PATH, "tools", "exiftool", "exiftool.exe")
                    if not os.path.exists(exiftool_path):
                        system_ex = shutil.which("exiftool")
                        exiftool_path = system_ex if system_ex else None
                    
                    if exiftool_path:
                        result = subprocess.run(
                            [exiftool_path, "-Description", "-b", file_path],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            description = result.stdout.strip()
                            print(f"[pyexiv2] Got PNG Description via exiftool: {description[:50]}...")
                except Exception as e:
                    print(f"[pyexiv2] Error reading PNG Description via exiftool: {e}")
        
        if isinstance(tags, list):
            tags_str = ','.join(tags)
        elif isinstance(tags, str):
            tags_str = tags
        else:
            tags_str = ''

        metadata.close()
        print(f"[pyexiv2 READ] {file_path} | title: {title} | description: {description} | tags: {tags_str}")
        return title, description, tags_str
    except Exception as e:
        print(f"[pyexiv2 READ ERROR] {file_path}: {e}")
        return None, None, None

def _svg_find_metadata_description(root):
	"""Return the rdf:Description element of an SVG's <metadata> block, or None."""
	if root is None or not _LXML_AVAILABLE:
		return None
	metadata = root.find('{%s}metadata' % _SVG_NS)
	if metadata is None:
		return None
	rdf = metadata.find('{%s}RDF' % _RDF_NS)
	if rdf is None:
		return None
	desc = rdf.find('{%s}Description' % _RDF_NS)
	return desc


def read_metadata_svg(file_path):
	if not _LXML_AVAILABLE:
		print(f"[svg READ] lxml not available, cannot read {file_path}")
		return None, None, None
	try:
		parser = _etree.XMLParser(remove_blank_text=False)
		tree = _etree.parse(file_path, parser)
		root = tree.getroot()
		desc = _svg_find_metadata_description(root)
		if desc is None:
			return None, None, None

		title_el = desc.find('{%s}title' % _DC_NS)
		title = title_el.text if title_el is not None and title_el.text else None

		desc_el = desc.find('{%s}description' % _DC_NS)
		description = desc_el.text if desc_el is not None and desc_el.text else None

		tags = None
		subject_el = desc.find('{%s}subject' % _DC_NS)
		if subject_el is not None:
			bag = subject_el.find('{%s}Bag' % _RDF_NS)
			if bag is not None:
				items = []
				for li in bag.findall('{%s}li' % _RDF_NS):
					if li.text and li.text.strip():
						items.append(li.text.strip())
				if items:
					tags = ','.join(items)

		print(f"[svg READ] {file_path} | title: {title} | description: {description} | tags: {tags}")
		return title, description, tags
	except Exception as e:
		print(f"[svg READ ERROR] {file_path}: {e}")
		return None, None, None


def write_metadata_svg(file_path, title, description, tag_list):
	if not _LXML_AVAILABLE:
		raise RuntimeError("lxml is required to write SVG metadata")

	title = _extract_xmp_value(title)
	description = _extract_xmp_value(description)
	if isinstance(tag_list, str):
		tag_list = [t.strip() for t in tag_list.split(',') if t.strip()]
	elif not isinstance(tag_list, list):
		tag_list = []
	tag_list = [_sanitize_keyword(t) for t in tag_list]
	tag_list = [t for t in tag_list if t]

	parser = _etree.XMLParser(remove_blank_text=False)
	if os.path.isfile(file_path):
		tree = _etree.parse(file_path, parser)
		root = tree.getroot()
	else:
		root = _etree.Element('{%s}svg' % _SVG_NS, nsmap={None: _SVG_NS})
		tree = _etree.ElementTree(root)

	metadata = root.find('{%s}metadata' % _SVG_NS)
	if metadata is None:
		metadata = _etree.SubElement(root, '{%s}metadata' % _SVG_NS)

	rdf = metadata.find('{%s}RDF' % _RDF_NS)
	if rdf is None:
		rdf = _etree.SubElement(metadata, '{%s}RDF' % _RDF_NS,
								nsmap={'rdf': _RDF_NS, 'dc': _DC_NS, 'cc': _CC_NS})

	desc = rdf.find('{%s}Description' % _RDF_NS)
	if desc is None:
		desc = _etree.SubElement(rdf, '{%s}Description' % _RDF_NS)

	# title
	title_el = desc.find('{%s}title' % _DC_NS)
	if not title:
		if title_el is not None:
			desc.remove(title_el)
	else:
		if title_el is None:
			title_el = _etree.SubElement(desc, '{%s}title' % _DC_NS)
		title_el.text = title

	# description
	desc_el = desc.find('{%s}description' % _DC_NS)
	if not description:
		if desc_el is not None:
			desc.remove(desc_el)
	else:
		if desc_el is None:
			desc_el = _etree.SubElement(desc, '{%s}description' % _DC_NS)
		desc_el.text = description

	# subject (tags)
	subject_el = desc.find('{%s}subject' % _DC_NS)
	if not tag_list:
		if subject_el is not None:
			desc.remove(subject_el)
	else:
		if subject_el is None:
			subject_el = _etree.SubElement(desc, '{%s}subject' % _DC_NS)
		bag = subject_el.find('{%s}Bag' % _RDF_NS)
		if bag is None:
			bag = _etree.SubElement(subject_el, '{%s}Bag' % _RDF_NS)
		for old_li in bag.findall('{%s}li' % _RDF_NS):
			bag.remove(old_li)
		for t in tag_list:
			li = _etree.SubElement(bag, '{%s}li' % _RDF_NS)
			li.text = t

	tree.write(file_path, xml_declaration=True, encoding='UTF-8', pretty_print=True)


def read_metadata_video(file_path):
	video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
	ext = os.path.splitext(file_path)[1].lower()
	if ext not in video_exts:
		return None, None, None
	if platform.system() == "Windows":
		exiftool_path = os.path.join(BASE_PATH, "tools", "exiftool", "exiftool.exe")
		if not (os.path.isfile(exiftool_path) and os.access(exiftool_path, os.X_OK)):
			system_ex = shutil.which("exiftool")
			if system_ex:
				exiftool_path = system_ex
	else:
		system_ex = shutil.which("exiftool")
		if not system_ex:
			app = QApplication.instance()
			if app is not None:
				try:
					from tools.tools_checker import show_manual_install_dialog
					show_manual_install_dialog("ExifTool", os.path.join(BASE_PATH, "tools", "exiftool"), "https://exiftool.org/", parent=app.activeWindow() if app else None)
				except Exception as e:
					print(f"[Metadata] Could not show ExifTool install dialog: {e}")
			else:
				print("ExifTool not found in PATH. Install examples:")
				print("  Ubuntu/Debian: sudo apt update && sudo apt install libimage-exiftool-perl")
				print("  Fedora: sudo dnf install perl-Image-ExifTool")
				print("  Arch: sudo pacman -S perl-image-exiftool")
				print("  macOS (Homebrew): brew install exiftool")
			return None, None, None
		exiftool_path = system_ex
	try:
		with exiftool.ExifToolHelper(executable=exiftool_path) as et:
			metadata_list = et.get_metadata([file_path])
			if not metadata_list or len(metadata_list) == 0:
				return None, None, None
			data = metadata_list[0]
			if not isinstance(data, dict):
				return None, None, None
			title_keys = ["Keys:Title", "QuickTime:Title", "UserData:Title", "XMP:Title", "Title"]
			description_keys = ["Keys:Description", "QuickTime:Description", "UserData:Description", "Keys:Comment", "QuickTime:Comment", "XMP:Description", "Description"]
			tags_keys = ["Keys:Keywords", "QuickTime:Keywords", "UserData:Keywords", "XMP:Subject", "XMP:Keywords", "Subject", "WM/Category", "Keywords"]
			title = None
			for k in title_keys:
				if k in data and data[k] is not None:
					title = data[k]
					break
			description = None
			for k in description_keys:
				if k in data and data[k] is not None:
					description = data[k]
					break
			tags = None
			for k in tags_keys:
				if k in data and data[k] is not None:
					tags = data[k]
					break
			if isinstance(tags, list):
				tags_str = ",".join(str(t).strip() for t in tags if str(t).strip())
			elif isinstance(tags, str):
				tags_str = ",".join(t.strip() for t in tags.replace(";", ",").split(",") if t.strip())
			else:
				tags_str = ""
			return title, description, tags_str
		return None, None, None
	except Exception as e:
		print(f"[exiftool READ ERROR] {file_path}: {e}")
		return None, None, None

class ImageMetadataWriterThread(QThread):
	# args: global_index, total, filename, chunk_pos, chunk_index, chunk_total, success_count, failed_count
	progress = Signal(int, int, str, int, int, int, int, int)
	finished = Signal(int, int, float, list)
	chunk_started = Signal(int, int, list)
	file_result = Signal(int, bool, str)

	def __init__(self, db, rows):
		super().__init__()
		self.db = db
		self.rows = rows
		self.chunk_size = _get_chunk_size()
		self.errors = []
		self.success_count = 0
		self.failed_count = 0

	def run(self):
		start_time = time.time()
		total = len(self.rows)
		total_chunks = (total + self.chunk_size - 1) // self.chunk_size
		
		for chunk_idx in range(total_chunks):
			if self.isInterruptionRequested():
				break
			
			chunk_start = chunk_idx * self.chunk_size
			chunk_end = min(chunk_start + self.chunk_size, total)
			chunk = self.rows[chunk_start:chunk_end]
			chunk_total = len(chunk)

			chunk_filenames = [row[2] for row in chunk]
			self.chunk_started.emit(chunk_idx + 1, total_chunks, chunk_filenames)
			
			for idx_in_chunk, row in enumerate(chunk):
				if self.isInterruptionRequested():
					break
				
				global_idx = chunk_start + idx_in_chunk
				chunk_pos = idx_in_chunk + 1
				id_, filepath, filename, title, description, tags, status, *_ = row
				
				# emit now includes chunk_pos
				self.progress.emit(global_idx + 1, total, filename, chunk_pos, chunk_idx + 1, chunk_total, 
								 self.success_count, self.failed_count)
				
				try:
					tag_list = [t.strip() for t in tags.split(',')] if tags else []
					ext = os.path.splitext(filepath)[1].lower()
					if ext in SVG_EXTS:
						write_metadata_svg(filepath, title, description, tag_list)
					else:
						write_metadata_pyexiv2(filepath, title, description, tag_list)
					self.success_count += 1
					self.file_result.emit(idx_in_chunk, True, "")
				except Exception as e:
					self.failed_count += 1
					self.errors.append((filename, str(e)))
					self.file_result.emit(idx_in_chunk, False, str(e))
				
				time.sleep(0.05)

			if not self.isInterruptionRequested():
				time.sleep(0.15)
		
		elapsed_time = time.time() - start_time
		self.finished.emit(self.success_count, self.failed_count, elapsed_time, self.errors)

class VideoMetadataWriterThread(QThread):
	# args: global_index, total, filename, chunk_pos, chunk_index, chunk_total, success_count, failed_count
	progress = Signal(int, int, str, int, int, int, int, int)
	finished = Signal(int, int, float, list)
	chunk_started = Signal(int, int, list)
	file_result = Signal(int, bool, str)

	def __init__(self, db, rows):
		super().__init__()
		self.db = db
		self.rows = rows
		self.chunk_size = _get_chunk_size()
		self.errors = []
		self.success_count = 0
		self.failed_count = 0

	def run(self):
		start_time = time.time()
		video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
		video_rows = [row for row in self.rows if os.path.splitext(row[1])[1].lower() in video_exts]
		if platform.system() == "Windows":
			exiftool_path = os.path.join(BASE_PATH, "tools", "exiftool", "exiftool.exe")
			if not (os.path.isfile(exiftool_path) and os.access(exiftool_path, os.X_OK)):
				system_ex = shutil.which("exiftool")
				if system_ex:
					exiftool_path = system_ex
		else:
			system_ex = shutil.which("exiftool")
			if not system_ex:
				app = QApplication.instance()
				try:
					from tools.tools_checker import show_manual_install_dialog
					show_manual_install_dialog("ExifTool", os.path.join(BASE_PATH, "tools", "exiftool"), "https://exiftool.org/", parent=app.activeWindow() if app else None)
				except Exception as e:
					print(f"[Metadata] Could not show ExifTool install dialog: {e}")
				for row in video_rows:
					filename = row[2] if len(row) > 2 else os.path.basename(row[1])
					self.failed_count += 1
					self.errors.append((filename, "ExifTool not found"))
				elapsed_time = time.time() - start_time
				self.finished.emit(self.success_count, self.failed_count, elapsed_time, self.errors)
				return
			exiftool_path = system_ex
		total = len(video_rows)
		total_chunks = (total + self.chunk_size - 1) // self.chunk_size
		
		for chunk_idx in range(total_chunks):
			if self.isInterruptionRequested():
				break
			
			chunk_start = chunk_idx * self.chunk_size
			chunk_end = min(chunk_start + self.chunk_size, total)
			chunk = video_rows[chunk_start:chunk_end]
			chunk_total = len(chunk)

			chunk_filenames = [row[2] for row in chunk]
			self.chunk_started.emit(chunk_idx + 1, total_chunks, chunk_filenames)
			
			for idx_in_chunk, row in enumerate(chunk):
				if self.isInterruptionRequested():
					break
				
				global_idx = chunk_start + idx_in_chunk
				chunk_pos = idx_in_chunk + 1
				id_, filepath, filename, title, description, tags, status, *_ = row
				
				self.progress.emit(global_idx + 1, total, filename, chunk_pos, chunk_idx + 1, chunk_total, 
								 self.success_count, self.failed_count)
				
				try:
					metadata_args = []
					if title is not None:
						metadata_args.append(f"-Title={title}")
						metadata_args.append(f"-Keys:Title={title}")
						metadata_args.append(f"-QuickTime:Title={title}")
						metadata_args.append(f"-XMP:Title={title}")
					if description is not None:
						metadata_args.append(f"-Description={description}")
						metadata_args.append(f"-Keys:Description={description}")
						metadata_args.append(f"-QuickTime:Description={description}")
						metadata_args.append(f"-QuickTime:Comment={description}")
						metadata_args.append(f"-XMP:Description={description}")
					if tags is not None:
						if isinstance(tags, str):
							tag_list = [t.strip() for t in tags.split(',') if t.strip()]
						elif isinstance(tags, list):
							tag_list = tags
						else:
							tag_list = []
						tag_list = [_sanitize_keyword(t) for t in tag_list]
						tag_list = [t for t in tag_list if t]
						if tag_list:
							joined_comma = ",".join(tag_list)
							joined_semi = "; ".join(tag_list)
							metadata_args.append(f"-Keys:Keywords={joined_comma}")
							metadata_args.append(f"-QuickTime:Keywords={joined_comma}")
							metadata_args.append(f"-Subject={joined_semi}")
							metadata_args.append(f"-WM/Category={joined_semi}")
							for t in tag_list:
								metadata_args.append(f"-XMP:Subject={t}")
					metadata_args.append(f"-Keys:Software=Image Tea")
					metadata_args.append(f"-QuickTime:Software=Image Tea")
					metadata_args.append(f"-XMP:CreatorTool=Image Tea")
					metadata_args.append("-overwrite_original")
					metadata_args.append(filepath)
					with exiftool.ExifTool(executable=exiftool_path) as et:
						result = et.execute(*[arg.encode('utf-8') for arg in metadata_args])
						if result is None:
							self.failed_count += 1
							self.errors.append((filename, "exiftool error (no result)"))
							self.file_result.emit(idx_in_chunk, False, "exiftool error (no result)")
						else:
							self.success_count += 1
							self.file_result.emit(idx_in_chunk, True, "")
				except Exception as e:
					self.failed_count += 1
					self.errors.append((filename, str(e)))
					self.file_result.emit(idx_in_chunk, False, str(e))
				
				time.sleep(0.05)

			if not self.isInterruptionRequested():
				time.sleep(0.15)
		
		elapsed_time = time.time() - start_time
		self.finished.emit(self.success_count, self.failed_count, elapsed_time, self.errors)

def write_metadata_to_images(db, parent=None):
	rows = db.get_all_files()
	if not rows:
		QMessageBox.information(parent, "No Files", "No files found in database.")
		return
	
	dialog = ProgressDialog(parent, len(rows), "Writing Metadata to Images")
	
	def on_progress(idx, total, filename, chunk_pos, chunk_current, chunk_total, success_count, failed_count):
		dialog.update_progress(idx, filename, chunk_pos, chunk_current, chunk_total, success_count, failed_count)
	
	def on_chunk_started(chunk_idx, total_chunks, filenames):
		dialog.setup_chunk_table(chunk_idx, total_chunks, filenames)
	
	def on_file_result(row_idx, success, error):
		dialog.update_file_row_status(row_idx, success, error)
	
	def on_finished(success_count, failed_count, elapsed_time, errors):
		# Close progress dialog first
		dialog.accept()
		# Defer ResultDialog to avoid nested event loop crash in embedded Python
		def show_result():
			result_dialog = ResultDialog(parent, len(rows), success_count, failed_count, 
										elapsed_time, errors, "Image", _get_chunk_size())
			result_dialog.exec()
		QTimer.singleShot(100, show_result)
	
	thread = ImageMetadataWriterThread(db, rows)
	thread.progress.connect(on_progress)
	thread.chunk_started.connect(on_chunk_started)
	thread.file_result.connect(on_file_result)
	thread.finished.connect(on_finished)
	dialog.set_thread(thread)
	QTimer.singleShot(0, thread.start)
	dialog.exec()

def write_metadata_to_videos(db, parent=None):
	rows = db.get_all_files()
	video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
	video_rows = [row for row in rows if os.path.splitext(row[1])[1].lower() in video_exts]
	
	if not video_rows:
		QMessageBox.information(parent, "No Videos", "No video files found in database.")
		return
	
	dialog = ProgressDialog(parent, len(video_rows), "Writing Metadata to Videos")
	
	def on_progress(idx, total, filename, chunk_pos, chunk_current, chunk_total, success_count, failed_count):
		dialog.update_progress(idx, filename, chunk_pos, chunk_current, chunk_total, success_count, failed_count)
	
	def on_chunk_started(chunk_idx, total_chunks, filenames):
		dialog.setup_chunk_table(chunk_idx, total_chunks, filenames)
	
	def on_file_result(row_idx, success, error):
		dialog.update_file_row_status(row_idx, success, error)
	
	def on_finished(success_count, failed_count, elapsed_time, errors):
		# Close progress dialog first
		dialog.accept()
		# Defer ResultDialog to avoid nested event loop crash in embedded Python
		def show_result():
			result_dialog = ResultDialog(parent, len(video_rows), success_count, failed_count, 
										elapsed_time, errors, "Video", _get_chunk_size())
			result_dialog.exec()
		QTimer.singleShot(100, show_result)
	
	thread = VideoMetadataWriterThread(db, rows)
	thread.progress.connect(on_progress)
	thread.chunk_started.connect(on_chunk_started)
	thread.file_result.connect(on_file_result)
	thread.finished.connect(on_finished)
	dialog.set_thread(thread)
	QTimer.singleShot(0, thread.start)
	dialog.exec()