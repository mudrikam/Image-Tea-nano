from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QComboBox
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.theme_system import theme


class MemberLimitDialog(QDialog):
    def __init__(self, parent=None, used=0, limit=0):
        super().__init__(parent)
        self.setWindowTitle("Usage Limit Reached")
        self.setFixedWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._used = used
        self._limit = limit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        # --- Header ---
        header_layout = QHBoxLayout()
        self._header_icon_lbl = QLabel()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._subtitle_lbl = QLabel()
        self._subtitle_lbl.setStyleSheet("font-size: 10px; opacity: 0.6;")
        header_text.addWidget(self._title_lbl)
        header_text.addWidget(self._subtitle_lbl)
        header_layout.addWidget(self._header_icon_lbl)
        header_layout.addSpacing(10)
        header_layout.addLayout(header_text)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # --- Status section ---
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setFrameShadow(QFrame.Sunken)
        status_vbox = QVBoxLayout(status_frame)
        status_vbox.setContentsMargins(10, 8, 10, 10)
        status_vbox.setSpacing(6)

        status_header_row = QHBoxLayout()
        status_header_row.setSpacing(5)
        status_ic = QLabel()
        status_ic.setPixmap(qta.icon('fa6s.circle-info', color=theme.get_color('error')).pixmap(12, 12))
        self._status_section_title = QLabel()
        self._status_section_title.setStyleSheet(
            f"font-size: 9px; font-weight: bold; color: {theme.get_color('error')}; letter-spacing: 1px;"
        )
        status_header_row.addWidget(status_ic)
        status_header_row.addWidget(self._status_section_title)
        status_header_row.addStretch()
        status_vbox.addLayout(status_header_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._status_key_lbl = QLabel()
        self._status_key_lbl.setStyleSheet("font-size: 11px; opacity: 0.6;")
        self._status_key_lbl.setFixedWidth(130)
        self._status_key_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._status_val_lbl = QLabel(f"{used} / {limit}")
        self._status_val_lbl.setStyleSheet(
            f"color: {theme.get_color('error')}; font-size: 11px; font-weight: bold;"
        )
        status_row.addWidget(self._status_key_lbl)
        status_row.addWidget(self._status_val_lbl, 1)
        status_vbox.addLayout(status_row)
        layout.addWidget(status_frame)

        # --- Options section ---
        options_frame = QFrame()
        options_frame.setFrameShape(QFrame.StyledPanel)
        options_frame.setFrameShadow(QFrame.Sunken)
        options_vbox = QVBoxLayout(options_frame)
        options_vbox.setContentsMargins(10, 8, 10, 10)
        options_vbox.setSpacing(6)

        options_header_row = QHBoxLayout()
        options_header_row.setSpacing(5)
        options_ic = QLabel()
        options_ic.setPixmap(qta.icon('fa6s.lightbulb', color=theme.get_color('warning')).pixmap(12, 12))
        self._options_section_title = QLabel()
        self._options_section_title.setStyleSheet(
            f"font-size: 9px; font-weight: bold; color: {theme.get_color('warning')}; letter-spacing: 1px;"
        )
        options_header_row.addWidget(options_ic)
        options_header_row.addWidget(self._options_section_title)
        options_header_row.addStretch()
        options_vbox.addLayout(options_header_row)

        self._option1_lbl = QLabel()
        self._option1_lbl.setWordWrap(True)
        self._option1_lbl.setStyleSheet("font-size: 11px;")
        self._option2_lbl = QLabel()
        self._option2_lbl.setWordWrap(True)
        self._option2_lbl.setStyleSheet("font-size: 11px;")
        options_vbox.addWidget(self._make_bullet_row('fa6s.user-shield', 'primary', self._option1_lbl))
        options_vbox.addWidget(self._make_bullet_row('fa6s.key', 'warning', self._option2_lbl))
        self._options_frame = options_frame
        layout.addWidget(self._options_frame)

        # --- Bottom row: language (left) + OK button (right) ---
        btn_layout = QHBoxLayout()
        lang_lbl = QLabel("Language:")
        lang_lbl.setStyleSheet("font-size: 11px;")
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["English", "Indonesia"])
        self._lang_combo.currentIndexChanged.connect(self._rebuild)
        ok_btn = QPushButton("  OK")
        ok_btn.setIcon(qta.icon('fa6s.check'))
        ok_btn.setMinimumHeight(30)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(lang_lbl)
        btn_layout.addWidget(self._lang_combo)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        self._rebuild(0)

    def _make_bullet_row(self, icon_name, color_key, text_label):
        w = QWidget()
        hbox = QHBoxLayout(w)
        hbox.setContentsMargins(0, 2, 0, 2)
        hbox.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(qta.icon(icon_name, color=theme.get_color(color_key)).pixmap(12, 12))
        ic.setFixedSize(16, 16)
        ic.setAlignment(Qt.AlignCenter)
        hbox.addWidget(ic)
        hbox.addWidget(text_label, 1)
        return w

    def _rebuild(self, idx):
        used = self._used
        limit = self._limit
        is_exceeded = limit > 0 and used >= limit
        limit_str = str(limit) if limit > 0 else ("Unlimited" if idx == 0 else "Tidak Terbatas")

        if is_exceeded:
            self._header_icon_lbl.setPixmap(
                qta.icon('fa6s.circle-xmark', color=theme.get_color('error')).pixmap(32, 32)
            )
            val_color = theme.get_color('error')
        else:
            self._header_icon_lbl.setPixmap(
                qta.icon('fa6s.gauge-high', color=theme.get_color('primary')).pixmap(32, 32)
            )
            val_color = theme.get_color('success') if not is_exceeded else theme.get_color('error')

        self._status_val_lbl.setStyleSheet(
            f"color: {val_color}; font-size: 11px; font-weight: bold;"
        )
        self._options_frame.setVisible(is_exceeded)

        if idx == 0:
            self.setWindowTitle("Member Usage Limit Reached" if is_exceeded else "Member Usage Info")
            self._title_lbl.setText("Member Usage Limit Reached" if is_exceeded else "Member Usage Info")
            self._subtitle_lbl.setText(
                f"{used} of {limit_str} files used"
            )
            self._status_section_title.setText("STATUS")
            self._status_key_lbl.setText("Files used / limit:")
            self._status_val_lbl.setText(f"{used} / {limit_str}")
            self._options_section_title.setText("WHAT CAN YOU DO?")
            self._option1_lbl.setText("Renew your membership, contact admin")
            self._option2_lbl.setText("Or use your own API Key via the Add API Key menu")
        else:
            self.setWindowTitle("Member Limit Tercapai" if is_exceeded else "Info Penggunaan Member")
            self._title_lbl.setText("Limit Penggunaan Member Tercapai" if is_exceeded else "Info Penggunaan Member")
            self._subtitle_lbl.setText(
                f"{used} dari {limit_str} file telah digunakan"
            )
            self._status_section_title.setText("STATUS")
            self._status_key_lbl.setText("File digunakan / limit:")
            self._status_val_lbl.setText(f"{used} / {limit_str}")
            self._options_section_title.setText("APA YANG BISA DILAKUKAN?")
            self._option1_lbl.setText("Perbarui membership kamu, hubungi admin")
            self._option2_lbl.setText("Atau gunakan API Key sendiri melalui menu Add API Key")


def show_member_limit_dialog(parent=None, used=0, limit=0):
    dlg = MemberLimitDialog(parent, used, limit)
    dlg.exec()
