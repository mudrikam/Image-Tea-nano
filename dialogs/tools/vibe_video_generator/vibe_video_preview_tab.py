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
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QProgressBar, QMessageBox
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
import qtawesome as qta
from ui.theme_system import theme

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
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'tcp'],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            pids = set()
            for line in result.stdout.split('\n'):
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                local_addr = parts[1]
                if not local_addr.endswith(f':{port}'):
                    continue
                pid = parts[-1]
                if pid.isdigit() and pid != '0':
                    if int(pid) == os.getpid():
                        continue
                    pids.add(pid)
            for pid in pids:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', pid],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
            return bool(pids)
        return False
    except Exception as e:
        print(f'[Port Cleanup] Error killing process on port {port}: {e}')
        return False


def _wait_for_port_release(host: str, port: int, timeout: float = 5.0, interval: float = 0.25) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not _is_port_open(host, port, timeout=interval):
            return True
        time.sleep(interval)
    return not _is_port_open(host, port, timeout=interval)


def _wait_for_server(host: str, port: int, timeout: float = 30.0, interval: float = 0.5) -> bool:
    """Wait until HTTP server is accessible by making HTTP requests."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            url = f'http://{host}:{port}/'
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=interval) as response:
                return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            if _is_port_open(host, port, timeout=interval):
                healthy, _ = _health_check_server(host, port)
                if healthy:
                    return True
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



class RemotionStudioWorker(QThread):
    """Worker untuk menjalankan Remotion Studio server (single instance untuk semua client)."""
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
        if not _wait_for_port_release('127.0.0.1', self._port, timeout=6.0, interval=0.25):
            self.server_failed.emit(f'Port {self._port} did not release after cleanup')
            return

        npx_cmd = _find_npx_cmd()
        if not npx_cmd:
            self.server_failed.emit('npx not found')
            return

        # Validate project directory
        if not os.path.exists(self._preview_dir):
            self.server_failed.emit(f'Project directory not found: {self._preview_dir}')
            return

        # Use index.ts entry file
        entry_file = os.path.join('src', 'index.ts')
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
                if _wait_for_server('127.0.0.1', self._port, timeout=60.0):
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
                    self.server_failed.emit(f'Server reported ready but not accessible on port {self._port} after 60s')
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
        if self._proc:
            try:
                if self._proc.poll() is None:
                    if platform.system() == 'Windows':
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(self._proc.pid)],
                                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        self._proc.terminate()
                        self._proc.wait(timeout=5)
            except Exception as e:
                print(f'[Remotion Studio] Stop error: {e}')
            finally:
                self._proc = None
        _kill_process_on_port(self._port)
        _wait_for_port_release('127.0.0.1', self._port, timeout=6.0, interval=0.25)

    def stop(self):
        self._cleanup_proc()



class PreviewTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scripts_widget = None
        self._server_worker = None
        self._server_port = None
        self._server_running = False
        self._server_starting = False
        self._preview_dir = None
        self._ignore_next_text_change = False
        self._pending_selected_script_name = ''
        self._preview_request_id = 0
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(350)
        self._selection_timer.timeout.connect(self._process_pending_script_selection)
        self._script_update_timer = QTimer(self)
        self._script_update_timer.setSingleShot(True)
        self._script_update_timer.setInterval(800)
        self._script_update_timer.timeout.connect(self._on_script_update_timeout)
        # Retry mechanism
        self._server_retry_count = 0
        self._retry_timer = None
        self._is_closing = False
        self._open_browser_after_start = False
        self._fullscreen_prev_maximized = False
        self._fullscreen_active = False
        self._fullscreen_prev_visibility = None
        self._fullscreen_prev_margins = None
        self._fullscreen_prev_spacing = None
        self._main_layout = None
        self._toolbar_container = None
        self._auto_controls_pending = False
        # Reload tracking (for compatibility, though HMR replaces manual reload)
        self._reload_request_id = 0
        self._reload_attempts = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._main_layout = layout

        self._toolbar_container = QWidget()
        toolbar_layout = QHBoxLayout(self._toolbar_container)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)

        self.toggle_server_btn = QPushButton('Start Server')
        self.toggle_server_btn.setIcon(qta.icon('fa6s.play'))
        self.toggle_server_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_server_btn.setEnabled(False)
        self.toggle_server_btn.clicked.connect(self._on_toggle_server)
        toolbar_layout.addWidget(self.toggle_server_btn)

        self.open_browser_btn = QPushButton('Open in Browser')
        self.open_browser_btn.setIcon(qta.icon('fa6s.arrow-up-right-from-square'))
        self.open_browser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_browser_btn.setEnabled(False)
        self.open_browser_btn.clicked.connect(self._on_open_browser)
        toolbar_layout.addWidget(self.open_browser_btn)

        self.cancel_start_btn = QPushButton('Cancel Start')
        self.cancel_start_btn.setIcon(qta.icon('fa6s.xmark'))
        self.cancel_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_start_btn.setVisible(False)
        self.cancel_start_btn.clicked.connect(self._on_cancel_starting)
        toolbar_layout.addWidget(self.cancel_start_btn)

        toolbar_layout.addStretch(1)
        layout.addWidget(self._toolbar_container)

        # Progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat('Starting Remotion Studio...')
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Placeholder label (shows status messages like health check)
        self.placeholder = QLabel('Select a script from the Collections tab, then click "Start Server" to open Remotion Studio.')
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.placeholder, 1)

        # Webview
        self.webview = QWebEngineView()
        settings = self.webview.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        self.webview.setVisible(False)
        self.webview.loadFinished.connect(self._on_webview_load_finished)
        self.webview.page().fullScreenRequested.connect(self._on_fullscreen_requested)
        layout.addWidget(self.webview, 1)

        self._exit_fullscreen_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._exit_fullscreen_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._exit_fullscreen_shortcut.activated.connect(self._on_escape_pressed)

        # Status label below webview (script info, running status, errors)
        self.status_label = QLabel('No script loaded.')
        self.status_label.setStyleSheet(f'color: {theme.get_color("text_dark")}; padding: 4px;')
        layout.addWidget(self.status_label)

    def set_scripts_widget(self, scripts_widget):
        self._scripts_widget = scripts_widget
        scripts_widget.script_selected.connect(self._on_script_selected)
        try:
            scripts_widget.script_content.textChanged.connect(self._on_script_content_changed)
        except Exception:
            pass

    def _get_render_settings(self) -> dict:
        """Get current render settings from the Render Settings tab."""
        # Walk up parent chain to find the dialog with render_settings_tab_widget
        p = self.parent()
        while p is not None:
            if hasattr(p, 'render_settings_tab_widget'):
                return p.render_settings_tab_widget.get_all_render_settings()
            p = p.parent()
        # Fallback to defaults if not found
        return {'width': 1920, 'height': 1080, 'fps': 30, 'duration': 10}

    def _on_script_selected(self, name):
        self._script_update_timer.stop()
        self._ignore_next_text_change = True
        self._pending_selected_script_name = name or ''

        script_name = name if name else 'No script loaded.'
        self.status_label.setText(f'Script: {script_name}')

        if not name:
            self._exit_embedded_fullscreen()
            self._selection_timer.stop()
            self._preview_request_id += 1
            # Abort any pending page load first
            self.webview.stop()
            # Disconnect webview from server first to avoid renderer crash on server kill
            self.webview.setUrl(QUrl('about:blank'))
            self.webview.setVisible(False)
            self.placeholder.setVisible(True)
            self.placeholder.setText('Select a script to open in Remotion Studio.')
            # Now it's safe to stop the server
            self._stop_server()
            self._reset_ui('No script selected.')
            self.toggle_server_btn.setEnabled(False)
            return

        self._selection_timer.start()

    def _process_pending_script_selection(self):
        # New request, reset retry counter and cancel any pending retry
        self._server_retry_count = 0
        if self._retry_timer:
            self._retry_timer.stop()
            self._retry_timer = None
        name = self._pending_selected_script_name

        if not name or not self._scripts_widget:
            self._reset_ui('No script loaded.')
            self.toggle_server_btn.setEnabled(False)
            return
        if self._server_starting:
            return

        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            self._reset_ui('Script is empty.')
            self.toggle_server_btn.setEnabled(False)
            return

        self._preview_request_id += 1
        request_id = self._preview_request_id

        if self._server_running and self._server_worker:
            # Hot-reload: update script without restarting server
            self._update_script_only(script_content, request_id=request_id)
            script_name = name if name else 'Current script'
            self.status_label.setText(f'Script: {script_name} - Updated (HMR...)')
            # Server is running - toggle becomes "Stop" (enabled)
            self._update_toggle_server_button()
            self.open_browser_btn.setEnabled(True)
        else:
            # Server not running - prepare UI for manual start
            script_name = name if name else 'Current script'
            self.status_label.setText(f'Script: {script_name} - Ready (click "Start Server")')
            self.placeholder.setText('Remotion Studio will open when you click "Start Server".')
            self.placeholder.setVisible(True)
            self.webview.setVisible(False)
            can_start = not self._server_starting and not self._server_running
            self._update_toggle_server_button()
            self.open_browser_btn.setEnabled(True)

    def _on_start_server(self, request_id=None, script_content=None):
        if self._server_starting or self._server_running:
            return
        self._auto_controls_pending = True
        if request_id is None:
            request_id = self._preview_request_id
        if script_content is None:
            if not self._scripts_widget:
                return
            script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            return

        self.toggle_server_btn.setEnabled(False)
        self.open_browser_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.webview.setVisible(False)
        self.placeholder.setVisible(True)
        self.placeholder.setText('Preparing Remotion Studio...')

        try:
            from helpers.remotion_helper.remotion_helper import setup_preview_dir
            # Get actual render settings from Render Settings tab
            render_settings = self._get_render_settings()
            preview_dir, _ = setup_preview_dir(script_content, render_settings)
            self._preview_dir = preview_dir
        except Exception as e:
            self._server_starting = False
            self._server_running = False
            self._reset_ui(f'Failed to start Remotion Studio: {e}')
            self._update_toggle_server_button()
            self.open_browser_btn.setEnabled(True)
            return

        self._server_starting = True
        self._server_running = True
        self.cancel_start_btn.setVisible(True)
        self._server_port = self._find_free_port(3099)
        worker = RemotionStudioWorker(self._preview_dir, self._server_port, request_id=request_id)
        self._server_worker = worker
        worker.server_ready.connect(self._on_server_ready)
        worker.server_failed.connect(self._on_server_failed)
        worker.start()
        self.placeholder.setText(f'Starting Remotion Studio on port {self._server_port}...')

    def _update_script_only(self, script_content: str, request_id=None):
        """Update script without restarting server – HMR handles auto-refresh."""
        try:
            from helpers.remotion_helper.remotion_helper import setup_preview_dir
            render_settings = self._get_render_settings()
            preview_dir, _ = setup_preview_dir(script_content, render_settings)
            self._preview_dir = preview_dir
            print('[PreviewTab] Script updated – Remotion HMR will auto-refresh')
            # Remotion's file watcher detects change and pushes HMR update automatically
        except Exception as e:
            print(f'[PreviewTab] Failed to update script: {e}')
            self.status_label.setText(f'Update failed: {e}')

    def _on_script_content_changed(self):
        if self._ignore_next_text_change:
            self._ignore_next_text_change = False
            return
        if self._selection_timer.isActive() or self._server_starting:
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
        if self._server_starting:
            return
        # New update, reset retry counter and cancel pending retry
        self._server_retry_count = 0
        if self._retry_timer:
            self._retry_timer.stop()
            self._retry_timer = None
        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            self._reset_ui('Script is empty.')
            self._update_toggle_server_button()
            return

        self._preview_request_id += 1
        request_id = self._preview_request_id

        if self._server_running and self._server_worker:
            # Hot-reload: update script without restarting server
            self._update_script_only(script_content, request_id=request_id)
            script_name = self._pending_selected_script_name or 'Current script'
            self.status_label.setText(f'Script: {script_name} - Updated (reloading...)')
            # Keep buttons: start disabled (server running), reload & open_browser enabled
        else:
            # Server not running - do nothing, just update status
            script_name = self._pending_selected_script_name or 'Current script'
            self.status_label.setText(f'Script: {script_name} - Modified (click "Start Server" to refresh)')
            self.placeholder.setText('Script updated. Click "Start Server" to refresh Remotion Studio.')
            self.placeholder.setVisible(True)
            self.webview.setVisible(False)
            can_start = not self._server_starting and not self._server_running
            self._update_toggle_server_button()
            self.open_browser_btn.setEnabled(True)


    def _on_webview_load_finished(self, success: bool):
        """Handle webview load completion after initial page load."""
        try:
            if success:
                if self._server_running:
                    script_name = self._pending_selected_script_name or 'Current script'
                    self.status_label.setText(f'Script: {script_name} - Ready')
                    print('[PreviewTab] Page loaded successfully')
                    if self._auto_controls_pending:
                        self._auto_controls_pending = False
                        self._enter_embedded_fullscreen()
                        self._send_auto_controls()
            else:
                # Initial load failed; server might still be starting, ignore
                print('[PreviewTab] Initial page load failed (will retry automatically)')
        except Exception as e:
            print(f'[PreviewTab] Error in loadFinished: {e}')

    def _send_auto_controls(self):
        self.webview.setFocus()
        script = (
            "(() => {"
            "const fire = (key, code) => {"
            "const evt = new KeyboardEvent('keydown', { key, code, keyCode: 32, which: 32, bubbles: true });"
            "document.dispatchEvent(evt); window.dispatchEvent(evt);" 
            "};"
            "setTimeout(() => { fire(' ', 'Space'); }, 250);"
            "})();"
        )
        self.webview.page().runJavaScript(script)

    def _on_fullscreen_requested(self, request):
        request.accept()
        if request.toggleOn():
            self._enter_embedded_fullscreen()
        else:
            self._exit_embedded_fullscreen()

    def _on_escape_pressed(self):
        if not self._fullscreen_active:
            return
        self.webview.page().runJavaScript('if (document.fullscreenElement) { document.exitFullscreen(); }')
        self._exit_embedded_fullscreen()

    def _enter_embedded_fullscreen(self):
        if self._fullscreen_active:
            return
        self._fullscreen_active = True
        self._fullscreen_prev_visibility = {
            'toolbar': self._toolbar_container.isVisible(),
            'status': self.status_label.isVisible(),
            'progress': self.progress_bar.isVisible(),
            'placeholder': self.placeholder.isVisible(),
        }
        margins = self._main_layout.contentsMargins() if self._main_layout else None
        if margins:
            self._fullscreen_prev_margins = (margins.left(), margins.top(), margins.right(), margins.bottom())
        self._fullscreen_prev_spacing = self._main_layout.spacing() if self._main_layout else None
        self.status_label.setVisible(False)
        self.progress_bar.setVisible(False)
        self.placeholder.setVisible(False)
        if self._main_layout:
            self._main_layout.setContentsMargins(0, 0, 0, 0)
            self._main_layout.setSpacing(0)

    def _exit_embedded_fullscreen(self):
        if not self._fullscreen_active:
            return
        self._fullscreen_active = False
        if self._fullscreen_prev_visibility:
            self._toolbar_container.setVisible(self._fullscreen_prev_visibility['toolbar'])
            self.status_label.setVisible(self._fullscreen_prev_visibility['status'])
            self.progress_bar.setVisible(self._fullscreen_prev_visibility['progress'])
            self.placeholder.setVisible(self._fullscreen_prev_visibility['placeholder'])
        if self._main_layout and self._fullscreen_prev_margins:
            left, top, right, bottom = self._fullscreen_prev_margins
            self._main_layout.setContentsMargins(left, top, right, bottom)
        if self._main_layout and self._fullscreen_prev_spacing is not None:
            self._main_layout.setSpacing(self._fullscreen_prev_spacing)

    def _on_status_update(self, message):
        worker = self.sender()
        if worker is not self._server_worker:
            return
        self.placeholder.setText(message)

    def _on_server_ready(self, port):
        if self._is_closing:
            return
        worker = self.sender()
        if worker is not self._server_worker:
            return
        url = f'http://127.0.0.1:{port}'
        print(f'[Remotion Studio] Ready at {url}')
        self._server_starting = False
        self.cancel_start_btn.setVisible(False)
        self._server_retry_count = 0
        if self._retry_timer:
            self._retry_timer.stop()
            self._retry_timer = None
        self.progress_bar.setVisible(False)
        self.placeholder.setVisible(False)
        self.webview.setVisible(True)
        self.open_browser_btn.setEnabled(True)
        self._update_toggle_server_button()
        self.status_label.setText(f'Remotion Studio running at {url}')
        self.webview.setUrl(QUrl(url))

        # If user clicked "Open in Browser" while server was stopped, open external browser now
        if getattr(self, '_open_browser_after_start', False):
            self._open_browser_after_start = False
            import webbrowser
            webbrowser.open(url)

    def _on_server_failed(self, error):
        if self._is_closing:
            return
        worker = self.sender()
        if worker is not self._server_worker:
            return
        self._server_starting = False
        self.cancel_start_btn.setVisible(False)
        if self._server_retry_count < 3:
            self._server_retry_count += 1
            print(f'[PreviewTab] Studio failed ({error}), retrying ({self._server_retry_count}/3)...')
            self._stop_server(force_cleanup=True)
            # Schedule retry with cancellable timer
            if self._retry_timer:
                self._retry_timer.stop()
            self._retry_timer = QTimer(self)
            self._retry_timer.setSingleShot(True)
            self._retry_timer.timeout.connect(self._retry_start_server)
            self._retry_timer.start(1000 * self._server_retry_count)
        else:
            self._reset_ui(f'Studio failed: {error}')
            self._server_retry_count = 0
            self.open_browser_btn.setEnabled(True)
            if self._retry_timer:
                self._retry_timer.stop()
                self._retry_timer = None

    def _retry_start_server(self):
        """Retry starting Remotion Studio after a failure."""
        if self._is_closing:
            return
        # Avoid duplicate starts
        if self._server_starting or self._server_running:
            return
        if not self._scripts_widget:
            return
        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            return
        self._on_start_server(script_content=script_content)

    def _on_stop_preview(self):
        self._server_running = False
        self._exit_embedded_fullscreen()
        self._stop_server()
        self._reset_ui('Remotion Studio stopped.')

    def _on_toggle_server(self):
        """Toggle server based on current state."""
        if self._server_running or self._server_starting:
            self._exit_embedded_fullscreen()
            self.webview.stop()
            self.webview.setUrl(QUrl('about:blank'))
            self.webview.setVisible(False)
            self.placeholder.setVisible(True)
            self._stop_server(force_cleanup=True)
            self._reset_ui('Remotion Studio stopped.')
            self._process_pending_script_selection()
        else:
            self._on_start_server()

    def _on_open_browser(self):
        """Open Remotion Studio in external browser (shares same server as embedded webview)."""
        # If server already running, just open browser to the same port
        if self._server_running and self._server_port:
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{self._server_port}')
            self.status_label.setText(f'Browser opened at http://127.0.0.1:{self._server_port}')
            return

        # Server not running – start it and then open browser when ready
        if not self._scripts_widget:
            return

        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            QMessageBox.warning(self, 'No Script', 'Please write or select a script first.')
            return

        # Set flag to open browser after server starts
        self._open_browser_after_start = True
        # Start the server (same as Start Server button)
        self._on_start_server()

    def _on_cancel_starting(self):
        if not self._server_starting:
            return
        self._auto_controls_pending = False
        self._exit_embedded_fullscreen()
        self._stop_server(force_cleanup=True, wait_ms=4000)
        self._reset_ui('Remotion Studio start cancelled.')
        self._process_pending_script_selection()

    def _on_stop_server(self):
        """Stop the Remotion Studio server."""
        self._exit_embedded_fullscreen()
        self.webview.stop()
        self.webview.setUrl(QUrl('about:blank'))
        self.webview.setVisible(False)
        self.placeholder.setVisible(True)
        self._stop_server(force_cleanup=True)
        self._reset_ui('Remotion Studio stopped.')
        # Re-evaluate UI state immediately
        self._process_pending_script_selection()



    def _stop_server(self, force_cleanup=False, wait_ms=70000):
        self._reload_request_id = 0  # Clear any pending reload
        self._reload_attempts = 0
        self._server_running = False
        self._server_starting = False
        self._server_retry_count = 0  # reset retry counter
        self.cancel_start_btn.setVisible(False)
        if self._retry_timer:
            self._retry_timer.stop()
            self._retry_timer = None
        if self._server_worker:
            worker = self._server_worker
            self._server_worker = None
            # Disconnect signals to prevent callbacks after stop
            try:
                worker.server_ready.disconnect()
                worker.server_failed.disconnect()
            except RuntimeError:
                pass
            worker.stop()
            # Wait for graceful exit (covers server startup wait)
            if not worker.wait(wait_ms):
                if worker.isRunning():
                    print("[Preview] Server worker did not stop in time, terminating.")
                    worker.terminate()
                    worker.wait()
            worker.deleteLater()
        from helpers.remotion_helper.remotion_helper import cleanup_preview_dir
        cleanup_preview_dir(force=force_cleanup)



    def _reset_ui(self, status=''):
        self._reload_request_id = 0  # Clear any pending reload tracking
        self._reload_attempts = 0
        self._open_browser_after_start = False  # Clear pending open-browser request
        self.cancel_start_btn.setVisible(False)
        self.open_browser_btn.setEnabled(False)
        self._update_toggle_server_button()
        self.progress_bar.setVisible(False)
        self.webview.setVisible(False)
        self.webview.setUrl(QUrl('about:blank'))
        self.placeholder.setVisible(True)
        self.placeholder.setText(status or 'Select a script from the Collections tab, then click "Start Server" to open Remotion Studio.')
        self.status_label.setText(status or self.status_label.text())

    def _update_toggle_server_button(self):
        """Update toggle server button text, icon, and enabled state based on server status."""
        if self._server_running:
            self.toggle_server_btn.setText('Stop Server')
            self.toggle_server_btn.setIcon(qta.icon('fa6s.stop'))
            self.toggle_server_btn.setEnabled(True)
        elif self._server_starting:
            self.toggle_server_btn.setText('Starting...')
            self.toggle_server_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.toggle_server_btn)))
            self.toggle_server_btn.setEnabled(False)
        else:
            self.toggle_server_btn.setText('Start Server')
            self.toggle_server_btn.setIcon(qta.icon('fa6s.play'))
            # Enable only if there's a script with content
            can_start = False
            if self._scripts_widget:
                script_content = self._scripts_widget.script_content.toPlainText().strip()
                can_start = bool(script_content)
            self.toggle_server_btn.setEnabled(can_start)

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
        self._is_closing = True
        # Immediately stop all timers to prevent callbacks during cleanup
        self._script_update_timer.stop()
        self._selection_timer.stop()
        if self._retry_timer:
            self._retry_timer.stop()
            self._retry_timer = None

        # Aggressive cleanup of all Remotion-related processes
        print('[PreviewTab] Closing - cleaning up all Remotion processes...')
        self._stop_server(force_cleanup=True)
        # Ensure port is freed
        if self._server_port:
            _kill_process_on_port(self._server_port)
        super().closeEvent(event)
