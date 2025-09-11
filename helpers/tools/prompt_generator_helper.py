import os
import json
import time
from helpers.ai_helper.ai_variation_helper import generate_timestamp, generate_token
from config import BASE_PATH
from helpers.ai_helper.gemini_helper import generate_metadata_gemini
from helpers.ai_helper.openai_helper import generate_metadata_openai
from helpers.image_compression_helper import compress_and_save_image

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
        
        return instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, prompt_types, aspect_ratios, variation_levels
    except Exception as e:
        print(f"Failed to load prompt generator config: {e}")
        return {}, {}, {}, 150, 5, 'image_generation', '16:9', 5, {}, {}, {}

def create_prompt_generation_request(instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, variation_levels, filename=None, metadata_context=None):
    """Create a prompt for AI to analyze an image and generate prompts based on type and aspect ratio"""
    batch_token = generate_token(16)
    batch_timestamp = generate_timestamp()
    
    # Get instruction based on prompt type
    if isinstance(instructions, dict):
        instruction_text = instructions.get(prompt_type, instructions.get('image_generation', ''))
    else:
        instruction_text = str(instructions)
    
    # Get variation description
    variation_description = variation_levels.get(str(variation_level), f"Level {variation_level} variation")
    
    # Build main instruction
    prompt = f"{instruction_text}\n\n"
    
    # Add requirements section based on prompt type
    if requirements:
        if isinstance(requirements, dict):
            req_list = requirements.get(prompt_type, requirements.get('image_generation', []))
        else:
            req_list = requirements
            
        if req_list:
            prompt += "REQUIREMENTS:\n"
            for req in req_list:
                formatted_req = req.format(
                    prompt_length=prompt_length, 
                    prompts_per_file=prompts_per_file,
                    aspect_ratio=aspect_ratio,
                    variation_level=variation_level,
                    variation_description=variation_description
                )
                prompt += f"- {formatted_req}\n"
            prompt += "\n"
    
    # Add batch info
    prompt += f"BATCH INFO:\n- batch_token: {batch_token}\n- batch_timestamp: {batch_timestamp}\n"
    prompt += f"- prompt_type: {prompt_type}\n- aspect_ratio: {aspect_ratio}\n- variation_level: {variation_level}/10\n\n"
    
    # Add context if provided
    if filename:
        prompt += f"CONTEXT: Image filename: {filename}\n"
    
    if metadata_context:
        prompt += f"EXISTING METADATA CONTEXT:\n{metadata_context}\n"
        prompt += "Use this metadata as additional context but focus primarily on what you see in the image.\n\n"
    
    # Add response format
    if response_format:
        structure = response_format.get('structure', {})
        validation_rules = response_format.get('validation_rules', [])
        
        prompt += "RESPONSE FORMAT (Strict JSON):\n"
        prompt += "Return ONLY valid JSON object, with NO explanation, NO markdown, NO comments, NO extra text. Output must be:\n"
        prompt += "{\n"
        prompt += f'    "prompts": [\n'
        for i in range(prompts_per_file):
            prompt += f'        "prompt {i+1} text here..."'
            if i < prompts_per_file - 1:
                prompt += ","
            prompt += "\n"
        prompt += "    ]\n}\n\n"
        
        if validation_rules:
            prompt += "VALIDATION RULES:\n"
            for i, rule in enumerate(validation_rules, 1):
                formatted_rule = rule.format(
                    prompt_length=prompt_length, 
                    prompts_per_file=prompts_per_file,
                    aspect_ratio=aspect_ratio
                )
                prompt += f"{i}. {formatted_rule}\n"
    
    return prompt

def generate_prompts_for_file(api_key, service, model, file_info, instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, variation_levels, stop_flag=None):
    """Generate prompts for a single file using AI service by analyzing the actual image"""
    if stop_flag and stop_flag.get('stop'):
        return []
    
    file_id, filepath, filename, title, description, tags, status, original_filename = file_info
    
    # Check if file exists
    if not filepath or not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return []
    
    # Check if it's an image file
    ext = os.path.splitext(filepath)[1].lower()
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg', '.eps', '.pdf'}
    if ext not in image_extensions:
        print(f"Skipping non-image file: {filepath}")
        return []
    
    # Compress image for AI processing
    try:
        compressed_path = compress_and_save_image(filepath)
        if not compressed_path:
            print(f"Failed to compress image: {filepath}")
            return []
    except Exception as e:
        print(f"Error compressing image {filepath}: {e}")
        return []
    
    # Create metadata context from existing file metadata
    metadata_parts = []
    if title and title.strip():
        metadata_parts.append(f"Title: {title.strip()}")
    if description and description.strip():
        metadata_parts.append(f"Description: {description.strip()}")
    if tags and tags.strip():
        metadata_parts.append(f"Tags: {tags.strip()}")
    
    metadata_context = "\n".join(metadata_parts) if metadata_parts else None
    
    # Create the prompt generation request
    prompt = create_prompt_generation_request(
        instructions, requirements, response_format, prompt_length, prompts_per_file, 
        prompt_type, aspect_ratio, variation_level, variation_levels, filename or original_filename, metadata_context
    )
    
    try:
        if service.lower() == 'gemini':
            prompts, token_input, token_output, token_total = generate_prompts_with_gemini(api_key, model, compressed_path, prompt, stop_flag)
        elif service.lower() == 'openai':
            prompts, token_input, token_output, token_total = generate_prompts_with_openai(api_key, model, compressed_path, prompt, stop_flag)
        else:
            print(f"Unsupported service: {service}")
            return []
        
        # Return prompts with token stats for tracking
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

def generate_prompts_with_gemini(api_key, model, image_path, prompt, stop_flag=None):
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
            
            client = genai.Client(api_key=api_key)
            
            # Load and prepare image
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
            
            # Extract token usage
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
            
            prompts = parse_ai_prompt_response(text)
            return prompts, token_input, token_output, token_total
        except Exception as e:
            error_msg = str(e)
            # Retry for connection errors
            if "10054" in error_msg or "10053" in error_msg or "connection" in error_msg.lower():
                if attempt < max_retries - 1:
                    print(f"Gemini connection error (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"Gemini connection failed after {max_retries} attempts: {e}")
            # Retry for Gemini 503 UNAVAILABLE (model overloaded)
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

def generate_prompts_with_openai(api_key, model, image_path, prompt, stop_flag=None):
    """Generate prompts using OpenAI API with actual image analysis"""
    if stop_flag and stop_flag.get('stop'):
        return [], 0, 0, 0
    
    try:
        import base64
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        
        # Load and encode image
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
        
        # Extract token usage
        token_input = 0
        token_output = 0
        token_total = 0
        usage = getattr(response, "usage", None)
        if usage:
            token_input = getattr(usage, "prompt_tokens", 0)
            token_output = getattr(usage, "completion_tokens", 0)
            token_total = getattr(usage, "total_tokens", 0)
        
        text = response.choices[0].message.content if response.choices else ""
        
        prompts = parse_ai_prompt_response(text)
        return prompts, token_input, token_output, token_total
        
    except Exception as e:
        print(f"OpenAI prompt generation error: {e}")
        return [], 0, 0, 0

def parse_ai_prompt_response(text):
    """Parse AI response to extract prompts array"""
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
            # Attempt to auto-fix truncated JSON (unterminated string/array)
            # Close array and object if missing
            fixed = text
            if '"prompts": [' in fixed:
                # If array not closed, add closing ]
                arr_start = fixed.find('"prompts": [') + len('"prompts": [')
                arr_end = fixed.find(']', arr_start)
                if arr_end == -1:
                    fixed += ']'
            if not fixed.rstrip().endswith('}'):  # If object not closed
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

def generate_prompts_for_all_files(db, api_key, service, model, instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, variation_levels, stop_flag=None, progress_callback=None, prompt_saved_callback=None, file_callback=None):
    """Generate prompts for all files in the database"""
    if stop_flag and stop_flag.get('stop'):
        return 0
    
    try:
        # Get all files from database
        files = db.get_all_files()
        if not files:
            print("No files found in database")
            return 0
        
        total_generated = 0
        
        for i, file_info in enumerate(files):
            if stop_flag and stop_flag.get('stop'):
                break
            
            file_id = file_info[0]
            filename = file_info[2] or file_info[1]  # filename or filepath
            
            # Notify UI about current file being processed
            if file_callback:
                file_callback(filename)
            
            # Calculate progress percentage
            progress_percent = (i / len(files)) * 100
            
            if progress_callback:
                progress_callback(f"Generating prompts for {filename}... ({i+1}/{len(files)})", progress_percent)
            
            # Generate prompts for this file
            prompts_data = generate_prompts_for_file(
                api_key, service, model, file_info, 
                instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, variation_levels, stop_flag
            )
            
            # Save prompts to database with token statistics
            for prompt_data in prompts_data:
                try:
                    if isinstance(prompt_data, dict):
                        # Add prompt to generated_prompts table (without token data)
                        db.add_generated_prompt(file_id, prompt_data['prompt'])
                        
                        # Trigger callback when prompt is saved
                        if prompt_saved_callback:
                            prompt_saved_callback()
                        
                        # Add token statistics to api_tokens table
                        if prompt_data.get('token_total', 0) > 0:
                            db.insert_api_token_stats(
                                filepath=file_info[1],  # filepath
                                service=prompt_data.get('service', service),
                                model=prompt_data.get('model', model),
                                token_input=prompt_data.get('token_input', 0),
                                token_output=prompt_data.get('token_output', 0),
                                token_total=prompt_data.get('token_total', 0)
                            )
                    else:
                        # Fallback for old format
                        db.add_generated_prompt(file_id, prompt_data)
                    total_generated += 1
                except Exception as e:
                    print(f"Error saving prompt to database: {e}")
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
        
        # Final progress update
        if progress_callback:
            progress_callback(f"Completed! Generated {total_generated} prompts", 100)
        
        return total_generated
        
    except Exception as e:
        print(f"Error in generate_prompts_for_all_files: {e}")
        return 0

def generate_prompts_batch(db, api_key, service, model, file_ids=None, stop_flag=None, progress_callback=None, prompt_saved_callback=None, file_callback=None):
    """Generate prompts for specific files or all files if file_ids is None"""
    if stop_flag and stop_flag.get('stop'):
        return 0
    
    # Load configuration
    instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, prompt_types, aspect_ratios, variation_levels = load_prompt_generator_config()
    
    if file_ids is None:
        # Generate for all files
        return generate_prompts_for_all_files(
            db, api_key, service, model, 
            instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, variation_levels,
            stop_flag, progress_callback, prompt_saved_callback, file_callback
        )
    else:
        # Generate for specific files
        total_generated = 0
        all_files = db.get_all_files()
        target_files = [f for f in all_files if f[0] in file_ids]
        
        for i, file_info in enumerate(target_files):
            if stop_flag and stop_flag.get('stop'):
                break
            
            file_id = file_info[0]
            filename = file_info[2] or file_info[1]
            
            # Calculate progress percentage
            progress_percent = (i / len(target_files)) * 100
            
            if progress_callback:
                progress_callback(f"Generating prompts for {filename}... ({i+1}/{len(target_files)})", progress_percent)
            
            prompts_data = generate_prompts_for_file(
                api_key, service, model, file_info,
                instructions, requirements, response_format, prompt_length, prompts_per_file, prompt_type, aspect_ratio, variation_level, variation_levels, stop_flag
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
                        # Fallback for old format
                        db.add_generated_prompt(file_id, prompt_data)
                    total_generated += 1
                except Exception as e:
                    print(f"Error saving prompt to database: {e}")
            
            time.sleep(0.1)
        
        # Final progress update for batch
        if progress_callback:
            progress_callback(f"Batch completed! Generated {total_generated} prompts", 100)
        
        return total_generated