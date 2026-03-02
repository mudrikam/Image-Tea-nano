from PySide6.QtWidgets import (
	QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
	QHeaderView, QPushButton, QLabel, QSpinBox, QSpacerItem, QSizePolicy,
	QApplication, QProgressBar, QComboBox, QMessageBox, QFileDialog,
	QWidget, QMenu, QToolTip, QTabWidget, QSplitter, QTextEdit,
	QListWidget, QListWidgetItem, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QAction, QCursor, QKeySequence, QColor, QFont
import os
import json
import csv
import time
from datetime import datetime
from config import BASE_PATH
import qtawesome as qta
from ui.api_key_section import ApiKeySectionWidget
from ui.theme_system import theme


class PromptGeneratorWorker(QThread):
	"""Worker thread for prompt generation by reference (image files)"""
	progress_updated = Signal(str)
	progress_value_changed = Signal(int)
	finished = Signal(int)
	error_occurred = Signal(str)
	prompt_added = Signal()
	file_processing = Signal(str)

	def __init__(self, db, api_key, service, model):
		super().__init__()
		self.db = db
		self.api_key = api_key
		self.service = service
		self.model = model
		self.stop_flag = {'stop': False}

	def stop(self):
		self.stop_flag['stop'] = True

	def run(self):
		try:
			from helpers.tools.prompt_generator_helper import generate_prompts_batch

			def progress_callback(message, progress_percent=None):
				self.progress_updated.emit(message)
				if progress_percent is not None:
					self.progress_value_changed.emit(int(progress_percent))

			def prompt_saved_callback():
				self.prompt_added.emit()

			def file_callback(filename):
				self.file_processing.emit(filename)

			provider_endpoint = None
			try:
				rows = self.db.get_all_api_keys()
				for r in rows:
					if len(r) >= 2 and r[1] == self.api_key and str(r[0]).lower() == (self.service or '').lower():
						provider_endpoint = r[6] if len(r) > 6 else None
						break
			except Exception as e:
				print(f"Error resolving provider_endpoint for Prompt Generator: {e}")

			if self.folder_files is not None:
				from helpers.tools.prompt_generator_helper import generate_prompts_from_folder
				total_generated = generate_prompts_from_folder(
					db=self.db,
					api_key=self.api_key,
					service=self.service,
					model=self.model,
					folder_files=self.folder_files,
					stop_flag=self.stop_flag,
					progress_callback=progress_callback,
					prompt_saved_callback=prompt_saved_callback,
					file_callback=file_callback,
					provider_endpoint=provider_endpoint
				)
			else:
				total_generated = generate_prompts_batch(
					db=self.db,
					api_key=self.api_key,
					service=self.service,
					model=self.model,
					file_ids=None,
					stop_flag=self.stop_flag,
					progress_callback=progress_callback,
					prompt_saved_callback=prompt_saved_callback,
					file_callback=file_callback,
					provider_endpoint=provider_endpoint
				)
			self.finished.emit(total_generated)
		except Exception as e:
			self.error_occurred.emit(str(e))


class PromptGeneratorParametersWorker(QThread):
	"""Worker thread for prompt generation by parameters (no reference images)"""
	progress_updated = Signal(str)
	progress_value_changed = Signal(int)
	finished = Signal(int)
	error_occurred = Signal(str)
	prompt_added = Signal()

	def __init__(self, db, api_key, service, model):
		super().__init__()
		self.db = db
		self.api_key = api_key
		self.service = service
		self.model = model
		self.stop_flag = {'stop': False}

	def stop(self):
		self.stop_flag['stop'] = True

	def run(self):
		try:
			from helpers.tools.prompt_generator_helper import generate_prompts_batch_by_parameters

			def progress_callback(message, progress_percent=None):
				self.progress_updated.emit(message)
				if progress_percent is not None:
					self.progress_value_changed.emit(int(progress_percent))

			def prompt_saved_callback():
				self.prompt_added.emit()

			provider_endpoint = None
			try:
				rows = self.db.get_all_api_keys()
				for r in rows:
					if len(r) >= 2 and r[1] == self.api_key and str(r[0]).lower() == (self.service or '').lower():
						provider_endpoint = r[6] if len(r) > 6 else None
						break
			except Exception as e:
				print(f"Error resolving provider_endpoint for Parameters Worker: {e}")

			total_generated = generate_prompts_batch_by_parameters(
				db=self.db,
				api_key=self.api_key,
				service=self.service,
				model=self.model,
				stop_flag=self.stop_flag,
				progress_callback=progress_callback,
				prompt_saved_callback=prompt_saved_callback,
				provider_endpoint=provider_endpoint
			)
			self.finished.emit(total_generated)
		except Exception as e:
			self.error_occurred.emit(str(e))


class CSVImportWorker(QThread):
	"""Worker thread for CSV import"""
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
			self.progress_updated.emit("Reading CSV file...")
			self.progress_value_changed.emit(10)
			imported_prompts = []
			with open(self.filename, 'r', encoding='utf-8') as csvfile:
				total_lines = sum(1 for _ in csvfile)
				csvfile.seek(0)
				self.progress_updated.emit(f"Processing {total_lines} rows...")
				self.progress_value_changed.emit(20)
				reader = csv.reader(csvfile)
				for row_num, row in enumerate(reader, 1):
					progress = 20 + int((row_num / total_lines) * 60)
					self.progress_value_changed.emit(progress)
					self.progress_updated.emit(f"Processing row {row_num}/{total_lines}...")
					if row and len(row) > 0:
						prompt_text = row[0].strip()
						if not prompt_text:
							continue
						if prompt_text.startswith('"') and prompt_text.endswith('"'):
							prompt_text = prompt_text[1:-1]
						elif prompt_text.startswith("'") and prompt_text.endswith("'"):
							prompt_text = prompt_text[1:-1]
						if len(prompt_text) >= 10:
							imported_prompts.append(prompt_text)
			if not imported_prompts:
				self.error_occurred.emit("No valid prompts found in the CSV file.")
				return
			self.progress_updated.emit(f"Saving {len(imported_prompts)} prompts to database...")
			self.progress_value_changed.emit(85)
			imported_count = 0
			for i, prompt_text in enumerate(imported_prompts):
				try:
					self.db.add_external_prompt(prompt_text)
					imported_count += 1
					progress = 85 + int((i / len(imported_prompts)) * 10)
					self.progress_value_changed.emit(progress)
				except Exception as e:
					print(f"Failed to import prompt: {prompt_text[:50]}... - {e}")
			self.progress_updated.emit("Import completed!")
			self.progress_value_changed.emit(100)
			self.finished.emit(imported_count)
		except Exception as e:
			self.error_occurred.emit(str(e))


class CSVImportProgressDialog(QDialog):
	"""Progress dialog for prompt import"""
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Importing Prompts")
		self.setFixedSize(450, 150)
		self.setModal(True)
		layout = QVBoxLayout(self)
		self.status_label = QLabel("Preparing import...")
		layout.addWidget(self.status_label)
		self.progress_bar = QProgressBar()
		self.progress_bar.setRange(0, 100)
		self.progress_bar.setValue(0)
		layout.addWidget(self.progress_bar)
		self.cancel_btn = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
		self.cancel_btn.clicked.connect(self.reject)
		layout.addWidget(self.cancel_btn)
		self.worker = None

	def update_progress(self, message):
		self.status_label.setText(message)

	def update_progress_value(self, value):
		self.progress_bar.setValue(value)

	def import_finished(self, imported_count):
		self.status_label.setText(f"Successfully imported {imported_count} prompts!")
		self.cancel_btn.setText("Close")
		QTimer.singleShot(2000, self.accept)


class PromptGeneratorDialog(QDialog):
	"""Prompt Generator with split layout: left action tabs, right table/logs/edit tabs."""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Prompt Generator")
		self.setMinimumSize(800, 500)
		self.page_size = 20
		self.current_page = 1
		self.prompt_data = []
		self.total_prompts = 0
		self.worker = None
		self.is_generating = False
		self.current_generating_file = None
		self.gen_icon = qta.icon('fa6s.wand-magic-sparkles')
		self.stop_icon = qta.icon('fa6s.stop')
		self.last_prompt_count = 0
		self.api_key = None
		self.selected_service = None
		self.selected_model_name = None
		self._editing_prompt_id = None
		self._gen_start_time = None
		self._gen_estimated_total = 0
		self._gen_prompts_at_start = 0
		self._ref_folder_files = []
		self._random_mode_active = False
		self._random_requests_remaining = 0
		self._random_original_num_requests = 1
		self._random_total_generated = 0

		from database import db_operation
		self.db = db_operation.ImageTeaDB()

		self._build_ui()
		self.load_prompts_from_db()
		self.update_pagination()
		self._load_parameters_from_config()

		self.refresh_timer = QTimer()
		self.refresh_timer.timeout.connect(self.refresh_table_if_needed)
		if self.db:
			self.last_prompt_count = self.db.get_generated_prompts_count()
		self.refresh_timer.start(1000)

		self._stats_tick_timer = QTimer()
		self._stats_tick_timer.timeout.connect(self.update_stats_display)

	def _build_ui(self):
		main_layout = QVBoxLayout(self)
		main_layout.setSpacing(6)

		if self.db:
			self.api_key_section = ApiKeySectionWidget(self.db, self)
			main_layout.addWidget(self.api_key_section)
			self.api_key_section.api_key_changed.connect(self.on_api_key_changed)
			self.api_key = self.api_key_section.get_current_api_key()
			self.selected_service = self.api_key_section.get_current_service()
			self.selected_model_name = self.api_key_section.get_current_model()

		splitter = QSplitter(Qt.Horizontal)
		splitter.setHandleWidth(6)

		left_widget = self._build_left_panel()
		right_widget = self._build_right_panel()

		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([320, 780])
		main_layout.addWidget(splitter, 1)

		actions_layout = self._build_actions_bar()
		main_layout.addLayout(actions_layout)

		self.progress_bar = QProgressBar()
		self.progress_bar.setVisible(False)
		self.progress_bar.setMinimum(0)
		self.progress_bar.setMaximum(100)
		self.progress_bar.setValue(0)
		main_layout.addWidget(self.progress_bar)

	def _build_left_panel(self):
		self.left_tabs = QTabWidget()
		self.left_tabs.setTabPosition(QTabWidget.North)
		self.left_tabs.setMinimumWidth(340)
		self.left_tabs.currentChanged.connect(self._on_left_tab_changed)

		ref_tab = self._build_reference_tab()
		params_tab = self._build_parameters_tab()

		self.left_tabs.addTab(ref_tab, qta.icon('fa6s.image'), " By Reference")
		self.left_tabs.addTab(params_tab, qta.icon('fa6s.sliders'), " By Parameters")
		return self.left_tabs

	def _build_reference_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)
		layout.setSpacing(8)
		layout.setContentsMargins(8, 8, 8, 8)

		cfg = self._load_ai_config()
		pg_section = cfg.get('prompt_generator', {}) if isinstance(cfg, dict) else {}
		settings = pg_section.get('settings', {}) if isinstance(pg_section, dict) else {}
		prompt_types = pg_section.get('prompt_types', {}) if isinstance(pg_section, dict) else {}
		aspect_ratios = pg_section.get('aspect_ratios', {}) if isinstance(pg_section, dict) else {}

		def add_row(label_text, widget_obj):
			h = QHBoxLayout()
			lbl = QLabel(label_text)
			lbl.setMinimumWidth(120)
			h.addWidget(lbl)
			h.addWidget(widget_obj, 1)
			layout.addLayout(h)

		self.ref_source_combo = QComboBox()
		self.ref_source_combo.addItem("Load from Database", "database")
		self.ref_source_combo.addItem("Loaded Folder", "folder")
		add_row("Source", self.ref_source_combo)

		self._ref_folder_row = QWidget()
		self._ref_folder_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		_frl = QHBoxLayout(self._ref_folder_row)
		_frl.setContentsMargins(0, 0, 0, 0)
		_frl.setSpacing(4)
		_flbl = QLabel("Folder")
		_flbl.setMinimumWidth(120)
		_frl.addWidget(_flbl)
		self.ref_load_folder_btn = QPushButton(qta.icon('fa6s.folder-open'), " Load Folder")
		_frl.addWidget(self.ref_load_folder_btn, 1)
		self._ref_folder_row.setVisible(False)
		layout.addWidget(self._ref_folder_row)

		self.ref_prompt_type_combo = QComboBox()
		self.ref_prompt_type_combo.setToolTip("Select prompt generation type")
		if prompt_types:
			for key, display_name in prompt_types.items():
				self.ref_prompt_type_combo.addItem(display_name, key)
		else:
			self.ref_prompt_type_combo.addItem("Image Generation", "image_generation")
			self.ref_prompt_type_combo.addItem("Video Generation", "video_generation")
		add_row("Type", self.ref_prompt_type_combo)

		self.ref_aspect_ratio_combo = QComboBox()
		self.ref_aspect_ratio_combo.setToolTip("Select aspect ratio for generated prompts")
		if aspect_ratios:
			for key, display_name in aspect_ratios.items():
				self.ref_aspect_ratio_combo.addItem(display_name, key)
		else:
			self.ref_aspect_ratio_combo.addItem("Widescreen (16:9)", "16:9")
			self.ref_aspect_ratio_combo.addItem("Square (1:1)", "1:1")
			self.ref_aspect_ratio_combo.addItem("Portrait (9:16)", "9:16")
		add_row("Ratio", self.ref_aspect_ratio_combo)

		self.ref_prompt_length_spin = QSpinBox()
		self.ref_prompt_length_spin.setMinimum(1)
		self.ref_prompt_length_spin.setMaximum(2048)
		self.ref_prompt_length_spin.setValue(settings.get('prompt_length', 150) if isinstance(settings.get('prompt_length'), int) else 150)
		self.ref_prompt_length_spin.setToolTip("Maximum character length for each generated prompt")
		add_row("Length", self.ref_prompt_length_spin)

		self.ref_prompts_per_file_spin = QSpinBox()
		self.ref_prompts_per_file_spin.setMinimum(1)
		self.ref_prompts_per_file_spin.setMaximum(20)
		self.ref_prompts_per_file_spin.setValue(min(settings.get('prompts_per_file', 3) if isinstance(settings.get('prompts_per_file'), int) else 3, 20))
		self.ref_prompts_per_file_spin.setToolTip("Prompts to generate per reference file (max 20)")
		add_row("Per File (max 20)", self.ref_prompts_per_file_spin)

		self.ref_variation_spin = QSpinBox()
		self.ref_variation_spin.setMinimum(1)
		self.ref_variation_spin.setMaximum(10)
		self.ref_variation_spin.setValue(settings.get('variation_level', 5) if isinstance(settings.get('variation_level'), int) else 5)
		self.ref_variation_spin.setToolTip("Control variation between prompts (1=very similar, 10=completely different)")
		add_row("Variation", self.ref_variation_spin)

		self.ref_delay_combo = QComboBox()
		self.ref_delay_combo.setEditable(True)
		self.ref_delay_combo.addItems(["No Delay", "Random", "1", "2", "3", "4", "5", "10", "15", "20", "30"])
		try:
			with open(os.path.join(BASE_PATH, "configs", "ai_config.json"), 'r', encoding='utf-8') as _f:
				_ai_cfg = json.load(_f)
			self.ref_delay_combo.setCurrentText(str(_ai_cfg.get('delay_interval', 'Random')))
		except Exception:
			self.ref_delay_combo.setCurrentText('Random')
		self.ref_delay_combo.setToolTip("Delay between files: No Delay=0s, Random=1-5s, or custom seconds")
		self.ref_delay_combo.currentTextChanged.connect(self._save_delay_to_config)
		add_row("Delay", self.ref_delay_combo)

		saved_type = settings.get('prompt_type', 'image_generation')
		for i in range(self.ref_prompt_type_combo.count()):
			if self.ref_prompt_type_combo.itemData(i) == saved_type:
				self.ref_prompt_type_combo.setCurrentIndex(i)
				break
		saved_ar = settings.get('aspect_ratio', '16:9')
		for i in range(self.ref_aspect_ratio_combo.count()):
			if self.ref_aspect_ratio_combo.itemData(i) == saved_ar:
				self.ref_aspect_ratio_combo.setCurrentIndex(i)
				break

		self.ref_prompt_length_spin.valueChanged.connect(self._save_reference_options)
		self.ref_prompts_per_file_spin.valueChanged.connect(self._save_reference_options)
		self.ref_variation_spin.valueChanged.connect(self._save_reference_options)
		self.ref_prompt_type_combo.currentIndexChanged.connect(self._save_reference_options)
		self.ref_aspect_ratio_combo.currentIndexChanged.connect(self._save_reference_options)
		self.ref_source_combo.currentIndexChanged.connect(self._on_ref_source_changed)
		self.ref_load_folder_btn.clicked.connect(self._load_ref_folder)

		layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

		self.ref_stats_label = QLabel("Files: 0 | Target prompts: 0")
		self.ref_stats_label.setWordWrap(True)
		self.ref_stats_label.setStyleSheet("color: gray; font-size: 11px;")
		layout.addWidget(self.ref_stats_label)

		return widget

	def _build_parameters_tab(self):
		widget = QWidget()
		outer = QVBoxLayout(widget)
		outer.setContentsMargins(0, 0, 0, 0)
		scroll = QScrollArea()
		scroll.setWidgetResizable(True)
		scroll.setFrameShape(QFrame.NoFrame)
		scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
		scroll.setObjectName("paramScrollArea")
		scroll.setStyleSheet("QScrollArea#paramScrollArea { background: transparent; border: none; }")
		scroll.viewport().setAutoFillBackground(False)
		inner_widget = QWidget()
		inner_widget.setAutoFillBackground(False)
		inner_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		inner_widget.setMinimumWidth(310)
		layout = QVBoxLayout(inner_widget)
		layout.setSpacing(8)
		layout.setContentsMargins(8, 8, 8, 8)
		scroll.setWidget(inner_widget)
		outer.addWidget(scroll)

		cfg = self._load_ai_config()
		params_cfg = cfg.get('prompt_generator_parameters', {}) if isinstance(cfg, dict) else {}
		p_settings = params_cfg.get('settings', {})
		pg_section = cfg.get('prompt_generator', {}) if isinstance(cfg, dict) else {}
		prompt_types = pg_section.get('prompt_types', {}) if isinstance(pg_section, dict) else {}
		aspect_ratios = pg_section.get('aspect_ratios', {}) if isinstance(pg_section, dict) else {}

		def add_row(label_text, widget_obj):
			h = QHBoxLayout()
			lbl = QLabel(label_text)
			lbl.setFixedWidth(110)
			h.addWidget(lbl)
			h.addWidget(widget_obj, 1)
			layout.addLayout(h)

		self.param_prompt_type_combo = QComboBox()
		if prompt_types:
			for key, display_name in prompt_types.items():
				self.param_prompt_type_combo.addItem(display_name, key)
		else:
			self.param_prompt_type_combo.addItem("Image Generation", "image_generation")
			self.param_prompt_type_combo.addItem("Video Generation", "video_generation")
		saved_pt = p_settings.get('prompt_type', 'image_generation')
		for i in range(self.param_prompt_type_combo.count()):
			if self.param_prompt_type_combo.itemData(i) == saved_pt:
				self.param_prompt_type_combo.setCurrentIndex(i)
				break
		add_row("Type", self.param_prompt_type_combo)

		languages_list = params_cfg.get('languages', [
			"English (Default)", "Indonesian / Bahasa Indonesia", "Japanese / 日本語",
			"Chinese Simplified / 简体中文", "Korean / 한국어", "Spanish / Español",
			"French / Français", "German / Deutsch", "Portuguese / Português", "Arabic / العربية",
		])
		self.param_language_combo = QComboBox()
		for lang in languages_list:
			self.param_language_combo.addItem(lang)
		saved_lang = p_settings.get('language', 'English (Default)')
		idx_lang = self.param_language_combo.findText(saved_lang)
		if idx_lang >= 0:
			self.param_language_combo.setCurrentIndex(idx_lang)
		add_row("Language", self.param_language_combo)

		self.param_aspect_ratio_combo = QComboBox()
		if aspect_ratios:
			for key, display_name in aspect_ratios.items():
				self.param_aspect_ratio_combo.addItem(display_name, key)
		else:
			self.param_aspect_ratio_combo.addItem("Widescreen (16:9)", "16:9")
			self.param_aspect_ratio_combo.addItem("Square (1:1)", "1:1")
			self.param_aspect_ratio_combo.addItem("Portrait (9:16)", "9:16")
		saved_ar_p = p_settings.get('aspect_ratio', '16:9')
		for i in range(self.param_aspect_ratio_combo.count()):
			if self.param_aspect_ratio_combo.itemData(i) == saved_ar_p:
				self.param_aspect_ratio_combo.setCurrentIndex(i)
				break
		add_row("Ratio", self.param_aspect_ratio_combo)

		self.param_prompt_length_spin = QSpinBox()
		self.param_prompt_length_spin.setMinimum(50)
		self.param_prompt_length_spin.setMaximum(2048)
		self.param_prompt_length_spin.setValue(p_settings.get('prompt_length', 150) if isinstance(p_settings.get('prompt_length'), int) else 150)
		self.param_prompt_length_spin.setToolTip("Character length of each generated prompt")
		add_row("Length", self.param_prompt_length_spin)

		self.param_prompts_per_batch_spin = QSpinBox()
		self.param_prompts_per_batch_spin.setMinimum(1)
		self.param_prompts_per_batch_spin.setMaximum(20)
		self.param_prompts_per_batch_spin.setValue(min(p_settings.get('prompts_per_batch', 5) if isinstance(p_settings.get('prompts_per_batch'), int) else 5, 20))
		self.param_prompts_per_batch_spin.setToolTip("How many prompts to generate per request (max 20)")
		add_row("Per Batch (max 20)", self.param_prompts_per_batch_spin)

		self.param_num_requests_spin = QSpinBox()
		self.param_num_requests_spin.setMinimum(1)
		self.param_num_requests_spin.setMaximum(100)
		self.param_num_requests_spin.setValue(p_settings.get('num_requests', 1) if isinstance(p_settings.get('num_requests'), int) else 1)
		self.param_num_requests_spin.setToolTip("How many times to repeat the request (total = per batch × requests)")
		add_row("Requests", self.param_num_requests_spin)

		self.param_variation_spin = QSpinBox()
		self.param_variation_spin.setMinimum(1)
		self.param_variation_spin.setMaximum(10)
		self.param_variation_spin.setValue(p_settings.get('variation_level', 5) if isinstance(p_settings.get('variation_level'), int) else 5)
		self.param_variation_spin.setToolTip("Variation level between prompts (1=very similar, 10=completely different)")
		add_row("Variation", self.param_variation_spin)

		saved_gen_mode = p_settings.get('gen_mode', 'user_defined')
		self.param_gen_mode_combo = QComboBox()
		self.param_gen_mode_combo.addItem(qta.icon('fa6s.pen'), " User Defined", "user_defined")
		self.param_gen_mode_combo.addItem(qta.icon('fa6s.shuffle'), " Random Parameters", "random")
		idx_gm = self.param_gen_mode_combo.findData(saved_gen_mode)
		if idx_gm >= 0:
			self.param_gen_mode_combo.setCurrentIndex(idx_gm)
		self.param_gen_mode_combo.setToolTip("User Defined: pick values manually. Random: auto-randomize Theme, Mood, Color, Art Style & Background before each generation.")
		add_row("Mode", self.param_gen_mode_combo)

		themes_list = params_cfg.get('themes', [])
		themes_row = QHBoxLayout()
		themes_row.addWidget(QLabel("Theme:"))
		self.param_themes_combo = QComboBox()
		self.param_themes_combo.setEditable(True)
		self.param_themes_combo.setToolTip("Select or type a custom theme")
		self.param_themes_combo.addItem("— None —")
		for t in themes_list:
			self.param_themes_combo.addItem(t)
		saved_theme = p_settings.get('theme', '')
		if saved_theme and saved_theme != '— None —':
			idx_t = self.param_themes_combo.findText(saved_theme)
			if idx_t >= 0:
				self.param_themes_combo.setCurrentIndex(idx_t)
			else:
				self.param_themes_combo.setCurrentText(saved_theme)
		themes_row.addWidget(self.param_themes_combo, 1)
		add_theme_btn = QPushButton(qta.icon('fa6s.plus'), "")
		add_theme_btn.setFixedSize(24, 24)
		add_theme_btn.setToolTip("Add current text to theme list")
		themes_row.addWidget(add_theme_btn)
		add_theme_btn.clicked.connect(lambda: self._add_custom_combo_item(self.param_themes_combo, 'themes'))
		layout.addLayout(themes_row)

		moods_list = params_cfg.get('moods', [])
		moods_row = QHBoxLayout()
		moods_row.addWidget(QLabel("Mood:"))
		self.param_moods_combo = QComboBox()
		self.param_moods_combo.setEditable(True)
		self.param_moods_combo.setToolTip("Select or type a custom mood")
		self.param_moods_combo.addItem("— None —")
		for m in moods_list:
			self.param_moods_combo.addItem(m)
		saved_mood = p_settings.get('mood', '')
		if saved_mood and saved_mood != '— None —':
			idx_m = self.param_moods_combo.findText(saved_mood)
			if idx_m >= 0:
				self.param_moods_combo.setCurrentIndex(idx_m)
			else:
				self.param_moods_combo.setCurrentText(saved_mood)
		moods_row.addWidget(self.param_moods_combo, 1)
		add_mood_btn = QPushButton(qta.icon('fa6s.plus'), "")
		add_mood_btn.setFixedSize(24, 24)
		add_mood_btn.setToolTip("Add current text to mood list")
		moods_row.addWidget(add_mood_btn)
		add_mood_btn.clicked.connect(lambda: self._add_custom_combo_item(self.param_moods_combo, 'moods'))
		layout.addLayout(moods_row)

		colors_list = params_cfg.get('colors', [])
		colors_row = QHBoxLayout()
		colors_row.addWidget(QLabel("Color Palette:"))
		self.param_colors_combo = QComboBox()
		self.param_colors_combo.setEditable(True)
		self.param_colors_combo.setToolTip("Select or type a custom color palette")
		self.param_colors_combo.addItem("— None —")
		for c in colors_list:
			self.param_colors_combo.addItem(c)
		saved_color = p_settings.get('color', '')
		if saved_color and saved_color != '— None —':
			idx_c = self.param_colors_combo.findText(saved_color)
			if idx_c >= 0:
				self.param_colors_combo.setCurrentIndex(idx_c)
			else:
				self.param_colors_combo.setCurrentText(saved_color)
		colors_row.addWidget(self.param_colors_combo, 1)
		add_color_btn = QPushButton(qta.icon('fa6s.plus'), "")
		add_color_btn.setFixedSize(24, 24)
		add_color_btn.setToolTip("Add current text to color palette list")
		colors_row.addWidget(add_color_btn)
		add_color_btn.clicked.connect(lambda: self._add_custom_combo_item(self.param_colors_combo, 'colors'))
		layout.addLayout(colors_row)

		art_styles_list = params_cfg.get('art_styles', [])
		art_styles_row = QHBoxLayout()
		art_styles_row.addWidget(QLabel("Art Style:"))
		self.param_art_style_combo = QComboBox()
		self.param_art_style_combo.setEditable(True)
		self.param_art_style_combo.setToolTip("Select or type a custom art style")
		self.param_art_style_combo.addItem("— None —")
		for s in art_styles_list:
			self.param_art_style_combo.addItem(s)
		saved_as = p_settings.get('art_style', '')
		if saved_as and saved_as != '— None —':
			idx_as = self.param_art_style_combo.findText(saved_as)
			if idx_as >= 0:
				self.param_art_style_combo.setCurrentIndex(idx_as)
			else:
				self.param_art_style_combo.setCurrentText(saved_as)
		art_styles_row.addWidget(self.param_art_style_combo, 1)
		add_art_style_btn = QPushButton(qta.icon('fa6s.plus'), "")
		add_art_style_btn.setFixedSize(24, 24)
		add_art_style_btn.setToolTip("Add current text to art style list")
		art_styles_row.addWidget(add_art_style_btn)
		add_art_style_btn.clicked.connect(lambda: self._add_custom_combo_item(self.param_art_style_combo, 'art_styles'))
		layout.addLayout(art_styles_row)

		bg_list = params_cfg.get('backgrounds', [])
		bg_row = QHBoxLayout()
		bg_row.addWidget(QLabel("Background:"))
		self.param_bg_combo = QComboBox()
		self.param_bg_combo.setEditable(True)
		self.param_bg_combo.setToolTip("Select or type a custom background")
		self.param_bg_combo.addItem("— None —")
		for b in bg_list:
			self.param_bg_combo.addItem(b)
		saved_bg = p_settings.get('background', '')
		if saved_bg and saved_bg != '— None —':
			idx_bg = self.param_bg_combo.findText(saved_bg)
			if idx_bg >= 0:
				self.param_bg_combo.setCurrentIndex(idx_bg)
			else:
				self.param_bg_combo.setCurrentText(saved_bg)
		bg_row.addWidget(self.param_bg_combo, 1)
		add_bg_btn = QPushButton(qta.icon('fa6s.plus'), "")
		add_bg_btn.setFixedSize(24, 24)
		add_bg_btn.setToolTip("Add current text to background list")
		bg_row.addWidget(add_bg_btn)
		add_bg_btn.clicked.connect(lambda: self._add_custom_combo_item(self.param_bg_combo, 'backgrounds'))
		pick_color_btn = QPushButton(qta.icon('fa6s.palette'), "")
		pick_color_btn.setFixedSize(24, 24)
		pick_color_btn.setToolTip("Pick a custom background color")
		pick_color_btn.clicked.connect(self._pick_background_color)
		bg_row.addWidget(pick_color_btn)
		layout.addLayout(bg_row)

		self._random_mode_hint_label = QLabel("\u26a1 Theme, Mood, Color, Art Style & Background will be auto-randomized before each generation")
		self._random_mode_hint_label.setWordWrap(True)
		self._random_mode_hint_label.setStyleSheet("color: #f59e0b; font-size: 10px; padding: 2px 0;")
		self._random_mode_hint_label.setVisible(saved_gen_mode == 'random')
		layout.addWidget(self._random_mode_hint_label)

		human_model_options = params_cfg.get('human_model_options', [])
		self.param_human_model_combo = QComboBox()
		self.param_human_model_combo.setEditable(True)
		if human_model_options:
			for opt in human_model_options:
				self.param_human_model_combo.addItem(opt)
		else:
			self.param_human_model_combo.addItems(["No people", "Yes - any person", "Yes - woman", "Yes - man", "Yes - group of people"])
		saved_hm = p_settings.get('human_model', 'No people')
		idx_hm = self.param_human_model_combo.findText(saved_hm)
		if idx_hm >= 0:
			self.param_human_model_combo.setCurrentIndex(idx_hm)
		else:
			self.param_human_model_combo.setCurrentText(saved_hm)
		self.param_human_model_combo.setToolTip("Specify whether human models should appear. Can also type custom value.")
		add_row("Human Model", self.param_human_model_combo)

		layout.addWidget(QLabel("Custom Instruction (optional):"))
		self.param_custom_instruction = QTextEdit()
		self.param_custom_instruction.setMaximumHeight(70)
		self.param_custom_instruction.setPlaceholderText("Optional: add extra instructions for the AI...")
		self.param_custom_instruction.setText(p_settings.get('custom_instruction', ''))
		layout.addWidget(self.param_custom_instruction)

		layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

		self.param_prompt_type_combo.currentIndexChanged.connect(self._save_parameters_to_config)
		self.param_aspect_ratio_combo.currentIndexChanged.connect(self._save_parameters_to_config)
		self.param_prompt_length_spin.valueChanged.connect(self._save_parameters_to_config)
		self.param_prompts_per_batch_spin.valueChanged.connect(self._save_parameters_to_config)
		self.param_num_requests_spin.valueChanged.connect(self._save_parameters_to_config)
		self.param_num_requests_spin.valueChanged.connect(self.update_stats_display)
		self.param_prompts_per_batch_spin.valueChanged.connect(self.update_stats_display)
		self.param_variation_spin.valueChanged.connect(self._save_parameters_to_config)
		self.param_human_model_combo.currentTextChanged.connect(self._save_parameters_to_config)
		self.param_themes_combo.currentTextChanged.connect(self._save_parameters_to_config)
		self.param_moods_combo.currentTextChanged.connect(self._save_parameters_to_config)
		self.param_colors_combo.currentTextChanged.connect(self._save_parameters_to_config)
		self.param_art_style_combo.currentTextChanged.connect(self._save_parameters_to_config)
		self.param_bg_combo.currentTextChanged.connect(self._save_parameters_to_config)
		self.param_language_combo.currentIndexChanged.connect(self._save_parameters_to_config)
		self.param_gen_mode_combo.currentIndexChanged.connect(self._on_param_mode_changed)
		self.param_gen_mode_combo.currentIndexChanged.connect(self._save_parameters_to_config)

		return widget

	def _build_right_panel(self):
		self.right_tabs = QTabWidget()
		self.right_tabs.setTabPosition(QTabWidget.North)

		table_tab = self._build_table_tab()
		logs_tab = self._build_logs_tab()
		configure_tab = self._build_configure_instructions_tab()

		self.right_tabs.addTab(table_tab, qta.icon('fa6s.table-list'), " Table")
		self.right_tabs.addTab(logs_tab, qta.icon('fa6s.terminal'), " Logs")
		self.right_tabs.addTab(configure_tab, qta.icon('fa6s.gear'), " Configure Instructions")

		return self.right_tabs

	def _build_table_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)
		layout.setContentsMargins(4, 4, 4, 4)
		layout.setSpacing(4)

		toolbar_layout = QHBoxLayout()
		toolbar_layout.setSpacing(4)

		self.refresh_btn = QPushButton(qta.icon('fa6s.rotate-right'), " Refresh")
		self.refresh_btn.setToolTip("Refresh the prompts table")
		self.refresh_btn.clicked.connect(self.refresh_table_immediately)
		toolbar_layout.addWidget(self.refresh_btn)

		self.clear_btn = QPushButton(qta.icon('fa6s.trash'), " Clear All")
		self.clear_btn.setToolTip("Delete all generated prompts")
		self.clear_btn.clicked.connect(self.clear_all_prompts)
		toolbar_layout.addWidget(self.clear_btn)

		self.clear_copied_btn = QPushButton(qta.icon('fa6s.trash-can'), " Clear Copied")
		self.clear_copied_btn.setToolTip("Delete prompts that have been copied")
		self.clear_copied_btn.clicked.connect(self.clear_copied_prompts)
		toolbar_layout.addWidget(self.clear_copied_btn)

		self.export_btn = QPushButton(qta.icon('fa6s.file-export'), " Export")
		self.export_btn.setToolTip("Export prompts to CSV or TXT file")
		self.export_btn.clicked.connect(self.export_to_csv)
		toolbar_layout.addWidget(self.export_btn)

		self.import_btn = QPushButton(qta.icon('fa6s.file-import'), " Import")
		self.import_btn.setToolTip("Import prompts from CSV or TXT file")
		self.import_btn.clicked.connect(self.import_from_csv)
		toolbar_layout.addWidget(self.import_btn)

		toolbar_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
		layout.addLayout(toolbar_layout)

		paging_layout = QHBoxLayout()
		paging_layout.setSpacing(4)

		self.page_size_combo = QComboBox()
		self.page_size_combo.addItems(["10", "20", "30", "50", "80", "100", "200"])
		self.page_size_combo.setCurrentText("20")
		self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)
		paging_layout.addWidget(QLabel("Per Page"))
		paging_layout.addWidget(self.page_size_combo)
		paging_layout.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

		self.prev_btn = QPushButton(qta.icon('fa6s.chevron-left'), "")
		self.prev_btn.setToolTip("Previous page")
		self.prev_btn.clicked.connect(self.go_prev)
		paging_layout.addWidget(self.prev_btn)

		self.page_label = QLabel("Page 1 of 1")
		paging_layout.addWidget(self.page_label)

		self.page_spinner = QSpinBox()
		self.page_spinner.setMinimum(1)
		self.page_spinner.setMaximum(1)
		self.page_spinner.setValue(1)
		self.page_spinner.setToolTip("Go to page")
		self.page_spinner.valueChanged.connect(self.on_page_spin)
		paging_layout.addWidget(self.page_spinner)

		self.next_btn = QPushButton(qta.icon('fa6s.chevron-right'), "")
		self.next_btn.setToolTip("Next page")
		self.next_btn.clicked.connect(self.go_next)
		paging_layout.addWidget(self.next_btn)
		layout.addLayout(paging_layout)

		self.table = QTableWidget()
		self.table.setColumnCount(4)
		self.table.setHorizontalHeaderLabels(["Prompts", "Chars", "Created", "Copy"])
		self.table.setColumnWidth(0, 450)
		self.table.setColumnWidth(1, 60)
		self.table.setColumnWidth(2, 150)
		self.table.setColumnWidth(3, 60)
		self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
		self.table.setEditTriggers(QTableWidget.NoEditTriggers)
		self.table.setSelectionBehavior(QTableWidget.SelectRows)
		self.table.setSelectionMode(QTableWidget.SingleSelection)
		self.table.setFocusPolicy(Qt.StrongFocus)
		self.table.setToolTip("Double-click to edit • Middle-click to copy • Ctrl+C to copy • Right-click for menu")
		self.table.doubleClicked.connect(self.on_prompt_double_click)
		self.table.setContextMenuPolicy(Qt.CustomContextMenu)
		self.table.customContextMenuRequested.connect(self.on_table_context_menu)
		self.table.mousePressEvent = self.table_mouse_press_event
		self.table.keyPressEvent = self.table_key_press_event
		layout.addWidget(self.table, 1)

		return widget

	def _build_logs_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)
		layout.setContentsMargins(4, 4, 4, 4)
		layout.setSpacing(4)

		log_header = QHBoxLayout()
		log_header.addWidget(QLabel("Generation Logs"))
		log_header.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
		clear_log_btn = QPushButton(qta.icon('fa6s.broom'), " Clear")
		clear_log_btn.setToolTip("Clear log output")
		clear_log_btn.clicked.connect(self._clear_logs)
		log_header.addWidget(clear_log_btn)
		layout.addLayout(log_header)

		self.log_output = QTextEdit()
		self.log_output.setReadOnly(True)
		self.log_output.setPlaceholderText("Generation logs will appear here...")
		font = QFont("Consolas", 9)
		font.setStyleHint(QFont.Monospace)
		self.log_output.setFont(font)
		layout.addWidget(self.log_output, 1)

		return widget

	def _build_configure_instructions_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)
		layout.setContentsMargins(4, 4, 4, 4)
		layout.setSpacing(4)

		self._cfg_full_data = {}
		self._cfg_pg_data = {}
		try:
			cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
			with open(cfg_path, 'r', encoding='utf-8') as f:
				self._cfg_full_data = json.load(f)
			self._cfg_pg_data = self._cfg_full_data.get('prompt_generator', {})
		except Exception as e:
			print(f"Failed to load config for Configure Instructions tab: {e}")

		inner_tabs = QTabWidget()

		instr_tab = QWidget()
		instr_layout = QVBoxLayout(instr_tab)
		instr_layout.addWidget(QLabel("Edit instructions for each prompt generation type:"))
		instr_sub = QTabWidget()
		img_instr_w = QWidget()
		img_instr_l = QVBoxLayout(img_instr_w)
		self.cfg_image_instruction_edit = QTextEdit()
		img_instr_l.addWidget(self.cfg_image_instruction_edit)
		vid_instr_w = QWidget()
		vid_instr_l = QVBoxLayout(vid_instr_w)
		self.cfg_video_instruction_edit = QTextEdit()
		vid_instr_l.addWidget(self.cfg_video_instruction_edit)
		instr_sub.addTab(img_instr_w, qta.icon('fa6s.image'), "Image Generation")
		instr_sub.addTab(vid_instr_w, qta.icon('fa6s.video'), "Video Generation")
		instr_layout.addWidget(instr_sub)
		inner_tabs.addTab(instr_tab, qta.icon('fa6s.pen-to-square'), "Instructions")

		req_tab = QWidget()
		req_layout = QVBoxLayout(req_tab)
		req_layout.addWidget(QLabel("Edit requirements for each prompt generation type:"))
		req_sub = QTabWidget()
		img_req_w = QWidget()
		img_req_l = QVBoxLayout(img_req_w)
		self.cfg_image_req_list = QListWidget()
		img_req_l.addWidget(self.cfg_image_req_list, 1)
		img_req_btns = QHBoxLayout()
		add_img_req = QPushButton(qta.icon('fa6s.plus'), " Add")
		add_img_req.clicked.connect(lambda: self._cfg_add_requirement('image'))
		edit_img_req = QPushButton(qta.icon('fa6s.pen-to-square'), " Edit")
		edit_img_req.clicked.connect(lambda: self._cfg_edit_requirement('image'))
		del_img_req = QPushButton(qta.icon('fa6s.trash-can'), " Remove")
		del_img_req.clicked.connect(lambda: self._cfg_remove_requirement('image'))
		for b in (add_img_req, edit_img_req, del_img_req):
			img_req_btns.addWidget(b)
		img_req_btns.addStretch()
		img_req_l.addLayout(img_req_btns)
		vid_req_w = QWidget()
		vid_req_l = QVBoxLayout(vid_req_w)
		self.cfg_video_req_list = QListWidget()
		vid_req_l.addWidget(self.cfg_video_req_list, 1)
		vid_req_btns = QHBoxLayout()
		add_vid_req = QPushButton(qta.icon('fa6s.plus'), " Add")
		add_vid_req.clicked.connect(lambda: self._cfg_add_requirement('video'))
		edit_vid_req = QPushButton(qta.icon('fa6s.pen-to-square'), " Edit")
		edit_vid_req.clicked.connect(lambda: self._cfg_edit_requirement('video'))
		del_vid_req = QPushButton(qta.icon('fa6s.trash-can'), " Remove")
		del_vid_req.clicked.connect(lambda: self._cfg_remove_requirement('video'))
		for b in (add_vid_req, edit_vid_req, del_vid_req):
			vid_req_btns.addWidget(b)
		vid_req_btns.addStretch()
		vid_req_l.addLayout(vid_req_btns)
		req_sub.addTab(img_req_w, qta.icon('fa6s.image'), "Image Generation")
		req_sub.addTab(vid_req_w, qta.icon('fa6s.video'), "Video Generation")
		req_layout.addWidget(req_sub)
		inner_tabs.addTab(req_tab, qta.icon('fa6s.list-ul'), "Requirements")

		var_tab = QWidget()
		var_layout = QVBoxLayout(var_tab)
		var_layout.addWidget(QLabel("Edit variation level descriptions:"))
		self.cfg_variation_list = QListWidget()
		var_layout.addWidget(self.cfg_variation_list, 1)
		var_btns = QHBoxLayout()
		edit_var_btn = QPushButton(qta.icon('fa6s.pen-to-square'), " Edit Selected Level")
		edit_var_btn.clicked.connect(self._cfg_edit_variation_level)
		var_btns.addWidget(edit_var_btn)
		var_btns.addStretch()
		var_layout.addLayout(var_btns)
		inner_tabs.addTab(var_tab, qta.icon('fa6s.sliders'), "Variation Levels")

		# --- Combo Lists tab ---
		combo_tab = QWidget()
		combo_layout = QVBoxLayout(combo_tab)
		combo_layout.setContentsMargins(2, 2, 2, 2)
		combo_sub = QTabWidget()

		def _make_list_tab(attr_name):
			w = QWidget()
			vl = QVBoxLayout(w)
			vl.setContentsMargins(4, 4, 4, 4)
			lw = QListWidget()
			setattr(self, attr_name, lw)
			vl.addWidget(lw, 1)
			btns = QHBoxLayout()
			add_b = QPushButton(qta.icon('fa6s.plus'), " Add")
			add_b.clicked.connect(lambda checked=False, _lw=lw: self._cfg_add_list_item(_lw))
			edit_b = QPushButton(qta.icon('fa6s.pen-to-square'), " Edit")
			edit_b.clicked.connect(lambda checked=False, _lw=lw: self._cfg_edit_list_item(_lw))
			del_b = QPushButton(qta.icon('fa6s.trash-can'), " Remove")
			del_b.clicked.connect(lambda checked=False, _lw=lw: self._cfg_remove_list_item(_lw))
			for b in (add_b, edit_b, del_b):
				btns.addWidget(b)
			btns.addStretch()
			vl.addLayout(btns)
			return w

		ar_tab = QWidget()
		ar_l = QVBoxLayout(ar_tab)
		ar_l.setContentsMargins(4, 4, 4, 4)
		ar_l.addWidget(QLabel("Format:  key | Display Label   (e.g.  16:9 | Widescreen (16:9))"))
		self.cfg_aspect_ratios_list = QListWidget()
		ar_l.addWidget(self.cfg_aspect_ratios_list, 1)
		ar_btns = QHBoxLayout()
		ar_add = QPushButton(qta.icon('fa6s.plus'), " Add")
		ar_add.clicked.connect(lambda: self._cfg_add_list_item(self.cfg_aspect_ratios_list))
		ar_edit = QPushButton(qta.icon('fa6s.pen-to-square'), " Edit")
		ar_edit.clicked.connect(lambda: self._cfg_edit_list_item(self.cfg_aspect_ratios_list))
		ar_del = QPushButton(qta.icon('fa6s.trash-can'), " Remove")
		ar_del.clicked.connect(lambda: self._cfg_remove_list_item(self.cfg_aspect_ratios_list))
		for b in (ar_add, ar_edit, ar_del):
			ar_btns.addWidget(b)
		ar_btns.addStretch()
		ar_l.addLayout(ar_btns)

		combo_sub.addTab(ar_tab, qta.icon('fa6s.crop-simple'), " Ratios")
		combo_sub.addTab(_make_list_tab('cfg_languages_list'), qta.icon('fa6s.language'), " Languages")
		combo_sub.addTab(_make_list_tab('cfg_themes_list'), qta.icon('fa6s.palette'), " Themes")
		combo_sub.addTab(_make_list_tab('cfg_moods_list'), qta.icon('fa6s.face-smile'), " Moods")
		combo_sub.addTab(_make_list_tab('cfg_colors_list'), qta.icon('fa6s.droplet'), " Colors")
		combo_sub.addTab(_make_list_tab('cfg_art_styles_list'), qta.icon('fa6s.paintbrush'), " Art Styles")
		combo_sub.addTab(_make_list_tab('cfg_bg_list'), qta.icon('fa6s.image'), " Backgrounds")
		combo_layout.addWidget(combo_sub, 1)
		inner_tabs.addTab(combo_tab, qta.icon('fa6s.list'), "Parameters")

		layout.addWidget(inner_tabs, 1)

		save_row = QHBoxLayout()
		save_row.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
		save_cfg_btn = QPushButton(qta.icon('fa6s.floppy-disk'), " Save")
		save_cfg_btn.clicked.connect(self._save_configure_instructions)
		save_row.addWidget(save_cfg_btn)
		layout.addLayout(save_row)

		self._load_configure_instructions_values()
		return widget

	def _build_actions_bar(self):
		actions_layout = QHBoxLayout()
		actions_layout.setSpacing(8)

		stats_widget = QWidget()
		stats_layout = QVBoxLayout(stats_widget)
		stats_layout.setContentsMargins(0, 0, 0, 0)
		stats_layout.setSpacing(1)

		row1 = QHBoxLayout()
		row1.setSpacing(16)
		self.stats_type_label = QLabel("Type: —")
		self.stats_type_label.setStyleSheet("font-size: 11px;")
		row1.addWidget(self.stats_type_label)
		self.stats_generated_label = QLabel("Generated: 0")
		self.stats_generated_label.setStyleSheet("font-size: 11px;")
		row1.addWidget(self.stats_generated_label)
		self.stats_estimated_label = QLabel("Est. total: 0")
		self.stats_estimated_label.setStyleSheet("font-size: 11px; color: gray;")
		row1.addWidget(self.stats_estimated_label)
		row1.addStretch()
		stats_layout.addLayout(row1)

		row2 = QHBoxLayout()
		row2.setSpacing(16)
		self.stats_elapsed_label = QLabel("Elapsed: —")
		self.stats_elapsed_label.setStyleSheet("font-size: 11px; color: gray;")
		row2.addWidget(self.stats_elapsed_label)
		self.stats_eta_label = QLabel("ETA: —")
		self.stats_eta_label.setStyleSheet("font-size: 11px; color: gray;")
		row2.addWidget(self.stats_eta_label)
		self.stats_remaining_label = QLabel("Remaining: —")
		self.stats_remaining_label.setStyleSheet("font-size: 11px; color: gray;")
		row2.addWidget(self.stats_remaining_label)
		row2.addStretch()
		stats_layout.addLayout(row2)

		self.generating_label = QLabel("Ready to generate")
		self.generating_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold; font-size: 11px;")
		stats_layout.addWidget(self.generating_label)

		actions_layout.addWidget(stats_widget)
		actions_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

		self.generate_btn = QPushButton(self.gen_icon, " Generate Prompts by Reference")
		self.generate_btn.setMinimumHeight(40)
		self.generate_btn.setMinimumWidth(220)
		self.generate_btn.setToolTip("Generate prompts based on current tab settings")
		self.generate_btn.clicked.connect(self.toggle_generation)
		self.generate_btn.setStyleSheet(f"""
			QPushButton {{
				background-color: {theme.get_color('primary')};
				color: {theme.get_color('white')};
				border: none;
				border-radius: 6px;
				font-weight: bold;
				font-size: 12px;
			}}
			QPushButton:hover {{
				background-color: {theme.get_color('primary_hover')};
			}}
			QPushButton:pressed {{
				background-color: {theme.get_color('primary_pressed')};
			}}
		""")
		actions_layout.addWidget(self.generate_btn)
		return actions_layout

	def _on_left_tab_changed(self, index):
		if not hasattr(self, 'generate_btn'):
			return
		if index == 0:
			self.generate_btn.setText(" Generate Prompts by Reference")
			self.generate_btn.setIcon(self.gen_icon)
		else:
			self.generate_btn.setText(" Generate Prompts by Parameters")
			self.generate_btn.setIcon(self.gen_icon)
		self.update_stats_display()

	def _lock_left_tabs(self, locked):
		tab_bar = self.left_tabs.tabBar()
		for i in range(self.left_tabs.count()):
			tab_bar.setTabEnabled(i, not locked)

	def _append_log(self, message):
		if hasattr(self, 'log_output'):
			ts = datetime.now().strftime("%H:%M:%S")
			self.log_output.append(f"[{ts}] {message}")
			scrollbar = self.log_output.verticalScrollBar()
			scrollbar.setValue(scrollbar.maximum())

	def _clear_logs(self):
		if hasattr(self, 'log_output'):
			self.log_output.clear()

	def _add_custom_combo_item(self, combo, cfg_list_key):
		text = combo.currentText().strip()
		if not text:
			return
		if combo.findText(text) < 0:
			combo.addItem(text)
			combo.setCurrentText(text)
			try:
				cfg = self._load_ai_config() or {}
				if 'prompt_generator_parameters' not in cfg:
					cfg['prompt_generator_parameters'] = {}
				current_list = cfg['prompt_generator_parameters'].get(cfg_list_key, [])
				if text not in current_list:
					current_list.append(text)
				cfg['prompt_generator_parameters'][cfg_list_key] = current_list
				cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
				with open(cfg_path, 'w', encoding='utf-8') as f:
					json.dump(cfg, f, indent=2, ensure_ascii=False)
				print(f"Custom item '{text}' added to {cfg_list_key}")
			except Exception as e:
				print(f"Failed to save custom item to {cfg_list_key}: {e}")

	def _on_instr_type_changed(self, index):
		pass

	def _load_instruction_templates(self):
		pass

	def _on_save_instructions(self):
		pass

	def _load_configure_instructions_values(self):
		if not hasattr(self, 'cfg_image_instruction_edit'):
			return
		instructions = self._cfg_pg_data.get('instructions', {})
		self.cfg_image_instruction_edit.setPlainText(instructions.get('image_generation', ''))
		self.cfg_video_instruction_edit.setPlainText(instructions.get('video_generation', ''))
		requirements = self._cfg_pg_data.get('requirements', {})
		self.cfg_image_req_list.clear()
		self.cfg_video_req_list.clear()
		for req in requirements.get('image_generation', []):
			self.cfg_image_req_list.addItem(QListWidgetItem(req))
		for req in requirements.get('video_generation', []):
			self.cfg_video_req_list.addItem(QListWidgetItem(req))
		self.cfg_variation_list.clear()
		variation_levels = self._cfg_pg_data.get('variation_levels', {})
		for level in range(1, 11):
			level_str = str(level)
			description = variation_levels.get(level_str, '')
			display_text = f"Level {level}: {description[:50]}{'...' if len(description) > 50 else ''}"
			item = QListWidgetItem(display_text)
			item.setData(Qt.UserRole, level_str)
			self.cfg_variation_list.addItem(item)

		# Load combo lists
		if hasattr(self, 'cfg_aspect_ratios_list'):
			try:
				cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
				with open(cfg_path, 'r', encoding='utf-8') as _f:
					_full = json.load(_f)
				_pg = _full.get('prompt_generator', {})
				_pgp = _full.get('prompt_generator_parameters', {})
				self.cfg_aspect_ratios_list.clear()
				for k, v in _pg.get('aspect_ratios', {}).items():
					self.cfg_aspect_ratios_list.addItem(QListWidgetItem(f"{k} | {v}"))
				for _attr, _key, _src in [
					('cfg_languages_list', 'languages', _pgp),
					('cfg_themes_list', 'themes', _pgp),
					('cfg_moods_list', 'moods', _pgp),
					('cfg_colors_list', 'colors', _pgp),
					('cfg_art_styles_list', 'art_styles', _pgp),
					('cfg_bg_list', 'backgrounds', _pgp),
				]:
					_lw = getattr(self, _attr, None)
					if _lw:
						_lw.clear()
						for _item in _src.get(_key, []):
							_lw.addItem(QListWidgetItem(_item))
			except Exception as e:
				print(f"Failed to load combo lists for config tab: {e}")

	def _save_configure_instructions(self):
		if not hasattr(self, 'cfg_image_instruction_edit'):
			return
		try:
			cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
			with open(cfg_path, 'r', encoding='utf-8') as f:
				full_cfg = json.load(f)
			pg_cfg = full_cfg.get('prompt_generator', {})
			pg_cfg['instructions'] = {
				'image_generation': self.cfg_image_instruction_edit.toPlainText(),
				'video_generation': self.cfg_video_instruction_edit.toPlainText()
			}
			pg_cfg['requirements'] = {
				'image_generation': [self.cfg_image_req_list.item(i).text() for i in range(self.cfg_image_req_list.count())],
				'video_generation': [self.cfg_video_req_list.item(i).text() for i in range(self.cfg_video_req_list.count())]
			}
			if hasattr(self, '_cfg_pg_data') and 'variation_levels' in self._cfg_pg_data:
				pg_cfg['variation_levels'] = self._cfg_pg_data['variation_levels']
			# Save aspect ratios
			if hasattr(self, 'cfg_aspect_ratios_list'):
				ar_dict = {}
				for i in range(self.cfg_aspect_ratios_list.count()):
					entry = self.cfg_aspect_ratios_list.item(i).text()
					if '|' in entry:
						k, v = entry.split('|', 1)
						k = k.strip()
						v = v.strip()
						if k:
							ar_dict[k] = v
					else:
						text = entry.strip()
						if text:
							ar_dict[text] = text
				if ar_dict:
					pg_cfg['aspect_ratios'] = ar_dict
			# Save parameter combo lists
			if hasattr(self, 'cfg_languages_list'):
				pgp_cfg = full_cfg.get('prompt_generator_parameters', {})
				for _attr, _key in [
					('cfg_languages_list', 'languages'),
					('cfg_themes_list', 'themes'),
					('cfg_moods_list', 'moods'),
					('cfg_colors_list', 'colors'),
					('cfg_art_styles_list', 'art_styles'),
					('cfg_bg_list', 'backgrounds'),
				]:
					_lw = getattr(self, _attr, None)
					if _lw:
						pgp_cfg[_key] = [_lw.item(i).text() for i in range(_lw.count())]
				full_cfg['prompt_generator_parameters'] = pgp_cfg
			full_cfg['prompt_generator'] = pg_cfg
			with open(cfg_path, 'w', encoding='utf-8') as f:
				json.dump(full_cfg, f, indent=2, ensure_ascii=False)
			self._append_log("Prompt generator configuration saved.")
			print("Prompt generator configuration saved successfully")
			self._reload_combo_lists()
		except Exception as e:
			print(f"Failed to save prompt generator configuration: {e}")

	def _cfg_requirement_dialog(self, title, label_text, initial_text=''):
		from PySide6.QtGui import QTextOption
		dlg = QDialog(self)
		dlg.setWindowTitle(title)
		dlg.resize(500, 220)
		layout = QVBoxLayout(dlg)
		layout.addWidget(QLabel(label_text))
		text_edit = QTextEdit()
		text_edit.setPlainText(initial_text)
		text_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
		layout.addWidget(text_edit, 1)
		btn_row = QHBoxLayout()
		btn_row.addStretch()
		ok_btn = QPushButton(qta.icon('fa6s.check'), " OK")
		ok_btn.clicked.connect(dlg.accept)
		cancel_btn = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
		cancel_btn.clicked.connect(dlg.reject)
		btn_row.addWidget(ok_btn)
		btn_row.addWidget(cancel_btn)
		layout.addLayout(btn_row)
		text_edit.setFocus()
		if dlg.exec() == QDialog.Accepted:
			return text_edit.toPlainText().strip()
		return None

	def _cfg_add_requirement(self, req_type):
		text = self._cfg_requirement_dialog("Add Requirement", "Enter requirement text:")
		if text:
			list_widget = self.cfg_image_req_list if req_type == 'image' else self.cfg_video_req_list
			list_widget.addItem(QListWidgetItem(text))

	def _cfg_edit_requirement(self, req_type):
		list_widget = self.cfg_image_req_list if req_type == 'image' else self.cfg_video_req_list
		current_item = list_widget.currentItem()
		if not current_item:
			return
		text = self._cfg_requirement_dialog("Edit Requirement", "Edit requirement text:", current_item.text())
		if text:
			current_item.setText(text)

	def _cfg_remove_requirement(self, req_type):
		list_widget = self.cfg_image_req_list if req_type == 'image' else self.cfg_video_req_list
		current_item = list_widget.currentItem()
		if not current_item:
			return
		reply = QMessageBox.question(self, "Delete Requirement", "Delete this requirement?",
									 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
		if reply == QMessageBox.Yes:
			list_widget.takeItem(list_widget.row(current_item))

	def _cfg_edit_variation_level(self):
		current_item = self.cfg_variation_list.currentItem()
		if not current_item:
			return
		level_str = current_item.data(Qt.UserRole)
		current_desc = self._cfg_pg_data.get('variation_levels', {}).get(level_str, '')
		text = self._cfg_requirement_dialog(f"Edit Variation Level {level_str}",
										  f"Edit description for Level {level_str}:", current_desc)
		if text:
			if 'variation_levels' not in self._cfg_pg_data:
				self._cfg_pg_data['variation_levels'] = {}
			self._cfg_pg_data['variation_levels'][level_str] = text
			display_text = f"Level {level_str}: {text[:50]}{'...' if len(text) > 50 else ''}"
			current_item.setText(display_text)

	def _cfg_add_list_item(self, list_widget):
		prompt = "Enter new item:"
		if hasattr(self, 'cfg_aspect_ratios_list') and list_widget is self.cfg_aspect_ratios_list:
			prompt = "Enter as:  key | Display Label\n(e.g.  16:9 | Widescreen (16:9))"
		text = self._cfg_requirement_dialog("Add Item", prompt)
		if text:
			list_widget.addItem(QListWidgetItem(text))

	def _cfg_edit_list_item(self, list_widget):
		current_item = list_widget.currentItem()
		if not current_item:
			return
		prompt = "Edit item:"
		if hasattr(self, 'cfg_aspect_ratios_list') and list_widget is self.cfg_aspect_ratios_list:
			prompt = "Edit as:  key | Display Label\n(e.g.  16:9 | Widescreen (16:9))"
		text = self._cfg_requirement_dialog("Edit Item", prompt, current_item.text())
		if text:
			current_item.setText(text)

	def _cfg_remove_list_item(self, list_widget):
		current_item = list_widget.currentItem()
		if not current_item:
			return
		reply = QMessageBox.question(self, "Delete Item", "Delete this item?",
									 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
		if reply == QMessageBox.Yes:
			list_widget.takeItem(list_widget.row(current_item))

	def _reload_combo_lists(self):
		cfg = self._load_ai_config()
		if not cfg:
			return
		pg = cfg.get('prompt_generator', {})
		pgp = cfg.get('prompt_generator_parameters', {})
		prompt_types = pg.get('prompt_types', {})
		aspect_ratios = pg.get('aspect_ratios', {})
		languages = pgp.get('languages', [])

		for attr, items_dict, current_fn in [
			('ref_aspect_ratio_combo', aspect_ratios, None),
			('ref_prompt_type_combo', prompt_types, None),
			('param_aspect_ratio_combo', aspect_ratios, None),
			('param_prompt_type_combo', prompt_types, None),
		]:
			if not hasattr(self, attr):
				continue
			combo = getattr(self, attr)
			current_data = combo.currentData()
			combo.blockSignals(True)
			combo.clear()
			for k, v in items_dict.items():
				combo.addItem(v, k)
			idx = combo.findData(current_data)
			if idx >= 0:
				combo.setCurrentIndex(idx)
			combo.blockSignals(False)

		if hasattr(self, 'param_language_combo'):
			current_lang = self.param_language_combo.currentText()
			self.param_language_combo.blockSignals(True)
			self.param_language_combo.clear()
			for lang in languages:
				self.param_language_combo.addItem(lang)
			idx = self.param_language_combo.findText(current_lang)
			if idx >= 0:
				self.param_language_combo.setCurrentIndex(idx)
			self.param_language_combo.blockSignals(False)

		for attr, cfg_key in [
			('param_themes_combo', 'themes'),
			('param_moods_combo', 'moods'),
			('param_colors_combo', 'colors'),
			('param_art_style_combo', 'art_styles'),
			('param_bg_combo', 'backgrounds'),
		]:
			if not hasattr(self, attr):
				continue
			combo = getattr(self, attr)
			current_text = combo.currentText()
			combo.blockSignals(True)
			combo.clear()
			combo.addItem('\u2014 None \u2014')
			for item in pgp.get(cfg_key, []):
				combo.addItem(item)
			idx = combo.findText(current_text)
			if idx >= 0:
				combo.setCurrentIndex(idx)
			combo.blockSignals(False)

		print("Combo lists reloaded successfully")

	def on_api_key_changed(self, api_key, service, model):
		self.api_key = api_key
		self.selected_service = service
		self.selected_model_name = model
		print(f"API key changed: {service} - {model} - {api_key[-10:] if api_key else 'None'}")

	def toggle_generation(self):
		if self.is_generating:
			self.stop_generation()
		else:
			active_tab = self.left_tabs.currentIndex()
			if active_tab == 0:
				self.generate_prompts_by_reference()
			else:
				self.generate_prompts_by_parameters()

	def stop_generation(self):
		if self.worker and self.worker.isRunning():
			self.worker.stop()
			self.worker.wait(3000)
		self.is_generating = False
		self._gen_start_time = None
		if hasattr(self, '_stats_tick_timer'):
			self._stats_tick_timer.stop()
		self._lock_left_tabs(False)
		self.update_generate_button()
		self.progress_bar.setVisible(False)
		self._append_log("Generation stopped by user.")
		print("Generation stopped")
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(5000)

	def update_generate_button(self):
		if not hasattr(self, 'generate_btn'):
			return
		if self.is_generating:
			self.generate_btn.setIcon(self.stop_icon)
			self.generate_btn.setText(" Stop Generation")
			_err_q = QColor(theme.get_color('error'))
			_err_rgb = f"{_err_q.red()},{_err_q.green()},{_err_q.blue()}"
			self.generate_btn.setStyleSheet(f"""
				QPushButton {{
					background-color: rgba({_err_rgb},0.3);
					color: {theme.get_color('white')};
					border: none;
					border-radius: 6px;
					font-weight: bold;
					font-size: 12px;
				}}
				QPushButton:hover {{
					background-color: rgba({_err_rgb},0.5);
				}}
				QPushButton:pressed {{
					background-color: rgba({_err_rgb},0.7);
				}}
			""")
		else:
			active_tab = self.left_tabs.currentIndex()
			label = " Generate Prompts by Reference" if active_tab == 0 else " Generate Prompts by Parameters"
			self.generate_btn.setIcon(self.gen_icon)
			self.generate_btn.setText(label)
			self.generate_btn.setStyleSheet(f"""
				QPushButton {{
					background-color: {theme.get_color('primary')};
					color: {theme.get_color('white')};
					border: none;
					border-radius: 6px;
					font-weight: bold;
					font-size: 12px;
				}}
				QPushButton:hover {{
					background-color: {theme.get_color('primary_hover')};
				}}
				QPushButton:pressed {{
					background-color: {theme.get_color('primary_pressed')};
				}}
			""")

	def generate_prompts_by_reference(self):
		if not self.db:
			print("Error: Database not available for prompt generation")
			return
		if not self.api_key or not self.selected_service or not self.selected_model_name:
			print("Error: API key and model must be selected for prompt generation")
			return
		if self.worker and self.worker.isRunning():
			return

		use_folder = hasattr(self, 'ref_source_combo') and self.ref_source_combo.currentData() == 'folder'
		if use_folder:
			if not self._ref_folder_files:
				QMessageBox.information(self, "No folder loaded", "Please load a reference folder first using the Load Folder button.")
				return
			total_files = len(self._ref_folder_files)
		else:
			total_files = self.db.get_files_count() if hasattr(self.db, "get_files_count") else 0
			if total_files == 0:
				QMessageBox.information(
					self,
					"No reference images",
					"No reference images were found in Image-Tea.\n"
					"Add images or videos to your library and try again."
				)
				return

		prompts_per_file = self.ref_prompts_per_file_spin.value() if hasattr(self, 'ref_prompts_per_file_spin') else 1
		self._gen_estimated_total = total_files * prompts_per_file
		self._gen_prompts_at_start = self.total_prompts
		self._gen_start_time = time.time()
		self.is_generating = True
		self._lock_left_tabs(True)
		self.update_generate_button()
		self.progress_bar.setVisible(True)
		self.progress_bar.setValue(0)
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(1000)
		if hasattr(self, '_stats_tick_timer'):
			self._stats_tick_timer.start(1000)

		source_label = "folder" if use_folder else "database"
		self._append_log(f"Starting generation by reference ({source_label}) — {total_files} file(s) found.")
		print(f"Starting prompt generation by reference ({source_label})...")

		self.worker = PromptGeneratorWorker(
			self.db, self.api_key, self.selected_service, self.selected_model_name,
			folder_files=self._ref_folder_files if use_folder else None
		)
		self.worker.progress_updated.connect(self.on_generation_progress)
		self.worker.progress_value_changed.connect(self.on_progress_value_changed)
		self.worker.finished.connect(self.on_generation_finished)
		self.worker.error_occurred.connect(self.on_generation_error)
		self.worker.prompt_added.connect(self.on_new_prompt_added)
		self.worker.file_processing.connect(self.on_file_processing)
		self.worker.start()

	def generate_prompts_by_parameters(self):
		if not self.db:
			print("Error: Database not available for prompt generation")
			return
		if not self.api_key or not self.selected_service or not self.selected_model_name:
			print("Error: API key and model must be selected for prompt generation")
			return
		if self.worker and self.worker.isRunning():
			return

		is_random = hasattr(self, 'param_gen_mode_combo') and self.param_gen_mode_combo.currentData() == 'random'
		if is_random:
			num_requests = self.param_num_requests_spin.value() if hasattr(self, 'param_num_requests_spin') else 1
			self._random_requests_remaining = num_requests
			self._random_original_num_requests = num_requests
			self._random_mode_active = True
			self._random_total_generated = 0
			self.is_generating = True
			self._lock_left_tabs(True)
			self.update_generate_button()
			self.progress_bar.setVisible(True)
			self.progress_bar.setValue(0)
			if hasattr(self, 'refresh_timer'):
				self.refresh_timer.start(1000)
			if hasattr(self, '_stats_tick_timer'):
				self._stats_tick_timer.start(1000)
			self._gen_prompts_at_start = self.total_prompts
			self._gen_start_time = time.time()
			self._gen_estimated_total = (self.param_prompts_per_batch_spin.value() if hasattr(self, 'param_prompts_per_batch_spin') else 1) * num_requests
			self._append_log(f"Starting random generation — {num_requests} request(s) total...")
			self._randomize_parameters_animated(self._start_single_random_request)
		else:
			self._random_mode_active = False
			self._start_parameters_worker()

	def _start_single_random_request(self):
		if not self.is_generating or not self._random_mode_active:
			return
		self.param_num_requests_spin.blockSignals(True)
		self.param_num_requests_spin.setValue(1)
		self.param_num_requests_spin.blockSignals(False)
		self._save_parameters_to_config()
		req_num = self._random_original_num_requests - self._random_requests_remaining + 1
		self._append_log(f"[Random {req_num}/{self._random_original_num_requests}] Sending request...")
		self._launch_parameters_worker_bare()

	def _launch_parameters_worker_bare(self):
		self.progress_bar.setValue(0)
		self.worker = PromptGeneratorParametersWorker(
			self.db, self.api_key, self.selected_service, self.selected_model_name
		)
		self.worker.progress_updated.connect(self.on_generation_progress)
		self.worker.progress_value_changed.connect(self.on_progress_value_changed)
		self.worker.finished.connect(self.on_generation_finished)
		self.worker.error_occurred.connect(self.on_generation_error)
		self.worker.prompt_added.connect(self.on_new_prompt_added)
		self.worker.start()

	def _start_parameters_worker(self):
		prompts_per_batch = self.param_prompts_per_batch_spin.value() if hasattr(self, 'param_prompts_per_batch_spin') else 1
		num_requests = self.param_num_requests_spin.value() if hasattr(self, 'param_num_requests_spin') else 1
		self._gen_estimated_total = prompts_per_batch * num_requests
		self._gen_prompts_at_start = self.total_prompts
		self._gen_start_time = time.time()
		self.is_generating = True
		self._lock_left_tabs(True)
		self.update_generate_button()
		self.progress_bar.setVisible(True)
		self.progress_bar.setValue(0)
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(1000)
		if hasattr(self, '_stats_tick_timer'):
			self._stats_tick_timer.start(1000)

		self._append_log("Starting generation by parameters...")
		print("Starting prompt generation by parameters...")

		self.worker = PromptGeneratorParametersWorker(
			self.db, self.api_key, self.selected_service, self.selected_model_name
		)
		self.worker.progress_updated.connect(self.on_generation_progress)
		self.worker.progress_value_changed.connect(self.on_progress_value_changed)
		self.worker.finished.connect(self.on_generation_finished)
		self.worker.error_occurred.connect(self.on_generation_error)
		self.worker.prompt_added.connect(self.on_new_prompt_added)
		self.worker.start()

	def on_generation_progress(self, message):
		print(f"Progress: {message}")
		self._append_log(message)

	def on_file_processing(self, filename):
		self.current_generating_file = filename
		self._append_log(f"Processing: {filename}")
		self.update_stats_display()

	def on_progress_value_changed(self, value):
		self.progress_bar.setValue(value)

	def on_generation_finished(self, total_generated):
		if total_generated > 0:
			self.load_prompts_from_db()
			self.update_pagination()

		if self._random_mode_active:
			self._random_total_generated += total_generated
			self._random_requests_remaining -= 1
			req_done = self._random_original_num_requests - self._random_requests_remaining
			if total_generated > 0:
				self._append_log(f"[Random {req_done}/{self._random_original_num_requests}] {total_generated} prompt(s) done.")
			else:
				self._append_log(f"[Random {req_done}/{self._random_original_num_requests}] No prompts produced.")

			if self._random_requests_remaining > 0:
				self.progress_bar.setValue(0)
				self._randomize_parameters_animated(self._start_single_random_request)
				return

			self._random_mode_active = False
			total_generated = self._random_total_generated
			self.param_num_requests_spin.blockSignals(True)
			self.param_num_requests_spin.setValue(self._random_original_num_requests)
			self.param_num_requests_spin.blockSignals(False)
			self._save_parameters_to_config()

		self.is_generating = False
		self.current_generating_file = None
		self._gen_start_time = None
		if hasattr(self, '_stats_tick_timer'):
			self._stats_tick_timer.stop()
		self._lock_left_tabs(False)
		self.update_generate_button()
		self.progress_bar.setVisible(False)
		if total_generated > 0:
			self._append_log(f"Done — {total_generated} prompt(s) generated successfully.")
			print(f"Successfully generated {total_generated} prompts")
		else:
			self._append_log("Generation finished — no prompts were produced.")
			print("No prompts were generated")
		self.update_stats_display()
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(5000)

	def on_generation_error(self, error_message):
		print(f"Prompt generation error: {error_message}")
		self._append_log(f"ERROR: {error_message}")
		if self._random_mode_active:
			self._random_mode_active = False
			self.param_num_requests_spin.blockSignals(True)
			self.param_num_requests_spin.setValue(self._random_original_num_requests)
			self.param_num_requests_spin.blockSignals(False)
			self._save_parameters_to_config()
		self.is_generating = False
		self._gen_start_time = None
		if hasattr(self, '_stats_tick_timer'):
			self._stats_tick_timer.stop()
		self._lock_left_tabs(False)
		self.update_generate_button()
		self.progress_bar.setVisible(False)
		self.update_stats_display()

	def _load_ai_config(self):
		cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
		if not os.path.exists(cfg_path):
			return {}
		try:
			with open(cfg_path, 'r', encoding='utf-8') as f:
				return json.load(f)
		except Exception:
			print(f"Failed to load ai_config.json from {cfg_path}")
			return {}

	def load_ai_config(self):
		return self._load_ai_config()

	def _save_reference_options(self):
		cfg = self._load_ai_config() or {}
		if 'prompt_generator' not in cfg or not isinstance(cfg['prompt_generator'], dict):
			cfg['prompt_generator'] = {}
		if 'settings' not in cfg['prompt_generator'] or not isinstance(cfg['prompt_generator']['settings'], dict):
			cfg['prompt_generator']['settings'] = {}
		s = cfg['prompt_generator']['settings']
		s['prompt_length'] = int(self.ref_prompt_length_spin.value())
		s['prompts_per_file'] = int(self.ref_prompts_per_file_spin.value())
		s['variation_level'] = int(self.ref_variation_spin.value())
		s['prompt_type'] = self.ref_prompt_type_combo.currentData() or 'image_generation'
		s['aspect_ratio'] = self.ref_aspect_ratio_combo.currentData() or '16:9'
		cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
		try:
			with open(cfg_path, 'w', encoding='utf-8') as f:
				json.dump(cfg, f, indent=2, ensure_ascii=False)
		except Exception as e:
			print(f"Failed to save reference options: {e}")

	def save_options_to_config(self):
		self._save_reference_options()

	def _on_ref_source_changed(self, index):
		is_folder = hasattr(self, 'ref_source_combo') and self.ref_source_combo.currentData() == 'folder'
		if hasattr(self, '_ref_folder_row'):
			self._ref_folder_row.setVisible(is_folder)
		self.update_stats_display()

	def _load_ref_folder(self):
		from PySide6.QtWidgets import QFileDialog
		home_dir = os.path.expanduser("~")
		folder = QFileDialog.getExistingDirectory(self, "Select Reference Folder", home_dir)
		if not folder:
			return
		image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
		self._ref_folder_files = [
			os.path.join(folder, f)
			for f in sorted(os.listdir(folder))
			if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f.lower())[1] in image_exts
		]
		count = len(self._ref_folder_files)
		self.update_stats_display()
		self._append_log(f"Loaded {count} image(s) from: {folder}")
		print(f"Loaded {count} reference images from folder: {folder}")

	def _pick_background_color(self):
		from PySide6.QtWidgets import QColorDialog
		color = QColorDialog.getColor(parent=self)
		if color.isValid():
			hex_val = color.name().upper()
			if hasattr(self, 'param_bg_combo'):
				idx = self.param_bg_combo.findText(hex_val)
				if idx < 0:
					self.param_bg_combo.insertItem(1, hex_val)
					idx = 1
				self.param_bg_combo.setCurrentIndex(idx)

	def _save_parameters_to_config(self):
		cfg = self._load_ai_config() or {}
		if 'prompt_generator_parameters' not in cfg or not isinstance(cfg['prompt_generator_parameters'], dict):
			cfg['prompt_generator_parameters'] = {}
		if 'settings' not in cfg['prompt_generator_parameters'] or not isinstance(cfg['prompt_generator_parameters']['settings'], dict):
			cfg['prompt_generator_parameters']['settings'] = {}
		s = cfg['prompt_generator_parameters']['settings']
		s['prompt_type'] = self.param_prompt_type_combo.currentData() or 'image_generation'
		s['aspect_ratio'] = self.param_aspect_ratio_combo.currentData() or '16:9'
		s['prompt_length'] = int(self.param_prompt_length_spin.value())
		s['prompts_per_batch'] = int(self.param_prompts_per_batch_spin.value())
		s['num_requests'] = int(self.param_num_requests_spin.value())
		s['variation_level'] = int(self.param_variation_spin.value())
		s['human_model'] = self.param_human_model_combo.currentText()
		s['custom_instruction'] = self.param_custom_instruction.toPlainText()
		s['theme'] = self.param_themes_combo.currentText()
		s['mood'] = self.param_moods_combo.currentText()
		s['color'] = self.param_colors_combo.currentText()
		s['art_style'] = self.param_art_style_combo.currentText() if hasattr(self, 'param_art_style_combo') else ''
		s['background'] = self.param_bg_combo.currentText() if hasattr(self, 'param_bg_combo') else ''
		s['language'] = self.param_language_combo.currentText() if hasattr(self, 'param_language_combo') else 'English (Default)'
		s['gen_mode'] = self.param_gen_mode_combo.currentData() if hasattr(self, 'param_gen_mode_combo') else 'user_defined'
		cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
		try:
			with open(cfg_path, 'w', encoding='utf-8') as f:
				json.dump(cfg, f, indent=2, ensure_ascii=False)
		except Exception as e:
			print(f"Failed to save parameters options: {e}")

	def _load_parameters_from_config(self):
		cfg = self._load_ai_config()
		params_cfg = cfg.get('prompt_generator_parameters', {}) if isinstance(cfg, dict) else {}
		p_settings = params_cfg.get('settings', {})
		saved_theme = p_settings.get('theme', '')
		if saved_theme:
			idx = self.param_themes_combo.findText(saved_theme)
			if idx >= 0:
				self.param_themes_combo.setCurrentIndex(idx)
			else:
				self.param_themes_combo.setCurrentText(saved_theme)
		saved_mood = p_settings.get('mood', '')
		if saved_mood:
			idx = self.param_moods_combo.findText(saved_mood)
			if idx >= 0:
				self.param_moods_combo.setCurrentIndex(idx)
			else:
				self.param_moods_combo.setCurrentText(saved_mood)
		saved_color = p_settings.get('color', '')
		if saved_color:
			idx = self.param_colors_combo.findText(saved_color)
			if idx >= 0:
				self.param_colors_combo.setCurrentIndex(idx)
			else:
				self.param_colors_combo.setCurrentText(saved_color)
		if hasattr(self, 'param_art_style_combo'):
			saved_as = p_settings.get('art_style', '')
			if saved_as:
				idx = self.param_art_style_combo.findText(saved_as)
				if idx >= 0:
					self.param_art_style_combo.setCurrentIndex(idx)
				else:
					self.param_art_style_combo.setCurrentText(saved_as)
		if hasattr(self, 'param_bg_combo'):
			saved_bg = p_settings.get('background', '')
			if saved_bg:
				idx = self.param_bg_combo.findText(saved_bg)
				if idx >= 0:
					self.param_bg_combo.setCurrentIndex(idx)
				else:
					self.param_bg_combo.setCurrentText(saved_bg)
		if hasattr(self, 'param_gen_mode_combo'):
			saved_gm = p_settings.get('gen_mode', 'user_defined')
			idx_gm = self.param_gen_mode_combo.findData(saved_gm)
			if idx_gm >= 0:
				self.param_gen_mode_combo.setCurrentIndex(idx_gm)
			if hasattr(self, '_random_mode_hint_label'):
				self._random_mode_hint_label.setVisible(saved_gm == 'random')

	def _on_param_mode_changed(self):
		is_random = hasattr(self, 'param_gen_mode_combo') and self.param_gen_mode_combo.currentData() == 'random'
		if hasattr(self, '_random_mode_hint_label'):
			self._random_mode_hint_label.setVisible(is_random)

	def _randomize_parameters_animated(self, on_complete):
		import random
		cfg = self._load_ai_config() or {}
		pcfg = cfg.get('prompt_generator_parameters', {})
		combo_defs = [
			(self.param_themes_combo, pcfg.get('themes', [])),
			(self.param_moods_combo, pcfg.get('moods', [])),
			(self.param_colors_combo, pcfg.get('colors', [])),
		]
		if hasattr(self, 'param_art_style_combo'):
			combo_defs.append((self.param_art_style_combo, pcfg.get('art_styles', [])))
		if hasattr(self, 'param_bg_combo'):
			combo_defs.append((self.param_bg_combo, pcfg.get('backgrounds', [])))
		chosen = []
		for combo, items in combo_defs:
			real = [it for it in items if it and it != '\u2014 None \u2014']
			chosen.append(random.choice(real) if real else '\u2014 None \u2014')
		self._animate_combo_sequence(combo_defs, chosen, 0, on_complete)

	def _animate_combo_sequence(self, combos, chosen, idx, on_complete):
		import random
		if idx >= len(combos):
			self._save_parameters_to_config()
			on_complete()
			return
		combo, items = combos[idx]
		target = chosen[idx]
		delays = [40, 40, 40, 40, 40, 40, 40, 40, 65, 90, 120, 160]
		spin_pool = [it for it in items if it] or [combo.itemText(i) for i in range(combo.count())]

		def step(frame):
			if frame >= len(delays):
				combo.blockSignals(True)
				combo.setCurrentText(target)
				combo.blockSignals(False)
				combo.setStyleSheet("QComboBox { border: 1px solid #22c55e; border-radius: 3px; }")
				def settle():
					combo.setStyleSheet("")
					QTimer.singleShot(80, lambda: self._animate_combo_sequence(combos, chosen, idx + 1, on_complete))
				QTimer.singleShot(200, settle)
				return
			if spin_pool:
				combo.blockSignals(True)
				combo.setCurrentText(random.choice(spin_pool))
				combo.blockSignals(False)
			combo.setStyleSheet("QComboBox { border: 1px solid #f59e0b; border-radius: 3px; }")
			QTimer.singleShot(delays[frame], lambda f=frame: step(f + 1))

		step(0)

	def _save_delay_to_config(self):
		try:
			config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
			with open(config_path, 'r', encoding='utf-8') as f:
				config = json.load(f)
			config['delay_interval'] = self.ref_delay_combo.currentText()
			with open(config_path, 'w', encoding='utf-8') as f:
				json.dump(config, f, indent=2, ensure_ascii=False)
		except Exception as e:
			print(f"Error saving delay to config: {e}")

	def save_delay_to_config(self):
		self._save_delay_to_config()

	def total_pages(self):
		if self.total_prompts == 0:
			return 1
		return ((self.total_prompts - 1) // self.page_size) + 1

	def on_page_size_changed(self, text):
		try:
			self.page_size = int(text)
			self.current_page = 1
			self.load_prompts_from_db()
			self.update_pagination()
		except ValueError:
			pass

	def update_pagination(self):
		total = self.total_pages()
		if self.current_page < 1:
			self.current_page = 1
		if self.current_page > total:
			self.current_page = total
		self.page_label.setText(f"Page {self.current_page} of {total}")
		self.page_spinner.setMaximum(total)
		self.page_spinner.setValue(self.current_page)

		self.table.clearContents()
		self.table.setRowCount(len(self.prompt_data))
		for r, prompt_row in enumerate(self.prompt_data):
			if len(prompt_row) >= 4:
				prompt_text = prompt_row[2] or ""
				created_at = prompt_row[3] or ""
				status = prompt_row[4] if len(prompt_row) > 4 else 'pending'

				display_prompt = prompt_text[:100] + "..." if len(prompt_text) > 100 else prompt_text
				char_count = len(prompt_text)

				item_prompt = QTableWidgetItem(display_prompt)
				item_prompt.setData(Qt.UserRole, prompt_text)
				item_prompt.setData(Qt.UserRole + 1, prompt_row[0])
				self.table.setItem(r, 0, item_prompt)
				self.table.setItem(r, 1, QTableWidgetItem(str(char_count)))
				self.table.setItem(r, 2, QTableWidgetItem(str(created_at)[:19]))

				copy_btn = QPushButton()
				copy_btn.setIcon(qta.icon('fa6s.copy'))
				copy_btn.setToolTip("Copy prompt to clipboard")
				copy_btn.clicked.connect(lambda checked, text=prompt_text, pid=prompt_row[0]: self.copy_prompt_and_update_status(text, pid))
				self.table.setCellWidget(r, 3, copy_btn)

				_copied_c = QColor(theme.get_color('success'))
				_copied_c.setAlpha(int(0.3 * 255))
				if status == 'copied':
					for col in range(4):
						item = self.table.item(r, col)
						if item:
							item.setBackground(_copied_c)
						else:
							empty_item = QTableWidgetItem("")
							empty_item.setBackground(_copied_c)
							self.table.setItem(r, col, empty_item)
					_warn_q = QColor(theme.get_color('warning'))
					_warn_q.setAlpha(int(0.3 * 255))
					_warn_rgb = f"{_warn_q.red()},{_warn_q.green()},{_warn_q.blue()}"
					copy_btn.setStyleSheet(f"""
						QPushButton {{
							background-color: rgba({_warn_rgb},0.3);
							border: 1px solid {theme.get_color('gray')};
							border-radius: 3px;
						}}
						QPushButton:hover {{
							background-color: rgba({_warn_rgb},0.39);
						}}
					""")
				else:
					copy_btn.setStyleSheet("")
					for col in range(3):
						item = self.table.item(r, col)
						if item:
							item.setBackground(QColor(0, 0, 0, 0))

		self.prev_btn.setEnabled(self.current_page > 1)
		self.next_btn.setEnabled(self.current_page < total)
		self.update_stats_display()

	@staticmethod
	def _format_elapsed(seconds):
		seconds = int(seconds)
		if seconds < 60:
			return f"{seconds}s"
		m, s = divmod(seconds, 60)
		if m < 60:
			return f"{m}m {s:02d}s"
		h, m = divmod(m, 60)
		return f"{h}h {m:02d}m {s:02d}s"

	def update_stats_display(self):
		db_file_count = self.db.get_files_count() if self.db and hasattr(self.db, 'get_files_count') else 0
		active_tab = self.left_tabs.currentIndex() if hasattr(self, 'left_tabs') else 0

		if active_tab == 0:
			use_folder = hasattr(self, 'ref_source_combo') and self.ref_source_combo.currentData() == 'folder'
			total_files = len(self._ref_folder_files) if use_folder else db_file_count
			prompts_per_file = self.ref_prompts_per_file_spin.value() if hasattr(self, 'ref_prompts_per_file_spin') else 1
			target_total = total_files * prompts_per_file
			gen_type = "By Reference (Folder)" if use_folder else "By Reference (DB)"
			if hasattr(self, 'ref_stats_label'):
				source_label = f"{total_files} folder image(s)" if use_folder else f"{total_files} DB file(s)"
				self.ref_stats_label.setText(f"{source_label} | Target: {target_total} prompts")
		else:
			prompts_per_batch = self.param_prompts_per_batch_spin.value() if hasattr(self, 'param_prompts_per_batch_spin') else 1
			num_requests = self.param_num_requests_spin.value() if hasattr(self, 'param_num_requests_spin') else 1
			target_total = prompts_per_batch * num_requests
			gen_type = "By Parameters"

		if hasattr(self, 'stats_type_label'):
			self.stats_type_label.setText(f"Type: {gen_type}")
		if hasattr(self, 'stats_generated_label'):
			self.stats_generated_label.setText(f"Generated: {self.total_prompts}")
		if hasattr(self, 'stats_estimated_label'):
			self.stats_estimated_label.setText(f"Est. total: {target_total}")

		if self.is_generating and self._gen_start_time:
			elapsed = time.time() - self._gen_start_time
			generated_this_run = max(0, self.total_prompts - self._gen_prompts_at_start)
			remaining = max(0, self._gen_estimated_total - generated_this_run)
			if generated_this_run > 0 and remaining > 0:
				eta_secs = (elapsed / generated_this_run) * remaining
				eta_str = self._format_elapsed(eta_secs)
			else:
				eta_str = "—"
			if hasattr(self, 'stats_elapsed_label'):
				self.stats_elapsed_label.setText(f"Elapsed: {self._format_elapsed(elapsed)}")
			if hasattr(self, 'stats_eta_label'):
				self.stats_eta_label.setText(f"ETA: {eta_str}")
			if hasattr(self, 'stats_remaining_label'):
				self.stats_remaining_label.setText(f"Remaining: {remaining}")
		else:
			if hasattr(self, 'stats_elapsed_label'):
				self.stats_elapsed_label.setText("Elapsed: —")
			if hasattr(self, 'stats_eta_label'):
				self.stats_eta_label.setText("ETA: —")
			if hasattr(self, 'stats_remaining_label'):
				self.stats_remaining_label.setText("Remaining: —")

		if self.current_generating_file:
			self.generating_label.setText(f"Processing: {self.current_generating_file}")
		else:
			self.generating_label.setText("Ready to generate" if not self.is_generating else "Generating...")

	def go_prev(self):
		if self.current_page > 1:
			self.current_page -= 1
			self.load_prompts_from_db()
			self.update_pagination()

	def go_next(self):
		if self.current_page < self.total_pages():
			self.current_page += 1
			self.load_prompts_from_db()
			self.update_pagination()

	def on_page_spin(self, value):
		if value != self.current_page:
			self.current_page = value
			self.load_prompts_from_db()
			self.update_pagination()

	def load_prompts_from_db(self):
		try:
			if not self.db:
				self.prompt_data = []
				self.total_prompts = 0
				return
			if hasattr(self.db, 'get_generated_prompts_count'):
				self.total_prompts = self.db.get_generated_prompts_count()
			else:
				self.total_prompts = 0
			if hasattr(self.db, 'get_prompts_with_status_paginated'):
				self.prompt_data = self.db.get_prompts_with_status_paginated(self.current_page, self.page_size)
			elif hasattr(self.db, 'get_generated_prompts_paginated'):
				self.prompt_data = self.db.get_generated_prompts_paginated(self.current_page, self.page_size)
			else:
				self.prompt_data = []
		except Exception as e:
			print(f"Failed loading prompts from DB: {e}")
			self.prompt_data = []
			self.total_prompts = 0

	def on_prompt_double_click(self, index):
		if not index.isValid() or not self.db:
			return
		row = index.row()
		if row >= len(self.prompt_data):
			return
		item = self.table.item(row, 0)
		if not item:
			return
		prompt_id = item.data(Qt.UserRole + 1)
		if not prompt_id:
			return
		prompt_row = self.db.get_generated_prompt_by_id(prompt_id)
		if not prompt_row:
			return
		prompt_text = prompt_row[2]
		self._open_inline_edit(prompt_id, prompt_text)

	def _open_inline_edit(self, prompt_id, prompt_text):
		dlg = QDialog(self)
		dlg.setWindowTitle("Edit Generated Prompt")
		dlg.resize(600, 320)
		layout = QVBoxLayout(dlg)
		layout.addWidget(QLabel(f"Editing prompt ID: {prompt_id}"))
		text_edit = QTextEdit()
		text_edit.setPlainText(prompt_text)
		layout.addWidget(text_edit, 1)
		btn_row = QHBoxLayout()
		btn_row.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
		cancel_btn = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
		cancel_btn.clicked.connect(dlg.reject)
		save_btn = QPushButton(qta.icon('fa6s.floppy-disk'), " Save")
		save_btn.clicked.connect(dlg.accept)
		btn_row.addWidget(cancel_btn)
		btn_row.addWidget(save_btn)
		layout.addLayout(btn_row)
		text_edit.setFocus()
		if dlg.exec() == QDialog.Accepted:
			new_text = text_edit.toPlainText().strip()
			if new_text and self.db and hasattr(self.db, 'update_generated_prompt'):
				try:
					self.db.update_generated_prompt(prompt_id, new_text)
					self.load_prompts_from_db()
					self.update_pagination()
					print(f"Prompt {prompt_id} updated successfully")
				except Exception as e:
					print(f"Failed to update prompt: {e}")

	def _on_edit_prompt_save(self):
		pass

	def _on_edit_prompt_cancel(self):
		pass

	def on_table_context_menu(self, pos):
		if not hasattr(self, 'table'):
			return
		item = self.table.itemAt(pos)
		if not item:
			return
		row = item.row()
		first_item = self.table.item(row, 0)
		if not first_item:
			return
		full_prompt = first_item.data(Qt.UserRole)
		prompt_id = first_item.data(Qt.UserRole + 1)
		if not full_prompt:
			return
		menu = QMenu(self)
		copy_action = QAction(qta.icon('fa6s.copy'), " Copy Prompt", self)
		copy_action.triggered.connect(lambda: self.copy_prompt_and_update_status(full_prompt, prompt_id))
		copy_action.setShortcut(QKeySequence("Ctrl+C"))
		menu.addAction(copy_action)
		edit_action = QAction(qta.icon('fa6s.pen-to-square'), " Edit Prompt", self)
		edit_action.triggered.connect(lambda: self._open_inline_edit(prompt_id, full_prompt))
		menu.addAction(edit_action)
		delete_action = QAction(qta.icon('fa6s.trash'), " Delete Prompt", self)
		delete_action.triggered.connect(lambda: self._delete_single_prompt(prompt_id))
		menu.addAction(delete_action)
		menu.exec(self.table.viewport().mapToGlobal(pos))

	def _delete_single_prompt(self, prompt_id):
		if not self.db or prompt_id is None:
			return
		reply = QMessageBox.question(
			self, "Delete Prompt",
			"Delete this prompt?",
			QMessageBox.Yes | QMessageBox.No,
			QMessageBox.No
		)
		if reply == QMessageBox.Yes:
			try:
				if hasattr(self.db, 'delete_generated_prompt'):
					self.db.delete_generated_prompt(prompt_id)
				self.load_prompts_from_db()
				self.update_pagination()
			except Exception as e:
				print(f"Failed to delete prompt: {e}")

	def copy_prompt_and_update_status(self, prompt_text, prompt_id):
		try:
			clipboard = QGuiApplication.clipboard()
			if clipboard:
				clipboard.setText(prompt_text)
				print(f"Prompt copied: {prompt_text[:50]}...")
				if self.db and hasattr(self.db, 'add_prompt_status') and (prompt_id is not None):
					self.db.add_prompt_status(prompt_id, 'copied')
				self.refresh_table_immediately()
				preview = (prompt_text[:80] + '...') if len(prompt_text) > 80 else prompt_text
				QToolTip.showText(QCursor.pos(), f"Copied: {preview}", self, msecShowTime=3000)
			else:
				print("Failed to access clipboard")
		except Exception as e:
			print(f"Error copying prompt: {e}")

	def copy_prompt_text(self, prompt_text):
		try:
			clipboard = QGuiApplication.clipboard()
			clipboard.setText(prompt_text)
			preview = (prompt_text[:80] + '...') if len(prompt_text) > 80 else prompt_text
			QToolTip.showText(QCursor.pos(), f"Copied: {preview}", self)
			print(f"Prompt copied: {preview}")
		except Exception as e:
			print(f"Failed to copy prompt: {e}")

	def refresh_table_immediately(self):
		try:
			current_page = self.current_page
			self.load_prompts_from_db()
			self.current_page = current_page
			self.update_pagination()
			self.table.repaint()
		except Exception as e:
			print(f"Error refreshing table: {e}")

	def table_key_press_event(self, event):
		QTableWidget.keyPressEvent(self.table, event)
		if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
			current_row = self.table.currentRow()
			if current_row >= 0:
				first_item = self.table.item(current_row, 0)
				if first_item:
					prompt_text = first_item.data(Qt.UserRole)
					prompt_id = first_item.data(Qt.UserRole + 1)
					if prompt_text and prompt_id:
						self.copy_prompt_and_update_status(prompt_text, prompt_id)
						event.accept()
						return
		event.ignore()

	def table_mouse_press_event(self, event):
		QTableWidget.mousePressEvent(self.table, event)
		if event.button() == Qt.MiddleButton:
			item = self.table.itemAt(event.pos())
			if item:
				row = item.row()
				first_item = self.table.item(row, 0)
				if first_item:
					prompt_text = first_item.data(Qt.UserRole)
					prompt_id = first_item.data(Qt.UserRole + 1)
					if prompt_text and prompt_id:
						self.copy_prompt_and_update_status(prompt_text, prompt_id)

	def clear_all_prompts(self):
		if not self.db:
			return
		reply = QMessageBox.question(
			self, "Clear All Prompts",
			"Are you sure you want to delete all generated prompts?\nThis action cannot be undone.",
			QMessageBox.Yes | QMessageBox.No,
			QMessageBox.No
		)
		if reply == QMessageBox.Yes:
			try:
				self.db.clear_all_generated_prompts()
				self.load_prompts_from_db()
				self.update_pagination()
				self._append_log("All prompts cleared.")
				print("All prompts cleared")
			except Exception as e:
				print(f"Failed to clear prompts: {e}")

	def clear_copied_prompts(self):
		if not self.db:
			return
		try:
			copied_count = self.db.get_copied_prompts_count()
		except Exception as e:
			print(f"Failed to get copied prompts count: {e}")
			copied_count = None
		if copied_count is None:
			message = "Delete prompts that have been copied?\nThis action cannot be undone."
		elif copied_count == 0:
			QMessageBox.information(self, "No Copied Prompts", "There are no copied prompts to clear.")
			return
		else:
			message = f"Delete {copied_count} copied prompt{'s' if copied_count != 1 else ''}?\nThis action cannot be undone."
		reply = QMessageBox.question(
			self, "Clear Copied Prompts", message,
			QMessageBox.Yes | QMessageBox.No,
			QMessageBox.No
		)
		if reply == QMessageBox.Yes:
			try:
				self.db.clear_copied_prompts()
				self.refresh_table_immediately()
				self.table.clearSelection()
				self.table.viewport().update()
				self._append_log("Copied prompts cleared.")
				print("Copied prompts cleared")
			except Exception as e:
				print(f"Failed to clear copied prompts: {e}")

	def export_to_csv(self):
		if not self.db:
			QMessageBox.warning(self, "Error", "Database not available")
			return
		try:
			all_prompts = self.db.get_all_generated_prompts()
			if not all_prompts:
				QMessageBox.information(self, "Export", "No prompts to export")
				return

			from dialogs.tools.prompt_io_dialogs import ExportSettingsDialog, build_export_content
			settings_dialog = ExportSettingsDialog(self)
			if settings_dialog.exec() != ExportSettingsDialog.Accepted:
				return
			settings = settings_dialog.settings

			prompt_texts = [row[2] for row in all_prompts]
			content, ext = build_export_content(prompt_texts, settings)

			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			default_filename = f"Image_Tea_Generated_Prompts_{timestamp}.{ext}"
			home_dir = os.path.expanduser("~")
			default_path = os.path.join(home_dir, default_filename)

			if ext == 'csv':
				file_filter = "CSV Files (*.csv);;All Files (*)"
			else:
				file_filter = "Text Files (*.txt);;All Files (*)"

			filename, _ = QFileDialog.getSaveFileName(
				self, "Save Exported Prompts", default_path, file_filter
			)
			if not filename:
				return

			with open(filename, 'w', encoding='utf-8', newline='') as f:
				f.write(content)

			self._append_log(f"Exported {len(prompt_texts)} prompts to {os.path.basename(filename)}")
			QMessageBox.information(self, "Export Complete", f"Exported {len(prompt_texts)} prompts to:\n{filename}")
		except Exception as e:
			print(f"Failed to export prompts: {e}")
			QMessageBox.critical(self, "Export Error", "Failed to export prompts — check console for details")

	def import_from_csv(self):
		try:
			filename, _ = QFileDialog.getOpenFileName(
				self, "Import Prompts",
				os.path.expanduser("~"),
				"Supported files (*.csv *.txt);;CSV files (*.csv);;Text files (*.txt);;All files (*.*)"
			)
			if not filename:
				return
			if not self.db:
				QMessageBox.critical(self, "Import Error", "Database connection not available.")
				return
			from dialogs.tools.prompt_io_dialogs import SmartImportWorker
			progress_dialog = CSVImportProgressDialog(self)
			worker = SmartImportWorker(self.db, filename)
			progress_dialog.worker = worker
			worker.progress_updated.connect(progress_dialog.update_progress)
			worker.progress_value_changed.connect(progress_dialog.update_progress_value)
			worker.finished.connect(progress_dialog.import_finished)
			worker.finished.connect(self.on_import_finished)
			worker.error_occurred.connect(self.on_import_error)
			worker.start()
			result = progress_dialog.exec()
			if worker.isRunning():
				worker.terminate()
				worker.wait()
		except Exception as e:
			print(f"Failed to import prompts: {e}")
			QMessageBox.critical(self, "Import Error", f"Failed to import prompts:\n{str(e)}")

	def on_import_finished(self, imported_count):
		try:
			self.load_prompts_from_db()
			self.update_pagination()
			self._append_log(f"Imported {imported_count} prompts.")
			print(f"Successfully imported {imported_count} prompts")
		except Exception as e:
			print(f"Error refreshing table after import: {e}")

	def on_import_error(self, error_message):
		self._append_log(f"Import error: {error_message}")
		QMessageBox.critical(self, "Import Error", f"Import failed:\n{error_message}")

	def on_new_prompt_added(self):
		if hasattr(self, 'table'):
			current_row = self.table.currentRow()
			self.load_prompts_from_db()
			self.update_pagination()
			if current_row >= 0 and current_row < self.table.rowCount():
				item = self.table.item(current_row, 0)
				if item:
					self.table.setCurrentItem(item)

	def refresh_table_if_needed(self):
		if not self.db or not hasattr(self, 'table'):
			return
		current_count = self.db.get_generated_prompts_count()
		if current_count != self.last_prompt_count:
			self.last_prompt_count = current_count
			current_row = self.table.currentRow()
			self.load_prompts_from_db()
			self.update_pagination()
			if current_row >= 0 and current_row < self.table.rowCount():
				item = self.table.item(current_row, 0)
				if item:
					self.table.setCurrentItem(item)
		if self.is_generating and self.refresh_timer.interval() != 1000:
			self.refresh_timer.start(1000)
		elif not self.is_generating and self.refresh_timer.interval() != 5000:
			self.refresh_timer.start(5000)

	def open_prompt_config_editor(self):
		from dialogs.prompt_generator_config_dialog import PromptGeneratorConfigDialog
		dialog = PromptGeneratorConfigDialog(self)
		result = dialog.exec()
		if result == QDialog.Accepted:
			QMessageBox.information(self, "Success", "Prompt configuration updated successfully.")

	def closeEvent(self, event):
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.stop()
		if self.worker and self.worker.isRunning():
			self.worker.stop()
			self.worker.wait()
		event.accept()
