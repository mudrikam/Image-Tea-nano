from PySide6.QtWidgets import (
	QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
	QPushButton, QHBoxLayout, QLabel, QSpinBox, QSpacerItem, QSizePolicy, QFrame, QApplication, QProgressBar,
	QComboBox, QMessageBox, QFileDialog, QWidget, QMenu, QToolTip
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QAction, QCursor, QKeySequence
import os
import json
import csv
from datetime import datetime
from config import BASE_PATH
import qtawesome as qta
from ui.api_key_section import ApiKeySectionWidget
from dialogs.tools.prompt_edit_dialog import PromptEditDialog


class PromptGeneratorWorker(QThread):
	"""Worker thread for prompt generation to prevent UI freezing"""
	progress_updated = Signal(str)
	progress_value_changed = Signal(int)  # Progress percentage (0-100)
	finished = Signal(int)  # total_generated
	error_occurred = Signal(str)
	prompt_added = Signal()  # Signal when a new prompt is saved
	file_processing = Signal(str)  # Signal when starting to process a file
	
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
				"""Callback when a prompt is saved to database"""
				self.prompt_added.emit()
			
			def file_callback(filename):
				"""Callback when starting to process a file"""
				self.file_processing.emit(filename)
			
			total_generated = generate_prompts_batch(
				db=self.db,
				api_key=self.api_key,
				service=self.service,
				model=self.model,
				file_ids=None,  # Generate for all files
				stop_flag=self.stop_flag,
				progress_callback=progress_callback,
				prompt_saved_callback=prompt_saved_callback,
				file_callback=file_callback
			)
			
			self.finished.emit(total_generated)
			
		except Exception as e:
			self.error_occurred.emit(str(e))



class PromptGeneratorDialog(QDialog):
	"""Empty placeholder dialog for the Prompt Generator tool."""
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Prompt Generator")
		self.setFixedSize(900, 750)
		self.page_size = 20
		
		# Database connection
		from database import db_operation
		self.db = db_operation.ImageTeaDB()
		
		# Realtime refresh timer
		self.refresh_timer = QTimer()
		self.refresh_timer.timeout.connect(self.refresh_table_if_needed)
		self.is_generating = False
		self.last_prompt_count = 0
		self.current_generating_file = None  # Track current file being processed
		# Ensure icon attributes exist before any UI update calls
		self.gen_icon = None
		self.stop_icon = None
		# Initialize pagination and prompt storage before loading
		self.current_page = 1
		# prompt items loaded from database
		self.prompt_data = []
		self.total_prompts = 0
		# Worker thread for generation (may be created later)
		self.worker = None
		
		# Load initial data
		self.load_prompts_from_db()
		
		# Start realtime refresh
		self.start_realtime_refresh()
		self.current_page = 1
		# prompt items loaded from database
		self.prompt_data = []
		self.total_prompts = 0
		
		# Worker thread for generation
		self.worker = None

		main_layout = QVBoxLayout(self)

		# API Key Section at the very top
		if self.db:
			self.api_key_section = ApiKeySectionWidget(self.db, self)
			main_layout.addWidget(self.api_key_section)
			
			# Connect to API key changes
			self.api_key_section.api_key_changed.connect(self.on_api_key_changed)
			
			# Set initial values
			self.api_key = self.api_key_section.get_current_api_key()
			self.selected_service = self.api_key_section.get_current_service()
			self.selected_model_name = self.api_key_section.get_current_model()

		# Top options HBox (no frame, keep layout compact)
		# Options layout: Prompt Type, Aspect Ratio, Prompt Length, Prompts Per File
		options_layout = QHBoxLayout()
		
		# Prompt Type combo
		type_label = QLabel("Type")
		self.prompt_type_combo = QComboBox()
		self.prompt_type_combo.setMinimumWidth(120)
		self.prompt_type_combo.setToolTip("Select prompt generation type")
		options_layout.addWidget(type_label)
		options_layout.addWidget(self.prompt_type_combo)
		
		# Aspect Ratio combo  
		ratio_label = QLabel("Aspect Ratio")
		self.aspect_ratio_combo = QComboBox()
		self.aspect_ratio_combo.setMinimumWidth(120)
		self.aspect_ratio_combo.setToolTip("Select aspect ratio for generated prompts")
		options_layout.addWidget(ratio_label)
		options_layout.addWidget(self.aspect_ratio_combo)
		
		# Prompt length
		length_label = QLabel("Prompt Length")
		self.prompt_length_spin = QSpinBox()
		self.prompt_length_spin.setMinimum(1)
		self.prompt_length_spin.setMaximum(2048)
		self.prompt_length_spin.setValue(64)
		self.prompt_length_spin.setToolTip("Maximum token/word length for generated prompts")
		options_layout.addWidget(length_label)
		options_layout.addWidget(self.prompt_length_spin)
		
		# Prompts per file
		perfile_label = QLabel("Prompts per File")
		self.prompts_per_file_spin = QSpinBox()
		self.prompts_per_file_spin.setMinimum(1)
		self.prompts_per_file_spin.setMaximum(100)
		self.prompts_per_file_spin.setValue(1)
		self.prompts_per_file_spin.setToolTip("How many prompts to generate per file")
		options_layout.addWidget(perfile_label)
		options_layout.addWidget(self.prompts_per_file_spin)
		
		# Variation Level
		variation_label = QLabel("Variation")
		self.variation_level_spin = QSpinBox()
		self.variation_level_spin.setMinimum(1)
		self.variation_level_spin.setMaximum(10)
		self.variation_level_spin.setValue(5)
		self.variation_level_spin.setToolTip("Control how different each prompt should be (1=very similar, 10=completely different)")
		options_layout.addWidget(variation_label)
		options_layout.addWidget(self.variation_level_spin)
		
		# push remaining space to the right
		options_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
		main_layout.addLayout(options_layout)

		# Load saved options from ai_config.json (if present)
		cfg = self.load_ai_config()
		pg_section = cfg.get('prompt_generator', {}) if isinstance(cfg, dict) else {}
		settings = pg_section.get('settings', {}) if isinstance(pg_section, dict) else {}
		prompt_types = pg_section.get('prompt_types', {}) if isinstance(pg_section, dict) else {}
		aspect_ratios = pg_section.get('aspect_ratios', {}) if isinstance(pg_section, dict) else {}
		
		# Populate prompt type combo
		if prompt_types:
			for key, display_name in prompt_types.items():
				self.prompt_type_combo.addItem(display_name, key)
		else:
			# Default options if config not available
			self.prompt_type_combo.addItem("Image Generation", "image_generation")
			self.prompt_type_combo.addItem("Video Generation", "video_generation")
		
		# Populate aspect ratio combo
		if aspect_ratios:
			for key, display_name in aspect_ratios.items():
				self.aspect_ratio_combo.addItem(display_name, key)
		else:
			# Default options if config not available
			self.aspect_ratio_combo.addItem("Widescreen (16:9)", "16:9")
			self.aspect_ratio_combo.addItem("Square (1:1)", "1:1")
			self.aspect_ratio_combo.addItem("Portrait (9:16)", "9:16")
		
		# Load saved values
		if isinstance(settings.get('prompt_length'), int):
			self.prompt_length_spin.setValue(settings.get('prompt_length'))
		if isinstance(settings.get('prompts_per_file'), int):
			self.prompts_per_file_spin.setValue(settings.get('prompts_per_file'))
		if isinstance(settings.get('variation_level'), int):
			self.variation_level_spin.setValue(settings.get('variation_level'))
		
		# Set saved prompt type
		saved_prompt_type = settings.get('prompt_type', 'image_generation')
		for i in range(self.prompt_type_combo.count()):
			if self.prompt_type_combo.itemData(i) == saved_prompt_type:
				self.prompt_type_combo.setCurrentIndex(i)
				break
		
		# Set saved aspect ratio
		saved_aspect_ratio = settings.get('aspect_ratio', '16:9')
		for i in range(self.aspect_ratio_combo.count()):
			if self.aspect_ratio_combo.itemData(i) == saved_aspect_ratio:
				self.aspect_ratio_combo.setCurrentIndex(i)
				break

		# Save options when changed
		self.prompt_length_spin.valueChanged.connect(self.save_options_to_config)
		self.prompts_per_file_spin.valueChanged.connect(self.save_options_to_config)
		self.variation_level_spin.valueChanged.connect(self.save_options_to_config)
		self.prompt_type_combo.currentIndexChanged.connect(self.save_options_to_config)
		self.aspect_ratio_combo.currentIndexChanged.connect(self.save_options_to_config)

		# Load prompts from DB if available
		if self.db:
			self.load_prompts_from_db()
		
		# Pagination controls (right aligned with page size)
		paging_layout = QHBoxLayout()
		
		# Page size selector (left side)
		pagesize_label = QLabel("Per Page")
		self.page_size_combo = QComboBox()
		self.page_size_combo.addItems(["10", "20", "30", "50", "80", "100", "200"])
		self.page_size_combo.setCurrentText("20")
		self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)
		paging_layout.addWidget(pagesize_label)
		paging_layout.addWidget(self.page_size_combo)
		
		# Spacer to push pagination controls to the right
		paging_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
		
		# Use qtawesome icons for buttons
		prev_icon = qta.icon('fa6s.chevron-left')
		next_icon = qta.icon('fa6s.chevron-right')
		self.prev_btn = QPushButton(prev_icon, "")
		self.prev_btn.setToolTip("Previous page")
		self.prev_btn.clicked.connect(self.go_prev)
		paging_layout.addWidget(self.prev_btn)

		self.page_label = QLabel()
		paging_layout.addWidget(self.page_label)

		self.page_spinner = QSpinBox()
		self.page_spinner.setMinimum(1)
		self.page_spinner.setMaximum(self.total_pages())
		self.page_spinner.setValue(self.current_page)
		self.page_spinner.setToolTip("Go to page")
		self.page_spinner.valueChanged.connect(self.on_page_spin)
		paging_layout.addWidget(self.page_spinner)

		self.next_btn = QPushButton(next_icon, "")
		self.next_btn.setToolTip("Next page")
		self.next_btn.clicked.connect(self.go_next)
		paging_layout.addWidget(self.next_btn)

		main_layout.addLayout(paging_layout)

		# Table with columns: Prompts, Characters, Created
		self.table = QTableWidget()
		self.table.setColumnCount(3)
		self.table.setHorizontalHeaderLabels(["Prompts", "Chars", "Created"])
		# Set column widths
		self.table.setColumnWidth(0, 500)  # Prompts - widest
		self.table.setColumnWidth(1, 60)   # Chars - narrow
		self.table.setColumnWidth(2, 150)  # Created - medium
		# Allow text wrapping in prompts column
		self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
		self.table.setEditTriggers(QTableWidget.NoEditTriggers)
		# Make table keyboard-friendly for shortcuts
		self.table.setSelectionBehavior(QTableWidget.SelectRows)
		self.table.setSelectionMode(QTableWidget.SingleSelection)
		self.table.setFocusPolicy(Qt.StrongFocus)
		self.table.doubleClicked.connect(self.on_prompt_double_click)
		# Enable custom context menu for copying full prompts
		self.table.setContextMenuPolicy(Qt.CustomContextMenu)
		self.table.customContextMenuRequested.connect(self.on_table_context_menu)
		main_layout.addWidget(self.table)

		# Actions section below the table: stats on the left, progress in middle, buttons on the right
		actions_layout = QHBoxLayout()
		
		# Stats section with vertical layout (left side)
		stats_widget = QWidget()
		stats_layout = QVBoxLayout(stats_widget)
		stats_layout.setContentsMargins(0, 0, 0, 0)
		stats_layout.setSpacing(2)
		
		# Stats label 1 - Prompts count
		self.prompts_stats_label = QLabel("Prompts: 0/0")
		stats_layout.addWidget(self.prompts_stats_label)
		
		# Stats label 2 - Total files
		self.files_stats_label = QLabel("Total files: 0")
		stats_layout.addWidget(self.files_stats_label)
		
		# Stats label 3 - Progress counter
		self.progress_counter_label = QLabel("Progress: (0/0)")
		stats_layout.addWidget(self.progress_counter_label)
		
		# Stats label 4 - Currently generating
		self.generating_label = QLabel("Ready to generate")
		self.generating_label.setStyleSheet("color: #0066cc; font-weight: bold; font-style: normal;")
		stats_layout.addWidget(self.generating_label)
		
		actions_layout.addWidget(stats_widget)
		
		# spacer in middle
		actions_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
		
		# Clear prompts button
		try:
			clear_icon = qta.icon('fa6s.trash')
		except Exception:
			clear_icon = None
		if clear_icon:
			self.clear_btn = QPushButton(clear_icon, "Clear All")
		else:
			self.clear_btn = QPushButton("Clear All")
		self.clear_btn.setToolTip("Delete all generated prompts")
		self.clear_btn.clicked.connect(self.clear_all_prompts)
		actions_layout.addWidget(self.clear_btn)
		
		# Export CSV button
		try:
			export_icon = qta.icon('fa6s.download')
		except Exception:
			export_icon = None
		if export_icon:
			self.export_btn = QPushButton(export_icon, "Export CSV")
		else:
			self.export_btn = QPushButton("Export CSV")
		self.export_btn.setToolTip("Export prompts to CSV file")
		self.export_btn.clicked.connect(self.export_to_csv)
		actions_layout.addWidget(self.export_btn)
		
		# Generate button (right) - larger and with conditional styling
		try:
			gen_icon = qta.icon('fa6s.wand-magic-sparkles')
			stop_icon = qta.icon('fa6s.stop')
		except Exception:
			gen_icon = None
			stop_icon = None
			
		if gen_icon:
			self.generate_btn = QPushButton(gen_icon, "Generate Prompts")
		else:
			self.generate_btn = QPushButton("Generate Prompts")
			
		self.generate_btn.setMinimumHeight(40)  # Make button larger
		self.generate_btn.setMinimumWidth(150)
		self.generate_btn.setToolTip("Generate prompts based on current options")
		self.generate_btn.clicked.connect(self.toggle_generation)
		
		# Set initial styling consistent with batch processing helper
		self.generate_btn.setStyleSheet("""
			QPushButton {
				background-color: #4e9e20;
				color: white;
				border: none;
				border-radius: 6px;
				font-weight: bold;
				font-size: 12px;
			}
			QPushButton:hover {
				background-color: #3d7307;
			}
			QPushButton:pressed {
				background-color: #1e7e34;
			}
		""")
		
		# Store icons for later use
		self.gen_icon = gen_icon
		self.stop_icon = stop_icon
		self.is_generating = False
		
		actions_layout.addWidget(self.generate_btn)
		main_layout.addLayout(actions_layout)
		
		# Progress bar (initially hidden)
		self.progress_bar = QProgressBar()
		self.progress_bar.setVisible(False)
		self.progress_bar.setMinimum(0)
		self.progress_bar.setMaximum(100)
		self.progress_bar.setValue(0)
		main_layout.addWidget(self.progress_bar)

		self.update_pagination()

	def total_pages(self):
		if self.total_prompts == 0:
			return 1
		return ((self.total_prompts - 1) // self.page_size) + 1
	
	def on_page_size_changed(self, text):
		"""Handle page size changes"""
		try:
			new_page_size = int(text)
			self.page_size = new_page_size
			self.current_page = 1  # Reset to first page
			self.load_prompts_from_db()
			self.update_pagination()
		except ValueError:
			pass

	def update_pagination(self):
		total = self.total_pages()
		# clamp current page
		if self.current_page < 1:
			self.current_page = 1
		if self.current_page > total:
			self.current_page = total
		self.page_label.setText(f"Page {self.current_page} of {total}")
		self.page_spinner.setMaximum(total)
		self.page_spinner.setValue(self.current_page)
		
		# Update table with current page data
		self.table.setRowCount(len(self.prompt_data))
		for r, prompt_row in enumerate(self.prompt_data):
			# prompt_row structure: (id, file_id, prompt, created_at, filename)
			if len(prompt_row) >= 4:
				prompt_text = prompt_row[2] or ""
				created_at = prompt_row[3] or ""
				
				# Truncate prompt for display
				display_prompt = prompt_text[:100] + "..." if len(prompt_text) > 100 else prompt_text
				char_count = len(prompt_text)
				
				# Set table items (3 columns now)
				item_prompt = QTableWidgetItem(display_prompt)
				item_prompt.setData(Qt.UserRole, prompt_text)  # Store full prompt text for copy
				item_prompt.setData(Qt.UserRole + 1, prompt_row[0])  # Store prompt ID for editing
				
				self.table.setItem(r, 0, item_prompt)
				self.table.setItem(r, 1, QTableWidgetItem(str(char_count)))
				self.table.setItem(r, 2, QTableWidgetItem(str(created_at)[:19]))  # Truncate datetime
		
		# enable/disable buttons
		self.prev_btn.setEnabled(self.current_page > 1)
		self.next_btn.setEnabled(self.current_page < total)
		
		# Update stats - show total prompts and remaining to generate
		self.update_stats_display()

	def update_stats_display(self):
		"""Update stats display with separate labels for each information"""
		total_files = self.db.get_files_count() if self.db and hasattr(self.db, 'get_files_count') else 0
		prompts_per_file = self.prompts_per_file_spin.value()
		target_total = total_files * prompts_per_file
		current_prompts = self.total_prompts
		
		# Update separate labels
		self.prompts_stats_label.setText(f"Prompts: {current_prompts}/{target_total}")
		self.files_stats_label.setText(f"Total files: {total_files}")
		
		# Update generating status - always show, either current file or idle state
		if hasattr(self, 'current_generating_file') and self.current_generating_file:
			self.generating_label.setText(f"Generating prompt for {self.current_generating_file}")
		else:
			self.generating_label.setText("Ready to generate")

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

	def on_api_key_changed(self, api_key, service, model):
		"""Handle API key changes"""
		self.api_key = api_key
		self.selected_service = service
		self.selected_model_name = model
		print(f"API key changed: {service} - {model} - {api_key[-10:] if api_key else 'None'}")

	def toggle_generation(self):
		"""Toggle between generate and stop"""
		if self.is_generating:
			self.stop_generation()
		else:
			self.generate_prompts()
	
	def stop_generation(self):
		"""Stop the current generation process"""
		if self.worker and self.worker.isRunning():
			self.worker.stop()
			self.worker.wait(3000)  # Wait up to 3 seconds
		
		self.is_generating = False
		self.update_generate_button()
		self.progress_bar.setVisible(False)
		self.progress_counter_label.setText("")  # Clear progress counter
		print("Generation stopped")
		
		# Set moderate refresh when idle
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(5000)

	def update_generate_button(self):
		"""Update generate button appearance based on state"""
		# If UI hasn't created the generate button yet, skip safely
		if not hasattr(self, 'generate_btn'):
			return
		if self.is_generating:
			# Red stop button - consistent with batch processing helper
			if self.stop_icon:
				self.generate_btn.setIcon(self.stop_icon)
			self.generate_btn.setText("Stop Generation")
			self.generate_btn.setStyleSheet("""
				QPushButton {
					background-color: rgba(204, 0, 0, 0.3);
					color: white;
					border: none;
					border-radius: 6px;
					font-weight: bold;
					font-size: 12px;
				}
				QPushButton:hover {
					background-color: rgba(204, 0, 0, 0.5);
				}
				QPushButton:pressed {
					background-color: rgba(204, 0, 0, 0.7);
				}
			""")
		else:
			# Green generate button - consistent with batch processing helper
			if self.gen_icon:
				self.generate_btn.setIcon(self.gen_icon)
			self.generate_btn.setText("Generate Prompts")
			self.generate_btn.setStyleSheet("""
				QPushButton {
					background-color: #4e9e20;
					color: white;
					border: none;
					border-radius: 6px;
					font-weight: bold;
					font-size: 12px;
				}
				QPushButton:hover {
					background-color: #3d7307;
				}
				QPushButton:pressed {
					background-color: #1e7e34;
				}
			""")

	def generate_prompts(self):
		"""Generate prompts using AI services based on files in database with threading."""
		if not self.db:
			print("Error: Database not available for prompt generation")
			return
		
		if not self.api_key or not self.selected_service or not self.selected_model_name:
			print("Error: API key and model must be selected for prompt generation")
			return
		
		# Check if worker is already running
		if self.worker and self.worker.isRunning():
			return
		
		# Set generating state and update UI
		self.is_generating = True
		self.update_generate_button()
		self.progress_bar.setVisible(True)
		self.progress_bar.setValue(0)
		
		# Set very fast refresh during generation
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(1000)
		print("Starting prompt generation...")
		
		# Create and start worker thread
		self.worker = PromptGeneratorWorker(
			self.db, self.api_key, self.selected_service, self.selected_model_name
		)
		
		# Connect signals
		self.worker.progress_updated.connect(self.on_generation_progress)
		self.worker.progress_value_changed.connect(self.on_progress_value_changed)
		self.worker.finished.connect(self.on_generation_finished)
		self.worker.error_occurred.connect(self.on_generation_error)
		self.worker.prompt_added.connect(self.on_new_prompt_added)
		self.worker.file_processing.connect(self.on_file_processing)
		
		# Start the worker
		self.worker.start()
	
	def on_generation_progress(self, message):
		"""Handle progress updates from worker thread"""
		# Log to console
		print(f"Progress: {message}")
		
		# Extract progress counter if available (x/y) format
		if "(" in message and "/" in message and ")" in message:
			start = message.rfind("(")
			end = message.rfind(")")
			if start < end:
				progress_text = message[start+1:end]  # Extract "3/9"
				self.progress_counter_label.setText(f"Progress: ({progress_text})")
		else:
			self.progress_counter_label.setText("")
	
	def on_file_processing(self, filename):
		"""Handle when worker starts processing a file"""
		self.current_generating_file = filename
		self.update_stats_display()
	
	def on_progress_value_changed(self, value):
		"""Handle progress bar value updates"""
		self.progress_bar.setValue(value)
	
	def on_generation_finished(self, total_generated):
		"""Handle completion of prompt generation"""
		# Reset generating state
		self.is_generating = False
		self.current_generating_file = None  # Clear current file
		self.progress_counter_label.setText("Progress: (0/0)")  # Reset progress counter
		self.update_generate_button()
		self.progress_bar.setVisible(False)
		
		if total_generated > 0:
			# Final reload to ensure all data is current
			self.load_prompts_from_db()
			self.update_pagination()
			print(f"Successfully generated {total_generated} prompts")
		else:
			print("No prompts were generated")
		
		# Update stats after clearing generating status
		self.update_stats_display()
		
		# Set moderate refresh when idle
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(5000)
	
	def on_generation_error(self, error_message):
		"""Handle errors from worker thread"""
		print(f"Prompt generation error: {error_message}")
		# Reset generating state
		self.is_generating = False
		self.update_generate_button()
		self.progress_bar.setVisible(False)
		print("Generation failed - check console for details")

	def load_ai_config(self):
		"""Load ai_config.json from the project's configs folder. Returns dict or {}."""
		cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
		if not os.path.exists(cfg_path):
			return {}
		try:
			with open(cfg_path, 'r', encoding='utf-8') as f:
				return json.load(f)
		except Exception:
			print(f"Failed to load ai_config.json from {cfg_path}")
			return {}

	def save_options_to_config(self):
		"""Persist current prompt options into ai_config.json under prompt_generator.settings keys."""
		cfg = self.load_ai_config() or {}
		# Ensure prompt_generator.settings exists
		if 'prompt_generator' not in cfg or not isinstance(cfg['prompt_generator'], dict):
			cfg['prompt_generator'] = {}
		if 'settings' not in cfg['prompt_generator'] or not isinstance(cfg['prompt_generator']['settings'], dict):
			cfg['prompt_generator']['settings'] = {}
		cfg['prompt_generator']['settings']['prompt_length'] = int(self.prompt_length_spin.value())
		cfg['prompt_generator']['settings']['prompts_per_file'] = int(self.prompts_per_file_spin.value())
		cfg['prompt_generator']['settings']['variation_level'] = int(self.variation_level_spin.value())
		cfg['prompt_generator']['settings']['prompt_type'] = self.prompt_type_combo.currentData() or 'image_generation'
		cfg['prompt_generator']['settings']['aspect_ratio'] = self.aspect_ratio_combo.currentData() or '16:9'
		cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
		try:
			with open(cfg_path, 'w', encoding='utf-8') as f:
				json.dump(cfg, f, indent=2, ensure_ascii=False)
		except Exception as e:
			print(f"Failed to save ai_config.json: {e}")

	def load_prompts_from_db(self):
		"""Load prompts from the database with pagination support."""
		try:
			if not self.db:
				self.prompt_data = []
				self.total_prompts = 0
				return
				
			# Get total count
			if hasattr(self.db, 'get_generated_prompts_count'):
				self.total_prompts = self.db.get_generated_prompts_count()
			else:
				self.total_prompts = 0
			
			# Get paginated data
			if hasattr(self.db, 'get_generated_prompts_paginated'):
				self.prompt_data = self.db.get_generated_prompts_paginated(self.current_page, self.page_size)
			else:
				self.prompt_data = []
				
		except Exception as e:
			print(f"Failed loading prompts from DB: {e}")
			self.prompt_data = []
			self.total_prompts = 0
	
	def on_prompt_double_click(self, index):
		"""Handle double-click on prompt to open edit dialog"""
		if not index.isValid() or not self.db:
			return
			
		row = index.row()
		if row >= len(self.prompt_data):
			return
			
		# Get prompt ID from the first column data
		item = self.table.item(row, 0)
		if not item:
			return
			
		prompt_id = item.data(Qt.UserRole + 1)  # Get prompt ID
		if not prompt_id:
			return
			
		# Get full prompt data
		prompt_row = self.db.get_generated_prompt_by_id(prompt_id)
		if not prompt_row:
			return
			
		prompt_text = prompt_row[2]  # prompt text
		
		# Open edit dialog
		dialog = PromptEditDialog(prompt_id, prompt_text, self)
		if dialog.exec() == QDialog.Accepted:
			# Refresh table data
			self.load_prompts_from_db()
			self.update_pagination()

	def on_table_context_menu(self, pos):
		"""Show context menu to copy full prompt text from selected row."""
		if not hasattr(self, 'table'):
			return
		item = self.table.itemAt(pos)
		if not item:
			return
		row = item.row()
		first_item = self.table.item(row, 0)
		if not first_item:
			return
		
		# Get full prompt text directly from table item
		full_prompt = first_item.data(Qt.UserRole)
		if not full_prompt:
			return
		
		# Build context menu
		menu = QMenu(self)
		# Try to get copy icon
		try:
			copy_icon = qta.icon('fa6s.copy')
		except Exception:
			copy_icon = None
		copy_action = QAction(copy_icon, "Copy Prompt" if copy_icon else "Copy Prompt", self)
		copy_action.triggered.connect(lambda: self.copy_prompt_text(full_prompt))
		menu.addAction(copy_action)
		# Show menu at global position
		menu.exec(self.table.viewport().mapToGlobal(pos))

	def copy_prompt_text(self, prompt_text):
		"""Copy the given prompt text to clipboard."""
		try:
			if not prompt_text or not prompt_text.strip():
				print("No prompt text to copy")
				return
				
			# Copy to clipboard
			clipboard = QGuiApplication.clipboard()
			clipboard.setText(prompt_text)
			preview = (prompt_text[:80] + '...') if len(prompt_text) > 80 else prompt_text
			QToolTip.showText(QCursor.pos(), f"Copied: {preview}", self)
			print(f"Prompt copied to clipboard: {preview}")
			
		except Exception as e:
			print(f"Failed to copy prompt: {e}")

	def copy_selected_prompt(self, prompt_id=None):
		"""Copy the currently selected prompt (or given prompt_id) to clipboard."""
		try:
			if prompt_id is None:
				# Get currently selected row
				row = self.table.currentRow()
				print(f"Current table row: {row}")
				print(f"Total table rows: {self.table.rowCount()}")
				
				if row < 0 or row >= self.table.rowCount():
					print("No prompt selected for copying")
					return
				
				# Try multiple ways to get the item
				item = self.table.item(row, 0)
				print(f"Table item at row {row}, col 0: {item}")
				
				if not item:
					print("No valid item selected")
					return
				
				# Get and validate the prompt ID
				prompt_id = item.data(Qt.UserRole)
				print(f"Retrieved prompt_id from table item: {prompt_id} (type: {type(prompt_id)})")
				
				# Additional check - try to get from current selection
				selected_items = self.table.selectedItems()
				print(f"Selected items count: {len(selected_items)}")
				if selected_items:
					for i, sel_item in enumerate(selected_items):
						sel_data = sel_item.data(Qt.UserRole)
						print(f"Selected item {i}: data = {sel_data} (type: {type(sel_data)})")
				
				# Check if we have valid prompt_id
				if prompt_id is None or prompt_id is False:
					print("No prompt ID found for selected item")
					# Try alternative approach - get from prompt_data directly
					if 0 <= row < len(self.prompt_data):
						prompt_row_data = self.prompt_data[row]
						if len(prompt_row_data) > 0:
							prompt_id = prompt_row_data[0]  # First element should be ID
							print(f"Fallback: retrieved prompt_id from prompt_data: {prompt_id}")
					if not prompt_id:
						return
			
			# Fetch full prompt from DB
			if not self.db:
				print("Database not available for copying")
				return
			
			# Debug: print the prompt_id being used
			print(f"Attempting to copy prompt with ID: {prompt_id}")
			
			prompt_row = self.db.get_generated_prompt_by_id(prompt_id)
			print(f"Database returned prompt_row: {prompt_row}")
			if not prompt_row:
				print(f"No prompt found in database for ID: {prompt_id}")
				return
				
			if len(prompt_row) < 3:
				print(f"Invalid prompt row structure: {prompt_row}")
				return
				
			full_prompt = prompt_row[2]
			print(f"Extracted prompt text (first 50 chars): {full_prompt[:50] if full_prompt else 'None'}")
			
			if not full_prompt or not full_prompt.strip():
				print("Prompt text is empty")
				return
				
			# Copy to clipboard
			clipboard = QGuiApplication.clipboard()
			clipboard.setText(full_prompt)
			preview = (full_prompt[:80] + '...') if len(full_prompt) > 80 else full_prompt
			QToolTip.showText(QCursor.pos(), f"Copied: {preview}", self)
			print(f"Prompt copied to clipboard: {preview}")
			
		except Exception as e:
			print(f"Failed to copy prompt: {e}")
			import traceback
			traceback.print_exc()
	
	def clear_all_prompts(self):
		"""Clear all generated prompts after confirmation"""
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
				print("All prompts cleared")
			except Exception as e:
				print(f"Failed to clear prompts: {e}")
	
	def export_to_csv(self):
		"""Export all prompts to CSV file (prompts only)"""
		if not self.db:
			QMessageBox.warning(self, "Error", "Database not available")
			return
			
		try:
			# Get all prompts (not paginated)
			all_prompts = self.db.get_all_generated_prompts()
			if not all_prompts:
				QMessageBox.information(self, "Export", "No prompts to export")
				return
			
			# Generate default filename with timestamp
			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			default_filename = f"Image_Tea_Generated_Prompts_{timestamp}.csv"
			
			# Get home directory
			home_dir = os.path.expanduser("~")
			default_path = os.path.join(home_dir, default_filename)
			
			# Show save file dialog
			filename, _ = QFileDialog.getSaveFileName(
				self, "Export Prompts to CSV", default_path,
				"CSV Files (*.csv);;All Files (*)"
			)
			
			if not filename:
				return
				
			# Write CSV file with prompts only
			with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
				writer = csv.writer(csvfile)
				
				# Write data - only prompt text (no headers)
				for row in all_prompts:
					# row format: (id, file_id, prompt, created_at)
					# Export only the prompt text (index 2)
					writer.writerow([row[2]])
			
			QMessageBox.information(self, "Export Complete", f"Exported {len(all_prompts)} prompts to:\n{filename}")
			
		except Exception as e:
			print(f"Failed to export prompts: {e}")
			QMessageBox.critical(self, "Export Error", "Failed to export prompts - check console for details")

	def on_new_prompt_added(self):
		"""Handle when a new prompt is added during generation - instant table refresh"""
		if hasattr(self, 'table'):
			# Save current selection
			current_row = self.table.currentRow()
			# Reload data and update UI immediately
			self.load_prompts_from_db()
			self.update_pagination()
			# Restore selection if possible
			if current_row >= 0 and current_row < self.table.rowCount():
				item = self.table.item(current_row, 0)
				if item:
					self.table.setCurrentItem(item)

	def start_realtime_refresh(self):
		"""Start the realtime refresh timer"""
		# Get current prompt count for comparison
		if self.db:
			self.last_prompt_count = self.db.get_generated_prompts_count()
		
		# Start with fast refresh (1 second for very responsive UI)
		self.refresh_timer.start(1000)

	def refresh_table_if_needed(self):
		"""Check if table needs refresh and update if necessary"""
		if not self.db or not hasattr(self, 'table'):
			return
		
		# Get current prompt count
		current_count = self.db.get_generated_prompts_count()
		
		# If count changed, refresh the table
		if current_count != self.last_prompt_count:
			self.last_prompt_count = current_count
			
			# Refresh table for any changes
			current_row = self.table.currentRow()
			self.load_prompts_from_db()
			self.update_pagination()
			# Restore selection if possible
			if current_row >= 0 and current_row < self.table.rowCount():
				item = self.table.item(current_row, 0)
				if item:
					self.table.setCurrentItem(item)
		
		# Adjust timer interval based on generation state
		if self.is_generating and self.refresh_timer.interval() != 1000:
			self.refresh_timer.start(1000)  # Very fast refresh during generation
		elif not self.is_generating and self.refresh_timer.interval() != 5000:
			self.refresh_timer.start(5000)  # Moderate refresh when idle

	def closeEvent(self, event):
		"""Handle dialog close event"""
		# Stop the refresh timer
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.stop()
		
		# Stop generation if running
		if self.worker and self.worker.isRunning():
			self.worker.stop()
			self.worker.wait()
		
		event.accept()

