import pyexiv2
from database.db_operation import ImageTeaDB, DB_PATH

from PySide6.QtCore import QThread, Signal, Qt, QObject, QTimer, QCoreApplication
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar, QSizePolicy, 
							   QTextEdit, QPushButton, QHBoxLayout, QTableWidget, 
							   QTableWidgetItem, QHeaderView, QFileDialog, QGroupBox, QMessageBox)
from PySide6.QtGui import QIcon
import os
import exiftool
from config import BASE_PATH
import time
import csv
from datetime import datetime
import qtawesome as qta

def _get_chunk_size():
	with open(os.path.join(BASE_PATH, "configs", "app_config.json"), encoding="utf-8") as f:
		app_config = json.load(f)
	return app_config.get('chunk_size', 20)

def _extract_xmp_value(val):
	if isinstance(val, dict):
		return next(iter(val.values()), '')
	return val if isinstance(val, str) else ''

class ProgressDialog(QDialog):
	def __init__(self, parent, total, title):
		super().__init__(parent)
		self.setWindowTitle(title)
		self.setMinimumWidth(500)
		self.setMinimumHeight(170)
		self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
		self.setModal(True)
		
		layout = QVBoxLayout()
		
		info_group = QGroupBox("Progress Information")
		info_layout = QVBoxLayout()
		
		self.chunk_label = QLabel("Chunk: 0 / 0")
		info_layout.addWidget(self.chunk_label)
		
		self.status_label = QLabel("Success: 0 | Failed: 0")
		info_layout.addWidget(self.status_label)
		
		self.file_label = QLabel("")
		self.file_label.setWordWrap(True)
		self.file_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		info_layout.addWidget(self.file_label)
		
		info_group.setLayout(info_layout)
		layout.addWidget(info_group)
		
		# Global progress (overall files) - use percentage scale to match widths
		global_h = QHBoxLayout()
		self.global_progress = QProgressBar()
		self.global_progress.setRange(0, 100)
		self.global_progress.setTextVisible(False)
		self.global_count_label = QLabel("")
		self.global_count_label.setMinimumWidth(120)
		global_h.addWidget(self.global_progress)
		global_h.addWidget(self.global_count_label)
		layout.addLayout(global_h)
		
		# Chunk progress (per current chunk) - percentage scale so widths match
		chunk_h = QHBoxLayout()
		self.chunk_progress = QProgressBar()
		self.chunk_progress.setRange(0, 100)
		self.chunk_progress.setTextVisible(False)
		self.chunk_count_label = QLabel("")
		self.chunk_count_label.setMinimumWidth(120)
		chunk_h.addWidget(self.chunk_progress)
		chunk_h.addWidget(self.chunk_count_label)
		layout.addLayout(chunk_h)
		
		# store total for percent calculations
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
		self.file_label.setText(f"Processing: {filename}")
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
		summary_layout.setSpacing(5)
		
		total_chunks = (total_files + chunk_size - 1) // chunk_size
		summary_layout.addWidget(QLabel(f"Total Files: {total_files} | Chunks: {total_chunks} ({chunk_size} files/chunk)"))
		summary_layout.addWidget(QLabel(f"Success: {success_count} | Failed: {failed_count}"))
		summary_layout.addWidget(QLabel(f"Elapsed Time: {elapsed_time:.2f} seconds"))
		
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
				self.failed_table.setItem(idx, 0, QTableWidgetItem(filename))
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
			id_, filepath, filename, title, description, tags, status, _ = row
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

		if not tags:
			tags = iptc.get('Iptc.Application2.Keywords')
		if not tags:
			user_comment = exif.get('Exif.Photo.UserComment')
			if user_comment:
				tags = [t.strip() for t in user_comment.split(',')]
		if not tags and 'Exif.Image.XPSubject' in exif:
			try:
				xpsubject = exif['Exif.Image.XPSubject']
				if isinstance(xpsubject, bytes):
					xpsubject = xpsubject.decode('utf-16le').rstrip('\x00')
				tags = [t.strip() for t in xpsubject.split(',')]
			except Exception as e:
				print(f"[pyexiv2] Error decoding Exif.Image.XPSubject for {file_path}: {e}")
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

def read_metadata_video(file_path):
	exiftool_path = os.path.join(BASE_PATH, "tools", "exiftool", "exiftool.exe")
	video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
	ext = os.path.splitext(file_path)[1].lower()
	if ext not in video_exts:
		return None, None, None
	try:
		with exiftool.ExifToolHelper(executable=exiftool_path) as et:
			metadata_list = et.get_metadata([file_path])
			if not metadata_list or len(metadata_list) == 0:
				return None, None, None
			data = metadata_list[0]
			if not isinstance(data, dict):
				return None, None, None
			title_keys = ["QuickTime:Title", "XMP:Title", "Title"]
			description_keys = ["QuickTime:Description", "XMP:Description", "Description"]
			tags_keys = ["QuickTime:Keywords", "XMP:Keywords", "Keywords"]
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
				tags_str = ",".join(str(t) for t in tags)
			elif isinstance(tags, str):
				tags_str = tags
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
			
			for idx_in_chunk, row in enumerate(chunk):
				if self.isInterruptionRequested():
					break
				
				global_idx = chunk_start + idx_in_chunk
				chunk_pos = idx_in_chunk + 1
				id_, filepath, filename, title, description, tags, status, _ = row
				
				# emit now includes chunk_pos
				self.progress.emit(global_idx + 1, total, filename, chunk_pos, chunk_idx + 1, chunk_total, 
								 self.success_count, self.failed_count)
				
				try:
					tag_list = [t.strip() for t in tags.split(',')] if tags else []
					write_metadata_pyexiv2(filepath, title, description, tag_list)
					self.success_count += 1
				except Exception as e:
					self.failed_count += 1
					self.errors.append((filename, str(e)))
		
		elapsed_time = time.time() - start_time
		self.finished.emit(self.success_count, self.failed_count, elapsed_time, self.errors)

class VideoMetadataWriterThread(QThread):
	# args: global_index, total, filename, chunk_pos, chunk_index, chunk_total, success_count, failed_count
	progress = Signal(int, int, str, int, int, int, int, int)
	finished = Signal(int, int, float, list)

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
		exiftool_path = os.path.join(BASE_PATH, "tools", "exiftool", "exiftool.exe")
		video_rows = [row for row in self.rows if os.path.splitext(row[1])[1].lower() in video_exts]
		total = len(video_rows)
		total_chunks = (total + self.chunk_size - 1) // self.chunk_size
		
		for chunk_idx in range(total_chunks):
			if self.isInterruptionRequested():
				break
			
			chunk_start = chunk_idx * self.chunk_size
			chunk_end = min(chunk_start + self.chunk_size, total)
			chunk = video_rows[chunk_start:chunk_end]
			chunk_total = len(chunk)
			
			for idx_in_chunk, row in enumerate(chunk):
				if self.isInterruptionRequested():
					break
				
				global_idx = chunk_start + idx_in_chunk
				chunk_pos = idx_in_chunk + 1
				id_, filepath, filename, title, description, tags, status, _ = row
				
				self.progress.emit(global_idx + 1, total, filename, chunk_pos, chunk_idx + 1, chunk_total, 
								 self.success_count, self.failed_count)
				
				try:
					metadata_args = []
					if title is not None:
						metadata_args.append(f"-Title={title}")
						metadata_args.append(f"-QuickTime:Title={title}")
						metadata_args.append(f"-XMP:Title={title}")
					if description is not None:
						metadata_args.append(f"-Description={description}")
						metadata_args.append(f"-QuickTime:Description={description}")
						metadata_args.append(f"-XMP:Description={description}")
						metadata_args.append(f"-QuickTime:Comment={description}")
					if tags is not None:
						if isinstance(tags, str):
							tag_list = [t.strip() for t in tags.split(',') if t.strip()]
						elif isinstance(tags, list):
							tag_list = tags
						else:
							tag_list = []
						if tag_list:
							joined_tags = ",".join(tag_list)
							metadata_args.append(f"-Keywords={joined_tags}")
							metadata_args.append(f"-QuickTime:Keywords={joined_tags}")
							metadata_args.append(f"-XMP:Keywords={joined_tags}")
					metadata_args.append(f"-QuickTime:Software=Image Tea")
					metadata_args.append(f"-XMP:CreatorTool=Image Tea")
					metadata_args.append(f"-Software=Image Tea")
					metadata_args.append("-overwrite_original")
					metadata_args.append(filepath)
					with exiftool.ExifTool(executable=exiftool_path) as et:
						result = et.execute(*[arg.encode('utf-8') for arg in metadata_args])
						if result is None:
							self.failed_count += 1
							self.errors.append((filename, "exiftool error (no result)"))
						else:
							self.success_count += 1
				except Exception as e:
					self.failed_count += 1
					self.errors.append((filename, str(e)))
		
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
		dialog.repaint()
		QCoreApplication.processEvents()
	
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
		dialog.repaint()
		QCoreApplication.processEvents()
	
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
	thread.finished.connect(on_finished)
	dialog.set_thread(thread)
	QTimer.singleShot(0, thread.start)
	dialog.exec()