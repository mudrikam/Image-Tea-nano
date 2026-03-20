from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.theme_system import theme


class GenerationResultDialog(QDialog):
    def __init__(self, parent=None, total_files=0, success_count=0, failed_count=0,
                 token_input=0, token_output=0, token_total=0, total_time_ms=0):
        super().__init__(parent)
        self.setWindowTitle("Generation Complete")
        self.setFixedWidth(350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        total_time_s = total_time_ms / 1000.0
        files_per_min = (success_count / total_time_s * 60) if total_time_s > 0 else 0

        if total_time_s >= 3600:
            h = int(total_time_s // 3600)
            m = int((total_time_s % 3600) // 60)
            s = int(total_time_s % 60)
            time_str = f"{h}h {m}m {s}s"
        elif total_time_s >= 60:
            m = int(total_time_s // 60)
            s = int(total_time_s % 60)
            time_str = f"{m}m {s}s"
        else:
            time_str = f"{total_time_s:.1f}s"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        # --- Header ---
        header_layout = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon('fa6s.circle-check', color=theme.get_color('success')).pixmap(28, 28))
        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        title_lbl = QLabel("Generation Complete")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        subtitle_lbl = QLabel(f"{success_count} success  ·  {failed_count} failed  ·  {total_files} total")
        subtitle_lbl.setStyleSheet("font-size: 10px; opacity: 0.6;")
        header_text.addWidget(title_lbl)
        header_text.addWidget(subtitle_lbl)
        header_layout.addWidget(icon_lbl)
        header_layout.addSpacing(10)
        header_layout.addLayout(header_text)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        def make_section(title, icon_name, icon_color_key='primary'):
            frame = QFrame()
            frame.setFrameShape(QFrame.StyledPanel)
            frame.setFrameShadow(QFrame.Sunken)
            vbox = QVBoxLayout(frame)
            vbox.setContentsMargins(10, 8, 10, 10)
            vbox.setSpacing(4)
            title_row = QHBoxLayout()
            title_row.setSpacing(5)
            ic = QLabel()
            ic.setPixmap(qta.icon(icon_name, color=theme.get_color(icon_color_key)).pixmap(12, 12))
            t = QLabel(title.upper())
            t.setStyleSheet(f"font-size: 9px; font-weight: bold; color: {theme.get_color(icon_color_key)}; letter-spacing: 1px;")
            title_row.addWidget(ic)
            title_row.addWidget(t)
            title_row.addStretch()
            vbox.addLayout(title_row)
            return frame, vbox

        def make_row(label, value, value_color_key=None, bold=False):
            hbox = QHBoxLayout()
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.setSpacing(8)
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("font-size: 11px; opacity: 0.6;")
            lbl.setFixedWidth(120)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            val = QLabel(str(value))
            if value_color_key:
                weight = "font-weight: bold;" if bold else ""
                val.setStyleSheet(f"color: {theme.get_color(value_color_key)}; font-size: 11px; {weight}")
            else:
                weight = "font-weight: bold;" if bold else ""
                val.setStyleSheet(f"font-size: 11px; {weight}")
            hbox.addWidget(lbl)
            hbox.addWidget(val, 1)
            w = QWidget()
            w.setLayout(hbox)
            return w

        # --- Files section ---
        files_frame, files_vbox = make_section("Files", 'fa6s.images', 'primary')
        files_vbox.addWidget(make_row("Total Files", total_files, bold=True))
        files_vbox.addWidget(make_row("Success", success_count, 'success', bold=True))
        files_vbox.addWidget(make_row("Failed", failed_count, 'error' if failed_count > 0 else None))
        layout.addWidget(files_frame)

        # --- Performance section ---
        perf_frame, perf_vbox = make_section("Performance", 'fa6s.gauge-high', 'warning')
        perf_vbox.addWidget(make_row("Total Time", time_str, bold=True))
        perf_vbox.addWidget(make_row("Files / Minute", f"{files_per_min:.1f}"))
        layout.addWidget(perf_frame)

        # --- Token section ---
        tok_frame, tok_vbox = make_section("Token Usage (Session)", 'fa6s.coins', 'warning')
        tok_vbox.addWidget(make_row("Token Input", f"{token_input:,}"))
        tok_vbox.addWidget(make_row("Token Output", f"{token_output:,}"))
        tok_vbox.addWidget(make_row("Token Total", f"{token_total:,}", bold=True))
        layout.addWidget(tok_frame)

        # --- Button ---
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("  OK")
        ok_btn.setIcon(qta.icon('fa6s.check'))
        ok_btn.setMinimumHeight(30)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

