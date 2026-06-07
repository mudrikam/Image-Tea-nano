import subprocess
import os
import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    SW_SHOW = 5
    SW_RESTORE = 9
    WM_CLOSE = 0x0010


class BrowserManager:
    """Manages launched browser processes and window focus"""
    
    def __init__(self):
        self.processes = {}  # profile_id -> {'proc': Popen, 'pid': int, 'type': str}
    
    def launch(self, profile_id, browser_exe, profile_path=None, browser_type='chrome'):
        """Launch browser and track process"""
        if not os.path.exists(browser_exe):
            QMessageBox.warning(None, 'Browser Not Found', f'Browser executable not found:\n{browser_exe}')
            return None
        
        browser_type = browser_type.lower()
        args = [browser_exe]
        
        if browser_type == 'firefox':
            # Firefox uses -profile for profile path
            if profile_path:
                args.append(f'-profile')
                args.append(profile_path)
        else:
            # Chrome/Chromium based uses --user-data-dir
            if profile_path:
                args.append(f'--user-data-dir={profile_path}')
        
        try:
            proc = subprocess.Popen(args, shell=False)
            self.processes[profile_id] = {'proc': proc, 'pid': proc.pid, 'type': browser_type, 'browser_exe': browser_exe}
            return proc.pid
        except Exception as e:
            QMessageBox.critical(None, 'Launch Failed', f'Failed to launch browser:\n{str(e)}')
            return None
    
    def get_process(self, profile_id):
        """Get tracked process for profile"""
        return self.processes.get(profile_id)
    
    def is_running(self, profile_id):
        """Check if browser process is still running"""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return False
        
        pid = proc_info['pid']
        browser_type = proc_info.get('type', 'chrome')
        
        try:
            proc = psutil.Process(pid)
            if not proc.is_running():
                del self.processes[profile_id]
                # For Firefox, check if browser is still running by process name
                if browser_type == 'firefox':
                    return self.is_browser_running_by_name('firefox')
                return False
            
            # For Firefox, check all child processes too
            if browser_type == 'firefox':
                # Check if main process or any child is running
                for child in proc.children(recursive=True):
                    try:
                        if child.is_running():
                            return True
                    except psutil.NoSuchProcess:
                        pass
                # If no children running, check main process
                try:
                    return proc.is_running()
                except psutil.NoSuchProcess:
                    del self.processes[profile_id]
                    return False
            return True
        except psutil.NoSuchProcess:
            if profile_id in self.processes:
                del self.processes[profile_id]
            # For Firefox, check if browser is still running by process name
            if browser_type == 'firefox':
                return self.is_browser_running_by_name('firefox')
            return False
    
    def is_browser_running_by_name(self, browser_type):
        """Check if any browser of given type is running (by process name)"""
        if os.name != 'nt':
            return False
        
        process_name = 'firefox.exe' if browser_type == 'firefox' else 'chrome.exe'
        try:
            for proc in psutil.process_iter(['name']):
                if process_name.lower() in proc.info['name'].lower():
                    return True
        except:
            pass
        return False
    
    def focus(self, profile_id):
        """Focus browser window (restore if minimized, bring to front if backgrounded)"""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return False
        
        pid = proc_info['pid']
        browser_type = proc_info.get('type', 'chrome')
        browser_exe = proc_info.get('browser_exe', '')
        
        # Collect all PIDs to check (for Firefox child processes)
        pids_to_check = [pid]
        proc = None
        try:
            proc = psutil.Process(pid)
            if proc.is_running():
                # For Firefox, find windows in all child processes
                if browser_type == 'firefox':
                    for child in proc.children(recursive=True):
                        try:
                            pids_to_check.append(child.pid)
                        except psutil.NoSuchProcess:
                            pass
        except (psutil.NoSuchProcess, Exception):
            pass
        
        # Find windows belonging to these processes
        hwnds = []
        for check_pid in pids_to_check:
            hwnds.extend(self._find_windows_by_pid(check_pid))
        
        if hwnds:
            # Focus the first found window
            hwnd = hwnds[0]
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return True
        
        # No windows found by PID - try by process name for Firefox
        if browser_type == 'firefox':
            hwnds = self._find_windows_by_process_name('firefox.exe')
            if hwnds:
                user32.ShowWindow(hwnds[0], SW_RESTORE)
                user32.SetForegroundWindow(hwnds[0])
                return True
        
        return False
    
    def close(self, profile_id):
        """Close browser process gracefully via WM_CLOSE"""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return False
        
        pid = proc_info['pid']
        browser_type = proc_info.get('type', 'chrome')
        browser_exe = proc_info.get('browser_exe', '')
        
        # Collect all PIDs to check (for Firefox child processes)
        pids_to_check = [pid]
        proc = None
        try:
            proc = psutil.Process(pid)
            if browser_type == 'firefox':
                for child in proc.children(recursive=True):
                    try:
                        pids_to_check.append(child.pid)
                    except psutil.NoSuchProcess:
                        pass
        except psutil.NoSuchProcess:
            # Parent process gone, try to find Firefox windows using exe path
            if browser_type == 'firefox' and browser_exe:
                pids = self._find_firefox_processes_by_exe(browser_exe)
                pids_to_check = pids
            elif browser_type == 'firefox':
                pids_to_check = []
        
        # Find windows and send WM_CLOSE for graceful shutdown
        hwnds = []
        for check_pid in pids_to_check:
            hwnds.extend(self._find_windows_by_pid(check_pid))
        
        # For Firefox, also try finding windows by process name as fallback
        if browser_type == 'firefox' and not hwnds:
            hwnds = self._find_windows_by_process_name('firefox.exe')
        
        for hwnd in hwnds:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        
        # If we found windows or processes, wait briefly then check
        if hwnds or pids_to_check:
            import time
            for _ in range(30):  # Wait up to 3 seconds
                if not self.is_running(profile_id):
                    break
                time.sleep(0.1)
            else:
                # Force kill all found processes
                for kill_pid in pids_to_check:
                    try:
                        kill_proc = psutil.Process(kill_pid)
                        for child in kill_proc.children(recursive=True):
                            try:
                                child.kill()
                            except:
                                pass
                        kill_proc.kill()
                    except:
                        pass
        
        if profile_id in self.processes:
            del self.processes[profile_id]
        return True
    
    def _is_process_running(self, pid):
        """Check if process is still running"""
        try:
            return psutil.Process(pid).is_running()
        except psutil.NoSuchProcess:
            return False
    
    def _find_windows_by_pid(self, pid):
        """Find all windows belonging to process PID"""
        if os.name != 'nt':
            return []
        
        hwnds = []
        
        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_windows_callback(hwnd, lParam):
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if process_id.value == pid and user32.IsWindowVisible(hwnd):
                hwnds.append(hwnd)
            return True
        
        user32.EnumWindows(enum_windows_callback, 0)
        return hwnds
    
    def _find_windows_by_process_name(self, process_name):
        """Find all windows belonging to processes by name (e.g., firefox.exe, chrome.exe)"""
        if os.name != 'nt':
            return []
        
        hwnds = []
        
        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_windows_callback(hwnd, lParam):
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if user32.IsWindowVisible(hwnd):
                try:
                    proc = psutil.Process(process_id.value)
                    if process_name.lower() in proc.name().lower():
                        hwnds.append(hwnd)
                except psutil.NoSuchProcess:
                    pass
            return True
        
        user32.EnumWindows(enum_windows_callback, 0)
        return hwnds
    
    def _find_firefox_processes_by_exe(self, browser_exe):
        """Find all running firefox.exe processes matching the browser executable"""
        firefox_pids = []
        try:
            browser_dir = os.path.dirname(browser_exe).lower()
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if 'firefox' in proc.info['name'].lower():
                        proc_exe = proc.info.get('exe', '') or ''
                        if browser_dir in proc_exe.lower() or not browser_dir:
                            firefox_pids.append(proc.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except:
            pass
        return firefox_pids