import os
import requests
import shutil
import time
import json
import threading
from pathlib import Path
from config import BASE_PATH

# Model storage directory inside project
MODEL_DIR = os.path.join(BASE_PATH, 'tools', 'rembg', 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

# Default model name
DEFAULT_MODEL = "isnet-general-use"

# Built-in model list
MODELS = {
    DEFAULT_MODEL: "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
    "u2net": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
    "u2netp": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx",
    "u2net_human_seg": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx",
    "u2net_cloth_seg": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_cloth_seg.onnx",
}

MODEL_FILENAMES = {
    DEFAULT_MODEL: "isnet-general-use.onnx",
    "u2net": "u2net.onnx",
    "u2netp": "u2netp.onnx",
    "u2net_human_seg": "u2net_human_seg.onnx",
    "u2net_cloth_seg": "u2net_cloth_seg.onnx",
}

current_downloads = {}
download_lock = threading.Lock()

GITHUB_RELEASE_API_URL = "https://api.github.com/repos/danielgatis/rembg/releases/tags/v0.0.0"
_fetched_once = False
CACHE_PATH = os.path.join(MODEL_DIR, "models_cache.json")


def _save_models_cache():
    try:
        payload = {'models': MODELS, 'filenames': MODEL_FILENAMES}
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _load_models_cache():
    try:
        if not os.path.exists(CACHE_PATH):
            return {}
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        models = payload.get('models', {}) or {}
        filenames = payload.get('filenames', {}) or {}
        if models:
            MODELS.update(models)
        if filenames:
            MODEL_FILENAMES.update(filenames)
        return models
    except Exception:
        return {}


def fetch_models_from_github(force=False):
    """Fetch ONNX asset list from the rembg GitHub release and return mapping name->url."""
    global _fetched_once
    if _fetched_once and not force:
        return {}

    try:
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Image-Tea'
        }
        resp = requests.get(GITHUB_RELEASE_API_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        assets = data.get('assets', [])
        found = {}
        for asset in assets:
            name = asset.get('name', '')
            url = asset.get('browser_download_url')
            if name.lower().endswith('.onnx') and url:
                key = os.path.splitext(name)[0]
                found[key] = url
                MODEL_FILENAMES[key] = name

        if found:
            MODELS.update(found)
            _fetched_once = True
            _save_models_cache()
    except Exception:
        cached = _load_models_cache()
        if cached:
            _fetched_once = True
            return cached

    return {}


def get_available_models():
    """Return a sorted list of available model names."""
    fetch_models_from_github()
    if len(MODELS) <= 1:
        _load_models_cache()
    return sorted(MODELS.keys(), key=lambda s: s.lower())


def get_model_path(model_name):
    """Return the full path to a model file if it exists, or None."""
    filename = MODEL_FILENAMES.get(model_name, f"{model_name}.onnx")
    model_path = os.path.join(MODEL_DIR, filename)
    if os.path.exists(model_path):
        return model_path
    return None


def download_model(model_name, callback=None):
    """Download a model file with progress callback(model_name, progress 0..100)."""
    if model_name not in MODELS:
        return False

    model_path = os.path.join(MODEL_DIR, MODEL_FILENAMES.get(model_name, f"{model_name}.onnx"))

    if os.path.exists(model_path):
        if callback:
            try:
                callback(model_name, 100.0)
            except Exception:
                pass
        return True

    with download_lock:
        if model_name in current_downloads:
            return False
        current_downloads[model_name] = True

    url = MODELS[model_name]
    temp_path = model_path + ".download"

    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0
            last_emit_time = 0.0
            last_progress = 0.0

            with open(temp_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if callback and total_size:
                            progress = (downloaded / total_size) * 100
                            now = time.monotonic()
                            if (progress - last_progress) >= 0.5 or (now - last_emit_time) >= 0.15 or progress >= 99.9:
                                try:
                                    callback(model_name, progress)
                                except Exception:
                                    pass
                                last_emit_time = now
                                last_progress = progress

        shutil.move(temp_path, model_path)
        if callback:
            try:
                callback(model_name, 100.0)
            except Exception:
                pass

        with download_lock:
            if model_name in current_downloads:
                del current_downloads[model_name]
        return True

    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        with download_lock:
            if model_name in current_downloads:
                del current_downloads[model_name]
        return False


def prepare_model(model_name, callback=None):
    """Ensure a model is downloaded and ready. Returns True if ready."""
    model_name = model_name or DEFAULT_MODEL
    if model_name not in MODELS:
        fetch_models_from_github()
    if model_name not in MODELS:
        return False
    model_path = get_model_path(model_name)
    if model_path:
        print(f"Model {model_name} already available at {model_path}")
        return True
    print(f"Model {model_name} not found in {MODEL_DIR}; downloading once")
    return download_model(model_name, callback)


def set_model_path():
    """Set U2NET_HOME env var to model directory."""
    os.environ["U2NET_HOME"] = MODEL_DIR
    os.makedirs(MODEL_DIR, exist_ok=True)
    return MODEL_DIR


# Set model path on import
set_model_path()
