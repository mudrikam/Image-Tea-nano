from datetime import datetime
from PySide6.QtCore import QObject, Signal


class HolidayCalendarLogger(QObject):
    log_emitted = Signal(str, str)

    def __init__(self):
        super().__init__()

    def _emit(self, level: str, message: str):
        ts = datetime.now().strftime('%H:%M:%S')
        entry = f'[{ts}] [{level}] {message}'
        print(entry)
        self.log_emitted.emit(level, entry)

    def info(self, message: str):
        self._emit('INFO', message)

    def success(self, message: str):
        self._emit('SUCCESS', message)

    def warning(self, message: str):
        self._emit('WARNING', message)

    def error(self, message: str):
        self._emit('ERROR', message)

    def api(self, message: str):
        self._emit('API', message)

    def cache(self, message: str):
        self._emit('CACHE', message)


logger = HolidayCalendarLogger()
