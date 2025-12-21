from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QMessageBox, QFileDialog, QLabel, QLineEdit, QInputDialog, QSizePolicy, QSpacerItem
from PySide6.QtCore import Qt
import os
import zipfile
from datetime import datetime
from config import BASE_PATH
import re
import shutil
import json
import qtawesome as qta
from dialogs.add_api_key_dialog import AddApiKeyDialog

EXCLUDED_FILES = { 'update_config.json', '__init__.py', 'backup_configs' }


class BackupGlobalConfigDialog(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Backup Configs")
		self.setFixedSize(650, 420)
		main_layout = QVBoxLayout(self)
		top_layout = QHBoxLayout()
		backup_icon = qta.icon('fa6s.file-zipper')
		self.backup_btn = QPushButton(backup_icon, "Backup Configs")
		self.backup_btn.clicked.connect(self.create_and_refresh)
		top_layout.addWidget(self.backup_btn)
		restore_icon = qta.icon('fa6s.rotate-right')
		self.restore_btn = QPushButton(restore_icon, "Restore From File...")
		self.restore_btn.clicked.connect(self.restore_from_dialog)
		top_layout.addWidget(self.restore_btn)
		export_api_icon = qta.icon('fa6s.file-csv')
		self.export_api_btn = QPushButton(export_api_icon, "Backup API Keys")
		self.export_api_btn.setToolTip("Export API keys to CSV")
		self.export_api_btn.clicked.connect(self.backup_api_keys)
		top_layout.addWidget(self.export_api_btn)
		clear_icon = qta.icon('fa6s.trash', color='#e61515')
		self.clear_all_btn = QPushButton(clear_icon, "Clear Backups")
		self.clear_all_btn.setToolTip("Delete all backups (permanent) — consider exporting first")
		self.clear_all_btn.clicked.connect(self.clear_all_backups)
		top_layout.addWidget(self.clear_all_btn)
		close_icon = qta.icon('fa6s.xmark')
		self.close_btn = QPushButton(close_icon, "Close")
		self.close_btn.clicked.connect(self.accept)
		top_layout.addWidget(self.close_btn)
		main_layout.addLayout(top_layout)
		name_row = QHBoxLayout()
		name_row.setAlignment(Qt.AlignLeft)
		name_label = QLabel("Backup name prefix")
		name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
		self.name_input = QLineEdit("backup_configs")
		self.name_input.setMaximumWidth(260)
		self.name_input.setAlignment(Qt.AlignLeft)
		name_row.addWidget(name_label)
		name_row.addWidget(self.name_input)
		name_row.addStretch()
		main_layout.addLayout(name_row)
		self.table = QTableWidget()
		self.table.setColumnCount(3)
		self.table.setHorizontalHeaderLabels(["Backup Name", "Timestamp", "Actions"])
		self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
		self.table.setColumnWidth(1, 180)
		self.table.setColumnWidth(2, 120)
		self.table.setEditTriggers(QTableWidget.NoEditTriggers)
		self.table.setSelectionBehavior(QTableWidget.SelectRows)
		self.table.setSortingEnabled(True)
		self.table.horizontalHeader().setSectionsClickable(True)
		main_layout.addWidget(self.table)
		stats_layout = QHBoxLayout()
		self.stats_count_label = QLabel("Backups: 0")
		self.stats_oldest_label = QLabel("Oldest: N/A")
		self.stats_newest_label = QLabel("Newest: N/A")
		stats_layout.addWidget(self.stats_count_label)
		stats_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
		stats_layout.addWidget(self.stats_oldest_label)
		stats_layout.addWidget(self.stats_newest_label)
		main_layout.addLayout(stats_layout)
		self.newer_label = QLabel("")
		self.newer_label.setWordWrap(True)
		main_layout.addWidget(self.newer_label)
		self.backups_dir = os.path.join(BASE_PATH, "configs", "backup_configs")
		os.makedirs(self.backups_dir, exist_ok=True)
		self.refresh_backup_list()

	def list_backups(self):
		files = [f for f in os.listdir(self.backups_dir) if f.lower().endswith('.zip')]
		files.sort(reverse=True)
		return files

	def refresh_backup_list(self):
		files = self.list_backups()
		self.table.setRowCount(len(files))
		timestamps = []
		for r, fname in enumerate(files):
			path = os.path.join(self.backups_dir, fname)
			mtime = os.path.getmtime(path)
			timestamps.append(mtime)
			ts = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
			prefix, _ = self._parse_backup_filename(fname)
			if prefix:
				display = prefix
			else:
				display = fname[:-4] if fname.lower().endswith('.zip') else fname
			item_name = QTableWidgetItem(display)
			item_ts = QTableWidgetItem(ts)
			self.table.setItem(r, 0, item_name)
			self.table.setItem(r, 1, item_ts)
			actions_widget = QWidget()
			btn_layout = QHBoxLayout(actions_widget)
			btn_layout.setContentsMargins(0, 0, 0, 0)
			edit_icon = qta.icon('fa6s.pen-to-square')
			edit_btn = QPushButton(edit_icon, "")
			edit_btn.setToolTip("Edit backup name (timestamp preserved)")
			edit_btn.clicked.connect(lambda checked, p=path: self.edit_backup_name(p))
			btn_layout.addWidget(edit_btn)
			export_icon = qta.icon('fa6s.upload', color='#4e9e20')
			export_btn = QPushButton(export_icon, "")
			export_btn.setToolTip("Export backup to location")
			export_btn.clicked.connect(lambda checked, p=path: self.export_backup(p))
			btn_layout.addWidget(export_btn)
			restore_icon = qta.icon('fa6s.rotate-right')
			restore_btn = QPushButton(restore_icon, "")
			restore_btn.setToolTip("Restore this backup")
			restore_btn.clicked.connect(lambda checked, p=path: self.confirm_and_restore(p))
			btn_layout.addWidget(restore_btn)
			delete_icon = qta.icon('fa6s.trash')
			delete_btn = QPushButton(delete_icon, "")
			delete_btn.setToolTip("Delete this backup")
			delete_btn.clicked.connect(lambda checked, p=path: self.confirm_and_delete(p))
			btn_layout.addWidget(delete_btn)
			btn_layout.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
			self.table.setCellWidget(r, 2, actions_widget)
		if timestamps:
			count = len(timestamps)
			oldest = datetime.fromtimestamp(min(timestamps)).strftime('%A, %b %d %Y %H:%M:%S')
			newest = datetime.fromtimestamp(max(timestamps)).strftime('%A, %b %d %Y %H:%M:%S')
			self.stats_count_label.setText(f"Backups: {count}")
			self.stats_oldest_label.setText(f"Oldest: {oldest}")
			self.stats_newest_label.setText(f"Newest: {newest}")
		else:
			self.stats_count_label.setText("Backups: 0")
			self.stats_oldest_label.setText("Oldest: N/A")
			self.stats_newest_label.setText("Newest: N/A")
		newer = self.get_configs_newer_than_latest_backup_files()
		if newer:
			if len(newer) <= 5:
				text = "Configs newer than latest backup: " + ", ".join(newer)
			else:
				text = "Configs newer than latest backup: " + ", ".join(newer[:5]) + f" and {len(newer)-5} more"
			self.newer_label.setText(text)
		else:
			self.newer_label.setText("All configs are backed up or no configs present.")

	def create_and_refresh(self):
		zip_path = self.create_backup()
		parent = self.parent()
		if parent and hasattr(parent, 'backup_configs_action'):
			parent.backup_configs_action.setIcon(qta.icon('fa6s.file-zipper'))
		fname = os.path.basename(zip_path)
		prefix, _ = self._parse_backup_filename(fname)
		display = prefix if prefix else (fname[:-4] if fname.lower().endswith('.zip') else fname)
		msg = f"Backup created: <span style='color:#4e9e20'><b>{display}</b></span>"
		mb = QMessageBox(self)
		mb.setWindowTitle("Backup Created")
		mb.setIcon(QMessageBox.Information)
		mb.setTextFormat(Qt.RichText)
		mb.setText(msg)
		btn_close = QPushButton("Close")
		btn_close.setIcon(qta.icon('fa6s.xmark'))
		mb.addButton(btn_close, QMessageBox.AcceptRole)
		mb.exec()
		self.refresh_backup_list()

	def backup_api_keys(self):
		dlg = AddApiKeyDialog(self)
		dlg.export_api_keys_csv()

	def create_backup(self, prefix=None):
		cfg_dir = os.path.join(BASE_PATH, 'configs')
		if prefix is None:
			prefix = self.name_input.text().strip() if hasattr(self, 'name_input') else 'backup_configs'
		if prefix.lower().endswith('.zip'):
			prefix = prefix[:-4]
		if not prefix:
			prefix = 'backup_configs'
		final_prefix = self._compute_numbered_prefix(prefix)
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		zip_name = f"{final_prefix}_{timestamp}.zip"
		zip_path = os.path.join(self.backups_dir, zip_name)
		zf = zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED)
		for root, dirs, files in os.walk(cfg_dir):
			dirs[:] = [d for d in dirs if d not in EXCLUDED_FILES]
			for f in files:
				if f in EXCLUDED_FILES:
					continue
				full = os.path.join(root, f)
				if not os.path.isfile(full):
					continue
				arc = os.path.relpath(full, cfg_dir)
				zf.write(full, arc)
		zf.close()
		return zip_path

	def _compute_numbered_prefix(self, base_prefix):
		m = re.match(r'^(.*?)(?:_(\d{3}))?$', base_prefix)
		base_name = m.group(1)
		files = self.list_backups()
		max_n = 0
		for f in files:
			p, _ = self._parse_backup_filename(f)
			if not p:
				continue
			m2 = re.match(r'^' + re.escape(base_name) + r'_(\d{3})$', p)
			if m2:
				n = int(m2.group(1))
				if n > max_n:
					max_n = n
		return f"{base_name}_{max_n+1:03d}"

	def confirm_and_delete(self, path):
		fname = os.path.basename(path)
		prefix, _ = self._parse_backup_filename(fname)
		display = prefix if prefix else (fname[:-4] if fname.lower().endswith('.zip') else fname)
		msg = f"Delete backup <b><span style='color:#4e9e20'>{display}</span></b>? This action cannot be undone."
		mb = QMessageBox(self)
		mb.setWindowTitle("Delete Backup")
		mb.setIcon(QMessageBox.Warning)
		mb.setTextFormat(Qt.RichText)
		mb.setText(msg)
		btn_yes = QPushButton("Delete")
		btn_yes.setIcon(qta.icon('fa6s.trash'))
		btn_no = QPushButton("Cancel")
		btn_no.setIcon(qta.icon('fa6s.xmark'))
		mb.addButton(btn_yes, QMessageBox.AcceptRole)
		mb.addButton(btn_no, QMessageBox.RejectRole)
		mb.setDefaultButton(btn_no)
		mb.exec()
		if mb.clickedButton() == btn_yes:
			os.remove(path)
			self.refresh_backup_list()

	def clear_all_backups(self):
		msg = (
			"This will permanently delete ALL Image Tea backups.\n"
			"This action cannot be undone. Consider exporting backups before proceeding.\n\n"
			"Do you want to continue?"
		)
		mb = QMessageBox(self)
		mb.setWindowTitle("Delete All Backups")
		mb.setIcon(QMessageBox.Warning)
		mb.setText(msg)
		btn_yes = QPushButton("Delete")
		btn_yes.setIcon(qta.icon('fa6s.trash'))
		btn_no = QPushButton("Cancel")
		btn_no.setIcon(qta.icon('fa6s.xmark'))
		mb.addButton(btn_yes, QMessageBox.AcceptRole)
		mb.addButton(btn_no, QMessageBox.RejectRole)
		mb.setDefaultButton(btn_no)
		mb.exec()
		if mb.clickedButton() == btn_yes:
			files = self.list_backups()
			for f in files:
				os.remove(os.path.join(self.backups_dir, f))
			self.refresh_backup_list()
			mb2 = QMessageBox(self)
			mb2.setWindowTitle("Deleted")
			mb2.setIcon(QMessageBox.Information)
			mb2.setText("All backups have been permanently deleted.")
			btn_close = QPushButton("Close")
			btn_close.setIcon(qta.icon('fa6s.xmark'))
			mb2.addButton(btn_close, QMessageBox.AcceptRole)
			mb2.exec()

	def export_backup(self, path):
		home = os.path.expanduser('~')
		default = os.path.join(home, os.path.basename(path))
		filename, _ = QFileDialog.getSaveFileName(self, "Export Backup As", default, "Zip files (*.zip);;All Files (*)")
		if filename:
			shutil.copy2(path, filename)
			fname = os.path.basename(path)
			prefix, _ = self._parse_backup_filename(fname)
			display = prefix if prefix else (fname[:-4] if fname.lower().endswith('.zip') else fname)
			msg = f"Exported backup <span style='color:#4e9e20'><b>{display}</b></span> to:<br/>{filename}"
			mb = QMessageBox(self)
			mb.setWindowTitle("Export Complete")
			mb.setIcon(QMessageBox.Information)
			mb.setTextFormat(Qt.RichText)
			mb.setText(msg)
			btn_close = QPushButton("Close")
			btn_close.setIcon(qta.icon('fa6s.xmark'))
			mb.addButton(btn_close, QMessageBox.AcceptRole)
			mb.exec()

	def _parse_backup_filename(self, filename):
		m = re.match(r'^(.*)_(\d{8}_\d{6})\.zip$', filename)
		if not m:
			return None, None
		return m.group(1), m.group(2)

	def get_configs_newer_than_latest_backup_files(self):
		configs_dir = os.path.join(BASE_PATH, 'configs')
		if not os.path.exists(configs_dir):
			return []
		file_list = []
		for root, dirs, files in os.walk(configs_dir):
			dirs[:] = [d for d in dirs if d not in EXCLUDED_FILES]
			for f in files:
				if f in EXCLUDED_FILES:
					continue
				full = os.path.join(root, f)
				if os.path.isfile(full):
					rel = os.path.relpath(full, configs_dir)
					file_list.append((rel, os.path.getmtime(full)))
		backups_dir = os.path.join(BASE_PATH, 'configs', 'backup_configs')
		if not os.path.exists(backups_dir):
			return [f for f, _ in file_list]
		zip_files = [f for f in os.listdir(backups_dir) if f.lower().endswith('.zip')]
		if not zip_files:
			return [f for f, _ in file_list]
		latest_zip = max(zip_files, key=lambda f: os.path.getmtime(os.path.join(backups_dir, f)))
		latest_mtime = os.path.getmtime(os.path.join(backups_dir, latest_zip))
		newer = [f for f, m in file_list if m > latest_mtime]
		newer.sort()
		return newer

	def prompt_edit_backup_name(self, prefix):
		dlg = QDialog(self)
		dlg.setWindowTitle("Edit Backup Name")
		layout = QVBoxLayout(dlg)
		label = QLabel("Edit backup name prefix (timestamp will be preserved):")
		edit = QLineEdit(prefix)
		layout.addWidget(label)
		layout.addWidget(edit)
		btn_row = QHBoxLayout()
		btn_row.addStretch()
		btn_save = QPushButton(qta.icon('fa6s.check'), "Save")
		btn_cancel = QPushButton(qta.icon('fa6s.xmark'), "Cancel")
		btn_save.clicked.connect(dlg.accept)
		btn_cancel.clicked.connect(dlg.reject)
		btn_row.addWidget(btn_save)
		btn_row.addWidget(btn_cancel)
		layout.addLayout(btn_row)
		res = dlg.exec()
		return edit.text(), (res == QDialog.Accepted)

	def edit_backup_name(self, path):
		fname = os.path.basename(path)
		prefix, timestamp = self._parse_backup_filename(fname)
		if not timestamp:
			mb = QMessageBox(self)
			mb.setWindowTitle("Invalid Backup")
			mb.setIcon(QMessageBox.Warning)
			mb.setText("Selected file is not a valid config backup.")
			btn_close = QPushButton("Close")
			btn_close.setIcon(qta.icon('fa6s.xmark'))
			mb.addButton(btn_close, QMessageBox.AcceptRole)
			mb.exec()
			return
		text, ok = self.prompt_edit_backup_name(prefix)
		if ok:
			new_prefix = text.strip()
			if not new_prefix:
				mb = QMessageBox(self)
				mb.setWindowTitle("Invalid Name")
				mb.setIcon(QMessageBox.Warning)
				mb.setText("Backup name prefix cannot be empty.")
				btn_close = QPushButton("Close")
				btn_close.setIcon(qta.icon('fa6s.xmark'))
				mb.addButton(btn_close, QMessageBox.AcceptRole)
				mb.exec()
				return
			new_name = f"{new_prefix}_{timestamp}.zip"
			new_path = os.path.join(self.backups_dir, new_name)
			os.rename(path, new_path)
			msg = f"Backup renamed to: <span style='color:#4e9e20'><b>{new_prefix}</b></span>"
			mb = QMessageBox(self)
			mb.setWindowTitle("Renamed")
			mb.setIcon(QMessageBox.Information)
			mb.setTextFormat(Qt.RichText)
			mb.setText(msg)
			btn_close = QPushButton("Close")
			btn_close.setIcon(qta.icon('fa6s.xmark'))
			mb.addButton(btn_close, QMessageBox.AcceptRole)
			mb.exec()
			self.refresh_backup_list()
			return

	def confirm_and_restore(self, path):
		fname = os.path.basename(path)
		_, timestamp = self._parse_backup_filename(fname)
		if not timestamp:
			mb = QMessageBox(self)
			mb.setWindowTitle("Invalid Backup")
			mb.setIcon(QMessageBox.Warning)
			mb.setText("Selected file is not a valid config backup.")
			btn_close = QPushButton("Close")
			btn_close.setIcon(qta.icon('fa6s.xmark'))
			mb.addButton(btn_close, QMessageBox.AcceptRole)
			mb.exec()
			return
		temp_base = os.path.join(BASE_PATH, 'temp', 'backup_config')
		os.makedirs(temp_base, exist_ok=True)
		sub = datetime.now().strftime('%Y%m%d_%H%M%S')
		tmpdir = os.path.join(temp_base, f"restore_{sub}")
		os.makedirs(tmpdir, exist_ok=True)
		try:
			with zipfile.ZipFile(path, 'r') as zf:
				for m in zf.infolist():
					dest = os.path.join(tmpdir, m.filename)
					abs_dest = os.path.abspath(dest)
					abs_tmp = os.path.abspath(tmpdir)
					if not (abs_dest == abs_tmp or abs_dest.startswith(abs_tmp + os.sep)):
						raise ValueError("Illegal file path in backup (possible Zip Slip)")
					if m.filename.endswith('/'):
						os.makedirs(abs_dest, exist_ok=True)
						continue
					os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
					with zf.open(m) as src, open(abs_dest, 'wb') as dst:
						dst.write(src.read())
		except Exception as e:
			print(f"Error preparing backup contents for restore: {e}")
			shutil.rmtree(tmpdir, ignore_errors=True)
			return
		temp_app = os.path.join(tmpdir, 'app_config.json')
		current_app = os.path.join(BASE_PATH, 'configs', 'app_config.json')
		if not os.path.exists(temp_app) or not os.path.exists(current_app):
			print('Error: app_config.json missing in backup or current configs')
			shutil.rmtree(tmpdir, ignore_errors=True)
			return
		try:
			with open(temp_app, 'r', encoding='utf-8') as f:
				tmp_json = json.load(f)
			with open(current_app, 'r', encoding='utf-8') as f:
				cur_json = json.load(f)
		except Exception as e:
			print(f"Error reading configuration files: {e}")
			shutil.rmtree(tmpdir, ignore_errors=True)
			return
		backup_ver = tmp_json['version']
		current_ver = cur_json['version']
		if backup_ver != current_ver:
			msg_html = (
				f"<p>The backup appears to be from version <b>{backup_ver}</b>.<br/>"
				f"Your current configuration version is <b>{current_ver}</b>.</p>"
				"<p><b>Important:</b> Different versions may include changes to configuration keys or formats. Restoring may alter behavior and can trigger update notifications (this is expected).</p>"
				"<p>Do you understand these implications and want to continue?</p>"
			)
			mb = QMessageBox(self)
			mb.setWindowTitle("Restore From Different Version")
			mb.setIcon(QMessageBox.Warning)
			mb.setTextFormat(Qt.RichText)
			mb.setText(msg_html)
			btn_yes = QPushButton("Yes")
			btn_yes.setIcon(qta.icon('fa6s.check'))
			btn_no = QPushButton("No")
			btn_no.setIcon(qta.icon('fa6s.xmark'))
			mb.addButton(btn_yes, QMessageBox.AcceptRole)
			mb.addButton(btn_no, QMessageBox.RejectRole)
			mb.setDefaultButton(btn_no)
			mb.exec()
			if mb.clickedButton() != btn_yes:
				shutil.rmtree(tmpdir)
				return
		ask_msg = "Skip creating pre/post backups around this restore? (Yes = Skip backups, No = Create backups)"
		mb = QMessageBox(self)
		mb.setWindowTitle("Pre/Post Backups")
		mb.setIcon(QMessageBox.Question)
		mb.setText(ask_msg)
		btn_yes = QPushButton("Yes")
		btn_yes.setIcon(qta.icon('fa6s.check'))
		btn_no = QPushButton("No")
		btn_no.setIcon(qta.icon('fa6s.xmark'))
		mb.addButton(btn_yes, QMessageBox.AcceptRole)
		mb.addButton(btn_no, QMessageBox.RejectRole)
		mb.setDefaultButton(btn_no)
		mb.exec()
		skip_backups = (mb.clickedButton() == btn_yes)
		pre_backup = None
		post_backup = None
		if not skip_backups:
			name_text = self.name_input.text().strip()
			if not name_text:
				print("Error: Backup name prefix is empty; cannot create pre/post backups.")
				shutil.rmtree(tmpdir, ignore_errors=True)
				return
			pre_prefix = f"pre_restore_{name_text}"
			try:
				pre_backup = self.create_backup(prefix=pre_prefix)
			except Exception as e:
				print(f"Error creating pre-restore backup: {e}")
				shutil.rmtree(tmpdir, ignore_errors=True)
				return
		parent = self.parent()
		if parent and hasattr(parent, 'backup_configs_action'):
			parent.backup_configs_action.setIcon(qta.icon('fa6s.file-zipper'))
		cfg_dir = os.path.join(BASE_PATH, 'configs')
		try:
			with zipfile.ZipFile(path, 'r') as zf:
				for m in zf.infolist():
					name = os.path.basename(m.filename)
					if name in EXCLUDED_FILES:
						continue
					dest = os.path.join(cfg_dir, m.filename)
					abs_dest = os.path.abspath(dest)
					abs_cfg = os.path.abspath(cfg_dir)
					if not (abs_dest == abs_cfg or abs_dest.startswith(abs_cfg + os.sep)):
						raise ValueError("Illegal file path in backup (possible Zip Slip)")
					if m.filename.endswith('/'):
						os.makedirs(abs_dest, exist_ok=True)
						continue
					os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
					with zf.open(m) as src, open(abs_dest, 'wb') as dst:
						dst.write(src.read())
		except Exception as e:
			print(f"Error during restore operation: {e}")
			shutil.rmtree(tmpdir, ignore_errors=True)
			return
		if not skip_backups:
			post_prefix = f"post_restore_{name_text}"
			try:
				post_backup = self.create_backup(prefix=post_prefix)
			except Exception as e:
				print(f"Error creating post-restore backup: {e}")
				shutil.rmtree(tmpdir, ignore_errors=True)
				return
		shutil.rmtree(tmpdir)
		if skip_backups:
			msg = "Restore complete. Pre/post backups were skipped."
		else:
			pre_name = os.path.basename(pre_backup)
			post_name = os.path.basename(post_backup)
			pre_prefix, _ = self._parse_backup_filename(pre_name)
			post_prefix, _ = self._parse_backup_filename(post_name)
			pre_display = pre_prefix if pre_prefix else (pre_name[:-4] if pre_name.lower().endswith('.zip') else pre_name)
			post_display = post_prefix if post_prefix else (post_name[:-4] if post_name.lower().endswith('.zip') else post_name)
			msg = (
				f"Restore complete.<br/>Pre-restore backup: <span style='color:#4e9e20'><b>{pre_display}</b></span><br/>"
				f"Post-restore backup: <span style='color:#4e9e20'><b>{post_display}</b></span>"
			)
		mb = QMessageBox(self)
		mb.setWindowTitle("Restore Complete")
		mb.setIcon(QMessageBox.Information)
		mb.setTextFormat(Qt.RichText)
		mb.setText(msg)
		btn_close = QPushButton("Close")
		btn_close.setIcon(qta.icon('fa6s.xmark'))
		mb.addButton(btn_close, QMessageBox.AcceptRole)
		mb.exec()
		self.refresh_backup_list()

	def restore_from_dialog(self):
		home = os.path.expanduser('~')
		fname, _ = QFileDialog.getOpenFileName(self, "Select Backup to Restore", home, "Zip files (*.zip);;All Files (*)")
		if fname:
			self.confirm_and_restore(fname)


def configs_newer_than_latest_backup():
	configs_dir = os.path.join(BASE_PATH, 'configs')
	if not os.path.exists(configs_dir):
		return False
	file_mtimes = []
	for root, dirs, files in os.walk(configs_dir):
		dirs[:] = [d for d in dirs if d not in EXCLUDED_FILES]
		for f in files:
			if f in EXCLUDED_FILES:
				continue
			full = os.path.join(root, f)
			if os.path.isfile(full):
				file_mtimes.append(os.path.getmtime(full))
	if not file_mtimes:
		return False
	backups_dir = os.path.join(BASE_PATH, 'configs', 'backup_configs')
	if not os.path.exists(backups_dir):
		return True
	zip_files = [f for f in os.listdir(backups_dir) if f.lower().endswith('.zip')]
	if not zip_files:
		return True
	latest_zip = max(zip_files, key=lambda f: os.path.getmtime(os.path.join(backups_dir, f)))
	latest_mtime = os.path.getmtime(os.path.join(backups_dir, latest_zip))
	return max(file_mtimes) > latest_mtime

