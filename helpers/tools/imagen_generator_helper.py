"""
Imagen Generator Helper

This module will contain helper functions for generating images using AI services.
Currently a placeholder for future implementation.
"""

import os
import json
from config import BASE_PATH


def load_imagen_config():
    """Load imagen generator configuration from ai_config.json"""
    try:
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("imagen_generator", {})
        return {}
    except Exception as e:
        print(f"Error loading imagen config: {e}")
        return {}


def save_imagen_config(config_data):
    """Save imagen generator configuration to ai_config.json"""
    try:
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        
        # Load existing config
        full_config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                full_config = json.load(f)
        
        # Update imagen_generator section
        full_config["imagen_generator"] = config_data
        
        # Save back to file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(full_config, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Error saving imagen config: {e}")


def generate_images_from_prompts(prompts, api_key, service, model, **kwargs):
    """
    Generate images from prompts using specified AI service.
    
    Args:
        prompts (list): List of text prompts to generate images from
        api_key (str): API key for the AI service
        service (str): AI service name (e.g., 'openai', 'google')
        model (str): Model name to use for generation
        **kwargs: Additional parameters like number_of_images, aspect_ratio, image_size, output_mime_type, etc.
    
    Returns:
        list: List of generated image results
    """
    
    print(f"Debug: Starting image generation with service={service}, model={model}")
    print(f"Debug: Number of prompts to process: {len(prompts)}")
    
    # Get callback functions for real-time status updates
    status_callback = kwargs.get('status_callback', None)
    progress_callback = kwargs.get('progress_callback', None)
    
    if service.lower() != 'google' and service.lower() != 'gemini':
        error_msg = f'Only Google/Gemini service is supported for image generation. Got: {service}'
        print(f"Debug: Service error: {error_msg}")
        return [{'status': 'error', 'error': error_msg}]
    
    try:
        print(f"Debug: Importing Google GenAI library...")
        from google import genai
        import os
        
        print(f"Debug: Creating GenAI client...")
        # Create the client directly - NO configure() method
        client = genai.Client(api_key=api_key)
        
        results = []
        
        for idx, prompt in enumerate(prompts, 1):
            print(f"Debug: Processing prompt {idx}/{len(prompts)}: {prompt[:100]}...")
            
            # Get prompt info for status callback
            prompt_info = prompt if isinstance(prompt, dict) else {'prompt': prompt}
            
            # Update status to processing
            if status_callback:
                status_callback(prompt_info, 'processing')
            
            try:
                # Prepare generation config using proper parameter names
                config_params = {
                    'number_of_images': kwargs.get('number_of_images', 4),
                }
                
                # Add aspect ratio if provided
                if 'aspect_ratio' in kwargs:
                    config_params['aspect_ratio'] = kwargs['aspect_ratio']
                
                # Add image size if provided (using proper parameter name)
                if 'image_size' in kwargs:
                    config_params['image_size'] = kwargs['image_size']
                
                # Add output format if provided
                if 'output_mime_type' in kwargs:
                    config_params['output_mime_type'] = kwargs['output_mime_type']
                
                print(f"Debug: Config params: {config_params}")
                
                print(f"Debug: Calling Gemini API to generate images...")
                # Generate images using the working method from imagen.py
                response = client.models.generate_images(
                    model=model,
                    prompt=prompt_info.get('prompt', prompt),
                    config=config_params
                )
                
                print(f"Debug: Got response from Gemini, processing images...")
                
                # Save generated images
                output_folder = kwargs.get('output_folder', '')
                if not output_folder or not os.path.exists(output_folder):
                    # Use default temp folder
                    output_folder = os.path.join(BASE_PATH, 'temp', 'images')
                    os.makedirs(output_folder, exist_ok=True)
                
                print(f"Debug: Saving images to: {output_folder}")
                
                saved_images = []
                images_generated = 0
                
                # Determine file extension from output_mime_type
                output_format = kwargs.get('output_mime_type', 'image/png')
                file_extension = '.png' if output_format == 'image/png' else '.jpg'
                
                for i, generated_image in enumerate(response.generated_images, 1):
                    try:
                        # Create filename based on prompt and index
                        safe_prompt = "".join(c for c in prompt_info.get('prompt', prompt) if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_prompt = safe_prompt[:50]  # Limit length
                        filename = f"{safe_prompt}_{i:03d}{file_extension}"
                        filepath = os.path.join(output_folder, filename)
                        
                        print(f"Debug: Saving image {i} as: {filename}")
                        
                        # Save the image
                        generated_image.image.save(filepath)
                        saved_images.append(filepath)
                        images_generated += 1
                        
                    except Exception as e:
                        print(f"Debug: Error saving image {i}: {e}")
                        continue
                
                print(f"Debug: Successfully generated {images_generated} images for this prompt")
                
                # Update status to success
                if status_callback:
                    status_callback(prompt_info, 'success', images_generated)
                
                results.append({
                    'prompt': prompt_info.get('prompt', prompt),
                    'prompt_info': prompt_info,
                    'status': 'success',
                    'images_generated': images_generated,
                    'saved_images': saved_images,
                    'error': None
                })
                
            except Exception as e:
                error_msg = str(e)
                print(f"Debug: Error generating images for prompt {idx}: {error_msg}")
                
                # Update status to failed
                if status_callback:
                    status_callback(prompt_info, 'failed', 0, error_msg)
                
                results.append({
                    'prompt': prompt_info.get('prompt', prompt),
                    'prompt_info': prompt_info,
                    'status': 'error',
                    'images_generated': 0,
                    'saved_images': [],
                    'error': error_msg
                })
                
        print(f"Debug: Completed all prompts. Total results: {len(results)}")
        return results
        
    except ImportError as e:
        error_msg = f'Google Generative AI library not installed. Install with: pip install google-generativeai. Error: {e}'
        print(f"Debug: Import error: {error_msg}")
        return [{'status': 'error', 'error': error_msg}]
    except Exception as e:
        error_msg = f'Generation failed: {str(e)}'
        print(f"Debug: General error: {error_msg}")
        return [{'status': 'error', 'error': error_msg}]


def validate_image_generation_params(prompts, api_key, service, model):
    """
    Validate parameters for image generation.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not prompts or len(prompts) == 0:
        return False, "No prompts provided"
    
    if not api_key or not api_key.strip():
        return False, "API key is required"
    
    if not service or not service.strip():
        return False, "AI service must be selected"
    
    if not model or not model.strip():
        return False, "Model must be selected"
    
    return True, None


def get_supported_image_services():
    """
    Get list of supported AI services for image generation.
    
    Returns:
        dict: Dictionary of service names and their capabilities
    """
    return {
        'openai': {
            'name': 'OpenAI DALL-E',
            'models': ['dall-e-3', 'dall-e-2'],
            'supported': True
        },
        'google': {
            'name': 'Google Imagen',
            'models': ['imagen-3.0', 'imagen-2.0'],
            'supported': False  # Placeholder - will be implemented later
        },
        'stability': {
            'name': 'Stability AI',
            'models': ['stable-diffusion-3', 'stable-diffusion-xl'],
            'supported': False  # Placeholder - will be implemented later
        }
    }


def get_default_image_settings():
    """
    Get default settings for image generation.
    
    Returns:
        dict: Default settings
    """
    return {
        'size': '1024x1024',
        'quality': 'standard',
        'style': 'natural',
        'output_format': 'png',
        'save_location': os.path.join(BASE_PATH, 'temp', 'images')
    }