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
REMOTION_ENTRY_FILE = "index.tsx"
COMPOSITION_ID = "main"


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


def _detect_component_name(script_content: str) -> Optional[str]:
    match = re.search(r'export\s+default\s+(?:function\s+)?(\w+)', script_content)
    if match:
        return match.group(1)
    match = re.search(r'(?:const|function|class)\s+(\w+)', script_content)
    if match:
        return match.group(1)
    return None


BASE_COMPOSITION_WIDTH = 1280
BASE_COMPOSITION_HEIGHT = 720


def _build_entry_content(component_name: str, render_settings: dict) -> str:
    fps = render_settings.get('fps', 30)
    duration = render_settings.get('duration', 10)
    duration_frames = int(fps * duration) if duration > 0 else int(fps * 10)

    return f'''import React from 'react';
import {{ registerRoot, Composition }} from 'remotion';
import {{ MyComponent }} from './MyComponent';

export const RemotionRoot: React.FC = () => {{
  return (
    <Composition
      id="{COMPOSITION_ID}"
      component={{MyComponent}}
      durationInFrames={{{duration_frames}}}
      fps={{{fps}}}
      width={{{BASE_COMPOSITION_WIDTH}}}
      height={{{BASE_COMPOSITION_HEIGHT}}}
    />
  );
}};

registerRoot(RemotionRoot);
'''


def _prepare_user_script(script_content: str) -> Tuple[str, str]:
    modified = script_content
    if 'import React' not in modified and 'from \'react\'' not in modified and 'from "react"' not in modified:
        modified = "import React from 'react';\n" + modified

    component_name = _detect_component_name(modified)
    if not component_name:
        component_name = "MyComponent"
        modified = modified + f"\n\nconst {component_name} = () => {{ return <div>Empty</div>; }};\n"

    if f'export {{ {component_name} }}' not in modified and 'export default' not in modified and f'export const {component_name}' not in modified and f'export function {component_name}' not in modified:
        modified = modified + f"\n\nexport {{ {component_name} }};\n"

    has_named_export = f'export {{ {component_name} }}' in modified or f'export const {component_name}' in modified or f'export function {component_name}' in modified
    if has_named_export:
        pass
    elif 'export default' in modified:
        modified = modified.replace(f'export default {component_name}', f'export {{ {component_name} }}')
        modified = modified.replace(f'export default function {component_name}', f'export function {component_name}')

    return modified, component_name


def _setup_temp_dir(script_content: str, render_settings: dict) -> Tuple[str, str]:
    if not os.path.exists(PROJECT_TEMP_DIR):
        os.makedirs(PROJECT_TEMP_DIR, exist_ok=True)

    temp_dir = os.path.join(PROJECT_TEMP_DIR, REMOTION_TEMP_DIR_NAME)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

    os.makedirs(temp_dir, exist_ok=True)
    src_dir = os.path.join(temp_dir, REMOTION_SRC_DIR)
    os.makedirs(src_dir, exist_ok=True)

    if _script_has_register_root(script_content):
        entry_file = os.path.join(src_dir, REMOTION_ENTRY_FILE)
        with open(entry_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
    elif _script_has_composition(script_content):
        entry_file = os.path.join(src_dir, REMOTION_ENTRY_FILE)
        if 'registerRoot' not in script_content:
            root_name = _detect_component_name(script_content)
            if not root_name:
                root_name = "Root"
            wrapped = script_content
            if "import { registerRoot" not in wrapped and "import {registerRoot" not in wrapped:
                wrapped = wrapped.replace("from 'remotion'", "registerRoot, Composition } from 'remotion'") if "registerRoot" not in wrapped else wrapped
                if "registerRoot" not in wrapped:
                    wrapped = "import { registerRoot } from 'remotion';\n" + wrapped
            wrapped = wrapped + f"\n\nregisterRoot({root_name});\n"
            with open(entry_file, 'w', encoding='utf-8') as f:
                f.write(wrapped)
        else:
            with open(entry_file, 'w', encoding='utf-8') as f:
                f.write(script_content)
    else:
        prepared_script, component_name = _prepare_user_script(script_content)
        component_file = os.path.join(src_dir, "MyComponent.tsx")
        with open(component_file, 'w', encoding='utf-8') as f:
            f.write(prepared_script)

        entry_content = _build_entry_content(component_name, render_settings)
        entry_content = entry_content.replace(
            "import { MyComponent } from './MyComponent';",
            f"import {{ {component_name} as MyComponent }} from './MyComponent';"
        ) if component_name != "MyComponent" else entry_content

        entry_file = os.path.join(src_dir, REMOTION_ENTRY_FILE)
        with open(entry_file, 'w', encoding='utf-8') as f:
            f.write(entry_content)

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

    # Copy node_modules instead of symlinking to avoid issues
    src_node_modules = os.path.join(TOOLS_REMOTION, "node_modules")
    dst_node_modules = os.path.join(temp_dir, "node_modules")
    if os.path.exists(src_node_modules):
        try:
            shutil.copytree(src_node_modules, dst_node_modules, symlinks=False, ignore=shutil.ignore_patterns('.git', '.DS_Store'))
        except Exception as e:
            print(f"[Remotion] Warning: Failed to copy node_modules: {e}")
            # Try to install dependencies using npm
            try:
                npm_cmd = _find_npm_cmd()
                if npm_cmd:
                    print("[Remotion] Installing dependencies...")
                    env = os.environ.copy()
                    node_dir = os.path.dirname(npm_cmd[0])
                    env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")
                    subprocess.run(
                        npm_cmd + ["install"],
                        cwd=temp_dir,
                        env=env,
                        check=True,
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
                    )
                    print("[Remotion] Dependencies installed successfully")
                else:
                    print("[Remotion] npm not found, dependencies may be missing")
            except subprocess.CalledProcessError as e:
                print(f"[Remotion] Failed to install dependencies: {e}")
            except Exception as e:
                print(f"[Remotion] Error installing dependencies: {e}")

    return temp_dir, entry_file


def setup_preview_dir(script_content: str) -> Tuple[str, str]:
    preview_dir = os.path.join(PROJECT_TEMP_DIR, REMOTION_PREVIEW_DIR_NAME)
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir, ignore_errors=True)
    render_settings = {'width': 1280, 'height': 720, 'fps': 30, 'duration': 10}
    orig_name = REMOTION_TEMP_DIR_NAME
    import types
    import helpers.remotion_helper.remotion_helper as _self_mod
    _self_mod.REMOTION_TEMP_DIR_NAME = REMOTION_PREVIEW_DIR_NAME
    try:
        result = _setup_temp_dir(script_content, render_settings)
    finally:
        _self_mod.REMOTION_TEMP_DIR_NAME = orig_name
    return result


def cleanup_preview_dir():
    preview_dir = os.path.join(PROJECT_TEMP_DIR, REMOTION_PREVIEW_DIR_NAME)
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir, ignore_errors=True)
        print('[Remotion] Preview dir cleaned up')


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

    target_width = render_settings.get('width', BASE_COMPOSITION_WIDTH)
    scale = target_width / BASE_COMPOSITION_WIDTH
    if scale != 1.0:
        args.extend(['--scale', str(scale)])
    if render_settings.get('fps', 0) > 0:
        args.extend(['--fps', str(int(render_settings['fps']))])

    if render_settings.get('codec') and render_settings['codec'] != 'h264':
        args.extend(['--codec', render_settings['codec']])
    if render_settings.get('pixel_format') and render_settings['pixel_format'] != 'yuv420p':
        args.extend(['--pixel-format', render_settings['pixel_format']])
    if render_settings.get('image_format') and render_settings['image_format'] != 'jpeg':
        args.extend(['--image-format', render_settings['image_format']])
    if render_settings.get('sequence', False):
        args.append('--sequence')
    if render_settings.get('frames'):
        args.extend(['--frames', render_settings['frames']])
    if render_settings.get('every_nth_frame', 1) > 1:
        args.extend(['--every-nth-frame', str(render_settings['every_nth_frame'])])

    if render_settings.get('audio_codec') and render_settings['audio_codec'] != 'aac':
        args.extend(['--audio-codec', render_settings['audio_codec']])
    if render_settings.get('audio_bitrate'):
        args.extend(['--audio-bitrate', render_settings['audio_bitrate']])
    if render_settings.get('muted', False):
        args.append('--muted')
    if render_settings.get('enforce_audio_track', False):
        args.append('--enforce-audio-track')
    if render_settings.get('separate_audio_to'):
        args.extend(['--separate-audio-to', render_settings['separate_audio_to']])
    if render_settings.get('for_seamless_aac_concatenation', False):
        args.append('--for-seamless-aac-concatenation')

    has_video_bitrate = bool(render_settings.get('video_bitrate'))
    has_crf = render_settings.get('crf', 0) > 0
    print(f"[Remotion] video_bitrate='{render_settings.get('video_bitrate')}', crf={render_settings.get('crf')}, has_video_bitrate={has_video_bitrate}")
    if has_crf and not has_video_bitrate:
        args.extend(['--crf', str(render_settings['crf'])])
    elif has_video_bitrate:
        args.extend(['--video-bitrate', render_settings['video_bitrate']])
    if render_settings.get('buffer_size'):
        args.extend(['--buffer-size', render_settings['buffer_size']])
    if render_settings.get('max_rate'):
        args.extend(['--max-rate', render_settings['max_rate']])
    if render_settings.get('jpeg_quality', 80) != 80:
        args.extend(['--jpeg-quality', str(render_settings['jpeg_quality'])])
    if render_settings.get('prores_profile') and render_settings['prores_profile'] != 'auto':
        args.extend(['--prores-profile', render_settings['prores_profile']])
    if render_settings.get('x264_preset') and render_settings['x264_preset'] != 'medium':
        args.extend(['--x264-preset', render_settings['x264_preset']])
    if render_settings.get('gif_loops', 0) > 0:
        args.extend(['--number-of-gif-loops', str(render_settings['gif_loops'])])

    if render_settings.get('concurrency', 0) > 0:
        args.extend(['--concurrency', str(render_settings['concurrency'])])
    if render_settings.get('hardware_acceleration') and render_settings['hardware_acceleration'] not in ['disabled', 'none']:
        args.extend(['--hardware-acceleration', render_settings['hardware_acceleration']])
    if render_settings.get('disallow_parallel_encoding', False):
        args.append('--disallow-parallel-encoding')

    if render_settings.get('browser_executable'):
        args.extend(['--browser-executable', render_settings['browser_executable']])
    if render_settings.get('chrome_mode') and render_settings['chrome_mode'] != 'default':
        args.extend(['--chrome-mode', render_settings['chrome_mode']])
    if render_settings.get('timeout', 30000) != 30000:
        args.extend(['--timeout', str(render_settings['timeout'])])
    if render_settings.get('ignore_certificate_errors', False):
        args.append('--ignore-certificate-errors')
    if render_settings.get('disable_web_security', False):
        args.append('--disable-web-security')
    if render_settings.get('disable_headless', False):
        args.append('--disable-headless')
    if render_settings.get('dark_mode', False):
        args.append('--dark-mode')
    if render_settings.get('user_agent'):
        args.extend(['--user-agent', render_settings['user_agent']])
    if render_settings.get('gl') and render_settings['gl'] != 'default':
        args.extend(['--gl', render_settings['gl']])

    if render_settings.get('config_file'):
        args.extend(['--config', render_settings['config_file']])
    if render_settings.get('env_file'):
        args.extend(['--env-file', render_settings['env_file']])
    if render_settings.get('props_file'):
        args.extend(['--props', render_settings['props_file']])
    if render_settings.get('bundle_cache', True) is False:
        args.append('--bundle-cache=false')
    if render_settings.get('log_level') and render_settings['log_level'] != 'info':
        args.extend(['--log', render_settings['log_level']])
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
    if render_settings.get('enable_multiprocess_on_linux', False):
        args.append('--enable-multiprocess-on-linux')
    if render_settings.get('repro', False):
        args.append('--repro')
    if render_settings.get('binaries_directory'):
        args.extend(['--binaries-directory', render_settings['binaries_directory']])
    if render_settings.get('experimental_rspack', False):
        args.append('--experimental-rspack')
    if render_settings.get('metadata'):
        args.extend(['--metadata', render_settings['metadata']])
    if render_settings.get('color_space') and render_settings['color_space'] != 'default':
        args.extend(['--color-space', render_settings['color_space']])
    if render_settings.get('image_sequence_pattern'):
        args.extend(['--image-sequence-pattern', render_settings['image_sequence_pattern']])
    if render_settings.get('overwrite', True):
        args.append('--overwrite')

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

        composition_id = _detect_composition_id(script_content)
        if not _script_has_register_root(script_content) and not _script_has_composition(script_content):
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
                            progress_callback(min(pct, 99), f"Frame {current}/{total}")
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
