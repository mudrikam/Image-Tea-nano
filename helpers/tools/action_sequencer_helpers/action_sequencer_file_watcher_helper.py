import os
import time
from pathlib import Path


class ActionSequencerFileWatcher:
    def __init__(self, output_path, config):
        self.output_path = output_path
        self.config = config
        self.timeout = config.get('watch_timeout', 30)
        self.supported_extensions = ['.ai', '.psd', '.png', '.eps', '.jpg', '.jpeg', '.svg', '.pdf', '.tif', '.tiff']
        
    def watch_for_file(self, expected_filename=None, existing_files=None):
        """Watch output folder for new file creation
        
        Args:
            expected_filename: Expected output filename (optional)
            existing_files: Set of existing files before action (for detecting new files)
        
        Returns:
            str: Path to detected output file, or None if timeout
        """
        if not os.path.exists(self.output_path):
            print(f"Output path does not exist: {self.output_path}")
            return None
        
        start_time = time.time()
        
        if existing_files is None:
            existing_files = set(self._get_all_files())
        
        print(f"Watching for new file in: {self.output_path}")
        print(f"Timeout: {self.timeout} seconds")
        if expected_filename:
            print(f"Expected filename: {expected_filename}")
        
        detected_file = None
        
        while time.time() - start_time < self.timeout:
            current_files = set(self._get_all_files())
            new_files = current_files - existing_files
            
            if new_files:
                if expected_filename:
                    for new_file in new_files:
                        if Path(new_file).name == expected_filename:
                            detected_file = new_file
                            break
                else:
                    detected_file = sorted(new_files)[0]
                
                if detected_file:
                    if self._is_file_stable(detected_file):
                        print(f"Found expected file: {detected_file}")
                        return detected_file
                    else:
                        print(f"File found but still being written: {Path(detected_file).name}")
            
            time.sleep(0.5)
        
        elapsed = time.time() - start_time
        print(f"File watch timeout after {elapsed:.1f} seconds")
        return None
    
    def _is_file_stable(self, file_path, stable_duration=0.3):
        """Check if file size is stable (not being written)
        
        Args:
            file_path: Path to file to check
            stable_duration: How long file size must remain unchanged (seconds)
        
        Returns:
            bool: True if file size is stable
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            size1 = os.path.getsize(file_path)
            time.sleep(stable_duration)
            
            if not os.path.exists(file_path):
                return False
                
            size2 = os.path.getsize(file_path)
            return size1 == size2 and size1 > 0
        except:
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
            print(f"Error scanning output directory: {e}")
        
        return files
    
    def get_existing_files_snapshot(self):
        """Get snapshot of existing files before running actions"""
        return set(self._get_all_files())
    
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
