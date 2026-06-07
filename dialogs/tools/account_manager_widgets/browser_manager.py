import subprocess
import os
import psutil
from PySide6.QtWidgets import QMessageBox

if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    WM_CLOSE = 0x0010


class BrowserManager:
    """Manages launched browser processes and window focus"""
    
    def __init__(self):
        self.processes = {}  # profile_id -> {'proc': Popen, 'pid': int, 'type': str, 'browser_exe': str}
    
    def launch(self, profile_id, browser_exe, profile_path=None, browser_type='chrome'):
        """Launch browser and track process"""
        if not os.path.exists(browser_exe):
            QMessageBox.warning(None, 'Browser Not Found', f'Browser executable not found:\n{browser_exe}')
            return None
        
        browser_type = (browser_type or 'chrome').lower()
        args = [browser_exe]
        
        if browser_type == 'firefox':
            if profile_path:
                args.extend(['-profile', profile_path])
        else:
            if profile_path:
                args.append(f'--user-data-dir={profile_path}')
        
        try:
            proc = subprocess.Popen(args, shell=False)
            self.processes[profile_id] = {
                'proc': proc,
                'pid': proc.pid,
                'type': browser_type,
                'browser_exe': browser_exe,
            }
            return proc.pid
        except Exception as e:
            QMessageBox.critical(None, 'Launch Failed', f'Failed to launch browser:\n{str(e)}')
            return None
    
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
        proc_info = self.processes.get(profile_id)
        if not proc_info:
            return False
        
        browser_type = proc_info.get('type', 'chrome')
        browser_exe = proc_info.get('browser_exe', '')
        hwnds = self._get_candidate_windows(profile_id)
        if hwnds:
            return True
        
        if browser_type == 'firefox':
            if browser_exe:
                for pid in self._find_firefox_processes_by_exe(browser_exe):
                    if self._find_windows_by_pid(pid):
                        return True
            if self._find_windows_by_process_name('firefox.exe'):
                return True
        
        return False
    
    def focus(self, profile_id):
        """Focus browser window (restore if minimized, bring to front if backgrounded)"""
        hwnds = self._get_candidate_windows(profile_id)
        proc_info = self.processes.get(profile_id)
        browser_type = proc_info.get('type', 'chrome') if proc_info else 'chrome'
        browser_exe = proc_info.get('browser_exe', '') if proc_info else ''
        
        if not hwnds and browser_type == 'firefox':
            if browser_exe:
                for pid in self._find_firefox_processes_by_exe(browser_exe):
                    hwnds.extend(self._find_windows_by_pid(pid))
            if not hwnds:
                hwnds = self._find_windows_by_process_name('firefox.exe')
        
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
        hwnds = self._get_candidate_windows(profile_id)
        
        if browser_type == 'firefox':
            if browser_exe:
                extra_pids = self._find_firefox_processes_by_exe(browser_exe)
                for pid in extra_pids:
                    if pid not in pids_to_check:
                        pids_to_check.append(pid)
                        hwnds.extend(self._find_windows_by_pid(pid))
            if not hwnds:
                hwnds = self._find_windows_by_process_name('firefox.exe')
        
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
        return hwnds
    
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
        """Find all windows belonging to processes by name"""
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
