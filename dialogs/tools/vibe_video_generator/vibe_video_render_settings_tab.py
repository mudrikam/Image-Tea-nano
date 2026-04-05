import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QGroupBox, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFormLayout, QScrollArea, QFrame,
    QTextEdit
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta


class RenderSettingsTabWidget(QWidget):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(12, 12, 12, 12)

        content_layout.addWidget(self._create_video_settings_group())
        content_layout.addWidget(self._create_audio_settings_group())
        content_layout.addWidget(self._create_quality_settings_group())
        content_layout.addWidget(self._create_performance_settings_group())
        content_layout.addWidget(self._create_browser_settings_group())
        content_layout.addWidget(self._create_advanced_settings_group())
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _create_group_box(self, title, icon_name):
        group = QGroupBox(title)
        layout = QFormLayout()
        layout.setSpacing(8)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        group.setLayout(layout)
        return group, layout

    def _create_video_settings_group(self):
        group, layout = self._create_group_box('Video Settings', 'fa6s.video')

        self.codec_combo = QComboBox()
        self.codec_combo.addItems(['h264', 'h265', 'av1', 'vp8', 'vp9', 'prores', 'h264-mkv'])
        self.codec_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Codec:', self.codec_combo)

        self.pixel_format_combo = QComboBox()
        self.pixel_format_combo.addItems(['yuv420p', 'yuv422p', 'yuv444p', 'yuva420p', 'yuva422p', 'yuva444p'])
        self.pixel_format_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Pixel Format:', self.pixel_format_combo)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 99999)
        self.width_spin.setSpecialValueText('Auto')
        self.width_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Width:', self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 99999)
        self.height_spin.setSpecialValueText('Auto')
        self.height_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Height:', self.height_spin)

        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0, 1000)
        self.fps_spin.setDecimals(2)
        self.fps_spin.setSpecialValueText('Auto')
        self.fps_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('FPS:', self.fps_spin)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 999999)
        self.duration_spin.setSpecialValueText('Auto')
        self.duration_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Duration (frames):', self.duration_spin)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 16.0)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setDecimals(2)
        self.scale_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Scale:', self.scale_spin)

        self.image_format_combo = QComboBox()
        self.image_format_combo.addItems(['jpeg', 'png'])
        self.image_format_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Image Format:', self.image_format_combo)

        self.sequence_checkbox = QCheckBox('Output as image sequence')
        self.sequence_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.sequence_checkbox)

        self.frames_edit = QLineEdit()
        self.frames_edit.setPlaceholderText('e.g., 0-100, 200-300')
        self.frames_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Frames:', self.frames_edit)

        self.every_nth_spin = QSpinBox()
        self.every_nth_spin.setRange(1, 1000)
        self.every_nth_spin.setValue(1)
        self.every_nth_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Every Nth Frame:', self.every_nth_spin)

        return group

    def _create_audio_settings_group(self):
        group, layout = self._create_group_box('Audio Settings', 'fa6s.volume-high')

        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(['aac', 'mp3', 'wav', 'opus'])
        self.audio_codec_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Audio Codec:', self.audio_codec_combo)

        self.audio_bitrate_edit = QLineEdit()
        self.audio_bitrate_edit.setPlaceholderText('e.g., 128k, 192k')
        self.audio_bitrate_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Audio Bitrate:', self.audio_bitrate_edit)

        self.muted_checkbox = QCheckBox('Mute audio')
        self.muted_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.muted_checkbox)

        self.enforce_audio_checkbox = QCheckBox('Enforce silent audio track')
        self.enforce_audio_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.enforce_audio_checkbox)

        self.separate_audio_edit = QLineEdit()
        self.separate_audio_edit.setPlaceholderText('Path for separate audio file')
        self.separate_audio_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Separate Audio To:', self.separate_audio_edit)

        self.for_seamless_aac_checkbox = QCheckBox('For seamless AAC concatenation')
        self.for_seamless_aac_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.for_seamless_aac_checkbox)

        return group

    def _create_quality_settings_group(self):
        group, layout = self._create_group_box('Quality Settings', 'fa6s.sliders')

        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setSpecialValueText('Auto')
        self.crf_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('CRF:', self.crf_spin)

        self.video_bitrate_edit = QLineEdit()
        self.video_bitrate_edit.setPlaceholderText('e.g., 5M, 10M')
        self.video_bitrate_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Video Bitrate:', self.video_bitrate_edit)

        self.buffer_size_edit = QLineEdit()
        self.buffer_size_edit.setPlaceholderText('e.g., 10M')
        self.buffer_size_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Buffer Size:', self.buffer_size_edit)

        self.max_rate_edit = QLineEdit()
        self.max_rate_edit.setPlaceholderText('e.g., 5M')
        self.max_rate_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Max Rate:', self.max_rate_edit)

        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(0, 100)
        self.jpeg_quality_spin.setValue(80)
        self.jpeg_quality_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('JPEG Quality:', self.jpeg_quality_spin)

        self.prores_profile_combo = QComboBox()
        self.prores_profile_combo.addItems(['auto', '4444', '4444-xq', 'hq', 'standard', 'light', 'proxy'])
        self.prores_profile_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('ProRes Profile:', self.prores_profile_combo)

        self.x264_preset_combo = QComboBox()
        self.x264_preset_combo.addItems(['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'])
        self.x264_preset_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('x264 Preset:', self.x264_preset_combo)

        self.gif_loops_spin = QSpinBox()
        self.gif_loops_spin.setRange(0, 9999)
        self.gif_loops_spin.setSpecialValueText('Infinite')
        self.gif_loops_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('GIF Loops:', self.gif_loops_spin)

        return group

    def _create_performance_settings_group(self):
        group, layout = self._create_group_box('Performance Settings', 'fa6s.gauge-high')

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 256)
        self.concurrency_spin.setSpecialValueText('Auto')
        self.concurrency_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Concurrency:', self.concurrency_spin)

        self.hardware_accel_combo = QComboBox()
        self.hardware_accel_combo.addItems(['none', 'cuda', 'videotoolbox', 'qsv', 'vaapi'])
        self.hardware_accel_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Hardware Acceleration:', self.hardware_accel_combo)

        self.disallow_parallel_checkbox = QCheckBox('Disallow parallel encoding')
        self.disallow_parallel_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.disallow_parallel_checkbox)

        return group

    def _create_browser_settings_group(self):
        group, layout = self._create_group_box('Browser Settings', 'fa6s.globe')

        self.browser_exec_edit = QLineEdit()
        self.browser_exec_edit.setPlaceholderText('Path to browser executable')
        self.browser_exec_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Browser Executable:', self.browser_exec_edit)

        self.browser_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.browser_browse_btn.setMaximumWidth(100)
        self.browser_browse_btn.clicked.connect(self._browse_browser)
        layout.addRow('', self.browser_browse_btn)

        self.chrome_mode_combo = QComboBox()
        self.chrome_mode_combo.addItems(['default', 'custom', 'launch'])
        self.chrome_mode_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Chrome Mode:', self.chrome_mode_combo)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1000, 999999999)
        self.timeout_spin.setValue(30000)
        self.timeout_spin.setSuffix(' ms')
        self.timeout_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Timeout:', self.timeout_spin)

        self.ignore_cert_checkbox = QCheckBox('Ignore certificate errors')
        self.ignore_cert_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.ignore_cert_checkbox)

        self.disable_web_security_checkbox = QCheckBox('Disable web security')
        self.disable_web_security_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.disable_web_security_checkbox)

        self.disable_headless_checkbox = QCheckBox('Disable headless mode')
        self.disable_headless_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.disable_headless_checkbox)

        self.dark_mode_checkbox = QCheckBox('Enable dark mode')
        self.dark_mode_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.dark_mode_checkbox)

        self.user_agent_edit = QLineEdit()
        self.user_agent_edit.setPlaceholderText('Custom user agent string')
        self.user_agent_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('User Agent:', self.user_agent_edit)

        self.gl_combo = QComboBox()
        self.gl_combo.addItems(['default', 'egl', 'angle', 'swiftshader', 'gles'])
        self.gl_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('GL Backend:', self.gl_combo)

        return group

    def _create_advanced_settings_group(self):
        group, layout = self._create_group_box('Advanced Settings', 'fa6s.gear')

        self.config_edit = QLineEdit()
        self.config_edit.setPlaceholderText('Path to config file')
        self.config_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Config File:', self.config_edit)

        self.config_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.config_browse_btn.setMaximumWidth(100)
        self.config_browse_btn.clicked.connect(self._browse_config)
        layout.addRow('', self.config_browse_btn)

        self.env_file_edit = QLineEdit()
        self.env_file_edit.setPlaceholderText('Path to .env file')
        self.env_file_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Env File:', self.env_file_edit)

        self.env_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.env_browse_btn.setMaximumWidth(100)
        self.env_browse_btn.clicked.connect(self._browse_env)
        layout.addRow('', self.env_browse_btn)

        self.props_edit = QLineEdit()
        self.props_edit.setPlaceholderText('Path to props JSON file')
        self.props_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Props File:', self.props_edit)

        self.props_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.props_browse_btn.setMaximumWidth(100)
        self.props_browse_btn.clicked.connect(self._browse_props)
        layout.addRow('', self.props_browse_btn)

        self.bundle_cache_checkbox = QCheckBox('Enable bundle cache')
        self.bundle_cache_checkbox.setChecked(True)
        self.bundle_cache_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.bundle_cache_checkbox)

        self.log_combo = QComboBox()
        self.log_combo.addItems(['error', 'warn', 'info', 'verbose'])
        self.log_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Log Level:', self.log_combo)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(0, 65535)
        self.port_spin.setSpecialValueText('Auto')
        self.port_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Port:', self.port_spin)

        self.public_dir_edit = QLineEdit()
        self.public_dir_edit.setPlaceholderText('Path to public directory')
        self.public_dir_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Public Directory:', self.public_dir_edit)

        self.public_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.public_browse_btn.setMaximumWidth(100)
        self.public_browse_btn.clicked.connect(self._browse_public_dir)
        layout.addRow('', self.public_browse_btn)

        self.media_cache_size_edit = QLineEdit()
        self.media_cache_size_edit.setPlaceholderText('Size in bytes')
        self.media_cache_size_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Media Cache Size:', self.media_cache_size_edit)

        self.offthreadvideo_cache_edit = QLineEdit()
        self.offthreadvideo_cache_edit.setPlaceholderText('Size in bytes')
        self.offthreadvideo_cache_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('OffthreadVideo Cache:', self.offthreadvideo_cache_edit)

        self.offthreadvideo_threads_spin = QSpinBox()
        self.offthreadvideo_threads_spin.setRange(1, 128)
        self.offthreadvideo_threads_spin.valueChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('OffthreadVideo Threads:', self.offthreadvideo_threads_spin)

        self.enable_multiprocess_checkbox = QCheckBox('Enable multiprocess on Linux')
        self.enable_multiprocess_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.enable_multiprocess_checkbox)

        self.repro_checkbox = QCheckBox('Generate repro')
        self.repro_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.repro_checkbox)

        self.binaries_dir_edit = QLineEdit()
        self.binaries_dir_edit.setPlaceholderText('Path to binaries directory')
        self.binaries_dir_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Binaries Directory:', self.binaries_dir_edit)

        self.binaries_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.binaries_browse_btn.setMaximumWidth(100)
        self.binaries_browse_btn.clicked.connect(self._browse_binaries_dir)
        layout.addRow('', self.binaries_browse_btn)

        self.experimental_rspack_checkbox = QCheckBox('Enable experimental Rspack')
        self.experimental_rspack_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.experimental_rspack_checkbox)

        self.metadata_edit = QTextEdit()
        self.metadata_edit.setPlaceholderText('Metadata JSON')
        self.metadata_edit.setMaximumHeight(80)
        self.metadata_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Metadata:', self.metadata_edit)

        self.color_space_combo = QComboBox()
        self.color_space_combo.addItems(['default', 'srgb', 'rec2020', 'display-p3'])
        self.color_space_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Color Space:', self.color_space_combo)

        self.image_sequence_pattern_edit = QLineEdit()
        self.image_sequence_pattern_edit.setPlaceholderText('e.g., frame-%04d.png')
        self.image_sequence_pattern_edit.textChanged.connect(lambda: self.settings_changed.emit())
        layout.addRow('Image Sequence Pattern:', self.image_sequence_pattern_edit)

        self.overwrite_checkbox = QCheckBox('Overwrite existing file')
        self.overwrite_checkbox.setChecked(True)
        self.overwrite_checkbox.toggled.connect(lambda: self.settings_changed.emit())
        layout.addRow('', self.overwrite_checkbox)

        return group

    def _browse_browser(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Browser Executable', '', 'Executable Files (*.exe);;All Files (*)')
        if file_path:
            self.browser_exec_edit.setText(file_path)

    def _browse_config(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Config File', '', 'Config Files (*.ts *.js *.json);;All Files (*)')
        if file_path:
            self.config_edit.setText(file_path)

    def _browse_env(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Env File', '', 'Env Files (.env*);;All Files (*)')
        if file_path:
            self.env_file_edit.setText(file_path)

    def _browse_props(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Props File', '', 'JSON Files (*.json);;All Files (*)')
        if file_path:
            self.props_edit.setText(file_path)

    def _browse_public_dir(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Public Directory')
        if folder:
            self.public_dir_edit.setText(folder)

    def _browse_binaries_dir(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Binaries Directory')
        if folder:
            self.binaries_dir_edit.setText(folder)

    def get_render_command_args(self):
        args = []

        if self.codec_combo.currentText() != 'h264':
            args.extend(['--codec', self.codec_combo.currentText()])

        if self.pixel_format_combo.currentText() != 'yuv420p':
            args.extend(['--pixel-format', self.pixel_format_combo.currentText()])

        if self.width_spin.value() > 0:
            args.extend(['--width', str(self.width_spin.value())])

        if self.height_spin.value() > 0:
            args.extend(['--height', str(self.height_spin.value())])

        if self.fps_spin.value() > 0:
            args.extend(['--fps', str(self.fps_spin.value())])

        if self.duration_spin.value() > 0:
            args.extend(['--duration', str(self.duration_spin.value())])

        if self.scale_spin.value() != 1.0:
            args.extend(['--scale', str(self.scale_spin.value())])

        if self.image_format_combo.currentText() != 'jpeg':
            args.extend(['--image-format', self.image_format_combo.currentText()])

        if self.sequence_checkbox.isChecked():
            args.append('--sequence')

        if self.frames_edit.text():
            args.extend(['--frames', self.frames_edit.text()])

        if self.every_nth_spin.value() > 1:
            args.extend(['--every-nth-frame', str(self.every_nth_spin.value())])

        if self.audio_codec_combo.currentText() != 'aac':
            args.extend(['--audio-codec', self.audio_codec_combo.currentText()])

        if self.audio_bitrate_edit.text():
            args.extend(['--audio-bitrate', self.audio_bitrate_edit.text()])

        if self.muted_checkbox.isChecked():
            args.append('--muted')

        if self.enforce_audio_checkbox.isChecked():
            args.append('--enforce-audio-track')

        if self.separate_audio_edit.text():
            args.extend(['--separate-audio-to', self.separate_audio_edit.text()])

        if self.for_seamless_aac_checkbox.isChecked():
            args.append('--for-seamless-aac-concatenation')

        if self.crf_spin.value() > 0:
            args.extend(['--crf', str(self.crf_spin.value())])

        if self.video_bitrate_edit.text():
            args.extend(['--video-bitrate', self.video_bitrate_edit.text()])

        if self.buffer_size_edit.text():
            args.extend(['--buffer-size', self.buffer_size_edit.text()])

        if self.max_rate_edit.text():
            args.extend(['--max-rate', self.max_rate_edit.text()])

        if self.jpeg_quality_spin.value() != 80:
            args.extend(['--jpeg-quality', str(self.jpeg_quality_spin.value())])

        if self.prores_profile_combo.currentText() != 'auto':
            args.extend(['--prores-profile', self.prores_profile_combo.currentText()])

        if self.x264_preset_combo.currentText() != 'medium':
            args.extend(['--x264-preset', self.x264_preset_combo.currentText()])

        if self.gif_loops_spin.value() > 0:
            args.extend(['--number-of-gif-loops', str(self.gif_loops_spin.value())])

        if self.concurrency_spin.value() > 0:
            args.extend(['--concurrency', str(self.concurrency_spin.value())])

        if self.hardware_accel_combo.currentText() != 'none':
            args.extend(['--hardware-acceleration', self.hardware_accel_combo.currentText()])

        if self.disallow_parallel_checkbox.isChecked():
            args.append('--disallow-parallel-encoding')

        if self.browser_exec_edit.text():
            args.extend(['--browser-executable', self.browser_exec_edit.text()])

        if self.chrome_mode_combo.currentText() != 'default':
            args.extend(['--chrome-mode', self.chrome_mode_combo.currentText()])

        if self.timeout_spin.value() != 30000:
            args.extend(['--timeout', str(self.timeout_spin.value())])

        if self.ignore_cert_checkbox.isChecked():
            args.append('--ignore-certificate-errors')

        if self.disable_web_security_checkbox.isChecked():
            args.append('--disable-web-security')

        if self.disable_headless_checkbox.isChecked():
            args.append('--disable-headless')

        if self.dark_mode_checkbox.isChecked():
            args.append('--dark-mode')

        if self.user_agent_edit.text():
            args.extend(['--user-agent', self.user_agent_edit.text()])

        if self.gl_combo.currentText() != 'default':
            args.extend(['--gl', self.gl_combo.currentText()])

        if self.config_edit.text():
            args.extend(['--config', self.config_edit.text()])

        if self.env_file_edit.text():
            args.extend(['--env-file', self.env_file_edit.text()])

        if self.props_edit.text():
            args.extend(['--props', self.props_edit.text()])

        if not self.bundle_cache_checkbox.isChecked():
            args.append('--bundle-cache=false')

        if self.log_combo.currentText() != 'info':
            args.extend(['--log', self.log_combo.currentText()])

        if self.port_spin.value() > 0:
            args.extend(['--port', str(self.port_spin.value())])

        if self.public_dir_edit.text():
            args.extend(['--public-dir', self.public_dir_edit.text()])

        if self.media_cache_size_edit.text():
            args.extend(['--media-cache-size-in-bytes', self.media_cache_size_edit.text()])

        if self.offthreadvideo_cache_edit.text():
            args.extend(['--offthreadvideo-cache-size-in-bytes', self.offthreadvideo_cache_edit.text()])

        if self.offthreadvideo_threads_spin.value() != 1:
            args.extend(['--offthreadvideo-video-threads', str(self.offthreadvideo_threads_spin.value())])

        if self.enable_multiprocess_checkbox.isChecked():
            args.append('--enable-multiprocess-on-linux')

        if self.repro_checkbox.isChecked():
            args.append('--repro')

        if self.binaries_dir_edit.text():
            args.extend(['--binaries-directory', self.binaries_dir_edit.text()])

        if self.experimental_rspack_checkbox.isChecked():
            args.append('--experimental-rspack')

        if self.metadata_edit.toPlainText():
            args.extend(['--metadata', self.metadata_edit.toPlainText()])

        if self.color_space_combo.currentText() != 'default':
            args.extend(['--color-space', self.color_space_combo.currentText()])

        if self.image_sequence_pattern_edit.text():
            args.extend(['--image-sequence-pattern', self.image_sequence_pattern_edit.text()])

        if not self.overwrite_checkbox.isChecked():
            args.append('--overwrite=false')

        return args
