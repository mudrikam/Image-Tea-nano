import os
import json
import base64
import time
import re
from openai import OpenAI
from config import BASE_PATH
from helpers.ai_helper.ai_variation_helper import generate_timestamp, generate_token
import threading
from PySide6.QtWidgets import QApplication
from helpers.image_compression_helper import compress_and_save_image
from dialogs.video_proxy_dialog import VideoProxyDialog
from helpers.video_proxy_helper import VideoProxyWorker, invoke_in_main_thread, get_video_proxy_invoker, create_video_proxy, get_video_proxy_setting

_generation_times_openai = []

def track_openai_generation_time(duration_ms):
    _generation_times_openai.append(duration_ms)
    if len(_generation_times_openai) > 1000:
        _generation_times_openai.pop(0)
    gen_time = duration_ms
    avg_time = int(sum(_generation_times_openai) / len(_generation_times_openai)) if _generation_times_openai else 0
    longest_time = max(_generation_times_openai) if _generation_times_openai else 0
    last_time = _generation_times_openai[-1] if _generation_times_openai else 0
    return gen_time, avg_time, longest_time, last_time


def _is_openrouter_key(api_key: str) -> bool:
    """Return True when the provided API key looks like an OpenRouter key.

    OpenRouter keys typically start with the prefix shown in the user's example:
    `sk-or-...`.
    """
    if not api_key or not isinstance(api_key, str):
        return False
    return bool(re.match(r"^sk-?or-", api_key))


def create_openai_client(api_key: str):
    """Create and return an OpenAI client, routing to OpenRouter when needed.

    If the api_key looks like an OpenRouter key, configure the official
    `openai.OpenAI` client with the OpenRouter `base_url` so calls are
    transparently sent to `openrouter.ai`.
    """
    if _is_openrouter_key(api_key):
        return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    return OpenAI(api_key=api_key)

def load_openai_prompt_vars():
    prompt_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompt_data = data["prompt"]
    shutterstock_map = data["shutterstock_category_map"]
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
        shutterstock_map,
        adobe_map
    )

def format_openai_prompt(
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
    shutterstock_map,
    adobe_map,
    filename=None
):
    title_reqs = title_requirements.replace("_MIN_LEN_", str(min_title_length)).replace("_MAX_LEN_", str(max_title_length))
    desc_reqs = description_requirements.replace("_MAX_DESC_LEN_", str(max_description_length))
    keywords_reqs = keywords_requirements.replace("_TAGS_COUNT_", str(required_tag_count))
    uniqueness = unique_token.replace("_TIMESTAMP_", generate_timestamp()).replace("_TOKEN_", generate_token())
    
    shutterstock_categories = {num: name for num, name in shutterstock_map.items()}
    adobe_categories = {num: name for num, name in adobe_map.items()}
    
    prompt_json = {
        "task": "Create high-quality image or video digital assets metadata",
        "output_format": {
            "type": "JSON",
            "keys": ["title", "description", "tags", "category", "filetype"],
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
    
    if filename:
        prompt_json["input_filename"] = filename
    
    if custom_prompt and custom_prompt.strip():
        prompt_json["mandatory_instruction"] = custom_prompt.strip()
    
    prompt_json["negative_prompt"] = [line for line in negative_prompt.split('\n') if line.strip()]
    prompt_json["system_instruction"] = [line for line in system_prompt.split('\n') if line.strip()]
    
    full_prompt = json.dumps(prompt_json, indent=2, ensure_ascii=False)
    
    print("="*80)
    print("OPENAI FULL PROMPT (JSON FORMAT):")
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
    text = text.replace('"', '').replace("'", "")
    # Replace all punctuation except comma with space
    text = re.sub(r'[^\w\s,]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def generate_metadata_openai(api_key, model, image_path, prompt=None, stop_flag=None):
    if stop_flag and stop_flag.get('stop'):
        return '', '', '', {}, '', '', 0, 0, 0
    start_time = time.perf_counter()
    try:
        ext = os.path.splitext(image_path)[1].lower()
        is_video = ext in ['.mp4', '.mpeg', '.mpg', '.mov', '.webm']
        filename = os.path.basename(image_path)
        is_openrouter = _is_openrouter_key(api_key)
        if is_video and not is_openrouter:
            error_message = (
                "OpenAI Vision API belum mendukung input video secara langsung. "
                "Silakan gunakan gambar atau pilih layanan Gemini untuk video. "
                "Jika di masa depan OpenAI sudah mendukung video, fitur ini akan segera ditambahkan."
            )
            return '', '', '', {}, '', error_message, 0, 0, 0
        client = create_openai_client(api_key)
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
                shutterstock_map,
                adobe_map
            ) = load_openai_prompt_vars()
            prompt = format_openai_prompt(
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
                shutterstock_map,
                adobe_map,
                filename=filename
            )
        if is_video:
            result_container = [None]
            finished_event = threading.Event()
            proxy_setting = get_video_proxy_setting()

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
                            print(f"[OpenAI] Dialog progress update error: {e}")

                    def on_finished(result):
                        if isinstance(result, str) and result:
                            result_container[0] = (result, None)
                        else:
                            result_container[0] = (None, 'proxy failed or cancelled')
                        try:
                            if dlg and dlg.isVisible():
                                dlg.close()
                        except Exception as e:
                            print(f"[OpenAI] Error closing dialog after proxy finished: {e}")
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
                        print(f"[OpenAI] Warning: failed to disconnect cancel button: {e}")
                    dlg.cancel_button.clicked.connect(on_cancel_clicked)

                    proxy_worker.start()
                    dlg.exec()
                except Exception as e:
                    print(f"[OpenAI] Dialog factory error: {e}")
                    try:
                        result_container[0] = (None, f"dialog factory error: {e}")
                    except Exception as e2:
                        print(f"[OpenAI] Failed to set result container after dialog factory error: {e2}")
                    try:
                        finished_event.set()
                    except Exception as e2:
                        print(f"[OpenAI] Failed to set finished_event after dialog factory error: {e2}")
                    raise

            invoked = invoke_in_main_thread(dialog_factory, (image_path, proxy_setting, stop_flag, result_container, finished_event))
            if not invoked:
                error_message = f"[OpenAI ERROR] Video proxy dialog could not be invoked for {image_path}; no GUI or invoker not registered."
                print(error_message)
                return '', '', '', {}, '', error_message, 0, 0, 0
            else:
                if not finished_event.wait(600):
                    error_message = f"[OpenAI ERROR] Video proxy dialog timeout"
                    print(error_message)
                    return '', '', '', {}, '', error_message, 0, 0, 0
                proxy_path, proxy_err = result_container[0]
                if proxy_err:
                    error_message = f"[OpenAI ERROR] Video proxy failed: {proxy_err}"
                    print(error_message)
                    return '', '', '', {}, '', error_message, 0, 0, 0
                video_to_upload = proxy_path or image_path
            video_mime_map = {
                '.mp4': 'video/mp4',
                '.mpeg': 'video/mpeg',
                '.mpg': 'video/mpeg',
                '.mov': 'video/mov',
                '.webm': 'video/webm'
            }
            mime_type = video_mime_map.get(ext, 'video/mp4')
            with open(video_to_upload, "rb") as f:
                video_bytes = f.read()
            video_b64 = base64.b64encode(video_bytes).decode("utf-8")
            video_data_url = f"data:{mime_type};base64,{video_b64}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "video_url", "video_url": {"url": video_data_url}}
                    ]
                }
            ]
        else:
            compressed_path = compress_and_save_image(image_path)
            if not compressed_path:
                error_message = f"[OpenAI ERROR] Failed to compress image: {image_path}"
                return '', '', '', {}, '', error_message, 0, 0, 0
            with open(compressed_path, "rb") as f:
                image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            image_data_url = f"data:image/jpeg;base64,{image_b64}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]
                }
            ]
        if stop_flag and stop_flag.get('stop'):
            return '', '', '', {}, '', '', 0, 0, 0
        response = client.chat.completions.create(
            model=model,
            messages=messages
        )
        
        print("="*80)
        print("OPENAI RAW RESPONSE:")
        print("="*80)
        print(response)
        print("="*80)
        
        token_input = 0
        token_output = 0
        token_total = 0
        usage = getattr(response, "usage", None)
        if usage:
            token_input = getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0)
            token_output = getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0)
            token_total = getattr(usage, "total_tokens", 0)
        text = None
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                text = choice.message.content
        if not text:
            text = str(response)
        
        print("="*80)
        print("OPENAI RAW TEXT:")
        print("="*80)
        print(text)
        print("="*80)
        
        try:
            def _extract_json_string_from_text(txt: str) -> str:
                txt = txt.strip()
                begin_marker = '<|begin_of_box|>'
                end_marker = '<|end_of_box|>'
                if txt.startswith(begin_marker) and txt.endswith(end_marker):
                    txt = txt[len(begin_marker):-len(end_marker)].strip()
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

            text_stripped = _extract_json_string_from_text(text)
            meta = json.loads(text_stripped)
            title = meta.get('title', '')
            description = meta.get('description', '')
            tags = meta.get('tags', [])
            if isinstance(tags, list):
                tags = ', '.join([str(tag).strip() for tag in tags])
            else:
                tags = str(tags)
            tags = tags.lower()
            category = meta.get('category', {})
            filetype = meta.get('filetype', '')
            error_message = ''
        except Exception as e:
            print(f"[OpenAI JSON PARSE ERROR] {e}")
            title = description = tags = ''
            category = {}
            filetype = ''
            error_message = f"[OpenAI JSON PARSE ERROR] {e}"
        if title:
            title = title_case_except(title)
            title = sanitize_text(title)
        if description:
            description = sanitize_text(description)
        return title, description, tags, category, filetype, error_message, token_input, token_output, token_total
    except Exception as e:
        err_str = str(e)
        error_message = f"[OpenAI ERROR] {err_str}"
        print(error_message)
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
                    code = m.group(1)
                elif 'rate limit' in err_str.lower() or 'quota' in err_str.lower():
                    code = '429'
            m = re.search(r"['\"]status['\"]\s*[:=]\s*['\"]([^'\"]+)['\"]", err_str)
            if m:
                status = m.group(1)
        except Exception as e2:
            print(f"[OpenAI] Error extracting code/status from exception: {e2}")
        try:
            if code or ('quota' in err_str.lower()) or ('rate limit' in err_str.lower()):
                signature = str(code) if not status else f"{code}|{status}"
                try:
                    from dialogs.ai_helper_error_code_dialog import invoker
                    invoker.showRequested.emit(signature, err_str, os.path.basename(image_path), 'openai')
                    # Kirim error code ke buffer untuk file ini
                    if signature in invoker._buffer:
                        error_code_map = invoker._buffer[signature].setdefault('error_code_map', {})
                        error_code_map[os.path.basename(image_path)] = code
                except Exception:
                    print("[Dialog Error] Failed to show error dialog")
        except Exception as e2:
            print(f"[OpenAI] Error during error-dialog notification: {e2}")
        return '', '', '', {}, '', error_message, 0, 0, 0
    finally:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        track_openai_generation_time(duration_ms)