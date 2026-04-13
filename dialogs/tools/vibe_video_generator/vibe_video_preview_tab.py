import os
import sys
import re
import subprocess
import platform
import socket
import time
import urllib.request
import urllib.error
import json
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


def _kill_process_on_port(port: int) -> bool:
    """Kill any process using the specified port."""
    try:
        if platform.system() == 'Windows':
            # Find PID using the port
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'tcp'],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        print(f'[Port Cleanup] Killing process {pid} using port {port}')
                        subprocess.run(
                            ['taskkill', '/F', '/T', '/PID', pid],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        return True
        return False
    except Exception as e:
        print(f'[Port Cleanup] Error killing process on port {port}: {e}')
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


class PlayerServerWorker(QThread):
    """Worker untuk menjalankan Remotion preview server (clean player only)."""
    server_ready = Signal(int)
    server_failed = Signal(str)
    status_update = Signal(str)

    def __init__(self, preview_dir, port, request_id=0):
        super().__init__()
        self._preview_dir = preview_dir
        self._port = port
        self._request_id = request_id
        self._proc = None

    def run(self):
        # Kill any existing process on this port first
        self.status_update.emit(f'Cleaning up port {self._port}...')
        _kill_process_on_port(self._port)
        time.sleep(0.5)  # Give time for port to be released

        # Check if port is already in use
        self.status_update.emit(f'Checking port {self._port}...')
        if _is_port_open('127.0.0.1', self._port, timeout=0.5):
            self.server_failed.emit(f'Port {self._port} is still in use after cleanup')
            return

        self.status_update.emit('Starting Remotion preview server...')
        print(f'[Player Server] Starting preview server on port {self._port}')

        entry_file = os.path.join('src', 'index.tsx')
        full_entry_path = os.path.join(self._preview_dir, entry_file)
        if not os.path.exists(full_entry_path):
            self.server_failed.emit(f'Entry file not found: {full_entry_path}')
            return

        try:
            flags = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            env = os.environ.copy()
            env['NODE_ENV'] = 'development'

            npx_cmd = _find_npx_cmd()
            if not npx_cmd:
                self.server_failed.emit('npx not found')
                return

            cmd = npx_cmd + ['remotion', 'preview', entry_file, '--port', str(self._port), '--host', '127.0.0.1', '--no-open']
            print(f'[Player Server] Command: {" ".join(cmd)}')
            print(f'[Player Server] Working directory: {self._preview_dir}')

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

            self.status_update.emit(f'Waiting for preview on port {self._port}...')
            if _wait_for_server('127.0.0.1', self._port, timeout=30.0):
                self.status_update.emit('Performing health check...')
                healthy, msg = _health_check_server('127.0.0.1', self._port)
                if healthy:
                    print(f'[Player Server] Health check passed: {msg}')
                    self.server_ready.emit(self._port)
                else:
                    self._cleanup_proc()
                    self.server_failed.emit(f'Server started but health check failed: {msg}')
                    return
            else:
                self._cleanup_proc()
                self.server_failed.emit(f'Preview server not accessible on port {self._port} after 30s')
                return

        except Exception as e:
            self._cleanup_proc()
            self.server_failed.emit(f'Failed to start preview server: {str(e)}')

    def _cleanup_proc(self):
        if self._proc and self._proc.poll() is None:
            try:
                if platform.system() == 'Windows':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self._proc.pid)],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    self._proc.terminate()
                    self._proc.wait(timeout=5)
            except Exception as e:
                print(f'[Player Server] Stop error: {e}')
        self._proc = None

    def stop(self):
        self._cleanup_proc()


class StudioServerWorker(QThread):
    """Worker untuk menjalankan full Remotion Studio (untuk Open in Browser)."""
    server_ready = Signal(int)
    server_failed = Signal(str)
    status_update = Signal(str)

    def __init__(self, preview_dir, port):
        super().__init__()
        self._preview_dir = preview_dir
        self._port = port
        self._proc = None

    def run(self):
        # Kill any existing process on this port first
        self.status_update.emit(f'Cleaning up port {self._port}...')
        _kill_process_on_port(self._port)
        time.sleep(0.5)  # Give time for port to be released

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
        if _is_port_open('127.0.0.1', self._port, timeout=0.5):
            self.server_failed.emit(f'Port {self._port} is still in use after cleanup')
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

        cmd = npx_cmd + ['remotion', 'studio', entry_file, '--port', str(self._port), '--host', '127.0.0.1', '--no-open']
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

            if self._proc.stdout is None:
                self._cleanup_proc()
                self.server_failed.emit('Process stdout is None')
                return

            for line in self._proc.stdout:
                clean = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', line).strip()
                if clean:
                    print(f'[Remotion Studio] {clean}')

                if self._proc.poll() is not None:
                    process_exited_early = True
                    break

                if ('Server listening on' in line or
                    'studio is running' in line.lower() or
                    f':{self._port}' in line):
                    server_started = True
                    break

            if process_exited_early:
                returncode = self._proc.poll()
                self._cleanup_proc()
                self.server_failed.emit(f'Remotion process exited early with code {returncode}')
                return

            if server_started:
                self.status_update.emit(f'Waiting for server on port {self._port}...')
                print(f'[Remotion Studio] Waiting for server to be accessible on port {self._port}...')
                if _wait_for_server('127.0.0.1', self._port, timeout=30.0):
                    self.status_update.emit('Performing health check...')
                    healthy, msg = _health_check_server('127.0.0.1', self._port)
                    if healthy:
                        print(f'[Remotion Studio] Health check passed: {msg}')
                        self.server_ready.emit(self._port)
                    else:
                        self._cleanup_proc()
                        self.server_failed.emit(f'Server started but health check failed: {msg}')
                        return
                else:
                    self._cleanup_proc()
                    self.server_failed.emit(f'Server reported ready but not accessible on port {self._port} after 30s')
                    return
            else:
                if self._proc.poll() is None:
                    self.status_update.emit('Checking server status...')
                    print(f'[Remotion Studio] Process still running, attempting health check...')
                    if _wait_for_server('127.0.0.1', self._port, timeout=10.0):
                        healthy, msg = _health_check_server('127.0.0.1', self._port)
                        if healthy:
                            print(f'[Remotion Studio] Health check passed: {msg}')
                            self.server_ready.emit(self._port)
                        else:
                            self._cleanup_proc()
                            self.server_failed.emit(f'Server running but health check failed: {msg}')
                            return
                    else:
                        self._cleanup_proc()
                        self.server_failed.emit('Server not responding to health check')
                        return
                else:
                    returncode = self._proc.poll()
                    self._cleanup_proc()
                    self.server_failed.emit(f'Remotion process exited with code {returncode}')
                    return

            if self._proc.stdout is not None:
                for line in self._proc.stdout:
                    pass

        except Exception as e:
            self._cleanup_proc()
            self.server_failed.emit(f'Failed to start studio: {str(e)}')

    def _cleanup_proc(self):
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

    def stop(self):
        self._cleanup_proc()
        self._cleanup_proc()


class PreviewTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scripts_widget = None
        self._server_worker = None
        self._studio_worker = None
        self._current_port = 3099
        self._studio_port = None
        self._server_running = False
        self._server_starting = False
        self._studio_running = False
        self._preview_dir = None
        self._ignore_next_text_change = False
        self._preview_request_id = 0
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._trigger_preview_reload)
        self._script_update_timer = QTimer(self)
        self._script_update_timer.setSingleShot(True)
        self._script_update_timer.setInterval(800)
        self._script_update_timer.timeout.connect(self._on_script_update_timeout)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top toolbar with buttons only
        toolbar = QHBoxLayout()

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
        self.progress_bar.setFormat('Starting Remotion Player...')
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Placeholder label (shows status messages like health check)
        self.placeholder = QLabel('Preview will start automatically when script loads.')
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
        try:
            scripts_widget.script_content.textChanged.connect(self._on_script_content_changed)
        except Exception:
            pass

    def _on_script_selected(self, name):
        self._script_update_timer.stop()
        self._reload_timer.stop()
        self._ignore_next_text_change = True
        self._preview_request_id += 1

        has_script = bool(name)
        script_name = name if name else 'No script loaded.'
        self.status_label.setText(f'Script: {script_name}')

        if not has_script:
            # No script selected - stop server
            self._stop_server()
            self.webview.setUrl(QUrl('about:blank'))
            self.webview.setVisible(False)
            self.placeholder.setVisible(True)
            self.placeholder.setText('Preview will start automatically when script loads.')
            return

        if not self._scripts_widget:
            return

        # Get script content
        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            return

        if self._server_running and self._server_worker and not self._server_starting:
            self._update_script_only(script_content, request_id=self._preview_request_id)
        elif not self._server_running and not self._server_starting:
            self._on_start_preview(request_id=self._preview_request_id, script_content=script_content)

    def _on_start_preview(self, request_id=None, script_content=None):
        if request_id is None:
            request_id = self._preview_request_id
        if script_content is None:
            if not self._scripts_widget:
                return
            script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            return

        self.reload_btn.setEnabled(False)
        self.open_browser_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.webview.setVisible(False)
        self.placeholder.setVisible(True)
        self.placeholder.setText('Preparing preview project...')

        try:
            from helpers.remotion_helper.remotion_helper import setup_preview_dir
            preview_dir, _ = setup_preview_dir(script_content)
            self._preview_dir = preview_dir
        except Exception as e:
            self._server_starting = False
            self._reset_ui(f'Failed to prepare preview: {e}')
            return

        self._current_port = self._find_free_port(3099)
        worker = PlayerServerWorker(self._preview_dir, self._current_port, request_id=request_id)
        self._server_worker = worker
        worker.server_ready.connect(self._on_server_ready)
        worker.server_failed.connect(self._on_server_failed)
        worker.status_update.connect(self._on_status_update)
        worker.start()
        self._server_running = True
        self._server_starting = True
        self.placeholder.setText(f'Starting Remotion Player on port {self._current_port}...')

    def _update_script_only(self, script_content: str, request_id=None):
        """Update script without restart server."""
        if request_id is None:
            request_id = self._preview_request_id
        print('[PreviewTab] Updating script without server restart...')
        self.placeholder.setText('Updating script...')
        self.placeholder.setVisible(True)

        try:
            from helpers.remotion_helper.remotion_helper import setup_preview_dir
            preview_dir, _ = setup_preview_dir(script_content)
            self._preview_dir = preview_dir
            print('[PreviewTab] Preview script updated in preview dir, reloading view...')
            self._reload_timer.stop()
            self._reload_timer.setProperty('request_id', request_id)
            self._reload_timer.start(500)
        except Exception as e:
            print(f'[PreviewTab] Failed to update script: {e}')
            self.status_label.setText(f'Update failed: {e}')

    def _on_script_content_changed(self):
        if self._ignore_next_text_change:
            self._ignore_next_text_change = False
            return
        if not self._scripts_widget:
            return
        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            return
        self._script_update_timer.start()

    def _on_script_update_timeout(self):
        if not self._scripts_widget:
            return
        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            return
        self._preview_request_id += 1
        request_id = self._preview_request_id
        if self._server_running and self._server_worker and not self._server_starting:
            self._update_script_only(script_content, request_id=request_id)
        elif not self._server_running and not self._server_starting:
            self._on_start_preview(request_id=request_id, script_content=script_content)

    def _trigger_preview_reload(self):
        """Trigger reload di webview."""
        request_id = self._reload_timer.property('request_id')
        if request_id != self._preview_request_id:
            return
        self.placeholder.setVisible(False)
        self.webview.setVisible(True)
        self.webview.reload()
        self.status_label.setText(f'Script updated - Preview running at http://127.0.0.1:{self._current_port}')

    def _on_status_update(self, message):
        worker = self.sender()
        if not worker or not hasattr(worker, '_request_id'):
            return
        if worker is not self._server_worker or worker._request_id != self._preview_request_id:
            return
        self.placeholder.setText(message)

    def _on_server_ready(self, port):
        worker = self.sender()
        if not worker or not hasattr(worker, '_request_id'):
            return
        if worker is not self._server_worker or worker._request_id != self._preview_request_id:
            return
        url = f'http://127.0.0.1:{port}'
        print(f'[Remotion Player] Ready at {url}')
        self._server_starting = False
        self.progress_bar.setVisible(False)
        self.placeholder.setVisible(False)
        self.webview.setVisible(True)
        self.reload_btn.setEnabled(True)
        self.open_browser_btn.setEnabled(True)
        self.status_label.setText(f'Preview running at {url}')
        self.webview.setUrl(QUrl(url))

    def _on_server_failed(self, error):
        worker = self.sender()
        if not worker or not hasattr(worker, '_request_id'):
            return
        if worker is not self._server_worker or worker._request_id != self._preview_request_id:
            return
        self._server_starting = False
        self._stop_server()
        self._reset_ui(f'Player failed: {error}')

    def _on_stop_preview(self):
        self._server_running = False
        self._stop_server()
        self._reset_ui('Preview stopped.')

    def _on_reload(self):
        self.webview.reload()

    def _on_open_browser(self):
        """Open full Remotion Studio in browser untuk advanced editing."""
        if not self._scripts_widget:
            return

        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            return

        # Always prepare latest preview dir for Studio
        try:
            from helpers.remotion_helper.remotion_helper import setup_preview_dir
            preview_dir, _ = setup_preview_dir(script_content)
            self._preview_dir = preview_dir
        except Exception as e:
            self.status_label.setText(f'Failed to prepare studio: {e}')
            return

        if self._studio_running and self._studio_port:
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{self._studio_port}')
            self.status_label.setText(f'Studio already running at http://127.0.0.1:{self._studio_port}')
            return

        self._studio_port = self._find_free_port(3100)

        self._studio_worker = StudioServerWorker(self._preview_dir, self._studio_port)
        self._studio_worker.server_ready.connect(self._on_studio_ready)
        self._studio_worker.server_failed.connect(self._on_studio_failed)
        self._studio_worker.start()
        self._studio_running = True
        self.status_label.setText(f'Starting Remotion Studio on port {self._studio_port}...')

    def _on_studio_ready(self, port):
        """Called when Remotion Studio is ready."""
        print(f'[Remotion Studio] Ready at http://127.0.0.1:{port}')
        self.status_label.setText(f'Studio running at http://127.0.0.1:{port}')
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{port}')

    def _on_studio_failed(self, error):
        """Called when Remotion Studio fails to start."""
        print(f'[Remotion Studio] Failed: {error}')
        self.status_label.setText(f'Studio failed: {error}')
        self._studio_running = False
        self._studio_worker = None

    def _stop_server(self, force_cleanup=False):
        self._server_running = False
        self._server_starting = False
        self._reload_timer.stop()
        if self._server_worker:
            worker = self._server_worker
            self._server_worker = None
            worker.stop()
            worker.quit()
            worker.wait(3000)
        from helpers.remotion_helper.remotion_helper import cleanup_preview_dir
        cleanup_preview_dir(force=force_cleanup)

    def _stop_studio(self):
        """Stop Remotion Studio server."""
        self._studio_running = False
        if self._studio_worker:
            self._studio_worker.stop()
            self._studio_worker.quit()
            self._studio_worker.wait(3000)
            self._studio_worker = None

    def _reset_ui(self, status=''):
        self.reload_btn.setEnabled(False)
        self.open_browser_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.webview.setVisible(False)
        self.webview.setUrl(QUrl('about:blank'))
        self.placeholder.setVisible(True)
        self.placeholder.setText(status or 'Preview will start automatically when script loads.')
        self.status_label.setText(status or self.status_label.text())

    def _find_free_port(self, start=3099):
        import socket
        for port in range(start, start + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('127.0.0.1', port))
                    return port
                except OSError:
                    continue
        return start

    def closeEvent(self, event):
        # Aggressive cleanup of all Remotion-related processes
        print('[PreviewTab] Closing - cleaning up all Remotion processes...')
        self._stop_server(force_cleanup=True)
        self._stop_studio()
        # Kill any remaining processes on our ports
        _kill_process_on_port(self._current_port)
        _kill_process_on_port(self._studio_port if self._studio_port else 3100)
        super().closeEvent(event)
