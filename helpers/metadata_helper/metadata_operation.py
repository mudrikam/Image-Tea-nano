import pyexiv2
from database.db_operation import ImageTeaDB, DB_PATH

from PySide6.QtCore import QThread, Signal, Qt, QObject, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QSizePolicy, QTextEdit, QPushButton
import os
import exiftool
from config import BASE_PATH

def _extract_xmp_value(val):
	if isinstance(val, dict):
		return next(iter(val.values()), '')
	return val if isinstance(val, str) else ''

class ProgressDialog(QDialog):
	def __init__(self, parent, total, title):
		super().__init__(parent)
		self.setWindowTitle(title)
		self.setMinimumWidth(400)
		self.setMinimumHeight(180)
		self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
		self.setModal(True)
		layout = QVBoxLayout()
		self.label = QLabel("")
		self.label.setWordWrap(True)
		self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		layout.addWidget(self.label)
		self.progress = QProgressBar()
		self.progress.setRange(0, total)
		layout.addWidget(self.progress)
		self.error_box = QTextEdit()
		self.error_box.setReadOnly(True)
		self.error_box.setVisible(False)
		self.error_box.setMinimumHeight(80)
		layout.addWidget(self.error_box)
		self.close_btn = QPushButton("Close")
		self.close_btn.setVisible(False)
		self.close_btn.clicked.connect(self.accept)
		layout.addWidget(self.close_btn)
		self.cancel_btn = QPushButton("Cancel")
		self.cancel_btn.setVisible(True)
		self.cancel_btn.clicked.connect(self._cancel_thread)
		layout.addWidget(self.cancel_btn)
		self.setLayout(layout)
		self._thread = None

	def set_thread(self, thread):
		self._thread = thread

	def update_progress(self, value, filename):
		self.progress.setValue(value)
		self.label.setText(f"Writing metadata to:\n{filename}")

	def show_errors(self, errors):
		if errors:
			self.error_box.setVisible(True)
			self.error_box.setPlainText("Error(s) occurred:\n" + "\n".join(errors))
			self.close_btn.setVisible(True)
			self.cancel_btn.setVisible(False)
			self.label.setText("Some errors occurred during writing metadata.")
		else:
			self.error_box.setVisible(False)
			self.close_btn.setVisible(False)
			self.cancel_btn.setVisible(True)

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
	progress = Signal(int, int, str)
	finished = Signal(list)

	def __init__(self, db, rows):
		super().__init__()
		self.db = db
		self.rows = rows
		self.errors = []

	def run(self):
		total = len(self.rows)
		for idx, row in enumerate(self.rows):
			if self.isInterruptionRequested():
				break
			id_, filepath, filename, title, description, tags, status, _ = row
			self.progress.emit(idx + 1, total, filename)
			try:
				tag_list = [t.strip() for t in tags.split(',')] if tags else []
				write_metadata_pyexiv2(filepath, title, description, tag_list)
			except Exception as e:
				self.errors.append(f"{filename}: {e}")
		self.finished.emit(self.errors)

class VideoMetadataWriterThread(QThread):
	progress = Signal(int, int, str)
	finished = Signal(list)

	def __init__(self, db, rows):
		super().__init__()
		self.db = db
		self.rows = rows
		self.errors = []

	def run(self):
		video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
		exiftool_path = os.path.join(BASE_PATH, "tools", "exiftool", "exiftool.exe")
		video_rows = [row for row in self.rows if os.path.splitext(row[1])[1].lower() in video_exts]
		total = len(video_rows)
		for idx, row in enumerate(video_rows):
			if self.isInterruptionRequested():
				break
			id_, filepath, filename, title, description, tags, status, _ = row
			self.progress.emit(idx + 1, total, filename)
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
						self.errors.append(f"{filename}: exiftool error (no result)")
			except Exception as e:
				self.errors.append(f"{filename}: {e}")
		self.finished.emit(self.errors)

def write_metadata_to_images(db, parent=None):
	rows = db.get_all_files()
	errors = []
	dialog = ProgressDialog(parent, len(rows), "Writing Metadata to Images")
	def on_progress(idx, total, filename):
		dialog.update_progress(idx, filename)
		dialog.repaint()
		from PySide6.QtCore import QCoreApplication
		QCoreApplication.processEvents()
	def on_finished(errors):
		if errors:
			dialog.show_errors(errors)
		else:
			dialog.close()
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
	dialog = ProgressDialog(parent, len(video_rows), "Writing Metadata to Videos")
	def on_progress(idx, total, filename):
		dialog.update_progress(idx, filename)
		dialog.repaint()
		from PySide6.QtCore import QCoreApplication
		QCoreApplication.processEvents()
	def on_finished(errors):
		if errors:
			dialog.show_errors(errors)
		else:
			dialog.close()
	thread = VideoMetadataWriterThread(db, rows)
	thread.progress.connect(on_progress)
	thread.finished.connect(on_finished)
	dialog.set_thread(thread)
	QTimer.singleShot(0, thread.start)
	dialog.exec()