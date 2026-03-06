from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QGroupBox
from PySide6.QtCore import Qt
import qtawesome as qta
import json
import os
from config import BASE_PATH

class MetadataWritingChunkSizeDialog(QDialog):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Metadata Writing Chunk Size")
		self.setMinimumWidth(400)
		self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
		self.setModal(True)
		
		self.config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
		self.current_chunk_size = self._load_chunk_size()
		
		self._setup_ui()
	
	def _load_chunk_size(self):
		with open(self.config_path, encoding="utf-8") as f:
			config = json.load(f)
		return config['chunk_size']
	
	def _setup_ui(self):
		layout = QVBoxLayout()
		layout.setSpacing(15)
		
		info_group = QGroupBox("Information")
		info_layout = QVBoxLayout()
		
		info_text = QLabel(
			"Chunk size determines how many files are processed in each batch when "
			"writing metadata to images or videos.\n\n"
			"• Smaller chunks (10-20): More stable, less memory usage, slower overall\n"
			"• Medium chunks (30-50): Balanced performance and stability\n"
			"• Larger chunks (60-100): Faster processing, more memory usage\n\n"
			"Recommended: 20-50 for most systems"
		)
		info_text.setWordWrap(True)
		info_layout.addWidget(info_text)
		info_group.setLayout(info_layout)
		layout.addWidget(info_group)
		
		chunk_group = QGroupBox("Chunk Size Setting")
		chunk_layout = QHBoxLayout()
		
		chunk_layout.addWidget(QLabel("Files per chunk:"))
		
		self._pending_chunk_size = self.current_chunk_size
		self.chunk_spinbox = QSpinBox()
		self.chunk_spinbox.setMinimum(1)
		self.chunk_spinbox.setMaximum(200)
		self.chunk_spinbox.setValue(self.current_chunk_size)
		self.chunk_spinbox.setSuffix(" files")
		self.chunk_spinbox.valueChanged.connect(lambda v: setattr(self, '_pending_chunk_size', v))
		chunk_layout.addWidget(self.chunk_spinbox)
		
		chunk_layout.addStretch()
		chunk_group.setLayout(chunk_layout)
		layout.addWidget(chunk_group)
		
		button_layout = QHBoxLayout()
		button_layout.addStretch()
		
		cancel_btn = QPushButton("Cancel")
		cancel_btn.setIcon(qta.icon('fa6s.xmark'))
		cancel_btn.clicked.connect(self.reject)
		button_layout.addWidget(cancel_btn)
		
		save_btn = QPushButton("Save")
		save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
		save_btn.clicked.connect(self._save_chunk_size)
		button_layout.addWidget(save_btn)
		
		layout.addLayout(button_layout)
		self.setLayout(layout)
	
	def _save_chunk_size(self):
		new_chunk_size = self._pending_chunk_size
		print(f"[ChunkSize] Saving chunk_size={new_chunk_size} to {self.config_path}")
		
		with open(self.config_path, encoding="utf-8") as f:
			config = json.load(f)
		
		config['chunk_size'] = new_chunk_size
		
		with open(self.config_path, 'w', encoding="utf-8") as f:
			json.dump(config, f, indent=4, ensure_ascii=False)
		
		print(f"[ChunkSize] Saved successfully.")
		self.accept()
