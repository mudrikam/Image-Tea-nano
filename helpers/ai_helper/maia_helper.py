from openai import OpenAI
import base64
import os
import json
import re
import time
import threading
import traceback
from config import BASE_PATH
from helpers.ai_helper.ai_variation_helper import generate_timestamp, generate_token
from helpers.image_compression_helper import compress_and_save_image
from helpers.video_proxy_helper import extract_video_frames

try:
    _cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
    with open(_cfg_path, 'r', encoding='utf-8') as _f:
        _cfg = json.load(_f)
    MAIA_BASE_URL = _cfg.get('provider_endpoints', {}).get('maia') or "https://api.maiarouter.ai/v1"
except Exception:
    MAIA_BASE_URL = "https://api.maiarouter.ai/v1"

_generation_times_maia = []

def track_maia_generation_time(duration_ms):
    _generation_times_maia.append(duration_ms)
    if len(_generation_times_maia) > 1000:
        _generation_times_maia.pop(0)
    gen_time = duration_ms
    avg_time = int(sum(_generation_times_maia) / len(_generation_times_maia)) if _generation_times_maia else 0
    longest_time = max(_generation_times_maia) if _generation_times_maia else 0
    last_time = _generation_times_maia[-1] if _generation_times_maia else 0
    return gen_time, avg_time, longest_time, last_time

def create_maia_client(api_key: str):
    return OpenAI(api_key=api_key, base_url=MAIA_BASE_URL)

def load_maia_prompt_vars():
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

def format_maia_prompt(
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
    print("MAIA ROUTER FULL PROMPT (JSON FORMAT):")
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
    text = re.sub(r'[^\w\s,]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def generate_metadata_maia(api_key, model, image_path, prompt=None, stop_flag=None, provider_endpoint=None, preextracted_frames=None, metadata_context=None, generate_prompt=False):
    if stop_flag and stop_flag.get('stop'):
        return '', '', '', {}, '', '', 0, 0, 0, ''
    start_time = time.perf_counter()
    try:
        ext = os.path.splitext(image_path)[1].lower()
        is_video = ext in ['.mp4', '.mpeg', '.mpg', '.mov', '.webm']
        filename = os.path.basename(image_path)
        
        frame_paths = []
        if is_video:
            if preextracted_frames:
                frame_paths = preextracted_frames
                print(f"[Maia] Using {len(frame_paths)} pre-extracted frames for video")
            else:
                print(f"[Maia] Video detected. Extracting frames for processing...")
                frame_paths = extract_video_frames(image_path)
                if not frame_paths:
                    error_message = (
                        "[Maia ERROR] Failed to extract frames from video. "
                        "Please ensure FFmpeg is installed and the video file is valid."
                    )
                    print(error_message)
                    return '', '', '', {}, '', error_message, 0, 0, 0, ''
                print(f"[Maia] Extracted {len(frame_paths)} frames from video")
        
        client = create_maia_client(api_key)
        
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
            ) = load_maia_prompt_vars()
            prompt = format_maia_prompt(
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
        
        content_items = [{"type": "text", "text": prompt}]
        
        if is_video and frame_paths:
            for frame_path in frame_paths:
                compressed_frame = compress_and_save_image(frame_path)
                if compressed_frame:
                    with open(compressed_frame, "rb") as f:
                        frame_bytes = f.read()
                    frame_b64 = base64.b64encode(frame_bytes).decode("utf-8")
                    frame_data_url = f"data:image/jpeg;base64,{frame_b64}"
                    content_items.append({
                        "type": "image_url",
                        "image_url": {"url": frame_data_url}
                    })
            print(f"[Maia] Sending {len(frame_paths)} video frames to API")
        else:
            compressed_path = compress_and_save_image(image_path)
            if not compressed_path:
                error_message = f"[Maia ERROR] Failed to compress image: {image_path}"
                return '', '', '', {}, '', error_message, 0, 0, 0, ''
            
            with open(compressed_path, "rb") as f:
                image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            image_data_url = f"data:image/jpeg;base64,{image_b64}"
            content_items.append({
                "type": "image_url",
                "image_url": {"url": image_data_url}
            })
        
        messages = [
            {
                "role": "user",
                "content": content_items,
            }
        ]
        
        # Support custom HTTP endpoints when provided
        used_custom_endpoint = False
        if provider_endpoint:
            from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
            try:
                endpoint_image_path = compressed_path if not is_video else None
                text, token_input, token_output, token_total = CustomEndpointHelper.call_endpoint_with_usage(api_key, provider_endpoint, 'maia', model, prompt, endpoint_image_path, timeout=180)
                used_custom_endpoint = True
            except Exception as e:
                print(f"[Maia][CustomEndpoint] {e}")
                raise
        
        if stop_flag and stop_flag.get('stop'):
            return '', '', '', {}, '', '', 0, 0, 0
        
        print(f"[Maia] Sending request: model={model}")
        
        if not used_custom_endpoint:
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
        else:
            response = None
        
        if not used_custom_endpoint:
            print("="*80)
            print("MAIA ROUTER RAW RESPONSE:")
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
        else:
            # custom endpoint path: text + usage already provided by call_endpoint_with_usage
            if 'text' not in locals():
                text = ''
            if 'token_input' not in locals():
                token_input = token_output = token_total = 0

        print("="*80)
        print("MAIA ROUTER RAW TEXT:")
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
            file_prompt = meta.get('file_prompt', '') or ''
            file_prompt = str(file_prompt).strip()
            error_message = ''
        except Exception as e:
            print(f"[Maia JSON PARSE ERROR] {e}")
            title = description = tags = ''
            category = {}
            filetype = ''
            file_prompt = ''
            error_message = f"[Maia JSON PARSE ERROR] {e}"

        if title:
            title = title_case_except(title)
            title = sanitize_text(title)
        if description:
            description = sanitize_text(description)

        return title, description, tags, category, filetype, error_message, token_input, token_output, token_total, file_prompt
    
    except Exception as e:
        err_str = str(e)
        error_message = f"[Maia ERROR] {err_str}"
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
                    code = int(m.group(1))
                elif 'rate limit' in err_str.lower() or 'quota' in err_str.lower():
                    code = 429
            m = re.search(r"['\"]status['\"]\s*[:=]\s*['\"]([^'\"]+)['\"]", err_str)
            if m:
                status = m.group(1)
        except Exception as e2:
            print(f"[Maia] Error extracting code/status from exception: {e2}")
        try:
            if code or ('quota' in err_str.lower()) or ('rate limit' in err_str.lower()):
                signature = str(code) if not status else f"{code}|{status}"
                print(f"[Maia] Emitting error dialog: code={code}, signature={signature}, service=maia, file={os.path.basename(image_path)}")
                try:
                    from dialogs.ai_helper_error_code_dialog import invoker
                    invoker.showRequested.emit(signature, err_str, os.path.basename(image_path), 'maia')
                    if signature in invoker._buffer:
                        error_code_map = invoker._buffer[signature].setdefault('error_code_map', {})
                        error_code_map[os.path.basename(image_path)] = code
                    print(f"[Maia] Error dialog emission successful")
                except Exception as e_dialog:
                    print(f"[Dialog Error] Failed to show error dialog: {e_dialog}")
                    traceback.print_exc()
        except Exception as e2:
            print(f"[Maia] Error during error-dialog notification: {e2}")
            traceback.print_exc()
        return '', '', '', {}, '', error_message, 0, 0, 0, ''
    finally:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        track_maia_generation_time(duration_ms)
