import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QSizePolicy, QApplication, QToolTip
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QIcon, QColor, QCursor
import qtawesome as qta
from ui.theme_system import theme
from helpers.tools.holiday_calendar_helper.search_helper import PLATFORMS, ico_path, build_url


class MetaRow(QFrame):
    def __init__(self, icon_name: str, label: str, value: str, color: str = None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(18, 18)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clr = color or theme.get_color('primary')
        try:
            icon_lbl.setPixmap(qta.icon(icon_name, color=clr).pixmap(13, 13))
        except Exception:
            icon_lbl.setText('')
        layout.addWidget(icon_lbl)

        key_lbl = QLabel(label)
        key_lbl.setStyleSheet('font-size: 10px;')
        key_lbl.setFixedWidth(64)
        layout.addWidget(key_lbl)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f'color: {clr}; font-size: 11px;')
        val_lbl.setWordWrap(True)
        layout.addWidget(val_lbl, 1)


class DetailPanelWidget(QWidget):
    close_requested = Signal()
    search_platform_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._holiday = None
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self):
        self.setMinimumWidth(220)
        self.setMaximumWidth(380)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(38)
        hdr_lyt = QHBoxLayout(header)
        hdr_lyt.setContentsMargins(10, 4, 6, 4)
        hdr_lyt.setSpacing(6)

        ico_lbl = QLabel()
        try:
            ico_lbl.setPixmap(qta.icon('fa6s.circle-info', color=theme.get_color('primary')).pixmap(14, 14))
        except Exception:
            pass

        title_lbl = QLabel('Holiday Detail')
        tf = QFont()
        tf.setBold(True)
        tf.setPointSize(10)
        title_lbl.setFont(tf)

        close_btn = QPushButton()
        close_btn.setFixedSize(22, 22)
        close_btn.setToolTip('Close panel')
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            close_btn.setIcon(qta.icon('fa6s.xmark'))
        except Exception:
            close_btn.setText('X')
        close_btn.clicked.connect(self._on_close)

        hdr_lyt.addWidget(ico_lbl)
        hdr_lyt.addWidget(title_lbl, 1)
        hdr_lyt.addWidget(close_btn)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(10, 10, 10, 10)
        self._content_layout.setSpacing(6)
        self._content_layout.addStretch()

        scroll.setWidget(self._content_widget)
        outer.addWidget(scroll, 1)

    def _on_close(self):
        self.setVisible(False)
        self.close_requested.emit()

    def show_holiday(self, holiday: dict):
        self._holiday = holiday
        self._render()
        self.setVisible(True)

    def show_date_holidays(self, date_str: str, holidays: list):
        if not holidays:
            return
        if len(holidays) == 1:
            self.show_holiday(holidays[0])
        else:
            self._render_multiple(date_str, holidays)
            self.setVisible(True)

    def _clear_content(self):
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render(self):
        self._clear_content()
        if not self._holiday:
            return
        h = self._holiday
        pos = 0
        primary = theme.get_color('primary')

        name_frame = QFrame()
        name_frame.setObjectName('hc_name_frame')
        name_frame.setStyleSheet('QFrame#hc_name_frame { border: none; }')
        nf_lyt = QVBoxLayout(name_frame)
        nf_lyt.setContentsMargins(10, 8, 10, 8)
        nf_lyt.setSpacing(3)

        name_lbl = QLabel(h.get('name', ''))
        nf = QFont()
        nf.setBold(True)
        nf.setPointSize(12)
        name_lbl.setFont(nf)
        name_lbl.setStyleSheet('background: transparent;')
        name_lbl.setWordWrap(True)
        nf_lyt.addWidget(name_lbl)

        date_lbl = QLabel(h.get('date', ''))
        date_lbl.setStyleSheet('font-size: 11px; background: transparent;')
        nf_lyt.addWidget(date_lbl)
        self._content_layout.insertWidget(pos, name_frame)
        pos += 1

        desc = h.get('description', '')
        if desc:
            desc_frame = QFrame()
            desc_frame.setObjectName('hc_desc_frame')
            desc_frame.setStyleSheet(f'''
                QFrame#hc_desc_frame {{
                    border: none;
                    border-left: 2px solid {primary}44;
                }}
            ''')
            df_lyt = QVBoxLayout(desc_frame)
            df_lyt.setContentsMargins(8, 6, 8, 6)

            desc_title = QLabel('Description')
            desc_title.setStyleSheet('font-size: 9px; font-weight: bold;')
            df_lyt.addWidget(desc_title)

            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet('font-size: 11px;')
            desc_lbl.setWordWrap(True)
            df_lyt.addWidget(desc_lbl)
            self._content_layout.insertWidget(pos, desc_frame)
            pos += 1

        types = h.get('type', [])
        type_text = ', '.join(str(t) for t in types) if isinstance(types, list) and types else str(types) if types else 'N/A'

        section_lbl = QLabel('DETAILS')
        section_lbl.setStyleSheet('font-size: 9px; font-weight: bold; letter-spacing: 1px;')
        self._content_layout.insertWidget(pos, section_lbl)
        pos += 1

        country_display = h.get('country_name', '') or h.get('country_id', '')
        states_display = h.get('states', 'All')
        if isinstance(states_display, list):
            states_display = 'All'
        scope_text = 'National' if h.get('is_national', False) else states_display

        meta_rows = [
            ('fa6s.globe', 'Country', country_display, theme.get_color('success')),
            ('fa6s.tag', 'Type', type_text, theme.get_color('warning')),
            ('fa6s.certificate', 'Primary Type', h.get('primary_type', 'N/A'), primary),
            ('fa6s.location-dot', 'Scope', scope_text, theme.get_color('success')),
        ]
        for icon_name, label, value, color in meta_rows:
            if value and value != 'N/A':
                row = MetaRow(icon_name, label, value, color)
                self._content_layout.insertWidget(pos, row)
                pos += 1

        keyword = h.get('name', '')
        if keyword:
            search_lbl = QLabel('SEARCH IN')
            search_lbl.setStyleSheet('font-size: 9px; font-weight: bold; letter-spacing: 1px;')
            self._content_layout.insertWidget(pos, search_lbl)
            pos += 1

            btn_container = QWidget()
            btn_vbox = QVBoxLayout(btn_container)
            btn_vbox.setContentsMargins(0, 0, 0, 0)
            btn_vbox.setSpacing(3)

            pc = QColor(primary)
            pr, pg, pb = pc.red(), pc.green(), pc.blue()

            for p in PLATFORMS:
                row_lyt = QHBoxLayout()
                row_lyt.setContentsMargins(0, 0, 0, 0)
                row_lyt.setSpacing(2)

                btn = QPushButton(p['name'])
                btn.setFixedHeight(26)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(f"Search '{keyword}' on {p['name']}")
                btn.setStyleSheet(f'''
                    QPushButton {{
                        border: none;
                        border-radius: 4px;
                        font-size: 10px;
                        padding: 0px 6px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background-color: rgba({pr},{pg},{pb},0.12);
                    }}
                ''')
                ico_file = ico_path(p['id'])
                if os.path.exists(ico_file):
                    btn.setIcon(QIcon(ico_file))
                pid = p['id']
                btn.clicked.connect(lambda checked=False, _pid=pid, _kw=keyword:
                    self.search_platform_requested.emit(_pid, _kw))

                copy_url_btn = QPushButton()
                copy_url_btn.setFixedSize(24, 26)
                copy_url_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                copy_url_btn.setStyleSheet(f'''
                    QPushButton {{
                        border: none;
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        background-color: rgba({pr},{pg},{pb},0.12);
                    }}
                ''')
                try:
                    copy_url_btn.setIcon(qta.icon('fa6s.link', color=theme.get_color('text_dark')))
                except Exception:
                    copy_url_btn.setText('🔗')
                def _copy_url(checked=False, _pid=pid, _kw=keyword):
                    url = build_url(_pid, _kw)
                    QApplication.clipboard().setText(url)
                    QToolTip.showText(QCursor.pos(), f'Copied: {url}')
                copy_url_btn.clicked.connect(_copy_url)

                row_lyt.addWidget(btn, 1)
                row_lyt.addWidget(copy_url_btn)
                btn_vbox.addLayout(row_lyt)

            self._content_layout.insertWidget(pos, btn_container)
            pos += 1

    def _render_multiple(self, date_str: str, holidays: list):
        self._clear_content()
        pos = 0
        primary = theme.get_color('primary')

        header_frame = QFrame()
        header_frame.setObjectName('hc_multi_header')
        header_frame.setStyleSheet('QFrame#hc_multi_header { border: none; }')
        hf_lyt = QVBoxLayout(header_frame)
        hf_lyt.setContentsMargins(10, 8, 10, 8)
        date_lbl = QLabel(date_str)
        df = QFont()
        df.setBold(True)
        df.setPointSize(12)
        date_lbl.setFont(df)
        date_lbl.setStyleSheet('background: transparent;')
        count_lbl = QLabel(f"{len(holidays)} holidays on this date")
        count_lbl.setStyleSheet('font-size: 10px;')
        hf_lyt.addWidget(date_lbl)
        hf_lyt.addWidget(count_lbl)
        self._content_layout.insertWidget(pos, header_frame)
        pos += 1

        for h in holidays:
            card = QFrame()
            card.setObjectName('hc_mini_card')
            card.setStyleSheet('QFrame#hc_mini_card { border: none; }')
            card_lyt = QVBoxLayout(card)
            card_lyt.setContentsMargins(8, 6, 8, 6)
            card_lyt.setSpacing(2)

            n = QLabel(h.get('name', ''))
            nf = QFont()
            nf.setBold(True)
            nf.setPointSize(10)
            n.setFont(nf)
            n.setWordWrap(True)
            card_lyt.addWidget(n)

            desc = h.get('description', '')
            if desc:
                dl = QLabel(desc[:80] + ('...' if len(desc) > 80 else ''))
                dl.setStyleSheet('font-size: 10px;')
                dl.setWordWrap(True)
                card_lyt.addWidget(dl)

            self._content_layout.insertWidget(pos, card)
            pos += 1
