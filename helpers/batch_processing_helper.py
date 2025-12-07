import json
import os
from PySide6.QtCore import Qt, QThread, Signal, QObject, QPropertyAnimation, QEasingCurve, QByteArray
from PySide6.QtGui import QColor
from config import BASE_PATH
import threading
import time

def get_batch_size():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return int(config['batch_size'])

class BatchWorkerSignals(QObject):
    finished = Signal(list)
    progress = Signal(int, int)
    row_status = Signal(int, str)
    api_rolled = Signal(str, str, str)  # api_key, service, model
    timing_updated = Signal(int, int, int, int)  # gen_time, avg_time, longest_time, last_time

class BatchWorker(QThread):
    def __init__(self, api_key, model, batch, service, metadata_func, row_map, parent=None, stop_flag=None, api_keys_list=None, is_rolling_mode=False, current_api_index=0):
        super().__init__(parent)
        self.api_key = api_key
        self.model = model
        self.batch = batch
        self.service = service
        self.metadata_func = metadata_func
        self.row_map = row_map
        self.signals = BatchWorkerSignals()
        self._results = []
        self._errors = []
        self._should_stop = False
        self._external_stop_flag = stop_flag
        self._threads = []
        self._lock = threading.Lock()
        self._completed = 0
        self.api_keys_list = api_keys_list or []
        self.is_rolling_mode = is_rolling_mode
        self.current_api_index = current_api_index  # Use provided index instead of resetting to 0
        self.failed_files = []  # Track files that failed with current API

    def get_current_api_credentials(self):
        if self.is_rolling_mode and self.api_keys_list:
            if self.current_api_index < len(self.api_keys_list):
                api_info = self.api_keys_list[self.current_api_index]
                return api_info['api_key'], api_info['service'], api_info['model']
        return self.api_key, self.service, self.model

    def get_current_api_info_detailed(self):
        """Get detailed API info including note and position"""
        if self.is_rolling_mode and self.api_keys_list:
            if self.current_api_index < len(self.api_keys_list):
                api_info = self.api_keys_list[self.current_api_index]
                api_key = api_info['api_key']
                service = api_info['service']
                model = api_info['model']
                note = api_info.get('note', '')
                
                # Format API key to show last 5 chars
                masked_key = f"***{api_key[-5:]}" if len(api_key) >= 5 else f"***{api_key}"
                
                # Current position
                position = f"{self.current_api_index + 1}/{len(self.api_keys_list)}"
                
                # Build detailed string
                detail_parts = [f"{service} - {model}", f"({masked_key})", position]
                if note and note.strip():
                    detail_parts.append(note.strip())
                
                return " ".join(detail_parts)
        
        # For non-rolling mode, just return basic info
        api_key = self.api_key
        masked_key = f"***{api_key[-5:]}" if api_key and len(api_key) >= 5 else f"***{api_key}" if api_key else "No API"
        return f"{self.service} - {self.model} ({masked_key})"

    def stop(self):
        self._should_stop = True
        if self._external_stop_flag is not None:
            self._external_stop_flag['stop'] = True

    def run(self):
        self._results = []
        self._errors = []
        self._completed = 0
        stop_flag = self._external_stop_flag
        
        if self.is_rolling_mode and self.api_keys_list:
            self._run_with_rolling_apis()
        else:
            self._run_single_api()

    def _run_single_api(self):
        """Run batch with single API (non-rolling mode)"""
        stop_flag = self._external_stop_flag
        threads = []
        results = [None] * len(self.batch)
        errors = [None] * len(self.batch)

        def task_wrapper(idx, row):
            if self._should_stop or (stop_flag and stop_flag.get('stop')):
                return
            try:
                image_path = row[1]
                prompt = None
                result = self.metadata_func(self.api_key, self.model, image_path, prompt, stop_flag)
                with self._lock:
                    if not self._should_stop and not (stop_flag and stop_flag.get('stop')):
                        results[idx] = (idx, result)
            except Exception as e:
                with self._lock:
                    if not self._should_stop and not (stop_flag and stop_flag.get('stop')):
                        errors[idx] = str(e)
            finally:
                with self._lock:
                    self._completed += 1
                    if not self._should_stop and not (stop_flag and stop_flag.get('stop')):
                        self.signals.progress.emit(self._completed, len(self.batch))

        for idx, row in enumerate(self.batch):
            t = threading.Thread(target=task_wrapper, args=(idx, row))
            threads.append(t)
            t.start()

        while self._completed < len(self.batch):
            if self._should_stop or (stop_flag and stop_flag.get('stop')):
                break
            self.msleep(50)

        if self._should_stop or (stop_flag and stop_flag.get('stop')):
            time.sleep(3)
            self._results = []
            self._errors = []
            self.signals.finished.emit([])
            return

        # Ensure ALL batch items have results
        for idx, row in enumerate(self.batch):
            if results[idx] is None:
                image_path = row[1]
                failed_result = {
                    "title": "", "description": "", "tags": "", "category": {},
                    "token_input": 0, "token_output": 0, "token_total": 0,
                    "image_path": image_path, "error_message": "Processing failed - no result generated",
                    "service": self.service, "model": self.model
                }
                results[idx] = (idx, failed_result)
                if errors[idx] is None:
                    errors[idx] = "Processing failed - no result generated"

        self._results = [r for r in results if r is not None]
        self._errors = [e for e in errors if e is not None]
        self.signals.finished.emit(self._errors)

    def _run_with_rolling_apis(self):
        """Run batch with rolling APIs - retry failed files with next API"""
        stop_flag = self._external_stop_flag
        remaining_files = list(enumerate(self.batch))  # (idx, row) pairs
        all_results = [None] * len(self.batch)
        all_errors = [None] * len(self.batch)
        
        api_attempt = 0
        max_api_attempts = len(self.api_keys_list)
        
        while remaining_files and api_attempt < max_api_attempts:
            if self._should_stop or (stop_flag and stop_flag.get('stop')):
                # Add delay like in normal mode to show stopping state
                import time
                time.sleep(3)
                break
                
            # Get current API credentials and detailed info
            current_api_key, current_service, current_model = self.get_current_api_credentials()
            api_detail = self.get_current_api_info_detailed()
            print(f"[ROLLING] Attempt {api_attempt + 1}/{max_api_attempts} using {api_detail}")
            print(f"[ROLLING] Processing {len(remaining_files)} remaining files")
            
            if api_attempt > 0:
                failed_files = [row[1] for _, row in remaining_files]
                print(f"[ROLLING] Retrying failed files: {failed_files[:3]}{'...' if len(failed_files) > 3 else ''}")
            
            # Process remaining files with current API
            threads = []
            batch_results = [None] * len(remaining_files)
            batch_errors = [None] * len(remaining_files)
            completed_count = 0
            
            def task_wrapper(batch_idx, original_idx, row):
                nonlocal completed_count
                if self._should_stop or (stop_flag and stop_flag.get('stop')):
                    return
                try:
                    image_path = row[1]
                    prompt = None
                    
                    # Create service-specific metadata function with timing
                    if current_service == "gemini":
                        from helpers.ai_helper.gemini_helper import generate_metadata_gemini, track_gemini_generation_time
                        import time
                        t0 = time.perf_counter()
                        title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_gemini(current_api_key, current_model, image_path, prompt, stop_flag)
                        t1 = time.perf_counter()
                        duration_ms = int((t1 - t0) * 1000)
                        gen_time, avg_time, longest_time, last_time = track_gemini_generation_time(duration_ms)
                        
                        # Update stats UI via signal
                        self.signals.timing_updated.emit(gen_time, avg_time, longest_time, last_time)
                        
                        result = {
                            "title": title, "description": description, "tags": tags, "category": category, "filetype": filetype,
                            "token_input": token_input, "token_output": token_output, "token_total": token_total,
                            "image_path": image_path, "error_message": error_message,
                            "service": current_service, "model": current_model
                        }
                    elif current_service == "openai":
                        from helpers.ai_helper.openai_helper import generate_metadata_openai, track_openai_generation_time
                        import time
                        t0 = time.perf_counter()
                        title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_openai(current_api_key, current_model, image_path, prompt, stop_flag)
                        t1 = time.perf_counter()
                        duration_ms = int((t1 - t0) * 1000)
                        gen_time, avg_time, longest_time, last_time = track_openai_generation_time(duration_ms)
                        
                        # Update stats UI via signal
                        self.signals.timing_updated.emit(gen_time, avg_time, longest_time, last_time)
                        
                        result = {
                            "title": title, "description": description, "tags": tags, "category": category, "filetype": filetype,
                            "token_input": token_input, "token_output": token_output, "token_total": token_total,
                            "image_path": image_path, "error_message": error_message,
                            "service": current_service, "model": current_model
                        }
                    else:
                        result = {
                            "title": "", "description": "", "tags": "", "category": {},
                            "token_input": 0, "token_output": 0, "token_total": 0,
                            "image_path": image_path, "error_message": f"Unknown service: {current_service}",
                            "service": current_service, "model": current_model
                        }
                    
                    with self._lock:
                        if not self._should_stop and not (stop_flag and stop_flag.get('stop')):
                            batch_results[batch_idx] = (original_idx, result)
                            
                except Exception as e:
                    with self._lock:
                        if not self._should_stop and not (stop_flag and stop_flag.get('stop')):
                            batch_errors[batch_idx] = str(e)
                finally:
                    with self._lock:
                        completed_count += 1
                        total_completed = sum(1 for r in all_results if r is not None) + completed_count
                        if not self._should_stop and not (stop_flag and stop_flag.get('stop')):
                            self.signals.progress.emit(total_completed, len(self.batch))

            # Start threads for current API attempt
            for batch_idx, (original_idx, row) in enumerate(remaining_files):
                t = threading.Thread(target=task_wrapper, args=(batch_idx, original_idx, row))
                threads.append(t)
                t.start()

            # Wait for completion
            while completed_count < len(remaining_files):
                if self._should_stop or (stop_flag and stop_flag.get('stop')):
                    break
                self.msleep(50)

            if self._should_stop or (stop_flag and stop_flag.get('stop')):
                # Add delay like in normal mode to show stopping state
                import time
                time.sleep(3)
                break

            # Process results and determine which files still need retry
            new_remaining_files = []
            for batch_idx, (original_idx, row) in enumerate(remaining_files):
                if batch_results[batch_idx] is not None:
                    # File was processed successfully
                    _, result = batch_results[batch_idx]
                    all_results[original_idx] = batch_results[batch_idx]
                    
                    # Check if result indicates failure that should trigger retry
                    if result.get('error_message') and not result.get('title'):
                        # API call failed, add to retry list if more APIs available
                        if api_attempt < max_api_attempts - 1:
                            new_remaining_files.append((original_idx, row))
                            print(f"[ROLLING] File {row[1]} failed with {current_service}, will retry with next API")
                        else:
                            print(f"[ROLLING] File {row[1]} failed with all APIs")
                    else:
                        print(f"[ROLLING] File {row[1]} succeeded with {current_service}")
                else:
                    # File was not processed at all, add to retry list
                    if api_attempt < max_api_attempts - 1:
                        new_remaining_files.append((original_idx, row))
                        if batch_errors[batch_idx]:
                            all_errors[original_idx] = batch_errors[batch_idx]
            
            remaining_files = new_remaining_files
            
            # Move to next API if there are still failures and more APIs available
            if remaining_files and api_attempt < max_api_attempts - 1:
                self.current_api_index += 1
                next_api_detail = self.get_current_api_info_detailed()
                print(f"[ROLLING] Switching to next API: {next_api_detail}")
                api_info = self.api_keys_list[self.current_api_index]
                self.signals.api_rolled.emit(api_info['api_key'], api_info['service'], api_info['model'])
            
            api_attempt += 1

        # Log final rolling summary
        if self.is_rolling_mode:
            successful_files = sum(1 for r in all_results if r is not None and r[1].get('title'))
            failed_files = len(self.batch) - successful_files
            print(f"[ROLLING] Final summary: {successful_files} successful, {failed_files} failed after {api_attempt} API attempts")

        # Ensure all files have final results
        for idx, row in enumerate(self.batch):
            if all_results[idx] is None:
                image_path = row[1]
                failed_result = {
                    "title": "", "description": "", "tags": "", "category": {},
                    "token_input": 0, "token_output": 0, "token_total": 0,
                    "image_path": image_path, "error_message": "All API keys failed",
                    "service": self.service, "model": self.model
                }
                all_results[idx] = (idx, failed_result)
                if all_errors[idx] is None:
                    all_errors[idx] = "All API keys failed"

        self._results = [r for r in all_results if r is not None]
        self._errors = [e for e in all_errors if e is not None]
        self.signals.finished.emit(self._errors)

def batch_generate_metadata(window):
    if getattr(window, 'is_generating', False):
        return

    # Clean up any stuck processing files from previous runs
    cleanup_stuck_processing_files(window)

    # Detect Rolling APIs mode
    is_rolling_mode = False
    api_keys_list = []
    
    if hasattr(window, "gen_mode_combo"):
        mode_text = window.gen_mode_combo.currentText().lower()
        if "rolling" in mode_text:
            is_rolling_mode = True
            # Get all API keys from database
            all_api_keys = window.db.get_all_api_keys()
            for row in all_api_keys:
                service, api_key, note, last_tested, status, model = row
                if api_key and model and service:  # Only include complete API key entries
                    api_keys_list.append({
                        'service': service.lower(),
                        'api_key': api_key,
                        'model': model,
                        'note': note,
                        'status': status
                    })
            
            if not api_keys_list:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(window, "Rolling APIs", "No valid API keys found in database for Rolling APIs mode.")
                return
            
            print(f"[ROLLING] Found {len(api_keys_list)} API keys for rolling mode")

    # Always fetch API key, model, and service from api_key_section if available
    api_key = None
    model = None
    service = None
    
    if is_rolling_mode and api_keys_list:
        # Use first API key from list for rolling mode
        first_api = api_keys_list[0]
        api_key = first_api['api_key']
        service = first_api['service']
        model = first_api['model']
        print(f"[ROLLING] Starting with API: {service} - {model}")
    elif hasattr(window, "api_key_section"):
        api_key = window.api_key_section.get_current_api_key()
        service = window.api_key_section.get_current_service()
        model = window.api_key_section.get_current_model()
        if service:
            service = service.lower()
    elif hasattr(window, "api_key_combo") and hasattr(window, "api_key_map"):
        idx = window.api_key_combo.currentIndex()
        api_key = window.api_key_combo.currentData() if idx >= 0 else None
        if api_key and api_key in window.api_key_map:
            model = window.api_key_map[api_key].get("model")
            service = window.api_key_map[api_key].get("service")
            if service:
                service = service.lower()
    
    if not api_key or not model or not service:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(window, "API Key", "Please select both API Key and Model first.")
        return

    mode = "all"
    if hasattr(window, "gen_mode_combo"):
        mode_text = window.gen_mode_combo.currentText().lower()
        if "selected" in mode_text:
            mode = "selected"
        elif "failed" in mode_text:
            mode = "failed"
        elif "draft" in mode_text:
            mode = "draft"
        elif "stopped" in mode_text or "resume" in mode_text:
            mode = "stopped"
        elif "rolling" in mode_text:
            mode = "all"  # Rolling APIs processes all files
        else:
            mode = "all"
    
    # Get rows based on pagination-aware approach
    rows = []
    row_map = {}
    
    if mode == "all":
        # For "all" mode, get all files across all pages
        search_text = window.table.search_edit.text() if hasattr(window.table, 'search_edit') else None
        total_count = window.db.get_files_count(search_text)
        if total_count == 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(window, "Generate Metadata", "No files found to process.")
            window.table.progress_bar.setVisible(False)
            return
        
        # Get all files using pagination to avoid memory issues for very large datasets
        page_size = 1000  # Use larger page size for batch processing
        current_page = 1
        while True:
            page_rows = window.db.get_files_paginated(
                page=current_page, 
                page_size=page_size, 
                search_text=search_text
            )
            if not page_rows:
                break
            rows.extend(page_rows)
            current_page += 1
            
    elif mode == "selected":
        # For "selected" mode, only get checked items from current page
        for row_idx in range(window.table.table.rowCount()):
            checkbox_item = window.table.table.item(row_idx, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                # Find the corresponding row in current page data
                if row_idx < len(window.table._current_rows):
                    rows.append(window.table._current_rows[row_idx])
                    
    elif mode == "failed":
        # For "failed" mode, get all failed files across all pages
        search_text = window.table.search_edit.text() if hasattr(window.table, 'search_edit') else None
        total_count = window.db.get_files_count(search_text)
        if total_count == 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(window, "Generate Metadata", "No files found to process.")
            window.table.progress_bar.setVisible(False)
            return
            
        page_size = 1000
        current_page = 1
        while True:
            page_rows = window.db.get_files_paginated(
                page=current_page, 
                page_size=page_size, 
                search_text=search_text
            )
            if not page_rows:
                break
            # Filter only failed files
            for row in page_rows:
                status = row[6] if len(row) > 6 else ""
                if status and status.lower() == "failed":
                    rows.append(row)
            current_page += 1
    
    elif mode == "draft":
        # For "draft" mode, get all files starting from the first draft file
        search_text = window.table.search_edit.text() if hasattr(window.table, 'search_edit') else None
        total_count = window.db.get_files_count(search_text)
        if total_count == 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(window, "Generate Metadata", "No files found to process.")
            window.table.progress_bar.setVisible(False)
            return
            
        page_size = 1000
        current_page = 1
        first_draft_found = False
        
        while True:
            page_rows = window.db.get_files_paginated(
                page=current_page, 
                page_size=page_size, 
                search_text=search_text
            )
            if not page_rows:
                break
            
            # Look for first draft file in this page
            for row in page_rows:
                status = row[6] if len(row) > 6 else ""
                
                # If we haven't found the first draft yet, keep looking
                if not first_draft_found:
                    if status and status.lower() == "draft":
                        first_draft_found = True
                        rows.append(row)
                    # Skip non-draft files until we find the first draft
                    continue
                else:
                    # Once we found the first draft, add all remaining files
                    rows.append(row)
            
            current_page += 1
            
        # If no draft files found, show message
        if not first_draft_found:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(window, "Draft Only", "No draft files found to process.")
            return
    
    elif mode == "stopped":
        # For "stopped" mode, get all files starting from the first stopped file
        search_text = window.table.search_edit.text() if hasattr(window.table, 'search_edit') else None
        total_count = window.db.get_files_count(search_text)
        if total_count == 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(window, "Generate Metadata", "No files found to process.")
            window.table.progress_bar.setVisible(False)
            return
            
        page_size = 1000
        current_page = 1
        first_stopped_found = False
        
        while True:
            page_rows = window.db.get_files_paginated(
                page=current_page, 
                page_size=page_size, 
                search_text=search_text
            )
            if not page_rows:
                break
            
            # Look for first stopped file in this page
            for row in page_rows:
                status = row[6] if len(row) > 6 else ""
                
                # If we haven't found the first stopped yet, keep looking
                if not first_stopped_found:
                    if status and status.lower() == "stopped":
                        first_stopped_found = True
                        rows.append(row)
                    # Skip non-stopped files until we find the first stopped
                    continue
                else:
                    # Once we found the first stopped, add all remaining files
                    rows.append(row)
            
            current_page += 1
            
        # If no stopped files found, show message
        if not first_stopped_found:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(window, "Resume Stopped", "No stopped files found to resume from.")
            return
    
    # Create row mapping for pagination-aware status updates
    for idx, row in enumerate(rows):
        filepath = row[1]
        row_map[filepath] = {
            'batch_index': idx,
            'row_data': row
        }
        
    if mode == "selected" and not rows:
        print("[DEBUG] No rows checked for Selected Only mode.")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(window, "No Files", "No files selected (checkbox) to process.")
        return
    elif mode == "draft" and not rows:
        print("[DEBUG] No draft files found for Draft Only mode.")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(window, "Draft Only", "No draft files found to process.")
        return
    elif mode == "stopped" and not rows:
        print("[DEBUG] No stopped files found for Resume Stopped mode.")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(window, "Resume Stopped", "No stopped files found to resume from.")
        return
    if not rows:
        print("[DEBUG] No rows to process after filtering.")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(window, "No Files", "No files to process.")
        return

    # --- FILE EXISTENCE CHECK BEFORE BATCH ---
    missing_files = []
    for row in rows:
        file_path = row[1]
        if not os.path.isfile(file_path):
            missing_files.append(file_path)
    if missing_files:
        from PySide6.QtWidgets import QMessageBox
        msg = "The following files were not found on disk and the process has been cancelled:\n\n"
        msg += "\n".join(missing_files)
        QMessageBox.critical(window, "File Not Found", msg)
        return
    # --- END FILE EXISTENCE CHECK ---

    # --- WARNING DIALOG FOR > 1000 FILES ---
    if len(rows) >= 1000:
        try:
            from dialogs.api_call_warning_dialog import ApiCallWarningDialog
            from PySide6.QtWidgets import QDialog
            if is_rolling_mode:
                # Custom message for rolling APIs mode
                dialog = ApiCallWarningDialog(window, file_count=len(rows))
                # Modify dialog text for rolling mode if possible
                if hasattr(dialog, 'label'):
                    dialog.label.setText(
                        f"You are about to generate metadata for {len(rows)} files using Rolling APIs mode.\n\n"
                        f"This will use all {len(api_keys_list)} API keys available in your database.\n"
                        "This may consume a significant amount of API credits.\n\n"
                        "Do you want to continue?"
                    )
            else:
                dialog = ApiCallWarningDialog(window, file_count=len(rows))
            result = dialog.exec()
            if result != QDialog.Accepted:
                return
        except Exception as e:
            print(f"[DEBUG] Failed to show ApiCallWarningDialog: {e}")
    # --- END WARNING DIALOG ---

    # Enable error dialog buffering
    try:
        from dialogs.ai_helper_error_code_dialog import invoker
        invoker.enable_buffering()
    except Exception as e:
        print(f"[Batch] Failed to enable error buffering: {e}")

    window.table.progress_bar.setVisible(True)
    window.table.progress_bar.setMinimum(0)
    window.table.progress_bar.setMaximum(len(rows))
    window.table.progress_bar.setValue(0)
    
    # Show initial progress with API info
    if is_rolling_mode and api_keys_list:
        first_api = api_keys_list[0]
        initial_text = window.table.get_progress_format_text("rolling", first_api['service'], first_api['api_key'])
    else:
        initial_text = window.table.get_progress_format_text(mode, service, api_key)
    window.table.set_progress_info(initial_text)
    
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()

    stop_flag = {'stop': False}
    if service == "gemini":
        from helpers.ai_helper.gemini_helper import generate_metadata_gemini, track_gemini_generation_time
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            import time
            t0 = time.perf_counter()
            title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_gemini(api_key, model, image_path, prompt, stop_flag)
            t1 = time.perf_counter()
            duration_ms = int((t1 - t0) * 1000)
            gen_time, avg_time, longest_time, last_time = track_gemini_generation_time(duration_ms)
            if hasattr(window, "stats_section"):
                window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
            if error_message:
                print(f"[Gemini ERROR] {error_message}")
            return {
                "title": title,
                "description": description,
                "tags": tags,
                "category": category,
                "filetype": filetype,
                "token_input": token_input,
                "token_output": token_output,
                "token_total": token_total,
                "image_path": image_path,
                "error_message": error_message
            }
    elif service == "openai":
        from helpers.ai_helper.openai_helper import generate_metadata_openai, track_openai_generation_time
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            import time
            t0 = time.perf_counter()
            title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_openai(api_key, model, image_path, prompt, stop_flag)
            t1 = time.perf_counter()
            duration_ms = int((t1 - t0) * 1000)
            gen_time, avg_time, longest_time, last_time = track_openai_generation_time(duration_ms)
            if hasattr(window, "stats_section"):
                window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
            if error_message:
                print(f"[OpenAI ERROR] {error_message}")
            return {
                "title": title,
                "description": description,
                "tags": tags,
                "category": category,
                "filetype": filetype,
                "token_input": token_input,
                "token_output": token_output,
                "token_total": token_total,
                "image_path": image_path,
                "error_message": error_message
            }
    else:
        print(f"[DEBUG] Unknown service: {service}")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(window, "API Service", f"Unknown service: {service}")
        window.table.progress_bar.setVisible(False)
        window.table.progress_bar.setValue(0)
        window.table.set_progress_info('', visible=False)
        return

    batch_size = get_batch_size()
    total_files = len(rows)
    batches = [rows[i:i+batch_size] for i in range(0, total_files, batch_size)]
    window._batch_processing_state = {
        'batches': batches,
        'current': 0,
        'errors': [],
        'api_key': api_key,
        'model': model,
        'service': service,
        'row_map': row_map,
        'metadata_func': metadata_func,
        'rows': rows,
        'should_stop': False,
        'worker': None,
        'stop_flag': stop_flag,
        'is_rolling_mode': is_rolling_mode,
        'api_keys_list': api_keys_list,
        'mode': mode,
        'current_api_index': 0  # Track current API across batches
    }
    window.is_generating = True
    
    # Start the generation timer for elapsed time calculation
    if hasattr(window, "stats_section"):
        window.stats_section.start_generation_timer()
        # Set the processing target to the total number of files being processed
        window.stats_section.set_processing_target(len(rows))
    
    _set_gen_btn_stop_state(window, True)
    window._gen_total_time_start = time.perf_counter()
    _run_next_batch(window)

def _set_gen_btn_blinking(window, blinking, color=None, text=None):
    if not hasattr(window, "gen_btn"):
        return
    btn = window.gen_btn
    if hasattr(window, "_gen_btn_anim") and window._gen_btn_anim:
        window._gen_btn_anim.stop()
        window._gen_btn_anim = None
    if blinking:
        from PySide6.QtCore import QTimer

        def set_bg_color(bg_color):
            btn.setStyleSheet(f"background-color: {bg_color};")

        color1 = color if color else "rgba(255, 220, 28, 0.3)"
        color2 = "rgba(255, 255, 255, 0.1)"
        window._gen_btn_blink_state = True

        window._gen_btn_last_bg = btn.styleSheet()

        def blink():
            if not hasattr(window, "_gen_btn_blink_state"):
                window._gen_btn_blink_state = True
            window._gen_btn_blink_state = not window._gen_btn_blink_state
            set_bg_color(color1 if window._gen_btn_blink_state else color2)

        window._gen_btn_blink_timer = getattr(window, "_gen_btn_blink_timer", None)
        if window._gen_btn_blink_timer:
            window._gen_btn_blink_timer.stop()
            window._gen_btn_blink_timer.deleteLater()
        from PySide6.QtCore import QTimer
        timer = QTimer(btn)
        timer.timeout.connect(blink)
        timer.start(400)
        window._gen_btn_blink_timer = timer
        set_bg_color(color1)
    else:
        if hasattr(window, "_gen_btn_blink_timer") and window._gen_btn_blink_timer:
            window._gen_btn_blink_timer.stop()
            window._gen_btn_blink_timer.deleteLater()
            window._gen_btn_blink_timer = None
        if hasattr(window, "_gen_btn_last_bg") and window._gen_btn_last_bg:
            btn.setStyleSheet(window._gen_btn_last_bg)
        else:
            btn.setStyleSheet(f"background-color: {color};" if color else "")
    if text:
        btn.setText(text)

def _set_gen_btn_stop_state(window, is_stop, is_stopping=False):
    if not hasattr(window, "gen_btn"):
        return
    import qtawesome as qta
    btn = window.gen_btn
    if is_stopping:
        btn.setText("Stopping Workers")
        btn.setIcon(qta.icon('fa6s.stop'))
        _set_gen_btn_blinking(window, True, "rgba(255, 220, 28, 0.3)", "Stopping Workers")
    elif is_stop:
        btn.setText("Stop Processes")
        btn.setIcon(qta.icon('fa6s.stop'))
        _set_gen_btn_blinking(window, False)
        btn.setStyleSheet("background-color: rgba(204, 0, 0, 0.3);")
        window._gen_btn_last_bg = "background-color: rgba(204, 0, 0, 0.3);"
    else:
        btn.setText("Generate Metadata")
        btn.setIcon(qta.icon('fa6s.wand-magic-sparkles', color='white'))
        _set_gen_btn_blinking(window, False)
        btn.setStyleSheet("background-color: #4e9e20; color: white;")
        window._gen_btn_last_bg = "background-color: #4e9e20; color: white;"

def _run_next_batch(window):
    state = window._batch_processing_state
    if state.get('should_stop', False):
        _on_generation_finished(window, state['errors'], stopped=True)
        return
    if state['current'] >= len(state['batches']):
        _on_generation_finished(window, state['errors'])
        return
    batch = state['batches'][state['current']]
    
    # Get variables from state first
    is_rolling_mode = state.get('is_rolling_mode', False)
    api_keys_list = state.get('api_keys_list', [])
    
    # For rolling mode, use current API from api_keys_list based on current_api_index
    if is_rolling_mode and api_keys_list:
        current_api_index = state.get('current_api_index', 0)
        if current_api_index < len(api_keys_list):
            current_api_info = api_keys_list[current_api_index]
            api_key = current_api_info['api_key']
            service = current_api_info['service']
            model = current_api_info['model']
            # Update state with current API
            state['api_key'] = api_key
            state['service'] = service
            state['model'] = model
            print(f"[BATCH {state['current'] + 1}] Using API: {service} - {model} (***{api_key[-5:] if len(api_key) >= 5 else api_key}) {current_api_index + 1}/{len(api_keys_list)}")
            
            # Update UI to show current API for this batch (only if first batch or different from current UI)
            if hasattr(window, "api_key_section"):
                current_ui_api = window.api_key_section.get_current_api_key()
                if state['current'] == 0 or current_ui_api != api_key:  # Only update if first batch or API changed
                    window.api_key_section.set_current_api_by_details(api_key, service, model)
            
            # Update status bar with current API info
            if hasattr(window, 'statusbar'):
                window.statusbar.set_api_info(service, api_key)
                
            # Update progress label to show current API
            current_mode = state.get('mode', 'all')
            if current_mode == "Rolling APIs":
                label_text = window.table.get_progress_format_text("rolling", service, api_key)
            else:
                label_text = window.table.get_progress_format_text(current_mode, service, api_key)
            window.table.set_progress_info(label_text)
        else:
            # Fallback to original API if index out of range
            api_key = state['api_key']
            service = state['service']
            model = state['model']
    else:
        # Non-rolling mode, use original API
        api_key = state['api_key']
        model = state['model']
        service = state['service']
    
    row_map = state['row_map']
    metadata_func = state['metadata_func']
    rows = state['rows']
    stop_flag = state.get('stop_flag')
    
    batch_indices = []
    table_widget = window.table.table
    for row in batch:
        filepath = row[1]
        # Update status in database to "processing"
        window.db.update_file_status(filepath, "processing")
        
        # Find and update row in current table view
        for row_idx in range(table_widget.rowCount()):
            item = table_widget.item(row_idx, 1)
            if item and item.data(Qt.UserRole) == filepath:
                batch_indices.append(row_idx)
                window.table.set_row_status_color(row_idx, "processing")
                break
    
    worker = BatchWorker(api_key, model, batch, service, metadata_func, row_map, 
                        stop_flag=stop_flag, api_keys_list=api_keys_list, is_rolling_mode=is_rolling_mode, 
                        current_api_index=state.get('current_api_index', 0))
    state['worker'] = worker
    
    def on_api_rolled(new_api_key, new_service, new_model):
        # Update UI to reflect the new API being used
        if hasattr(window, "api_key_section"):
            # Get detailed API info from worker
            worker = state.get('worker')
            if worker and hasattr(worker, 'get_current_api_info_detailed'):
                api_detail = worker.get_current_api_info_detailed()
                print(f"[UI UPDATE] Switching UI to: {api_detail}")
            else:
                # Fallback to basic info
                masked_key = f"***{new_api_key[-5:]}" if len(new_api_key) >= 5 else f"***{new_api_key}"
                print(f"[UI UPDATE] Switching UI to: {new_service} - {new_model} ({masked_key})")
            # Update API key section only during rolling (not every batch)
            window.api_key_section.set_current_api_by_details(new_api_key, new_service, new_model)
        
        # Update state
        state['api_key'] = new_api_key
        state['service'] = new_service  
        state['model'] = new_model
        # Update current_api_index in state for next batch
        worker = state.get('worker')
        if worker and hasattr(worker, 'current_api_index'):
            state['current_api_index'] = worker.current_api_index
        
        # Update status bar or other UI elements to show API rolling
        if hasattr(window, 'statusbar'):
            window.statusbar.showMessage(f"Rolling to: {new_service} - {new_model} (retrying failed files)", 3000)
            window.statusbar.set_api_info(new_service, new_api_key)
        
        # Update progress label to show new API realtime
        current_mode = state.get('mode', 'all')
        if current_mode == "Rolling APIs" or is_rolling_mode:
            label_text = window.table.get_progress_format_text("rolling", new_service, new_api_key)
        else:
            label_text = window.table.get_progress_format_text(current_mode, new_service, new_api_key)
        window.table.set_progress_info(label_text)
        
        # Force UI update
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
    
    def on_progress(cur, total):
        if state.get('should_stop', False) or (stop_flag and stop_flag.get('stop')):
            window.table.set_progress_info('Stopping...')
            window.table.progress_bar.setMinimum(0)
            window.table.progress_bar.setMaximum(0)
            _set_gen_btn_stop_state(window, False, is_stopping=True)
        else:
            rolling_text = " (Rolling APIs)" if is_rolling_mode else ""
            current_mode = state.get('mode', 'all')
            if is_rolling_mode:
                # Show more detailed progress for rolling mode
                current_api_index = state.get('current_api_index', 0)
                api_count = len(api_keys_list)
                if current_api_index < len(api_keys_list):
                    current_api_info = api_keys_list[current_api_index]
                else:
                    current_api_info = api_keys_list[0] if api_keys_list else {}
                current_service = current_api_info.get('service', 'Unknown')
                current_api_key = current_api_info.get('api_key', '')
                label_text = window.table.get_progress_format_text("rolling", current_service, current_api_key)
                # Update status bar with current API info
                if hasattr(window, 'statusbar'):
                    window.statusbar.set_api_info(current_service, current_api_key)
            else:
                # Show current API info for normal mode too
                current_service = state.get('service', '')
                current_api_key = state.get('api_key', '')
                label_text = window.table.get_progress_format_text(current_mode, current_service, current_api_key)
                # Show API info for non-rolling mode
                if hasattr(window, 'statusbar'):
                    window.statusbar.set_api_info(current_service, current_api_key)
            window.table.set_progress_info(label_text)
            window.table.progress_bar.setMinimum(0)
            window.table.progress_bar.setMaximum(len(rows))
            window.table.progress_bar.setValue(state['current'] * get_batch_size() + cur)
            _set_gen_btn_stop_state(window, True)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
    def on_finished(errors):
        if state.get('should_stop', False) or (stop_flag and stop_flag.get('stop')):
            for row in batch:
                filepath = row[1]
                window.db.update_file_status(filepath, "stopped")
                for row_idx in range(table_widget.rowCount()):
                    item = table_widget.item(row_idx, 1)
                    if item and item.data(Qt.UserRole) == filepath:
                        window.table.set_row_status_color(row_idx, "stopped")
            window.table.refresh_table()
            window.table.set_progress_info('Stopped')
            window.table.progress_bar.setValue(0)
            window.table.progress_bar.setMinimum(0)
            window.table.progress_bar.setMaximum(1)
            window.table.progress_bar.setVisible(True)
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            _on_generation_finished(window, state['errors'], stopped=True)
            return
        cache_results = worker._results
        
        # Process ALL results (both successful and failed)
        for idx, result in cache_results:
            if not isinstance(result, dict):
                continue
            image_path = result.get("image_path")
            title = result.get("title")
            description = result.get("description")
            tags = result.get("tags")
            token_input = result.get("token_input")
            token_output = result.get("token_output")
            token_total = result.get("token_total")
            category = result.get("category")
            filetype = result.get("filetype")
            result_service = result.get("service", service)
            result_model = result.get("model", model)
            error_message = result.get("error_message", "")
            
            if category is not None:
                file_id = None
                for row in batch:
                    if row[1] == image_path:
                        file_id = row[0]
                        break
                if file_id is not None and isinstance(category, dict) and len(category) > 0:
                    window.db.save_category_mapping(file_id, category)
            
            # Save filetype if provided and valid
            if filetype and filetype in ["Photo", "Illustration"]:
                file_id = None
                for row in batch:
                    if row[1] == image_path:
                        file_id = row[0]
                        break
                if file_id is not None:
                    # Clear existing file types for this file first
                    window.db.delete_file_types_for_file(file_id)
                    # Add new file type
                    window.db.add_file_type(file_id, filetype)
            
            # Determine status based on title and error
            final_status = "success" if title and not error_message else "failed"
            window.db.update_metadata(image_path, title, description, tags, status=final_status)
            
            # Insert token stats for calls that produced content, even if there was an initial error
            # This handles rolling API cases where first API failed but second succeeded
            if token_total > 0 and title:  # If we got content and tokens were used
                window.db.insert_api_token_stats(image_path, result_service, result_model, token_input, token_output, token_total)
            
            # Update UI row colors in current table view (if visible)
            for row_idx in range(table_widget.rowCount()):
                item = table_widget.item(row_idx, 1)
                if item and item.data(Qt.UserRole) == image_path:
                    window.table.set_row_status_color(row_idx, final_status)
                    break
        
        update_token_stats_ui(window)
        window.table.refresh_table()
        
        # Update stats for real-time estimation
        if hasattr(window.table, '_emit_stats'):
            window.table._emit_stats()
        
        # Update progress display
        current_mode = state.get('mode', 'all')
        if is_rolling_mode:
            current_api_index = state.get('current_api_index', 0)
            if current_api_index < len(api_keys_list):
                current_api_info = api_keys_list[current_api_index]
            else:
                current_api_info = api_keys_list[0] if api_keys_list else {}
            current_service = current_api_info.get('service', 'Unknown')
            current_api_key = current_api_info.get('api_key', '')
            label_text = window.table.get_progress_format_text("rolling", current_service, current_api_key)
        else:
            # Show current API info for normal mode too
            current_service = state.get('service', '')
            current_api_key = state.get('api_key', '')
            label_text = window.table.get_progress_format_text(current_mode, current_service, current_api_key)
        window.table.set_progress_info(label_text)
        window.table.progress_bar.setMinimum(0)
        window.table.progress_bar.setMaximum(len(rows))
        window.table.progress_bar.setValue(state['current'] * get_batch_size() + len(batch))  # Update to show completed batch
        _set_gen_btn_stop_state(window, True)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        state['current'] += 1
        if errors:
            state['errors'].extend(errors)
        _run_next_batch(window)
    
    def on_timing_updated(gen_time, avg_time, longest_time, last_time):
        if hasattr(window, "stats_section"):
            window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
    
    worker.signals.api_rolled.connect(on_api_rolled)
    worker.signals.progress.connect(on_progress)
    worker.signals.finished.connect(on_finished)
    worker.signals.timing_updated.connect(on_timing_updated)
    worker.start()

def stop_generate_metadata(window):
    state = getattr(window, '_batch_processing_state', None)
    if state and state.get('worker'):
        worker = state['worker']
        if worker.isRunning():
            print("[STOP] Stopping batch worker thread...")
            state['should_stop'] = True
            stop_flag = state.get('stop_flag')
            if stop_flag is not None:
                stop_flag['stop'] = True
            table_widget = window.table.table
            for row in range(table_widget.rowCount()):
                status_item = table_widget.item(row, 8)
                if status_item and status_item.text().lower() == "processing":
                    window.table.set_row_status_color(row, "stopping")
            window.table.set_progress_info('Stopping...')
            window.table.progress_bar.setMinimum(0)
            window.table.progress_bar.setMaximum(0)
            window.table.progress_bar.setVisible(True)
            _set_gen_btn_stop_state(window, False, is_stopping=True)
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            worker.stop()
    
    # Clear error buffer saat stop
    try:
        from dialogs.ai_helper_error_code_dialog import invoker
        invoker.clear_buffer()
        invoker.disable_buffering()
    except Exception as e:
        print(f"[STOP] Failed to clear error buffer: {e}")
    
    window.is_generating = False
    
    # Stop the estimation timer but keep the stats visible
    if hasattr(window, "stats_section"):
        window.stats_section.stop_estimation_timer()
    
    window.table.refresh_table()
    print("[STOP] Metadata generation stopped and UI reset.")

def _on_generation_finished(window, errors, stopped=False):
    window.is_generating = False
    
    # Disable buffering dan flush semua error yang terkumpul
    try:
        from dialogs.ai_helper_error_code_dialog import invoker
        invoker.disable_buffering()
        invoker.flush_all()
    except Exception as e:
        print(f"[Batch] Failed to flush error dialogs: {e}")
    
    # Stop the estimation timer but keep the final stats visible
    if hasattr(window, "stats_section"):
        window.stats_section.stop_estimation_timer()
    
    _set_gen_btn_stop_state(window, False)
    table_widget = window.table.table
    
    # Check if rolling mode was used
    state = getattr(window, '_batch_processing_state', {})
    is_rolling_mode = state.get('is_rolling_mode', False)
    
    # Clean up any remaining "processing" statuses
    cleanup_count = cleanup_stuck_processing_files(window)
    
    if stopped:
        for row in range(table_widget.rowCount()):
            status_item = table_widget.item(row, 8)
            if status_item and status_item.text().lower() == "stopping":
                filepath_item = table_widget.item(row, 1)
                if filepath_item:
                    filepath = filepath_item.data(Qt.UserRole) or filepath_item.text()
                    window.db.update_file_status(filepath, "stopped")
                window.table.set_row_status_color(row, "stopped")
        window.table.set_progress_info('Stopped')
        window.table.progress_bar.setValue(0)
        window.table.progress_bar.setMinimum(0)
        window.table.progress_bar.setMaximum(1)
        window.table.progress_bar.setVisible(True)
        # Clear API info from status bar when stopped
        if hasattr(window, 'statusbar'):
            window.statusbar.set_api_info()
    else:
        completion_text = 'Done'
        if is_rolling_mode:
            completion_text += ' (Rolling APIs)'
        window.table.set_progress_info(completion_text)
        window.table.progress_bar.setMaximum(1)
        window.table.progress_bar.setValue(1)
        window.table.progress_bar.setVisible(True)
        # Clear API info from status bar when done
        if hasattr(window, 'statusbar'):
            window.statusbar.set_api_info()
    
    if hasattr(window, "stats_section") and hasattr(window, "_gen_total_time_start"):
        total_time_ms = int((time.perf_counter() - window._gen_total_time_start) * 1000)
        window.stats_section.update_total_time(total_time_ms)
    
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    window.table.refresh_table()
    update_token_stats_ui(window)
    
    if errors:
        print("[Batch Errors]")
        for err in errors:
            print(err)
    
    # Show completion message for rolling mode
    if is_rolling_mode and not stopped:
        if hasattr(window, 'statusbar'):
            api_count = len(state.get('api_keys_list', []))
            window.statusbar.showMessage(f"Rolling APIs completed using {api_count} API keys", 5000)
    
    print("[CLEANUP] Generation finished cleanup completed.")

def update_token_stats_ui(window):
    if hasattr(window, "stats_section") and hasattr(window.stats_section, "update_token_stats"):
        token_input, token_output, token_total = window.db.get_token_stats_sum()
        window.stats_section.update_token_stats(token_input, token_output, token_total)

def cleanup_stuck_processing_files(window):
    """Clean up any files that are stuck in 'processing' status"""
    print("[CLEANUP] Checking for stuck processing files...")
    table_widget = window.table.table
    cleanup_count = 0
    
    for row_idx in range(table_widget.rowCount()):
        status_item = table_widget.item(row_idx, 8)
        if status_item and status_item.text().lower() == "processing":
            filepath_item = table_widget.item(row_idx, 1)
            if filepath_item:
                filepath = filepath_item.data(Qt.UserRole) or filepath_item.text()
                print(f"[CLEANUP] Cleaning stuck processing file: {filepath}")
                # Update database to failed status
                window.db.update_file_status(filepath, "failed")
                # Update UI
                window.table.set_row_status_color(row_idx, "failed")
                cleanup_count += 1
    
    if cleanup_count > 0:
        print(f"[CLEANUP] Cleaned up {cleanup_count} stuck processing files")
        window.table.refresh_table()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
    else:
        print("[CLEANUP] No stuck processing files found")
    
    return cleanup_count
