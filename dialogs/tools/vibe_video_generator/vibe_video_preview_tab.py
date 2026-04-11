import os
import re
import subprocess
import platform
import socket
import time
import urllib.request
import urllib.error
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QProgressBar
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
import qtawesome as qta

TOOLS_NODEJS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'tools', 'nodejs')
PROJECT_TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'temp')


def _find_npx_cmd() -> list[str] | None:
    import shutil
    if platform.system() == 'Windows':
        for root, dirs, files in os.walk(TOOLS_NODEJS):
            if 'npx.cmd' in files:
                return [os.path.join(root, 'npx.cmd')]
    for root, dirs, files in os.walk(TOOLS_NODEJS):
        if 'npx' in files:
            return [os.path.join(root, 'npx')]
    found = shutil.which('npx')
    return [found] if found else None


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if port is accessible (TCP connection test)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _wait_for_server(host: str, port: int, timeout: float = 30.0, interval: float = 0.5) -> bool:
    """Wait until HTTP server is accessible by making HTTP requests."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Try HTTP request to root path
            url = f'http://{host}:{port}/'
            req = urllib.request.Request(url, method='HEAD')
            req.timeout = interval
            with urllib.request.urlopen(req) as response:
                return True
        except urllib.error.HTTPError:
            # HTTP error but server responded = server is running
            return True
        except Exception:
            # Server not ready yet, wait a bit
            time.sleep(interval)
    return False


def _health_check_server(host: str, port: int) -> tuple[bool, str]:
    """Perform complete health check on Remotion server."""
    # Step 1: Check TCP connection
    if not _is_port_open(host, port):
        return False, f"Port {port} is not accessible (connection refused)"

    # Step 2: Check HTTP response
    try:
        url = f'http://{host}:{port}/'
        req = urllib.request.Request(url, method='GET')
        req.timeout = 5.0
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            if status == 200:
                return True, f"Server healthy (HTTP {status})"
            else:
                return True, f"Server responding (HTTP {status})"
    except urllib.error.HTTPError as e:
        # HTTP error but server responded
        return True, f"Server responding (HTTP {e.code})"
    except Exception as e:
        return False, f"HTTP check failed: {str(e)}"


class PreviewServerWorker(QThread):
    server_ready = Signal(int)
    server_failed = Signal(str)
    status_update = Signal(str)

    def __init__(self, preview_dir, port):
        super().__init__()
        self._preview_dir = preview_dir
        self._port = port
        self._proc = None

    def run(self):
        npx_cmd = _find_npx_cmd()
        if not npx_cmd:
            self.server_failed.emit('npx not found')
            return

        # Validate preview directory
        if not os.path.exists(self._preview_dir):
            self.server_failed.emit(f'Preview directory not found: {self._preview_dir}')
            return

        entry_file = os.path.join('src', 'index.tsx')
        full_entry_path = os.path.join(self._preview_dir, entry_file)
        if not os.path.exists(full_entry_path):
            self.server_failed.emit(f'Entry file not found: {full_entry_path}')
            return

        # Check if port is already in use
        self.status_update.emit(f'Checking port {self._port}...')
        if _is_port_open('localhost', self._port, timeout=0.5):
            self.server_failed.emit(f'Port {self._port} is already in use')
            return

        env = os.environ.copy()
        node_bin = None
        for root, dirs, files in os.walk(TOOLS_NODEJS):
            for name in ['node.exe', 'node']:
                if name in files:
                    node_bin = root
                    break
            if node_bin:
                break
        if node_bin:
            env['PATH'] = node_bin + os.pathsep + env.get('PATH', '')
        env['NODE_ENV'] = 'development'

        cmd = npx_cmd + ['remotion', 'studio', entry_file, '--port', str(self._port), '--no-open']
        print(f'[Remotion Studio] Starting with command: {" ".join(cmd)}')
        print(f'[Remotion Studio] Working directory: {self._preview_dir}')

        try:
            flags = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            self._proc = subprocess.Popen(
                cmd,
                cwd=self._preview_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=flags
            )

            server_started = False
            process_exited_early = False

            # Read output and wait for signal from stdout
            if self._proc.stdout is None:
                self.server_failed.emit('Process stdout is None')
                return

            for line in self._proc.stdout:
                clean = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', line).strip()
                if clean:
                    print(f'[Remotion Studio] {clean}')

                # Check if process is still running
                if self._proc.poll() is not None:
                    process_exited_early = True
                    break

                # Detect server ready from output
                if ('Server listening on' in line or
                    'studio is running' in line.lower() or
                    f':{self._port}' in line):
                    server_started = True
                    break

            if process_exited_early:
                returncode = self._proc.poll()
                self.server_failed.emit(f'Remotion process exited early with code {returncode}')
                return

            if server_started:
                # Wait until server is actually accessible via HTTP
                self.status_update.emit(f'Waiting for server on port {self._port}...')
                print(f'[Remotion Studio] Waiting for server to be accessible on port {self._port}...')
                if _wait_for_server('localhost', self._port, timeout=30.0):
                    # Perform final health check
                    self.status_update.emit('Performing health check...')
                    healthy, msg = _health_check_server('localhost', self._port)
                    if healthy:
                        print(f'[Remotion Studio] Health check passed: {msg}')
                        self.server_ready.emit(self._port)
                    else:
                        self.server_failed.emit(f'Server started but health check failed: {msg}')
                else:
                    self.server_failed.emit(f'Server reported ready but not accessible on port {self._port} after 30s')
            else:
                # If stdout loop finished without detecting server ready
                if self._proc.poll() is None:
                    # Process still running, try health check
                    self.status_update.emit('Checking server status...')
                    print(f'[Remotion Studio] Process still running, attempting health check...')
                    if _wait_for_server('localhost', self._port, timeout=10.0):
                        healthy, msg = _health_check_server('localhost', self._port)
                        if healthy:
                            print(f'[Remotion Studio] Health check passed: {msg}')
                            self.server_ready.emit(self._port)
                        else:
                            self.server_failed.emit(f'Server running but health check failed: {msg}')
                    else:
                        self.server_failed.emit('Server not responding to health check')
                else:
                    returncode = self._proc.poll()
                    self.server_failed.emit(f'Remotion process exited with code {returncode}')

            # Drain remaining stdout
            if self._proc.stdout is not None:
                for line in self._proc.stdout:
                    pass

        except Exception as e:
            self.server_failed.emit(f'Failed to start: {str(e)}')

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                if platform.system() == 'Windows':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self._proc.pid)],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    self._proc.terminate()
                    self._proc.wait(timeout=5)
            except Exception as e:
                print(f'[Remotion Studio] Stop error: {e}')
            self._proc = None


class PreviewTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scripts_widget = None
        self._server_worker = None
        self._current_port = 3099
        self._server_running = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top toolbar with buttons only
        toolbar = QHBoxLayout()

        self.start_btn = QPushButton('Start Preview')
        self.start_btn.setIcon(qta.icon('fa6s.play'))
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start_preview)
        toolbar.addWidget(self.start_btn)

        self.stop_btn = QPushButton('Stop')
        self.stop_btn.setIcon(qta.icon('fa6s.stop'))
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_preview)
        toolbar.addWidget(self.stop_btn)

        self.reload_btn = QPushButton('Reload')
        self.reload_btn.setIcon(qta.icon('fa6s.rotate'))
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.setEnabled(False)
        self.reload_btn.clicked.connect(self._on_reload)
        toolbar.addWidget(self.reload_btn)

        self.open_browser_btn = QPushButton('Open in Browser')
        self.open_browser_btn.setIcon(qta.icon('fa6s.arrow-up-right-from-square'))
        self.open_browser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_browser_btn.setEnabled(False)
        self.open_browser_btn.clicked.connect(self._on_open_browser)
        toolbar.addWidget(self.open_browser_btn)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # Progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat('Starting Remotion Studio...')
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Placeholder label (shows status messages like health check)
        self.placeholder = QLabel('Click "Start Preview" to launch Remotion Studio in this panel.')
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.placeholder, 1)

        # Webview
        self.webview = QWebEngineView()
        settings = self.webview.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.webview.setVisible(False)
        layout.addWidget(self.webview, 1)

        # Status label below webview (script info, running status, errors)
        self.status_label = QLabel('No script loaded.')
        self.status_label.setStyleSheet('color: #666; padding: 4px;')
        layout.addWidget(self.status_label)

    def set_scripts_widget(self, scripts_widget):
        self._scripts_widget = scripts_widget
        scripts_widget.script_selected.connect(self._on_script_selected)

    def _on_script_selected(self, name):
        has_script = bool(name)
        self.start_btn.setEnabled(has_script)
        script_name = name if name else 'No script loaded.'
        self.status_label.setText(f'Script: {script_name}')
        was_running = self._server_running
        self._stop_server()
        self.webview.setUrl(QUrl('about:blank'))
        self.webview.setVisible(False)
        self.progress_bar.setVisible(False)
        self.placeholder.setVisible(True)
        self.placeholder.setText('Loading preview, please wait...' if was_running and has_script else 'Click "Start Preview" to launch Remotion Studio in this panel.')
        if was_running and has_script:
            QTimer.singleShot(500, self._on_start_preview)

    def _on_start_preview(self):
        if not self._scripts_widget:
            return
        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            return
        self._stop_server()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.reload_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.webview.setVisible(False)
        self.placeholder.setVisible(True)
        self.placeholder.setText('Preparing preview project...')

        try:
            from helpers.remotion_helper.remotion_helper import setup_preview_dir
            preview_dir, _ = setup_preview_dir(script_content)
        except Exception as e:
            self._reset_ui(f'Failed to prepare preview: {e}')
            return

        self._current_port = self._find_free_port(3099)
        self._server_worker = PreviewServerWorker(preview_dir, self._current_port)
        self._server_worker.server_ready.connect(self._on_server_ready)
        self._server_worker.server_failed.connect(self._on_server_failed)
        self._server_worker.status_update.connect(self._on_status_update)
        self._server_worker.start()
        self._server_running = True
        self.placeholder.setText(f'Starting Remotion Studio on port {self._current_port}...')

    def _on_status_update(self, message):
        self.placeholder.setText(message)

    def _on_server_ready(self, port):
        url = f'http://localhost:{port}'
        print(f'[Remotion Studio] Ready at {url}')
        self.progress_bar.setVisible(False)
        self.placeholder.setVisible(False)
        self.webview.setVisible(True)
        self.reload_btn.setEnabled(True)
        self.open_browser_btn.setEnabled(True)
        self.status_label.setText(f'Preview running at {url}')
        QTimer.singleShot(1500, lambda: self.webview.setUrl(QUrl(url)))

    def _on_server_failed(self, error):
        self._reset_ui(f'Studio failed: {error}')

    def _on_stop_preview(self):
        self._server_running = False
        self._stop_server()
        self._reset_ui('Preview stopped.')

    def _on_reload(self):
        self.webview.reload()

    def _on_open_browser(self):
        import webbrowser
        webbrowser.open(f'http://localhost:{self._current_port}')

    def _stop_server(self):
        self._server_running = False
        if self._server_worker:
            self._server_worker.stop()
            self._server_worker.quit()
            self._server_worker.wait(3000)
            self._server_worker = None
        from helpers.remotion_helper.remotion_helper import cleanup_preview_dir
        cleanup_preview_dir()

    def _reset_ui(self, status=''):
        self.start_btn.setEnabled(self._scripts_widget is not None and bool(
            self._scripts_widget.script_content.toPlainText().strip()))
        self.stop_btn.setEnabled(False)
        self.reload_btn.setEnabled(False)
        self.open_browser_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.webview.setVisible(False)
        self.webview.setUrl(QUrl('about:blank'))
        self.placeholder.setVisible(True)
        self.placeholder.setText(status or 'Click "Start Preview" to launch Remotion Studio in this panel.')
        self.status_label.setText(status or self.status_label.text())

    def _find_free_port(self, start=3099):
        import socket
        for port in range(start, start + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('localhost', port))
                    return port
                except OSError:
                    continue
        return start

    def closeEvent(self, event):
        self._stop_server()
        super().closeEvent(event)
