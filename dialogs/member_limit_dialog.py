from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QComboBox, QProgressBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import qtawesome as qta
from ui.theme_system import theme


class MemberLimitDialog(QDialog):
    def __init__(self, parent=None, used=0, limit=0, session=None):
        super().__init__(parent)
        self.setWindowTitle("Usage Limit Reached")
        self.setFixedWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._used = used
        self._limit = limit
        self._session = session or {}

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

        self._usage_bar = QProgressBar()
        self._usage_bar.setMinimum(0)
        self._usage_bar.setMaximum(100)
        self._usage_bar.setFixedHeight(16)
        self._usage_bar.setTextVisible(True)
        self._usage_bar.setAlignment(Qt.AlignCenter)
        status_vbox.addWidget(self._usage_bar)

        layout.addWidget(status_frame)

        # --- Account Info section ---
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_frame.setFrameShadow(QFrame.Sunken)
        info_vbox = QVBoxLayout(info_frame)
        info_vbox.setContentsMargins(10, 8, 10, 10)
        info_vbox.setSpacing(6)

        info_header_row = QHBoxLayout()
        info_header_row.setSpacing(5)
        info_ic = QLabel()
        info_ic.setPixmap(qta.icon('fa6s.id-card', color=theme.get_color('primary')).pixmap(12, 12))
        self._info_section_title = QLabel()
        self._info_section_title.setStyleSheet(
            f"font-size: 9px; font-weight: bold; color: {theme.get_color('primary')}; letter-spacing: 1px;"
        )
        info_header_row.addWidget(info_ic)
        info_header_row.addWidget(self._info_section_title)
        info_header_row.addStretch()
        info_vbox.addLayout(info_header_row)

        self._info_name_key = QLabel()
        self._info_name_key.setStyleSheet("font-size: 11px; opacity: 0.6;")
        self._info_name_key.setFixedWidth(80)
        self._info_name_val = QLabel()
        self._info_name_val.setStyleSheet("font-size: 11px;")
        self._info_name_val.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._info_email_key = QLabel()
        self._info_email_key.setStyleSheet("font-size: 11px; opacity: 0.6;")
        self._info_email_key.setFixedWidth(80)
        self._info_email_val = QLabel()
        self._info_email_val.setStyleSheet("font-size: 11px;")
        self._info_email_val.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._info_license_key = QLabel()
        self._info_license_key.setStyleSheet("font-size: 11px; opacity: 0.6;")
        self._info_license_key.setFixedWidth(80)
        self._info_license_val = QLabel()
        self._info_license_val.setStyleSheet("font-size: 11px;")
        self._info_license_val.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._info_status_key = QLabel()
        self._info_status_key.setStyleSheet("font-size: 11px; opacity: 0.6;")
        self._info_status_key.setFixedWidth(80)
        self._info_status_val = QLabel()

        self._info_expires_key = QLabel()
        self._info_expires_key.setStyleSheet("font-size: 11px; opacity: 0.6;")
        self._info_expires_key.setFixedWidth(80)
        self._info_expires_val = QLabel()
        self._info_expires_val.setStyleSheet("font-size: 11px;")

        for key_lbl, val_lbl in [
            (self._info_name_key, self._info_name_val),
            (self._info_email_key, self._info_email_val),
            (self._info_license_key, self._info_license_val),
            (self._info_status_key, self._info_status_val),
            (self._info_expires_key, self._info_expires_val),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(key_lbl)
            row.addWidget(val_lbl, 1)
            info_vbox.addLayout(row)

        layout.addWidget(info_frame)
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

        if limit > 0:
            pct = min(used / limit * 100, 100)
            if pct >= 80:
                bar_color_key = 'error'
            elif pct >= 50:
                bar_color_key = 'warning'
            else:
                bar_color_key = 'success'
        else:
            pct = 0
            bar_color_key = 'primary'

        chunk_color = theme.get_color(bar_color_key)
        bg_color = QColor(chunk_color)
        bg_color.setAlpha(51)
        self._usage_bar.setValue(int(pct))
        self._usage_bar.setFormat(f"Used: {pct:.1f}%")
        self._usage_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: rgba({bg_color.red()}, {bg_color.green()}, {bg_color.blue()}, {bg_color.alpha()});
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background-color: {chunk_color};
            }}
        """)

        self._options_frame.setVisible(is_exceeded)

        session = self._session
        name = session.get('name') or '-'
        email = session.get('email') or '-'
        license_key = session.get('license') or '-'
        status = session.get('status') or '-'
        expires_at = session.get('expires_at')

        days_left = None
        if expires_at:
            try:
                import datetime
                if isinstance(expires_at, str):
                    exp_dt = datetime.datetime.fromisoformat(expires_at.replace('Z', '+00:00')).replace(tzinfo=None)
                elif hasattr(expires_at, 'year'):
                    exp_dt = expires_at.replace(tzinfo=None) if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo else expires_at
                else:
                    exp_dt = None
                if exp_dt:
                    days_left = (exp_dt - datetime.datetime.now()).days
            except Exception:
                pass

        if idx == 0:
            self._info_section_title.setText('ACCOUNT INFO')
            self._info_name_key.setText('Name:')
            self._info_email_key.setText('Email:')
            self._info_license_key.setText('License:')
            self._info_status_key.setText('Status:')
            self._info_expires_key.setText('Expires:')
            status_color = theme.get_color('success') if status == 'active' else theme.get_color('error')
            self._info_status_val.setText(status.capitalize())
            self._info_status_val.setStyleSheet(f'font-size: 11px; color: {status_color}; font-weight: bold;')
            if days_left is not None:
                self._info_expires_val.setText(f'in {days_left} day{"s" if days_left != 1 else ""}')
            elif expires_at:
                self._info_expires_val.setText(str(expires_at)[:10])
            else:
                self._info_expires_val.setText('Lifetime')
        else:
            self._info_section_title.setText('INFO AKUN')
            self._info_name_key.setText('Nama:')
            self._info_email_key.setText('Email:')
            self._info_license_key.setText('Lisensi:')
            self._info_status_key.setText('Status:')
            self._info_expires_key.setText('Kedaluwarsa:')
            status_color = theme.get_color('success') if status == 'active' else theme.get_color('error')
            self._info_status_val.setText('Aktif' if status == 'active' else status.capitalize())
            self._info_status_val.setStyleSheet(f'font-size: 11px; color: {status_color}; font-weight: bold;')
            if days_left is not None:
                self._info_expires_val.setText(f'{days_left} hari lagi')
            elif expires_at:
                self._info_expires_val.setText(str(expires_at)[:10])
            else:
                self._info_expires_val.setText('Selamanya')

        self._info_name_val.setText(name)
        self._info_email_val.setText(email)
        lic_display = license_key[:4] + '...' + license_key[-4:] if len(license_key) > 11 else license_key
        self._info_license_val.setText(lic_display)

        if idx == 0:
            self.setWindowTitle("Member Usage Limit Reached" if is_exceeded else "Member Usage Info")
            self._title_lbl.setText("Member Usage Limit Reached" if is_exceeded else "Member Usage Info")
            self._subtitle_lbl.setText(
                f"{used} of {limit_str} credits used"
            )
            self._status_section_title.setText("STATUS")
            self._status_key_lbl.setText("Credits used / limit:")
            self._status_val_lbl.setText(f"{used} / {limit_str}")
            self._options_section_title.setText("WHAT CAN YOU DO?")
            self._option1_lbl.setText("Renew your membership, contact admin")
            self._option2_lbl.setText("Or use your own API Key via the Add API Key menu")
        else:
            self.setWindowTitle("Member Limit Tercapai" if is_exceeded else "Info Penggunaan Member")
            self._title_lbl.setText("Limit Penggunaan Member Tercapai" if is_exceeded else "Info Penggunaan Member")
            self._subtitle_lbl.setText(
                f"{used} dari {limit_str} credit telah digunakan"
            )
            self._status_section_title.setText("STATUS")
            self._status_key_lbl.setText("Credit digunakan / limit:")
            self._status_val_lbl.setText(f"{used} / {limit_str}")
            self._options_section_title.setText("APA YANG BISA DILAKUKAN?")
            self._option1_lbl.setText("Perbarui membership kamu, hubungi admin")
            self._option2_lbl.setText("Atau gunakan API Key sendiri melalui menu Add API Key")


def show_member_limit_dialog(parent=None, used=0, limit=0):
    dlg = MemberLimitDialog(parent, used, limit)
    dlg.exec()
