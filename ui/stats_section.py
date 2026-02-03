from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtGui import QFont
from dialogs.donation_dialog import DonateDialog, is_donation_optout_today
import qtawesome as qta
from PySide6.QtCore import Qt, QTimer
import time
from datetime import datetime, timedelta
from .theme_system import theme

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
        label_color = theme.get_color('text_dark')

        def make_icon_label(icon_name, text):
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon(icon_name, color=theme.get_color('gray')).pixmap(12, 12))
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
        file_total_widget, self.label_total = make_icon_label("fa6s.database", "Total Files: 0")
        file_selected_widget, self.label_selected = make_icon_label("fa6s.check-double", "Selected: 0")
        file_failed_widget, self.label_failed = make_icon_label("fa6s.triangle-exclamation", "Failed: 0")
        file_success_widget, self.label_success = make_icon_label("fa6s.circle-check", "Success: 0")
        file_draft_widget, self.label_draft = make_icon_label("fa6s.file-pen", "Draft: 0")
        file_stats_layout.addWidget(file_total_widget)
        file_stats_layout.addWidget(file_selected_widget)
        file_stats_layout.addWidget(file_failed_widget)
        file_stats_layout.addWidget(file_success_widget)
        file_stats_layout.addWidget(file_draft_widget)

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

        self.reset_token_btn = QPushButton("Reset")
        self.reset_token_btn.setIcon(qta.icon("fa6s.rotate-right", color=theme.get_color('gray')))
        self.reset_token_btn.setToolTip("Reset token stats")
        self.reset_token_btn.setCursor(Qt.PointingHandCursor)
        token_stats_layout.addWidget(self.reset_token_btn)

        estimation_stats_layout = QVBoxLayout()
        estimation_stats_layout.setContentsMargins(0, 0, 0, 0)
        estimation_stats_layout.setSpacing(1)
        estimation_stats_layout.setAlignment(Qt.AlignTop)
        elapsed_time_widget, self.label_elapsed_time = make_icon_label("fa6s.hourglass-start", "Elapsed Time: 0 ms")
        remaining_time_widget, self.label_remaining_time = make_icon_label("fa6s.hourglass-half", "Remaining Time: ~ 0 ms")
        eta_widget, self.label_eta = make_icon_label("fa6s.clock", "ETA: --:--")
        progress_widget, self.label_progress = make_icon_label("fa6s.chart-line", "Progress: 0.0%")
        speed_widget, self.label_speed = make_icon_label("fa6s.gauge-high", "Speed: 0 files/min")
        estimation_stats_layout.addWidget(elapsed_time_widget)
        estimation_stats_layout.addWidget(remaining_time_widget)
        estimation_stats_layout.addWidget(eta_widget)
        estimation_stats_layout.addWidget(progress_widget)
        estimation_stats_layout.addWidget(speed_widget)

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

        hbox.addLayout(file_stats_layout)
        hbox.addSpacing(8)
        hbox.addLayout(token_stats_layout)
        hbox.addSpacing(8)
        hbox.addLayout(estimation_stats_layout)
        hbox.addSpacing(8)
        hbox.addLayout(time_stats_layout)
        hbox.addStretch(1)

        main_vbox.addLayout(hbox)

        self._last_gen_time = 0
        self._avg_time = 0
        self._longest_time = 0
        self._last_time = 0
        self._total_time = 0

        # Estimation tracking variables
        self._generation_start_time = None  # When generate button is clicked
        self._current_total = 0
        self._current_success = 0
        self._current_failed = 0
        self._current_selected = 0
        self._processing_target = 0  # Total files being processed in current batch

        self._donation_dialog_shown_token = False

        self.reset_token_btn.clicked.connect(self._reset_token_stats)
        
        # Timer for real-time updates
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_estimation_stats)
        self._update_timer.setInterval(1000)  # Update every 1 second

    def start_generation_timer(self):
        """Start the elapsed time counter when generate button is clicked"""
        # Reset timer first to ensure fresh start
        self.reset_estimation_timer()
        
        # Start fresh generation timer
        self._generation_start_time = time.time()
        # Start the real-time update timer
        self._update_timer.start()

    def set_processing_target(self, target_count):
        """Set the total number of files that will be processed"""
        self._processing_target = target_count

    def update_stats(self, total, selected, failed, success=0, draft=0):
        self.label_total.setText(f"Total Files: {total}")
        self.label_selected.setText(f"Selected: {selected}")
        self.label_failed.setText(f"Failed: {failed}")
        self.label_success.setText(f"Success: {success}")
        self.label_draft.setText(f"Draft: {draft}")
        
        # Update tracking variables for estimation calculations
        self._current_total = total
        self._current_success = success
        self._current_failed = failed
        self._current_selected = selected
        
        # Update estimation stats in real-time
        self._update_estimation_stats()

    def _update_estimation_stats(self):
        # Calculate elapsed time since generate button was clicked
        if self._generation_start_time is None:
            # Generation hasn't started yet
            self.label_elapsed_time.setText("Elapsed Time: 0 ms")
            self.label_remaining_time.setText("Remaining Time: ~ 0 ms")
            self.label_eta.setText("ETA: --:--")
            self.label_progress.setText("Progress: 0.0%")
            self.label_speed.setText("Speed: 0 files/min")
            return
        
        current_time = time.time()
        elapsed_time_seconds = current_time - self._generation_start_time
        elapsed_time_ms = elapsed_time_seconds * 1000
        
        # Calculate progress: completed files (success + failed) out of total files to process
        completed_files = self._current_success + self._current_failed
        total_files_to_process = self._processing_target if self._processing_target > 0 else self._current_selected
        remaining_files = max(0, total_files_to_process - completed_files)
        
        # Calculate progress percentage: completed / total * 100
        if total_files_to_process > 0:
            progress_percentage = (completed_files / total_files_to_process) * 100
        else:
            progress_percentage = 0.0
        
        # Ensure progress doesn't exceed 100%
        progress_percentage = min(100.0, progress_percentage)
        
        # Calculate remaining time using last generation time
        remaining_time_ms = 0
        if remaining_files > 0 and self._last_time > 0:
            # Use last generation time to estimate remaining time
            remaining_time_ms = remaining_files * self._last_time
        
        # Calculate speed (files per minute) based on completed files and elapsed time
        speed_files_per_min = 0
        if completed_files > 0 and elapsed_time_seconds > 0:
            files_per_second = completed_files / elapsed_time_seconds
            speed_files_per_min = files_per_second * 60
        
        # Calculate ETA based on remaining time
        eta_text = "--:--"
        if remaining_files <= 0:
            # All files completed
            eta_text = "Complete"
        elif remaining_time_ms > 0:
            try:
                # Convert remaining time to seconds and add to current time
                remaining_seconds = remaining_time_ms / 1000
                eta_datetime = datetime.now() + timedelta(seconds=remaining_seconds)
                eta_text = eta_datetime.strftime("%H:%M")
            except Exception as e:
                eta_text = "Calculating..."
        else:
            # No last time data available yet
            eta_text = "Calculating..."
        
        # Update labels with proper formatting
        self.label_elapsed_time.setText(f"Elapsed Time: {self._format_time(elapsed_time_ms)}")
        
        # Format remaining time properly
        if remaining_files <= 0:
            self.label_remaining_time.setText("Remaining Time: Complete")
        else:
            self.label_remaining_time.setText(f"Remaining Time: ~ {self._format_time(remaining_time_ms)}")
        
        self.label_eta.setText(f"ETA: {eta_text}")
        self.label_progress.setText(f"Progress: {progress_percentage:.1f}%")
        self.label_speed.setText(f"Speed: {speed_files_per_min:.1f} files/min")

    def reset_estimation_timer(self):
        """Reset the estimation timer to start fresh calculations"""
        self._generation_start_time = None
        self._processing_target = 0
        # Stop the real-time update timer
        self._update_timer.stop()
        
    def stop_estimation_timer(self):
        """Stop the estimation timer without resetting data"""
        # Only stop the timer, keep the data for display
        self._update_timer.stop()

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
        # Handle negative or zero values
        if ms <= 0:
            return "0 ms"
        
        # Convert to absolute value to handle any negative edge cases
        ms = abs(ms)
        
        if ms >= 3600000:  # 1 hour or more
            hours = ms / 3600000
            return f"{hours:.1f} h"
        elif ms >= 60000:  # 1 minute or more
            minutes = ms / 60000
            return f"{minutes:.1f} m"
        elif ms >= 1000:  # 1 second or more
            seconds = ms / 1000
            return f"{seconds:.1f} s"
        else:
            return f"{int(ms)} ms"

    def update_generation_times(self, gen_time_ms, avg_time_ms, longest_time_ms, last_time_ms):
        self.label_gen_time.setText(f"Generation Time: {self._format_time(gen_time_ms)}")
        self.label_avg_time.setText(f"Average Time: {self._format_time(avg_time_ms)}")
        self.label_longest_time.setText(f"Longest Time: {self._format_time(longest_time_ms)}")
        self.label_last_time.setText(f"Last Time: {self._format_time(last_time_ms)}")
        
        # Update internal tracking variables for estimation calculations
        self._last_gen_time = gen_time_ms
        self._avg_time = avg_time_ms
        self._longest_time = longest_time_ms
        self._last_time = last_time_ms  # This is used for remaining time estimation
        
        # Update estimation stats when new timing data arrives
        self._update_estimation_stats()

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

    def get_estimation_data(self):
        """Get current estimation statistics"""
        if self._generation_start_time is None:
            return {
                "elapsed_time": 0,
                "remaining_time": 0,
                "eta": None,
                "progress_percentage": 0.0,
                "speed_files_per_min": 0.0,
                "is_processing": False
            }
        
        current_time = time.time()
        elapsed_time_ms = (current_time - self._generation_start_time) * 1000
        completed_files = self._current_success + self._current_failed
        
        progress_percentage = 0.0
        total_files_to_process = self._processing_target if self._processing_target > 0 else self._current_selected
        if total_files_to_process > 0:
            progress_percentage = (completed_files / total_files_to_process) * 100
        
        speed_files_per_min = 0.0
        elapsed_seconds = elapsed_time_ms / 1000
        if elapsed_seconds > 0 and completed_files > 0:
            speed_files_per_min = (completed_files / elapsed_seconds) * 60
        
        return {
            "elapsed_time": elapsed_time_ms,
            "remaining_time": 0,  # This would need to be calculated based on current state
            "eta": None,
            "progress_percentage": progress_percentage,
            "speed_files_per_min": speed_files_per_min,
            "is_processing": True
        }

    def _reset_token_stats(self):
        self.db.delete_all_api_tokens()
        self.label_token_input.setText("Token Input: 0")
        self.label_token_output.setText("Token Output: 0")
        self.label_token_total.setText("Token Total: 0")
        self._donation_dialog_shown_token = False
