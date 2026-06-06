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
            self.processes[profile_id] = {'proc': proc, 'pid': proc.pid, 'type': browser_type}
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
        try:
            return psutil.Process(pid).is_running()
        except psutil.NoSuchProcess:
            del self.processes[profile_id]
            return False
    
    def focus(self, profile_id):
        """Focus browser window (restore if minimized, bring to front if backgrounded)"""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return False
        
        pid = proc_info['pid']
        try:
            proc = psutil.Process(pid)
            if not proc.is_running():
                del self.processes[profile_id]
                return False
            
            # Find windows belonging to this process
            hwnds = self._find_windows_by_pid(pid)
            if hwnds:
                # Focus the first found window
                hwnd = hwnds[0]
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                return True
        except (psutil.NoSuchProcess, Exception):
            pass
        
        return False
    
    def close(self, profile_id):
        """Close browser process gracefully via WM_CLOSE"""
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return False
        
        pid = proc_info['pid']
        try:
            # Find windows and send WM_CLOSE for graceful shutdown
            hwnds = self._find_windows_by_pid(pid)
            for hwnd in hwnds:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            
            # Wait briefly then check if still running
            import time
            for _ in range(30):  # Wait up to 3 seconds
                if not self._is_process_running(pid):
                    break
                time.sleep(0.1)
            else:
                # Force kill if still running
                proc = psutil.Process(pid)
                proc.kill()
            
            if profile_id in self.processes:
                del self.processes[profile_id]
            return True
        except (psutil.NoSuchProcess, Exception):
            if profile_id in self.processes:
                del self.processes[profile_id]
            return False
    
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