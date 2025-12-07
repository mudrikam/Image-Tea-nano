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
    PREDEFINED_ERRORS[k] = v
for k, v in OPENAI_ERRORS.items():
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
        self._filenames = filenames or []
        self._should_auto_select = False

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
        
        # Jika ada error_code_map dan filenames, gunakan error code dari file pertama
        if self._error_code_map and filenames:
            first_file = filenames[0]
            first_error_code = self._error_code_map.get(first_file)
            if first_error_code and first_error_code in PREDEFINED_ERRORS:
                code_key = str(first_error_code)
                ent = PREDEFINED_ERRORS.get(code_key)
                if ent:
                    entries = [ent]
                    print(f"[Dialog] Auto-loading initial details from first file: {first_file} (error {first_error_code})")
        elif code_key and code_key in PREDEFINED_ERRORS:
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

        # ALWAYS create error detail section jika ada error_code_map atau entries
        # Widget dibuat sejak awal, hanya konten yang di-update
        self.error_label = None
        self.status_label = None
        self.description_label = None
        self.example_label = None
        self.solution_label = None
        
        if self._error_code_map or entries:
            # Buat frame untuk detail error (ALWAYS created, not conditional)
            detail_frame = QFrame()
            detail_frame.setFrameShape(QFrame.StyledPanel)
            detail_layout = QVBoxLayout(detail_frame)
            detail_layout.setContentsMargins(8, 8, 8, 8)
            
            # Error row
            error_row = QFrame()
            error_layout = QHBoxLayout(error_row)
            error_layout.setContentsMargins(4, 2, 4, 2)
            error_layout.setAlignment(Qt.AlignLeft)
            error_icon = QLabel()
            try:
                error_icon.setPixmap(qta.icon('fa6s.xmark', color='#ff6464').pixmap(14, 14))
            except Exception as e:
                print(f"[Dialog Icon Error] {e}")
            self.error_label = QLabel("Error : Loading...")
            self.error_label.setWordWrap(True)
            self.error_label.setStyleSheet('background-color: rgba(255,100,100,0.12); padding:6px; border-radius:4px;')
            self.error_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            error_layout.addWidget(error_icon)
            error_layout.addWidget(self.error_label)
            detail_layout.addWidget(error_row)
            
            # Status row
            status_row = QFrame()
            status_layout = QHBoxLayout(status_row)
            status_layout.setContentsMargins(4, 2, 4, 2)
            status_layout.setAlignment(Qt.AlignLeft)
            status_icon = QLabel()
            try:
                status_icon.setPixmap(qta.icon('fa6s.circle-info', color='#ffa500').pixmap(14, 14))
            except Exception as e:
                print(f"[Dialog Icon Error] {e}")
            self.status_label = QLabel("Status : Loading...")
            self.status_label.setWordWrap(True)
            self.status_label.setStyleSheet('background-color: rgba(255,165,0,0.12); padding:6px; border-radius:4px;')
            self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            status_layout.addWidget(status_icon)
            status_layout.addWidget(self.status_label)
            detail_layout.addWidget(status_row)
            
            # Description row
            desc_row = QFrame()
            desc_layout = QHBoxLayout(desc_row)
            desc_layout.setContentsMargins(4, 2, 4, 2)
            desc_layout.setAlignment(Qt.AlignLeft)
            desc_icon = QLabel()
            try:
                desc_icon.setPixmap(qta.icon('fa6s.book', color='#f0f0f0').pixmap(14, 14))
            except Exception as e:
                print(f"[Dialog Icon Error] {e}")
            self.description_label = QLabel("Description : Loading...")
            self.description_label.setWordWrap(True)
            self.description_label.setStyleSheet('background-color: rgba(240,240,240,0.12); padding:6px; border-radius:4px;')
            self.description_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            desc_layout.addWidget(desc_icon)
            desc_layout.addWidget(self.description_label)
            detail_layout.addWidget(desc_row)
            
            # Example row
            example_row = QFrame()
            example_layout = QHBoxLayout(example_row)
            example_layout.setContentsMargins(4, 2, 4, 2)
            example_layout.setAlignment(Qt.AlignLeft)
            example_icon = QLabel()
            try:
                example_icon.setPixmap(qta.icon('fa6s.clipboard', color='#dcdcdc').pixmap(14, 14))
            except Exception as e:
                print(f"[Dialog Icon Error] {e}")
            self.example_label = QLabel("Example : Loading...")
            self.example_label.setWordWrap(True)
            self.example_label.setStyleSheet('background-color: rgba(220,220,220,0.12); padding:6px; border-radius:4px;')
            self.example_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            example_layout.addWidget(example_icon)
            example_layout.addWidget(self.example_label)
            detail_layout.addWidget(example_row)
            
            # Solution row
            solution_row = QFrame()
            solution_layout = QHBoxLayout(solution_row)
            solution_layout.setContentsMargins(4, 2, 4, 2)
            solution_layout.setAlignment(Qt.AlignLeft)
            solution_icon = QLabel()
            try:
                solution_icon.setPixmap(qta.icon('fa6s.circle-check', color='#4bb64b').pixmap(14, 14))
            except Exception as e:
                print(f"[Dialog Icon Error] {e}")
            self.solution_label = QLabel("Solution : Loading...")
            self.solution_label.setWordWrap(True)
            self.solution_label.setStyleSheet('background-color: rgba(200,255,200,0.12); padding:6px; border-radius:4px;')
            self.solution_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            solution_layout.addWidget(solution_icon)
            solution_layout.addWidget(self.solution_label)
            detail_layout.addWidget(solution_row)
            
            layout.addWidget(detail_frame)
            
            # Jangan load di init, biarkan showEvent yang handle untuk consistency

        # Set flag untuk auto-select di showEvent (setelah dialog benar-benar ditampilkan)
        if hasattr(self, 'table') and self._error_code_map and self.table.rowCount() > 0:
            self._should_auto_select = True
            print("[Dialog] Will auto-select first row after dialog is shown")
        elif entries and len(entries) > 0:
            # Jika tidak ada tabel tapi ada entries, load langsung
            entry = entries[0]
            print(f"[Dialog Init] Loading initial entry for error {code_key} (no table)")
            if self.error_label:
                self._update_error_labels(code_key, entry)

        raw_parts = []
        self._copy_text = ""

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

    def showEvent(self, event):
        """Override showEvent untuk auto-select row pertama dan center dialog"""
        super().showEvent(event)
        
        # Center dialog di layar
        try:
            if self.parent():
                parent_geo = self.parent().geometry()
                self.move(
                    parent_geo.x() + (parent_geo.width() - self.width()) // 2,
                    parent_geo.y() + (parent_geo.height() - self.height()) // 2
                )
            else:
                from PySide6.QtWidgets import QApplication
                screen = QApplication.primaryScreen().geometry()
                self.move(
                    (screen.width() - self.width()) // 2,
                    (screen.height() - self.height()) // 2
                )
        except Exception as e:
            print(f"[Dialog Center Error] {e}")
        
        # Auto-select row pertama setelah dialog ditampilkan
        if self._should_auto_select and hasattr(self, 'table'):
            try:
                from PySide6.QtCore import QTimer
                # Delay sedikit untuk memastikan UI sudah ter-render penuh
                QTimer.singleShot(50, self._do_auto_select)
            except Exception as e:
                print(f"[Dialog Auto-select Timer Error] {e}")
    
    def _do_auto_select(self):
        """Melakukan auto-select dan load detail dari row pertama"""
        try:
            if hasattr(self, 'table') and self.table.rowCount() > 0:
                self.table.selectRow(0)
                # Trigger click event untuk load detail
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
            
            # Update copy text
            self._copy_text = f"""Error: {error_code}
Status: {entry.get('status', '')}
Description: {entry.get('description', '')}
Example: {entry.get('example', '')}
Solution: {entry.get('solution', '')}"""
            
            print(f"[Dialog Update Labels] Labels updated successfully")
        except Exception as e:
            print(f"[Dialog Update Labels Error] {e}")
            import traceback
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
            
            print(f"[Dialog Click] File: {fn}, Error Code: {file_error_code}")
            
            if file_error_code:
                entry = PREDEFINED_ERRORS.get(str(file_error_code))
                if entry:
                    # Hanya update label text, tidak rebuild widget
                    self._update_error_labels(str(file_error_code), entry)
                    print(f"[Dialog Click] Updated labels for error {file_error_code}")
                else:
                    print(f"[Dialog Click] No predefined error for code {file_error_code}")
            else:
                print(f"[Dialog Click] No error code found for {fn}")
                
            # Select row
            self.table.selectRow(row)
            self.table.scrollToItem(self.table.item(row, 0))
            
        except Exception as e:
            print(f"[Dialog Table Click Error] {e}")
            import traceback
            traceback.print_exc()
    
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
        self.buffering_enabled = False

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
            except Exception:
                pass
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
            except Exception:
                pass
        self._timers.clear()
        self._buffer.clear()

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
