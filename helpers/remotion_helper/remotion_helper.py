import os
import sys
import subprocess
import platform
import shutil
import json
import re
from typing import Optional, Tuple, List

from config import BASE_PATH

TOOLS_NODEJS = os.path.join(BASE_PATH, "tools", "nodejs")
TOOLS_REMOTION = os.path.join(BASE_PATH, "tools", "remotion")
PROJECT_TEMP_DIR = os.path.join(BASE_PATH, "temp")

REMOTION_TEMP_DIR_NAME = "remotion_temp"
REMOTION_PREVIEW_DIR_NAME = "remotion_preview"
REMOTION_SRC_DIR = "src"
REMOTION_ENTRY_FILE = "index.ts"
COMPOSITION_ID = "main"

# Global state untuk persistent preview
_preview_dir_initialized = False
_preview_dir_path = None
_preview_server_port = None


def _find_node() -> Optional[str]:
    for root, dirs, files in os.walk(TOOLS_NODEJS):
        for name in ["node.exe", "node"]:
            if name in files:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    return path
    return shutil.which("node")


def _find_npm_cmd() -> Optional[List[str]]:
    if platform.system() == "Windows":
        for root, dirs, files in os.walk(TOOLS_NODEJS):
            if "npm.cmd" in files:
                return [os.path.join(root, "npm.cmd")]
    for root, dirs, files in os.walk(TOOLS_NODEJS):
        if "npm" in files:
            return [os.path.join(root, "npm")]
    system_npm = shutil.which("npm")
    if system_npm:
        return [system_npm]
    return None


def _find_remotion_executable() -> Tuple[Optional[str], Optional[str]]:
    """
    Find remotion executable.
    Returns: (entry_point, exec_type) where:
    - entry_point: path to the executable
    - exec_type: 'cmd', 'js', 'shell', or None
    """
    # Look for CLI entry point (remotion-cli.js) - the actual Node.js entry point
    cli_js = os.path.join(TOOLS_REMOTION, "node_modules", "@remotion", "cli", "remotion-cli.js")
    if os.path.exists(cli_js):
        return cli_js, "js"
    
    # Fallback to shell wrappers
    bin_dir = os.path.join(TOOLS_REMOTION, "node_modules", ".bin")
    if not os.path.exists(bin_dir):
        return None, None
    
    system = platform.system()
    if system == "Windows":
        # Check for .cmd first
        cmd_exe = os.path.join(bin_dir, "remotion.cmd")
        if os.path.exists(cmd_exe):
            return cmd_exe, "cmd"
        # Then .ps1
        ps1_exe = os.path.join(bin_dir, "remotion.ps1")
        if os.path.exists(ps1_exe):
            return ps1_exe, "ps1"
    else:
        exe = os.path.join(bin_dir, "remotion")
        if os.path.exists(exe):
            return exe, "shell"
    return None, None


def _script_has_register_root(script_content: str) -> bool:
    has_import = ('from \'remotion\'' in script_content or 'from "remotion"' in script_content or
                  'from \'@remotion/root\'' in script_content or 'from "@remotion/root"' in script_content)
    has_call = 'registerRoot(' in script_content
    return has_import and has_call


def _script_has_composition(script_content: str) -> bool:
    return '<Composition' in script_content


def _normalize_default_export(script_content: str) -> Tuple[str, Optional[str]]:
    name = None

    pattern_func = r'export\s+default\s+function\s*\('
    if re.search(pattern_func, script_content):
        script_content = re.sub(pattern_func, 'const MyComponent = function(', script_content, count=1)
        return script_content, 'MyComponent'

    pattern_class = r'export\s+default\s+class\s*\{'
    if re.search(pattern_class, script_content):
        script_content = re.sub(pattern_class, 'class MyComponent {', script_content, count=1)
        return script_content, 'MyComponent'

    pattern_arrow = r'export\s+default\s*\(([^)]*)\)\s*=>'
    match = re.search(pattern_arrow, script_content)
    if match:
        params = match.group(1)
        script_content = re.sub(pattern_arrow, f'const MyComponent = ({params}) =>', script_content, count=1)
        return script_content, 'MyComponent'

    pattern_arrow_no_paren = r'export\s+default\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=>'
    match = re.search(pattern_arrow_no_paren, script_content)
    if match:
        param = match.group(1)
        script_content = re.sub(pattern_arrow_no_paren, f'const MyComponent = {param} =>', script_content, count=1)
        return script_content, 'MyComponent'

    pattern_id = r'export\s+default\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*;'
    match = re.search(pattern_id, script_content)
    if match:
        name = match.group(1)
    return script_content, name


def _detect_component_name(script_content: str) -> Optional[str]:
    export_patterns = [
        r'^\s*export\s+default\s+function\s+([A-Z][A-Za-z0-9_]*)\b',
        r'^\s*export\s+const\s+([A-Z][A-Za-z0-9_]*)\b',
        r'^\s*export\s+function\s+([A-Z][A-Za-z0-9_]*)\b',
        r'^\s*export\s+class\s+([A-Z][A-Za-z0-9_]*)\b',
    ]
    for pattern in export_patterns:
        match = re.search(pattern, script_content, re.MULTILINE)
        if match:
            return match.group(1)

    patterns = [
        r'^\s*const\s+([A-Z][A-Za-z0-9_]*)\s*:\s*React\.FC\b',
        r'^\s*const\s+([A-Z][A-Za-z0-9_]*)\s*=\s*\(',
        r'^\s*function\s+([A-Z][A-Za-z0-9_]*)\s*\(',
        r'^\s*class\s+([A-Z][A-Za-z0-9_]*)\s*\{',
    ]
    for pattern in patterns:
        match = re.search(pattern, script_content, re.MULTILINE)
        if match:
            return match.group(1)
    return None


def _extract_component_from_composition(script: str) -> Optional[str]:
    """Extract the component name from the first <Composition ... component={...}> tag."""
    pattern = r'<Composition\b[^>]*component\s*=\s*\{([^}]+)\}[^>]*\/?>'
    match = re.search(pattern, script, re.DOTALL | re.IGNORECASE)
    if match:
        comp_expr = match.group(1).strip()
        identifier_match = re.search(r'([A-Za-z_$][A-Za-z0-9_$]*)', comp_expr)
        if identifier_match:
            return identifier_match.group(1)
        return comp_expr
    return None


def _component_defined(script: str, name: str) -> bool:
    """Check whether a component with the given name is defined in the script."""
    pattern = r'(?:const|let|var|function|class)\s+' + re.escape(name) + r'\b'
    return bool(re.search(pattern, script))


def _strip_composition_tags(script: str) -> str:
    """Strip all <Composition ...> JSX tags from the script."""
    # Replace self-closing tags with an empty fragment to keep valid JSX
    script = re.sub(r'<Composition\b[^>]*\/>', '<></>', script, flags=re.DOTALL)
    # Replace tags with explicit closing with an empty fragment
    script = re.sub(r'<Composition\b[^>]*>.*?<\/Composition>', '<></>', script, flags=re.DOTALL)
    # Normalize multiple newlines
    script = re.sub(r'\n\s*\n\s*\n+', '\n\n', script)
    return script.strip() + '\n'


def sanitize_script_content(content: str) -> str:
    """
    Clean up arbitrary user script content to produce valid TypeScript/JavaScript code.
    - Strips BOM
    - Normalizes line endings
    - Removes markdown code fences
    - Strips trailing whitespace
    - Ensures trailing newline
    """
    # Remove BOM
    if content.startswith('\ufeff'):
        content = content[1:]

    # Normalize line endings to \n
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Strip trailing whitespace on each line
    content = '\n'.join(line.rstrip() for line in content.splitlines())

    # Remove markdown code fences (```tsx, ```typescript, ```js, ```javascript, ```)
    # Pattern: optional language identifier, then code, then closing fence
    fence_pattern = r'^```(?:\w+)?\s*\n(.*?)(?:\n```|$)?'
    matches = list(re.finditer(fence_pattern, content, re.DOTALL | re.MULTILINE))
    if matches:
        # Extract the first code block only; discard surrounding text
        first = matches[0]
        code = first.group(1) if first.group(1) else ''
        # Remove any remaining fence markers inside code
        code = re.sub(r'^```.*$', '', code, flags=re.MULTILINE)
        content = code.strip()

    # Ensure single trailing newline
    content = content.rstrip('\n') + '\n'

    return content


def _load_active_preset_settings() -> dict:
    """Load width/height/fps/video_bitrate from the currently active preset or custom preset."""
    config_path = os.path.join(BASE_PATH, "configs", "remotion_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        active_key = config.get("active_preset", "1080p30")
        if active_key == "custom":
            preset = config.get("custom_preset", {})
        else:
            preset = config.get("presets", {}).get(active_key, {})
        if preset:
            return {
                "width": preset.get("width", 1920),
                "height": preset.get("height", 1080),
                "fps": preset.get("fps", 30),
                "video_bitrate": preset.get("video_bitrate", "10M"),
                "duration": 10,
            }
    return {"width": 1920, "height": 1080, "fps": 30, "video_bitrate": "10M", "duration": 10}


def _write_root_tsx(preview_dir: str, component_name: str, render_settings: dict):
    """Write Root.tsx that wraps the user component in a Composition."""
    src_dir = os.path.join(preview_dir, REMOTION_SRC_DIR)
    fps = render_settings.get('fps', 30)
    duration = render_settings.get('duration', 10)
    duration_frames = int(fps * duration) if duration > 0 else int(fps * 10)
    width = render_settings.get('width')
    height = render_settings.get('height')
    if width is None or height is None:
        raise ValueError("render_settings must contain 'width' and 'height'")
    # Output dimensions
    base_width = width
    base_height = height
    scale = 1.0
    offset_x = 0.0
    offset_y = 0.0

    content = f'''import {{ Composition }} from 'remotion';
import {{ {component_name} as UserComponent }} from './MyComponent';

const ScaledRoot = () => (
    <div style={{{{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}}}>
        <div
            style={{{{
                width: {base_width},
                height: {base_height},
                position: 'absolute',
                left: {offset_x},
                top: {offset_y},
                transform: 'scale({scale})',
                transformOrigin: 'top left',
            }}}}
        >
            <UserComponent />
        </div>
    </div>
);

export const Root = () => (
    <Composition
        id="{COMPOSITION_ID}"
        component={{ScaledRoot}}
        durationInFrames={{{duration_frames}}}
        fps={{{fps}}}
        width={{{width}}}
        height={{{height}}}
    />
);
'''
    path = os.path.join(src_dir, "Root.tsx")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _ensure_main_composition(script: str) -> str:
    """Ensure there is a Composition with id="main" by modifying the first Composition tag."""
    # Already has a main composition? Skip.
    if re.search(r'<Composition\b[^>]*\bid\s*=\s*["\']main["\']', script):
        return script

    def replacer(match):
        tag = match.group(0)
        # Detect if self-closing (<Composition .../>)
        is_self_closing = tag.rstrip().endswith('/>')
        suffix = '/>' if is_self_closing else '>'
        # Remove the closing '>' or '/>' to get prefix
        prefix = tag[:-len(suffix)]

        # Pattern to detect any existing id attribute (quoted, braced, or unquoted)
        id_pattern = r'''\bid\s*=\s*("[^"]*"|'[^']*'|\{[^}]*\}|[^\s>]+)'''

        if re.search(id_pattern, prefix):
            # Replace existing id (any format) with id="main"
            new_prefix = re.sub(id_pattern, 'id="main"', prefix, count=1)
        else:
            # Append id="main" before closing
            new_prefix = prefix + ' id="main"'
        return new_prefix + suffix

    # Replace only the first <Composition ...> occurrence
    return re.sub(r'<Composition\b[^>]*>', replacer, script, count=1)


def _extract_component_from_composition(script: str) -> Optional[str]:
    """Extract the component name from the first <Composition ... component={...}> tag."""
    pattern = r'<Composition\b[^>]*component\s*=\s*\{([^}]+)\}[^>]*\/?>'
    match = re.search(pattern, script, re.DOTALL | re.IGNORECASE)
    if match:
        comp_expr = match.group(1).strip()
        identifier_match = re.search(r'([A-Za-z_$][A-Za-z0-9_$]*)', comp_expr)
        if identifier_match:
            return identifier_match.group(1)
        return comp_expr
    return None


def _component_defined(script: str, name: str) -> bool:
    """Check whether a component with the given name is defined in the script."""
    pattern = r'(?:const|let|var|function|class)\s+' + re.escape(name) + r'\b'
    return bool(re.search(pattern, script))


def _strip_composition_tags(script: str) -> str:
    """Strip all <Composition ...> JSX tags from the script."""
    # Replace self-closing tags with an empty fragment to keep valid JSX
    script = re.sub(r'<Composition\b[^>]*\/>', '<></>', script, flags=re.DOTALL)
    # Replace tags with explicit closing with an empty fragment
    script = re.sub(r'<Composition\b[^>]*>.*?<\/Composition>', '<></>', script, flags=re.DOTALL)
    # Normalize multiple newlines
    script = re.sub(r'\n\s*\n\s*\n+', '\n\n', script)
    return script.strip() + '\n'


def _prepare_user_script(script_content: str) -> Tuple[str, str]:
    modified = script_content

    # Remove any existing registerRoot calls to avoid duplicate registration
    modified = re.sub(r'\bregisterRoot\s*\([^)]*\)\s*;?', '', modified)

    modified, forced_name = _normalize_default_export(modified)

    # Ensure React import
    if 'import React' not in modified and 'from \'react\'' not in modified and 'from "react"' not in modified:
        modified = "import React from 'react';\n" + modified

    # Try to infer the intended component from <Composition> if present (AI-generated full scripts)
    extracted_component = None
    if '<Composition' in modified:
        extracted_component = _extract_component_from_composition(modified)
        if extracted_component and _component_defined(modified, extracted_component):
            component_name = extracted_component
        else:
            component_name = forced_name or _detect_component_name(modified)
    else:
        component_name = forced_name or _detect_component_name(modified)

    # Fallback: if we still don't have a component name, create a minimal placeholder
    if not component_name:
        component_name = "MyComponent"
        modified += f"\n\nconst {component_name} = () => {{ return <div>Empty</div>; }};\n"

    # Strip all <Composition> tags – our wrapper will provide the Composition
    modified = _strip_composition_tags(modified)

    # Ensure the component is exported as a named export.
    # Detect existing named exports (covers const/let/var/function/class and brace-export).
    export_patterns = [
        r'export\s+(?:const|let|var|function|class)\s+' + re.escape(component_name) + r'\b',
        r'export\s+{[^}]*\b' + re.escape(component_name) + r'\b[^}]*}',
    ]
    has_named_export = any(re.search(p, modified) for p in export_patterns)
    if not has_named_export:
        # Append a named export for the component.
        modified = modified.rstrip() + f"\nexport {{ {component_name} }};\n"

    # Defensive: if any Composition tag survived, ensure it has id="main"
    if '<Composition' in modified:
        modified = _ensure_main_composition(modified)

    return modified, component_name


def _write_index_ts(preview_dir: str, import_source: str, import_name: str):
    """Write the JSX-free entry file that registers the root component.

    Args:
        preview_dir: preview directory path
        import_source: module path without extension (e.g., 'Root' or 'MyComponent')
        import_name: exported component name to register
    """
    src_dir = os.path.join(preview_dir, REMOTION_SRC_DIR)
    content = (
        f"import {{ registerRoot }} from 'remotion';\n"
        f"import {{ {import_name} }} from './{import_source}';\n\n"
        f"registerRoot({import_name});\n"
    )
    path = os.path.join(src_dir, REMOTION_ENTRY_FILE)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _write_root_tsx(preview_dir: str, component_name: str, render_settings: dict):
    """Write Root.tsx that wraps the user component in a Composition."""
    src_dir = os.path.join(preview_dir, REMOTION_SRC_DIR)
    fps = render_settings.get('fps', 30)
    duration = render_settings.get('duration', 10)
    duration_frames = int(fps * duration) if duration > 0 else int(fps * 10)
    width = render_settings.get('width')
    height = render_settings.get('height')
    if width is None or height is None:
        raise ValueError("render_settings must contain 'width' and 'height'")
    # Output dimensions - inner container matches exactly, no scaling
    base_width = width
    base_height = height
    scale = 1.0
    offset_x = 0.0
    offset_y = 0.0

    content = f'''import {{ Composition }} from 'remotion';
import {{ {component_name} as UserComponent }} from './MyComponent';

const ScaledRoot = () => (
    <div style={{{{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}}}>
        <div
            style={{{{
                width: {base_width},
                height: {base_height},
                position: 'absolute',
                left: {offset_x},
                top: {offset_y},
                transform: 'scale({scale})',
                transformOrigin: 'top left',
            }}}}
        >
            <UserComponent />
        </div>
    </div>
);

export const Root = () => (
    <Composition
        id="{COMPOSITION_ID}"
        component={{ScaledRoot}}
        durationInFrames={{{duration_frames}}}
        fps={{{fps}}}
        width={{{width}}}
        height={{{height}}}
    />
);
'''
    path = os.path.join(src_dir, "Root.tsx")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _setup_temp_dir(script_content: str, render_settings: dict) -> Tuple[str, str]:
    if not os.path.exists(PROJECT_TEMP_DIR):
        os.makedirs(PROJECT_TEMP_DIR, exist_ok=True)

    temp_dir = os.path.join(PROJECT_TEMP_DIR, REMOTION_TEMP_DIR_NAME)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

    os.makedirs(temp_dir, exist_ok=True)
    src_dir = os.path.join(temp_dir, REMOTION_SRC_DIR)
    os.makedirs(src_dir, exist_ok=True)

    # Sanitize and prepare user component
    script_content = sanitize_script_content(script_content)
    prepared_script, component_name = _prepare_user_script(script_content)

    # Write MyComponent.tsx always
    component_file = os.path.join(src_dir, "MyComponent.tsx")
    with open(component_file, 'w', encoding='utf-8') as f:
        f.write(prepared_script)

    entry_file = os.path.join(src_dir, REMOTION_ENTRY_FILE)

    # Wrap user component in Root.tsx so registerRoot always points to a Composition tree
    _write_root_tsx(temp_dir, component_name, render_settings)
    _write_index_ts(temp_dir, 'Root', 'Root')

    for pkg_file in ["package.json", "package-lock.json"]:
        src = os.path.join(TOOLS_REMOTION, pkg_file)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(temp_dir, pkg_file))

    tsconfig_content = {
        "compilerOptions": {
            "target": "es2018",
            "module": "commonjs",
            "jsx": "react-jsx",
            "strict": True,
            "moduleResolution": "node",
            "esModuleInterop": True,
            "skipLibCheck": True,
            "forceConsistentCasingInFileNames": True,
            "resolveJsonModule": True,
            "isolatedModules": True,
            "noEmit": True
        },
        "include": ["src"]
    }
    with open(os.path.join(temp_dir, "tsconfig.json"), 'w', encoding='utf-8') as f:
        json.dump(tsconfig_content, f, indent=2)

    # Copy node_modules from tools/remotion (fast reuse)
    src_node_modules = os.path.join(TOOLS_REMOTION, "node_modules")
    dst_node_modules = os.path.join(temp_dir, "node_modules")
    if os.path.exists(src_node_modules):
        try:
            if os.path.exists(dst_node_modules):
                print(f"[Remotion] Removing stale node_modules at {dst_node_modules}")
                shutil.rmtree(dst_node_modules, ignore_errors=True)
            shutil.copytree(src_node_modules, dst_node_modules, symlinks=False, ignore=shutil.ignore_patterns('.git', '.DS_Store'))
            print("[Remotion] Copied node_modules from tools/remotion")
        except Exception as e:
            print(f"[Remotion] Warning: Failed to copy node_modules: {e}")

    return temp_dir, entry_file


def setup_preview_dir(script_content: str, render_settings: dict = None) -> Tuple[str, str]:
    """Setup preview directory - persistent, reused across script changes."""
    global _preview_dir_initialized, _preview_dir_path

    # Sanitize script content first
    script_content = sanitize_script_content(script_content)

    if render_settings is None:
        render_settings = _load_active_preset_settings()

    preview_dir = os.path.join(PROJECT_TEMP_DIR, REMOTION_PREVIEW_DIR_NAME)
    src_dir = os.path.join(preview_dir, REMOTION_SRC_DIR)
    entry_file = os.path.join(src_dir, REMOTION_ENTRY_FILE)

    # If already initialized, just update script content (and Root.tsx if needed)
    if _preview_dir_initialized and _preview_dir_path == preview_dir:
        if os.path.exists(preview_dir):
            _update_preview_script(script_content, render_settings)
            return preview_dir, entry_file

    # First time setup - create fresh directory structure
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir, ignore_errors=True)

    orig_name = REMOTION_TEMP_DIR_NAME
    import helpers.remotion_helper.remotion_helper as _self_mod
    _self_mod.REMOTION_TEMP_DIR_NAME = REMOTION_PREVIEW_DIR_NAME
    try:
        result = _setup_temp_dir(script_content, render_settings)
    finally:
        _self_mod.REMOTION_TEMP_DIR_NAME = orig_name

    _preview_dir_initialized = True
    _preview_dir_path = preview_dir
    return result


def _update_preview_script(script_content: str, render_settings: dict = None) -> str:
    """Update script content without recreating directory."""
    global _preview_dir_path

    if not _preview_dir_path:
        raise RuntimeError("Preview directory not initialized")

    src_dir = os.path.join(_preview_dir_path, REMOTION_SRC_DIR)
    entry_file = os.path.join(src_dir, REMOTION_ENTRY_FILE)

    # Sanitize script content first
    script_content = sanitize_script_content(script_content)

    # Prepare user component
    prepared_script, component_name = _prepare_user_script(script_content)
    component_file = os.path.join(src_dir, "MyComponent.tsx")
    with open(component_file, 'w', encoding='utf-8') as f:
        f.write(prepared_script)

    # Use provided render_settings or load from active preset
    if render_settings is None:
        render_settings = _load_active_preset_settings()

    # Wrap user component in Root.tsx so registerRoot always points to a Composition tree
    _write_root_tsx(_preview_dir_path, component_name, render_settings)
    _write_index_ts(_preview_dir_path, 'Root', 'Root')

    print(f'[Remotion] Script updated at {entry_file}')
    return entry_file


def cleanup_preview_dir(force=False):
    """Cleanup preview directory - hanya dipanggil saat tab ditutup."""
    global _preview_dir_initialized, _preview_dir_path, _preview_server_port

    if not force:
        print('[Remotion] Skipping cleanup - server persistent mode')
        return

    preview_dir = os.path.join(PROJECT_TEMP_DIR, REMOTION_PREVIEW_DIR_NAME)
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir, ignore_errors=True)
        print('[Remotion] Preview dir cleaned up')

    _preview_dir_initialized = False
    _preview_dir_path = None
    _preview_server_port = None


def get_preview_dir() -> Optional[str]:
    """Get current preview directory path."""
    global _preview_dir_path
    return _preview_dir_path


def set_preview_server_port(port: int):
    """Set preview server port."""
    global _preview_server_port
    _preview_server_port = port


def get_preview_server_port() -> Optional[int]:
    """Get preview server port."""
    global _preview_server_port
    return _preview_server_port


def _detect_composition_id(script_content: str) -> str:
    match = re.search(r'id\s*=\s*["\']([^"\']+)["\']', script_content)
    if match:
        return match.group(1)
    return COMPOSITION_ID


def _build_render_args(
    entry_file: str,
    composition_id: str,
    output_path: str,
    render_settings: dict
) -> List[str]:
    args = ["render", entry_file, composition_id, "--output", output_path]

    scale = render_settings.get('scale', 0)
    if scale and scale != 1:
        args.extend(['--scale', str(scale)])

    # FPS
    if render_settings.get('fps', 0) > 0:
        args.extend(['--fps', str(int(render_settings['fps']))])

    # Duration: convert seconds -> frames using fps
    duration_seconds = render_settings.get('duration', 0)
    fps = render_settings.get('fps', 0)
    if duration_seconds > 0 and fps > 0:
        duration_frames = int(duration_seconds * fps)
        args.extend(['--duration', str(duration_frames)])

    # Codec & pixel format
    if render_settings.get('codec') and render_settings['codec'] != 'h264':
        args.extend(['--codec', render_settings['codec']])
    pixel_format = render_settings.get('pixel_format', 'yuv420p')
    if pixel_format and pixel_format != 'yuv420p':
        args.extend(['--pixel-format', pixel_format])

    # Image format
    if render_settings.get('image_format') and render_settings['image_format'] != 'jpeg':
        args.extend(['--image-format', render_settings['image_format']])

    # Sequence / frames range
    if render_settings.get('sequence', False):
        args.append('--sequence')
    if render_settings.get('frames'):
        args.extend(['--frames', str(render_settings['frames'])])
    if render_settings.get('every_nth_frame', 1) > 1:
        args.extend(['--every-nth-frame', str(render_settings['every_nth_frame'])])

    # Audio
    if render_settings.get('audio_codec') and render_settings['audio_codec'] != 'aac':
        args.extend(['--audio-codec', render_settings['audio_codec']])
    if render_settings.get('audio_bitrate'):
        args.extend(['--audio-bitrate', str(render_settings['audio_bitrate'])])
    if render_settings.get('muted'):
        args.append('--muted')
    if render_settings.get('enforce_audio_track'):
        args.append('--enforce-audio-track')
    if render_settings.get('separate_audio_to'):
        args.extend(['--separate-audio-to', render_settings['separate_audio_to']])
    if render_settings.get('for_seamless_aac_concatenation'):
        args.append('--for-seamless-aac-concatenation')

    # Sample rate (Hz)
    sample_rate = render_settings.get('sample_rate')
    if sample_rate:
        try:
            args.extend(['--sample-rate', str(int(sample_rate))])
        except (ValueError, TypeError):
            pass  # ignore invalid

    if render_settings.get('crf', 0) > 0:
        args.extend(['--crf', str(int(render_settings['crf']))])
    if render_settings.get('video_bitrate'):
        args.extend(['--video-bitrate', str(render_settings['video_bitrate'])])
    if render_settings.get('buffer_size'):
        args.extend(['--buffer-size', str(render_settings['buffer_size'])])
    if render_settings.get('max_rate'):
        args.extend(['--max-rate', str(render_settings['max_rate'])])
    if render_settings.get('jpeg_quality', 80) != 80:
        args.extend(['--jpeg-quality', str(render_settings['jpeg_quality'])])
    if render_settings.get('prores_profile') and render_settings['prores_profile'] != 'auto':
        args.extend(['--prores-profile', render_settings['prores_profile']])
    if render_settings.get('x264_preset') and render_settings['x264_preset'] != 'medium':
        args.extend(['--x264-preset', render_settings['x264_preset']])
    if render_settings.get('gif_loops', 0) > 0:
        args.extend(['--number-of-gif-loops', str(render_settings['gif_loops'])])

    # Performance
    if render_settings.get('concurrency', 1) > 0:
        args.extend(['--concurrency', str(render_settings['concurrency'])])
    if render_settings.get('hardware_acceleration') and render_settings['hardware_acceleration'] not in ('disabled', 'none'):
        args.extend(['--hardware-acceleration', render_settings['hardware_acceleration']])
    if render_settings.get('disallow_parallel_encoding'):
        args.append('--disallow-parallel-encoding')

    # Browser / advanced
    if render_settings.get('browser_executable'):
        args.extend(['--browser-executable', render_settings['browser_executable']])
    chrome_mode = render_settings.get('chrome_mode')
    if chrome_mode:
        if chrome_mode not in ('headless-shell', 'chrome-for-testing'):
            print(f"[Remotion] Warning: Unknown chrome_mode '{chrome_mode}', ignoring.")
        else:
            args.extend(['--chrome-mode', chrome_mode])
    if render_settings.get('timeout', 30000) != 30000:
        args.extend(['--timeout', str(render_settings['timeout'])])
    if render_settings.get('ignore_certificate_errors'):
        args.append('--ignore-certificate-errors')
    if render_settings.get('disable_web_security'):
        args.append('--disable-web-security')
    if render_settings.get('disable_headless'):
        args.append('--disable-headless')
    if render_settings.get('dark_mode'):
        args.append('--dark-mode')
    if render_settings.get('user_agent'):
        args.extend(['--user-agent', render_settings['user_agent']])
    gl = render_settings.get('gl')
    if gl and gl not in ('default', ''):
        args.extend(['--gl', gl])
    # if gl is '' or 'default' or None: omit flag (use Remotion default)
    if render_settings.get('config_file'):
        args.extend(['--config', render_settings['config_file']])
    if render_settings.get('env_file'):
        args.extend(['--env-file', render_settings['env_file']])
    if render_settings.get('props'):
        args.extend(['--props', render_settings['props']])
    if not render_settings.get('bundle_cache', True):
        args.append('--bundle-cache=false')
    if render_settings.get('log') and render_settings['log'] != 'info':
        args.extend(['--log', render_settings['log']])
    if render_settings.get('port', 0) > 0:
        args.extend(['--port', str(render_settings['port'])])
    if render_settings.get('public_dir'):
        args.extend(['--public-dir', render_settings['public_dir']])
    if render_settings.get('media_cache_size_in_bytes'):
        args.extend(['--media-cache-size-in-bytes', render_settings['media_cache_size_in_bytes']])
    if render_settings.get('offthreadvideo_cache_size_in_bytes'):
        args.extend(['--offthreadvideo-cache-size-in-bytes', render_settings['offthreadvideo_cache_size_in_bytes']])
    if render_settings.get('offthreadvideo_video_threads', 1) != 1:
        args.extend(['--offthreadvideo-video-threads', str(render_settings['offthreadvideo_video_threads'])])
    if render_settings.get('enable_multiprocess_on_linux'):
        args.append('--enable-multiprocess-on-linux')
    if render_settings.get('repro'):
        args.append('--repro')
    if render_settings.get('binaries_directory'):
        args.extend(['--binaries-directory', render_settings['binaries_directory']])
    if render_settings.get('experimental_rspack'):
        args.append('--experimental-rspack')
    if render_settings.get('metadata'):
        args.extend(['--metadata', render_settings['metadata']])
    if render_settings.get('color_space') and render_settings['color_space'] != 'default':
        args.extend(['--color-space', render_settings['color_space']])
    if render_settings.get('image_sequence_pattern'):
        args.extend(['--image-sequence-pattern', render_settings['image_sequence_pattern']])
    if not render_settings.get('overwrite', True):
        args.append('--overwrite=false')

    return args


def _cleanup_temp_dir(temp_dir: Optional[str]):
    if not temp_dir:
        return
    try:
        if os.path.exists(temp_dir):
            node_modules_path = os.path.join(temp_dir, "node_modules")
            if os.path.islink(node_modules_path) or os.path.isjunction(node_modules_path):
                os.remove(node_modules_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"[WARN] Failed to cleanup temp directory: {e}")


def render_video(
    script_content: str,
    output_path: str,
    render_settings: dict,
    progress_callback=None,
    cancel_event=None
) -> Tuple[bool, str]:
    if not script_content or not script_content.strip():
        return False, "Script content is empty"

    print(f"[Remotion] Script preview:\n{script_content[:500]}{'...' if len(script_content) > 500 else ''}")

    output_path = output_path.strip()
    if not output_path:
        return False, "Output path is empty"

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            return False, f"Failed to create output directory: {e}"

    node = _find_node()
    if not node:
        return False, "Node.js not found. Please ensure tools/nodejs is available."

    npm_cmd = _find_npm_cmd()
    if not npm_cmd:
        return False, "npm not found. Please ensure tools/nodejs is complete."

    temp_dir = None

    try:
        if progress_callback:
            progress_callback(5, "Setting up project...")
        temp_dir, entry_file = _setup_temp_dir(script_content, render_settings)

        print(f"[Remotion] Temp directory: {temp_dir}")
        print(f"[Remotion] Entry file: {entry_file}")

        entry_relative = os.path.relpath(entry_file, temp_dir).replace("\\", "/")

        # After sanitization, all compositions are normalized to use "main"
        composition_id = COMPOSITION_ID

        args = _build_render_args(entry_relative, composition_id, output_path, render_settings)
        print(f"[Remotion] Render args: {args}")

        if progress_callback:
            progress_callback(10, "Starting render...")

        remotion_exe, exec_type = _find_remotion_executable()
        if not remotion_exe or not exec_type:
            return False, "Remotion executable not found in tools/remotion/node_modules/.bin"

        env = os.environ.copy()
        node_dir = os.path.dirname(node)
        env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")
        env["NODE_ENV"] = "production"

        # Build command based on exec_type
        if exec_type == 'cmd':
            # Windows batch files - run through cmd.exe
            cmd = ['cmd', '/c', remotion_exe] + args
        elif exec_type == 'ps1':
            # PowerShell scripts
            cmd = ['powershell', '-NoProfile', '-File', remotion_exe] + args
        elif exec_type == 'js':
            # JS files - run with node
            cmd = [node, remotion_exe] + args
        elif exec_type == 'shell':
            # Shell scripts - run directly
            cmd = [remotion_exe] + args
        else:
            # Fallback - try with node
            cmd = [node, remotion_exe] + args
        print(f"[Remotion] Command: {' '.join(cmd)}")
        print(f"[Remotion] Working directory: {temp_dir}")

        proc = subprocess.Popen(
            cmd,
            cwd=temp_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )

        output_lines = []
        if proc.stdout:
            while True:
                line = proc.stdout.readline()
                if line == '' and proc.poll() is not None:
                    break
                if cancel_event and cancel_event.is_set():
                    try:
                        if platform.system() == 'Windows':
                            subprocess.run(
                                ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                                capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW
                            )
                        else:
                            proc.terminate()
                        proc.wait(timeout=5)
                    except Exception:
                        pass
                    return False, 'Render cancelled.'
                if line:
                    stripped = line.strip()
                    clean = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', stripped)
                    if clean:
                        output_lines.append(clean)
                        print(f"[Remotion] {clean}")
                    if progress_callback and ('Rendered' in line or 'Bundl' in line):
                        frame_match = re.search(r'Rendered\s+(\d+)/(\d+)', line)
                        if frame_match:
                            current = int(frame_match.group(1))
                            total = int(frame_match.group(2))
                            pct = int(current / total * 100) if total > 0 else 0
                            # Extract ETA if present
                            eta_match = re.search(r'time remaining[:\s]+([0-9]+h\s*[0-9]+m\s*[0-9]+s|[0-9]+m\s*[0-9]+s|[0-9]+s)', line, re.IGNORECASE)
                            eta_text = eta_match.group(1).strip() if eta_match else ''
                            msg = f"Frame {current}/{total}"
                            if eta_text:
                                msg += f", ETA: {eta_text}"
                            progress_callback(min(pct, 99), msg)
                        elif 'Bundl' in line:
                            progress_callback(5, "Bundling...")

        proc.wait()

        if proc.returncode == 0:
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if progress_callback:
                    progress_callback(100, "Render complete!")
                return True, f"Render completed successfully!\nOutput: {output_path}\nSize: {file_size / 1024 / 1024:.1f} MB"
            else:
                if progress_callback:
                    progress_callback(100, "Render complete!")
                return True, f"Render completed but output file not found at expected path.\nCheck: {output_path}"
        else:
            full_output = "\n".join(output_lines)
            error_lines = output_lines[-30:] if output_lines else ["Unknown error"]
            error_msg = "\n".join(error_lines)
            print(f"[Remotion] Render failed with exit code {proc.returncode}")
            return False, f"Render failed (exit code {proc.returncode}):\n{error_msg}"

    except Exception as e:
        print(f"[Remotion] Exception: {str(e)}")
        return False, f"Render error: {str(e)}"

    finally:
        if progress_callback:
            progress_callback(100, "Cleaning up...")
        if temp_dir:
            _cleanup_temp_dir(temp_dir)
