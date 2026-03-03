import os
import json
import time
import random
from helpers.ai_helper.ai_variation_helper import generate_timestamp, generate_token
from config import BASE_PATH
from helpers.ai_helper.gemini_helper import generate_metadata_gemini
from helpers.ai_helper.openai_helper import generate_metadata_openai
from helpers.ai_helper.blackbox_ai_helper import generate_metadata_blackbox
from helpers.ai_helper.maia_helper import generate_metadata_maia, create_maia_client
from helpers.image_compression_helper import compress_and_save_image

def get_delay_interval():
    """Get delay interval from config"""
    try:
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        delay_value = config.get('delay_interval', 'Random')
        
        if delay_value == 'No Delay':
            return 0
        elif delay_value == 'Random':
            return random.uniform(1, 5)
        else:
            try:
                return float(delay_value)
            except ValueError:
                return random.uniform(1, 5)
    except Exception as e:
        print(f"Error loading delay interval: {e}")
        return random.uniform(1, 5)

def load_prompt_generator_config():
    """Load prompt generator configuration from ai_config.json"""
    config_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pg_config = data.get('prompt_generator', {})
        instructions = pg_config.get('instructions', {})
        requirements = pg_config.get('requirements', {})
        response_format = pg_config.get('response_format', {})
        settings = pg_config.get('settings', {})
        prompt_types = pg_config.get('prompt_types', {})
        aspect_ratios = pg_config.get('aspect_ratios', {})
        variation_levels = pg_config.get('variation_levels', {})
        
        prompt_length = settings.get('prompt_length', 150)
        prompts_per_file = settings.get('prompts_per_file', 5)
        prompt_type = settings.get('prompt_type', 'image_generation')
        aspect_ratio = settings.get('aspect_ratio', '16:9')
        variation_level = settings.get('variation_level', 5)
        custom_instruction = settings.get('custom_instruction', '')
        
        return instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, prompt_types, aspect_ratios, variation_levels
    except Exception as e:
        print(f"Failed to load prompt generator config: {e}")
        return {}, {}, {}, 150, 5, 'image_generation', '16:9', 5, '', {}, {}, {}

def create_prompt_generation_request(instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction='', variation_levels=None, filename=None, metadata_context=None):
    """Create a prompt for AI to analyze an image and generate prompts based on type and aspect ratio"""
    batch_token = generate_token(16)
    batch_timestamp = generate_timestamp()
    
    if isinstance(instructions, dict):
        instruction_text = instructions.get(prompt_type, instructions.get('image_generation', ''))
    else:
        instruction_text = str(instructions)
    
    variation_description = variation_levels.get(str(variation_level), f"Level {variation_level} variation")
    
    req_list_formatted = []
    if requirements:
        if isinstance(requirements, dict):
            req_list = requirements.get(prompt_type, requirements.get('image_generation', []))
        else:
            req_list = requirements
            
        if req_list:
            for req in req_list:
                formatted_req = req.format(
                    prompt_length=prompt_length, 
                    prompts_per_file=prompts_per_file,
                    aspect_ratio=aspect_ratio,
                    variation_level=variation_level,
                    variation_description=variation_description
                )
                req_list_formatted.append(formatted_req)
    
    validation_list_formatted = []
    if response_format:
        validation_rules = response_format.get('validation_rules', [])
        if validation_rules:
            for rule in validation_rules:
                formatted_rule = rule.format(
                    prompt_length=prompt_length, 
                    prompts_per_file=prompts_per_file,
                    aspect_ratio=aspect_ratio
                )
                validation_list_formatted.append(formatted_rule)
    
    prompt_json = {
        "instruction": instruction_text,
        "batch_info": {
            "batch_token": batch_token,
            "batch_timestamp": batch_timestamp,
            "prompt_type": prompt_type,
            "aspect_ratio": aspect_ratio,
            "variation_level": f"{variation_level}/10",
            "variation_description": variation_description
        },
        "requirements": req_list_formatted,
        "response_format": {
            "type": "JSON",
            "structure": {
                "prompts": [f"prompt {i+1} text here..." for i in range(prompts_per_file)]
            },
            "validation_rules": validation_list_formatted,
            "note": "Return ONLY valid JSON object, with NO explanation, NO markdown, NO comments, NO extra text"
        }
    }
    # attach custom instruction if provided
    if custom_instruction and custom_instruction.strip():
        prompt_json["additional_instruction"] = custom_instruction.strip()
    
    if filename:
        prompt_json["context"] = {"filename": filename}
    
    if metadata_context:
        if "context" not in prompt_json:
            prompt_json["context"] = {}
        prompt_json["context"]["existing_metadata"] = metadata_context
        prompt_json["context"]["note"] = "Use this metadata as additional context but focus primarily on what you see in the image"
    
    full_prompt = json.dumps(prompt_json, indent=2, ensure_ascii=False)
    
    return full_prompt

def generate_prompts_for_file(api_key, service, model, file_info, instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, variation_levels, stop_flag=None, provider_endpoint=None):
    """Generate prompts for a single file using AI service by analyzing the actual image"""
    if stop_flag and stop_flag.get('stop'):
        return []
    
    file_id, filepath, filename, title, description, tags, status, original_filename = file_info
    
    if not filepath or not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return []
    
    try:
        compressed_path = compress_and_save_image(filepath)
        if not compressed_path:
            print(f"Failed to compress image: {filepath}")
            return []
    except Exception as e:
        print(f"Error compressing image {filepath}: {e}")
        return []
    
    metadata_parts = []
    if title and title.strip():
        metadata_parts.append(f"Title: {title.strip()}")
    if description and description.strip():
        metadata_parts.append(f"Description: {description.strip()}")
    if tags and tags.strip():
        metadata_parts.append(f"Tags: {tags.strip()}")
    
    metadata_context = "\n".join(metadata_parts) if metadata_parts else None
    
    prompt = create_prompt_generation_request(
        instructions, requirements, response_format, prompt_length, prompts_per_file, 
        prompt_type, aspect_ratio, variation_level, custom_instruction, variation_levels, filename or original_filename, metadata_context
    )

    try:
        if service.lower() == 'gemini':
            prompts, token_input, token_output, token_total = generate_prompts_with_gemini(api_key, model, compressed_path, prompt, aspect_ratio, stop_flag, provider_endpoint=provider_endpoint)
        elif service.lower() in ('openai', 'openrouter'):
            prompts, token_input, token_output, token_total = generate_prompts_with_openai(api_key, model, compressed_path, prompt, aspect_ratio, stop_flag, provider_endpoint=provider_endpoint)
        elif service.lower() == 'groq':
            prompts, token_input, token_output, token_total = generate_prompts_with_groq(api_key, model, compressed_path, prompt, aspect_ratio, stop_flag, provider_endpoint=provider_endpoint)
        elif service.lower() == 'blackbox':
            prompts, token_input, token_output, token_total = generate_prompts_with_blackbox(api_key, model, compressed_path, prompt, aspect_ratio, stop_flag, provider_endpoint=provider_endpoint)
        elif service.lower() == 'maia':
            prompts, token_input, token_output, token_total = generate_prompts_with_maia(api_key, model, compressed_path, prompt, aspect_ratio, stop_flag, provider_endpoint=provider_endpoint)
        elif service.lower() == 'custom':
            prompts, token_input, token_output, token_total = generate_prompts_with_custom(api_key, model, compressed_path, prompt, aspect_ratio, stop_flag, provider_endpoint=provider_endpoint)
        else:
            print(f"Unsupported service: {service}")
            return []
        
        result = []
        for prompt_text in prompts:
            result.append({
                'prompt': prompt_text,
                'token_input': token_input,
                'token_output': token_output, 
                'token_total': token_total,
                'service': service,
                'model': model
            })
        
        return result
    except Exception as e:
        print(f"Error generating prompts for file {filename}: {e}")
        return []

def generate_prompts_with_gemini(api_key, model, image_path, prompt, aspect_ratio=None, stop_flag=None, provider_endpoint=None):
    """Generate prompts using Gemini API with actual image analysis"""
    if stop_flag and stop_flag.get('stop'):
        return [], 0, 0, 0
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            import google.genai as genai
            from google.genai import types
            import time
            
            if provider_endpoint:
                try:
                    from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                    text = CustomEndpointHelper.call_endpoint(api_key, provider_endpoint, 'gemini', model, prompt, image_path=image_path, timeout=180)
                    prompts = parse_ai_prompt_response(text, aspect_ratio)
                    return prompts, 0, 0, 0
                except Exception as e:
                    print(f"Gemini custom endpoint error: {e}")
                    return [], 0, 0, 0

            client = genai.Client(api_key=api_key)
            
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            contents = [types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), prompt]
            
            if stop_flag and stop_flag.get('stop'):
                return [], 0, 0, 0
            
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=5000,
                )
            )
            
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
                    text = str(response)
            elif hasattr(response, "text"):
                text = response.text
            else:
                text = str(response)
            
            prompts = parse_ai_prompt_response(text, aspect_ratio)
            return prompts, token_input, token_output, token_total
        except Exception as e:
            error_msg = str(e)
            if "10054" in error_msg or "10053" in error_msg or "connection" in error_msg.lower():
                if attempt < max_retries - 1:
                    print(f"Gemini connection error (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    print(f"Gemini connection failed after {max_retries} attempts: {e}")
            elif ("503" in error_msg and "UNAVAILABLE" in error_msg) or ("model is overloaded" in error_msg.lower()):
                if attempt < max_retries - 1:
                    print(f"Gemini model overloaded (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"Gemini model overloaded after {max_retries} attempts: {e}")
            else:
                print(f"Gemini prompt generation error: {e}")
            if attempt == max_retries - 1:
                return [], 0, 0, 0

def generate_prompts_with_openai(api_key, model, image_path, prompt, aspect_ratio=None, stop_flag=None, provider_endpoint=None):
    """Generate prompts using OpenAI API with actual image analysis"""
    if stop_flag and stop_flag.get('stop'):
        return [], 0, 0, 0
    
    try:
        import base64
        from helpers.ai_helper.openai_helper import create_openai_client

        if provider_endpoint:
            try:
                from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                text = CustomEndpointHelper.call_endpoint(api_key, provider_endpoint, 'openai', model, prompt, image_path=image_path, timeout=180)
                prompts = parse_ai_prompt_response(text, aspect_ratio)
                return prompts, 0, 0, 0
            except Exception as e:
                print(f"Custom OpenAI endpoint error: {e}")
                return [], 0, 0, 0

        client = create_openai_client(api_key)
        
        with open(image_path, "rb") as f:
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
            return [], 0, 0, 0
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.8
        )
        
        token_input = 0
        token_output = 0
        token_total = 0
        usage = getattr(response, "usage", None)
        if usage:
            token_input = getattr(usage, "prompt_tokens", 0)
            token_output = getattr(usage, "completion_tokens", 0)
            token_total = getattr(usage, "total_tokens", 0)
        
        text = response.choices[0].message.content if response.choices else ""
        
        prompts = parse_ai_prompt_response(text, aspect_ratio)
        return prompts, token_input, token_output, token_total
        
    except Exception as e:
        print(f"OpenAI prompt generation error: {e}")
        return [], 0, 0, 0


def generate_prompts_with_groq(api_key, model, image_path, prompt, aspect_ratio=None, stop_flag=None, provider_endpoint=None):
    """Generate prompts using Groq API with image analysis"""
    if stop_flag and stop_flag.get('stop'):
        return [], 0, 0, 0
    try:
        import base64
        from groq import Groq

        if provider_endpoint:
            try:
                from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                text = CustomEndpointHelper.call_endpoint(api_key, provider_endpoint, 'groq', model, prompt, image_path=image_path, timeout=180)
                prompts = parse_ai_prompt_response(text, aspect_ratio)
                return prompts, 0, 0, 0
            except Exception as e:
                print(f"Groq custom endpoint error: {e}")
                return [], 0, 0, 0

        client = Groq(api_key=api_key)

        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
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
            return [], 0, 0, 0

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.8
        )

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

        prompts = parse_ai_prompt_response(text, aspect_ratio)
        return prompts, token_input, token_output, token_total
    except Exception as e:
        print(f"Groq prompt generation error: {e}")
        return [], 0, 0, 0

def generate_prompts_with_blackbox(api_key, model, image_path, prompt, aspect_ratio=None, stop_flag=None, provider_endpoint=None):
    """Generate prompts using Blackbox API with image analysis"""
    if stop_flag and stop_flag.get('stop'):
        return [], 0, 0, 0
    try:
        import base64
        from openai import OpenAI

        if provider_endpoint:
            try:
                from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                text = CustomEndpointHelper.call_endpoint(api_key, provider_endpoint, 'blackbox', model, prompt, image_path=image_path, timeout=180)
                prompts = parse_ai_prompt_response(text, aspect_ratio)
                return prompts, 0, 0, 0
            except Exception as e:
                print(f"Blackbox custom endpoint error: {e}")
                return [], 0, 0, 0

        client = OpenAI(api_key=api_key, base_url="https://api.blackbox.ai")

        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
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
            return [], 0, 0, 0

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.8
        )


        token_input = 0
        token_output = 0
        token_total = 0
        usage = getattr(response, "usage", None)
        if usage:
            token_input = getattr(usage, "prompt_tokens", 0)
            token_output = getattr(usage, "completion_tokens", 0)
            token_total = getattr(usage, "total_tokens", 0)

        text = None
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                text = choice.message.content
        if not text:
            text = str(response)

        prompts = parse_ai_prompt_response(text, aspect_ratio)
        return prompts, token_input, token_output, token_total
    except Exception as e:
        print(f"Blackbox prompt generation error: {e}")
        return [], 0, 0, 0

def generate_prompts_with_maia(api_key, model, image_path, prompt, aspect_ratio=None, stop_flag=None, provider_endpoint=None):
    """Generate prompts using MAIA Router API with image analysis"""
    if stop_flag and stop_flag.get('stop'):
        return [], 0, 0, 0
    try:
        import base64

        if provider_endpoint:
            try:
                from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                text = CustomEndpointHelper.call_endpoint(api_key, provider_endpoint, 'maia', model, prompt, image_path=image_path, timeout=180)
                prompts = parse_ai_prompt_response(text, aspect_ratio)
                return prompts, 0, 0, 0
            except Exception as e:
                print(f"MAIA custom endpoint error: {e}")
                return [], 0, 0, 0

        client = create_maia_client(api_key)

        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
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
            return [], 0, 0, 0

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.8
        )

        token_input = 0
        token_output = 0
        token_total = 0
        usage = getattr(response, "usage", None)
        if usage:
            token_input = getattr(usage, "prompt_tokens", 0)
            token_output = getattr(usage, "completion_tokens", 0)
            token_total = getattr(usage, "total_tokens", 0)

        text = None
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                text = choice.message.content
        if not text:
            text = str(response)

        prompts = parse_ai_prompt_response(text, aspect_ratio)
        return prompts, token_input, token_output, token_total
    except Exception as e:
        print(f"Maia prompt generation error: {e}")
        return [], 0, 0, 0

def generate_prompts_with_custom(api_key, model, image_path, prompt, aspect_ratio=None, stop_flag=None, provider_endpoint=None):
    """Generate prompts using custom endpoint with image analysis"""
    if stop_flag and stop_flag.get('stop'):
        return [], 0, 0, 0
    
    if not provider_endpoint:
        print("Custom endpoint error: No endpoint URL provided")
        return [], 0, 0, 0
    
    try:
        from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
        
        full_prompt = prompt
        if aspect_ratio:
            full_prompt = f"{prompt}. Generate prompts optimized for {aspect_ratio} aspect ratio."
        
        try:
            response_text = CustomEndpointHelper.call_endpoint(
                api_key,
                provider_endpoint,
                "custom",
                model or "",
                full_prompt,
                image_path,
                timeout=30
            )
        except Exception as e:
            print(f"Custom endpoint call error: {e}")
            return [], 0, 0, 0
        
        prompts = parse_ai_prompt_response(response_text, aspect_ratio)
        
        token_estimate = len(response_text) // 4 if response_text else 0
        
        return prompts, token_estimate, token_estimate, token_estimate * 2
    except Exception as e:
        print(f"Custom prompt generation error: {e}")
        return [], 0, 0, 0

def parse_ai_prompt_response(text, aspect_ratio=None):
    """Parse AI response to extract prompts array and optionally add aspect ratio"""
    import re
    import json
    text = str(text).strip()
    if not text or not (text.startswith('{') or text.startswith('```')):
        return []
    try:
        if text.startswith('```'):
            text = re.sub(r'^```[a-zA-Z]*', '', text)
            if text.endswith('```'):
                text = text[:text.rfind('```')].strip()
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            text = text[start:end+1]
        text = re.sub(r'[\x00-\x1F\x7F]+', '', text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            fixed = text
            if '"prompts": [' in fixed:
                arr_start = fixed.find('"prompts": [') + len('"prompts": [')
                arr_end = fixed.find(']', arr_start)
                if arr_end == -1:
                    fixed += ']'
            if not fixed.rstrip().endswith('}'):
                fixed += '}'
            try:
                data = json.loads(fixed)
            except Exception as e2:
                print(f"Error parsing AI prompt response (fixed): {e2}")
                print(f"Raw response (fixed): {fixed}")
                return []
        prompts = data.get('prompts', [])
        cleaned_prompts = []
        for prompt in prompts:
            if isinstance(prompt, str) and prompt.strip():
                sanitized = re.sub(r'[\x00-\x1F\x7F]+', '', prompt.strip())                
                cleaned_prompts.append(sanitized)
        return cleaned_prompts
    except Exception as e:
        print(f"Error parsing AI prompt response: {e}")
        print(f"Raw response: {text}")
        return []

def generate_prompts_for_all_files(db, api_key, service, model, instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, variation_levels, stop_flag=None, progress_callback=None, prompt_saved_callback=None, file_callback=None, provider_endpoint=None):
    """Generate prompts for all files in the database"""
    if stop_flag and stop_flag.get('stop'):
        return 0

    try:
        files = db.get_all_files()
        if not files:
            print("No files found in database")
            return 0

        total_generated = 0

        for i, file_info in enumerate(files):
            if stop_flag and stop_flag.get('stop'):
                break

            file_id = file_info[0]
            filename = file_info[2] or file_info[1]

            if file_callback:
                file_callback(filename)

            progress_percent = (i / len(files)) * 100

            if progress_callback:
                progress_callback(f"Generating prompts for {filename}... ({i+1}/{len(files)})", progress_percent)

            prompts_data = generate_prompts_for_file(
                api_key, service, model, file_info, 
                instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, variation_levels, stop_flag, provider_endpoint=provider_endpoint
            )

            for prompt_data in prompts_data:
                try:
                    if isinstance(prompt_data, dict):
                        db.add_generated_prompt(file_id, prompt_data['prompt'])

                        if prompt_saved_callback:
                            prompt_saved_callback()

                        if prompt_data.get('token_total', 0) > 0:
                            db.insert_api_token_stats(
                                filepath=file_info[1],
                                service=prompt_data.get('service', service),
                                model=prompt_data.get('model', model),
                                token_input=prompt_data.get('token_input', 0),
                                token_output=prompt_data.get('token_output', 0),
                                token_total=prompt_data.get('token_total', 0)
                            )
                    else:
                        db.add_generated_prompt(file_id, prompt_data)
                    total_generated += 1
                except Exception as e:
                    print(f"Error saving prompt to database: {e}")

            if i < len(files) - 1:
                delay_seconds = get_delay_interval()
                if progress_callback:
                    progress_callback(f"Waiting {delay_seconds:.1f} seconds delay...", progress_percent)
                time.sleep(delay_seconds)

        if progress_callback:
            progress_callback(f"Completed! Generated {total_generated} prompts", 100)

        return total_generated

    except Exception as e:
        print(f"Error in generate_prompts_for_all_files: {e}")
        return 0

def generate_prompts_from_folder(db, api_key, service, model, folder_files, stop_flag=None, progress_callback=None, prompt_saved_callback=None, file_callback=None, provider_endpoint=None):
    """Generate prompts for a list of image file paths from a local folder (not from DB)"""
    if stop_flag and stop_flag.get('stop'):
        return 0

    instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, prompt_types, aspect_ratios, variation_levels = load_prompt_generator_config()

    total_generated = 0
    total = len(folder_files)

    for i, filepath in enumerate(folder_files):
        if stop_flag and stop_flag.get('stop'):
            break

        filename = os.path.basename(filepath)
        if file_callback:
            file_callback(filename)

        progress_percent = (i / total) * 100 if total > 0 else 0
        if progress_callback:
            progress_callback(f"Generating prompts for {filename}... ({i+1}/{total})", progress_percent)

        file_info = (None, filepath, filename, '', '', '', 'active', filename)

        prompts_data = generate_prompts_for_file(
            api_key, service, model, file_info,
            instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, variation_levels, stop_flag, provider_endpoint=provider_endpoint
        )

        for prompt_data in prompts_data:
            try:
                if isinstance(prompt_data, dict):
                    db.add_generated_prompt(None, prompt_data['prompt'])
                    if prompt_saved_callback:
                        prompt_saved_callback()
                else:
                    db.add_generated_prompt(None, prompt_data)
                total_generated += 1
            except Exception as e:
                print(f"Error saving prompt from folder file {filename}: {e}")

        if i < total - 1:
            delay_seconds = get_delay_interval()
            if progress_callback:
                progress_callback(f"Waiting {delay_seconds:.1f}s before next file...", progress_percent)
            time.sleep(delay_seconds)

    if progress_callback:
        progress_callback(f"Folder generation completed! Generated {total_generated} prompts", 100)

    return total_generated


def generate_prompts_batch(db, api_key, service, model, file_ids=None, stop_flag=None, progress_callback=None, prompt_saved_callback=None, file_callback=None, provider_endpoint=None):
    """Generate prompts for specific files or all files if file_ids is None"""
    if stop_flag and stop_flag.get('stop'):
        return 0
    
    instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, prompt_types, aspect_ratios, variation_levels = load_prompt_generator_config()
    
    if file_ids is None:
        return generate_prompts_for_all_files(
            db, api_key, service, model, 
            instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, variation_levels,
            stop_flag, progress_callback, prompt_saved_callback, file_callback, provider_endpoint=provider_endpoint
        )
    else:
        total_generated = 0
        all_files = db.get_all_files()
        target_files = [f for f in all_files if f[0] in file_ids]
        
        for i, file_info in enumerate(target_files):
            if stop_flag and stop_flag.get('stop'):
                break
            
            file_id = file_info[0]
            filename = file_info[2] or file_info[1]
            
            progress_percent = (i / len(target_files)) * 100
            
            if progress_callback:
                progress_callback(f"Generating prompts for {filename}... ({i+1}/{len(target_files)})", progress_percent)
            
            prompts_data = generate_prompts_for_file(
                api_key, service, model, file_info,
                instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, custom_instruction, variation_levels, stop_flag, provider_endpoint=provider_endpoint
            )
            for prompt_data in prompts_data:
                try:
                    if isinstance(prompt_data, dict):
                        db.add_generated_prompt(
                            file_id, 
                            prompt_data['prompt'],
                            prompt_data.get('token_input', 0),
                            prompt_data.get('token_output', 0),
                            prompt_data.get('token_total', 0),
                            prompt_data.get('service'),
                            prompt_data.get('model')
                        )
                    else:
                        db.add_generated_prompt(file_id, prompt_data)
                    total_generated += 1
                except Exception as e:
                    print(f"Error saving prompt to database: {e}")
            
            time.sleep(0.1)
        
        if progress_callback:
            progress_callback(f"Batch completed! Generated {total_generated} prompts", 100)
        
        return total_generated


def load_prompt_generator_parameters_config():
    """Load prompt_generator_parameters section from ai_config.json"""
    config_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        params_cfg = data.get('prompt_generator_parameters', {})
        pg_cfg = data.get('prompt_generator', {})

        settings = params_cfg.get('settings', {})
        themes_list = params_cfg.get('themes', [])
        moods_list = params_cfg.get('moods', [])
        colors_list = params_cfg.get('colors', [])
        human_model_options = params_cfg.get('human_model_options', [])
        instructions = params_cfg.get('instructions', pg_cfg.get('instructions', {}))
        variation_levels = pg_cfg.get('variation_levels', {})
        aspect_ratios = pg_cfg.get('aspect_ratios', {})

        prompt_type = settings.get('prompt_type', 'image_generation')
        aspect_ratio = settings.get('aspect_ratio', '16:9')
        prompt_length = settings.get('prompt_length', 150)
        prompts_per_batch = min(settings.get('prompts_per_batch', 5), 20)
        num_requests = max(settings.get('num_requests', 1), 1)
        variation_level = settings.get('variation_level', 5)
        human_model = settings.get('human_model', 'No people')
        custom_instruction = settings.get('custom_instruction', '')
        theme = settings.get('theme', '')
        if theme == '\u2014 None \u2014':
            theme = ''
        mood = settings.get('mood', '')
        if mood == '\u2014 None \u2014':
            mood = ''
        color = settings.get('color', '')
        if color == '\u2014 None \u2014':
            color = ''
        language = settings.get('language', 'English (Default)')
        art_style = settings.get('art_style', '')
        if art_style == '\u2014 None \u2014':
            art_style = ''
        background = settings.get('background', '')
        if background == '\u2014 None \u2014':
            background = ''

        return (
            prompt_type, aspect_ratio, prompt_length, prompts_per_batch,
            variation_level, human_model, custom_instruction,
            theme, mood, color,
            instructions, variation_levels, num_requests,
            language, art_style, background
        )
    except Exception as e:
        print(f"Failed to load prompt_generator_parameters config: {e}")
        return (
            'image_generation', '16:9', 150, 5, 5,
            'No people', '', '', '', '', {}, {}, 1,
            'English (Default)', '', ''
        )


def create_parameters_prompt_request(prompt_type, aspect_ratio, prompt_length, prompts_per_batch,
                                     variation_level, human_model, custom_instruction,
                                     theme, mood, color,
                                     instructions, variation_levels,
                                     language=None, art_style=None, background=None):
    """Build a text-only prompt for parameters-based generation (no reference image)"""
    from helpers.ai_helper.ai_variation_helper import generate_timestamp, generate_token

    batch_token = generate_token(16)
    batch_timestamp = generate_timestamp()

    if isinstance(instructions, dict):
        instruction_text = instructions.get(prompt_type, instructions.get('image_generation', ''))
    else:
        instruction_text = str(instructions)

    variation_description = variation_levels.get(str(variation_level), f"Level {variation_level} variation")

    parameters = {
        "prompt_type": prompt_type,
        "aspect_ratio": aspect_ratio,
        "prompt_length_chars": prompt_length,
        "variation_level": f"{variation_level}/10 — {variation_description}",
        "human_model": human_model,
    }
    if language and language not in ('English (Default)', ''):
        parameters["output_language"] = language
    if theme and theme.strip():
        parameters["theme"] = theme.strip()
    if mood and mood.strip():
        parameters["mood"] = mood.strip()
    if color and color.strip():
        parameters["color_palette"] = color.strip()
    if art_style and art_style.strip():
        parameters["art_style"] = art_style.strip()
    if background and background.strip():
        parameters["background"] = background.strip()
    if custom_instruction and custom_instruction.strip():
        parameters["additional_instruction"] = custom_instruction.strip()

    prompt_json = {
        "instruction": instruction_text,
        "batch_info": {
            "batch_token": batch_token,
            "batch_timestamp": batch_timestamp,
        },
        "parameters": parameters,
        "requirements": [
            f"Generate exactly {prompts_per_batch} unique, creative prompts (max {prompts_per_batch})",
            f"Each prompt must be approximately {prompt_length} characters long",
            f"Include aspect ratio {aspect_ratio} in each prompt",
            f"Apply variation level {variation_level}/10: {variation_description}",
            "All prompts must be distinct from each other",
            "Base prompts on the provided parameters only (no reference image)",
            f"Human model setting: {human_model}",
        ],
        "response_format": {
            "type": "JSON",
            "structure": {
                "prompts": [f"prompt {i+1} text here..." for i in range(prompts_per_batch)]
            },
            "validation_rules": [
                f"Return exactly {prompts_per_batch} prompts in the array",
                "Use double quotes for all strings",
                "Response must be valid JSON",
                "NO explanation, markdown, or extra text outside the JSON",
            ]
        }
    }

    return json.dumps(prompt_json, indent=2, ensure_ascii=False)


def generate_prompts_text_only(api_key, service, model, prompt_text, aspect_ratio=None, stop_flag=None, provider_endpoint=None):
    """Call AI service with text-only prompt (no image). Returns (prompts_list, token_in, token_out, token_total)."""
    if stop_flag and stop_flag.get('stop'):
        return [], 0, 0, 0

    try:
        if service.lower() == 'gemini':
            import google.genai as genai
            from google.genai import types

            if provider_endpoint:
                try:
                    from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                    text = CustomEndpointHelper.call_endpoint(api_key, provider_endpoint, 'gemini', model, prompt_text, image_path=None, timeout=120)
                    return parse_ai_prompt_response(text, aspect_ratio), 0, 0, 0
                except Exception as e:
                    print(f"Gemini custom endpoint text-only error: {e}")
                    return [], 0, 0, 0

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=[prompt_text],
                config=types.GenerateContentConfig(temperature=0.9, max_output_tokens=5000)
            )
            token_input = token_output = token_total = 0
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
                    text = str(response)
            elif hasattr(response, "text"):
                text = response.text
            else:
                text = str(response)
            return parse_ai_prompt_response(text, aspect_ratio), token_input, token_output, token_total

        elif service.lower() in ('openai', 'openrouter', 'blackbox', 'maia', 'custom'):
            if service.lower() == 'openai' or service.lower() == 'openrouter':
                from helpers.ai_helper.openai_helper import create_openai_client
                client = create_openai_client(api_key)
            elif service.lower() == 'blackbox':
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url="https://api.blackbox.ai")
            elif service.lower() == 'maia':
                from helpers.ai_helper.maia_helper import create_maia_client
                client = create_maia_client(api_key)
            else:
                if not provider_endpoint:
                    print("Custom text-only: no endpoint provided")
                    return [], 0, 0, 0
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=provider_endpoint)

            if provider_endpoint and service.lower() not in ('openai', 'openrouter'):
                try:
                    from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                    text = CustomEndpointHelper.call_endpoint(api_key, provider_endpoint, service, model, prompt_text, image_path=None, timeout=120)
                    return parse_ai_prompt_response(text, aspect_ratio), 0, 0, 0
                except Exception as e:
                    print(f"{service} custom endpoint text-only error: {e}")
                    return [], 0, 0, 0

            messages = [{"role": "user", "content": prompt_text}]
            if stop_flag and stop_flag.get('stop'):
                return [], 0, 0, 0
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=3000,
                temperature=0.9
            )
            token_input = token_output = token_total = 0
            usage = getattr(response, "usage", None)
            if usage:
                token_input = getattr(usage, "prompt_tokens", 0)
                token_output = getattr(usage, "completion_tokens", 0)
                token_total = getattr(usage, "total_tokens", 0)
            text = None
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    text = choice.message.content
            if not text:
                text = str(response)
            return parse_ai_prompt_response(text, aspect_ratio), token_input, token_output, token_total

        elif service.lower() == 'groq':
            from groq import Groq
            client = Groq(api_key=api_key)
            messages = [{"role": "user", "content": prompt_text}]
            if stop_flag and stop_flag.get('stop'):
                return [], 0, 0, 0
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=3000,
                temperature=0.9
            )
            token_input = token_output = token_total = 0
            usage = getattr(response, "usage", None)
            if usage:
                token_input = getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0)
                token_output = getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0)
                token_total = getattr(usage, "total_tokens", 0)
            text = None
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message"):
                    text = choice.message.content
            if not text:
                text = str(response)
            return parse_ai_prompt_response(text, aspect_ratio), token_input, token_output, token_total

        else:
            print(f"Unsupported service for text-only generation: {service}")
            return [], 0, 0, 0

    except Exception as e:
        print(f"Text-only prompt generation error ({service}): {e}")
        return [], 0, 0, 0


def generate_prompts_batch_by_parameters(db, api_key, service, model, stop_flag=None,
                                         progress_callback=None, prompt_saved_callback=None,
                                         provider_endpoint=None):
    """Generate prompts using parameters (no reference image) and save to database."""
    if stop_flag and stop_flag.get('stop'):
        return 0

    (
        prompt_type, aspect_ratio, prompt_length, prompts_per_batch,
        variation_level, human_model, custom_instruction,
        selected_themes, selected_moods, selected_colors,
        instructions, variation_levels, num_requests,
        language, art_style, background
    ) = load_prompt_generator_parameters_config()

    if progress_callback:
        progress_callback("Building parameters prompt...", 5)

    prompt_text = create_parameters_prompt_request(
        prompt_type, aspect_ratio, prompt_length, prompts_per_batch,
        variation_level, human_model, custom_instruction,
        selected_themes, selected_moods, selected_colors,
        instructions, variation_levels,
        language=language, art_style=art_style, background=background
    )

    if stop_flag and stop_flag.get('stop'):
        return 0

    total_saved = 0
    total_token_input = 0
    total_token_output = 0
    total_token_total = 0

    for req_idx in range(num_requests):
        if stop_flag and stop_flag.get('stop'):
            break
        pct_start = 10 + int((req_idx / num_requests) * 80)
        if progress_callback:
            progress_callback(f"Request {req_idx + 1}/{num_requests} — calling {service} ({model})...", pct_start)

        prompts, token_input, token_output, token_total = generate_prompts_text_only(
            api_key, service, model, prompt_text, aspect_ratio, stop_flag, provider_endpoint
        )

        if not prompts:
            if progress_callback:
                progress_callback(f"Request {req_idx + 1}/{num_requests} — no prompts returned.", pct_start)
            print(f"generate_prompts_batch_by_parameters: request {req_idx + 1} returned no prompts")
            continue

        total_token_input += token_input
        total_token_output += token_output
        total_token_total += token_total

        if progress_callback:
            progress_callback(f"Request {req_idx + 1}/{num_requests} — saving {len(prompts)} prompts...", pct_start + 5)

        for prompt_item in prompts:
            if stop_flag and stop_flag.get('stop'):
                break
            try:
                db.add_generated_prompt(None, prompt_item)
                total_saved += 1
                if prompt_saved_callback:
                    prompt_saved_callback()
            except Exception as e:
                print(f"Error saving parameter-generated prompt: {e}")

    if total_token_total > 0:
        try:
            db.insert_api_token_stats(
                filepath='parameters',
                service=service,
                model=model,
                token_input=total_token_input,
                token_output=total_token_output,
                token_total=total_token_total
            )
        except Exception as e:
            print(f"Error saving token stats: {e}")

    if progress_callback:
        progress_callback(f"Done — {total_saved} prompt(s) generated by parameters.", 100)

    return total_saved