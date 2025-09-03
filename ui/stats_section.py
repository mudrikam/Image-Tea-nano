from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtGui import QFont
from dialogs.donation_dialog import DonateDialog, is_donation_optout_today
import qtawesome as qta
from PySide6.QtCore import Qt

class StatsSectionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main_vbox = QVBoxLayout(self)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(2)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(8)
        hbox.setAlignment(Qt.AlignTop)

        font = QFont()
        font.setPointSize(8)
        label_color = "#808080"

        def make_icon_label(icon_name, text):
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon(icon_name, color="#888").pixmap(12, 12))
            text_label = QLabel(text)
            text_label.setFont(font)
            text_label.setStyleSheet(f"color: {label_color};")
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            layout.addWidget(icon_label)
            layout.addWidget(text_label)
            layout.addStretch(1)
            container = QWidget()
            container.setLayout(layout)
            return container, text_label

        file_stats_layout = QVBoxLayout()
        file_stats_layout.setContentsMargins(0, 0, 0, 0)
        file_stats_layout.setSpacing(1)
        file_stats_layout.setAlignment(Qt.AlignTop)
        file_total_widget, self.label_total = make_icon_label("fa6s.file", "Total Files: 0")
        file_selected_widget, self.label_selected = make_icon_label("fa6s.square-check", "Selected: 0")
        file_failed_widget, self.label_failed = make_icon_label("fa6s.circle-xmark", "Failed: 0")
        file_success_widget, self.label_success = make_icon_label("fa6s.circle-check", "Success: 0")
        file_draft_widget, self.label_draft = make_icon_label("fa6s.pen-to-square", "Draft: 0")
        file_stats_layout.addWidget(file_total_widget)
        file_stats_layout.addWidget(file_selected_widget)
        file_stats_layout.addWidget(file_failed_widget)
        file_stats_layout.addWidget(file_success_widget)
        file_stats_layout.addWidget(file_draft_widget)

        time_stats_layout = QVBoxLayout()
        time_stats_layout.setContentsMargins(0, 0, 0, 0)
        time_stats_layout.setSpacing(1)
        time_stats_layout.setAlignment(Qt.AlignTop)
        gen_time_widget, self.label_gen_time = make_icon_label("fa6s.clock", "Generation Time: 0 ms")
        avg_time_widget, self.label_avg_time = make_icon_label("fa6s.stopwatch", "Average Time: 0 ms")
        longest_time_widget, self.label_longest_time = make_icon_label("fa6s.hourglass-end", "Longest Time: 0 ms")
        last_time_widget, self.label_last_time = make_icon_label("fa6s.clock-rotate-left", "Last Time: 0 ms")
        total_time_widget, self.label_total_time = make_icon_label("fa6s.calendar-check", "Total Time: 0 ms")
        time_stats_layout.addWidget(gen_time_widget)
        time_stats_layout.addWidget(avg_time_widget)
        time_stats_layout.addWidget(longest_time_widget)
        time_stats_layout.addWidget(last_time_widget)
        time_stats_layout.addWidget(total_time_widget)

        token_stats_layout = QVBoxLayout()
        token_stats_layout.setContentsMargins(0, 0, 0, 0)
        token_stats_layout.setSpacing(1)
        token_stats_layout.setAlignment(Qt.AlignTop)
        token_input_widget, self.label_token_input = make_icon_label("fa6s.right-to-bracket", "Token Input: 0")
        token_output_widget, self.label_token_output = make_icon_label("fa6s.right-from-bracket", "Token Output: 0")
        token_total_widget, self.label_token_total = make_icon_label("fa6s.coins", "Token Total: 0")
        token_stats_layout.addWidget(token_input_widget)
        token_stats_layout.addWidget(token_output_widget)
        token_stats_layout.addWidget(token_total_widget)

        self.reset_token_btn = QPushButton()
        self.reset_token_btn.setIcon(qta.icon("fa6s.rotate-right", color="#888"))
        self.reset_token_btn.setFixedSize(24, 24)
        self.reset_token_btn.setToolTip("Reset token stats")
        self.reset_token_btn.setCursor(Qt.PointingHandCursor)
        token_stats_layout.addWidget(self.reset_token_btn)

        hbox.addLayout(file_stats_layout)
        hbox.addSpacing(8)
        hbox.addLayout(time_stats_layout)
        hbox.addSpacing(8)
        hbox.addLayout(token_stats_layout)
        hbox.addStretch(1)

        main_vbox.addLayout(hbox)

        self._last_gen_time = 0
        self._avg_time = 0
        self._longest_time = 0
        self._last_time = 0
        self._total_time = 0

        self._donation_dialog_shown_token = False

        self.reset_token_btn.clicked.connect(self._reset_token_stats)

    def update_stats(self, total, selected, failed, success=0, draft=0):
        self.label_total.setText(f"Total Files: {total}")
        self.label_selected.setText(f"Selected: {selected}")
        self.label_failed.setText(f"Failed: {failed}")
        self.label_success.setText(f"Success: {success}")
        self.label_draft.setText(f"Draft: {draft}")

    def update_token_stats(self, token_input, token_output, token_total):
        self.label_token_input.setText(f"Token Input: {token_input}")
        self.label_token_output.setText(f"Token Output: {token_output}")
        self.label_token_total.setText(f"Token Total: {token_total}")
        if token_total >= 1_000_000:
            if not self._donation_dialog_shown_token and not is_donation_optout_today():
                self._donation_dialog_shown_token = True
                dialog = DonateDialog(self, show_not_today=True)
                dialog.setWindowTitle("Support the Development")
                label = dialog.findChild(QLabel)
                if label:
                    label.setText(
                        "Thank you for trusting Image Tea for your metadata needs!\n\n"
                        "You're awesome!\n\n"
                        "Image Tea is possible thanks to the support of users like you.\n"
                        "If you really love using Image Tea to generate metadata,\nconsider supporting its development!"
                    )
                dialog.exec()
        else:
            self._donation_dialog_shown_token = False

    def _format_time(self, ms):
        if ms >= 60000:
            return f"{ms/60000:.1f} m"
        elif ms >= 1000:
            return f"{ms/1000:.1f} s"
        else:
            return f"{ms} ms"

    def update_generation_times(self, gen_time_ms, avg_time_ms, longest_time_ms, last_time_ms):
        self.label_gen_time.setText(f"Generation Time: {self._format_time(gen_time_ms)}")
        self.label_avg_time.setText(f"Average Time: {self._format_time(avg_time_ms)}")
        self.label_longest_time.setText(f"Longest Time: {self._format_time(longest_time_ms)}")
        self.label_last_time.setText(f"Last Time: {self._format_time(last_time_ms)}")
        self._last_gen_time = gen_time_ms
        self._avg_time = avg_time_ms
        self._longest_time = longest_time_ms
        self._last_time = last_time_ms

    def update_total_time(self, total_time_ms):
        self.label_total_time.setText(f"Total Time: {self._format_time(total_time_ms)}")
        self._total_time = total_time_ms

    def get_last_generation_times(self):
        return {
            "generation_time": self._last_gen_time,
            "average_time": self._avg_time,
            "longest_time": self._longest_time,
            "last_time": self._last_time,
            "total_time": self._total_time
        }

    def _reset_token_stats(self):
        self.db.delete_all_api_tokens()
        self.label_token_input.setText("Token Input: 0")
        self.label_token_output.setText("Token Output: 0")
        self.label_token_total.setText("Token Total: 0")
        self._donation_dialog_shown_token = False
