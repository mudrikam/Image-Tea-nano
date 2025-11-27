from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QSizePolicy
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtCore import Qt
import qtawesome as qta
from PySide6.QtCore import QObject, Signal, Slot, QTimer
import ast
import webbrowser
from datetime import datetime

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
PREDEFINED_ERRORS = {}
for k, v in GEMINI_ERRORS.items():
    # GEMINI_ERRORS entries are single dict objects now
    PREDEFINED_ERRORS[k] = v
for k, v in OPENAI_ERRORS.items():
    # If Gemini already defines this code prefer Gemini; otherwise use OpenAI mapping
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
            import re, json as _json
            m = re.search(r"(\{\s*\"?error\"?[\s\S]*\})", message)
            if m:
                js = m.group(1)
                js2 = js.replace("'", '"')
                try:
                    parsed = _json.loads(js2)
                except Exception:
                    parsed = None
        if isinstance(parsed, dict):
            return parsed
        return {}
    except Exception as e:
        print(f"[Dialog Error Parse] {e}")
        return {}

class AIHelperErrorCodeDialog(QDialog):
    def __init__(self, error_code: str, message: str, parent=None, status: str = None, filenames=None, file_map=None, error_code_map=None):
        super().__init__(parent)
        self.setWindowTitle("Error Report")
        self.setModal(True)
        self.setMinimumWidth(560)
        
        self._error_code_map = error_code_map or {}

        layout = QVBoxLayout(self)

        top = QHBoxLayout()

        icon_lbl = QLabel()
        try:
            icon_lbl.setPixmap(qta.icon('fa6s.triangle-exclamation', color='#FFD600').pixmap(28, 28))
        except Exception:
            icon_lbl.setText("!")
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
        summary_lbl.setStyleSheet('color: gray; font-size: 12px;')
        summary_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        vtitle = QVBoxLayout()
        vtitle.addWidget(title_lbl)
        vtitle.addWidget(summary_lbl)
        top.addLayout(vtitle)
        top.addStretch()
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ts_lbl = QLabel(now)
            ts_lbl.setStyleSheet('color: gray; font-size: 11px;')
            ts_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            top.addWidget(ts_lbl)
        except Exception:
            pass
        layout.addLayout(top)

        code_key = str(error_code) if error_code is not None else ''
        provided_status = status
        entries = []
        if code_key and code_key in PREDEFINED_ERRORS:
            ent = PREDEFINED_ERRORS.get(code_key)
            if ent:
                entries = [ent]

        api_info = parse_api_error(message)

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
            except Exception as e:
                print(f"[Dialog Table Error] {e}")

        self.detail_widget = None
        self.alert_frame = None
        self.alert_layout = None

        raw_parts = []
        if entries:
            entry = entries[0]
            try:
                self.alert_frame = QFrame()
                self.alert_frame.setFrameShape(QFrame.StyledPanel)
                self.alert_layout = QHBoxLayout(self.alert_frame)
                self.alert_layout.setContentsMargins(8, 8, 8, 8)

                a_right = QVBoxLayout()
                rows = [
                    ("Error : {}".format(code_key), 'fa6s.xmark', 'rgba(255,100,100,0.12)', '#ff6464'),
                    ("Status : {}".format(entry.get('status','')), 'fa6s.info-circle', 'rgba(255,165,0,0.12)', '#ffa500'),
                    ("Description : {}".format(entry.get('description','')), 'fa6s.book', 'rgba(240,240,240,0.12)', '#f0f0f0'),
                    ("Example : {}".format(entry.get('example','')), 'fa6s.clipboard', 'rgba(220,220,220,0.12)', '#dcdcdc'),
                    ("Solution : {}".format(entry.get('solution','')), 'fa6s.circle-check', 'rgba(200,255,200,0.12)', "#4bb64b")
                ]
                for text, icon_name, bg, icon_color in rows:
                    try:
                        row_widget = QFrame()
                        row_layout = QHBoxLayout(row_widget)
                        row_layout.setContentsMargins(4, 2, 4, 2)
                        row_layout.setAlignment(Qt.AlignLeft)
                        row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                        i_lbl = QLabel()
                        try:
                            i_lbl.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(14, 14))
                        except Exception:
                            # fallback to triangle icon if specific icon missing
                            i_lbl.setPixmap(qta.icon('fa6s.triangle-exclamation', color=icon_color).pixmap(14, 14))
                        txt_lbl = QLabel(text)
                        txt_lbl.setWordWrap(True)
                        # apply the requested semi-transparent color per label (non-white)
                        try:
                            txt_lbl.setStyleSheet(f'background-color: {bg}; padding:6px; border-radius:4px;')
                        except Exception:
                            pass
                        txt_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        txt_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                        row_layout.addWidget(i_lbl)
                        row_layout.addWidget(txt_lbl)
                        a_right.addWidget(row_widget)
                    except Exception as _e:
                        # on error fallback to plain label
                        l = QLabel(text)
                        l.setWordWrap(True)
                        a_right.addWidget(l)

                # make the alert frame expand to the available horizontal space
                self.alert_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                self.alert_layout.addLayout(a_right)
                layout.addWidget(self.alert_frame)

                # prepare copyable raw parts
                raw_parts.append(f"Error: {code_key}")
                raw_parts.append(f"Status: {entry.get('status','')}")
                raw_parts.append(f"Description: {entry.get('description','')}")
                raw_parts.append(f"Example: {entry.get('example','')}")
                raw_parts.append(f"Solution: {entry.get('solution','')}")
            except Exception as e:
                print(f"[Alert Render Error] {e}")

        raw_content = "\n".join(raw_parts)
        self._copy_text = raw_content

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        copy_btn = QPushButton("Copy")
        copy_btn.setIcon(qta.icon('fa6s.copy'))
        copy_btn.clicked.connect(self._copy)
        btn_layout.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setIcon(qta.icon('fa6s.xmark'))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _clear_layout(self, layout):
        try:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
        except Exception as e:
            print(f"[Dialog Layout Clear Error] {e}")

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
                return
            fn = item.text()
            msgs = self._file_map.get(fn, [])
            sample = msgs[0] if msgs else ''
            self._copy_text = sample
            
            # Simpan posisi scroll dan selected row sebelum update
            current_row = row
            
            # Update detail error sesuai error code file yang diklik
            file_error_code = self._error_code_map.get(fn)
            if file_error_code and self.alert_frame:
                self._update_error_details(str(file_error_code))
                # Pertahankan selection dan scroll position
                self.table.selectRow(current_row)
                self.table.scrollToItem(self.table.item(current_row, 0))
        except Exception as e:
            print(f"[Dialog Table Click Error] {e}")

    def _update_error_details(self, error_code):
        try:
            if not self.alert_layout:
                return
            
            # Simpan scroll position tabel sebelum clear layout
            vscroll = self.table.verticalScrollBar().value() if hasattr(self, 'table') else 0
            
            # Clear existing layout
            while self.alert_layout.count():
                item = self.alert_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    self._clear_layout(item.layout())
            
            # Get error details
            entry = PREDEFINED_ERRORS.get(str(error_code))
            if not entry:
                return
            
            # Rebuild detail layout
            a_right = QVBoxLayout()
            rows = [
                ("Error : {}".format(error_code), 'fa6s.xmark', 'rgba(255,100,100,0.12)', '#ff6464'),
                ("Status : {}".format(entry.get('status','')), 'fa6s.info-circle', 'rgba(255,165,0,0.12)', '#ffa500'),
                ("Description : {}".format(entry.get('description','')), 'fa6s.book', 'rgba(240,240,240,0.12)', '#f0f0f0'),
                ("Example : {}".format(entry.get('example','')), 'fa6s.clipboard', 'rgba(220,220,220,0.12)', '#dcdcdc'),
                ("Solution : {}".format(entry.get('solution','')), 'fa6s.circle-check', 'rgba(200,255,200,0.12)', "#4bb64b")
            ]
            for text, icon_name, bg, icon_color in rows:
                try:
                    row_widget = QFrame()
                    row_layout = QHBoxLayout(row_widget)
                    row_layout.setContentsMargins(4, 2, 4, 2)
                    row_layout.setAlignment(Qt.AlignLeft)
                    row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    i_lbl = QLabel()
                    try:
                        i_lbl.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(14, 14))
                    except Exception:
                        i_lbl.setPixmap(qta.icon('fa6s.triangle-exclamation', color=icon_color).pixmap(14, 14))
                    txt_lbl = QLabel(text)
                    txt_lbl.setWordWrap(True)
                    try:
                        txt_lbl.setStyleSheet(f'background-color: {bg}; padding:6px; border-radius:4px;')
                    except Exception:
                        pass
                    txt_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    txt_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    row_layout.addWidget(i_lbl)
                    row_layout.addWidget(txt_lbl)
                    a_right.addWidget(row_widget)
                except Exception:
                    l = QLabel(text)
                    l.setWordWrap(True)
                    a_right.addWidget(l)
            
            self.alert_layout.addLayout(a_right)
            
            # Restore scroll position tabel setelah update
            if hasattr(self, 'table'):
                self.table.verticalScrollBar().setValue(vscroll)
            
            # Update copy text
            raw_parts = [
                f"Error: {error_code}",
                f"Status: {entry.get('status','')}",
                f"Description: {entry.get('description','')}",
                f"Example: {entry.get('example','')}",
                f"Solution: {entry.get('solution','')}"
            ]
            self._copy_text = "\n".join(raw_parts)
        except Exception as e:
            print(f"[Dialog Update Details Error] {e}")
    
    def _copy(self):
        try:
            QGuiApplication.clipboard().setText(self._copy_text)
        except Exception as e:
            print(f"[Dialog Copy Error] {e}")

class _DialogInvoker(QObject):
    showRequested = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.showRequested.connect(self._on_show)
        self._buffer = {}
        self._timers = {}
        self._last_shown = {}

    @Slot(str, str, str)
    def _on_show(self, signature, message, filename):
        try:
            entry = self._buffer.get(signature)
            if not entry:
                entry = {'count': 0, 'messages': [], 'filenames': [], 'file_map': {}}
                self._buffer[signature] = entry
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

            if signature not in self._timers:
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

    def _flush_signature(self, signature):
        try:
            entry = self._buffer.pop(signature, None)
            if not entry:
                return

            count = entry.get('count', 0)
            messages = entry.get('messages', [])

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
                from PySide6.QtWidgets import QApplication
                parent = QApplication.activeWindow()
            except Exception:
                parent = None

            filenames = entry.get('filenames', [])
            file_map = entry.get('file_map', {})
            error_code_map = entry.get('error_code_map', {})
            dlg = AIHelperErrorCodeDialog(code, aggregated, parent, status=status, filenames=filenames, file_map=file_map, error_code_map=error_code_map)
            try:
                dlg.show()
                try:
                    dlg.raise_()
                    dlg.activateWindow()
                except Exception:
                    pass
            except Exception as e:
                print(f"[Dialog Show Error] {e}")
        except Exception as e:
            print(f"[Dialog Invoker Flush Error] {e}")

invoker = _DialogInvoker()
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        try:
            invoker.moveToThread(app.thread())
        except Exception as e:
            print(f"[Dialog Invoker MoveToThread Error] {e}")
except Exception as e:
    print(f"[Dialog Invoker App Error] {e}")
