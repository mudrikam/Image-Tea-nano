import io
import json
import logging
import os
import re
import sys
import threading
from datetime import date
from logging.handlers import RotatingFileHandler

from config import BASE_PATH

LOG_FILE = os.path.join(BASE_PATH, "temp", "image_tea.log")
_CLEANUP_STATE = os.path.join(BASE_PATH, "temp", "log_cleanup_state.json")
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(module)s | %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3
_LOG_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


class StreamToLogger:
    def __init__(self, logger, level):
        self._logger = logger
        self._level = level
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, message):
        with self._lock:
            self._buffer += message
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                stripped = line.rstrip()
                if stripped:
                    self._logger.log(self._level, stripped)

    def flush(self):
        with self._lock:
            if self._buffer.strip():
                self._logger.log(self._level, self._buffer.rstrip())
                self._buffer = ""

    def isatty(self):
        return False

    @property
    def encoding(self):
        return "utf-8"

    @property
    def errors(self):
        return "replace"

    def fileno(self):
        raise io.UnsupportedOperation("fileno")


def _qt_message_handler(mode, context, message):
    from PySide6.QtCore import QtMsgType
    logger = logging.getLogger("Qt")
    _level_map = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    logger.log(_level_map.get(mode, logging.DEBUG), message)


def init_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    if root_logger.handlers:
        return

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.__stdout__)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)

    sys.stdout = StreamToLogger(logging.getLogger("stdout"), logging.INFO)
    sys.stderr = StreamToLogger(logging.getLogger("stderr"), logging.ERROR)

    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        root_logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _excepthook

    def _threading_excepthook(args):
        if args.exc_type is SystemExit:
            return
        root_logger.critical(
            "Uncaught exception in thread %s", args.thread,
            exc_info=(args.exc_type, args.exc_value, args.exc_tb),
        )

    threading.excepthook = _threading_excepthook

    try:
        from PySide6.QtCore import qInstallMessageHandler
        qInstallMessageHandler(_qt_message_handler)
    except Exception as e:
        root_logger.warning("Could not install Qt message handler: %s", e)

    _cleanup_old_logs()
    root_logger.info("Logging initialized. Log file: %s", LOG_FILE)


def _cleanup_old_logs():
    if not os.path.exists(LOG_FILE):
        return
    today = date.today().isoformat()
    if os.path.exists(_CLEANUP_STATE):
        try:
            with open(_CLEANUP_STATE, "r", encoding="utf-8") as f:
                state = json.load(f)
            if state.get("last_cleanup") == today:
                return
        except Exception:
            pass
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        kept = [line for line in lines
                if not (m := _LOG_DATE_RE.match(line)) or m.group(1) >= today]
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.writelines(kept)
    except Exception as e:
        print(f"[logging_helper] Log cleanup failed: {e}")
    try:
        with open(_CLEANUP_STATE, "w", encoding="utf-8") as f:
            json.dump({"last_cleanup": today}, f)
    except Exception:
        pass
