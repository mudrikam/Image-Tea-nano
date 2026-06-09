import subprocess
import os
import psutil
import threading
import time
import json
from PySide6.QtWidgets import QMessageBox

if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    SW_MAXIMIZE = 3
    WM_CLOSE = 0x0010
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    VK_F11 = 0x7A
    GW_OWNER = 4


class BrowserManager:
    """Manages launched browser processes and window focus"""
    FIREFOX_PROXY_PREFS = [
        'network.proxy.type',
        'network.proxy.http',
        'network.proxy.http_port',
        'network.proxy.ssl',
        'network.proxy.ssl_port',
        'network.proxy.ftp',
        'network.proxy.ftp_port',
        'network.proxy.socks',
        'network.proxy.socks_port',
        'network.proxy.socks_version',
        'network.proxy.socks_remote_dns',
        'network.proxy.autoconfig_url',
        'network.proxy.no_proxies_on',
        'signon.autologin.proxy',
    ]
    
    def __init__(self):
        self.processes = {}  # profile_id -> {'proc': Popen, 'pid': int, 'type': str, 'browser_exe': str}
    
    def close_all(self):
        """Close all tracked browser processes - called on app shutdown"""
        profile_ids = list(self.processes.keys())
        for profile_id in profile_ids:
            try:
                self.close(profile_id)
            except Exception:
                pass

    def _is_truthy(self, value):
        return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}

    def _normalize_proxy_settings(self, proxy_settings):
        proxy_settings = proxy_settings or {}
        defaults = {
            'proxy_enabled': 'false',
            'proxy_mode': 'system',
            'proxy_scheme': 'http',
            'proxy_host': '',
            'proxy_port': '',
            'proxy_username': '',
            'proxy_password': '',
            'proxy_bypass_list': '[]',
            'proxy_pac_url': '',
            'proxy_dns_remote': 'false',
            'proxy_share_all_protocols': 'true',
            'proxy_http_host': '',
            'proxy_http_port': '',
            'proxy_ssl_host': '',
            'proxy_ssl_port': '',
            'proxy_ftp_host': '',
            'proxy_ftp_port': '',
            'proxy_socks_host': '',
            'proxy_socks_port': '',
            'proxy_socks_version': '5',
        }
        normalized = {}
        for key, default_value in defaults.items():
            value = proxy_settings.get(key, default_value)
            normalized[key] = '' if value is None else str(value)
        return normalized

    def _parse_proxy_bypass_list(self, value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            try:
                decoded = json.loads(value)
                if isinstance(decoded, list):
                    return [str(item).strip() for item in decoded if str(item).strip()]
            except json.JSONDecodeError:
                pass
            return [line.strip() for line in value.splitlines() if line.strip()]
        return []

    def _build_proxy_auth_prefix(self, proxy_settings):
        username = str(proxy_settings.get('proxy_username', '') or '').strip()
        password = str(proxy_settings.get('proxy_password', '') or '').strip()
        if not username:
            return ''
        if password:
            return f'{username}:{password}@'
        return f'{username}@'

    def _build_chromium_proxy_args(self, proxy_settings):
        proxy_settings = self._normalize_proxy_settings(proxy_settings)
        if not self._is_truthy(proxy_settings.get('proxy_enabled')):
            return []

        mode = proxy_settings.get('proxy_mode', 'system') or 'system'
        bypass_list = self._parse_proxy_bypass_list(proxy_settings.get('proxy_bypass_list'))
        args = []

        if mode == 'direct':
            args.append('--no-proxy-server')
        elif mode == 'manual':
            if self._is_truthy(proxy_settings.get('proxy_share_all_protocols')):
                host = proxy_settings.get('proxy_host', '').strip()
                port = proxy_settings.get('proxy_port', '').strip()
                scheme = proxy_settings.get('proxy_scheme', 'http').strip() or 'http'
                if host and port:
                    auth_prefix = self._build_proxy_auth_prefix(proxy_settings)
                    args.append(f'--proxy-server={scheme}://{auth_prefix}{host}:{port}')
            else:
                server_parts = []
                endpoint_map = [
                    ('http', proxy_settings.get('proxy_http_host', '').strip(), proxy_settings.get('proxy_http_port', '').strip()),
                    ('https', proxy_settings.get('proxy_ssl_host', '').strip(), proxy_settings.get('proxy_ssl_port', '').strip()),
                ]
                for scheme, host, port in endpoint_map:
                    if host and port:
                        server_parts.append(f'{scheme}={host}:{port}')

                socks_host = proxy_settings.get('proxy_socks_host', '').strip()
                socks_port = proxy_settings.get('proxy_socks_port', '').strip()
                socks_version = proxy_settings.get('proxy_socks_version', '5').strip() or '5'
                if socks_host and socks_port:
                    server_parts.append(f'socks=socks{socks_version}://{socks_host}:{socks_port}')

                ftp_host = proxy_settings.get('proxy_ftp_host', '').strip()
                ftp_port = proxy_settings.get('proxy_ftp_port', '').strip()
                if ftp_host and ftp_port:
                    server_parts.append(f'ftp={ftp_host}:{ftp_port}')

                if server_parts:
                    args.append(f'--proxy-server={";".join(server_parts)}')
        elif mode == 'pac':
            pac_url = proxy_settings.get('proxy_pac_url', '').strip()
            if pac_url:
                args.append(f'--proxy-pac-url={pac_url}')
        elif mode == 'autodetect':
            args.append('--proxy-auto-detect')

        if bypass_list and mode in {'manual', 'pac'}:
            args.append(f'--proxy-bypass-list={";".join(bypass_list)}')
        return args

    def _escape_firefox_pref_string(self, value):
        return str(value).replace('\\', '\\\\').replace('"', '\\"')

    def _build_firefox_proxy_prefs(self, proxy_settings):
        proxy_settings = self._normalize_proxy_settings(proxy_settings)
        prefs = {}
        if not self._is_truthy(proxy_settings.get('proxy_enabled')):
            prefs['network.proxy.type'] = 5
            return prefs

        mode = proxy_settings.get('proxy_mode', 'system') or 'system'
        bypass_list = ','.join(self._parse_proxy_bypass_list(proxy_settings.get('proxy_bypass_list')))
        username_present = bool(proxy_settings.get('proxy_username', '').strip())

        if mode == 'system':
            prefs['network.proxy.type'] = 5
        elif mode == 'direct':
            prefs['network.proxy.type'] = 0
        elif mode == 'pac':
            prefs['network.proxy.type'] = 2
            prefs['network.proxy.autoconfig_url'] = proxy_settings.get('proxy_pac_url', '').strip()
        elif mode == 'autodetect':
            prefs['network.proxy.type'] = 4
        elif mode == 'manual':
            prefs['network.proxy.type'] = 1
            if self._is_truthy(proxy_settings.get('proxy_share_all_protocols')):
                host = proxy_settings.get('proxy_host', '').strip()
                port = proxy_settings.get('proxy_port', '').strip()
                scheme = proxy_settings.get('proxy_scheme', 'http').strip() or 'http'
                if host and port:
                    if scheme in {'http', 'https'}:
                        prefs['network.proxy.http'] = host
                        prefs['network.proxy.http_port'] = int(port)
                        prefs['network.proxy.ssl'] = host
                        prefs['network.proxy.ssl_port'] = int(port)
                    else:
                        prefs['network.proxy.socks'] = host
                        prefs['network.proxy.socks_port'] = int(port)
                        prefs['network.proxy.socks_version'] = 4 if scheme == 'socks4' else 5
            else:
                if proxy_settings.get('proxy_http_host', '').strip() and proxy_settings.get('proxy_http_port', '').strip():
                    prefs['network.proxy.http'] = proxy_settings.get('proxy_http_host', '').strip()
                    prefs['network.proxy.http_port'] = int(proxy_settings.get('proxy_http_port', '').strip())
                if proxy_settings.get('proxy_ssl_host', '').strip() and proxy_settings.get('proxy_ssl_port', '').strip():
                    prefs['network.proxy.ssl'] = proxy_settings.get('proxy_ssl_host', '').strip()
                    prefs['network.proxy.ssl_port'] = int(proxy_settings.get('proxy_ssl_port', '').strip())
                if proxy_settings.get('proxy_ftp_host', '').strip() and proxy_settings.get('proxy_ftp_port', '').strip():
                    prefs['network.proxy.ftp'] = proxy_settings.get('proxy_ftp_host', '').strip()
                    prefs['network.proxy.ftp_port'] = int(proxy_settings.get('proxy_ftp_port', '').strip())
                if proxy_settings.get('proxy_socks_host', '').strip() and proxy_settings.get('proxy_socks_port', '').strip():
                    prefs['network.proxy.socks'] = proxy_settings.get('proxy_socks_host', '').strip()
                    prefs['network.proxy.socks_port'] = int(proxy_settings.get('proxy_socks_port', '').strip())
                    prefs['network.proxy.socks_version'] = int(proxy_settings.get('proxy_socks_version', '5').strip() or '5')
            prefs['network.proxy.socks_remote_dns'] = self._is_truthy(proxy_settings.get('proxy_dns_remote'))

        prefs['network.proxy.no_proxies_on'] = bypass_list
        prefs['signon.autologin.proxy'] = username_present
        return prefs

    def _sync_firefox_proxy_preferences(self, profile_path, proxy_settings):
        if not profile_path:
            return
        os.makedirs(profile_path, exist_ok=True)
        prefs = self._build_firefox_proxy_prefs(proxy_settings)
        user_js_path = os.path.join(profile_path, 'user.js')
        managed_lines = ['// Managed by Account Manager proxy settings']
        for key in self.FIREFOX_PROXY_PREFS:
            if key not in prefs:
                continue
            value = prefs[key]
            if isinstance(value, bool):
                rendered = 'true' if value else 'false'
            elif isinstance(value, int):
                rendered = str(value)
            else:
                rendered = f'"{self._escape_firefox_pref_string(value)}"'
            managed_lines.append(f'user_pref("{key}", {rendered});')
        managed_block = '\n'.join(managed_lines).strip() + '\n'

        existing_content = ''
        if os.path.exists(user_js_path):
            try:
                with open(user_js_path, 'r', encoding='utf-8') as file_handle:
                    existing_content = file_handle.read()
            except Exception:
                existing_content = ''

        filtered_lines = []
        for line in existing_content.splitlines():
            stripped = line.strip()
            if stripped == '// Managed by Account Manager proxy settings':
                continue
            if any(stripped.startswith(f'user_pref("{pref_key}"') for pref_key in self.FIREFOX_PROXY_PREFS):
                continue
            filtered_lines.append(line)

        new_content = '\n'.join(filtered_lines).strip()
        if new_content:
            new_content += '\n\n'
        new_content += managed_block
        with open(user_js_path, 'w', encoding='utf-8') as file_handle:
            file_handle.write(new_content)
    
    def launch(self, profile_id, browser_exe, profile_path=None, browser_type='chrome', window_mode='windowed', additional_parameters=None, proxy_settings=None):
        """Launch browser and track process"""
        if not os.path.exists(browser_exe):
            QMessageBox.warning(None, 'Browser Not Found', f'Browser executable not found:\n{browser_exe}')
            return None
        
        browser_type = (browser_type or 'chrome').lower()
        window_mode = (window_mode or 'windowed').lower()
        proxy_settings = self._normalize_proxy_settings(proxy_settings)
        args = [browser_exe]
        
        if browser_type == 'firefox':
            self._sync_firefox_proxy_preferences(profile_path, proxy_settings)
            if profile_path:
                args.extend(['-profile', profile_path])
            if window_mode == 'fullscreen':
                args.append('-fullscreen')
        else:
            if profile_path:
                args.append(f'--user-data-dir={profile_path}')
            if window_mode == 'maximized':
                args.append('--start-maximized')
            elif window_mode == 'fullscreen':
                args.append('--start-fullscreen')
            args.extend(self._build_chromium_proxy_args(proxy_settings))
        
        if additional_parameters:
            args.extend([str(parameter).strip() for parameter in additional_parameters if str(parameter).strip()])
        
        try:
            proc = subprocess.Popen(args, shell=False)
            self.processes[profile_id] = {
                'proc': proc,
                'pid': proc.pid,
                'type': browser_type,
                'browser_exe': browser_exe,
                'window_mode': window_mode,
            }
            self._apply_window_mode_async(profile_id, window_mode)
            return proc.pid
        except Exception as e:
            QMessageBox.critical(None, 'Launch Failed', f'Failed to launch browser:\n{str(e)}')
            return None

    def _apply_window_mode_async(self, profile_id, window_mode):
        """Best-effort native window mode adjustment after browser window appears."""
        if os.name != 'nt' or window_mode not in {'maximized', 'fullscreen'}:
            return

        def worker():
            for _ in range(40):
                proc_info = self.processes.get(profile_id)
                if not proc_info:
                    return

                browser_type = proc_info.get('type', 'chrome')
                hwnds = self._resolve_window_handles(profile_id)
                if hwnds:
                    hwnd = hwnds[0]
                    if window_mode == 'maximized':
                        user32.ShowWindow(hwnd, SW_MAXIMIZE)
                    elif window_mode == 'fullscreen':
                        if browser_type == 'firefox':
                            # Firefox already receives -fullscreen at launch; F11 here would toggle it back off.
                            return
                        user32.ShowWindow(hwnd, SW_MAXIMIZE)
                        time.sleep(0.2)
                        user32.PostMessageW(hwnd, WM_KEYDOWN, VK_F11, 0)
                        user32.PostMessageW(hwnd, WM_KEYUP, VK_F11, 0)
                    return
                time.sleep(0.25)

        threading.Thread(target=worker, daemon=True).start()
    
    def get_process(self, profile_id):
        """Get tracked process for profile"""
        return self.processes.get(profile_id)
    
    def is_running(self, profile_id):
        """Check if tracked browser is still running"""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return False
        
        browser_type = proc_info.get('type', 'chrome')
        browser_exe = proc_info.get('browser_exe', '')
        pids = self._get_candidate_pids(profile_id)
        
        if pids:
            return True
        
        if browser_type == 'firefox':
            if browser_exe and self._find_firefox_processes_by_exe(browser_exe):
                return True
            if self._find_windows_by_process_name('firefox.exe'):
                return True
        
        if profile_id in self.processes:
            del self.processes[profile_id]
        return False
    
    def has_window(self, profile_id):
        """Check whether tracked browser currently has a visible window"""
        return bool(self._resolve_window_handles(profile_id))
    
    def focus(self, profile_id):
        """Focus browser window (restore if minimized, bring to front if backgrounded)"""
        hwnds = self._resolve_window_handles(profile_id)
        if hwnds:
            hwnd = hwnds[0]
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return True
        
        return False
    
    def close(self, profile_id):
        """Close browser process gracefully via WM_CLOSE"""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return False
        
        browser_type = proc_info.get('type', 'chrome')
        browser_exe = proc_info.get('browser_exe', '')
        pids_to_check = self._get_candidate_pids(profile_id)
        hwnds = self._resolve_window_handles(profile_id)
        
        if browser_type == 'firefox':
            if browser_exe:
                extra_pids = self._find_firefox_processes_by_exe(browser_exe)
                for pid in extra_pids:
                    if pid not in pids_to_check:
                        pids_to_check.append(pid)
            hwnds = list(dict.fromkeys(hwnds))
        
        for hwnd in hwnds:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        
        if hwnds or pids_to_check:
            import time
            for _ in range(30):
                if not self.has_window(profile_id) and not self.is_running(profile_id):
                    break
                time.sleep(0.1)
            else:
                for kill_pid in pids_to_check:
                    try:
                        kill_proc = psutil.Process(kill_pid)
                        for child in kill_proc.children(recursive=True):
                            try:
                                child.kill()
                            except Exception:
                                pass
                        kill_proc.kill()
                    except Exception:
                        pass
        
        if profile_id in self.processes:
            del self.processes[profile_id]
        return True
    
    def _get_candidate_pids(self, profile_id):
        """Get tracked PID plus live child PIDs"""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return []
        
        pids = []
        pid = proc_info.get('pid')
        if not pid:
            return pids
        
        try:
            proc = psutil.Process(pid)
            if proc.is_running():
                pids.append(pid)
                for child in proc.children(recursive=True):
                    try:
                        if child.is_running():
                            pids.append(child.pid)
                    except psutil.NoSuchProcess:
                        pass
        except psutil.NoSuchProcess:
            pass
        
        return list(dict.fromkeys(pids))
    
    def _get_candidate_windows(self, profile_id):
        """Get visible windows for tracked PID and children"""
        hwnds = []
        for pid in self._get_candidate_pids(profile_id):
            hwnds.extend(self._find_windows_by_pid(pid))
        return list(dict.fromkeys(hwnds))

    def _resolve_window_handles(self, profile_id):
        """Resolve visible windows for tracked browser, including Firefox fallbacks."""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return []

        hwnds = self._get_candidate_windows(profile_id)
        if hwnds:
            return hwnds

        browser_type = proc_info.get('type', 'chrome')
        browser_exe = proc_info.get('browser_exe', '')
        if browser_type != 'firefox':
            return hwnds

        if browser_exe:
            for pid in self._find_firefox_processes_by_exe(browser_exe):
                hwnds.extend(self._find_windows_by_pid(pid))

        if not hwnds:
            hwnds = self._find_windows_by_process_name('firefox.exe')

        return list(dict.fromkeys(hwnds))
    
    def _find_windows_by_pid(self, pid):
        """Find all windows belonging to process PID"""
        if os.name != 'nt':
            return []
        
        hwnds = []
        
        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_windows_callback(hwnd, lParam):
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if process_id.value == pid and user32.IsWindowVisible(hwnd) and user32.GetWindow(hwnd, GW_OWNER) == 0:
                hwnds.append(hwnd)
            return True
        
        user32.EnumWindows(enum_windows_callback, 0)
        return hwnds
    
    def _find_windows_by_process_name(self, process_name):
        """Find all windows belonging to processes by name"""
        if os.name != 'nt':
            return []
        
        hwnds = []
        
        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_windows_callback(hwnd, lParam):
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if user32.IsWindowVisible(hwnd) and user32.GetWindow(hwnd, GW_OWNER) == 0:
                try:
                    proc = psutil.Process(process_id.value)
                    name = (proc.name() or '').lower()
                    if process_name.lower() in name:
                        hwnds.append(hwnd)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return True
        
        user32.EnumWindows(enum_windows_callback, 0)
        return hwnds
    
    def _find_firefox_processes_by_exe(self, browser_exe):
        """Find all running firefox.exe processes matching the browser executable directory"""
        firefox_pids = []
        try:
            browser_dir = os.path.dirname(browser_exe).lower()
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    proc_name = (proc.info.get('name') or '').lower()
                    proc_exe = (proc.info.get('exe') or '').lower()
                    if 'firefox' in proc_name and (not browser_dir or browser_dir in proc_exe):
                        firefox_pids.append(proc.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return firefox_pids
