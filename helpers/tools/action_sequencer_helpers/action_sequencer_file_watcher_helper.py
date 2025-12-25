import os
import time
from pathlib import Path
from config import BASE_PATH
import datetime
import re


class ActionSequencerFileWatcher:
    def __init__(self, output_path, config):
        self.output_path = output_path
        self.config = config
        self.timeout = config.get('watch_timeout', 30)
        self.poll_interval = config.get('watch_poll_interval', 1)
        self.stable_duration = config.get('file_stable_duration', 1)
        self.supported_extensions = ['.ai', '.psd', '.png', '.eps', '.jpg', '.jpeg', '.svg', '.pdf', '.tif', '.tiff']
        
    def watch_for_file(self, expected_filename=None, existing_files=None, stop_check=None):
        """Watch output folder for new file creation
        
        Args:
            expected_filename: Expected output filename (optional)
            existing_files: Set of existing files before action (for detecting new files)
            stop_check: Optional callable returning True if watch should stop (e.g., user cancelled)
        
        Returns:
            str: Path to detected output file, or None if timeout or stopped
        """
        try:
            if not os.path.isabs(self.output_path):
                self.output_path = os.path.abspath(os.path.join(BASE_PATH, self.output_path))
        except Exception:
            self.output_path = os.path.abspath(self.output_path)

        if not os.path.exists(self.output_path):
            msg = f"Output path does not exist: {self.output_path}"
            print(msg)
            self._log(msg)
            return None
        
        start_time = time.time()
        
        if existing_files is None:
            existing_files = set(self._get_all_files())
        
        msg = f"Watching for new file in: {self.output_path}"
        print(msg)
        self._log(msg)
        msg = f"Timeout: {self.timeout} seconds; Poll interval: {self.poll_interval} seconds; file stable duration: {self.stable_duration} seconds"
        print(msg)
        self._log(msg)
        if expected_filename:
            if isinstance(expected_filename, (list, tuple, set)):
                variants = list(expected_filename)
            else:
                variants = self.build_expected_variants(expected_filename, None)
            msg = f"Expected filename variants: {variants}"
            print(msg)
            self._log(msg)

            expected_set = set(variants)
            def _norm(s):
                return re.sub(r"[^0-9a-z]+", '', s.lower())
            normalized_expected = {_norm(v) for v in variants} 

            detected_file = None

            while time.time() - start_time < self.timeout:
                current_files = set(self._get_all_files())
                new_files = current_files - existing_files
                self._log(f"Scan found {len(current_files)} supported files; {len(new_files)} new files")

                if new_files:
                    new_names = [Path(n).name for n in new_files]
                    self._log(f"New files detected: {new_names}")

                    for new_file in new_files:
                        name = Path(new_file).name
                        if name in expected_set:
                            detected_file = new_file
                            self._log(f"Matched by direct filename: {name}")
                            break
                        if name.lower() in expected_set:
                            detected_file = new_file
                            self._log(f"Matched by case-insensitive filename: {name}")
                            break
                        if _norm(name) in normalized_expected:
                            detected_file = new_file
                            self._log(f"Matched by normalized filename: {name}")
                            break

                if not detected_file:
                    for cf in current_files:
                        name = Path(cf).name
                        if name in expected_set:
                            detected_file = cf
                            self._log(f"Matched by direct filename (existing files): {name}")
                            break
                        if name.lower() in expected_set:
                            detected_file = cf
                            self._log(f"Matched by case-insensitive filename (existing files): {name}")
                            break
                        if _norm(name) in normalized_expected:
                            detected_file = cf
                            self._log(f"Matched by normalized filename (existing files): {name}")
                            break

                if detected_file:
                    if self._is_file_stable(detected_file):
                        msg = f"Found expected file: {detected_file}"
                        print(msg)
                        self._log(msg)
                        return detected_file
                    else:
                        msg = f"File found but still being written: {Path(detected_file).name}"
                        print(msg)
                        self._log(msg)

                if expected_filename:
                    self._log(f"Waiting for expected filename: {variants}")

                try:
                    if stop_check and callable(stop_check) and stop_check():
                        msg = "Watch aborted by stop request"
                        print(msg)
                        self._log(msg)
                        return None
                except Exception as e:
                    self._log(f"stop_check callable raised: {e}")

                time.sleep(self.poll_interval)
        
        elapsed = time.time() - start_time
        if expected_filename:
            msg = f"File watch timeout after {elapsed:.1f} seconds while waiting for: {expected_filename}"
        else:
            msg = f"File watch timeout after {elapsed:.1f} seconds"
        print(msg)
        self._log(msg)
        return None
    
    def _is_file_stable(self, file_path, stable_duration=None):
        """Check if file size is stable (not being written)
        
        Args:
            file_path: Path to file to check
            stable_duration: How long file size must remain unchanged (seconds). If None, uses configured default.
        
        Returns:
            bool: True if file size is stable
        """
        try:
            if stable_duration is None:
                stable_duration = self.stable_duration
            if not os.path.exists(file_path):
                return False

            size1 = os.path.getsize(file_path)
            time.sleep(stable_duration)

            if not os.path.exists(file_path):
                return False

            size2 = os.path.getsize(file_path)
            return size1 == size2 and size1 > 0
        except Exception as e:
            msg = f"Error checking file stability: {e}"
            print(msg)
            self._log(msg)
            return False
    
    def _get_all_files(self):
        """Get all supported files in output directory"""
        files = []
        try:
            for root, dirs, filenames in os.walk(self.output_path):
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in self.supported_extensions:
                        files.append(os.path.join(root, filename))
        except Exception as e:
            msg = f"Error scanning output directory: {e}"
            print(msg)
            self._log(msg)
        
        self._log(f"_get_all_files returning {len(files)} files")
        return files
    
    def get_existing_files_snapshot(self):
        """Get snapshot of existing files before running actions"""
        files = set(self._get_all_files())
        self._log(f"Existing files snapshot: {len(files)} entries")
        return files
    
    def build_expected_filename(self, source_filename, export_format=None):
        """Build expected output filename based on config
        
        Args:
            source_filename: Source file name (without path)
            export_format: Export format if Export action (PNG, EPS, etc), None to use source extension
        
        Returns:
            str: Expected output filename with prefix/suffix applied
        """
        prefix = self.config.get('output_prefix', '')
        suffix = self.config.get('output_suffix', '')

        name_without_ext = os.path.splitext(source_filename)[0]

        if export_format:
            ext = '.' + export_format.lower()
            if ext == '.jpeg':
                ext = '.jpg'
        else:
            ext = os.path.splitext(source_filename)[1]

        expected_name = f"{prefix}{name_without_ext}{suffix}{ext}"
        return expected_name

    def build_expected_variants(self, source_filename, export_format=None):
        """Return a list of plausible expected output filename variants to match exporter behavior.

        The exporter (Photoshop/Illustrator) may sanitize the document name when saving
        (e.g., replacing spaces/punctuation with hyphens). This helper returns the original
        expected name plus simple sanitized variants to improve detection reliability.

        Returns:
            list[str]: Ordered list of candidate filenames (most-likely first)
        """
        base = self.build_expected_filename(source_filename, export_format)
        name, ext = os.path.splitext(base)

        candidates = [base]

        core = os.path.splitext(source_filename)[0]
        prefix = self.config.get('output_prefix', '')
        suffix = self.config.get('output_suffix', '')
        core_full = f"{prefix}{core}{suffix}"

        hyphen = re.sub(r"[^\w]+", '-', core_full)
        hyphen = re.sub(r"-+", '-', hyphen).strip('-')
        candidates.append(f"{hyphen}{ext}")

        spaces_to_hyphen = re.sub(r"\s+", '-', core_full)
        spaces_to_hyphen = re.sub(r"-+", '-', spaces_to_hyphen).strip('-')
        candidates.append(f"{spaces_to_hyphen}{ext}")

        removed = re.sub(r"[\,\.;:]+", '', core_full)
        removed = re.sub(r"\s+", ' ', removed).strip()
        candidates.append(f"{removed}{ext}")

        under = re.sub(r"[^\w]+", '_', core_full)
        under = re.sub(r"_+", '_', under).strip('_')
        candidates.append(f"{under}{ext}")

        lower_candidates = [c.lower() for c in candidates]
        for lc in lower_candidates:
            candidates.append(lc)

        seen = set()
        uniques = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                uniques.append(c)

        self._log(f"Generated filename variants: {uniques}")
        return uniques
    
    @staticmethod
    def cleanup_jsx_files(*jsx_directories):
        """Clean up temporary JSX files after batch processing
        
        Args:
            *jsx_directories: Variable number of directory paths to clean
        """
        for jsx_dir in jsx_directories:
            if not jsx_dir or not os.path.exists(jsx_dir):
                continue
            
            try:
                for root, dirs, files in os.walk(jsx_dir):
                    for file in files:
                        if file.endswith('.jsx'):
                            file_path = os.path.join(root, file)
                            try:
                                os.remove(file_path)
                                print(f"Cleaned up JSX file: {file}")
                            except Exception as e:
                                print(f"Failed to remove {file}: {e}")
            except Exception as e:
                print(f"Error cleaning up directory {jsx_dir}: {e}")

    def _log(self, msg: str):
        """Print a timestamped debug message to console (no file logging)."""
        try:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"{timestamp} - {msg}")
        except Exception:
            pass
