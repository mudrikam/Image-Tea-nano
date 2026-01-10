from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QLabel, QCheckBox, QPushButton, QHBoxLayout, QRadioButton, QButtonGroup
from PySide6.QtGui import QIcon, QFont, QPixmap
from PySide6.QtCore import Qt
import os
import json
from config import BASE_PATH
import qtawesome as qta

class DisclaimerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        icon_path = os.path.join(BASE_PATH, "res", "image_tea.ico")
        self.setWindowTitle("Disclaimer")
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                app_config = json.load(f)
        except Exception as e:
            print(f"Error loading app_config.json: {e}")
            app_config = {}

        app_name = app_config["name"]
        app_version = app_config["version"]
        app_developer = app_config["developer"]
        app_description = app_config["description"]
        disclaimer_text_en = app_config["disclaimer_text_en"]
        disclaimer_text_id = app_config["disclaimer_text_id"]
        disclaimer_explanation_en = app_config["disclaimer_explanation_en"]
        disclaimer_explanation_id = app_config["disclaimer_explanation_id"]

        icon_label = QLabel()
        icon = QIcon(icon_path)
        pixmap = icon.pixmap(64, 64)
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap)
            icon_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            layout.addWidget(icon_label)

        title_label = QLabel("Disclaimer")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.addWidget(title_label)

        app_info = f"{app_name} v{app_version}\n{app_developer}\n{app_description}"
        app_info_label = QLabel(app_info)
        app_info_font = QFont()
        app_info_font.setPointSize(11)
        app_info_label.setFont(app_info_font)
        app_info_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        app_info_label.setWordWrap(True)
        layout.addWidget(app_info_label)

        self.disclaimer_label = QLabel(disclaimer_text_id)
        disclaimer_font = QFont()
        disclaimer_font.setPointSize(11)
        disclaimer_font.setBold(True)
        self.disclaimer_label.setFont(disclaimer_font)
        self.disclaimer_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.disclaimer_label.setWordWrap(True)

        self.license_title_en = "This App is licensed under the MIT License"
        self.license_title_id = "Aplikasi ini dilisensikan di bawah Lisensi MIT"
        self.license_title_label = QLabel(self.license_title_id)
        license_title_font = QFont()
        license_title_font.setPointSize(12)
        license_title_font.setBold(True)
        self.license_title_label.setFont(license_title_font)
        self.license_title_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)

        self.mit_license_content_label = QLabel(disclaimer_explanation_id)
        self.mit_license_content_label.setWordWrap(True)
        self.mit_license_content_label.setAlignment(Qt.AlignTop)
        self.scroll_layout.addWidget(self.mit_license_content_label)
        self.scroll.setWidget(self.scroll_content)

        layout.addWidget(self.disclaimer_label)
        layout.addWidget(self.license_title_label)
        layout.addWidget(self.scroll)

        radio_layout = QHBoxLayout()
        self.radio_id = QRadioButton("Bahasa Indonesia")
        self.radio_en = QRadioButton("English")
        self.radio_id.setChecked(True)
        self.lang_group = QButtonGroup()
        self.lang_group.addButton(self.radio_id)
        self.lang_group.addButton(self.radio_en)
        radio_layout.addWidget(self.radio_id)
        radio_layout.addWidget(self.radio_en)
        layout.addLayout(radio_layout)

        self.checkbox = QCheckBox("Saya telah membaca dan menyetujui syarat dan disclaimer di atas.")
        layout.addWidget(self.checkbox)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.continue_btn = QPushButton(qta.icon('fa6s.check'), " Mengerti dan Lanjutkan")
        self.continue_btn.setEnabled(False)
        btn_layout.addWidget(self.continue_btn)
        layout.addLayout(btn_layout)

        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        self.continue_btn.clicked.connect(self.accept)
        self.radio_id.toggled.connect(lambda: self._set_language('id'))
        self.radio_en.toggled.connect(lambda: self._set_language('en'))

        self.disclaimer_text_en = disclaimer_text_en
        self.disclaimer_text_id = disclaimer_text_id
        self.disclaimer_explanation_en = disclaimer_explanation_en
        self.disclaimer_explanation_id = disclaimer_explanation_id

        self.setLayout(layout)

    def _on_checkbox_changed(self, state):
        self.continue_btn.setEnabled(self.checkbox.isChecked())

    def _set_language(self, lang):
        if lang == 'id' and self.radio_id.isChecked():
            self.disclaimer_label.setText(self.disclaimer_text_id)
            self.mit_license_content_label.setText(self.disclaimer_explanation_id)
            self.license_title_label.setText(self.license_title_id)
            self.checkbox.setText("Saya telah membaca dan menyetujui syarat dan disclaimer di atas.")
            self.continue_btn.setText("Mengerti dan Lanjutkan")
        elif lang == 'en' and self.radio_en.isChecked():
            self.disclaimer_label.setText(self.disclaimer_text_en)
            self.mit_license_content_label.setText(self.disclaimer_explanation_en)
            self.license_title_label.setText(self.license_title_en)
            self.checkbox.setText("I have read and agree to the terms and disclaimer above.")
            self.continue_btn.setText("Understand and Continue")

    def closeEvent(self, event):
        event.accept()

    @staticmethod
    def check_and_show(parent=None):
        temp_path = os.path.join(BASE_PATH, "temp")
        try:
            if not os.path.exists(temp_path):
                os.makedirs(temp_path)
        except Exception as e:
            print(f"Error creating temp directory: {e}")
            return False
        flag_file = os.path.join(temp_path, ".is_first_launch")
        try:
            if os.path.exists(flag_file):
                return True
            dialog = DisclaimerDialog(parent)
            result = dialog.exec()
            if result == QDialog.Accepted:
                try:
                    with open(flag_file, "w") as f:
                        f.write("shown")
                except Exception as e:
                    print(f"Error writing flag file: {e}")
                return True
            else:
                return False
        except Exception as e:
            print(f"Error in disclaimer check_and_show: {e}")
            return False
