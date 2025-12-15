from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QHBoxLayout, QLabel, QSpinBox, QSpacerItem, QSizePolicy, QFrame, QApplication, QProgressBar,
    QComboBox, QMessageBox, QFileDialog, QWidget, QMenu, QToolTip, QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QAction, QCursor, QKeySequence, QColor, QBrush
import qtawesome as qta
import json
import os
import random
import time
from datetime import datetime
from config import BASE_PATH
from ui.api_key_section import ApiKeySectionWidget
from dialogs.tools.imagen_config_dialog import ImagenConfigDialog
from helpers.tools.imagen_generator_helper import (
    load_imagen_config, save_imagen_config, generate_images_from_prompts,
    validate_image_generation_params, get_default_image_settings, get_openrouter_resolutions
)


class ImagenGeneratorWorker(QThread):
    """Worker thread for image generation to prevent UI freezing"""
    progress_updated = Signal(str)
    progress_value_changed = Signal(int)
    finished = Signal(int)
    error_occurred = Signal(str)
    image_generated = Signal()
    prompt_processing = Signal(str)
    status_updated = Signal(int, str, int, str)
    
    def __init__(self, db, api_key, service, model, config):
        super().__init__()
        self.db = db
        self.api_key = api_key
        self.service = service
        self.model = model
        self.config = config
        self.stop_flag = {'stop': False}
    
    def stop(self):
        self.stop_flag['stop'] = True
    
    def get_delay_interval(self):
        """Get delay interval from config"""
        try:
            config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            delay_value = config.get('delay_interval', 'Random')
            
            if delay_value == 'No Delay':
                return 0
            elif delay_value == 'Random':
                return random.uniform(1, 5)
            else:
                try:
                    return float(delay_value)
                except ValueError:
                    return random.uniform(1, 5)
        except Exception as e:
            print(f"Error loading delay interval: {e}")
            return random.uniform(1, 5)
    
    def run(self):
        try:
            print("Debug: Worker thread starting...")
            if self.config['generation_mode'] == 'Generate All':
                prompts = self.db.get_pending_imagen_prompts()
                print(f"Debug: Generate All mode - found {len(prompts)} pending prompts")
            else:
                prompts = [(p[0], p[1], p[2], p[3], p[4]) for p in self.db.get_pending_imagen_prompts() 
                          if p[2] == 'stopped' or p[2] is None]
                print(f"Debug: Continue from Stopped mode - found {len(prompts)} stopped/null prompts")
            
            total_prompts = len(prompts)
            print(f"Debug: Total prompts to process: {total_prompts}")
            
            if total_prompts == 0:
                self.progress_updated.emit("No prompts to process")
                self.finished.emit(0)
                return
            
            total_generated = 0
            
            for idx, (prompt_id, prompt_text, status, images_generated, images_requested) in enumerate(prompts):
                if self.stop_flag['stop']:
                    for remaining_idx in range(idx, len(prompts)):
                        remaining_prompt_id = prompts[remaining_idx][0]
                        self.db.update_imagen_generation_status(remaining_prompt_id, 'stopped')
                    break
                
                print(f"Debug: Processing prompt {idx+1}/{total_prompts}, ID={prompt_id}")
                print(f"Debug: Prompt text: {prompt_text[:100]}...")
                
                self.prompt_processing.emit(prompt_text[:50] + "..." if len(prompt_text) > 50 else prompt_text)
                progress = int((idx / total_prompts) * 100)
                self.progress_value_changed.emit(progress)
                
                if status is None:
                    print(f"Debug: Adding status record for prompt {prompt_id}")
                    self.db.add_imagen_generation_status(prompt_id, self.config['number_of_images'])
                    
                self.db.update_imagen_generation_status(prompt_id, 'processing')
                self.status_updated.emit(prompt_id, 'processing', 0, "")
                
                # Generate images for this prompt
                try:
                    print(f"Debug: Calling generate_images_from_prompts with model={self.model}")
                    
                    valid_params = ['number_of_images', 'image_size', 'aspect_ratio', 'output_mime_type', 'output_folder', 'generation_mode', 'resolution']
                    config_for_generation = {k: v for k, v in self.config.items() if k in valid_params}
                    
                    results = generate_images_from_prompts(
                        [prompt_text], 
                        self.api_key, 
                        self.service, 
                        self.model,
                        **config_for_generation
                    )
                    
                    print(f"Debug: Got results: {results}")
                    
                    if results and len(results) > 0:
                        result = results[0]
                        if result['status'] == 'success':
                            images_count = result.get('images_generated', self.config['number_of_images'])
                            print(f"Debug: Success! Generated {images_count} images")
                            # Persist generation metadata (warnings, requested resolution, sent message, saved_images_meta)
                            try:
                                meta = {
                                    'requested_resolution': result.get('requested_resolution'),
                                    'sent_message': result.get('sent_message'),
                                    'warnings': result.get('warnings', []),
                                    'saved_images_meta': result.get('saved_images_meta', [])
                                }
                                meta_folder = os.path.join(BASE_PATH, 'temp', 'imagen_meta')
                                os.makedirs(meta_folder, exist_ok=True)
                                meta_path = os.path.join(meta_folder, f"{prompt_id}.json")
                                with open(meta_path, 'w', encoding='utf-8') as mf:
                                    json.dump(meta, mf, indent=2, ensure_ascii=False)
                            except Exception as e:
                                print(f"Debug: Failed to save imagen meta for prompt {prompt_id}: {e}")
                            self.db.update_imagen_generation_status(prompt_id, 'generated', images_count)
                            self.status_updated.emit(prompt_id, 'generated', images_count, "")
                            total_generated += images_count
                            self.image_generated.emit()
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            print(f"Debug: Generation failed: {error_msg}")
                            self.db.update_imagen_generation_status(prompt_id, 'failed', 0, error_msg)
                            self.status_updated.emit(prompt_id, 'failed', 0, error_msg)
                            if 'quota' in error_msg.lower() or 'limit' in error_msg.lower():
                                self.error_occurred.emit(f"API quota exceeded: {error_msg}")
                                for remaining_idx in range(idx + 1, len(prompts)):
                                    remaining_prompt_id = prompts[remaining_idx][0]
                                    self.db.update_imagen_generation_status(remaining_prompt_id, 'stopped')
                                break
                    else:
                        print(f"Debug: No results returned")
                        self.db.update_imagen_generation_status(prompt_id, 'failed', 0, 'No results returned')
                        self.status_updated.emit(prompt_id, 'failed', 0, 'No results returned')
                        
                except Exception as e:
                    error_msg = str(e)
                    print(f"Debug: Exception during generation: {error_msg}")
                    self.db.update_imagen_generation_status(prompt_id, 'failed', 0, error_msg)
                    self.status_updated.emit(prompt_id, 'failed', 0, error_msg)
                    if 'quota' in error_msg.lower() or 'limit' in error_msg.lower():
                        self.error_occurred.emit(f"API error: {error_msg}")
                        for remaining_idx in range(idx + 1, len(prompts)):
                            remaining_prompt_id = prompts[remaining_idx][0]
                            self.db.update_imagen_generation_status(remaining_prompt_id, 'stopped')
                        break
                
                if idx < total_prompts - 1:
                    delay_seconds = self.get_delay_interval()
                    self.progress_updated.emit(f"Waiting {delay_seconds:.1f} seconds delay...")
                    time.sleep(delay_seconds)
            
            self.progress_value_changed.emit(100)
            print(f"Debug: Worker finished. Total generated: {total_generated}")
            self.finished.emit(total_generated)
            
        except Exception as e:
            error_msg = f"Generation error: {str(e)}"
            print(f"Debug: Worker error: {error_msg}")
            self.error_occurred.emit(error_msg)


class ImagenGeneratorDialog(QDialog):
    """Dialog for the Imagen Generator tool - generates images from prompts."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Imagen Generator")
        self.setFixedSize(900, 750)
        self.page_size = 20
        
        from database import db_operation
        self.db = db_operation.ImageTeaDB()
        
        self.current_page = 1
        self.prompt_data = []
        self.total_prompts = 0
        self.is_running = False
        self.worker = None
        
        try:
            self.config = load_imagen_config()
            if not self.config:
                self.config = self._get_default_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = self._get_default_config()
        
        self.load_prompts_from_db()
        
        self.setup_ui()
        self.update_pagination()
        self.update_stats_display()
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_stats_if_needed)
        self.refresh_timer.start(2000)

    def _get_default_config(self):
        """Get default configuration if loading fails"""
        return {
            'models': ['imagen-4.0-generate-001', 'imagen-4.0-ultra-generate-001', 'imagen-4.0-fast-generate-001', 'imagen-3.0-generate-002'],
            'settings': {
                'model': 'imagen-4.0-generate-001',
                'number_of_images': 4,
                'generation_mode': 'Generate All',
                'aspect_ratio': '1:1',
                'image_size': '1K',
                'resolution': '',
                'output_mime_type': 'image/png',
                'output_folder': ''
            },
            'aspect_ratios': {
                '1:1': 'Square (1:1)',
                '3:4': 'Portrait (3:4)',
                '4:3': 'Landscape (4:3)',
                '9:16': 'Vertical (9:16)',
                '16:9': 'Horizontal (16:9)'
            }
        }

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        if self.db:
            self.api_key_widget = ApiKeySectionWidget(
                db=self.db, 
                parent=self
            )
            self.api_key_widget.api_key_changed.connect(self.on_api_key_changed)
            main_layout.addWidget(self.api_key_widget)

        settings_frame = QFrame()
        settings_frame.setFrameStyle(QFrame.StyledPanel)
        settings_layout = QVBoxLayout(settings_frame)
        
        row1_layout = QHBoxLayout()
        
        model_label = QLabel("Model")
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        self.model_combo.setToolTip("Select Imagen model to use")
        models = self.config.get('models', ['imagen-4.0-generate-001'])
        for model in models:
            self.model_combo.addItem(model)
        
        saved_model = self.config.get('settings', {}).get('model', 'imagen-4.0-generate-001')
        if saved_model in models:
            self.model_combo.setCurrentText(saved_model)
        
        row1_layout.addWidget(model_label)
        row1_layout.addWidget(self.model_combo)
        
        self.config_btn = QPushButton(qta.icon('fa6s.gear'), "")
        self.config_btn.setToolTip("Configure Imagen models")
        self.config_btn.setFixedSize(30, 25)
        self.config_btn.clicked.connect(self.open_config_dialog)
        row1_layout.addWidget(self.config_btn)
        
        images_label = QLabel("Number of Images")
        self.num_images_spin = QSpinBox()
        self.num_images_spin.setMinimum(1)
        self.num_images_spin.setMaximum(4)
        self.num_images_spin.setValue(self.config.get('settings', {}).get('number_of_images', 4))
        self.num_images_spin.setToolTip("Number of images to generate per prompt (1-4)")
        row1_layout.addWidget(images_label)
        row1_layout.addWidget(self.num_images_spin)
        
        mode_label = QLabel("Mode")
        self.generation_mode_combo = QComboBox()
        self.generation_mode_combo.setMinimumWidth(180)
        self.generation_mode_combo.addItems(["Generate All", "Continue from Stopped"])
        self.generation_mode_combo.setCurrentText(self.config.get('settings', {}).get('generation_mode', 'Generate All'))
        self.generation_mode_combo.setToolTip("Choose generation mode: all prompts or continue from stopped")
        row1_layout.addWidget(mode_label)
        row1_layout.addWidget(self.generation_mode_combo)
        
        row1_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        settings_layout.addLayout(row1_layout)
        
        row2_layout = QHBoxLayout()
        
        ratio_label = QLabel("Aspect Ratio")
        self.aspect_ratio_combo = QComboBox()
        aspect_ratios = self.config.get('aspect_ratios', {})
        for key, value in aspect_ratios.items():
            self.aspect_ratio_combo.addItem(value, key)
        
        saved_ratio = self.config.get('settings', {}).get('aspect_ratio', '1:1')
        for i in range(self.aspect_ratio_combo.count()):
            if self.aspect_ratio_combo.itemData(i) == saved_ratio:
                self.aspect_ratio_combo.setCurrentIndex(i)

        # Populate resolution options based on current aspect ratio
        try:
            self.update_resolution_options()
        except Exception:
            pass
        
        row2_layout.addWidget(ratio_label)
        row2_layout.addWidget(self.aspect_ratio_combo)

        # Resolution combo for OpenRouter models (updates based on aspect ratio)
        res_label = QLabel("Resolution")
        self.resolution_combo = QComboBox()
        self.resolution_combo.setMinimumWidth(180)
        self.resolution_combo.setToolTip("Choose explicit resolution for OpenRouter image models (optional)")
        row2_layout.addWidget(res_label)
        row2_layout.addWidget(self.resolution_combo)
        # Populate initial resolution options now that combo exists
        try:
            self.update_resolution_options()
        except Exception:
            pass
        
        size_label = QLabel("Image Size")
        self.image_size_combo = QComboBox()
        self.image_size_combo.addItems(["1K", "2K"])
        self.image_size_combo.setCurrentText(self.config.get('settings', {}).get('image_size', '1K'))
        row2_layout.addWidget(size_label)
        row2_layout.addWidget(self.image_size_combo)
        
        format_label = QLabel("Output Format")
        self.output_format_combo = QComboBox()
        
        self.output_format_combo.addItem("PNG", "image/png")
        self.output_format_combo.addItem("JPG", "image/jpeg")
        
        saved_format = self.config.get('settings', {}).get('output_mime_type', 'image/png')
        for i in range(self.output_format_combo.count()):
            if self.output_format_combo.itemData(i) == saved_format:
                self.output_format_combo.setCurrentIndex(i)
                break
        
        row2_layout.addWidget(format_label)
        row2_layout.addWidget(self.output_format_combo)
        
        row2_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        settings_layout.addLayout(row2_layout)
        
        row2_5_layout = QHBoxLayout()
        
        delay_label = QLabel("Delay Interval")
        self.delay_combo = QComboBox()
        self.delay_combo.setEditable(True)
        self.delay_combo.addItems(["Random", "1", "2", "3", "4", "5", "10", "15", "20", "30"])
        
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                ai_config = json.load(f)
            saved_delay = ai_config.get('delay_interval', 'Random')
            self.delay_combo.setCurrentText(str(saved_delay))
        except Exception:
            self.delay_combo.setCurrentText('Random')
        
        self.delay_combo.setToolTip("Delay interval between batches.\nRandom = 1-5s, or enter custom value in seconds.")
        self.delay_combo.currentTextChanged.connect(self.save_delay_to_config)
        row2_5_layout.addWidget(delay_label)
        row2_5_layout.addWidget(self.delay_combo)
        
        row2_5_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        settings_layout.addLayout(row2_5_layout)
        
        row3_layout = QHBoxLayout()
        
        folder_label = QLabel("Output Folder")
        self.output_folder_line = QLineEdit()
        self.output_folder_line.setPlaceholderText("Select output folder for generated images...")
        saved_folder = self.config.get('settings', {}).get('output_folder', '')
        if saved_folder:
            self.output_folder_line.setText(saved_folder)
        row3_layout.addWidget(folder_label)
        row3_layout.addWidget(self.output_folder_line)
        
        self.browse_btn = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.browse_btn.setToolTip("Browse for output folder")
        self.browse_btn.setFixedSize(30, 25)
        self.browse_btn.clicked.connect(self.browse_output_folder)
        row3_layout.addWidget(self.browse_btn)
        
        self.paste_btn = QPushButton(qta.icon('fa6s.paste'), "")
        self.paste_btn.setToolTip("Paste output folder path from clipboard")
        self.paste_btn.setFixedSize(30, 25)
        self.paste_btn.clicked.connect(self.paste_output_folder)
        row3_layout.addWidget(self.paste_btn)
        
        settings_layout.addLayout(row3_layout)
        main_layout.addWidget(settings_frame)
        
        self.model_combo.currentTextChanged.connect(self.save_settings)
        self.num_images_spin.valueChanged.connect(self.save_settings)
        self.generation_mode_combo.currentTextChanged.connect(self.save_settings)
        self.aspect_ratio_combo.currentTextChanged.connect(self.save_settings)
        # Update resolution options when aspect ratio changes
        self.aspect_ratio_combo.currentTextChanged.connect(self.update_resolution_options)
        if hasattr(self, 'resolution_combo'):
            self.resolution_combo.currentTextChanged.connect(self.save_settings)
        self.image_size_combo.currentTextChanged.connect(self.save_settings)
        self.output_format_combo.currentTextChanged.connect(self.save_settings)
        self.output_folder_line.textChanged.connect(self.save_settings)

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

        main_layout.addLayout(paging_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Prompts", "Chars", "Status", "Created"])
        self.table.setColumnWidth(0, 400)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 150)
        
        header = self.table.horizontalHeader()
        header.setDefaultSectionSize(100)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(3, Qt.DescendingOrder)
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_table_context_menu)
        
        self.table.doubleClicked.connect(self.on_prompt_double_click)
        
        main_layout.addWidget(self.table)

        # Statistics and generation display
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.StyledPanel)
        stats_layout = QVBoxLayout(stats_frame)
        
        # First row of stats
        stats_row1 = QHBoxLayout()
        self.total_prompts_label = QLabel("Total Prompts: 0")
        self.completed_prompts_label = QLabel("Completed: 0")
        self.pending_prompts_label = QLabel("Pending: 0")
        stats_row1.addWidget(self.total_prompts_label)
        stats_row1.addWidget(self.completed_prompts_label)
        stats_row1.addWidget(self.pending_prompts_label)
        stats_row1.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        stats_layout.addLayout(stats_row1)
        
        # Second row of stats
        stats_row2 = QHBoxLayout()
        self.total_images_label = QLabel("Generated Images: 0")
        self.remaining_prompts_label = QLabel("Remaining: 0")
        self.current_generation_label = QLabel("Ready to generate")
        self.current_generation_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        stats_row2.addWidget(self.total_images_label)
        stats_row2.addWidget(self.remaining_prompts_label)
        stats_row2.addWidget(self.current_generation_label)
        stats_row2.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        stats_layout.addLayout(stats_row2)
        
        main_layout.addWidget(stats_frame)

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Bottom buttons layout
        buttons_layout = QHBoxLayout()
        
        # Left side buttons
        self.clear_btn = QPushButton(qta.icon('fa6s.trash'), "Clear All")
        self.clear_btn.setToolTip("Clear all generated images status from database")
        self.clear_btn.clicked.connect(self.clear_all_status)
        buttons_layout.addWidget(self.clear_btn)
        
        self.export_btn = QPushButton(qta.icon('fa6s.file-export'), "Export CSV")
        self.export_btn.setToolTip("Export prompts with generation status to CSV file")
        self.export_btn.clicked.connect(self.export_to_csv)
        buttons_layout.addWidget(self.export_btn)
        
        # Spacer to push Run Prompt button to the right
        buttons_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Main action button - conditional styling like prompt generator
        self.run_btn = QPushButton(qta.icon('fa6s.play'), "Run Prompt")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setMinimumWidth(150)
        self.run_btn.setToolTip("Generate images from prompts")
        self.run_btn.clicked.connect(self.toggle_generation)
        
        # Set initial styling - green for run, red for stop
        self.update_run_button()
        
        buttons_layout.addWidget(self.run_btn)
        
        main_layout.addLayout(buttons_layout)

        # Load table data
        self.refresh_table()

    def browse_output_folder(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder_line.setText(folder)

    def paste_output_folder(self):
        """Paste output folder path from clipboard"""
        clipboard = QGuiApplication.clipboard()
        text = clipboard.text().strip()
        if text and os.path.isdir(text):
            self.output_folder_line.setText(text)
        elif text:
            QMessageBox.warning(self, "Invalid Path", "The clipboard text is not a valid directory path.")

    def save_settings(self):
        """Save current settings to configuration"""
        try:
            config = load_imagen_config()
            if 'settings' not in config:
                config['settings'] = {}
            
            if hasattr(self, 'model_combo'):
                config['settings']['model'] = self.model_combo.currentText()
            if hasattr(self, 'num_images_spin'):
                config['settings']['number_of_images'] = self.num_images_spin.value()
            if hasattr(self, 'generation_mode_combo'):
                config['settings']['generation_mode'] = self.generation_mode_combo.currentText()
            if hasattr(self, 'aspect_ratio_combo'):
                config['settings']['aspect_ratio'] = self.aspect_ratio_combo.currentData()
            if hasattr(self, 'image_size_combo'):
                config['settings']['image_size'] = self.image_size_combo.currentText()
            if hasattr(self, 'resolution_combo'):
                # store resolution string (empty means auto/default)
                res = self.resolution_combo.currentData() or self.resolution_combo.currentText()
                config['settings']['resolution'] = res
            if hasattr(self, 'output_format_combo'):
                config['settings']['output_mime_type'] = self.output_format_combo.currentData()
            if hasattr(self, 'output_folder_line'):
                config['settings']['output_folder'] = self.output_folder_line.text()
            
            save_imagen_config(config)
            self.config = config
            
        except Exception as e:
            print(f"Error saving settings: {e}")

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

    def update_resolution_options(self):
        """Populate resolution options based on selected aspect ratio (OpenRouter mapping)."""
        try:
            ar = self.aspect_ratio_combo.currentData() or self.aspect_ratio_combo.currentText()
            options = get_openrouter_resolutions(ar)
            if not hasattr(self, 'resolution_combo'):
                return
            self.resolution_combo.blockSignals(True)
            self.resolution_combo.clear()
            # First option: Auto (choose highest available if left unset)
            self.resolution_combo.addItem("Auto (highest available)", "")
            for opt in options:
                self.resolution_combo.addItem(opt, opt)
            # Try to set saved value
            saved_res = self.config.get('settings', {}).get('resolution', '')
            if saved_res:
                for i in range(self.resolution_combo.count()):
                    if self.resolution_combo.itemData(i) == saved_res or self.resolution_combo.itemText(i) == saved_res:
                        self.resolution_combo.setCurrentIndex(i)
                        break
            self.resolution_combo.blockSignals(False)
        except Exception:
            pass

    def update_run_button(self):
        """Update run button appearance based on current state"""
        if self.is_running:
            self.run_btn.setIcon(qta.icon('fa6s.stop'))
            self.run_btn.setText("Stop Generation")
            self.run_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
                QPushButton:pressed {
                    background-color: #bd2130;
                }
            """)
        else:
            self.run_btn.setIcon(qta.icon('fa6s.play'))
            self.run_btn.setText("Run Prompt")
            self.run_btn.setStyleSheet("""
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

    def toggle_generation(self):
        """Toggle image generation on/off"""
        if self.is_running:
            self.stop_generation()
        else:
            self.start_generation()

    def start_generation(self):
        """Start image generation process"""
        if not self.output_folder_line.text().strip():
            QMessageBox.warning(self, "Output Folder Required", 
                              "Please select an output folder for generated images.")
            return
        
        if not os.path.exists(self.output_folder_line.text()):
            QMessageBox.warning(self, "Invalid Output Folder", 
                              "The selected output folder does not exist.")
            return
        
        api_key = self.api_key_widget.get_current_api_key()
        service = self.api_key_widget.get_current_service()
        model_name = self.api_key_widget.get_current_model()
        
        if not api_key:
            QMessageBox.warning(self, "API Key Required", 
                              "Please select an API key before starting generation.")
            return
        
        generation_config = {
            'model': self.model_combo.currentText(),
            'number_of_images': self.num_images_spin.value(),
            'generation_mode': self.generation_mode_combo.currentText(),
            'aspect_ratio': self.aspect_ratio_combo.currentData() or '1:1',
            'image_size': self.image_size_combo.currentText(),
            'resolution': self.resolution_combo.currentData() or self.resolution_combo.currentText(),
            'output_mime_type': self.output_format_combo.currentData() or 'image/png',
            'output_folder': self.output_folder_line.text()
        }
        
        imagen_model = self.model_combo.currentText()
        self.worker = ImagenGeneratorWorker(self.db, api_key, service, imagen_model, generation_config)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.progress_value_changed.connect(self.on_progress_value_changed)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error_occurred.connect(self.on_generation_error)
        self.worker.image_generated.connect(self.on_image_generated)
        self.worker.prompt_processing.connect(self.on_prompt_processing)
        self.worker.status_updated.connect(self.update_table_row_status)
        
        self.is_running = True
        self.update_run_button()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.load_prompts_from_db()
        self.refresh_table()
        
        self.worker.start()

    def stop_generation(self):
        """Stop image generation process"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.current_generation_label.setText("Stopping generation...")
            self.current_generation_label.setStyleSheet("color: #ffc107; font-weight: bold;")
            
            self.load_prompts_from_db()
            self.refresh_table()

    def on_progress_updated(self, message):
        """Handle progress message updates"""
        self.current_generation_label.setText(message)

    def on_progress_value_changed(self, value):
        """Handle progress bar value changes"""
        self.progress_bar.setValue(value)

    def on_prompt_processing(self, prompt_text):
        """Handle prompt processing updates"""
        self.current_generation_label.setText(f"Generating images for: {prompt_text}")
        self.current_generation_label.setStyleSheet("color: #007bff; font-weight: bold;")

    def on_image_generated(self):
        """Handle when a new image is generated - just refresh stats, table is updated real-time via status_updated"""
        self.refresh_stats_if_needed()

    def on_generation_finished(self, total_generated):
        """Handle generation completion"""
        self.is_running = False
        self.update_run_button()
        self.progress_bar.setVisible(False)
        self.current_generation_label.setText(f"Generation completed. {total_generated} images generated.")
        self.current_generation_label.setStyleSheet("color: #28a745; font-weight: bold;")
        self.refresh_stats_if_needed()
        
        self.load_prompts_from_db()
        self.refresh_table()
        
        if total_generated > 0:
            QMessageBox.information(self, "Generation Complete", 
                                  f"Successfully generated {total_generated} images!")

    def on_generation_error(self, error_message):
        """Handle generation errors"""
        self.is_running = False
        self.update_run_button()
        self.progress_bar.setVisible(False)
        self.current_generation_label.setText(f"Generation stopped: {error_message}")
        self.current_generation_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        self.refresh_stats_if_needed()
        
        self.load_prompts_from_db()
        self.refresh_table()
        
        QMessageBox.warning(self, "Generation Error", error_message)

    def refresh_stats_if_needed(self):
        """Refresh statistics display"""
        try:
            self.update_stats_display()
        except Exception as e:
            print(f"Error refreshing stats: {e}")

    def load_prompts_from_db(self):
        """Load prompts from database with pagination and generation status"""
        if not self.db:
            self.prompt_data = []
            self.total_prompts = 0
            return
            
        try:
            self.total_prompts = self.db.get_generated_prompts_count()
            
            self.prompt_data = []
            prompts = self.db.get_generated_prompts_paginated(self.current_page, self.page_size)
            
            for prompt_record in prompts:
                prompt_id = prompt_record[0]
                
                try:
                    status_record = self.db.get_imagen_generation_status(prompt_id)
                    status = status_record[2] if status_record else None
                except:
                    status = None
                
                self.prompt_data.append({
                    'id': prompt_record[0],
                    'file_id': prompt_record[1],
                    'prompt': prompt_record[2],
                    'created_at': prompt_record[3],
                    'status': status or 'pending'
                })
                
        except Exception as e:
            print(f"Error loading prompts from database: {e}")
            self.prompt_data = []
            self.total_prompts = 0
            
        for prompt_item in self.prompt_data:
            if 'status' not in prompt_item:
                prompt_item['status'] = 'pending'

    def update_stats_display(self):
        """Update statistics display with generation information"""
        if not self.db:
            return
            
        try:
            stats = self.db.get_imagen_generation_stats()
            
            self.total_prompts_label.setText(f"Total Prompts: {stats['total_prompts']}")
            self.completed_prompts_label.setText(f"Completed: {stats['completed']}")
            self.pending_prompts_label.setText(f"Pending: {stats['pending'] + stats['no_status']}")
            self.total_images_label.setText(f"Generated Images: {stats['total_images']}")
            self.remaining_prompts_label.setText(f"Remaining: {stats['pending'] + stats['no_status'] + stats['stopped']}")
            
        except Exception as e:
            print(f"Error updating stats: {e}")
            self.total_prompts_label.setText("Total Prompts: 0")
            self.completed_prompts_label.setText("Completed: 0") 
            self.pending_prompts_label.setText("Pending: 0")
            self.total_images_label.setText("Generated Images: 0")
            self.remaining_prompts_label.setText("Remaining: 0")

    def refresh_table(self):
        """Refresh the table with current data including generation status"""
        was_sorting_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        
        self.table.setRowCount(len(self.prompt_data))
        
        for row, prompt_data in enumerate(self.prompt_data):
            prompt_text = prompt_data['prompt']
            truncated_prompt = prompt_text if len(prompt_text) <= 100 else prompt_text[:97] + "..."
            prompt_item = QTableWidgetItem(truncated_prompt)
            prompt_item.setData(Qt.UserRole, prompt_data['id'])
            prompt_item.setToolTip(prompt_text)
            self.table.setItem(row, 0, prompt_item)
            
            char_count = len(prompt_text)
            char_item = QTableWidgetItem(str(char_count))
            char_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, char_item)
            
            status = prompt_data.get('status', 'pending')
            status_item = QTableWidgetItem(status.title() if status else 'Pending')
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, status_item)
            
            created_str = prompt_data['created_at']
            if created_str:
                try:
                    created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    formatted_date = created_dt.strftime('%Y-%m-%d %H:%M')
                except:
                    formatted_date = created_str
            else:
                formatted_date = "Unknown"
            
            created_item = QTableWidgetItem(formatted_date)
            created_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, created_item)
            
            status_color = self._status_color(status)
            
            for col in range(self.table.columnCount()):
                cell_item = self.table.item(row, col)
                if cell_item:
                    cell_item.setBackground(QBrush(status_color))
                    cell_item.setData(Qt.UserRole + 1, status)
        
        self.table.setSortingEnabled(was_sorting_enabled)
        if was_sorting_enabled:
            self.table.sortByColumn(3, Qt.DescendingOrder)
        
        self.update_stats_display()

    def total_pages(self):
        if self.page_size <= 0:
            return 1
        return max(1, (self.total_prompts + self.page_size - 1) // self.page_size)
    
    def on_page_size_changed(self, text):
        try:
            new_page_size = int(text)
            if new_page_size != self.page_size:
                self.page_size = new_page_size
                self.current_page = 1
                self.load_prompts_from_db()
                self.refresh_table()
                self.update_pagination()
        except ValueError:
            pass

    def update_pagination(self):
        total_pages = self.total_pages()
        
        self.page_spinner.setMaximum(total_pages)
        self.page_spinner.setValue(self.current_page)
        
        start_idx = (self.current_page - 1) * self.page_size + 1
        end_idx = min(self.current_page * self.page_size, self.total_prompts)
        
        if self.total_prompts == 0:
            self.page_label.setText("No prompts")
        else:
            self.page_label.setText(f"{start_idx}-{end_idx} of {self.total_prompts}")
        
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)

    def go_prev(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_prompts_from_db()
            self.refresh_table()
            self.update_pagination()

    def go_next(self):
        if self.current_page < self.total_pages():
            self.current_page += 1
            self.load_prompts_from_db()
            self.refresh_table()
            self.update_pagination()

    def on_page_spin(self, value):
        if value != self.current_page and 1 <= value <= self.total_pages():
            self.current_page = value
            self.load_prompts_from_db()
            self.refresh_table()
            self.update_pagination()

    def on_api_key_changed(self, api_key, service, model):
        """Called when API key selection changes"""
        has_api_key = bool(api_key and api_key.strip())
        has_output_folder = bool(self.output_folder_line.text().strip()) if hasattr(self, 'output_folder_line') else False
        if hasattr(self, 'run_btn'):
            self.run_btn.setEnabled(has_api_key and has_output_folder and not self.is_running)

        # Enable resolution combo when OpenRouter is available, even if service is 'openai' (OpenRouter-compatible keys)
        try:
            from helpers.ai_helper.openai_helper import _is_openrouter_key
        except Exception:
            def _is_openrouter_key(k):
                return isinstance(k, str) and k.startswith('sk-or-')

        is_or_key = _is_openrouter_key(api_key) if api_key else False
        is_or_service = service and service.lower() in ('openrouter', 'openrouter.ai')
        if hasattr(self, 'resolution_combo'):
            if is_or_service or is_or_key:
                self.resolution_combo.setEnabled(True)
                self.resolution_combo.setToolTip("Choose explicit resolution for OpenRouter image models (optional)")
                # refresh options to reflect aspect ratio
                try:
                    self.update_resolution_options()
                except Exception:
                    pass
            else:
                # Not OpenRouter-capable: set to Auto and disable
                try:
                    self.resolution_combo.blockSignals(True)
                    self.resolution_combo.clear()
                    self.resolution_combo.addItem("Auto (default)", "")
                    self.resolution_combo.setCurrentIndex(0)
                    self.resolution_combo.setEnabled(False)
                    self.resolution_combo.setToolTip("Resolution only available for OpenRouter image models (OpenRouter key required)")
                    self.resolution_combo.blockSignals(False)
                except Exception:
                    pass

    def clear_all_status(self):
        """Clear all generation status from database"""
        if not self.db:
            return
            
        stats = self.db.get_imagen_generation_stats()
        total_status_records = stats['completed'] + stats['pending'] + stats['stopped'] + stats['failed']
        
        if total_status_records == 0:
            QMessageBox.information(self, "Clear All", "No generation status to clear.")
            return
        
        reply = QMessageBox.question(self, "Clear All Status", 
                                   f"Are you sure you want to clear all {total_status_records} generation status records?\n\n"
                                   "This will reset all prompts to pending status. Images files will not be deleted.",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                self.db.clear_all_imagen_generation_status()
                self.load_prompts_from_db()
                self.refresh_table()
                self.update_stats_display()
                QMessageBox.information(self, "Clear All", "All generation status has been cleared successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear status: {str(e)}")

    def export_to_csv(self):
        """Export prompts with generation status to CSV file"""
        if self.total_prompts == 0:
            QMessageBox.information(self, "Export CSV", "No prompts to export.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Prompts with Status to CSV", 
            f"imagen_prompts_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV files (*.csv)")
        
        if filename and self.db:
            try:
                import csv
                all_prompts = self.db.get_all_generated_prompts()
                
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['ID', 'File ID', 'Prompt', 'Characters', 'Status', 'Images Generated', 'Created', 'Generated At'])
                    
                    for prompt in all_prompts:
                        prompt_id = prompt[0]
                        status_record = self.db.get_imagen_generation_status(prompt_id)
                        
                        if status_record:
                            status = status_record[2]
                            images_generated = status_record[3]
                            generated_at = status_record[5]
                        else:
                            status = 'pending'
                            images_generated = 0
                            generated_at = ''
                        
                        writer.writerow([
                            prompt[0],
                            prompt[1],
                            prompt[2],
                            len(prompt[2]),
                            status,
                            images_generated,
                            prompt[3],
                            generated_at
                        ])
                
                QMessageBox.information(self, "Export Complete", 
                                      f"Successfully exported {len(all_prompts)} prompts with status to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export CSV: {str(e)}")

    def on_prompt_double_click(self, index):
        """Handle double-click on prompt - show details"""
        row = index.row()
        if 0 <= row < len(self.prompt_data):
            prompt_data = self.prompt_data[row]
            
            status_record = self.db.get_imagen_generation_status(prompt_data['id'])
            
            details = f"Prompt ID: {prompt_data['id']}\n"
            details += f"Status: {prompt_data['status']}\n"
            details += f"Created: {prompt_data['created_at']}\n\n"
            
            if status_record:
                details += f"Images Generated: {status_record[3]}/{status_record[4]}\n"
                if status_record[5]:
                    details += f"Generated At: {status_record[5]}\n"
                if status_record[6]:
                    details += f"Error: {status_record[6]}\n"
                # Include any saved generation metadata if present
                try:
                    meta_path = os.path.join(BASE_PATH, 'temp', 'imagen_meta', f"{prompt_data['id']}.json")
                    if os.path.exists(meta_path):
                        with open(meta_path, 'r', encoding='utf-8') as mf:
                            meta = json.load(mf)
                        details += "\nGeneration Metadata:\n"
                        if meta.get('requested_resolution'):
                            details += f"Requested Resolution: {meta.get('requested_resolution')}\n"
                        if meta.get('warnings'):
                            details += "Warnings:\n"
                            for w in meta.get('warnings'):
                                details += f" - {w}\n"
                        if meta.get('saved_images_meta'):
                            details += "Saved Images:\n"
                            for im in meta.get('saved_images_meta'):
                                try:
                                    details += f" - {os.path.basename(im.get('path'))}: {im.get('width')}x{im.get('height')} ({im.get('bytes')} bytes)\n"
                                except Exception:
                                    pass
                except Exception as e:
                    print(f"Error loading generation metadata: {e}")
            
            details += f"\nPrompt Text:\n{prompt_data['prompt']}"
            
            QMessageBox.information(self, "Prompt Details", details)

    def copy_prompt_text(self, prompt_text):
        """Copy prompt text to clipboard"""
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(prompt_text)
            
            QToolTip.showText(
                QCursor.pos(),
                f"Copied to clipboard: {prompt_text[:50]}{'...' if len(prompt_text) > 50 else ''}",
                None,
                QToolTip.hideText,
                2000
            )
        except Exception as e:
            print(f"Failed to copy to clipboard: {e}")

    def on_table_context_menu(self, pos):
        """Handle right-click context menu on table"""
        item = self.table.itemAt(pos)
        if item is None:
            return
        
        row = item.row()
        if row < 0 or row >= len(self.prompt_data):
            return
            
        prompt_data = self.prompt_data[row]
        
        menu = QMenu(self)
        
        copy_action = QAction(qta.icon('fa6s.copy'), "Copy Prompt", self)
        copy_action.triggered.connect(lambda: self.copy_prompt_text(prompt_data['prompt']))
        menu.addAction(copy_action)
        
        details_action = QAction(qta.icon('fa6s.info'), "View Details", self)
        details_action.triggered.connect(lambda: self.on_prompt_double_click(self.table.indexFromItem(item)))
        menu.addAction(details_action)
        
        menu.exec(self.table.mapToGlobal(pos))

    def _status_color(self, status):
        """Get status color consistent with main_table.py"""
        if status == "processing":
            return QColor(243, 200, 24, int(0.3 * 255))
        elif status == "generated" or status == "success":
            return QColor(113, 204, 0, int(0.3 * 255))
        elif status == "failed":
            return QColor(255, 0, 0, int(0.15 * 255))
        elif status == "stopping":
            return QColor(255, 140, 0, int(0.18 * 255))
        elif status == "stopped":
            return QColor(200, 40, 40, int(0.18 * 255))
        elif status == "pending" or status is None:
            return QColor(120, 120, 120, int(0.18 * 255))
        return QColor(0, 0, 0, int(0.1 * 255))

    def update_table_row_status(self, prompt_id, status, images_generated=0, error_msg=""):
        """Update table row status with color and real-time data"""
        for row, data in enumerate(self.prompt_data):
            if data.get('id') == prompt_id:
                self.prompt_data[row]['status'] = status
                self.prompt_data[row]['images_generated'] = images_generated
                if error_msg:
                    self.prompt_data[row]['error_message'] = error_msg
                
                status_item = self.table.item(row, 2)
                
                if status_item:
                    status_item.setText(status.title() if status else 'Pending')
                    
                status_color = self._status_color(status)
                for col in range(self.table.columnCount()):
                    cell_item = self.table.item(row, col)
                    if cell_item:
                        cell_item.setBackground(QBrush(status_color))
                        cell_item.setData(Qt.UserRole + 1, status)
                break

    def open_config_dialog(self):
        """Open configuration dialog for Imagen models"""
        dialog = ImagenConfigDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.reload_models()
    
    def reload_models(self):
        """Reload models from config after changes"""
        try:
            self.config = load_imagen_config()
            current_model = self.model_combo.currentText()
            self.model_combo.clear()
            
            models = self.config.get('models', ['imagen-4.0-generate-001'])
            for model in models:
                self.model_combo.addItem(model)
            
            if current_model in models:
                self.model_combo.setCurrentText(current_model)
            elif models:
                self.model_combo.setCurrentIndex(0)
            
            print(f"[ImagenGeneratorDialog] Models reloaded: {len(models)} models")
        except Exception as e:
            print(f"[ImagenGeneratorDialog] Error reloading models: {e}")

    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(self, "Generation in Progress", 
                                       "Image generation is currently running. Do you want to stop it and close?",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.worker.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()