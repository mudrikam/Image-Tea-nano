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
        
    def watch_for_multiple_files(self, expected_filenames, existing_files=None, stop_check=None):
        """Watch output folder for multiple file creation (multiple exports)
        
        Args:
            expected_filenames: List of expected output filenames
            existing_files: Set of existing files before action (for detecting new files)
            stop_check: Optional callable returning True if watch should stop (e.g., user cancelled)
        
        Returns:
            list: List of detected output file paths, or empty list if timeout/stopped
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
            return []
        
        start_time = time.time()
        
        if existing_files is None:
            existing_files = set(self._get_all_files())
        
        msg = f"Watching for {len(expected_filenames)} files in: {self.output_path}"
        print(msg)
        self._log(msg)
        self._log(f"DEBUG: Expected filenames list: {expected_filenames}")
        
        all_expected_variants = {}
        for expected in expected_filenames:
            if isinstance(expected, (list, tuple, set)):
                variants = list(expected)
            else:
                variants = self.build_expected_variants(expected, None)
            all_expected_variants[expected] = variants
            msg = f"Expected variants for '{expected}': {variants}"
            print(msg)
            self._log(msg)
        
        detected_files = {}
        
        def _norm(s):
            return re.sub(r"[^0-9a-z]+", '', s.lower())
        
        # Debug: log new files yang muncul untuk troubleshooting
        logged_new_files = set()
        
        while time.time() - start_time < self.timeout:
            current_files = set(self._get_all_files())
            new_files = current_files - existing_files
            
            # Debug: log new files yang belum pernah di-log
            for new_file in new_files:
                if new_file not in logged_new_files:
                    name = Path(new_file).name
                    self._log(f"DEBUG: New file detected: {name}")
                    logged_new_files.add(new_file)
            
            # Track which files are still waiting
            still_waiting = []
            
            for expected, variants in all_expected_variants.items():
                if expected in detected_files:
                    continue
                
                still_waiting.append(expected)
                
                expected_set = set(variants)
                normalized_expected = {_norm(v) for v in variants}
                
                # Check both new files AND existing files (for files created before snapshot)
                files_to_check = new_files.union(current_files)
                
                for file_path in files_to_check:
                    name = Path(file_path).name
                    norm_name = _norm(name)
                    
                    # Skip if already detected
                    if file_path in detected_files.values():
                        continue
                    
                    # Check if matches any variant
                    matched = False
                    if name in expected_set:
                        matched = True
                    elif name.lower() in expected_set:
                        matched = True
                    elif norm_name in normalized_expected:
                        matched = True
                    
                    if matched:
                        if self._is_file_stable(file_path):
                            detected_files[expected] = file_path
                            msg = f"Detected file {len(detected_files)}/{len(expected_filenames)}: {name}"
                            print(msg)
                            self._log(msg)
                            break
            
            # Log what we're still waiting for
            if still_waiting and len(detected_files) < len(expected_filenames):
                elapsed = time.time() - start_time
                self._log(f"Still waiting for {len(still_waiting)} file(s) [{elapsed:.1f}s]: {still_waiting}")
            
            if len(detected_files) == len(expected_filenames):
                msg = f"All {len(expected_filenames)} files detected successfully"
                print(msg)
                self._log(msg)
                return list(detected_files.values())
            
            try:
                if stop_check and callable(stop_check) and stop_check():
                    msg = "Watch aborted by stop request"
                    print(msg)
                    self._log(msg)
                    return list(detected_files.values())
            except Exception as e:
                self._log(f"stop_check callable raised: {e}")
            
            time.sleep(self.poll_interval)
        
        elapsed = time.time() - start_time
        msg = f"Watch timeout after {elapsed:.1f}s. Found {len(detected_files)}/{len(expected_filenames)} files"
        print(msg)
        self._log(msg)
        return list(detected_files.values())
    
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
        
        Smart collision handling: checks existing files to predict next numbering (_001, _002, etc.)

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

        # Smart collision detection: check existing files to predict next numbering
        base_candidates = candidates.copy()
        collision_variants = self._get_smart_collision_variants(base_candidates, ext)
        
        all_variants = candidates + collision_variants
        
        seen = set()
        uniques = []
        for c in all_variants:
            if c not in seen:
                seen.add(c)
                uniques.append(c)

        self._log(f"Generated filename variants (smart collision): {uniques}")
        return uniques
    
    def _get_smart_collision_variants(self, base_names, extension):
        """Smart collision detection: check existing files and predict next numbering
        
        Args:
            base_names: List of base filenames to check (without extension)
            extension: File extension to check
            
        Returns:
            list: Smart collision variants based on existing files
        """
        variants = []
        
        try:
            # Get ALL files in output directory (not just new files from snapshot)
            # Because JSX checks ALL files when determining collision numbering
            existing_files = []
            if os.path.exists(self.output_path):
                for item in os.listdir(self.output_path):
                    item_path = os.path.join(self.output_path, item)
                    if os.path.isfile(item_path):
                        existing_files.append(item)
            
            self._log(f"Smart collision: Scanning {len(existing_files)} existing files in output folder")
            
            # For each base name, find highest numbering across ALL sanitization variants
            for base_name in base_names:
                name_part = os.path.splitext(base_name)[0]
                
                # Check if base file exists (without numbering) - check all sanitization variants
                base_exists = False
                for existing in existing_files:
                    existing_name = os.path.splitext(existing)[0]
                    existing_ext = os.path.splitext(existing)[1].lower()
                    
                    # Match if extension matches and base name matches (case-insensitive, ignoring special chars)
                    if existing_ext == extension.lower():
                        # Normalize both names: remove all non-alphanumeric chars and compare
                        normalized_existing = re.sub(r'[^a-z0-9]', '', existing_name.lower())
                        normalized_base = re.sub(r'[^a-z0-9]', '', name_part.lower())
                        
                        if normalized_existing == normalized_base:
                            base_exists = True
                            self._log(f"Smart collision: Base file exists: {existing}")
                            break
                
                # Find ALL numbered variants across different sanitization patterns
                # Extract the "core" without special chars for loose matching
                core_normalized = re.sub(r'[^a-z0-9]', '', name_part.lower())
                max_num = 0
                
                for filename in existing_files:
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext != extension.lower():
                        continue
                    
                    # Check if this file is a numbered variant of our base
                    # Pattern: <anything>_<digits><extension>
                    match = re.match(r'^(.+)_(\d{3})' + re.escape(extension) + r'$', filename, re.IGNORECASE)
                    if match:
                        file_base = match.group(1)
                        file_num = int(match.group(2))
                        
                        # Normalize and compare
                        file_base_normalized = re.sub(r'[^a-z0-9]', '', file_base.lower())
                        
                        if file_base_normalized == core_normalized:
                            if file_num > max_num:
                                max_num = file_num
                            self._log(f"Found existing numbered file: {filename} (num={file_num})")
                
                # Determine next expected number
                if base_exists or max_num > 0:
                    # Either base exists or numbered files exist
                    next_num = max_num + 1
                    next_num_str = f"{'000' + str(next_num)}"[-3:]
                    next_variant = f"{name_part}_{next_num_str}{extension}"
                    variants.append(next_variant)
                    self._log(f"Smart collision: Base exists={base_exists}, max_num={max_num}, expecting: {next_variant}")
                # else: no existing files, base name already in candidates
                
        except Exception as e:
            self._log(f"Error in smart collision detection: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            # Fallback to simple _001 variant
            for base_name in base_names:
                name_part = os.path.splitext(base_name)[0]
                variants.append(f"{name_part}_001{extension}")
        
        return variants
    
    @staticmethod
    def cleanup_jsx_files(*jsx_directories):
        """Clean up temporary JSX files after batch processing.

        Args:
            *jsx_directories: Variable number of directory paths to clean
        """
        preset_pattern = re.compile(r'^preset_.*\.jsx$', re.IGNORECASE)

        for jsx_dir in jsx_directories:
            if not jsx_dir or not os.path.exists(jsx_dir):
                continue

            try:
                removed_count = 0
                skipped = []
                for root, dirs, files in os.walk(jsx_dir):
                    for file in files:
                        if not file.lower().endswith('.jsx'):
                            continue
                        if not preset_pattern.match(file):
                            skipped.append(file)
                            continue

                        file_path = os.path.join(root, file)
                        attempts = 0
                        while attempts < 3:
                            try:
                                os.remove(file_path)
                                print(f"Cleaned up JSX file: {file}")
                                removed_count += 1
                                break
                            except PermissionError:
                                attempts += 1
                                time.sleep(0.2)
                            except Exception as e:
                                print(f"Failed to remove {file}: {e}")
                                break

                if removed_count > 0:
                    print(f"Removed {removed_count} preset JSX file(s) from {jsx_dir}")
                else:
                    print(f"No preset JSX files removed from {jsx_dir}")
                    if skipped:
                        print(f"Skipped {len(skipped)} non-preset JSX files (e.g. resident files): {skipped}")
            except Exception as e:
                print(f"Error cleaning up directory {jsx_dir}: {e}")

    def _log(self, msg: str):
        """Print a timestamped debug message to console (no file logging)."""
        try:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"{timestamp} - {msg}")
        except Exception:
            pass
