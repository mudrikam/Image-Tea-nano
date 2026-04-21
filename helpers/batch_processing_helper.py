import json
import os
import time
import random
import threading
from PySide6.QtCore import Qt, QThread, Signal, QObject, QPropertyAnimation, QEasingCurve, QByteArray, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox, QApplication, QDialog
from dialogs.member_limit_dialog import show_member_limit_dialog
from dialogs.members.member_secret_manager_dialog import MemberSecretManagerDialog
import qtawesome as qta
from config import BASE_PATH
from dialogs.get_api_key_dialog import GetApiKeyDialog
from dialogs.api_call_warning_dialog import ApiCallWarningDialog
from dialogs.ai_helper_error_code_dialog import invoker
from dialogs.generation_result_dialog import GenerationResultDialog
from helpers.ai_helper.gemini_helper import generate_metadata_gemini, track_gemini_generation_time
from helpers.ai_helper.openai_helper import generate_metadata_openai, track_openai_generation_time
from helpers.ai_helper.groq_helper import generate_metadata_groq, track_groq_generation_time
from helpers.ai_helper.blackbox_ai_helper import generate_metadata_blackbox, track_blackbox_generation_time
from helpers.ai_helper.maia_helper import generate_metadata_maia, track_maia_generation_time
from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
from helpers.video_proxy_helper import batch_process_videos_with_dialog, batch_extract_frames_with_dialog, VIDEO_EXTENSIONS, get_video_proxy_setting, get_prefer_frame_analysis, extract_video_frames, cleanup_video_temp_folder, BatchFrameExtractionWorker, BatchVideoProxyWorker
from helpers.image_compression_helper import cleanup_temp_folder
from helpers.members_helper.members_helper import is_logged_in, get_member_api_config, is_member_secret_valid

from ui.theme_system import theme



def _track_member_usage_and_check_limit(window, success_count: int) -> bool:
    from helpers.members_helper.members_helper import is_logged_in, increment_member_usage, get_usage_info
    if not is_logged_in() or success_count <= 0:
        return False
    increment_member_usage(success_count)
    used, limit = get_usage_info()
    if hasattr(window, 'statusbar') and hasattr(window.statusbar, 'update_member_status'):
        window.statusbar.update_member_status()
    if hasattr(window, '_apply_member_mode'):
        window._apply_member_mode()
    if limit > 0 and used >= limit:
        print(f"[MemberUsage] Limit reached: {used}/{limit}")
        show_member_limit_dialog(window, used, limit)
        return True
    print(f"[MemberUsage] +{success_count} | total: {used}/{limit if limit > 0 else 'unlimited'}")
    return False


def get_batch_size():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return int(config['batch_size'])

def get_delay_interval():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    delay_value = config['delay_interval']
    if delay_value == 'No Delay':
        return 0.0
    if delay_value == 'Random':
        return random.uniform(1, 5)
    return float(delay_value)

def get_max_retries():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return int(config['max_retries'])

def get_fresh_ai_config():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config

def is_typewriter_animation_enabled():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config.get("typewriter_animation_enabled", True)

def interruptible_sleep(total_seconds, stop_check):
    end_time = time.time() + total_seconds
    while time.time() < end_time:
        if stop_check():
            return False
        time.sleep(0.1)
    return True

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
                return api_info['api_key'], api_info['service'], api_info['model'], api_info.get('provider_endpoint')
        return self.api_key, self.service, self.model, None

    def get_current_api_info_detailed(self):
        """Get detailed API info including note and position"""
        if self.is_rolling_mode and self.api_keys_list:
            if self.current_api_index < len(self.api_keys_list):
                api_info = self.api_keys_list[self.current_api_index]
                api_key = api_info['api_key']
                service = api_info['service']
                model = api_info['model']
                note = api_info.get('note', '')
                provider_endpoint = api_info.get('provider_endpoint')
                
                # Format API key to show last 5 chars
                masked_key = f"***{api_key[-5:]}" if len(api_key) >= 5 else f"***{api_key}"
                
                # Current position
                position = f"{self.current_api_index + 1}/{len(self.api_keys_list)}"
                
                # Build detailed string
                detail_parts = [f"{service} - {model}", f"({masked_key})", position]
                if provider_endpoint:
                    detail_parts.append(f"endpoint={provider_endpoint}")
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
                # For rolling mode, pass service to metadata_func; for non-rolling, use old signature
                if self.is_rolling_mode:
                    result = self.metadata_func(self.api_key, self.model, image_path, prompt, stop_flag, service_override=self.service)
                else:
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
                time.sleep(3)
                break
            # Get current API credentials and detailed info
            current_api_key, current_service, current_model, current_provider_endpoint = self.get_current_api_credentials()
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
                        t0 = time.perf_counter()
                        title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_gemini(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
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
                        t0 = time.perf_counter()
                        title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_openai(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
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
                    elif current_service == "groq":
                        t0 = time.perf_counter()
                        title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_groq(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
                        t1 = time.perf_counter()
                        duration_ms = int((t1 - t0) * 1000)
                        gen_time, avg_time, longest_time, last_time = track_groq_generation_time(duration_ms)
                        
                        # Update stats UI via signal
                        self.signals.timing_updated.emit(gen_time, avg_time, longest_time, last_time)
                        
                        result = {
                            "title": title, "description": description, "tags": tags, "category": category, "filetype": filetype,
                            "token_input": token_input, "token_output": token_output, "token_total": token_total,
                            "image_path": image_path, "error_message": error_message,
                            "service": current_service, "model": current_model
                        }
                    elif current_service == "blackbox":
                        t0 = time.perf_counter()
                        title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_blackbox(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
                        t1 = time.perf_counter()
                        duration_ms = int((t1 - t0) * 1000)
                        gen_time, avg_time, longest_time, last_time = track_blackbox_generation_time(duration_ms)
                        self.signals.timing_updated.emit(gen_time, avg_time, longest_time, last_time)
                        result = {
                            "title": title, "description": description, "tags": tags, "category": category, "filetype": filetype,
                            "token_input": token_input, "token_output": token_output, "token_total": token_total,
                            "image_path": image_path, "error_message": error_message,
                            "service": current_service, "model": current_model
                        }
                    elif current_service == "maia":
                        t0 = time.perf_counter()
                        title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_maia(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
                        t1 = time.perf_counter()
                        duration_ms = int((t1 - t0) * 1000)
                        gen_time, avg_time, longest_time, last_time = track_maia_generation_time(duration_ms)
                        self.signals.timing_updated.emit(gen_time, avg_time, longest_time, last_time)
                        result = {
                            "title": title, "description": description, "tags": tags, "category": category, "filetype": filetype,
                            "token_input": token_input, "token_output": token_output, "token_total": token_total,
                            "image_path": image_path, "error_message": error_message,
                            "service": current_service, "model": current_model
                        }
                    elif current_service == "custom":
                        # Custom endpoint - try to detect provider type based on endpoint and use appropriate helper
                        if not current_provider_endpoint:
                            print(f"[CUSTOM ERROR] No endpoint URL provided for custom service")
                            result = {
                                "title": "", "description": "", "tags": "", "category": {},
                                "token_input": 0, "token_output": 0, "token_total": 0,
                                "image_path": image_path, "error_message": "Custom endpoint selected but no endpoint URL provided",
                                "service": current_service, "model": current_model
                            }
                        else:
                            # Detect provider type from endpoint
                            prov_type = "openai"  # Default to OpenAI-compatible
                            ep_lower = current_provider_endpoint.lower()
                            if "gemini" in ep_lower:
                                prov_type = "gemini"
                            elif "groq" in ep_lower:
                                prov_type = "groq"
                            elif "blackbox" in ep_lower:
                                prov_type = "blackbox"
                            elif "maia" in ep_lower:
                                prov_type = "maia"
                            
                            print(f"[CUSTOM] Using provider type: {prov_type} with endpoint: {current_provider_endpoint}")
                            
                            try:
                                # Use the appropriate helper based on detected type
                                # These functions are imported at the top of the file
                                if prov_type == "gemini":
                                    result_tuple = generate_metadata_gemini(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
                                elif prov_type == "groq":
                                    result_tuple = generate_metadata_groq(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
                                elif prov_type == "blackbox":
                                    result_tuple = generate_metadata_blackbox(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
                                elif prov_type == "maia":
                                    result_tuple = generate_metadata_maia(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
                                else:
                                    # Default to OpenAI (works for most OpenAI-compatible endpoints)
                                    result_tuple = generate_metadata_openai(current_api_key, current_model, image_path, prompt, stop_flag, provider_endpoint=current_provider_endpoint)
                                
                                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = result_tuple
                                result = {
                                    "title": title, "description": description, "tags": tags, "category": category,
                                    "token_input": token_input, "token_output": token_output, "token_total": token_total,
                                    "image_path": image_path, "error_message": error_message,
                                    "service": current_service, "model": current_model
                                }
                            except Exception as e:
                                print(f"[CUSTOM ERROR] Exception: {str(e)}")
                                result = {
                                    "title": "", "description": "", "tags": "", "category": {},
                                    "token_input": 0, "token_output": 0, "token_total": 0,
                                    "image_path": image_path, "error_message": f"Custom endpoint error: {str(e)}",
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
                # Ensure index doesn't exceed bounds
                if self.current_api_index >= len(self.api_keys_list):
                    self.current_api_index = 0
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

def create_parallel_rounds(files, api_keys_list, batch_size):
    """
    Create parallel processing rounds where multiple APIs work simultaneously.
    
    Example: 10 files, 2 API keys, batch_size=3
    - Round 1: API1 processes files 1-3, API2 processes files 4-6 (SIMULTANEOUSLY)
    - Round 2: API1 processes files 7-9, API2 processes file 10 (SIMULTANEOUSLY)
    
    Returns: List of rounds, each round contains list of tasks [{api_info, files}, ...]
    """
    if not api_keys_list or not files:
        return []
    
    num_apis = len(api_keys_list)
    num_files = len(files)
    files_per_round = batch_size * num_apis  # Total files processed per round
    
    rounds = []
    round_start = 0
    
    while round_start < num_files:
        round_tasks = []
        task_start = round_start
        
        for api_idx, api_info in enumerate(api_keys_list):
            if task_start >= num_files:
                break
            
            task_end = min(task_start + batch_size, num_files)
            task_files = files[task_start:task_end]
            
            if task_files:
                round_tasks.append({
                    'api_info': api_info,
                    'files': task_files,
                    'api_index': api_idx
                })
            
            task_start = task_end
        
        if round_tasks:
            rounds.append(round_tasks)
        
        round_start += files_per_round
    
    return rounds

def batch_generate_metadata(window):
    if getattr(window, 'is_generating', False):
        return

    # Clean up any stuck processing files from previous runs
    cleanup_stuck_processing_files(window)

    # Detect Rolling APIs mode and Parallel API Processing mode
    is_rolling_mode = False
    is_parallel_mode = False
    api_keys_list = []
    
    if hasattr(window, "gen_mode_combo"):
        mode_text = window.gen_mode_combo.currentText().lower()
        if "rolling" in mode_text and "parallel" not in mode_text:
            is_rolling_mode = True
            # Get all API keys from database
            all_api_keys = window.db.get_all_api_keys()
            for row in all_api_keys:
                # DB row: (service, api_key, note, last_tested, status, model, provider_endpoint)
                service = row[0] if len(row) > 0 else None
                api_key = row[1] if len(row) > 1 else None
                note = row[2] if len(row) > 2 else ''
                last_tested = row[3] if len(row) > 3 else None
                status = row[4] if len(row) > 4 else ''
                model = row[5] if len(row) > 5 else ''
                endpoint = row[6] if len(row) > 6 else None
                if api_key and model and service:  # Only include complete API key entries
                    api_keys_list.append({
                        'service': service.lower(),
                        'api_key': api_key,
                        'model': model,
                        'note': note,
                        'status': status,
                        'provider_endpoint': endpoint
                    })
            
            if not api_keys_list:
                QMessageBox.warning(window, "Rolling APIs", "No valid API keys found in database for Rolling APIs mode.")
                return
            
            print(f"[ROLLING] Found {len(api_keys_list)} API keys for rolling mode")
        
        elif "parallel" in mode_text:
            is_parallel_mode = True
            # Get all API keys from database
            all_api_keys = window.db.get_all_api_keys()
            for row in all_api_keys:
                # DB row: (service, api_key, note, last_tested, status, model, provider_endpoint)
                service = row[0] if len(row) > 0 else None
                api_key = row[1] if len(row) > 1 else None
                note = row[2] if len(row) > 2 else ''
                last_tested = row[3] if len(row) > 3 else None
                status = row[4] if len(row) > 4 else ''
                model = row[5] if len(row) > 5 else ''
                endpoint = row[6] if len(row) > 6 else None
                if api_key and model and service:  # Only include complete API key entries
                    api_keys_list.append({
                        'service': service.lower(),
                        'api_key': api_key,
                        'model': model,
                        'note': note,
                        'status': status,
                        'provider_endpoint': endpoint
                    })
            
            if not api_keys_list:
                QMessageBox.warning(window, "Parallel API Processing", "No valid API keys found in database for Parallel API Processing mode.")
                return
            
            print(f"[PARALLEL] Found {len(api_keys_list)} API keys for parallel mode")

    # Always fetch API key, model, and service from api_key_section if available
    api_key = None
    model = None
    service = None

    # Member session takes priority over local API keys
    if is_logged_in():
        if not is_member_secret_valid():
            print("[BATCH] Member is logged in but MEMBER_SECRET is invalid or missing.")
            dlg = MemberSecretManagerDialog(window)
            dlg.exec()
            return
        _member_cfg = get_member_api_config()
        api_key = _member_cfg["api_key"]
        model = _member_cfg["model"]
        service = _member_cfg["service_type"] or "custom"
        _raw_endpoint = _member_cfg["endpoint"]
        del _member_cfg
        # For gemini native, the google.genai SDK handles the URL internally — no endpoint needed.
        # For blackbox/maia, pass endpoint through. For openai/groq/custom, pass endpoint through.
        if service == "gemini":
            provider_endpoint = None
        else:
            provider_endpoint = _raw_endpoint
        del _raw_endpoint
    elif (is_rolling_mode or is_parallel_mode) and api_keys_list:
        # Use first API key from list for rolling/parallel mode
        first_api = api_keys_list[0]
        api_key = first_api['api_key']
        service = first_api['service']
        model = first_api['model']
        if is_rolling_mode:
            print(f"[ROLLING] Starting with API: {service} - {model}")
        else:
            print(f"[PARALLEL] Starting with {len(api_keys_list)} API keys for parallel processing")
    elif hasattr(window, "api_key_section"):
        api_key = window.api_key_section.get_current_api_key()
        service = window.api_key_section.get_current_service()
        model = window.api_key_section.get_current_model()
        # detect provider_endpoint for the selected API key (if stored in UI map)
        provider_endpoint = None
        try:
            if api_key and hasattr(window.api_key_section, 'api_key_map') and api_key in window.api_key_section.api_key_map:
                provider_endpoint = window.api_key_section.api_key_map[api_key].get('endpoint')
        except Exception:
            provider_endpoint = None
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
    
    # ensure provider_endpoint is defined for downstream calls
    if 'provider_endpoint' not in locals():
        provider_endpoint = None

    if not api_key or not model or not service:
        dlg = GetApiKeyDialog(window)
        dlg.exec()
        return

    if not is_logged_in():
        print(f"[BATCH] Starting batch generation with service: {service}, model: {model}")

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
        elif ("rolling" in mode_text or "parallel" in mode_text) and "failed" not in mode_text and "selected" not in mode_text and "draft" not in mode_text:
            mode = "all"  # Pure rolling/parallel APIs processes all files
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
            QMessageBox.information(window, "Draft Only", "No draft files found to process.")
            return
    
    elif mode == "stopped":
        # For "stopped" mode, get all files starting from the first stopped file
        search_text = window.table.search_edit.text() if hasattr(window.table, 'search_edit') else None
        total_count = window.db.get_files_count(search_text)
        if total_count == 0:
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
        QMessageBox.information(window, "No Files", "No files selected (checkbox) to process.")
        return
    elif mode == "draft" and not rows:
        print("[DEBUG] No draft files found for Draft Only mode.")
        QMessageBox.information(window, "Draft Only", "No draft files found to process.")
        return
    elif mode == "stopped" and not rows:
        print("[DEBUG] No stopped files found for Resume Stopped mode.")
        QMessageBox.information(window, "Resume Stopped", "No stopped files found to resume from.")
        return
    if not rows:
        print("[DEBUG] No rows to process after filtering.")
        QMessageBox.information(window, "No Files", "No files to process.")
        return

    # --- FILE EXISTENCE CHECK BEFORE BATCH ---
    missing_files = []
    for row in rows:
        file_path = row[1]
        if not os.path.isfile(file_path):
            missing_files.append(file_path)
    if missing_files:
        msg = "The following files were not found on disk and the process has been cancelled:\n\n"
        msg += "\n".join(missing_files)
        QMessageBox.critical(window, "File Not Found", msg)
        return
    # --- END FILE EXISTENCE CHECK ---

    # --- MEMBER USAGE LIMIT PRE-CHECK ---
    from helpers.members_helper.members_helper import is_logged_in as _is_member_logged_in, get_usage_info as _get_usage_info, refresh_usage_from_supabase as _refresh_usage
    if _is_member_logged_in():
        _used, _limit = _get_usage_info()
        if _limit > 0 and _used >= _limit:
            print(f"[MemberLimit] Local limit reached {_used}/{_limit}, refreshing from Supabase...")
            _refresh_usage()
            _used, _limit = _get_usage_info()
        if _limit > 0:
            if _used >= _limit:
                print(f"[MemberLimit] Blocked: already at limit {_used}/{_limit}")
                show_member_limit_dialog(window, _used, _limit)
                window.table.progress_bar.setVisible(False)
                return
            _remaining = _limit - _used
            if _remaining < len(rows):
                rows = rows[:_remaining]
                row_map = {}
                for _idx, _row in enumerate(rows):
                    row_map[_row[1]] = {'batch_index': _idx, 'row_data': _row}
                print(f"[MemberLimit] Files trimmed to {len(rows)} (remaining quota: {_remaining}/{_limit})")
    # --- END MEMBER USAGE LIMIT PRE-CHECK ---

    # --- WARNING DIALOG FOR > 1000 FILES ---
    if len(rows) >= 1000:
        try:
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
            elif is_parallel_mode:
                # Custom message for parallel APIs mode
                dialog = ApiCallWarningDialog(window, file_count=len(rows))
                if hasattr(dialog, 'label'):
                    dialog.label.setText(
                        f"You are about to generate metadata for {len(rows)} files using Parallel API Processing.\n\n"
                        f"This will use {len(api_keys_list)} API keys in parallel, distributing files across them.\n"
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
        invoker.enable_buffering()
    except Exception as e:
        print(f"[Batch] Failed to enable error buffering: {e}")

    window.table.progress_bar.setVisible(True)
    window.table.progress_bar.setMinimum(0)
    window.table.progress_bar.setMaximum(len(rows))
    window.table.progress_bar.setValue(0)
    
    # Show initial progress with API info
    if is_parallel_mode and api_keys_list:
        batch_size = get_batch_size()
        files_per_round = batch_size * len(api_keys_list)
        total_rounds = (len(rows) + files_per_round - 1) // files_per_round
        initial_text = f"Parallel API Processing - {len(api_keys_list)} APIs, {batch_size} files/API, ~{total_rounds} rounds"
    elif is_rolling_mode and api_keys_list:
        first_api = api_keys_list[0]
        initial_text = window.table.get_progress_format_text("rolling", first_api['service'], first_api['api_key'])
    else:
        initial_text = window.table.get_progress_format_text(mode, service, api_key)
    window.table.set_progress_info(initial_text)
    
    QApplication.processEvents()

    stop_flag = {'stop': False}
    
    # For parallel mode, create a universal metadata function that can handle all services
    if is_parallel_mode:
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None, service_override=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            
            proxy_path = None
            preextracted_frames = None
            if hasattr(window, '_batch_processing_state'):
                video_proxy_map = window._batch_processing_state.get('video_proxy_map', {})
                proxy_path = video_proxy_map.get(image_path)
                video_frame_map = window._batch_processing_state.get('video_frame_map', {})
                preextracted_frames = video_frame_map.get(image_path)
            
            target_service = service_override if service_override else service
            target_service = target_service.lower() if target_service else 'gemini'
            
            if target_service == "gemini":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_gemini(api_key, model, image_path, prompt, stop_flag, proxy_path=proxy_path, provider_endpoint=provider_endpoint, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_gemini_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    print(f"[Gemini ERROR] {error_message}")
            elif target_service == "openai" or target_service == "openrouter":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_openai(api_key, model, image_path, prompt, stop_flag, proxy_path=proxy_path, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_openai_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    service_name = "OpenRouter" if target_service == "openrouter" else "OpenAI"
                    print(f"[{service_name} ERROR] {error_message}")
            elif target_service == "groq":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_groq(api_key, model, image_path, prompt, stop_flag, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_groq_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    print(f"[Groq ERROR] {error_message}")
            elif target_service == "blackbox":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_blackbox(api_key, model, image_path, prompt, stop_flag, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_blackbox_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    print(f"[Blackbox ERROR] {error_message}")
            elif target_service == "maia":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_maia(api_key, model, image_path, prompt, stop_flag, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_maia_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    print(f"[Maia ERROR] {error_message}")
            else:
                print(f"[ERROR] Unknown service in parallel mode: {target_service}")
                title = ""
                description = ""
                tags = ""
                category = {}
                filetype = ""
                error_message = f"Unknown service: {target_service}"
                token_input = 0
                token_output = 0
                token_total = 0
            
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
    # For rolling mode, create a universal metadata function that can handle all services
    elif is_rolling_mode:
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None, service_override=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            
            proxy_path = None
            preextracted_frames = None
            if hasattr(window, '_batch_processing_state'):
                video_proxy_map = window._batch_processing_state.get('video_proxy_map', {})
                proxy_path = video_proxy_map.get(image_path)
                video_frame_map = window._batch_processing_state.get('video_frame_map', {})
                preextracted_frames = video_frame_map.get(image_path)
            
            target_service = service_override if service_override else service
            target_service = target_service.lower() if target_service else 'gemini'
            
            if target_service == "gemini":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_gemini(api_key, model, image_path, prompt, stop_flag, proxy_path=proxy_path, provider_endpoint=provider_endpoint, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_gemini_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    print(f"[Gemini ERROR] {error_message}")
            elif target_service == "openai" or target_service == "openrouter":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_openai(api_key, model, image_path, prompt, stop_flag, proxy_path=proxy_path, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_openai_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    service_name = "OpenRouter" if target_service == "openrouter" else "OpenAI"
                    print(f"[{service_name} ERROR] {error_message}")
            elif target_service == "groq":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_groq(api_key, model, image_path, prompt, stop_flag, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_groq_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    print(f"[Groq ERROR] {error_message}")
            elif target_service == "blackbox":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_blackbox(api_key, model, image_path, prompt, stop_flag, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_blackbox_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    print(f"[Blackbox ERROR] {error_message}")
            elif target_service == "maia":
                t0 = time.perf_counter()
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_maia(api_key, model, image_path, prompt, stop_flag, preextracted_frames=preextracted_frames)
                t1 = time.perf_counter()
                duration_ms = int((t1 - t0) * 1000)
                gen_time, avg_time, longest_time, last_time = track_maia_generation_time(duration_ms)
                if hasattr(window, "stats_section"):
                    window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
                if error_message:
                    print(f"[Maia ERROR] {error_message}")
            else:
                print(f"[ERROR] Unknown service in rolling mode: {target_service}")
                title = ""
                description = ""
                tags = ""
                category = {}
                filetype = ""
                error_message = f"Unknown service: {target_service}"
                token_input = 0
                token_output = 0
                token_total = 0
            
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
    elif service == "gemini":
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            t0 = time.perf_counter()
            proxy_path = None
            preextracted_frames = None
            if hasattr(window, '_batch_processing_state'):
                video_proxy_map = window._batch_processing_state.get('video_proxy_map', {})
                proxy_path = video_proxy_map.get(image_path)
                video_frame_map = window._batch_processing_state.get('video_frame_map', {})
                preextracted_frames = video_frame_map.get(image_path)
            title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_gemini(api_key, model, image_path, prompt, stop_flag, proxy_path=proxy_path, provider_endpoint=provider_endpoint, preextracted_frames=preextracted_frames)
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
    elif service == "openai" or service == "openrouter":
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            t0 = time.perf_counter()
            proxy_path = None
            preextracted_frames = None
            if hasattr(window, '_batch_processing_state'):
                video_proxy_map = window._batch_processing_state.get('video_proxy_map', {})
                proxy_path = video_proxy_map.get(image_path)
                video_frame_map = window._batch_processing_state.get('video_frame_map', {})
                preextracted_frames = video_frame_map.get(image_path)
            title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_openai(api_key, model, image_path, prompt, stop_flag, proxy_path=proxy_path, provider_endpoint=provider_endpoint, preextracted_frames=preextracted_frames)
            t1 = time.perf_counter()
            duration_ms = int((t1 - t0) * 1000)
            gen_time, avg_time, longest_time, last_time = track_openai_generation_time(duration_ms)
            if hasattr(window, "stats_section"):
                window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
            if error_message:
                service_name = "OpenRouter" if service == "openrouter" else "OpenAI"
                print(f"[{service_name} ERROR] {error_message}")
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
    elif service == "groq":
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            t0 = time.perf_counter()
            preextracted_frames = None
            if hasattr(window, '_batch_processing_state'):
                video_frame_map = window._batch_processing_state.get('video_frame_map', {})
                preextracted_frames = video_frame_map.get(image_path)
            title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_groq(api_key, model, image_path, prompt, stop_flag, provider_endpoint=provider_endpoint, preextracted_frames=preextracted_frames)
            t1 = time.perf_counter()
            duration_ms = int((t1 - t0) * 1000)
            gen_time, avg_time, longest_time, last_time = track_groq_generation_time(duration_ms)
            if hasattr(window, "stats_section"):
                window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
            if error_message:
                print(f"[Groq ERROR] {error_message}")
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
    elif service == "blackbox":
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            t0 = time.perf_counter()
            preextracted_frames = None
            if hasattr(window, '_batch_processing_state'):
                video_frame_map = window._batch_processing_state.get('video_frame_map', {})
                preextracted_frames = video_frame_map.get(image_path)
            title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_blackbox(api_key, model, image_path, prompt, stop_flag, provider_endpoint=provider_endpoint, preextracted_frames=preextracted_frames)
            t1 = time.perf_counter()
            duration_ms = int((t1 - t0) * 1000)
            gen_time, avg_time, longest_time, last_time = track_blackbox_generation_time(duration_ms)
            if hasattr(window, "stats_section"):
                window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
            if error_message:
                print(f"[Blackbox ERROR] {error_message}")
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
    elif service == "maia":
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            t0 = time.perf_counter()
            proxy_path = None
            preextracted_frames = None
            if hasattr(window, '_batch_processing_state'):
                video_proxy_map = window._batch_processing_state.get('video_proxy_map', {})
                proxy_path = video_proxy_map.get(image_path)
                video_frame_map = window._batch_processing_state.get('video_frame_map', {})
                preextracted_frames = video_frame_map.get(image_path)
            title, description, tags, category, filetype, error_message, token_input, token_output, token_total = generate_metadata_maia(api_key, model, image_path, prompt, stop_flag, provider_endpoint=provider_endpoint, preextracted_frames=preextracted_frames)
            t1 = time.perf_counter()
            duration_ms = int((t1 - t0) * 1000)
            gen_time, avg_time, longest_time, last_time = track_maia_generation_time(duration_ms)
            if hasattr(window, "stats_section"):
                window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
            if error_message:
                print(f"[Maia ERROR] {error_message}")
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
    elif service == "custom":
        # Custom endpoint - use the same approach as other providers
        # Try to detect provider type based on endpoint and use appropriate helper
        if not provider_endpoint:
            print(f"[DEBUG] Custom service selected but no endpoint URL provided")
            QMessageBox.warning(window, "API Service", "Custom endpoint selected but no endpoint URL provided. Please add an endpoint URL when adding the API key.")
            window.table.progress_bar.setVisible(False)
            window.table.progress_bar.setValue(0)
            window.table.set_progress_info('', visible=False)
            return
        
        print(f"[BATCH] Custom service detected. Provider endpoint: {provider_endpoint}")
        
        # Detect provider type from endpoint
        prov_type = "openai"  # Default to OpenAI-compatible
        if provider_endpoint:
            ep_lower = provider_endpoint.lower()
            # Detect provider type from endpoint URL
            if "gemini" in ep_lower:
                prov_type = "gemini"
            elif "groq" in ep_lower:
                prov_type = "groq"
            elif "blackbox" in ep_lower:
                prov_type = "blackbox"
            elif "maia" in ep_lower:
                prov_type = "maia"
            # For other endpoints (openai, openrouter, etc.), default to openai
        
        print(f"[BATCH] Detected provider type: {prov_type}")
        
        # Use the appropriate helper based on detected type
        # These functions are already imported at the top of the file
        if prov_type == "gemini":
            helper_func = generate_metadata_gemini
        elif prov_type == "groq":
            helper_func = generate_metadata_groq
        elif prov_type == "blackbox":
            helper_func = generate_metadata_blackbox
        elif prov_type == "maia":
            helper_func = generate_metadata_maia
        else:
            # Default to OpenAI (works for most OpenAI-compatible endpoints)
            helper_func = generate_metadata_openai
        
        def metadata_func(api_key, model, image_path, prompt=None, stop_flag=None):
            if stop_flag and stop_flag.get('stop'):
                return {'title': '', 'description': '', 'tags': '', 'category': {}, 'filetype': '', 'token_input': 0, 'token_output': 0, 'token_total': 0, 'image_path': image_path, 'error_message': ''}
            try:
                preextracted_frames = None
                if hasattr(window, '_batch_processing_state'):
                    video_frame_map = window._batch_processing_state.get('video_frame_map', {})
                    preextracted_frames = video_frame_map.get(image_path)
                # Use the appropriate helper function with the custom endpoint
                result = helper_func(api_key, model, image_path, prompt, stop_flag, provider_endpoint=provider_endpoint, preextracted_frames=preextracted_frames)
                # Result is a tuple: (title, description, tags, category, filetype, error_message, token_input, token_output, token_total)
                title, description, tags, category, filetype, error_message, token_input, token_output, token_total = result
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
            except Exception as e:
                print(f"[Custom ERROR] {str(e)}")
                return {
                    "title": "",
                    "description": "",
                    "tags": "",
                    "category": {},
                    "filetype": "",
                    "token_input": 0,
                    "token_output": 0,
                    "token_total": 0,
                    "image_path": image_path,
                    "error_message": f"Custom endpoint error: {str(e)}"
                }
    else:
        print(f"[DEBUG] Unknown service: {service}")
        QMessageBox.warning(window, "API Service", f"Unknown service: {service}")
        window.table.progress_bar.setVisible(False)
        window.table.progress_bar.setValue(0)
        window.table.set_progress_info('', visible=False)
        return

    batch_size = get_batch_size()
    total_files = len(rows)

    video_proxy_map = {}
    video_frame_map = {}

    # Create batches based on mode
    if is_parallel_mode and api_keys_list:
        # For parallel mode, create rounds where multiple APIs work simultaneously
        # Each round contains tasks for each API key working in parallel
        parallel_rounds = create_parallel_rounds(rows, api_keys_list, batch_size)
        
        # Use rounds as batches - each "batch" is actually a round with multiple parallel tasks
        batches = parallel_rounds
        
        total_tasks = sum(len(round_tasks) for round_tasks in parallel_rounds)
        print(f"[PARALLEL] Created {len(parallel_rounds)} round(s) with {total_tasks} total tasks from {len(api_keys_list)} API key(s)")
        print(f"[PARALLEL] Each round processes up to {batch_size * len(api_keys_list)} files ({batch_size} per API)")
    else:
        # Standard batching for non-parallel modes
        batches = [rows[i:i+batch_size] for i in range(0, total_files, batch_size)]
    
    # Note: Configuration settings (batch_size, delay, prompt params, etc.) will be refreshed from JSON
    # at the start of each batch run in _run_next_batch(), so users can change settings on-the-fly
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
        'is_parallel_mode': is_parallel_mode,
        'api_keys_list': api_keys_list,
        'mode': mode,
        'current_api_index': 0,
        'batch_retry_count': 0,
        'batch_same_api_retry': 0,
        'file_retry_count': 0,
        'video_proxy_map': video_proxy_map,
        'video_frame_map': video_frame_map
    }
    window.is_generating = True
    
    # Start the generation timer for elapsed time calculation
    if hasattr(window, "stats_section"):
        window.stats_section.start_generation_timer()
        # Set the processing target to the total number of files being processed
        window.stats_section.set_processing_target(len(rows))
    
    _set_gen_btn_stop_state(window, True)
    window._gen_total_time_start = time.perf_counter()
    window._session_token_input = 0
    window._session_token_output = 0
    window._session_token_total = 0
    _run_next_batch(window)

def _gen_btn_style_string(bg_color, text_color=None, pressed_color=None, hover_color=None):
    color_line = f"color: {text_color};\n        " if text_color is not None else ""
    pressed = pressed_color if pressed_color is not None else theme.get_color('primary_pressed')
    hover = hover_color if hover_color is not None else pressed
    return f"""
    QPushButton {{
        background-color: {bg_color};
        {color_line}border: none;
        border-radius: 5px;
        padding: 6px 12px;
        min-height: 36px;
        max-height: 36px;
        min-width: 240px;
        max-width: 240px;
    }}
    QPushButton:hover {{ background-color: {hover}; }}
    QPushButton:pressed {{ background-color: {pressed}; }}
    QPushButton:disabled {{ background-color: {theme.get_color('button_disabled_bg')}; color: {theme.get_color('button_disabled_fg')}; }}
    """


def _set_gen_btn_blinking(window, blinking, color=None, text=None):
    if not hasattr(window, "gen_btn"):
        return
    btn = window.gen_btn
    if hasattr(window, "_gen_btn_anim") and window._gen_btn_anim:
        window._gen_btn_anim.stop()
        window._gen_btn_anim = None
    if blinking:

        def set_bg_color(bg_color):
            style = _gen_btn_style_string(bg_color, text_color=None, hover_color=bg_color)
            btn.setStyleSheet(style)

        _warn_q = QColor(theme.get_color('warning'))
        _warn_rgb = f"{_warn_q.red()},{_warn_q.green()},{_warn_q.blue()}"
        _gray_q = QColor(theme.get_color('gray'))
        _gray_rgb = f"{_gray_q.red()},{_gray_q.green()},{_gray_q.blue()}"
        color1 = color if color else f"rgba({_warn_rgb},0.22)"
        color2 = f"rgba({_gray_rgb},0.12)"
        window._gen_btn_blink_state = True

        # Keep the full last stylesheet so it can be restored exactly
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
    btn = window.gen_btn
    if is_stopping:
        btn.setText("Stopping process")
        btn.setIcon(qta.icon('fa6s.stop'))
        _warn_q2 = QColor(theme.get_color('warning'))
        _warn_rgb2 = f"{_warn_q2.red()},{_warn_q2.green()},{_warn_q2.blue()}"
        _set_gen_btn_blinking(window, True, f"rgba({_warn_rgb2},0.3)", "Stopping process")
    elif is_stop:
        btn.setText("Stop Processes")
        btn.setIcon(qta.icon('fa6s.stop', color=theme.get_color('white')))
        _set_gen_btn_blinking(window, False)
        _err_q = QColor(theme.get_color('error'))
        _err_rgb = f"{_err_q.red()},{_err_q.green()},{_err_q.blue()}"
        bg = f"rgba({_err_rgb},0.90)"
        hover = f"rgba({_err_rgb},0.85)"
        pressed = f"rgba({_err_rgb},1.00)"
        style = _gen_btn_style_string(bg, text_color='white', pressed_color=pressed, hover_color=hover)
        btn.setStyleSheet(style)
        window._gen_btn_last_bg = style
    else:
        btn.setText("Generate Metadata")
        btn.setIcon(qta.icon('fa6s.wand-magic-sparkles', color=theme.get_color('white')))
        _set_gen_btn_blinking(window, False)
        style = _gen_btn_style_string(theme.get_color('primary'), theme.get_color('white'), pressed_color=theme.get_color('primary_pressed'), hover_color=theme.get_color('primary_hover'))
        btn.setStyleSheet(style)
        window._gen_btn_last_bg = style

def _run_parallel_round(window, state, round_tasks):
    """
    Run a parallel round where multiple API keys process their tasks simultaneously.
    
    round_tasks: List of dicts [{api_info, files, api_index}, ...]
    """
    stop_flag = state.get('stop_flag')
    metadata_func = state['metadata_func']
    row_map = state['row_map']
    rows = state['rows']
    api_keys_list = state.get('api_keys_list', [])
    table_widget = window.table.table
    
    # Build API info string for progress display
    api_info_parts = []
    total_files_in_round = 0
    for task in round_tasks:
        api_info = task['api_info']
        files = task['files']
        total_files_in_round += len(files)
        masked_key = f"***{api_info['api_key'][-5:]}" if len(api_info['api_key']) >= 5 else f"***{api_info['api_key']}"
        api_info_parts.append(f"{api_info['service'].upper()}({masked_key}): {len(files)} files")
    
    # Update progress label to show up to two API entries, then truncate with "and N others"
    round_num = state['current'] + 1
    total_rounds = len(state['batches'])
    max_display = 2
    display_parts = api_info_parts[:max_display]
    remaining = len(api_info_parts) - max_display
    if remaining > 0:
        display_parts.append(f"and {remaining} others")
    progress_text = f"Round {round_num}/{total_rounds} - Parallel: {' | '.join(display_parts)}"
    window.table.set_progress_info(progress_text)
    
    # Update status bar with parallel processing info (concise)
    if hasattr(window, 'statusbar'):
        status_preview = ' | '.join(display_parts)
        statusbar_text = f"Parallel: {len(round_tasks)} APIs, {total_files_in_round} files ({status_preview})"
        window.statusbar.showMessage(statusbar_text, 0)  # 0 means don't auto-hide
    
    print(f"[PARALLEL ROUND {round_num}] Starting with {len(round_tasks)} API(s): {', '.join(api_info_parts)}")
    
    # Mark all files in this round as "processing"
    all_files_in_round = []
    for task in round_tasks:
        for row in task['files']:
            filepath = row[1]
            all_files_in_round.append(row)
            window.db.update_file_status(filepath, "processing")
            
            # Update UI
            for row_idx in range(table_widget.rowCount()):
                item = table_widget.item(row_idx, 1)
                if item and item.data(Qt.UserRole) == filepath:
                    window.table.set_row_status_color(row_idx, "processing")
                    break
    
    QApplication.processEvents()
    
    # Create workers for each task in the round
    workers = []
    worker_results = {}  # Store results from each worker
    completed_workers = {'count': 0}  # Track completed workers
    
    def create_worker_finished_handler(task_idx, task, worker):
        def on_worker_finished(errors):
            nonlocal completed_workers
            
            if state.get('should_stop', False) or (stop_flag and stop_flag.get('stop')):
                completed_workers['count'] += 1
                return
            
            # Store results from this worker
            cache_results = worker._results
            worker_results[task_idx] = {
                'task': task,
                'results': cache_results,
                'errors': errors
            }
            
            # Process results immediately
            api_info = task['api_info']
            batch_files = task['files']
            current_service = api_info['service']
            current_model = api_info['model']
            
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
                result_service = result.get("service", current_service)
                result_model = result.get("model", current_model)
                error_message = result.get("error_message", "")
                
                if category is not None:
                    file_id = None
                    for row in batch_files:
                        if row[1] == image_path:
                            file_id = row[0]
                            break
                    if file_id is not None and isinstance(category, dict) and len(category) > 0:
                        window.db.save_category_mapping(file_id, category)
                
                if filetype and filetype in ["Photo", "Illustration"]:
                    file_id = None
                    for row in batch_files:
                        if row[1] == image_path:
                            file_id = row[0]
                            break
                    if file_id is not None:
                        window.db.delete_file_types_for_file(file_id)
                        window.db.add_file_type(file_id, filetype)
                
                final_status = "success" if title and not error_message else "failed"
                window.db.update_metadata(image_path, title, description, tags, status=final_status)
                
                if token_total > 0 and title:
                    window.db.insert_api_token_stats(image_path, result_service, result_model, token_input, token_output, token_total)
                    window._session_token_input = getattr(window, '_session_token_input', 0) + token_input
                    window._session_token_output = getattr(window, '_session_token_output', 0) + token_output
                    window._session_token_total = getattr(window, '_session_token_total', 0) + token_total
                for row_idx in range(table_widget.rowCount()):
                    item = table_widget.item(row_idx, 1)
                    if item and item.data(Qt.UserRole) == image_path:
                        window.table.set_row_status_color(row_idx, final_status)
                        break
            
            completed_workers['count'] += 1
            
            # Check if all workers completed
            if completed_workers['count'] >= len(round_tasks):
                _on_parallel_round_completed(window, state, round_tasks, worker_results)
        
        return on_worker_finished
    
    def create_worker_progress_handler(task_idx, task):
        def on_worker_progress(cur, total):
            if state.get('should_stop', False) or (stop_flag and stop_flag.get('stop')):
                return
            
            # Update progress bar based on total progress across all rounds
            total_files = len(rows)
            
            # Count files completed in previous rounds
            files_before_this_round = 0
            for i in range(state['current']):
                batch_item = state['batches'][i]
                if isinstance(batch_item, list) and len(batch_item) > 0:
                    if isinstance(batch_item[0], dict) and 'files' in batch_item[0]:
                        # It's a parallel round
                        for t in batch_item:
                            files_before_this_round += len(t.get('files', []))
                    else:
                        # Regular batch (list of rows)
                        files_before_this_round += len(batch_item)
            
            # For current round, estimate progress based on completed results
            current_round_completed = 0
            for wr_data in worker_results.values():
                current_round_completed += len(wr_data.get('results', []))
            
            total_completed = files_before_this_round + current_round_completed
            window.table.progress_bar.setMinimum(0)
            window.table.progress_bar.setMaximum(total_files)
            window.table.progress_bar.setValue(min(total_completed, total_files))
            
            QApplication.processEvents()
        
        return on_worker_progress
    
    # Start all workers for this round
    for task_idx, task in enumerate(round_tasks):
        api_info = task['api_info']
        batch_files = task['files']
        
        api_key = api_info['api_key']
        service = api_info['service']
        model = api_info['model']
        
        worker = BatchWorker(
            api_key, model, batch_files, service, metadata_func, row_map,
            stop_flag=stop_flag, api_keys_list=api_keys_list, 
            is_rolling_mode=False, current_api_index=task.get('api_index', task_idx)
        )
        worker.is_parallel_mode = True
        
        # Connect signals
        worker.signals.finished.connect(create_worker_finished_handler(task_idx, task, worker))
        worker.signals.progress.connect(create_worker_progress_handler(task_idx, task))
        
        workers.append(worker)
    
    # Store workers in state for potential stop handling
    state['parallel_workers'] = workers
    
    # Start all workers simultaneously
    for worker in workers:
        worker.start()

def _on_parallel_round_completed(window, state, round_tasks, worker_results):
    """Called when all workers in a parallel round have completed."""
    stop_flag = state.get('stop_flag')
    rows = state['rows']
    api_keys_list = state.get('api_keys_list', [])
    
    if state.get('should_stop', False) or (stop_flag and stop_flag.get('stop')):
        _on_generation_finished(window, state['errors'], stopped=True)
        return
    
    # Count successes and failures across all tasks in this round
    total_in_round = sum(len(task['files']) for task in round_tasks)
    failed_count = 0
    failed_files = []
    
    for task_idx, result_data in worker_results.items():
        task = result_data['task']
        results = result_data['results']
        
        for idx, result in results:
            if isinstance(result, dict) and (not result.get("title") or result.get("error_message")):
                failed_count += 1
                # Find original file row
                image_path = result.get("image_path")
                for row in task['files']:
                    if row[1] == image_path:
                        failed_files.append({
                            'row': row,
                            'api_info': task['api_info'],
                            'error': result.get("error_message", "Unknown error")
                        })
                        break
    
    success_count = total_in_round - failed_count
    print(f"[PARALLEL ROUND {state['current'] + 1}] Completed: {success_count} success, {failed_count} failed")
    
    # Track member usage for this parallel round
    if _track_member_usage_and_check_limit(window, success_count):
        state['current'] += 1
        _on_generation_finished(window, state['errors'])
        return
    
    # Handle failures with retry (prefer unused APIs; fall back to all if needed)
    if failed_files:
        retry_count = state.get('parallel_retry_count', 0)
        max_retries = get_max_retries()
        
        if retry_count < max_retries:
            # Find APIs that haven't been tried for failed files
            used_apis = set()
            for failed_file in failed_files:
                used_apis.add(failed_file['api_info']['api_key'])
            
            available_apis = [api for api in api_keys_list if api['api_key'] not in used_apis]
            if not available_apis:
                available_apis = api_keys_list
            
            print(f"[PARALLEL] Retrying {len(failed_files)} failed files (attempt {retry_count + 1}/{max_retries})")
            state['parallel_retry_count'] = retry_count + 1
            
            # Create retry tasks for failed files with available APIs
            retry_round = []
            for i, failed_file in enumerate(failed_files):
                api_idx = i % len(available_apis)
                retry_round.append({
                    'api_info': available_apis[api_idx],
                    'files': [failed_file['row']],
                    'api_index': api_idx
                })
            
            # Replace current batch with retry tasks
            state['batches'][state['current']] = retry_round
            
            # Delay before retry
            delay_seconds = get_delay_interval()
            if delay_seconds > 0:
                window.table.set_progress_info(f"Retrying {len(failed_files)} failed files (attempt {retry_count + 1}/{max_retries})...")
                def _retry_cb():
                    if state.get('should_stop', False) or (stop_flag and stop_flag.get('stop')):
                        _on_generation_finished(window, state['errors'], stopped=True)
                        window._batch_delay_timer = None
                        return
                    window._batch_delay_timer = None
                    _run_parallel_round(window, state, retry_round)
                timer = QTimer(window)
                timer.setSingleShot(True)
                timer.timeout.connect(_retry_cb)
                timer.start(int(delay_seconds * 1000))
                window._batch_delay_timer = timer
            else:
                _run_parallel_round(window, state, retry_round)
            return
    
    # Reset retry counter for next round
    state['parallel_retry_count'] = 0
    
    # Update UI
    update_token_stats_ui(window)
    window.table.refresh_table()
    
    if hasattr(window.table, '_emit_stats'):
        window.table._emit_stats()
    
    # Move to next round
    state['current'] += 1
    
    if state['current'] < len(state['batches']):
        # Get fresh delay from config before next round
        delay_seconds = get_delay_interval()
        if delay_seconds > 0:
            if hasattr(window, 'statusbar'):
                window.statusbar.showMessage(f"Waiting {delay_seconds:.1f}s before next round...", int(delay_seconds * 1000))
            def _delayed_cb():
                if state.get('should_stop', False) or (stop_flag and stop_flag.get('stop')):
                    _on_generation_finished(window, state['errors'], stopped=True)
                    window._batch_delay_timer = None
                    return
                window._batch_delay_timer = None
                _run_next_batch(window)
            timer = QTimer(window)
            timer.setSingleShot(True)
            timer.timeout.connect(_delayed_cb)
            timer.start(int(delay_seconds * 1000))
            window._batch_delay_timer = timer
        else:
            _run_next_batch(window)
    else:
        _on_generation_finished(window, state['errors'])

def _preprocess_frames_for_batch(window):
    from dialogs.video_proxy_dialog import VideoProxyDialog
    state = window._batch_processing_state
    stop_flag = state.get('stop_flag')
    batch = state['_current_batch']

    video_frame_map = state.get('video_frame_map', {})
    video_files = [
        row[1] for row in batch
        if os.path.splitext(row[1])[1].lower() in VIDEO_EXTENSIONS and row[1] not in video_frame_map
    ]
    if not video_files:
        _run_next_batch(window)
        return

    print(f"[BATCH {state['current'] + 1}] Extracting frames for {len(video_files)} video(s)...")
    dlg = VideoProxyDialog(parent=window, batch_info={'total_files': len(video_files)}, mode='frame_extraction')
    worker = BatchFrameExtractionWorker(video_files)

    def on_progress(data):
        status = data.get("status")
        if status == "file_start":
            dlg.set_current_file(data.get("file_index", 0), data.get("filename", ""))
        elif status == "file_done":
            dlg.update_batch_progress(data.get("completed_count", 0))
        else:
            dlg.update_progress(data)
        QApplication.processEvents()

    def on_all_finished(results):
        state['video_frame_map'].update(results)
        dlg.close()

    def on_cancel():
        worker.stop()
        if stop_flag:
            stop_flag['stop'] = True
        dlg.request_stop()

    worker.progress_update.connect(on_progress)
    worker.all_finished.connect(on_all_finished)
    try:
        dlg.cancel_button.clicked.disconnect()
    except Exception:
        pass
    dlg.cancel_button.clicked.connect(on_cancel)
    worker.start()
    dlg.exec()

    if stop_flag and stop_flag.get('stop'):
        print(f"[BATCH {state['current'] + 1}] Frame extraction cancelled")
        window.table.progress_bar.setVisible(False)
        window.table.set_progress_info('', visible=False)
        return

    _run_next_batch(window)


def _preprocess_proxy_for_batch(window):
    from dialogs.video_proxy_dialog import VideoProxyDialog
    state = window._batch_processing_state
    stop_flag = state.get('stop_flag')
    batch = state['_current_batch']
    proxy_setting = get_video_proxy_setting()

    video_proxy_map = state.get('video_proxy_map', {})
    video_files = [
        row[1] for row in batch
        if os.path.splitext(row[1])[1].lower() in VIDEO_EXTENSIONS and row[1] not in video_proxy_map
    ]
    if not video_files:
        _run_next_batch(window)
        return

    print(f"[BATCH {state['current'] + 1}] Creating proxy for {len(video_files)} video(s) with setting: {proxy_setting}...")
    dlg = VideoProxyDialog(parent=window, batch_info={'total_files': len(video_files)})
    worker = BatchVideoProxyWorker(video_files, proxy_setting)

    def on_progress(data):
        status = data.get("status")
        if status == "file_start":
            dlg.set_current_file(data.get("file_index", 0), data.get("filename", ""))
        elif status == "file_done":
            dlg.update_batch_progress(data.get("completed_count", 0))
        else:
            dlg.update_progress(data)
        QApplication.processEvents()

    def on_all_finished(results):
        state['video_proxy_map'].update(results)
        dlg.close()

    def on_cancel():
        worker.stop()
        if stop_flag:
            stop_flag['stop'] = True
        dlg.request_stop()

    worker.progress_update.connect(on_progress)
    worker.all_finished.connect(on_all_finished)
    try:
        dlg.cancel_button.clicked.disconnect()
    except Exception:
        pass
    dlg.cancel_button.clicked.connect(on_cancel)
    worker.start()
    dlg.exec()

    if stop_flag and stop_flag.get('stop'):
        print(f"[BATCH {state['current'] + 1}] Proxy creation cancelled")
        window.table.progress_bar.setVisible(False)
        window.table.set_progress_info('', visible=False)
        return

    _run_next_batch(window)


def _run_next_batch(window):
    state = window._batch_processing_state
    if state.get('should_stop', False):
        _on_generation_finished(window, state['errors'], stopped=True)
        return
    if state['current'] >= len(state['batches']):
        _on_generation_finished(window, state['errors'])
        return
    
    # Refresh configuration from JSON for each batch run
    try:
        fresh_config = get_fresh_ai_config()
        print(f"[BATCH {state['current'] + 1}] Loading fresh config from JSON...")
    except Exception as e:
        print(f"[ERROR] Failed to load fresh config: {e}")
    
    batch = state['batches'][state['current']]
    
    # Get variables from state first
    is_rolling_mode = state.get('is_rolling_mode', False)
    is_parallel_mode = state.get('is_parallel_mode', False)
    api_keys_list = state.get('api_keys_list', [])
    
    # Handle PARALLEL mode - batch is a list of parallel tasks (a "round")
    if is_parallel_mode and isinstance(batch, list) and len(batch) > 0 and isinstance(batch[0], dict) and 'api_info' in batch[0]:
        _run_parallel_round(window, state, batch)
        return
    
    # Extract batch data - could be dict (single parallel task fallback) or list (normal)
    if is_parallel_mode and isinstance(batch, dict) and 'api_info' in batch:
        batch_files = batch['files']
        batch_api_info = batch['api_info']
        api_key = batch_api_info['api_key']
        service = batch_api_info['service']
        model = batch_api_info['model']
        state['api_key'] = api_key
        state['service'] = service
        state['model'] = model
        print(f"[BATCH {state['current'] + 1}] [PARALLEL] Using API: {service} - {model} (***{api_key[-5:] if len(api_key) >= 5 else api_key}) with {len(batch_files)} files")
        batch = batch_files
    # For rolling mode, use current API from api_keys_list based on current_api_index
    elif is_rolling_mode and api_keys_list:
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
        # Normal mode (non-parallel, non-rolling) - use API from state
        api_key = state['api_key']
        service = state['service']
        model = state['model']

    # Per-batch video pre-processing: only process this batch's videos, not all upfront
    state['_current_batch'] = batch
    if not is_parallel_mode:
        batch_video_files = [
            row[1] for row in batch
            if os.path.splitext(row[1])[1].lower() in VIDEO_EXTENSIONS
        ]
        if batch_video_files:
            prefer_frame = get_prefer_frame_analysis()
            proxy_setting = get_video_proxy_setting()
            video_frame_map = state.get('video_frame_map', {})
            video_proxy_map = state.get('video_proxy_map', {})
            if prefer_frame:
                if any(v not in video_frame_map for v in batch_video_files):
                    _preprocess_frames_for_batch(window)
                    return
            elif proxy_setting != "Off":
                if any(v not in video_proxy_map for v in batch_video_files):
                    _preprocess_proxy_for_batch(window)
                    return

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
    # Set parallel mode flag if applicable
    if is_parallel_mode:
        worker.is_parallel_mode = True
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
        QApplication.processEvents()
    
    def on_progress(cur, total):
        if state.get('should_stop', False) or (stop_flag and stop_flag.get('stop')):
            window.table.set_progress_info('Stopping process...')
            window.table.progress_bar.setMinimum(0)
            window.table.progress_bar.setMaximum(0)
            _set_gen_btn_stop_state(window, False, is_stopping=True)
        else:
            current_mode = state.get('mode', 'all')
            if is_parallel_mode:
                # Show parallel API processing progress
                num_apis = len(api_keys_list) if api_keys_list else 1
                label_text = f"Parallel API Processing ({num_apis} APIs) - {cur}/{total} files"
                if hasattr(window, 'statusbar'):
                    window.statusbar.showMessage(f"Processing {cur}/{total} files in parallel across {num_apis} API keys", 3000)
            elif is_rolling_mode:
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
            QApplication.processEvents()
            _on_generation_finished(window, state['errors'], stopped=True)
            return
        cache_results = worker._results
        
        # Get current service and model from state for fallback
        current_service = state.get('service', 'unknown')
        current_model = state.get('model', 'unknown')
        
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
            result_service = result.get("service", current_service)
            result_model = result.get("model", current_model)
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
                window._session_token_input = getattr(window, '_session_token_input', 0) + token_input
                window._session_token_output = getattr(window, '_session_token_output', 0) + token_output
                window._session_token_total = getattr(window, '_session_token_total', 0) + token_total
            
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
        
        # Count successes and failures in this batch
        total_batch = len(cache_results)
        failed_count = sum(1 for idx, result in cache_results 
                          if isinstance(result, dict) and (not result.get("title") or result.get("error_message")))
        success_count = total_batch - failed_count
        
        # Track member usage
        if _track_member_usage_and_check_limit(window, success_count):
            state['current'] += 1
            if errors:
                state['errors'].extend(errors)
            _on_generation_finished(window, state['errors'])
            return

        # Determine batch status
        batch_completely_failed = (failed_count == total_batch and total_batch > 0)
        batch_partially_failed = (failed_count > 0 and success_count > 0)
        
        # Handle parallel API processing fallback logic
        if is_parallel_mode and api_keys_list:
            # For parallel mode, if a specific API fails, we have fallback options
            if batch_completely_failed:
                print(f"[PARALLEL] Batch completely failed ({failed_count}/{total_batch}). Using fallback API from pool.")
                
                # Build list of failed files
                failed_files_batch = []
                for idx, result in cache_results:
                    if isinstance(result, dict) and (not result.get("title") or result.get("error_message")):
                        image_path = result.get("image_path")
                        for row in batch:
                            if row[1] == image_path:
                                failed_files_batch.append(row)
                                break
                
                current_api_index = state.get('current_api_index', 0)
                
                # Try to find next available API
                attempted_count = state.get('batch_retry_count', 0)
                max_retries = len(api_keys_list) - 1  # We already tried the first API
                
                if attempted_count < max_retries and failed_files_batch:
                    next_api_index = (current_api_index + 1) % len(api_keys_list)
                    if next_api_index >= len(api_keys_list):
                        next_api_index = 0
                    
                    # Skip current API index, try next
                    state['batch_retry_count'] = attempted_count + 1
                    state['current_api_index'] = next_api_index
                    
                    next_api_info = api_keys_list[next_api_index]
                    next_service = next_api_info.get('service', '')
                    next_api_key = next_api_info.get('api_key', '')
                    
                    print(f"[PARALLEL] Retrying {len(failed_files_batch)} failed files with API #{next_api_index + 1}: {next_service}")
                    
                    # Update display
                    label_text = window.table.get_progress_format_text("parallel", next_service, next_api_key)
                    window.table.set_progress_info(f"{label_text} (Retrying {len(failed_files_batch)} failed files with fallback API...)")
                    
                    # Replace current batch with failed files only and retry
                    state['batches'][state['current']] = {
                        'files': failed_files_batch,
                        'api_info': next_api_info,
                        'is_parallel_task': True
                    }
                    
                    QApplication.processEvents()
                    
                    # Delay before retry
                    delay_seconds = get_delay_interval()
                    if delay_seconds > 0:
                        if hasattr(window, 'statusbar'):
                            window.statusbar.showMessage(f"Waiting {delay_seconds:.1f} seconds before retrying with fallback API...")
                        def _retry_parallel_cb():
                            state2 = getattr(window, '_batch_processing_state', {})
                            stop_flag2 = state2.get('stop_flag')
                            if state2.get('should_stop', False) or (stop_flag2 and stop_flag2.get('stop')):
                                if hasattr(window, 'statusbar'):
                                    window.statusbar.clearMessage()
                                _on_generation_finished(window, state2.get('errors', []), stopped=True)
                                window._batch_delay_timer = None
                                return
                            window._batch_delay_timer = None
                            _run_next_batch(window)
                        timer = QTimer(window)
                        timer.setSingleShot(True)
                        timer.timeout.connect(_retry_parallel_cb)
                        timer.start(int(delay_seconds * 1000))
                        window._batch_delay_timer = timer
                    else:
                        if hasattr(window, 'statusbar'):
                            window.statusbar.clearMessage()
                        _run_next_batch(window)
                    return
                else:
                    # All APIs failed for this batch
                    print(f"[PARALLEL] All fallback APIs exhausted for batch {state.get('current', 0) + 1}")
                    # Continue with partial results, don't stop completely
            
            # Reset parallel retry counter for next batch if successful
            if not batch_completely_failed:
                state['batch_retry_count'] = 0
        
        # Handle rolling API retry logic
        elif is_rolling_mode and api_keys_list:
            # Case 1: Partial failure - retry failed files only with SAME API (parsing errors)
            if batch_partially_failed:
                retry_count = state.get('batch_same_api_retry', 0)
                max_same_api_retries = get_max_retries()
                
                if retry_count < max_same_api_retries:
                    print(f"[ROLLING] Batch partially failed ({success_count} succeeded, {failed_count} failed). Retrying failed files with same API (attempt {retry_count + 1}/{max_same_api_retries}).")
                    
                    # Build list of failed files only
                    failed_files_batch = []
                    for idx, result in cache_results:
                        if isinstance(result, dict) and (not result.get("title") or result.get("error_message")):
                            # Find original row for this failed file
                            image_path = result.get("image_path")
                            for row in batch:
                                if row[1] == image_path:
                                    failed_files_batch.append(row)
                                    break
                    
                    if failed_files_batch:
                        # Update batch to only contain failed files
                        state['batches'][state['current']] = failed_files_batch
                        state['batch_same_api_retry'] = retry_count + 1
                        
                        # Update display
                        current_service = state.get('service', '')
                        current_api_key = state.get('api_key', '')
                        label_text = window.table.get_progress_format_text("rolling", current_service, current_api_key)
                        window.table.set_progress_info(f"{label_text} (Retrying {len(failed_files_batch)} failed files with same API...)")
                        
                        QApplication.processEvents()
                        
                        # Delay before retry - get fresh from config
                        delay_seconds = get_delay_interval()
                        if delay_seconds > 0:
                            if hasattr(window, 'statusbar'):
                                window.statusbar.showMessage(f"Waiting {delay_seconds:.1f} seconds before retrying failed files...")
                            def _retry_same_api_cb():
                                state2 = getattr(window, '_batch_processing_state', {})
                                stop_flag2 = state2.get('stop_flag')
                                if state2.get('should_stop', False) or (stop_flag2 and stop_flag2.get('stop')):
                                    if hasattr(window, 'statusbar'):
                                        window.statusbar.clearMessage()
                                    _on_generation_finished(window, state2.get('errors', []), stopped=True)
                                    window._batch_delay_timer = None
                                    return
                                window._batch_delay_timer = None
                                _run_next_batch(window)  # Retry failed files with same API
                            timer = QTimer(window)
                            timer.setSingleShot(True)
                            timer.timeout.connect(_retry_same_api_cb)
                            timer.start(int(delay_seconds * 1000))
                            window._batch_delay_timer = timer
                        else:
                            if hasattr(window, 'statusbar'):
                                window.statusbar.clearMessage()
                            _run_next_batch(window)  # Retry failed files with same API
                        return  # Don't proceed to next batch yet
                else:
                    # Max same-API retries reached, treat remaining failures as acceptable and move on
                    print(f"[ROLLING] Max same-API retries reached. Moving to next batch. {failed_count} files still failed.")
                    state['batch_same_api_retry'] = 0  # Reset for next batch
            
            # Case 2: Complete failure - roll to next API and retry entire batch
            elif batch_completely_failed:
                retry_count = state.get('batch_retry_count', 0)
                max_retries = len(api_keys_list) - 1  # -1 because first API was already tried
                
                print(f"[ROLLING] Batch completely failed ({failed_count}/{total_batch}). Rolling to next API.")
                
                if retry_count < max_retries:
                    # Try next API for the same batch
                    state['batch_retry_count'] = retry_count + 1
                    state['batch_same_api_retry'] = 0  # Reset same-API retry counter
                    next_api_index = (state.get('current_api_index', 0) + 1) % len(api_keys_list)
                    # Ensure index is within bounds
                    if next_api_index >= len(api_keys_list):
                        next_api_index = 0
                    state['current_api_index'] = next_api_index
                    
                    next_api_info = api_keys_list[next_api_index]
                    next_service = next_api_info.get('service', '')
                    next_api_key = next_api_info.get('api_key', '')
                    
                    # Update display for retry
                    label_text = window.table.get_progress_format_text("rolling", next_service, next_api_key)
                    window.table.set_progress_info(f"{label_text} (Retrying batch with next API...)")
                    
                    QApplication.processEvents()
                    
                    # Delay before retry - get fresh from config
                    delay_seconds = get_delay_interval()
                    if delay_seconds > 0:
                        if hasattr(window, 'statusbar'):
                            window.statusbar.showMessage(f"Waiting {delay_seconds:.1f} seconds before retrying with next API...")
                        def _retry_cb():
                            state2 = getattr(window, '_batch_processing_state', {})
                            stop_flag2 = state2.get('stop_flag')
                            if state2.get('should_stop', False) or (stop_flag2 and stop_flag2.get('stop')):
                                if hasattr(window, 'statusbar'):
                                    window.statusbar.clearMessage()
                                _on_generation_finished(window, state2.get('errors', []), stopped=True)
                                window._batch_delay_timer = None
                                return
                            window._batch_delay_timer = None
                            _run_next_batch(window)  # Retry same batch with next API
                        timer = QTimer(window)
                        timer.setSingleShot(True)
                        timer.timeout.connect(_retry_cb)
                        timer.start(int(delay_seconds * 1000))
                        window._batch_delay_timer = timer
                    else:
                        if hasattr(window, 'statusbar'):
                            window.statusbar.clearMessage()
                        _run_next_batch(window)  # Retry same batch with next API
                    return  # Don't proceed to next batch yet
                else:
                    # All APIs tried and still failed - show detailed warning and stop
                    print(f"[ROLLING] All {len(api_keys_list)} APIs failed for batch {state.get('current', 0) + 1}")
                    
                    # Determine last failed file from cache_results
                    last_failed_file = None
                    for _idx, _res in reversed(cache_results):
                        if isinstance(_res, dict) and (_res.get('error_message') or not _res.get('title')):
                            last_failed_file = _res.get('image_path')
                            break
                    if last_failed_file is None and batch:
                        last_failed_file = batch[-1][1]
                    last_failed_name = os.path.basename(last_failed_file) if last_failed_file else 'Unknown'

                    apis_tried = len(api_keys_list)
                    failed_batch_num = state.get('current', 0) + 1

                    # Build list of tried APIs with details
                    tried_apis_details = []
                    for api_info in api_keys_list:
                        api_key = api_info.get('api_key', '')
                        service = api_info.get('service', '')
                        model = api_info.get('model', '')
                        note = api_info.get('note', '')
                        
                        # Mask API key
                        masked_key = f"***{api_key[-5:]}" if api_key and len(api_key) >= 5 else f"***{api_key}" if api_key else "No key"
                        
                        # Format line with note if available
                        if note:
                            line = f"  • {service.upper()} - {model} ({masked_key}) - {note}"
                        else:
                            line = f"  • {service.upper()} - {model} ({masked_key})"
                        tried_apis_details.append(line)
                    
                    apis_list_text = "\n".join(tried_apis_details)

                    msg = (
                        f"Image-Tea has tried {apis_tried} API key(s) and all attempts have failed while processing batch {failed_batch_num}.\n\n"
                        f"Last failed file: {last_failed_name}\n\n"
                        f"APIs tried (in order):\n{apis_list_text}\n\n"
                        "Please check your API keys and their quota/status before continuing."
                    )

                    QMessageBox.warning(window, "All API Keys Failed", msg)

                    # Mark batch files as failed and stop processing
                    for row in batch:
                        filepath = row[1]
                        window.db.update_file_status(filepath, "failed")
                    _on_generation_finished(window, state['errors'], stopped=False)
                    return
        
        # Normal mode: retry only failed files up to max_retries
        if not is_parallel_mode and not is_rolling_mode and failed_count > 0:
            file_retry_count = state.get('file_retry_count', 0)
            max_file_retries = get_max_retries()
            if file_retry_count < max_file_retries:
                failed_rows = []
                for idx, result in cache_results:
                    if isinstance(result, dict) and (not result.get("title") or result.get("error_message")):
                        image_path = result.get("image_path")
                        for row in batch:
                            if row[1] == image_path:
                                failed_rows.append(row)
                                break
                if failed_rows:
                    state['batches'][state['current']] = failed_rows
                    state['file_retry_count'] = file_retry_count + 1
                    print(f"[RETRY] Retrying {len(failed_rows)} failed files (attempt {file_retry_count + 1}/{max_file_retries})")
                    _rmode = state.get('mode', 'all')
                    _rsvc = state.get('service', '')
                    _rkey = state.get('api_key', '')
                    _rlbl = window.table.get_progress_format_text(_rmode, _rsvc, _rkey)
                    window.table.set_progress_info(f"{_rlbl} (Retrying {len(failed_rows)} failed, attempt {file_retry_count + 1}/{max_file_retries})...")
                    QApplication.processEvents()
                    retry_delay = get_delay_interval()
                    if retry_delay > 0:
                        def _retry_normal_cb():
                            _st = getattr(window, '_batch_processing_state', {})
                            _sf = _st.get('stop_flag')
                            if _st.get('should_stop', False) or (_sf and _sf.get('stop')):
                                _on_generation_finished(window, _st.get('errors', []), stopped=True)
                                window._batch_delay_timer = None
                                return
                            window._batch_delay_timer = None
                            _run_next_batch(window)
                        _rtimer = QTimer(window)
                        _rtimer.setSingleShot(True)
                        _rtimer.timeout.connect(_retry_normal_cb)
                        _rtimer.start(int(retry_delay * 1000))
                        window._batch_delay_timer = _rtimer
                    else:
                        _run_next_batch(window)
                    return
            state['file_retry_count'] = 0

        # Reset retry counters when moving to next batch successfully
        if not (is_rolling_mode and (batch_partially_failed or batch_completely_failed)):
            state['batch_retry_count'] = 0
            state['batch_same_api_retry'] = 0
        
        # Update progress display
        current_mode = state.get('mode', 'all')
        if is_parallel_mode:
            # For parallel mode, show that we're using parallel processing
            num_apis = len(api_keys_list) if api_keys_list else 1
            label_text = window.table.get_progress_format_text("parallel", "", "")
            if "parallel" not in label_text.lower():
                label_text = f"Parallel API Processing ({num_apis} APIs)"
        elif is_rolling_mode:
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
        QApplication.processEvents()
        
        # Move to next batch only if not retrying current batch
        # (retry logic above would have returned early if retrying)
        state['batch_retry_count'] = 0
        state['batch_same_api_retry'] = 0
        state['file_retry_count'] = 0
        state['current'] += 1
        if errors:
            state['errors'].extend(errors)
        
        if state['current'] < len(state['batches']):
            # Get fresh delay from config before next batch
            delay_seconds = get_delay_interval()
            if delay_seconds > 0:
                if hasattr(window, 'statusbar'):
                    window.statusbar.showMessage(f"Waiting {delay_seconds:.1f} seconds delay before next batch...")
                def _delayed_cb():
                    state2 = getattr(window, '_batch_processing_state', {})
                    stop_flag2 = state2.get('stop_flag')
                    if state2.get('should_stop', False) or (stop_flag2 and stop_flag2.get('stop')):
                        if hasattr(window, 'statusbar'):
                            window.statusbar.clearMessage()
                        _on_generation_finished(window, state2.get('errors', []), stopped=True)
                        window._batch_delay_timer = None
                        return
                    window._batch_delay_timer = None
                    _run_next_batch(window)
                timer = QTimer(window)
                timer.setSingleShot(True)
                timer.timeout.connect(_delayed_cb)
                timer.start(int(delay_seconds * 1000))
                window._batch_delay_timer = timer
            else:
                if hasattr(window, 'statusbar'):
                    window.statusbar.clearMessage()
                _run_next_batch(window)
        else:
            # Clear delay message before finishing
            if hasattr(window, 'statusbar'):
                window.statusbar.clearMessage()
            _run_next_batch(window)
    
    def on_timing_updated(gen_time, avg_time, longest_time, last_time):
        if hasattr(window, "stats_section"):
            window.stats_section.update_generation_times(gen_time, avg_time, longest_time, last_time)
    
    worker.signals.api_rolled.connect(on_api_rolled)
    worker.signals.progress.connect(on_progress)
    worker.signals.finished.connect(on_finished)
    worker.signals.timing_updated.connect(on_timing_updated)
    cleanup_temp_folder()
    worker.start()

def stop_generate_metadata(window):
    state = getattr(window, '_batch_processing_state', None)
    if not state:
        print("[STOP] No active generation state found.")
        return

    # Always signal stop deterministically
    state['should_stop'] = True
    stop_flag = state.get('stop_flag')
    if stop_flag is not None:
        stop_flag['stop'] = True

    # Update UI to stopping regardless of whether a worker is running
    table_widget = window.table.table
    for row in range(table_widget.rowCount()):
        status_item = table_widget.item(row, 8)
        if status_item and status_item.text().lower() == "processing":
            window.table.set_row_status_color(row, "stopping")
    window.table.set_progress_info('Stopping process...')
    window.table.progress_bar.setMinimum(0)
    window.table.progress_bar.setMaximum(0)
    window.table.progress_bar.setVisible(True)
    _set_gen_btn_stop_state(window, False, is_stopping=True)
    QApplication.processEvents()

    # Stop running worker if present (single worker mode)
    worker = state.get('worker')
    if worker and worker.isRunning():
        print("[STOP] Stopping batch worker thread...")
        worker.stop()
    
    # Stop parallel workers if present (parallel mode)
    parallel_workers = state.get('parallel_workers', [])
    for pw in parallel_workers:
        if pw and pw.isRunning():
            print("[STOP] Stopping parallel worker thread...")
            pw.stop()

    # Cancel any pending inter-batch delay timer immediately
    if hasattr(window, '_batch_delay_timer') and window._batch_delay_timer:
        try:
            window._batch_delay_timer.stop()
            window._batch_delay_timer.deleteLater()
        except Exception as e:
            print(f"[STOP] Failed to stop batch delay timer: {e}")
        window._batch_delay_timer = None
        if hasattr(window, 'statusbar'):
            window.statusbar.clearMessage()

    # If there is no active worker running, schedule a 3s cooldown then finalize
    if not (worker and worker.isRunning()):
        if hasattr(window, '_stop_cooldown_timer') and window._stop_cooldown_timer:
            try:
                window._stop_cooldown_timer.stop()
                window._stop_cooldown_timer.deleteLater()
            except Exception as e:
                print(f"[STOP] Failed to reset stop cooldown timer: {e}")
            window._stop_cooldown_timer = None
        def _finish_after_cooldown():
            # Clear the cooldown timer first so _on_generation_finished is not deferred
            window._stop_cooldown_timer = None
            # If a deferred finish was set during cooldown, use it
            if hasattr(window, '_deferred_finish') and window._deferred_finish:
                errors2, stopped2 = window._deferred_finish
                window._deferred_finish = None
                _on_generation_finished(window, errors2, stopped2)
            else:
                state2 = getattr(window, '_batch_processing_state', None)
                if state2:
                    _on_generation_finished(window, state2.get('errors', []), stopped=True)
            if hasattr(window, 'statusbar'):
                window.statusbar.clearMessage()
        timer = QTimer(window)
        timer.setSingleShot(True)
        timer.timeout.connect(_finish_after_cooldown)
        timer.start(3000)
        window._stop_cooldown_timer = timer
        print("[STOP] Scheduled finalization after 3s cooldown.")
    
    # Clear error buffer saat stop
    try:
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
    # If stop cooldown in progress, defer finalization
    if hasattr(window, '_stop_cooldown_timer') and window._stop_cooldown_timer:
        window._deferred_finish = (errors, stopped)
        print("[DEFER] Finalization deferred until stop cooldown completes.")
        return

    window.is_generating = False
    
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
        if hasattr(window, 'statusbar'):
            window.statusbar.set_api_info()
    
    if hasattr(window, "stats_section") and hasattr(window, "_gen_total_time_start"):
        total_time_ms = int((time.perf_counter() - window._gen_total_time_start) * 1000)
        window.stats_section.update_total_time(total_time_ms)
    
    # Refresh table and hide all spinners BEFORE showing any dialogs
    QApplication.processEvents()
    window.table.refresh_table()
    if hasattr(window.table, '_hide_all_spinners'):
        window.table._hide_all_spinners()
    QApplication.processEvents()

    # Flush buffered error dialogs AFTER table is clean
    try:
        invoker.disable_buffering()
        # Remove files that eventually succeeded after retries from the error buffer
        try:
            all_files = window.db.get_all_files()
            succeeded_paths = {row[1] for row in all_files if row[6] and row[6].lower() == 'success'} if all_files else set()
            if succeeded_paths:
                invoker.remove_succeeded_files(succeeded_paths)
                print(f"[Batch] Filtered {len(succeeded_paths)} succeeded file(s) from error buffer")
        except Exception as ef:
            print(f"[Batch] Failed to filter succeeded files from error buffer: {ef}")
        invoker.flush_all()
        # Re-enable buffering untuk batch berikutnya
        invoker.enable_buffering()
    except Exception as e:
        print(f"[Batch] Failed to flush error dialogs: {e}")
    
    # Stop the estimation timer but keep the final stats visible
    if hasattr(window, "stats_section"):
        window.stats_section.stop_estimation_timer()
    
    update_token_stats_ui(window)
    
    if errors:
        print("[Batch Errors]")
        for err in errors:
            print(err)
    
    # Show completion message for rolling or parallel mode
    if not stopped:
        is_parallel_mode = state.get('is_parallel_mode', False)
        is_rolling_mode = state.get('is_rolling_mode', False)
        
        if is_parallel_mode and hasattr(window, 'statusbar'):
            api_count = len(state.get('api_keys_list', []))
            window.statusbar.showMessage(f"Parallel API Processing completed using {api_count} API keys", 5000)
        elif is_rolling_mode and hasattr(window, 'statusbar'):
            api_count = len(state.get('api_keys_list', []))
            window.statusbar.showMessage(f"Rolling APIs completed using {api_count} API keys", 5000)

    total_time_ms = 0
    if hasattr(window, '_gen_total_time_start'):
        total_time_ms = int((time.perf_counter() - window._gen_total_time_start) * 1000)
    token_input = getattr(window, '_session_token_input', 0)
    token_output = getattr(window, '_session_token_output', 0)
    token_total = getattr(window, '_session_token_total', 0)
    success_count = window.db.get_files_count(status_filter='success')
    failed_count = window.db.get_files_count(status_filter='failed')
    stopped_count = window.db.get_files_count(status_filter='stopped') if stopped else 0
    total_files = success_count + failed_count + stopped_count
    dlg = GenerationResultDialog(
        parent=window,
        total_files=total_files,
        success_count=success_count,
        failed_count=failed_count,
        token_input=token_input,
        token_output=token_output,
        token_total=token_total,
        total_time_ms=total_time_ms,
        stopped=stopped,
        stopped_count=stopped_count
    )
    tw_queue = getattr(window.table, '_tw_queue', None)
    if tw_queue:
        window.table._pending_result_dialog = dlg
    else:
        if hasattr(window.table, '_hide_all_spinners'):
            window.table._hide_all_spinners()
        dlg.exec()
    
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
        QApplication.processEvents()
    else:
        print("[CLEANUP] No stuck processing files found")
    
    return cleanup_count
