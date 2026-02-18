from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QSizePolicy, QMessageBox, QFileDialog, QApplication
from PySide6.QtGui import QIcon, QGuiApplication, QColor
from PySide6.QtCore import Qt
import qtawesome as qta
from PySide6.QtCore import QObject, Signal, Slot, QTimer
import ast
import json
import csv
import os
import webbrowser
from datetime import datetime
from config import BASE_PATH
import re
import traceback

from ui.theme_system import theme

GEMINI_ERRORS = {
    "400": {
        "status": "INVALID_ARGUMENT",
        "description": "The request body is malformed or API key is invalid.",
        "example": "There is a typo, missing required field, or your API key is incorrect/expired.",
        "solution": "Check your API key validity and request format. Verify the API reference for correct format, examples, and supported versions. Regenerate API key if necessary."
    },
    "403": {
        "status": "PERMISSION_DENIED",
        "description": "Your API key doesn't have the required permissions.",
        "example": "You are using the wrong API key; you are trying to use a tuned model without going through proper authentication.",
        "solution": "Check that your API key is set and has the right access. Ensure proper authentication for tuned models."
    },
    "404": {
        "status": "NOT_FOUND",
        "description": "The requested resource wasn't found.",
        "example": "An image, audio, or video file referenced in your request was not found.",
        "solution": "Check if all parameters in your request are valid for your API version and that referenced files exist."
    },
    "429": {
        "status": "RESOURCE_EXHAUSTED",
        "description": "You've exceeded the rate limit.",
        "example": "You are sending too many requests per minute with the free tier Gemini API.",
        "solution": "Verify you are within the model's rate limit. Consider requesting a quota increase or slow down requests."
    },
    "500": {
        "status": "INTERNAL",
        "description": "An unexpected error occurred on Google's side.",
        "example": "Your input context is too long.",
        "solution": "Reduce your input context or temporarily switch to another model; retry later and report persistent issues to Google AI Studio."
    },
    "503": {
        "status": "UNAVAILABLE",
        "description": "The service may be temporarily overloaded or down.",
        "example": "The service is temporarily running out of capacity.",
        "solution": "Temporarily switch to another model or wait and retry. Report persistent issues via Google AI Studio feedback."
    },
    "504": {
        "status": "DEADLINE_EXCEEDED",
        "description": "The service is unable to finish processing within the deadline.",
        "example": "Your prompt (or context) is too large to be processed in time.",
        "solution": "Set a larger timeout in your client request or reduce the prompt/context size."
    }
}

OPENAI_ERRORS = {
        "401": {
            "status": "INVALID_AUTHENTICATION",
            "description": "Invalid authentication or API key provided.",
            "example": "Ensure the correct API key and requesting organization are being used.",
            "solution": "Verify the API key and organization; regenerate a key if necessary."
        },
        "403": {
            "status": "ACCESS_DENIED",
            "description": "Access to the API is forbidden from your account or region.",
            "example": "You may be accessing the API from an unsupported region or lack required permissions.",
            "solution": "Check region support and API permissions for your account/organization."
        },
        "429": {
            "status": "RATE_LIMIT_EXCEEDED",
            "description": "You are sending requests too quickly or have exhausted quota.",
            "example": "Too many requests per minute or monthly quota exhausted.",
            "solution": "Implement backoff/retry and review your quota/billing settings."
        },
        "500": {
            "status": "INTERNAL_ERROR",
            "description": "The server had an error while processing your request.",
            "example": "Issue on provider servers.",
            "solution": "Retry after a brief wait and contact support if the issue persists."
        },
        "503": {
            "status": "UNAVAILABLE",
            "description": "The engine is temporarily overloaded or slow to respond.",
            "example": "The engine is experiencing high traffic or capacity issues.",
            "solution": "Retry after a brief wait or switch to a different model."
        }
    }

OPENROUTER_ERRORS = {
    "400": {
        "status": "BAD_REQUEST",
        "description": "The server could not understand the request due to invalid syntax.",
        "example": "Review the request format and ensure it is correct.",
        "solution": "Check your request parameters and format according to OpenRouter API documentation."
    },
    "401": {
        "status": "UNAUTHORIZED",
        "description": "The request was not successful because it lacks valid authentication credentials.",
        "example": "Ensure the request includes the necessary authentication credentials and the API key is valid.",
        "solution": "Verify your API key and ensure it is correctly configured in the request headers."
    },
    "402": {
        "status": "INSUFFICIENT_CREDITS",
        "description": "Your account or API key has insufficient credits.",
        "example": "Add more credits and retry the request.",
        "solution": "Check your account balance and add credits to continue using the API."
    },
    "403": {
        "status": "MODERATION_FLAGGED",
        "description": "Your chosen model requires moderation and your input was flagged.",
        "example": "The content violated moderation policies.",
        "solution": "Review your input content and ensure it complies with moderation guidelines."
    },
    "408": {
        "status": "REQUEST_TIMEOUT",
        "description": "Your request timed out.",
        "example": "The request took too long to process.",
        "solution": "Reduce the complexity of your request or try again later."
    },
    "429": {
        "status": "RATE_LIMITED",
        "description": "You are being rate limited.",
        "example": "Too many requests sent in a short period.",
        "solution": "Implement request throttling and respect rate limits. Wait before retrying."
    },
    "502": {
        "status": "MODEL_DOWN",
        "description": "Your chosen model is down or we received an invalid response from it.",
        "example": "The model is temporarily unavailable or returned an error.",
        "solution": "Try switching to another model or wait and retry later."
    },
    "503": {
        "status": "NO_PROVIDER_AVAILABLE",
        "description": "There is no available model provider that meets your routing requirements.",
        "example": "No provider can handle your request at this time.",
        "solution": "Adjust your routing requirements or try again later when providers are available."
    }
}

GROQ_ERRORS = {
    "400": {
        "status": "BAD_REQUEST",
        "description": "The server could not understand the request due to invalid syntax.",
        "example": "Review the request format and ensure it is correct.",
        "solution": "Verify your request parameters match the API specification."
    },
    "401": {
        "status": "UNAUTHORIZED",
        "description": "The request was not successful because it lacks valid authentication credentials.",
        "example": "Ensure the request includes the necessary authentication credentials and the API key is valid.",
        "solution": "Check your API key and ensure it's correctly configured."
    },
    "403": {
        "status": "FORBIDDEN",
        "description": "The request is not allowed due to permission restrictions.",
        "example": "Ensure the request includes the necessary permissions to access the resource or your permissions are configured correctly.",
        "solution": "Verify your account permissions and ensure you have access to the requested resource."
    },
    "404": {
        "status": "NOT_FOUND",
        "description": "The requested resource could not be found.",
        "example": "Check the request URL and the existence of the resource.",
        "solution": "Verify the endpoint URL and ensure the resource exists."
    },
    "413": {
        "status": "REQUEST_ENTITY_TOO_LARGE",
        "description": "The request body is too large.",
        "example": "Please reduce the size of the request body.",
        "solution": "Reduce the input size or split your request into smaller chunks."
    },
    "422": {
        "status": "UNPROCESSABLE_ENTITY",
        "description": "The request was well-formed but could not be followed due to semantic errors or model hallucinations.",
        "example": "Verify the data provided for correctness and completeness or retry your request.",
        "solution": "Check your request data for semantic issues and ensure all required fields are valid."
    },
    "424": {
        "status": "FAILED_DEPENDENCY",
        "description": "The request failed because the dependent request failed.",
        "example": "This may occur when using Remote MCP in the case of authentication issues.",
        "solution": "Check dependencies and authentication, then retry the request."
    },
    "429": {
        "status": "TOO_MANY_REQUESTS",
        "description": "Too many requests were sent in a given timeframe.",
        "example": "Implement request throttling and respect rate limits.",
        "solution": "Wait before sending more requests and implement exponential backoff."
    },
    "498": {
        "status": "FLEX_TIER_CAPACITY_EXCEEDED",
        "description": "Custom status code - the flex tier is at capacity and the request won't be processed.",
        "example": "Try again later when capacity is available.",
        "solution": "Wait and retry later, or consider upgrading to a paid tier with guaranteed capacity."
    },
    "499": {
        "status": "REQUEST_CANCELLED",
        "description": "Custom status code used in logs to signify when the request is cancelled by the caller.",
        "example": "The request was intentionally cancelled.",
        "solution": "This is expected if you cancelled the request. No action needed unless unintentional."
    },
    "500": {
        "status": "INTERNAL_SERVER_ERROR",
        "description": "A generic error occurred on the server.",
        "example": "Try the request again later or contact support if the issue persists.",
        "solution": "Retry after a brief wait. If the error persists, contact Groq support."
    },
    "502": {
        "status": "BAD_GATEWAY",
        "description": "The server received an invalid response from an upstream server.",
        "example": "This may be a temporary issue, retrying the request might resolve it.",
        "solution": "Wait and retry. This is usually a temporary issue with upstream services."
    },
    "503": {
        "status": "SERVICE_UNAVAILABLE",
        "description": "The server is not ready to handle the request, often due to maintenance or overload.",
        "example": "Wait before retrying the request.",
        "solution": "Wait a few minutes and retry. The service may be under maintenance or experiencing high load."
    }
}

MAIA_ERRORS = {
    "400": {
        "status": "BAD_REQUEST",
        "description": "The server could not understand the request due to invalid syntax.",
        "example": "Review the request format and ensure it is correct.",
        "solution": "Check your request parameters and format according to MAIA Router API documentation."
    },
    "401": {
        "status": "UNAUTHORIZED",
        "description": "Invalid authentication or API key provided.",
        "example": "Ensure the correct API key is being used.",
        "solution": "Verify your API key at https://dash.maiarouter.ai/dashboard/api-keys and regenerate if necessary."
    },
    "402": {
        "status": "INSUFFICIENT_CREDITS",
        "description": "Your account has insufficient credits.",
        "example": "Add more credits and retry the request.",
        "solution": "Check your account balance at MAIA Router dashboard and add credits."
    },
    "429": {
        "status": "RATE_LIMITED",
        "description": "You are being rate limited.",
        "example": "Too many requests sent in a short period.",
        "solution": "Implement request throttling and respect rate limits. Wait before retrying."
    },
    "500": {
        "status": "INTERNAL_SERVER_ERROR",
        "description": "An unexpected error occurred on the server.",
        "example": "Issue on MAIA Router servers.",
        "solution": "Retry after a brief wait. Contact cs@maiarouter.ai if the issue persists."
    },
    "502": {
        "status": "BAD_GATEWAY",
        "description": "The server received an invalid response from an upstream model provider.",
        "example": "The upstream model is temporarily unavailable.",
        "solution": "Try switching to another model or wait and retry later."
    },
    "503": {
        "status": "SERVICE_UNAVAILABLE",
        "description": "The service is temporarily overloaded or down.",
        "example": "The service is experiencing high traffic.",
        "solution": "Wait a few minutes and retry. The service may be under maintenance or experiencing high load."
    }
}

PREDEFINED_ERRORS = {}
for k, v in GEMINI_ERRORS.items():
    PREDEFINED_ERRORS[k] = v
for k, v in OPENAI_ERRORS.items():
    if k not in PREDEFINED_ERRORS:
        PREDEFINED_ERRORS[k] = v
for k, v in OPENROUTER_ERRORS.items():
    if k not in PREDEFINED_ERRORS:
        PREDEFINED_ERRORS[k] = v
for k, v in GROQ_ERRORS.items():
    if k not in PREDEFINED_ERRORS:
        PREDEFINED_ERRORS[k] = v
for k, v in MAIA_ERRORS.items():
    if k not in PREDEFINED_ERRORS:
        PREDEFINED_ERRORS[k] = v

def parse_api_error(message):
    try:
        parsed = None
        try:
            parsed = ast.literal_eval(message)
        except Exception:
            parsed = None
        if not parsed:
            m = re.search(r"(\{\s*\"?error\"?[\s\S]*\})", message)
            if m:
                js = m.group(1)
                js2 = js.replace("'", '"')
                try:
                    parsed = json.loads(js2)
                except Exception:
                    parsed = None
        if isinstance(parsed, dict):
            return parsed
        return {}
    except Exception as e:
        print(f"[Dialog Error Parse] {e}")
        return {}

class AIHelperErrorCodeDialog(QDialog):
    def __init__(self, error_code: str, message: str, parent=None, status: str = None, filenames=None, file_map=None, error_code_map=None, service='gemini'):
        super().__init__(parent)
        self.setWindowTitle("Error Report")
        self.setModal(True)
        self.setMinimumWidth(560)
        
        self._error_code_map = error_code_map or {}
        self._filenames = filenames or []
        self._should_auto_select = False
        self._service = service

        layout = QVBoxLayout(self)

        top = QHBoxLayout()

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon('fa6s.triangle-exclamation', color=theme.get_color('warning')).pixmap(28, 28))
        icon_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        top.addWidget(icon_lbl)

        title_lbl = QLabel("Generation Error Report")
        title_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_lbl.setStyleSheet('font-weight: 700; font-size: 16px;')

        try:
            count = len(filenames) if filenames else 0
        except Exception:
            count = 0
        summary_parts = []
        if error_code is not None:
            summary_parts.append(str(error_code))
        if status:
            summary_parts.append(str(status))
        if count:
            summary_parts.append(f"{count} file(s) affected")
        summary_text = " \u00B7 ".join(summary_parts) if summary_parts else "Error"

        summary_lbl = QLabel(summary_text)
        summary_lbl.setStyleSheet(f'color: {theme.get_color("text_dark")}; font-size: 12px;')
        summary_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        vtitle = QVBoxLayout()
        vtitle.addWidget(title_lbl)
        vtitle.addWidget(summary_lbl)
        top.addLayout(vtitle)
        top.addStretch()
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ts_lbl = QLabel(now)
            ts_lbl.setStyleSheet(f'color: {theme.get_color("text_dark")}; font-size: 11px;')
            ts_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            top.addWidget(ts_lbl)
        except Exception as e:
            print(f"[Dialog Timestamp Error] {e}")
        layout.addLayout(top)

        code_key = str(error_code) if error_code is not None else ''
        provided_status = status
        entries = []
        
        # Select error definitions based on service
        svc = (self._service or '').lower()
        if svc == 'gemini':
            error_definitions = GEMINI_ERRORS
        elif svc == 'openai':
            error_definitions = OPENAI_ERRORS
        elif svc == 'openrouter':
            error_definitions = OPENROUTER_ERRORS
        elif svc == 'groq':
            error_definitions = GROQ_ERRORS
        elif svc == 'maia':
            error_definitions = MAIA_ERRORS
        elif svc in ('custom', 'custom endpoint'):
            # For custom endpoints, show the aggregated/predefined lookup table
            error_definitions = PREDEFINED_ERRORS
        else:
            error_definitions = PREDEFINED_ERRORS
        
        if self._error_code_map and filenames:
            first_file = filenames[0]
            first_error_code = self._error_code_map.get(first_file)
            if first_error_code and first_error_code in error_definitions:
                code_key = str(first_error_code)
                ent = error_definitions.get(code_key)
                if ent:
                    entries = [ent]
                    print(f"[Dialog] Auto-loading initial details from first file: {first_file} (error {first_error_code}, service: {self._service})")
        elif code_key and code_key in error_definitions:
            ent = error_definitions.get(code_key)
            if ent:
                entries = [ent]

        api_info = parse_api_error(message)
        self._aggregated_message = message or ""

        self._file_map = file_map or {}
        if filenames:
            try:
                table_lbl = QLabel("Error recap:")
                layout.addWidget(table_lbl)
                self.table = QTableWidget()
                self.table.setColumnCount(2)
                self.table.setHorizontalHeaderLabels(["Filename", "Error Code"])
                self.table.setRowCount(len(filenames))
                self.table.setMinimumHeight(220)
                self.table.setMaximumHeight(400)
                self.table.setSelectionBehavior(QTableWidget.SelectRows)
                for i, fn in enumerate(filenames):
                    self.table.setItem(i, 0, QTableWidgetItem(fn))
                    file_error_code = self._error_code_map.get(fn, str(error_code))
                    self.table.setItem(i, 1, QTableWidgetItem(str(file_error_code)))
                header = self.table.horizontalHeader()
                header.setSectionResizeMode(0, QHeaderView.Stretch)
                header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
                self.table.cellClicked.connect(self._on_table_click)
                layout.addWidget(self.table)

                instr = QLabel("Click a table row to view the error details. Use 'Export CSV' to save a report file you can share when asking for help in community channels.")
                instr.setWordWrap(True)
                instr.setStyleSheet(f'color: {theme.get_color("text_dark")}; font-size: 12px;')
                layout.addWidget(instr)

                cfg_path = os.path.join(BASE_PATH, 'configs', 'app_config.json')
                print(f"[Dialog Config] Loading app_config.json from: {cfg_path}")
                with open(cfg_path, 'r', encoding='utf-8') as cf:
                    cfg = json.load(cf)
                self._wa_link = cfg['links']['whatsapp']
            except Exception as e:
                print(f"[Dialog Table Error] {e}")

        self.error_label = None
        self.status_label = None
        self.description_label = None
        self.example_label = None
        self.solution_label = None
        
        if self._error_code_map or entries:
            detail_frame = QFrame()
            detail_frame.setFrameShape(QFrame.StyledPanel)
            detail_layout = QVBoxLayout(detail_frame)
            detail_layout.setContentsMargins(8, 8, 8, 8)
            
            error_row = QFrame()
            error_layout = QHBoxLayout(error_row)
            error_layout.setContentsMargins(4, 2, 4, 2)
            error_layout.setAlignment(Qt.AlignLeft)
            error_icon = QLabel()
            error_icon.setPixmap(qta.icon('fa6s.xmark', color=theme.get_color('error')).pixmap(14, 14))
            self.error_label = QLabel("Error : Loading...")
            self.error_label.setWordWrap(True)
            _err_q = QColor(theme.get_color('error'))
            _err_rgb = f"{_err_q.red()},{_err_q.green()},{_err_q.blue()}"
            self.error_label.setStyleSheet(f'background-color: rgba({_err_rgb},0.12); padding:6px; border-radius:4px;')
            self.error_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            error_layout.addWidget(error_icon)
            error_layout.addWidget(self.error_label)
            detail_layout.addWidget(error_row)
            
            status_row = QFrame()
            status_layout = QHBoxLayout(status_row)
            status_layout.setContentsMargins(4, 2, 4, 2)
            status_layout.setAlignment(Qt.AlignLeft)
            status_icon = QLabel()
            status_icon.setPixmap(qta.icon('fa6s.circle-info', color=theme.get_color('warning')).pixmap(14, 14))
            self.status_label = QLabel("Status : Loading...")
            self.status_label.setWordWrap(True)
            _warn_q = QColor(theme.get_color('warning'))
            _warn_rgb = f"{_warn_q.red()},{_warn_q.green()},{_warn_q.blue()}"
            self.status_label.setStyleSheet(f'background-color: rgba({_warn_rgb},0.12); padding:6px; border-radius:4px;')
            self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            status_layout.addWidget(status_icon)
            status_layout.addWidget(self.status_label)
            detail_layout.addWidget(status_row)
            
            desc_row = QFrame()
            desc_layout = QHBoxLayout(desc_row)
            desc_layout.setContentsMargins(4, 2, 4, 2)
            desc_layout.setAlignment(Qt.AlignLeft)
            desc_icon = QLabel()
            desc_icon.setPixmap(qta.icon('fa6s.book', color=theme.get_color('text_light')).pixmap(14, 14))
            self.description_label = QLabel("Description : Loading...")
            self.description_label.setWordWrap(True)
            _txt_q = QColor(theme.get_color('text_light'))
            _txt_rgb = f"{_txt_q.red()},{_txt_q.green()},{_txt_q.blue()}"
            self.description_label.setStyleSheet(f'background-color: rgba({_txt_rgb},0.12); padding:6px; border-radius:4px;')
            self.description_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            desc_layout.addWidget(desc_icon)
            desc_layout.addWidget(self.description_label)
            detail_layout.addWidget(desc_row)
            
            example_row = QFrame()
            example_layout = QHBoxLayout(example_row)
            example_layout.setContentsMargins(4, 2, 4, 2)
            example_layout.setAlignment(Qt.AlignLeft)
            example_icon = QLabel()
            example_icon.setPixmap(qta.icon('fa6s.clipboard', color=theme.get_color('text_light')).pixmap(14, 14))
            self.example_label = QLabel("Example : Loading...")
            self.example_label.setWordWrap(True)
            _txt_q2 = QColor(theme.get_color('text_light'))
            _txt_rgb2 = f"{_txt_q2.red()},{_txt_q2.green()},{_txt_q2.blue()}"
            self.example_label.setStyleSheet(f'background-color: rgba({_txt_rgb2},0.12); padding:6px; border-radius:4px;')
            self.example_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            example_layout.addWidget(example_icon)
            example_layout.addWidget(self.example_label)
            detail_layout.addWidget(example_row)
            
            solution_row = QFrame()
            solution_layout = QHBoxLayout(solution_row)
            solution_layout.setContentsMargins(4, 2, 4, 2)
            solution_layout.setAlignment(Qt.AlignLeft)
            solution_icon = QLabel()
            solution_icon.setPixmap(qta.icon('fa6s.circle-check', color=theme.get_color('success')).pixmap(14, 14))
            self.solution_label = QLabel("Solution : Loading...")
            self.solution_label.setWordWrap(True)
            _succ_q = QColor(theme.get_color('success'))
            _succ_rgb = f"{_succ_q.red()},{_succ_q.green()},{_succ_q.blue()}"
            self.solution_label.setStyleSheet(f'background-color: rgba({_succ_rgb},0.12); padding:6px; border-radius:4px;')
            self.solution_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            solution_layout.addWidget(solution_icon)
            solution_layout.addWidget(self.solution_label)
            detail_layout.addWidget(solution_row)
            
            layout.addWidget(detail_frame)

        if hasattr(self, 'table') and self.table.rowCount() > 0:
            self._should_auto_select = True
            print("[Dialog] Will auto-select first row after dialog is shown")
        elif entries and len(entries) > 0:
            entry = entries[0]
            print(f"[Dialog Init] Loading initial entry for error {code_key} (no table)")
            if self.error_label:
                self._update_error_labels(code_key, entry)

        raw_parts = []
        self._copy_text = ""

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        export_btn = QPushButton(qta.icon('fa6s.file-csv'), " Export CSV")
        export_btn.setToolTip("Export the table as CSV for reporting or community support")
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)

        wa_btn = QPushButton("Report Error")
        wa_btn.setIcon(qta.icon('fa6b.whatsapp', color=theme.get_color('success')))
        wa_btn.setToolTip("Report this error via WhatsApp")
        wa_btn.clicked.connect(self._report_via_whatsapp)
        btn_layout.addWidget(wa_btn)

        copy_btn = QPushButton("Copy")
        copy_btn.setIcon(qta.icon('fa6s.copy'))
        copy_btn.setToolTip("Copy current error details to clipboard")
        copy_btn.clicked.connect(self._copy)
        btn_layout.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setIcon(qta.icon('fa6s.xmark'))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def showEvent(self, event):
        """Override showEvent untuk auto-select row pertama dan center dialog"""
        super().showEvent(event)
        
        try:
            if self.parent():
                parent_geo = self.parent().geometry()
                self.move(
                    parent_geo.x() + (parent_geo.width() - self.width()) // 2,
                    parent_geo.y() + (parent_geo.height() - self.height()) // 2
                )
            else:
                screen = QApplication.primaryScreen().geometry()
                self.move(
                    (screen.width() - self.width()) // 2,
                    (screen.height() - self.height()) // 2
                )
        except Exception as e:
            print(f"[Dialog Center Error] {e}")
        
        if self._should_auto_select and hasattr(self, 'table'):
            try:
                QTimer.singleShot(150, self._do_auto_select)
            except Exception as e:
                print(f"[Dialog Auto-select Timer Error] {e}")
    
    def _do_auto_select(self):
        """Melakukan auto-select dan load detail dari row pertama"""
        try:
            if hasattr(self, 'table') and self.table.rowCount() > 0:
                self.table.selectRow(0)
                first_file = self._filenames[0] if self._filenames else None
                if first_file:
                    first_error_code = self._error_code_map.get(first_file)
                    if first_error_code:
                        self._on_table_click(0, 0)
                        print(f"[Dialog] Auto-selected and loaded details: {first_file} (error {first_error_code})")
                    else:
                        self._on_table_click(0, 0)
                        print(f"[Dialog] Auto-selected first row")
                else:
                    self._on_table_click(0, 0)
                    print(f"[Dialog] Auto-selected first row")
                self._should_auto_select = False
        except Exception as e:
            print(f"[Dialog Auto-select Execution Error] {e}")

    def _clear_layout(self, layout):
        try:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
        except Exception as e:
            print(f"[Dialog Layout Clear Error] {e}")
    
    def _update_error_labels(self, error_code, entry):
        """Update label text only, tidak rebuild widget"""
        try:
            print(f"[Dialog Update Labels] Updating for error {error_code}")
            
            if self.error_label:
                self.error_label.setText(f"Error : {error_code}")
            if self.status_label:
                self.status_label.setText(f"Status : {entry.get('status', 'N/A')}")
            if self.description_label:
                self.description_label.setText(f"Description : {entry.get('description', 'N/A')}")
            if self.example_label:
                self.example_label.setText(f"Example : {entry.get('example', 'N/A')}")
            if self.solution_label:
                self.solution_label.setText(f"Solution : {entry.get('solution', 'N/A')}")
            
            self._copy_text = f"""Error: {error_code}
Status: {entry.get('status', '')}
Description: {entry.get('description', '')}
Example: {entry.get('example', '')}
Solution: {entry.get('solution', '')}"""
            
            print(f"[Dialog Update Labels] Labels updated successfully")
        except Exception as e:
            print(f"[Dialog Update Labels Error] {e}")
            traceback.print_exc()

    def _render_parsed_message(self, message, target_layout):
        try:
            self._clear_layout(target_layout)
        except Exception as e:
            print(f"[Dialog Layout Clear Error] {e}")
        api_info = parse_api_error(message)
        if api_info:
            err = api_info.get('error') if isinstance(api_info, dict) else None
            if err and isinstance(err, dict):
                err_status = err.get('status') or err.get('code')
                err_msg = err.get('message')
                if err_status:
                    s = QLabel(f"API Status: {err_status}")
                    s.setWordWrap(True)
                    target_layout.addWidget(s)
                if err_msg:
                    mlabel = QLabel("API Message:")
                    target_layout.addWidget(mlabel)
                    msg_box = QTextEdit(err_msg)
                    msg_box.setReadOnly(True)
                    msg_box.setFixedHeight(120)
                    target_layout.addWidget(msg_box)

                details = err.get('details', [])
                links = []
                quota_lines = []
                retry_delay = None
                for d in details:
                    if isinstance(d, dict):
                        t = d.get('@type', '')
                        if 'Help' in t and isinstance(d.get('links'), list):
                            for l in d.get('links'):
                                if isinstance(l, dict) and l.get('url'):
                                    links.append((l.get('description') or l.get('url'), l.get('url')))
                        if 'QuotaFailure' in t and isinstance(d.get('violations'), list):
                            for v in d.get('violations'):
                                qmetric = v.get('quotaMetric')
                                qval = v.get('quotaValue')
                                quota_lines.append(f"{qmetric} -> limit {qval}")
                        if 'RetryInfo' in t and d.get('retryDelay'):
                            retry_delay = d.get('retryDelay')

                if quota_lines:
                    qlbl = QLabel("Quota details:")
                    qlbl.setWordWrap(True)
                    target_layout.addWidget(qlbl)
                    qtxt = QTextEdit("\n".join(quota_lines))
                    qtxt.setReadOnly(True)
                    qtxt.setFixedHeight(60)
                    target_layout.addWidget(qtxt)

                if retry_delay:
                    rlbl = QLabel(f"Retry after: {retry_delay}")
                    target_layout.addWidget(rlbl)

                if links:
                    links_lbl = QLabel("Helpful links:")
                    target_layout.addWidget(links_lbl)
                    for desc, url in links:
                        link_btn = QPushButton(desc)
                        link_btn.setFlat(True)
                        link_btn.clicked.connect(lambda _, u=url: webbrowser.open(u))
                        target_layout.addWidget(link_btn)

    def _on_table_click(self, row, column):
        try:
            item = self.table.item(row, 0)
            if not item:
                print(f"[Dialog Click] No item at row {row}")
                return
            
            fn = item.text()
            file_error_code = self._error_code_map.get(fn)
            if not file_error_code:
                try:
                    second_item = self.table.item(row, 1)
                    if second_item:
                        file_error_code = second_item.text()
                except Exception:
                    file_error_code = None

            print(f"[Dialog Click] File: {fn}, Error Code: {file_error_code}, Service: {self._service}")

            entry = None
            if file_error_code:
                entry = PREDEFINED_ERRORS.get(str(file_error_code))
                if entry:
                    self._update_error_labels(str(file_error_code), entry)
                    print(f"[Dialog Click] Updated labels for error {file_error_code} from PREDEFINED_ERRORS")
                else:
                    # Select appropriate error definitions based on service
                    if self._service == 'gemini':
                        error_definitions = GEMINI_ERRORS
                    elif self._service == 'openai':
                        error_definitions = OPENAI_ERRORS
                    elif self._service == 'openrouter':
                        error_definitions = OPENROUTER_ERRORS
                    elif self._service == 'groq':
                        error_definitions = GROQ_ERRORS
                    elif self._service == 'maia':
                        error_definitions = MAIA_ERRORS
                    else:
                        error_definitions = PREDEFINED_ERRORS
                    
                    entry = error_definitions.get(str(file_error_code))
                    if entry:
                        self._update_error_labels(str(file_error_code), entry)
                        print(f"[Dialog Click] Updated labels for error {file_error_code} from {self._service.upper()} definitions")
                    else:
                        print(f"[Dialog Click] No predefined error for code {file_error_code} in known definitions")
            else:
                print(f"[Dialog Click] No error code found for {fn}")

            self.table.selectRow(row)
            self.table.scrollToItem(self.table.item(row, 0))
            
        except Exception as e:
            print(f"[Dialog Table Click Error] {e}")
            traceback.print_exc()
    
    def _copy(self):
        try:
            QGuiApplication.clipboard().setText(self._copy_text)
        except Exception as e:
            print(f"[Dialog Copy Error] {e}")

    def _report_via_whatsapp(self):
        """Open the configured WhatsApp link in the default browser.

        Deterministic: no try/except; errors should surface to the console.
        """
        wa = self._wa_link
        webbrowser.open(wa)

    def _export_csv(self):
        """Show a Save File dialog and export the table details to the selected CSV file.
        """
        try:
            home = os.path.expanduser('~')
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_name = f"Image_Tea_AI_Generation_Error_Report_{ts}.csv"
            default_path = os.path.join(home, default_name)

            path, _ = QFileDialog.getSaveFileName(self, "Save Error Report", default_path, "CSV Files (*.csv);;All Files (*)")
            if not path:
                print("[Dialog Export] Save canceled by user")
                return

            if not path.lower().endswith('.csv'):
                path = path + '.csv'

            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Filename', 'Error Code', 'Status', 'Description', 'Example', 'Solution'])

                if hasattr(self, 'table'):
                    rows = self.table.rowCount()
                    for i in range(rows):
                        fn_item = self.table.item(i, 0)
                        ec_item = self.table.item(i, 1)
                        fn = fn_item.text() if fn_item else ''
                        ec = ec_item.text() if ec_item else ''

                        status = ''
                        description = ''
                        example = ''
                        solution = ''

                        try:
                            entry = PREDEFINED_ERRORS.get(str(ec)) if ec else None
                            if not entry:
                                if self._service == 'gemini':
                                    entry = GEMINI_ERRORS.get(str(ec)) if ec else None
                                elif self._service == 'openai':
                                    entry = OPENAI_ERRORS.get(str(ec)) if ec else None
                                elif self._service == 'openrouter':
                                    entry = OPENROUTER_ERRORS.get(str(ec)) if ec else None
                                elif self._service == 'groq':
                                    entry = GROQ_ERRORS.get(str(ec)) if ec else None
                                elif self._service == 'maia':
                                    entry = MAIA_ERRORS.get(str(ec)) if ec else None
                                else:
                                    entry = None

                            if isinstance(entry, dict):
                                status = entry.get('status', '')
                                description = entry.get('description', '')
                                example = entry.get('example', '')
                                solution = entry.get('solution', '')
                        except Exception as e:
                            print(f"[Dialog Export] Error looking up details for code {ec}: {e}")

                        writer.writerow([fn, ec, status, description, example, solution])

            print(f"[Dialog Export] Wrote CSV to {path}")
            try:
                QMessageBox.information(self, "Export Completed", f"Exported error report to:\n{path}")
            except Exception as e:
                print(f"[Dialog Export Notify Error] {e}")
        except Exception as e:
            print(f"[Dialog Export Error] {e}")
            try:
                QMessageBox.critical(self, "Export Failed", f"Failed to write CSV: {e}")
            except Exception as e2:
                print(f"[Dialog Export Critical Notify Error] {e2}")

class _DialogInvoker(QObject):
    showRequested = Signal(str, str, str, str)

    def __init__(self):
        super().__init__()
        self.showRequested.connect(self._on_show)
        self._buffer = {}
        self._timers = {}
        self._last_shown = {}
        self.buffering_enabled = True

    @Slot(str, str, str, str)
    def _on_show(self, signature, message, filename, service='gemini'):
        try:
            entry = self._buffer.get(signature)
            if not entry:
                entry = {'count': 0, 'messages': [], 'filenames': [], 'file_map': {}, 'service': service}
                self._buffer[signature] = entry
            else:
                if 'service' not in entry:
                    entry['service'] = service
            entry['count'] += 1
            if message not in entry['messages']:
                entry['messages'].append(message)
                if len(entry['messages']) > 10:
                    entry['messages'] = entry['messages'][:10]
            if filename:
                try:
                    if filename not in entry['filenames']:
                        entry['filenames'].append(filename)
                        if len(entry['filenames']) > 50:
                            entry['filenames'] = entry['filenames'][:50]
                    fmap = entry.setdefault('file_map', {})
                    arr = fmap.setdefault(filename, [])
                    if message not in arr:
                        arr.append(message)
                        if len(arr) > 20:
                            fmap[filename] = arr[:20]
                except Exception as e:
                    print(f"[Dialog Invoker Filemap Error] {e}")

            if signature not in self._timers and not self.buffering_enabled:
                def _flush(sig=signature):
                    try:
                        self._flush_signature(sig)
                    finally:
                        if sig in self._timers:
                            del self._timers[sig]

                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(_flush)
                self._timers[signature] = timer
                timer.start(1500)
        except Exception as e:
            print(f"[Dialog Invoker Show Error] {e}")

    def enable_buffering(self):
        self.buffering_enabled = True
        print("[Dialog Invoker] Buffering enabled - errors will be collected")

    def disable_buffering(self):
        self.buffering_enabled = False
        print("[Dialog Invoker] Buffering disabled")

    def flush_all(self):
        print(f"[Dialog Invoker] Flushing all buffered errors ({len(self._buffer)} signatures)")
        for timer in list(self._timers.values()):
            try:
                timer.stop()
            except Exception as e:
                print(f"[Dialog Timer Stop Error] {e}")
        self._timers.clear()
        
        signatures = list(self._buffer.keys())
        for sig in signatures:
            try:
                self._flush_signature(sig)
            except Exception as e:
                print(f"[Dialog Invoker] Error flushing signature {sig}: {e}")

    def clear_buffer(self):
        print("[Dialog Invoker] Clearing buffer")
        for timer in list(self._timers.values()):
            try:
                timer.stop()
            except Exception as e:
                print(f"[Dialog Timer Stop Error] {e}")
        self._timers.clear()
        self._buffer.clear()

    def _flush_signature(self, signature):
        try:
            entry = self._buffer.pop(signature, None)
            if not entry:
                return

            count = entry.get('count', 0)
            messages = entry.get('messages', [])
            service = entry.get('service', 'gemini')

            header = f"{count} occurrence(s) of this error were received."
            sample_header = "Sample messages (truncated):"
            samples = "\n\n".join(messages[:5]) if messages else ''
            aggregated = header + "\n\n" + sample_header + "\n" + samples

            code = signature
            status = None
            if '|' in signature:
                parts = signature.split('|', 1)
                code = parts[0]
                status = parts[1]

            parent = None
            try:
                parent = QApplication.activeWindow()
            except Exception:
                parent = None

            filenames = entry.get('filenames', [])
            file_map = entry.get('file_map', {})
            error_code_map = entry.get('error_code_map', {})
            dlg = AIHelperErrorCodeDialog(code, aggregated, parent, status=status, filenames=filenames, file_map=file_map, error_code_map=error_code_map, service=service)
            try:
                dlg.exec()
            except Exception as e:
                print(f"[Dialog Show Error] {e}")
        except Exception as e:
            print(f"[Dialog Invoker Flush Error] {e}")

invoker = _DialogInvoker()
try:
    app = QApplication.instance()
    if app is not None:
        try:
            invoker.moveToThread(app.thread())
        except Exception as e:
            print(f"[Dialog Invoker MoveToThread Error] {e}")
except Exception as e:
    print(f"[Dialog Invoker App Error] {e}")
