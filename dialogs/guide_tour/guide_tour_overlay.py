from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QSizePolicy
from PySide6.QtCore import Qt, QRect, QPoint, QTimer, QSize
import qtawesome as qta
import sys
from pathlib import Path
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QGuiApplication


class GuidePanel(QWidget):
    """A small QWidget that draws a rounded background so it remains visible
    when used as a top-level tool window with translucent background."""
    def __init__(self, *args, bg_color="#3c8b0e", radius=8, **kwargs):
        super().__init__(*args, **kwargs)
        self._bg = QColor(bg_color)
        self._radius = radius
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._bg)
        r = self.rect()
        painter.drawRoundedRect(r, self._radius, self._radius)
        super().paintEvent(ev)

class GuideOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.target_widget = None
        self.title = ""
        self.description = ""
        self._guide_font_family = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"


        self.panel = GuidePanel(parent or self)
        self.panel.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.panel.setStyleSheet("""
            QWidget {
                background-color: #4e9e20;
                border: none;
                border-radius: 6px;
                color: white;
                padding: 6px;
            }
            QLabel {
                background-color: transparent;
                color: white;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: white;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
            QComboBox {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #4e9e20;
                color: white;
                border: none;
                outline: none;
                selection-background-color: rgba(255, 255, 255, 0.12);
            }
            QComboBox QAbstractItemView::item {
                border: none;
                padding: 6px 10px;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: rgba(255, 255, 255, 0.12);
                color: white;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(255, 255, 255, 0.06);
            }
        """)
        self.panel.setVisible(False)
        self.panel.setMinimumWidth(420)
        self.panel.setMaximumWidth(760)


        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        self.title_label = QLabel()
        self.title_label.setFont(QFont(self._guide_font_family, 12, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setFont(QFont(self._guide_font_family, 10))
        layout.addWidget(self.desc_label)

        ctrl_row = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.setIcon(qta.icon('fa6s.chevron-left', color='white'))
        self.prev_btn.setIconSize(QSize(14, 14))
        self.prev_btn.clicked.connect(lambda: self._on_prev())
        ctrl_row.addWidget(self.prev_btn)

        self.index_label = QLabel("")
        self.index_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_row.addWidget(self.index_label)

        self.next_btn = QPushButton("Next")
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setIcon(qta.icon('fa6s.chevron-right', color='white'))
        self.next_btn.setIconSize(QSize(14, 14))
        self.next_btn.clicked.connect(lambda: self._on_next())
        ctrl_row.addWidget(self.next_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setIcon(qta.icon('fa6s.xmark', color='white'))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.clicked.connect(self._on_close)
        self.close_btn.setVisible(False)
        ctrl_row.addWidget(self.close_btn)

        ctrl_row.addStretch()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "EN")
        self.lang_combo.addItem("Indonesia", "ID")
        self.lang_combo.setCurrentIndex(0)
        self.lang_combo.setMinimumWidth(140)
        self.lang_combo.currentIndexChanged.connect(lambda idx: self._on_lang_changed(self.lang_combo.itemData(idx) or 'EN'))
        ctrl_row.addWidget(self.lang_combo)

        layout.addLayout(ctrl_row)

        if parent:
            parent.installEventFilter(self)

        self.tour_content = {
            'EN': [
                {
                    'title': 'Step 1: Add files to Image Tea',
                    'description': 'This is the main table for viewing and managing your files. To start generating metadata, drag & drop images, vector files, or videos into this area. Supported formats include common image formats (.jpg, .jpeg, .png, .psd, .bmp, .gif, .tiff, .webp), vector formats (.svg, .eps, .pdf), and video formats (.mp4, .mov, .avi, .webm, .flv, .mpeg). You can also select files to edit metadata, copy values, or perform batch operations.',
                    'target': 'table'
                },
                {
                    'title': 'Step 2: Add An API Key',
                    'description': "Image Tea requires an API key to generate metadata. Click the 'Get FREE API Key' button to obtain keys from providers, or use 'Add API Key' to add your own key. You can also purchase API keys from the community via the 'Add API Key' dialog. Supported services include Gemini, OpenAI, and OpenRouter. Image Tea does not provide API keys. You must use your own.",
                    'targets': ['api_key_section.get_api_btn', 'api_key_section.add_api_btn']
                },
                {
                    'title': 'Step 3: Select Service and Model',
                    'description': 'After adding an API key, choose the service first and then the model using the dropdowns in the API key section. API keys you added will appear automatically in the dropdowns. Select the API key to enable the corresponding service and model.',
                    'targets': ['api_key_section.model_combo', 'api_key_section.api_key_combo']
                },
                {
                    'title': 'Step 4: Adjust Prompt Behavior',
                    'description': 'Configure how metadata is generated using the Prompt section. Use "Min Title" and "Max Title" to set target title length, "Max Desc" to set description length, and "Tag Count" to control number of keywords. Use "Batch Size" to control files processed per request, "Quality" to set image compression before upload (does not apply to video), "Delay" to add a pause between batches, and "Proxy" to choose video proxy presets. Changes are saved automatically.',
                    'target': 'prompt_section'
                },
                {
                    'title': 'Step 5: Choose Generation Mode',
                    'description': 'Pick a generation mode from this dropdown to control which files will be processed. "Generate All Files" processes every file in the table. "Generate Selected Only" processes only selected files (those you checked). "Generate Failed Only" retries files that previously failed. "Generate Drafts Only" processes files marked as drafts. "Resume Generation From Stopped" resumes generation starting from the first stopped file. "Generate With Rolling API Keys" uses available API keys and automatically switches when one fails.',
                    'target': 'gen_mode_combo'
                },
                {
                    'title': 'Step 6: Generate Metadata',
                    'description': 'Click the "Generate Metadata" button to start processing. Image Tea will process files per the selected generation mode and Prompt settings, upload files (compressed or proxied as configured), call the chosen API using the selected API key, and save generated metadata back into the table. Large batches may trigger a warning. Individual file errors are recorded and can be retried with "Generate Failed Only".',
                    'target': 'gen_btn'
                },
                {
                    'title': 'Step 7: View Generation Stats',
                    'description': 'The Stats panel shows real-time generation metrics: Total, Selected, Failed, Success, Draft, Token Input/Output/Total, Elapsed Time, Remaining Time, ETA, Progress, and Speed. Start a generation to see these values update live. Use the Reset control to clear token statistics if needed.',
                    'target': 'stats_section'
                },
                {
                    'title': 'Step 8: View Saved Metadata in Properties',
                    'description': 'After generation finishes, click a file in the table to view its saved metadata in the Properties panel. Title, Description, and Tags will show the generated values and the preview can be used to inspect the image or open the original file.',
                    'target': 'properties_widget'
                },
                {
                    'title': 'Step 9: Toolbar Overview',
                    'description': 'The toolbar provides quick actions: Import, Clear, Delete, Edit, Write (images/videos), Export, Prompt editing, Custom prompt, API Key management, Relaunch, Update, Donate, and Help. Use these buttons to manage files, edit or write metadata, and access utilities.',
                    'target': 'main_toolbar'
                },
                {
                    'title': 'Step 10: File Actions (Import, Clear, Delete)',
                    'description': 'Use Import to add files to the table. Clear removes all entries from the table without deleting files on disk. Delete removes only selected rows from the table. Use these to prepare the files you want to process in Image Tea.',
                    'targets': ['find:wrapper_toolbar_import', 'find:wrapper_toolbar_clear', 'find:wrapper_toolbar_delete']
                }, 
                {
                    'title': 'Step 11: Maintenance Actions (Clear Metadata, Rename, Edit)',
                    'description': 'Clear (metadata) removes all metadata records in the database for files and cannot be undone. Rename opens the batch rename dialog to rename files on disk. Edit opens the metadata editor so you can adjust title, description, keywords, and other fields manually.',
                    'targets': ['find:wrapper_toolbar_clear_metadata', 'find:wrapper_toolbar_rename', 'find:wrapper_toolbar_edit']
                },
                {
                    'title': 'Step 12: Write and Export',
                    'description': 'Use Write (images) or Write (videos) to write metadata directly into files on disk. This action is permanent. Use Export to save metadata from the table into a CSV file for backup or further processing.',
                    'targets': ['find:wrapper_toolbar_write_images', 'find:wrapper_toolbar_write_videos', 'find:wrapper_toolbar_export']
                }, 
                {
                    'title': 'Step 13: Prompt and API Controls',
                    'description': 'Prompt opens the system prompt editor that controls how AI generates titles, descriptions, and keywords. Custom lets you apply a temporary prompt override for one-off generations. API Key opens the manager where you add or select API keys used to call AI services.',
                    'targets': ['find:wrapper_toolbar_prompt', 'find:wrapper_toolbar_custom', 'find:wrapper_toolbar_api_key']
                }, 
                {
                    'title': 'Step 14: App Tools (Relaunch, Update)',
                    'description': 'Relaunch restarts Image Tea. Update checks for and applies new versions. Save your work before updating as the app may restart.',
                    'targets': ['find:wrapper_toolbar_relaunch', 'find:wrapper_toolbar_update']
                },
                {
                    'title': 'Step 15: Community Support (WhatsApp)',
                    'description': 'If you encounter issues or need assistance, click the WhatsApp button to open the support channel and request help.',
                    'targets': ['find:wrapper_toolbar_whatsapp']
                },
                {
                    'title': 'Step 16: Community Channels (TikTok, Telegram, Repo)',
                    'description': 'Click the TikTok or Telegram buttons to find short tutorials and community discussions. Click Repo to open the project repository for source code and issue tracking.',
                    'targets': ['find:wrapper_toolbar_website', 'find:wrapper_toolbar_telegram', 'find:wrapper_toolbar_repo']
                },
                {
                    'title': 'Step 17: Donate',
                    'description': "If you've found Image Tea helpful, consider donating to support ongoing development. This project is developed using the developer's personal funds; donations help cover development time, hosting, and improvements.",
                    'targets': ['find:wrapper_toolbar_donate']
                },
                {
                    'title': 'Step 18: Help & Documentation',
                    'description': 'All essential information about Image Tea is available in the documentation. Click Help to open guides, troubleshooting information, and usage notes.',
                    'targets': ['find:wrapper_toolbar_help']
                },
                {
                    'title': 'Thank You',
                    'description': 'Thank you for using Image Tea. You can reopen this guide anytime from the Help menu by selecting "Show Guide". Please enjoy your work.',
                    'target': 'table'
                },
            ],
            'ID': [
                {
                    'title': 'Langkah 1: Menambahkan file ke Image Tea',
                    'description': 'Ini adalah tabel utama untuk melihat dan mengelola file. Untuk memulai proses pembuatan metadata, drag & drop gambar, file vektor, atau video ke area ini. Format yang didukung termasuk gambar (.jpg, .jpeg, .png, .psd, .bmp, .gif, .tiff, .webp), vektor (.svg, .eps, .pdf), dan video (.mp4, .mov, .avi, .webm, .flv, .mpeg). Kamu juga bisa memilih file untuk mengedit metadata, menyalin nilai, atau melakukan operasi batch.',
                    'target': 'table'
                },
                {
                    'title': 'Langkah 2: Menambahkan API Key',
                    'description': "Image Tea membutuhkan API key untuk menghasilkan metadata. Klik tombol 'Get FREE API Key' untuk mendapatkan key dari penyedia, atau tombol 'Add API Key' untuk menambahkan key sendiri. Kamu juga bisa membeli API key dari komunitas melalui dialog 'Add API Key'. Layanan yang didukung termasuk Gemini, OpenAI, dan OpenRouter. Image Tea tidak menyediakan API key. Gunakan API key milikmu sendiri.",
                    'targets': ['api_key_section.get_api_btn', 'api_key_section.add_api_btn']
                },
                {
                    'title': 'Langkah 3: Memilih Layanan dan Model',
                    'description': 'Setelah menambahkan API key, pilih layanan terlebih dahulu lalu pilih model menggunakan dropdown di bagian API key. API key yang sudah ditambahkan akan otomatis muncul di dropdown. Pilih API key yang sesuai untuk mengaktifkan layanan dan model.',
                    'targets': ['api_key_section.model_combo', 'api_key_section.api_key_combo']
                },
                {
                    'title': 'Langkah 4: Sesuaikan Perilaku Prompt',
                    'description': 'Sesuaikan cara pembuatan metadata melalui bagian Prompt. Gunakan "Min Title" dan "Max Title" untuk panjang judul, "Max Desc" untuk panjang deskripsi, dan "Tag Count" untuk jumlah kata kunci. Gunakan "Batch Size" untuk jumlah file per permintaan, "Quality" untuk kompresi gambar sebelum upload (tidak berlaku untuk video), "Delay" untuk jeda antar batch, dan "Proxy" untuk memilih preset proxy video. Perubahan disimpan otomatis.',
                    'target': 'prompt_section'
                },
                {
                    'title': 'Langkah 5: Pilih Mode Generasi',
                    'description': 'Pilih mode generasi dari dropdown ini untuk menentukan file mana yang akan diproses. "Generate All Files" memproses semua file di tabel. "Generate Selected Only" hanya memproses file yang dipilih (yang kamu centang). "Generate Failed Only" mencoba kembali file yang sebelumnya gagal. "Generate Drafts Only" memproses file yang berstatus draft. "Resume Generation From Stopped" melanjutkan proses dari file yang berhenti pertama. "Generate With Rolling API Keys" menggunakan semua API key yang tersedia dan otomatis berpindah ketika salah satu gagal.',
                    'target': 'gen_mode_combo'
                },
                {
                    'title': 'Langkah 6: Mulai Generate Metadata',
                    'description': 'Klik tombol "Generate Metadata" untuk memulai proses. Image Tea akan memproses file sesuai mode dan pengaturan Prompt, mengupload file (terkompresi atau melalui proxy sesuai konfigurasi), memanggil layanan API yang dipilih menggunakan API key yang terpilih, dan menyimpan metadata yang dihasilkan ke tabel. Untuk batch besar akan muncul peringatan. Error pada file tertentu dicatat dan dapat dicoba lagi dengan mode "Generate Failed Only".',
                    'target': 'gen_btn'
                },
                {
                    'title': 'Langkah 7: Lihat Statistik Generasi',
                    'description': 'Panel Statistik menampilkan metrik waktu-nyata: Total, Terpilih, Gagal, Sukses, Draft, Token Input/Output/Total, Waktu Berjalan, Sisa Waktu, ETA, Progres, dan Kecepatan. Mulai proses generate untuk melihat pembaruan secara langsung. Gunakan tombol Reset untuk mengosongkan statistik token jika diperlukan.',
                    'target': 'stats_section'
                },
                {
                    'title': 'Langkah 8: Lihat Metadata Tersimpan di Properties',
                    'description': 'Setelah proses selesai, klik file di tabel untuk melihat metadata yang tersimpan di panel Properties. Judul, Deskripsi, dan Tags menampilkan nilai yang dihasilkan. Gunakan preview untuk memeriksa gambar atau buka file asli jika diperlukan.',
                    'target': 'properties_widget'
                },
                {
                    'title': 'Langkah 9: Ringkasan Toolbar',
                    'description': 'Toolbar menyediakan aksi cepat: Import, Clear, Delete, Edit, Write (gambar/video), Export, Edit Prompt, Custom Prompt, Manajemen API Key, Relaunch, Update, Donate, dan Help. Gunakan tombol-tombol ini untuk mengelola file, mengedit atau menulis metadata, dan mengakses utilitas lainnya.',
                    'target': 'main_toolbar'
                },
                {
                    'title': 'Langkah 10: Tindakan File (Import, Clear, Delete)',
                    'description': 'Gunakan Import untuk menambahkan file ke tabel. Clear menghapus semua entri dari tabel tanpa menghapus file di disk. Delete menghapus hanya baris yang dipilih. Gunakan ini untuk menyiapkan file yang ingin diproses di Image Tea.',
                    'targets': ['find:wrapper_toolbar_import', 'find:wrapper_toolbar_clear', 'find:wrapper_toolbar_delete']
                },
                {
                    'title': 'Langkah 11: Tindakan Pemeliharaan (Clear Metadata, Rename, Edit)',
                    'description': 'Clear (metadata) menghapus semua metadata di database untuk file dan tidak dapat dibatalkan. Rename membuka dialog batch rename untuk mengganti nama file di disk. Edit membuka dialog edit metadata untuk mengubah judul, deskripsi, kata kunci, dan field lain secara manual.',
                    'targets': ['find:wrapper_toolbar_clear_metadata', 'find:wrapper_toolbar_rename', 'find:wrapper_toolbar_edit']
                },
                {
                    'title': 'Langkah 12: Menulis dan Ekspor',
                    'description': 'Gunakan Write (gambar) atau Write (video) untuk menulis metadata langsung ke file di disk. Tindakan ini permanen. Gunakan Export untuk menyimpan metadata dari tabel ke file CSV untuk backup atau pemrosesan lanjutan.',
                    'targets': ['find:wrapper_toolbar_write_images', 'find:wrapper_toolbar_write_videos', 'find:wrapper_toolbar_export']
                },
                {
                    'title': 'Langkah 13: Kontrol Prompt dan API',
                    'description': 'Prompt membuka editor prompt sistem yang mengatur bagaimana AI menghasilkan judul, deskripsi, dan kata kunci. Custom memungkinkan override prompt sementara untuk satu kali generate. API Key membuka manajer untuk menambah atau memilih API key yang dipakai layanan AI.',
                    'targets': ['find:wrapper_toolbar_prompt', 'find:wrapper_toolbar_custom', 'find:wrapper_toolbar_api_key']
                },

                {
                    'title': 'Langkah 14: Alat Aplikasi (Relaunch, Update)',
                    'description': 'Relaunch memulai ulang Image Tea. Update memeriksa dan memasang versi baru. Simpan pekerjaanmu sebelum memperbarui karena aplikasi mungkin akan dimulai ulang.',
                    'targets': ['find:wrapper_toolbar_relaunch', 'find:wrapper_toolbar_update']
                },
                {
                    'title': 'Langkah 15: Dukungan Komunitas (WhatsApp)',
                    'description': 'Jika mengalami masalah atau kendala, klik tombol WhatsApp untuk meminta bantuan dan pemecahan masalah.',
                    'targets': ['find:wrapper_toolbar_whatsapp']
                },
                {
                    'title': 'Langkah 16: Kanal Komunitas (TikTok, Telegram, Repo)',
                    'description': 'Klik tombol TikTok atau Telegram untuk melihat tutorial singkat dan diskusi komunitas. Klik Repo untuk membuka repositori proyek dan pelacakan isu.',
                    'targets': ['find:wrapper_toolbar_website', 'find:wrapper_toolbar_telegram', 'find:wrapper_toolbar_repo']
                },
                {
                    'title': 'Langkah 17: Donasi',
                    'description': 'Jika kamu merasa Image Tea bermanfaat, pertimbangkan untuk berdonasi untuk mendukung pengembangan berkelanjutan. Aplikasi ini dikembangkan menggunakan dana pribadi developer; donasi membantu menutupi biaya hosting, perbaikan, dan waktu pengembangan.',
                    'targets': ['find:wrapper_toolbar_donate']
                },
                {
                    'title': 'Langkah 18: Bantuan & Dokumentasi',
                    'description': 'Semua informasi penting tentang Image Tea tersedia di dokumentasi. Klik Help untuk membuka panduan, informasi pemecahan masalah, dan catatan penggunaan.',
                    'targets': ['find:wrapper_toolbar_help']
                },
                {
                    'title': 'Terima Kasih',
                    'description': 'Terima kasih telah menggunakan Image Tea. Panduan ini dapat dibuka kembali melalui menu Help dengan memilih "Show Guide". Selamat bekerja kembali.',
                    'target': 'table'
                }
            ]
        }
        self.current_lang = 'EN'
        self.current_index = 0

        self.panel.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self._target_widgets = []
        self._target_global_rect = None
        self._installed_target_filters = []

        try:
            self._seen_file = Path(__file__).resolve().parents[2] / 'temp' / '.is_guide_shown'
        except Exception:
            self._seen_file = None

        self._tracking_timer = QTimer(self)
        self._tracking_timer.setInterval(200)
        self._tracking_timer.timeout.connect(self._on_tracking_tick)

    def set_target(self, widget: QWidget, title: str, description: str):
        self.target_widget = widget
        if title or description:
            self.tour_content = {self.current_lang: [{'title': title, 'description': description}]}
            self.current_index = 0
        self._update_panel_content()

        self.panel.adjustSize()
        self.update_geometry()
        self.show()
        has_content = len(self.tour_content.get(self.current_lang, [])) > 0
        self.panel.setVisible(has_content)
        try:
            if not self._tracking_timer.isActive():
                self._tracking_timer.start()
        except Exception:
            pass

    def clear_target(self):
        self.target_widget = None
        self._target_widgets = []
        self._target_global_rect = None
        self.panel.setVisible(False)
        self.hide()
        try:
            if self._tracking_timer.isActive():
                self._tracking_timer.stop()
        except Exception:
            pass
        try:
            for w in list(self._installed_target_filters):
                try:
                    w.removeEventFilter(self)
                except Exception:
                    pass
            self._installed_target_filters = []
        except Exception:
            pass

    def set_tour_content(self, content: dict):
        """Set tour content with structure {'EN':[{'title':..,'description':..}], 'ID': [...]}"""
        self.tour_content = content
        self.current_index = 0
        self._update_panel_content()

    def add_step(self, lang: str, title: str, description: str):
        self.tour_content.setdefault(lang, []).append({'title': title, 'description': description})

    def _update_panel_content(self):
        steps = self.tour_content.get(self.current_lang, [])
        if not steps:
            self.title_label.setText("")
            self.desc_label.setText("")
            self.index_label.setText("")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return
        idx = max(0, min(self.current_index, len(steps) - 1))
        step = steps[idx]
        self.title_label.setText(step.get('title', ''))
        self.desc_label.setText(step.get('description', ''))
        self.index_label.setText(f"{idx + 1} / {len(steps)}")


        self._target_global_rect = None
        self._target_widgets = []
        target_spec = step.get('target') or step.get('targets')
        if target_spec and self.parent():
            widgets, global_rect = self._resolve_targets(target_spec)

            try:
                for w in list(self._installed_target_filters):
                    try:
                        w.removeEventFilter(self)
                    except Exception:
                        pass
                self._installed_target_filters = []
            except Exception:
                self._installed_target_filters = []

            if widgets:
                self._target_widgets = widgets
                self.target_widget = widgets[0]
                self._target_global_rect = None

                for w in self._target_widgets:
                    try:
                        if isinstance(w, QWidget):
                            w.installEventFilter(self)
                            self._installed_target_filters.append(w)
                    except Exception:
                        pass

            elif global_rect is not None:
                self._target_global_rect = global_rect
                self._target_widgets = []
                self.target_widget = None
            else:
                self.target_widget = None
                self._target_widgets = []
                self._target_global_rect = None

        if self.current_lang == 'ID':
            self.prev_btn.setText('Kembali')
            self.next_btn.setText('Berikutnya')
            self.close_btn.setText('Tutup')
        else:
            self.prev_btn.setText('Previous')
            self.next_btn.setText('Next')
            self.close_btn.setText('Close')

        self.prev_btn.setVisible(idx > 0)
        self.prev_btn.setEnabled(idx > 0)
        self.next_btn.setVisible(idx < len(steps) - 1)
        self.next_btn.setEnabled(idx < len(steps) - 1)

        if idx >= len(steps) - 1:
            self.close_btn.setVisible(True)
        else:
            self.close_btn.setVisible(False)

        self.panel.adjustSize()
        self.update_geometry()

    def _resolve_targets(self, target_spec):
        """Resolve a target spec (string or list of strings) to either a single widget or a combined global QRect.
        Supported forms:
          - 'attr_name' (attribute on parent)
          - 'attr.child' (nested attributes)
          - 'find:objectName' (findChild by objectName)
          - list of any of the above to combine multiple widgets into one rect
        Returns (widget, global_rect) where one of them is set.
        """
        if not target_spec or not self.parent():
            return ([], None)
        paths = target_spec if isinstance(target_spec, (list, tuple)) else [target_spec]
        rects = []
        widgets = []
        for path in paths:
            if not isinstance(path, str):
                continue
            widget = None
            if path.startswith('find:'):
                name = path.split(':', 1)[1]
                try:
                    widget = self.parent().findChild(QWidget, name)
                except Exception:
                    widget = None
            else:
                obj = self.parent()
                parts = path.split('.')
                for p in parts:
                    obj = getattr(obj, p, None)
                    if obj is None:
                        break
                if obj is not None:
                    widget = obj
                else:
                    try:
                        widget = self.parent().findChild(QWidget, path)
                    except Exception:
                        widget = None
            if widget is not None:
                widgets.append(widget)
                gpos = widget.mapToGlobal(QPoint(0, 0))
                rects.append(QRect(gpos, widget.rect().size()))
        if not widgets:
            return ([], None)
        if len(widgets) == 1:
            return (widgets, rects[0])
        u = rects[0]
        for r in rects[1:]:
            u = u.united(r)
        return (widgets, u)

    def _on_tracking_tick(self):
        if not self.isVisible():
            try:
                if self._tracking_timer.isActive():
                    self._tracking_timer.stop()
            except Exception:
                pass
            return
        if getattr(self, '_target_global_rect', None) is not None or getattr(self, '_target_widgets', None) or self.target_widget is not None:
            self.update_geometry()


    def update_geometry(self):
        if self.parent():
            parent_rect = self.parent().rect()
            parent_global_pos = self.parent().mapToGlobal(QPoint(0, 0))
            self.setGeometry(QRect(parent_global_pos, parent_rect.size()))
        else:
            return

        target_global_rect = None
        if getattr(self, '_target_global_rect', None) is not None:
            target_global_rect = self._target_global_rect
        elif getattr(self, '_target_widgets', None):
            rects = []
            for w in self._target_widgets:
                try:
                    gpos = w.mapToGlobal(QPoint(0, 0))
                    rects.append(QRect(gpos, w.rect().size()))
                except Exception:
                    pass
            if rects:
                u = rects[0]
                for r in rects[1:]:
                    u = u.united(r)
                target_global_rect = u
        elif self.target_widget is not None:
            try:
                target_rect = self.target_widget.rect()
                global_pos = self.target_widget.mapToGlobal(QPoint(0, 0))
                target_global_rect = QRect(global_pos, target_rect.size())
            except Exception:
                target_global_rect = None

        if target_global_rect is not None:
            self._position_panel(target_global_rect)
        else:
            panel_size = self.panel.sizeHint()
            parent_global_pos = self.parent().mapToGlobal(QPoint(0, 0))
            parent_size = self.parent().rect().size()
            center_pos = QPoint(parent_global_pos.x() + parent_size.width() // 2 - panel_size.width() // 2,
                                 parent_global_pos.y() + parent_size.height() // 2 - panel_size.height() // 2)
            self.panel.move(center_pos)

        self.update()

    def _position_panel(self, target_rect: QRect):
        panel_size = self.panel.sizeHint()

        positions = [
            ('above', QPoint(target_rect.center().x() - panel_size.width() // 2, target_rect.top() - panel_size.height() - 10)),
            ('below', QPoint(target_rect.center().x() - panel_size.width() // 2, target_rect.bottom() + 10)),
            ('right', QPoint(target_rect.right() + 10, target_rect.center().y() - panel_size.height() // 2)),
            ('left', QPoint(target_rect.left() - panel_size.width() - 10, target_rect.center().y() - panel_size.height() // 2)),
        ]

        screen = QGuiApplication.screenAt(target_rect.center()) or QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry()

        for _, pos in positions:
            panel_rect_global = QRect(pos, panel_size)
            if screen_rect.contains(panel_rect_global) and not panel_rect_global.intersects(target_rect):
                self.panel.move(pos)
                return

        best_score = None
        best_pos = None
        target_center = QPoint(target_rect.center())
        for _, pos in positions:
            cand_rect = QRect(pos, panel_size)
            x = cand_rect.x()
            y = cand_rect.y()
            x = max(screen_rect.x(), min(x, screen_rect.right() - panel_size.width() + 1))
            y = max(screen_rect.y(), min(y, screen_rect.bottom() - panel_size.height() + 1))
            clamped = QRect(QPoint(x, y), panel_size)

            dx = clamped.center().x() - target_center.x()
            dy = clamped.center().y() - target_center.y()
            dist2 = dx * dx + dy * dy

            if clamped.intersects(target_rect):
                inter = clamped.intersected(target_rect)
                penalty = inter.width() * inter.height()
            else:
                penalty = 0

            score = dist2 + penalty * 1000
            if best_score is None or score < best_score:
                best_score = score
                best_pos = clamped.topLeft()

        if best_pos is not None:
            self.panel.move(best_pos)
            return

        # As a last resort, center on screen (should rarely happen now)
        center_pos = QPoint(screen_rect.x() + screen_rect.width() // 2 - panel_size.width() // 2,
                             screen_rect.y() + screen_rect.height() // 2 - panel_size.height() // 2)
        self.panel.move(center_pos)

    def paintEvent(self, event):
        target_exists = bool(getattr(self, '_target_global_rect', None) is not None or getattr(self, '_target_widgets', None) or self.target_widget is not None)
        if not target_exists and not self.panel.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if getattr(self, '_target_global_rect', None) is not None:
            target_global = self._target_global_rect
        elif getattr(self, '_target_widgets', None):
            rects = []
            for w in self._target_widgets:
                try:
                    gpos = w.mapToGlobal(QPoint(0, 0))
                    rects.append(QRect(gpos, w.rect().size()))
                except Exception:
                    pass
            if not rects:
                return
            u = rects[0]
            for r in rects[1:]:
                u = u.united(r)
            target_global = u
        else:
            target_global = QRect(self.target_widget.mapToGlobal(QPoint(0, 0)), self.target_widget.rect().size())
        overlay_pos = self.mapFromGlobal(target_global.topLeft())
        relative_rect = QRect(overlay_pos, target_global.size())

        if target_exists:
            glow_color = QColor(255, 0, 0)
            for expand, alpha, pen_width in ((4, 40, 8), (2, 90, 4), (0, 160, 2)):
                c = QColor(glow_color)
                c.setAlpha(alpha)
                pen = QPen(c, pen_width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                r = QRect(relative_rect.adjusted(-expand, -expand, expand, expand))
                radius = max(6, 6 + expand * 0.5)
                painter.drawRoundedRect(r, radius, radius)

            pen = QPen(QColor(255, 46, 46), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(relative_rect, 6, 6)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_geometry()
        try:
            if not self._tracking_timer.isActive():
                self._tracking_timer.start()
        except Exception:
            pass

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.parent() and event.type() in (QEvent.Resize, QEvent.Move, QEvent.LayoutRequest, QEvent.ChildAdded, QEvent.ChildRemoved, QEvent.Show, QEvent.Hide, QEvent.WindowStateChange):
            QTimer.singleShot(0, self.update_geometry)
            return super().eventFilter(obj, event)

        if getattr(self, '_target_widgets', None) and obj in self._target_widgets:
            if event.type() in (QEvent.Resize, QEvent.Move, QEvent.Show, QEvent.Hide, QEvent.LayoutRequest):
                QTimer.singleShot(0, self.update_geometry)
                return super().eventFilter(obj, event)

        return super().eventFilter(obj, event)

    def _on_next(self):
        steps = self.tour_content.get(self.current_lang, [])
        if not steps:
            return
        self.current_index = min(len(steps) - 1, self.current_index + 1)
        self._update_panel_content()

    def _on_prev(self):
        steps = self.tour_content.get(self.current_lang, [])
        if not steps:
            return
        self.current_index = max(0, self.current_index - 1)
        self._update_panel_content()

    def _on_lang_changed(self, lang):
        self.current_lang = lang
        steps = self.tour_content.get(self.current_lang, [])
        if self.current_index >= len(steps):
            self.current_index = max(0, len(steps) - 1)
        self._update_panel_content()

    def _mark_guide_as_shown(self):
        """Create the .is_guide_shown file in temp/ to persist that the guide was closed."""
        if not self._seen_file:
            return
        try:
            self._seen_file.parent.mkdir(parents=True, exist_ok=True)
            self._seen_file.write_text('1')
        except Exception as e:
            print(f"GuideOverlay: Failed to write seen file {self._seen_file}: {e}")

    def _is_guide_already_shown(self) -> bool:
        return bool(self._seen_file and self._seen_file.exists())

    def _on_close(self):
        try:
            self._mark_guide_as_shown()
        except Exception:
            pass
        self.clear_target()

    def reset_shown_marker(self) -> bool:
        """Remove the persistent marker so the guide can be shown again."""
        if not self._seen_file:
            return False
        try:
            if self._seen_file.exists():
                self._seen_file.unlink()
                return True
        except Exception as e:
            print(f"GuideOverlay: Failed to remove seen file {self._seen_file}: {e}")
        return False

    def reset_and_show(self):
        """Public helper: remove marker and show the guide immediately."""
        try:
            self.reset_shown_marker()
        except Exception:
            pass
        self.current_index = 0
        try:
            self.show_if_needed()
        except Exception:
            try:
                if hasattr(self.parent(), 'table'):
                    self.set_target(self.parent().table, "", "")
                    self._update_panel_content()
            except Exception:
                pass

    def show_if_needed(self):
        try:
            if self._is_guide_already_shown():
                return
        except Exception:
            pass

        if hasattr(self.parent(), 'table'):
            self.set_target(self.parent().table, "", "")
            idx = self.lang_combo.currentIndex()
            self.current_lang = self.lang_combo.itemData(idx) or 'EN'
            self.current_index = 0
            self._update_panel_content()