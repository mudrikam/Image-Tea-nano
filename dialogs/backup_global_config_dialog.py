from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QMessageBox, QFileDialog, QLabel, QLineEdit, QInputDialog, QSizePolicy, QSpacerItem
from PySide6.QtCore import Qt
import os
import zipfile
from datetime import datetime
from config import BASE_PATH
import re
import shutil
import qtawesome as qta
from dialogs.add_api_key_dialog import AddApiKeyDialog

EXCLUDED_CONFIG_FILES = { 'update_config.json', '__init__.py' }


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
		self.table.setHorizontalHeaderLabels(["Config Name", "Timestamp", "Actions"])
		self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
		self.table.setColumnWidth(1, 180)
		self.table.setColumnWidth(2, 120)
		self.table.setEditTriggers(QTableWidget.NoEditTriggers)
		self.table.setSelectionBehavior(QTableWidget.SelectRows)
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
		self.backups_dir = os.path.join(BASE_PATH, "backup_configs")
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
			item_name = QTableWidgetItem(fname)
			item_ts = QTableWidgetItem(ts)
			self.table.setItem(r, 0, item_name)
			self.table.setItem(r, 1, item_ts)
			actions_widget = QWidget()
			btn_layout = QHBoxLayout(actions_widget)
			btn_layout.setContentsMargins(0, 0, 0, 0)
			edit_icon = qta.icon('fa6s.pen-to-square')
			edit_btn = QPushButton(edit_icon, "")
			edit_btn.setToolTip("Edit backup name (timestamp preserved)")
			edit_btn.setFixedSize(28, 28)
			edit_btn.clicked.connect(lambda checked, p=path: self.edit_backup_name(p))
			btn_layout.addWidget(edit_btn)
			export_icon = qta.icon('fa6s.upload', color='#4e9e20')
			export_btn = QPushButton(export_icon, "")
			export_btn.setToolTip("Export backup to location")
			export_btn.setFixedSize(28, 28)
			export_btn.clicked.connect(lambda checked, p=path: self.export_backup(p))
			btn_layout.addWidget(export_btn)
			restore_icon = qta.icon('fa6s.rotate-right')
			restore_btn = QPushButton(restore_icon, "")
			restore_btn.setToolTip("Restore this backup")
			restore_btn.setFixedSize(28, 28)
			restore_btn.clicked.connect(lambda checked, p=path: self.confirm_and_restore(p))
			btn_layout.addWidget(restore_btn)
			delete_icon = qta.icon('fa6s.trash')
			delete_btn = QPushButton(delete_icon, "")
			delete_btn.setToolTip("Delete this backup")
			delete_btn.setFixedSize(28, 28)
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
			try:
				parent.backup_configs_action.setIcon(qta.icon('fa6s.file-zipper'))
			except Exception:
				pass
		QMessageBox.information(self, "Backup Created", f"Backup created:\n{zip_path}")
		self.refresh_backup_list()

	def backup_api_keys(self):
		dlg = AddApiKeyDialog(self)
		dlg.export_api_keys_csv()

	def create_backup(self):
		cfg_dir = os.path.join(BASE_PATH, 'configs')
		prefix = self.name_input.text().strip() if hasattr(self, 'name_input') else 'backup_configs'
		if prefix.lower().endswith('.zip'):
			prefix = prefix[:-4]
		if not prefix:
			prefix = 'backup_configs'
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		zip_name = f"{prefix}_{timestamp}.zip"
		zip_path = os.path.join(self.backups_dir, zip_name)
		zf = zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED)
		for root, dirs, files in os.walk(cfg_dir):
			for f in files:
				if f in EXCLUDED_CONFIG_FILES:
					continue
				full = os.path.join(root, f)
				if not os.path.isfile(full):
					continue
				arc = os.path.relpath(full, cfg_dir)
				zf.write(full, arc)
		zf.close()
		return zip_path

	def confirm_and_delete(self, path):
		reply = QMessageBox.question(self, "Delete Backup", f"Delete backup file?\n{path}", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
		if reply == QMessageBox.Yes:
			os.remove(path)
			self.refresh_backup_list()

	def export_backup(self, path):
		home = os.path.expanduser('~')
		default = os.path.join(home, os.path.basename(path))
		filename, _ = QFileDialog.getSaveFileName(self, "Export Backup As", default, "Zip files (*.zip);;All Files (*)")
		if filename:
			shutil.copy2(path, filename)
			QMessageBox.information(self, "Export Complete", f"Exported backup to:\n{filename}")

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
			for f in files:
				if f in EXCLUDED_CONFIG_FILES:
					continue
				full = os.path.join(root, f)
				if os.path.isfile(full):
					rel = os.path.relpath(full, configs_dir)
					file_list.append((rel, os.path.getmtime(full)))
		backups_dir = os.path.join(BASE_PATH, 'backup_configs')
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

	def edit_backup_name(self, path):
		fname = os.path.basename(path)
		prefix, timestamp = self._parse_backup_filename(fname)
		if not timestamp:
			QMessageBox.warning(self, "Invalid Backup", "Selected file is not a valid config backup.")
			return
		text, ok = QInputDialog.getText(self, "Edit Backup Name", "Edit backup name prefix (timestamp will be preserved):", text=prefix)
		if ok:
			new_prefix = text.strip()
			if not new_prefix:
				QMessageBox.warning(self, "Invalid Name", "Backup name prefix cannot be empty.")
				return
			new_name = f"{new_prefix}_{timestamp}.zip"
			new_path = os.path.join(self.backups_dir, new_name)
			os.rename(path, new_path)
			QMessageBox.information(self, "Renamed", f"Backup renamed to:\n{new_name}")
			self.refresh_backup_list()

	def confirm_and_restore(self, path):
		fname = os.path.basename(path)
		_, timestamp = self._parse_backup_filename(fname)
		if not timestamp:
			QMessageBox.warning(self, "Invalid Backup", "Selected file is not a valid config backup.")
			return
		reply = QMessageBox.question(self, "Restore Backup", f"This will replace current configs with backup:\n{path}\nA backup of current configs will be created first. Continue?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
		if reply == QMessageBox.Yes:
			pre_backup = self.create_backup()
			parent = self.parent()
			if parent and hasattr(parent, 'backup_configs_action'):
				try:
					parent.backup_configs_action.setIcon(qta.icon('fa6s.file-zipper'))
				except Exception:
					pass
			cfg_dir = os.path.join(BASE_PATH, 'configs')
			zf = zipfile.ZipFile(path, 'r')
			zf.extractall(cfg_dir)
			zf.close()
			QMessageBox.information(self, "Restore Complete", f"Restore complete. Pre-restore backup:\n{pre_backup}")
			self.refresh_backup_list()

	def restore_from_dialog(self):
		fname, _ = QFileDialog.getOpenFileName(self, "Select Backup to Restore", self.backups_dir, "Zip files (*.zip);;All Files (*)")
		if fname:
			self.confirm_and_restore(fname)


def configs_newer_than_latest_backup():
	configs_dir = os.path.join(BASE_PATH, 'configs')
	if not os.path.exists(configs_dir):
		return False
	file_mtimes = []
	for root, dirs, files in os.walk(configs_dir):
		for f in files:
			if f in EXCLUDED_CONFIG_FILES:
				continue
			full = os.path.join(root, f)
			if os.path.isfile(full):
				file_mtimes.append(os.path.getmtime(full))
	if not file_mtimes:
		return False
	backups_dir = os.path.join(BASE_PATH, 'backup_configs')
	if not os.path.exists(backups_dir):
		return True
	zip_files = [f for f in os.listdir(backups_dir) if f.lower().endswith('.zip')]
	if not zip_files:
		return True
	latest_zip = max(zip_files, key=lambda f: os.path.getmtime(os.path.join(backups_dir, f)))
	latest_mtime = os.path.getmtime(os.path.join(backups_dir, latest_zip))
	return min(file_mtimes) > latest_mtime

