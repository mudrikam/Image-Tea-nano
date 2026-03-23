from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QWidget, QSizePolicy, QFrame, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, QThread, Signal
import qtawesome as qta
import datetime

from ui.theme_system import theme


def _relative_time(iso_str):
    if not iso_str:
        return '-'
    try:
        dt = datetime.datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - dt
        days = diff.days
        if days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                mins = diff.seconds // 60
                return f"{mins} minute{'s' if mins != 1 else ''} ago"
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        return f"{days} day{'s' if days != 1 else ''} ago"
    except Exception:
        return str(iso_str)


KOBOILLM_LLM_KEY_WARNING = (
    "This API key does not have permission to check credit usage.\n\n"
    "Currently your API key is an LLM-only key, which can only be used to make "
    "chat completions. To check your balance, you need a Management Key or the "
    "default account key.\n\n"
    "Please contact KoboILLM admin for more details."
)


class CreditCheckThread(QThread):
    result = Signal(dict)
    error = Signal(str)

    def __init__(self, api_key: str, is_koboillm: bool = False):
        super().__init__()
        self._api_key = api_key
        self._is_koboillm = is_koboillm

    def run(self):
        try:
            import requests
            if self._is_koboillm:
                resp = requests.get(
                    "https://api.koboillm.com/key/info",
                    params={"key": self._api_key},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=15
                )
                body = resp.text.strip() if resp.text else ""
                if not body:
                    self.error.emit("No response from KoboILLM API.")
                    return
                try:
                    data = resp.json()
                except Exception:
                    self.error.emit(f"Invalid response from server (HTTP {resp.status_code}):\n{body[:300]}")
                    return
                if resp.status_code == 403:
                    detail = data.get('detail', '')
                    if 'not allowed to call' in str(detail).lower() or 'llm_api_routes' in str(detail).lower():
                        self.error.emit(KOBOILLM_LLM_KEY_WARNING)
                    else:
                        self.error.emit(f"Access denied.\n\nServer: {detail}")
                    return
                if resp.status_code >= 400:
                    detail = data.get('detail') or data.get('message') or str(data)
                    self.error.emit(f"API key does not exist or is invalid.\n\nServer: {detail}")
                    return
                self.result.emit(data)
            else:
                webhook_url = "https://purchese.desainia.my.id/webhook/check-key"
                payload = {"key": self._api_key}
                resp = requests.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=15
                )
                body = resp.text.strip() if resp.text else ""
                if not body:
                    self.error.emit("API key does not exist or is not recognized by Desainia API.")
                    return
                try:
                    data = resp.json()
                except Exception:
                    self.error.emit(f"Invalid response from server (HTTP {resp.status_code}):\n{body[:300]}")
                    return
                if resp.status_code >= 400:
                    detail = data.get('detail') or data.get('message') or str(data)
                    self.error.emit(f"API key does not exist or is invalid.\n\nServer: {detail}")
                    return
                self.result.emit(data)
        except Exception as e:
            self.error.emit(str(e))
            print(f"[CreditCheckThread] Error: {e}")


class CreditUsageDialog(QDialog):
    def __init__(self, api_key: str, parent=None, endpoint: str = ''):
        super().__init__(parent)
        self._api_key = api_key
        self._is_koboillm = 'api.koboillm.com' in str(endpoint)
        self._truncated = self._truncate_key(api_key)
        self.setWindowTitle(f"Credit Usage — {self._truncated}")
        self.setFixedWidth(500)
        self.setMinimumHeight(380)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        icon_lbl = QLabel()
        icon = qta.icon('fa6s.coins', color=theme.get_color('warning'))
        pix = icon.pixmap(28, 28)
        icon_lbl.setPixmap(pix)

        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        title_lbl = QLabel("Desainia API")
        title_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: bold;"
        )
        subtitle_lbl = QLabel(f"Credit Usage  ·  {self._truncated}")
        subtitle_lbl.setStyleSheet(f"font-size: 10px; opacity: 0.6;")
        header_text.addWidget(title_lbl)
        header_text.addWidget(subtitle_lbl)

        header_layout.addWidget(icon_lbl)
        header_layout.addSpacing(10)
        header_layout.addLayout(header_text)
        header_layout.addStretch()
        layout.addLayout(header_layout)


        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.content_widget = QWidget()
        self.content_widget.setVisible(False)
        self._content_layout = QVBoxLayout(self.content_widget)
        self._content_layout.setContentsMargins(0, 2, 0, 0)
        self._content_layout.setSpacing(8)
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll, 1)

        self.error_lbl = QLabel()
        self.error_lbl.setVisible(False)
        self.error_lbl.setWordWrap(True)
        self.error_lbl.setStyleSheet(
            f"color: {theme.get_color('error')}; font-size: 11px;"
            f"padding: 10px; border-radius: 6px;"
        )
        layout.addWidget(self.error_lbl)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("  Close")
        close_btn.setIcon(qta.icon('fa6s.xmark'))
        close_btn.setMinimumHeight(30)
        close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        self._thread = CreditCheckThread(api_key, is_koboillm=self._is_koboillm)
        self._thread.result.connect(self._on_result)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def closeEvent(self, event):
        if self._thread.isRunning():
            self._thread.blockSignals(True)
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)

    def _truncate_key(self, key, head=4, tail=6):
        s = str(key) if key else ''
        if len(s) <= head + tail + 3:
            return s
        return f"{s[:head]}...{s[-tail:]}"

    def _on_result(self, data):
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(1)
        self.progress_bar.setVisible(False)
        info = data.get('info', {})
        self._populate_content(info)
        self.content_widget.setVisible(True)

    def _on_error(self, error_msg):
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(1)
        self.progress_bar.setVisible(False)
        self.error_lbl.setText(f"Failed to fetch credit usage:\n{error_msg}")
        self.error_lbl.setVisible(True)

    def _make_section(self, title, icon_name, icon_color_key='primary'):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Sunken)
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(10, 8, 10, 10)
        vbox.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(5)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            qta.icon(icon_name, color=theme.get_color(icon_color_key)).pixmap(12, 12)
        )
        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(
            f"font-size: 9px; font-weight: bold; color: {theme.get_color(icon_color_key)}; letter-spacing: 1px;"
        )
        title_row.addWidget(icon_lbl)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        vbox.addLayout(title_row)

        return frame, vbox

    def _make_row(self, label, value, value_color_key=None, bold=False):
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(8)

        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet(f"font-size: 11px; opacity: 0.6;")
        lbl.setFixedWidth(110)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        val_text = str(value) if value is not None else '-'
        val = QLabel(val_text)
        if value_color_key:
            color = theme.get_color(value_color_key)
            weight = "font-weight: bold;" if bold else ""
            val.setStyleSheet(f"color: {color}; font-size: 11px; {weight}")
        else:
            weight = "font-weight: bold;" if bold else ""
            val.setStyleSheet(f"font-size: 11px; {weight}")
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        val.setWordWrap(True)

        hbox.addWidget(lbl)
        hbox.addWidget(val, 1)
        w = QWidget()
        w.setLayout(hbox)
        return w

    def _populate_content(self, info):
        layout = self._content_layout

        spend = float(info.get('spend') or 0)
        max_budget = float(info.get('max_budget') or 0)
        budget_pct = (spend / max_budget * 100) if max_budget > 0 else 0

        if budget_pct >= 80:
            spend_color_key = 'error'
        elif budget_pct >= 50:
            spend_color_key = 'warning'
        else:
            spend_color_key = 'success'

        budget_frame, budget_vbox = self._make_section("Budget & Dates", 'fa6s.dollar-sign', spend_color_key)

        spend_row = QHBoxLayout()
        spend_row.setSpacing(16)
        spend_lbl = QLabel(f"${spend:.4f}")
        spend_lbl.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {theme.get_color(spend_color_key)};"
        )
        spend_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        remain = max(max_budget - spend, 0)
        of_lbl = QLabel(f"of ${max_budget:.4f}  ·  ${remain:.4f} left")
        of_lbl.setStyleSheet(f"font-size: 11px; opacity: 0.6;")
        of_lbl.setAlignment(Qt.AlignVCenter)
        spend_row.addWidget(spend_lbl)
        spend_row.addWidget(of_lbl)
        spend_row.addStretch()
        budget_vbox.addLayout(spend_row)

        pct_bar = QProgressBar()
        pct_bar.setMinimum(0)
        pct_bar.setMaximum(100)
        pct_bar.setValue(int(min(budget_pct, 100)))
        pct_bar.setFixedHeight(16)
        pct_bar.setTextVisible(True)
        pct_bar.setFormat(f"Used: {budget_pct:.1f}%")
        pct_bar.setAlignment(Qt.AlignCenter)
        chunk_color = theme.get_color(spend_color_key)
        from PySide6.QtGui import QColor
        bg_color = QColor(chunk_color)
        bg_color.setAlpha(51)
        pct_bar.setStyleSheet(f"""
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
        budget_vbox.addWidget(pct_bar)

        budget_duration = info.get('budget_duration')
        if budget_duration:
            budget_vbox.addWidget(self._make_row("Duration", budget_duration))

        created_at = info.get('created_at')
        updated_at = info.get('updated_at')
        expires = info.get('expires')
        expiry_text = _relative_time(expires) if expires else 'Lifetime'
        expiry_color = 'success' if not expires else 'warning'
        budget_vbox.addWidget(self._make_row("Created", _relative_time(created_at)))
        budget_vbox.addWidget(self._make_row("Updated", _relative_time(updated_at)))
        budget_vbox.addWidget(self._make_row("Expires", expiry_text, expiry_color))

        layout.addWidget(budget_frame)

        key_frame, key_vbox = self._make_section("Key & User Info", 'fa6s.key')
        key_name = info.get('key_name') or self._truncated
        key_alias = info.get('key_alias') or info.get('user_id') or '-'
        blocked = info.get('blocked')
        status_text = 'Active' if not blocked else 'Blocked'
        status_color_key = 'success' if not blocked else 'error'
        status_icon_lbl = QLabel()
        status_icon_lbl.setPixmap(
            qta.icon('fa6s.circle', color=theme.get_color(status_color_key)).pixmap(8, 8)
        )
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        status_label = QLabel("Status:")
        status_label.setStyleSheet(f"font-size: 11px; opacity: 0.6;")
        status_label.setFixedWidth(110)
        status_val_row = QHBoxLayout()
        status_val_row.setSpacing(4)
        status_val_row.addWidget(status_icon_lbl)
        status_val = QLabel(status_text)
        status_val.setStyleSheet(
            f"color: {theme.get_color(status_color_key)}; font-size: 11px; font-weight: bold;"
        )
        status_val_row.addWidget(status_val)
        status_val_row.addStretch()
        status_row.addWidget(status_label)
        status_row.addLayout(status_val_row, 1)
        status_w = QWidget()
        status_w.setLayout(status_row)
        key_vbox.addWidget(status_w)
        key_vbox.addWidget(self._make_row("API Key", key_name))
        key_vbox.addWidget(self._make_row("Email", info.get('user_id') or '-'))
        layout.addWidget(key_frame)

        limits_frame, limits_vbox = self._make_section("Rate Limits", 'fa6s.sliders')
        tpm = info.get('tpm_limit')
        rpm = info.get('rpm_limit')
        max_par = info.get('max_parallel_requests')
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        for col, (label, val, icon_name) in enumerate([
            ("TPM Limit", tpm, 'fa6s.bolt'),
            ("RPM Limit", rpm, 'fa6s.rotate'),
            ("Max Parallel", max_par, 'fa6s.layer-group'),
        ]):
            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon(icon_name, color=theme.get_color('primary')).pixmap(10, 10))
            display = str(val) if val is not None else '∞'
            color_key = 'foreground' if val is not None else 'text_dark'
            metric_lbl = QLabel(display)
            metric_lbl.setStyleSheet(
                f"font-size: 20px; font-weight: bold; color: {theme.get_color(color_key)};"
            )
            cap_lbl = QLabel(label)
            cap_lbl.setStyleSheet(f"font-size: 9px; opacity: 0.6;")
            cell = QVBoxLayout()
            cell.setSpacing(1)
            icon_row = QHBoxLayout()
            icon_row.setSpacing(4)
            icon_row.addWidget(icon_lbl)
            icon_row.addWidget(cap_lbl)
            icon_row.addStretch()
            cell.addLayout(icon_row)
            cell.addWidget(metric_lbl)
            cell_w = QWidget()
            cell_w.setLayout(cell)
            grid.addWidget(cell_w, 0, col)
        limits_vbox.addLayout(grid)
        layout.addWidget(limits_frame)

        layout.addStretch()
