from PySide6.QtWidgets import (
	QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
	QPushButton, QHBoxLayout, QLabel, QSpinBox, QSpacerItem, QSizePolicy, QFrame, QApplication, QProgressBar,
	QComboBox, QMessageBox, QFileDialog, QWidget, QMenu, QToolTip
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QAction, QCursor, QKeySequence, QColor
import os
import json
import csv
import random
import time
from datetime import datetime
from config import BASE_PATH
import qtawesome as qta
from ui.api_key_section import ApiKeySectionWidget
from dialogs.tools.prompt_edit_dialog import PromptEditDialog


class PromptGeneratorWorker(QThread):
	"""Worker thread for prompt generation to prevent UI freezing"""
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
				file_ids=None,
				stop_flag=self.stop_flag,
				progress_callback=progress_callback,
				prompt_saved_callback=prompt_saved_callback,
				file_callback=file_callback
			)
			
			self.finished.emit(total_generated)
			
		except Exception as e:
			self.error_occurred.emit(str(e))


class CSVImportWorker(QThread):
	"""Worker thread for CSV import to prevent UI freezing"""
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
	"""Progress dialog for CSV import"""
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Importing CSV")
		self.setFixedSize(450, 150)
		self.setModal(True)
		
		layout = QVBoxLayout(self)
		
        
		self.status_label = QLabel("Preparing import...")
		layout.addWidget(self.status_label)
		
        
		self.progress_bar = QProgressBar()
		self.progress_bar.setRange(0, 100)
		self.progress_bar.setValue(0)
		layout.addWidget(self.progress_bar)
		
        
		self.cancel_btn = QPushButton("Cancel")
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
	"""Empty placeholder dialog for the Prompt Generator tool."""
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Prompt Generator")
		self.setFixedSize(900, 750)
		self.page_size = 20
		
        
		from database import db_operation
		self.db = db_operation.ImageTeaDB()
		
        
		self.refresh_timer = QTimer()
		self.refresh_timer.timeout.connect(self.refresh_table_if_needed)
		self.is_generating = False
		self.last_prompt_count = 0
		self.current_generating_file = None
        
		self.gen_icon = None
		self.stop_icon = None
        
		self.current_page = 1
        
		self.prompt_data = []
		self.total_prompts = 0
        
		self.worker = None
		
        
		self.load_prompts_from_db()
		
        
		self.start_realtime_refresh()
		self.current_page = 1
        
		self.prompt_data = []
		self.total_prompts = 0
		
        
		self.worker = None

		main_layout = QVBoxLayout(self)

        
		if self.db:
			self.api_key_section = ApiKeySectionWidget(self.db, self)
			main_layout.addWidget(self.api_key_section)
			
            
			self.api_key_section.api_key_changed.connect(self.on_api_key_changed)
			
            
			self.api_key = self.api_key_section.get_current_api_key()
			self.selected_service = self.api_key_section.get_current_service()
			self.selected_model_name = self.api_key_section.get_current_model()

        
        
		options_layout = QHBoxLayout()
		
        
		type_label = QLabel("Type")
		self.prompt_type_combo = QComboBox()
		self.prompt_type_combo.setMinimumWidth(120)
		self.prompt_type_combo.setToolTip("Select prompt generation type")
		options_layout.addWidget(type_label)
		options_layout.addWidget(self.prompt_type_combo)
		
        
		ratio_label = QLabel("Ratio")
		self.aspect_ratio_combo = QComboBox()
		self.aspect_ratio_combo.setMinimumWidth(120)
		self.aspect_ratio_combo.setToolTip("Select aspect ratio for generated prompts")
		options_layout.addWidget(ratio_label)
		options_layout.addWidget(self.aspect_ratio_combo)
		
        
		length_label = QLabel("Length")
		self.prompt_length_spin = QSpinBox()
		self.prompt_length_spin.setMinimum(1)
		self.prompt_length_spin.setMaximum(2048)
		self.prompt_length_spin.setValue(64)
		self.prompt_length_spin.setToolTip("Maximum token/word length for generated prompts")
		options_layout.addWidget(length_label)
		options_layout.addWidget(self.prompt_length_spin)
		
        
		perfile_label = QLabel("Prompts per File")
		self.prompts_per_file_spin = QSpinBox()
		self.prompts_per_file_spin.setMinimum(1)
		self.prompts_per_file_spin.setMaximum(100)
		self.prompts_per_file_spin.setValue(1)
		self.prompts_per_file_spin.setToolTip("How many prompts to generate per file")
		options_layout.addWidget(perfile_label)
		options_layout.addWidget(self.prompts_per_file_spin)
		
        
		variation_label = QLabel("Variation")
		self.variation_level_spin = QSpinBox()
		self.variation_level_spin.setMinimum(1)
		self.variation_level_spin.setMaximum(10)
		self.variation_level_spin.setValue(5)
		self.variation_level_spin.setToolTip("Control how different each prompt should be (1=very similar, 10=completely different)")
		options_layout.addWidget(variation_label)
		options_layout.addWidget(self.variation_level_spin)
		
        
		delay_label = QLabel("Delay")
		self.delay_combo = QComboBox()
		self.delay_combo.setEditable(True)
		self.delay_combo.addItems(["No Delay", "Random", "1", "2", "3", "4", "5", "10", "15", "20", "30"])
		
		config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
		try:
			with open(config_path, 'r', encoding='utf-8') as f:
				ai_config = json.load(f)
			saved_delay = ai_config.get('delay_interval', 'Random')
			self.delay_combo.setCurrentText(str(saved_delay))
		except Exception:
			self.delay_combo.setCurrentText('Random')
		
		self.delay_combo.setToolTip("Delay interval between files.\nNo Delay = 0s, Random = 1-5s, or enter custom value in seconds.")
		self.delay_combo.currentTextChanged.connect(self.save_delay_to_config)
		options_layout.addWidget(delay_label)
		options_layout.addWidget(self.delay_combo)
		
        
		options_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
		main_layout.addLayout(options_layout)

        
		cfg = self.load_ai_config()
		pg_section = cfg.get('prompt_generator', {}) if isinstance(cfg, dict) else {}
		settings = pg_section.get('settings', {}) if isinstance(pg_section, dict) else {}
		prompt_types = pg_section.get('prompt_types', {}) if isinstance(pg_section, dict) else {}
		aspect_ratios = pg_section.get('aspect_ratios', {}) if isinstance(pg_section, dict) else {}
		
        
		if prompt_types:
			for key, display_name in prompt_types.items():
				self.prompt_type_combo.addItem(display_name, key)
		else:
            
			self.prompt_type_combo.addItem("Image Generation", "image_generation")
			self.prompt_type_combo.addItem("Video Generation", "video_generation")
		
        
		if aspect_ratios:
			for key, display_name in aspect_ratios.items():
				self.aspect_ratio_combo.addItem(display_name, key)
		else:
            
			self.aspect_ratio_combo.addItem("Widescreen (16:9)", "16:9")
			self.aspect_ratio_combo.addItem("Square (1:1)", "1:1")
			self.aspect_ratio_combo.addItem("Portrait (9:16)", "9:16")
		
        
		if isinstance(settings.get('prompt_length'), int):
			self.prompt_length_spin.setValue(settings.get('prompt_length'))
		if isinstance(settings.get('prompts_per_file'), int):
			self.prompts_per_file_spin.setValue(settings.get('prompts_per_file'))
		if isinstance(settings.get('variation_level'), int):
			self.variation_level_spin.setValue(settings.get('variation_level'))
		
        
		saved_prompt_type = settings.get('prompt_type', 'image_generation')
		for i in range(self.prompt_type_combo.count()):
			if self.prompt_type_combo.itemData(i) == saved_prompt_type:
				self.prompt_type_combo.setCurrentIndex(i)
				break
		
        
		saved_aspect_ratio = settings.get('aspect_ratio', '16:9')
		for i in range(self.aspect_ratio_combo.count()):
			if self.aspect_ratio_combo.itemData(i) == saved_aspect_ratio:
				self.aspect_ratio_combo.setCurrentIndex(i)
				break

        
		self.prompt_length_spin.valueChanged.connect(self.save_options_to_config)
		self.prompts_per_file_spin.valueChanged.connect(self.save_options_to_config)
		self.variation_level_spin.valueChanged.connect(self.save_options_to_config)
		self.prompt_type_combo.currentIndexChanged.connect(self.save_options_to_config)
		self.aspect_ratio_combo.currentIndexChanged.connect(self.save_options_to_config)

        
		if self.db:
			self.load_prompts_from_db()
		
        
		paging_layout = QHBoxLayout()
		
        
		pagesize_label = QLabel("Per Page")
		self.page_size_combo = QComboBox()
		self.page_size_combo.addItems(["10", "20", "30", "50", "80", "100", "200"])
		self.page_size_combo.setCurrentText("20")
		self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)
		paging_layout.addWidget(pagesize_label)
		paging_layout.addWidget(self.page_size_combo)
		
        
		paging_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
		
        
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
		self.table.setToolTip("Double-click to edit • Middle-click to copy • Ctrl+C to copy selected prompt • Right-click for menu")
		self.table.doubleClicked.connect(self.on_prompt_double_click)
        
		self.table.setContextMenuPolicy(Qt.CustomContextMenu)
		self.table.customContextMenuRequested.connect(self.on_table_context_menu)
        
		self.table.mousePressEvent = self.table_mouse_press_event
        
		self.table.keyPressEvent = self.table_key_press_event

        
		top_buttons_layout = QHBoxLayout()
        
		top_buttons_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
		try:
			self.edit_config_btn = QPushButton(qta.icon('fa6s.gear'), "Edit Prompt")
		except Exception:
			self.edit_config_btn = QPushButton("Edit Prompt")
		self.edit_config_btn.setToolTip("Edit prompt generator configuration")
		self.edit_config_btn.clicked.connect(self.open_prompt_config_editor)
		top_buttons_layout.addWidget(self.edit_config_btn)
		
        
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
		top_buttons_layout.addWidget(self.clear_btn)
		
        
		try:
			export_icon = qta.icon('fa6s.upload')
		except Exception:
			export_icon = None
		if export_icon:
			self.export_btn = QPushButton(export_icon, "Export CSV")
		else:
			self.export_btn = QPushButton("Export CSV")
		self.export_btn.setToolTip("Export prompts to CSV file")
		self.export_btn.clicked.connect(self.export_to_csv)
		top_buttons_layout.addWidget(self.export_btn)
		
        
		try:
			import_icon = qta.icon('fa6s.download')
		except Exception:
			import_icon = None
		if import_icon:
			self.import_btn = QPushButton(import_icon, "Import CSV")
		else:
			self.import_btn = QPushButton("Import CSV")
		self.import_btn.setToolTip("Import prompts from CSV file")
		self.import_btn.clicked.connect(self.import_from_csv)
		top_buttons_layout.addWidget(self.import_btn)
		
		main_layout.addLayout(top_buttons_layout)
        
		main_layout.addLayout(paging_layout)
        
		main_layout.addWidget(self.table)

        
		actions_layout = QHBoxLayout()
		
        
		stats_widget = QWidget()
		stats_layout = QVBoxLayout(stats_widget)
		stats_layout.setContentsMargins(0, 0, 0, 0)
		stats_layout.setSpacing(2)
		
        
		self.prompts_stats_label = QLabel("Prompts: 0/0")
		stats_layout.addWidget(self.prompts_stats_label)
		
        
		self.files_stats_label = QLabel("Total files: 0")
		stats_layout.addWidget(self.files_stats_label)
		
        
		self.progress_counter_label = QLabel("Progress: (0/0)")
		stats_layout.addWidget(self.progress_counter_label)
		
        
		self.generating_label = QLabel("Ready to generate")
		self.generating_label.setStyleSheet("color: #0066cc; font-weight: bold; font-style: normal;")
		stats_layout.addWidget(self.generating_label)
		
		actions_layout.addWidget(stats_widget)
		
        
		actions_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
		

		
        
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
			
		self.generate_btn.setMinimumHeight(40)
		self.generate_btn.setMinimumWidth(150)
		self.generate_btn.setToolTip("Generate prompts based on current options")
		self.generate_btn.clicked.connect(self.toggle_generation)
		
        
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
		
        
		self.gen_icon = gen_icon
		self.stop_icon = stop_icon
		self.is_generating = False
		
		actions_layout.addWidget(self.generate_btn)
		main_layout.addLayout(actions_layout)
		
        
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
				try:
					copy_icon = qta.icon('fa6s.copy')
					copy_btn.setIcon(copy_icon)
				except Exception:
					copy_btn.setText("Copy")
				copy_btn.setFixedSize(40, 25)
				copy_btn.setToolTip("Copy prompt to clipboard")
				copy_btn.clicked.connect(lambda checked, text=prompt_text, pid=prompt_row[0]: self.copy_prompt_and_update_status(text, pid))
				self.table.setCellWidget(r, 3, copy_btn)
				
                
				copied_color = QColor(243, 200, 24, int(0.3 * 255))
				if status == 'copied':
                    
					for col in range(4):
						item = self.table.item(r, col)
						if item:
							item.setBackground(copied_color)
						else:
                            
							empty_item = QTableWidgetItem("")
							empty_item.setBackground(copied_color)
							self.table.setItem(r, col, empty_item)
					
                    
					copy_btn.setStyleSheet("""
						QPushButton {
							background-color: rgba(243, 200, 24, 77);
							border: 1px solid #ccc;
							border-radius: 3px;
						}
						QPushButton:hover {
							background-color: rgba(243, 200, 24, 100);
						}
					""")
				else:
                    
					copy_btn.setStyleSheet("")
		
		
        
		self.prev_btn.setEnabled(self.current_page > 1)
		self.next_btn.setEnabled(self.current_page < total)
		
        
		self.update_stats_display()

	def update_stats_display(self):
		"""Update stats display with separate labels for each information"""
		total_files = self.db.get_files_count() if self.db and hasattr(self.db, 'get_files_count') else 0
		prompts_per_file = self.prompts_per_file_spin.value()
		target_total = total_files * prompts_per_file
		current_prompts = self.total_prompts
		
        
		self.prompts_stats_label.setText(f"Prompts: {current_prompts}/{target_total}")
		self.files_stats_label.setText(f"Total files: {total_files}")
		
        
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
			self.worker.wait(3000)
		
		self.is_generating = False
		self.update_generate_button()
		self.progress_bar.setVisible(False)
		self.progress_counter_label.setText("")
		print("Generation stopped")
		
        
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(5000)

	def update_generate_button(self):
		"""Update generate button appearance based on state"""
        
		if not hasattr(self, 'generate_btn'):
			return
		if self.is_generating:
            
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
		
        
		if self.worker and self.worker.isRunning():
			return
		
        
		self.is_generating = True
		self.update_generate_button()
		self.progress_bar.setVisible(True)
		self.progress_bar.setValue(0)
		
        
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(1000)
		print("Starting prompt generation...")
		
        
		self.worker = PromptGeneratorWorker(
			self.db, self.api_key, self.selected_service, self.selected_model_name
		)
		
        
		self.worker.progress_updated.connect(self.on_generation_progress)
		self.worker.progress_value_changed.connect(self.on_progress_value_changed)
		self.worker.finished.connect(self.on_generation_finished)
		self.worker.error_occurred.connect(self.on_generation_error)
		self.worker.prompt_added.connect(self.on_new_prompt_added)
		self.worker.file_processing.connect(self.on_file_processing)
		
        
		self.worker.start()
	
	def on_generation_progress(self, message):
		"""Handle progress updates from worker thread"""
        
		print(f"Progress: {message}")
		
        
		if "(" in message and "/" in message and ")" in message:
			start = message.rfind("(")
			end = message.rfind(")")
			if start < end:
				progress_text = message[start+1:end]
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
        
		self.is_generating = False
		self.current_generating_file = None
		self.progress_counter_label.setText("Progress: (0/0)")
		self.update_generate_button()
		self.progress_bar.setVisible(False)
		
		if total_generated > 0:
            
			self.load_prompts_from_db()
			self.update_pagination()
			print(f"Successfully generated {total_generated} prompts")
		else:
			print("No prompts were generated")
		
        
		self.update_stats_display()
		
        
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.start(5000)
	
	def on_generation_error(self, error_message):
		"""Handle errors from worker thread"""
		print(f"Prompt generation error: {error_message}")
        
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
	
	def save_delay_to_config(self):
		"""Save delay interval to ai_config.json and update prompt section if available"""
		try:
			config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
			with open(config_path, 'r', encoding='utf-8') as f:
				config = json.load(f)
			
			config['delay_interval'] = self.delay_combo.currentText()
			
			with open(config_path, 'w', encoding='utf-8') as f:
				json.dump(config, f, indent=2, ensure_ascii=False)
			
			if self.parent() and hasattr(self.parent(), 'prompt_section'):
				self.parent().prompt_section.load_prompt_config()
				
		except Exception as e:
			print(f"Error saving delay to config: {e}")
	
	def open_prompt_config_editor(self):
		from dialogs.prompt_generator_config_dialog import PromptGeneratorConfigDialog
		
		dialog = PromptGeneratorConfigDialog(self)
		result = dialog.exec()
		
		if result == QDialog.Accepted:
			QMessageBox.information(self, "Success", "Prompt configuration updated successfully.")

	def load_prompts_from_db(self):
		"""Load prompts from the database with pagination support."""
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
		"""Handle double-click on prompt to open edit dialog"""
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
		
        
		dialog = PromptEditDialog(prompt_id, prompt_text, self)
		if dialog.exec() == QDialog.Accepted:
            
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
		
        
		full_prompt = first_item.data(Qt.UserRole)
		prompt_id = first_item.data(Qt.UserRole + 1)
		if not full_prompt:
			return
		
        
		menu = QMenu(self)
        
		try:
			copy_icon = qta.icon('fa6s.copy')
		except Exception:
			copy_icon = None
		copy_action = QAction(copy_icon, "Copy Prompt" if copy_icon else "Copy Prompt", self)
		copy_action.triggered.connect(lambda: self.copy_prompt_and_update_status(full_prompt, prompt_id))
		copy_action.setShortcut(QKeySequence("Ctrl+C"))
		menu.addAction(copy_action)
        
		menu.exec(self.table.viewport().mapToGlobal(pos))

	def copy_prompt_text(self, prompt_text):
		"""Copy the given prompt text to clipboard."""
		try:
			if not prompt_text or not prompt_text.strip():
				print("No prompt text to copy")
				return
				
            
			clipboard = QGuiApplication.clipboard()
			clipboard.setText(prompt_text)
			preview = (prompt_text[:80] + '...') if len(prompt_text) > 80 else prompt_text
			QToolTip.showText(QCursor.pos(), f"Copied: {preview}", self)
			print(f"Prompt copied to clipboard: {preview}")
			
		except Exception as e:
			print(f"Failed to copy prompt: {e}")

	def copy_prompt_and_update_status(self, prompt_text, prompt_id):
		"""Copy prompt to clipboard and update status to 'copied'"""
		try:
            
			clipboard = QGuiApplication.clipboard()
			if clipboard:
				clipboard.setText(prompt_text)
				print(f"Prompt copied to clipboard: {prompt_text[:50]}...")
				
                
				if self.db and hasattr(self.db, 'add_prompt_status') and (prompt_id is not None):
					self.db.add_prompt_status(prompt_id, 'copied')
					
                
				self.refresh_table_immediately()
				
                
				preview = (prompt_text[:80] + '...') if len(prompt_text) > 80 else prompt_text
				tooltip_text = f"Copied: {preview}"
				QToolTip.showText(QCursor.pos(), tooltip_text, self, msecShowTime=3000)
			else:
				print("Failed to access clipboard")
				
		except Exception as e:
			print(f"Error copying prompt and updating status: {e}")

	def refresh_table_immediately(self):
		"""Force immediate table refresh for status updates"""
		try:
            
			current_page = self.current_page
			
            
			self.load_prompts_from_db()
			
            
			self.current_page = current_page
			self.update_pagination()
			
            
			self.table.repaint()
			
		except Exception as e:
			print(f"Error refreshing table: {e}")

	def table_key_press_event(self, event):
		"""Handle keyboard shortcuts on table"""
        
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
		"""Handle mouse press events on table including middle click"""
        
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

	def copy_selected_prompt(self, prompt_id=None):
		"""Copy the currently selected prompt (or given prompt_id) to clipboard."""
		try:
			if prompt_id is None:
                
				row = self.table.currentRow()
				print(f"Current table row: {row}")
				print(f"Total table rows: {self.table.rowCount()}")
				
				if row < 0 or row >= self.table.rowCount():
					print("No prompt selected for copying")
					return
				
                
				item = self.table.item(row, 0)
				print(f"Table item at row {row}, col 0: {item}")
				
				if not item:
					print("No valid item selected")
					return
				
                
				prompt_id = item.data(Qt.UserRole)
				print(f"Retrieved prompt_id from table item: {prompt_id} (type: {type(prompt_id)})")
				
                
				selected_items = self.table.selectedItems()
				print(f"Selected items count: {len(selected_items)}")
				if selected_items:
					for i, sel_item in enumerate(selected_items):
						sel_data = sel_item.data(Qt.UserRole)
						print(f"Selected item {i}: data = {sel_data} (type: {type(sel_data)})")
				
                
				if prompt_id is None or prompt_id is False:
					print("No prompt ID found for selected item")
                    
					if 0 <= row < len(self.prompt_data):
						prompt_row_data = self.prompt_data[row]
						if len(prompt_row_data) > 0:
							prompt_id = prompt_row_data[0]
							print(f"Fallback: retrieved prompt_id from prompt_data: {prompt_id}")
					if not prompt_id:
						return
			
            
			if not self.db:
				print("Database not available for copying")
				return
			
            
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
            
			all_prompts = self.db.get_all_generated_prompts()
			if not all_prompts:
				QMessageBox.information(self, "Export", "No prompts to export")
				return
			
            
			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			default_filename = f"Image_Tea_Generated_Prompts_{timestamp}.csv"
			
            
			home_dir = os.path.expanduser("~")
			default_path = os.path.join(home_dir, default_filename)
			
            
			filename, _ = QFileDialog.getSaveFileName(
				self, "Export Prompts to CSV", default_path,
				"CSV Files (*.csv);;All Files (*)"
			)
			
			if not filename:
				return
				
            
			with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
				writer = csv.writer(csvfile)
				
                
				for row in all_prompts:
                    
                    
					writer.writerow([row[2]])
			
			QMessageBox.information(self, "Export Complete", f"Exported {len(all_prompts)} prompts to:\n{filename}")
			
		except Exception as e:
			print(f"Failed to export prompts: {e}")
			QMessageBox.critical(self, "Export Error", "Failed to export prompts - check console for details")

	def import_from_csv(self):
		"""Import prompts from CSV file using threaded progress dialog"""
		try:
			filename, _ = QFileDialog.getOpenFileName(
				self, 
				"Import Prompts from CSV", 
				os.path.expanduser("~"), 
				"CSV files (*.csv);;All files (*.*)"
			)
			
			if not filename:
				return
			
			if not self.db:
				QMessageBox.critical(self, "Import Error", "Database connection not available.")
				return
			
            
			progress_dialog = CSVImportProgressDialog(self)
			
            
			worker = CSVImportWorker(self.db, filename)
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
		"""Handle when CSV import is finished"""
		try:
            
			self.load_prompts_from_db()
			self.update_pagination()
			print(f"Successfully imported {imported_count} prompts from CSV")
		except Exception as e:
			print(f"Error refreshing table after import: {e}")
	
	def on_import_error(self, error_message):
		"""Handle CSV import errors"""
		QMessageBox.critical(self, "Import Error", f"Import failed:\n{error_message}")

	def on_new_prompt_added(self):
		"""Handle when a new prompt is added during generation - instant table refresh"""
		if hasattr(self, 'table'):
            
			current_row = self.table.currentRow()
            
			self.load_prompts_from_db()
			self.update_pagination()
            
			if current_row >= 0 and current_row < self.table.rowCount():
				item = self.table.item(current_row, 0)
				if item:
					self.table.setCurrentItem(item)

	def start_realtime_refresh(self):
		"""Start the realtime refresh timer"""
        
		if self.db:
			self.last_prompt_count = self.db.get_generated_prompts_count()
		
        
		self.refresh_timer.start(1000)

	def refresh_table_if_needed(self):
		"""Check if table needs refresh and update if necessary"""
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

	def closeEvent(self, event):
		"""Handle dialog close event"""
        
		if hasattr(self, 'refresh_timer'):
			self.refresh_timer.stop()
		
        
		if self.worker and self.worker.isRunning():
			self.worker.stop()
			self.worker.wait()
		
		event.accept()

