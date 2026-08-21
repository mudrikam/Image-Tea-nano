import time
import os
import json
import re
import traceback
import google.genai as genai
from google.genai import types
from config import BASE_PATH
from helpers.ai_helper.ai_variation_helper import generate_timestamp, generate_token
import threading
from PySide6.QtWidgets import QApplication
from helpers.image_compression_helper import compress_and_save_image
from dialogs.video_proxy_dialog import VideoProxyDialog
from helpers.video_proxy_helper import VideoProxyWorker, invoke_in_main_thread, get_video_proxy_invoker, create_video_proxy, get_video_proxy_setting
from helpers.ai_helper.metadata_helper import normalize_tags
from helpers.ai_helper.openai_stream_helper import extract_response_text

_generation_times_gemini = []

def track_gemini_generation_time(duration_ms):
    _generation_times_gemini.append(duration_ms)
    if len(_generation_times_gemini) > 1000:
        _generation_times_gemini.pop(0)
    gen_time = duration_ms
    avg_time = int(sum(_generation_times_gemini) / len(_generation_times_gemini)) if _generation_times_gemini else 0
    longest_time = max(_generation_times_gemini) if _generation_times_gemini else 0
    last_time = _generation_times_gemini[-1] if _generation_times_gemini else 0
    return gen_time, avg_time, longest_time, last_time

def load_gemini_prompt_vars():
    prompt_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompt_data = data["prompt"]
    shutterstock_image_map = data["shutterstock_category_map"]
    shutterstock_video_map = data["shutterstock_video_category_map"]
    adobe_map = data["adobe_stock_category_map"]
    return (
        prompt_data["title_requirements"],
        prompt_data["description_requirements"],
        prompt_data["keywords_requirements"],
        prompt_data["general_guides"],
        prompt_data["strict_donts"],
        prompt_data["unique_token"],
        prompt_data["negative_prompt"],
        prompt_data["system_prompt"],
        prompt_data["custom_prompt"],
        data["min_title_length"],
        data["max_title_length"],
        data["max_description_length"],
        data["required_tag_count"],
        shutterstock_image_map,
        shutterstock_video_map,
        adobe_map
    )

def format_gemini_prompt(
    title_requirements,
    description_requirements,
    keywords_requirements,
    general_guides,
    strict_donts,
    unique_token,
    negative_prompt,
    system_prompt,
    custom_prompt,
    min_title_length,
    max_title_length,
    max_description_length,
    required_tag_count,
    shutterstock_image_map,
    shutterstock_video_map,
    adobe_map,
    filename=None,
    is_video=False,
    metadata_context=None,
    generate_prompt=False
):
    title_reqs = title_requirements.replace("_MIN_LEN_", str(min_title_length)).replace("_MAX_LEN_", str(max_title_length))
    desc_reqs = description_requirements.replace("_MAX_DESC_LEN_", str(max_description_length))
    keywords_reqs = keywords_requirements.replace("_TAGS_COUNT_", str(required_tag_count))
    uniqueness = unique_token.replace("_TIMESTAMP_", generate_timestamp()).replace("_TOKEN_", generate_token())

    shutterstock_map = shutterstock_video_map if is_video else shutterstock_image_map
    shutterstock_categories = {num: name for num, name in shutterstock_map.items()}
    adobe_categories = {num: name for num, name in adobe_map.items()}

    output_keys = ["title", "description", "tags", "category", "filetype"]
    if generate_prompt:
        output_keys.append("file_prompt")

    prompt_json = {
        "task": "Create high-quality image or video digital assets metadata",
        "output_format": {
            "type": "JSON",
            "keys": output_keys,
            "category_structure": {
                "shutterstock": {"primary": "number", "secondary": "number"},
                "adobe_stock": "number"
            }
        },
        "requirements": {
            "title": [line for line in title_reqs.split('\n') if line.strip()],
            "description": [line for line in desc_reqs.split('\n') if line.strip()],
            "keywords": [line for line in keywords_reqs.split('\n') if line.strip()]
        },
        "guidelines": {
            "general": [line for line in general_guides.split('\n') if line.strip()],
            "strict_donts": [line for line in strict_donts.split('\n') if line.strip()],
            "uniqueness": [line for line in uniqueness.split('\n') if line.strip()]
        },
        "categories": {
            "shutterstock": {
                "instruction": "Select TWO relevant categories - one PRIMARY (most relevant) and one SECONDARY (next most relevant)",
                "available_categories": shutterstock_categories
            },
            "adobe_stock": {
                "available_categories": adobe_categories
            }
        }
    }

    if generate_prompt:
        prompt_json["requirements"]["file_prompt"] = [
            "Generate a detailed, single-paragraph prompt suitable for an AI image-generation model.",
            "The prompt must describe the subject, composition, lighting, style, mood, and other visible details of the asset.",
            "Use natural English prose without bullet points, JSON, or meta references to the source.",
            "Keep the prompt under 1200 characters and avoid brand names, trademarks, or copyrighted references."
        ]

    if filename:
        prompt_json["input_filename"] = filename

    if metadata_context:
        if "context" not in prompt_json:
            prompt_json["context"] = {}
        prompt_json["context"]["existing_metadata"] = metadata_context
        prompt_json["context"]["note"] = "Use as context reference, prioritize image content"

    if custom_prompt and custom_prompt.strip():
        prompt_json["mandatory_instruction"] = custom_prompt.strip()

    prompt_json["negative_prompt"] = [line for line in negative_prompt.split('\n') if line.strip()]
    prompt_json["system_instruction"] = [line for line in system_prompt.split('\n') if line.strip()]

    full_prompt = json.dumps(prompt_json, indent=2, ensure_ascii=False)

    print("="*80)
    print("GEMINI FULL PROMPT (JSON FORMAT):")
    print("="*80)
    print(full_prompt)
    print("="*80)

    return full_prompt

def title_case_except(text):
    exceptions = {"to", "and", "at", "in", "on", "for", "with", "of", "the", "a", "an", "but", "or", "nor", "so", "yet", "as", "by", "from", "into", "over", "per", "via"}
    words = text.split()
    if not words:
        return text
    result = [words[0].capitalize()]
    for w in words[1:]:
        lw = w.lower()
        if lw in exceptions:
            result.append(lw)
        else:
            result.append(w.capitalize())
    return " ".join(result)

def sanitize_text(text):
    if not text:
        return text
    
    # Check if sanitization is enabled in config
    try:
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            ai_cfg = json.load(f)
        if not ai_cfg.get("metadata_sanitization_enabled", True):
            return text  # Skip sanitization
    except Exception:
        pass  # Default to sanitizing on error
    
    text = text.replace('"', '').replace("'", "")
    # Replace all punctuation except comma with space
    text = re.sub(r'[^\w\s,]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def generate_metadata_gemini(api_key, model, image_path, prompt=None, stop_flag=None, proxy_path=None, provider_endpoint=None, preextracted_frames=None, metadata_context=None, generate_prompt=False):
    if stop_flag and stop_flag.get('stop'):
        return '', '', '', '', '', 0, 0, 0, ''
    start_time = time.perf_counter()
    uploaded_file_id = None
    try:
        client = genai.Client(api_key=api_key)
        ext = os.path.splitext(image_path)[1].lower()
        is_video = ext in ['.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp', '.3gpp']
        filename = os.path.basename(image_path)
        if not prompt:
            (
                title_requirements,
                description_requirements,
                keywords_requirements,
                general_guides,
                strict_donts,
                unique_token,
                negative_prompt,
                system_prompt,
                custom_prompt,
                min_title_length,
                max_title_length,
                max_description_length,
                required_tag_count,
                shutterstock_image_map,
                shutterstock_video_map,
                adobe_map
            ) = load_gemini_prompt_vars()
            prompt = format_gemini_prompt(
                title_requirements,
                description_requirements,
                keywords_requirements,
                general_guides,
                strict_donts,
                unique_token,
                negative_prompt,
                system_prompt,
                custom_prompt,
                min_title_length,
                max_title_length,
                max_description_length,
                required_tag_count,
                shutterstock_image_map,
                shutterstock_video_map,
                adobe_map,
                filename=filename,
                is_video=is_video,
                metadata_context=metadata_context,
                generate_prompt=generate_prompt
            )
        # if a provider_endpoint is supplied, use the universal HTTP helper (works for text and data-URL images)
        used_custom_endpoint = False
        if provider_endpoint:
            from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
            try:
                endpoint_image_path = None
                endpoint_frame_paths = None
                if is_video and preextracted_frames:
                    compressed_frames = []
                    for fp in preextracted_frames:
                        cf = compress_and_save_image(fp)
                        if cf:
                            compressed_frames.append(cf)
                    endpoint_frame_paths = compressed_frames if compressed_frames else None
                elif not is_video:
                    endpoint_image_path = compress_and_save_image(image_path)
                if not endpoint_image_path:
                    print(f"[Gemini ERROR] Failed to compress image for custom endpoint: {image_path}")
                    return '', '', '', {}, '', f"[Gemini ERROR] Failed to compress image: {image_path}", 0, 0, 0, ''
                text, token_input, token_output, token_total = CustomEndpointHelper.call_endpoint_with_usage(api_key, provider_endpoint, 'gemini', model, prompt, endpoint_image_path, timeout=180, frame_paths=endpoint_frame_paths)
                used_custom_endpoint = True
            except Exception as e:
                print(f"[Gemini][CustomEndpoint] {e}")
                raise
        if is_video:
            if preextracted_frames:
                print(f"[Gemini] Using {len(preextracted_frames)} pre-extracted frames (prefer frame analysis mode)...")
                uploaded_frames = []
                uploaded_frame_ids = []
                for fp in preextracted_frames:
                    compressed = compress_and_save_image(fp)
                    if compressed:
                        fobj = client.files.upload(file=compressed)
                        fid = fobj.name if hasattr(fobj, 'name') else getattr(fobj, 'id', None)
                        if fid:
                            uploaded_frame_ids.append(fid)
                        uploaded_frames.append(fobj)
                if not uploaded_frames:
                    print(f"[Gemini ERROR] No frames could be uploaded for {image_path}")
                    return '', '', '', {}, '', f"[Gemini ERROR] Failed to upload frames for video: {image_path}", 0, 0, 0, ''
                video_context = (
                    f"[VIDEO FRAME CONTEXT] The {len(uploaded_frames)} images below are evenly-spaced frames "
                    f"extracted from the video file '{filename}'. "
                    "You MUST generate metadata that describes the VIDEO as a whole — NOT a single photo or portrait. "
                    "Title, description, and tags must reflect motion, scene, and activity visible across the frames."
                )
                contents = [video_context] + uploaded_frames + [prompt]
                uploaded_file_id = uploaded_frame_ids
            else:
                if proxy_path:
                    video_to_upload = proxy_path
                    print(f"[Gemini] Using pre-proxied video: {os.path.basename(proxy_path)}")
                else:
                    proxy_setting = get_video_proxy_setting()
                    if proxy_setting == "Off":
                        video_to_upload = image_path
                        print(f"[Gemini] Video proxy is Off, using original video: {os.path.basename(image_path)}")
                    else:
                        result_container = [None]
                        finished_event = threading.Event()

                        def dialog_factory(video_path, proxy_setting, stop_flag, result_container, finished_event):
                            try:
                                parent = QApplication.instance().activeWindow() if QApplication.instance() else None
                                dlg = VideoProxyDialog(parent=parent, batch_info={'total_files': 1})
                                dlg.set_current_file(0, os.path.basename(video_path))
                                proxy_worker = VideoProxyWorker(video_path, proxy_setting)

                                def on_progress(data):
                                    try:
                                        dlg.update_progress(data)
                                        QApplication.processEvents()
                                    except Exception as e:
                                        print(f"[Gemini] Dialog progress update error: {e}")

                                def on_finished(result):
                                    if isinstance(result, str) and result:
                                        result_container[0] = (result, None)
                                    else:
                                        result_container[0] = (None, 'proxy failed or cancelled')
                                    try:
                                        if dlg and dlg.isVisible():
                                            dlg.close()
                                    except Exception as e:
                                        print(f"[Gemini] Error closing dialog after proxy finished: {e}")
                                    finished_event.set()

                                proxy_worker.progress_update.connect(on_progress)
                                proxy_worker.finished.connect(on_finished)

                                def on_cancel_clicked():
                                    proxy_worker.stop()
                                    if stop_flag:
                                        stop_flag['stop'] = True
                                    dlg.request_stop()

                                try:
                                    dlg.cancel_button.clicked.disconnect()
                                except Exception as e:
                                    print(f"[Gemini] Warning: failed to disconnect cancel button: {e}")
                                dlg.cancel_button.clicked.connect(on_cancel_clicked)

                                proxy_worker.start()
                                dlg.exec()
                            except Exception as e:
                                print(f"[Gemini] Dialog factory error: {e}")
                                try:
                                    result_container[0] = (None, f"dialog factory error: {e}")
                                except Exception as e2:
                                    print(f"[Gemini] Failed to set result container after dialog factory error: {e2}")
                                try:
                                    finished_event.set()
                                except Exception as e2:
                                    print(f"[Gemini] Failed to set finished_event after dialog factory error: {e2}")
                                raise

                        invoked = invoke_in_main_thread(dialog_factory, (image_path, proxy_setting, stop_flag, result_container, finished_event))
                        if not invoked:
                            print(f"[Gemini ERROR] Video proxy dialog could not be invoked for {image_path}; no GUI or invoker not registered.")
                            return '', '', '', {}, '', '[Gemini ERROR] Video proxy dialog invocation failed', 0, 0, 0, ''
                        else:
                            if not finished_event.wait(600):
                                print("[Gemini ERROR] Video proxy dialog timeout")
                                return '', '', '', {}, '', '[Gemini ERROR] Video proxy timeout', 0, 0, 0, ''
                            proxy_result, proxy_err = result_container[0]
                            if proxy_err:
                                print(f"[Gemini ERROR] Video proxy failed: {proxy_err}")
                                return '', '', '', {}, '', f"[Gemini ERROR] Video proxy failed: {proxy_err}", 0, 0, 0, ''
                            video_to_upload = proxy_result or image_path

                myfile = client.files.upload(file=video_to_upload)
                uploaded_file_id = myfile.name if hasattr(myfile, 'name') else getattr(myfile, 'id', None)
                status = None
                max_wait_seconds = 600
                poll_interval = 1
                waited = 0
                while waited < max_wait_seconds:
                    if stop_flag and stop_flag.get('stop'):
                        return '', '', '', '', '', 0, 0, 0, ''
                    fileinfo = client.files.get(name=uploaded_file_id)
                    status = getattr(fileinfo, 'state', None) or getattr(fileinfo, 'status', None)
                    if status == 'ACTIVE':
                        break
                    time.sleep(poll_interval)
                    waited += poll_interval
                if status != 'ACTIVE':
                    print(f"[Gemini ERROR] File {uploaded_file_id} not ACTIVE after upload, status: {status}")
                    return '', '', '', '', '', 0, 0, 0, ''
                contents = [myfile, prompt]
        else:
            compressed_path = compress_and_save_image(image_path)
            if not compressed_path:
                print(f"[Gemini ERROR] Failed to compress image: {image_path}")
                return '', '', '', '', '', 0, 0, 0, ''
            myfile = client.files.upload(file=compressed_path)
            uploaded_file_id = myfile.name if hasattr(myfile, 'name') else getattr(myfile, 'id', None)
            contents = [myfile, prompt]
        if stop_flag and stop_flag.get('stop'):
            return '', '', '', '', '', 0, 0, 0, ''
        if not used_custom_endpoint:
            response = client.models.generate_content(
                model=model,
                contents=contents
            )

            print("="*80)
            print("GEMINI RAW RESPONSE:")
            print("="*80)
            print(response)
            print("="*80)

            token_input = 0
            token_output = 0
            token_total = 0
            usage = getattr(response, "usage_metadata", None)
            if usage:
                token_input = getattr(usage, "prompt_token_count", 0)
                token_output = getattr(usage, "candidates_token_count", 0)
                token_total = getattr(usage, "total_token_count", 0)
            text = None
            if hasattr(response, "candidates") and response.candidates:
                try:
                    text = response.candidates[0].content.parts[0].text
                except Exception:
                    text = extract_response_text(response)
            elif hasattr(response, "text"):
                text = response.text
            elif isinstance(response, dict) and 'text' in response:
                text = response['text']
            else:
                text = extract_response_text(response)
        else:
            # custom endpoint path: text + usage already provided by call_endpoint_with_usage
            if 'text' not in locals():
                text = ''
            if 'token_input' not in locals():
                token_input = token_output = token_total = 0

        
        print("="*80)
        print("GEMINI RAW TEXT:")
        print("="*80)
        print(text)
        print("="*80)
        
        try:
            def _extract_json_string_from_text(txt: str) -> str:
                txt = txt.strip()
                if '```' in txt:
                    start = txt.find('```')
                    end = txt.rfind('```')
                    inner = txt[start+3:end].strip()
                    if inner.lower().startswith('json'):
                        inner = inner[len('json'):].lstrip('\n \t')
                    return inner.strip()
                m = re.search(r"\{.*\}", txt, re.DOTALL)
                if m:
                    return m.group(0).strip()
                return txt

            text_clean = _extract_json_string_from_text(text)
            meta = json.loads(text_clean)
            title = meta.get('title', '')
            description = meta.get('description', '')
            tags = meta.get('tags', [])
            tags = normalize_tags(tags)
            category = meta.get('category', {})
            filetype = meta.get('filetype', '')
            file_prompt = meta.get('file_prompt', '') or ''
            file_prompt = str(file_prompt).strip()
            error_message = ''
        except Exception as e:
            print(f"[Gemini JSON PARSE ERROR] {e}")
            title = description = tags = ''
            category = {}
            filetype = ''
            file_prompt = ''
            error_message = f"[Gemini JSON PARSE ERROR] {e}"
        if title:
            title = title_case_except(title)
            title = sanitize_text(title)
        if description:
            description = sanitize_text(description)
        return title, description, tags, category, filetype, error_message, token_input, token_output, token_total, file_prompt
    except Exception as e:
        err_str = str(e)
        print(f"[Gemini ERROR] {err_str}")
        code = None
        status = None
        try:
            if hasattr(e, 'code'):
                code = getattr(e, 'code')
            elif hasattr(e, 'status_code'):
                code = getattr(e, 'status_code')
            else:
                m = re.search(r"(\b\d{3}\b)", err_str)
                if m:
                    code = int(m.group(1))
                elif 'rate limit' in err_str.lower() or 'quota' in err_str.lower():
                    code = 429
            m = re.search(r"['\"]status['\"]\s*[:=]\s*['\"]([^'\"]+)['\"]", err_str)
            if m:
                status = m.group(1)
        except Exception as e2:
            print(f"[Gemini] Error extracting code/status from exception: {e2}")
        try:
            if code or ('quota' in err_str.lower()) or ('rate limit' in err_str.lower()):
                signature = str(code) if not status else f"{code}|{status}"
                print(f"[Gemini] Emitting error dialog: code={code}, signature={signature}, service=gemini, file={os.path.basename(image_path)}")
                try:
                    from dialogs.ai_helper_error_code_dialog import invoker
                    invoker.showRequested.emit(signature, err_str, os.path.basename(image_path), 'gemini')
                    if signature in invoker._buffer:
                        error_code_map = invoker._buffer[signature].setdefault('error_code_map', {})
                        error_code_map[os.path.basename(image_path)] = code
                    print(f"[Gemini] Error dialog emission successful")
                except Exception as e_dialog:
                    print(f"[Dialog Error] Failed to show error dialog: {e_dialog}")
                    traceback.print_exc()
        except Exception as e2:
            print(f"[Gemini] Error during error-dialog notification: {e2}")
            traceback.print_exc()
        return '', '', '', {}, '', f"[Gemini ERROR] {err_str}", 0, 0, 0, ''
    finally:
        if uploaded_file_id:
            ids_to_delete = uploaded_file_id if isinstance(uploaded_file_id, list) else [uploaded_file_id]
            for fid in ids_to_delete:
                try:
                    client.files.delete(name=fid)
                    print(f"[Gemini] File {fid} deleted from server")
                    try:
                        client.files.get(name=fid)
                        print(f"[Gemini] Verification: file {fid} still exists after delete")
                    except Exception:
                        print(f"[Gemini] Verification: file {fid} not found (deleted).")
                except Exception:
                    print(f"[Gemini] File {fid} auto cleanup by Gemini")
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        track_gemini_generation_time(duration_ms)
