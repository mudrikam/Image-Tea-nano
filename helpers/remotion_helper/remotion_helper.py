import os
import sys
import subprocess
import platform
import shutil
import tempfile
import json
import re
from pathlib import Path
from typing import Optional, Tuple, List

BASE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TOOLS_NODEJS = os.path.join(BASE_PATH, "tools", "nodejs")
TOOLS_REMOTION = os.path.join(BASE_PATH, "tools", "remotion")
PROJECT_TEMP_DIR = os.path.join(BASE_PATH, "temp")

REMOTION_TEMP_DIR_NAME = "remotion_temp"
REMOTION_SRC_DIR = "src"
REMOTION_ENTRY_FILE = "index.tsx"


def _find_node() -> Optional[str]:
    """Find Node.js executable in tools/nodejs or system PATH."""
    # Check tools/nodejs
    for root, dirs, files in os.walk(TOOLS_NODEJS):
        for name in ["node", "node.exe"]:
            if name in files:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    return path
    # Check system PATH
    return shutil.which("node")


def _find_npm_cmd() -> Optional[str]:
    """Find npm command in tools/nodejs or system PATH."""
    # Check tools/nodejs for npm.cmd (Windows) or npm (Unix)
    for root, dirs, files in os.walk(TOOLS_NODEJS):
        for name in ["npm.cmd", "npm"]:
            if name in files:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    return path
    # Check system PATH
    npm = shutil.which("npm")
    if npm:
        return npm
    return None


def _find_npx_runner(node_path: str) -> Optional[List[str]]:
    """Find npx runner, returns command list to execute."""
    # Check for npx-cli.js (common in portable Node)
    for root, dirs, files in os.walk(TOOLS_NODEJS):
        if "npx-cli.js" in files:
            return [node_path, os.path.join(root, "npx-cli.js")]

    # Check for npx.cmd (Windows)
    if platform.system() == "Windows":
        for root, dirs, files in os.walk(TOOLS_NODEJS):
            if "npx.cmd" in files:
                return ["cmd", "/c", os.path.join(root, "npx.cmd")]

    # Check for npx (Unix)
    for root, dirs, files in os.walk(TOOLS_NODEJS):
        if "npx" in files:
            return [node_path, os.path.join(root, "npx")]

    # System npx
    system_npx = shutil.which("npx")
    if system_npx:
        if platform.system() == "Windows" and system_npx.endswith(".cmd"):
            return ["cmd", "/c", system_npx]
        return [node_path, system_npx]

    return None


def _create_root_wrapper(script_content: str, composition_name: str = "VibeComposition") -> Optional[str]:
    """Create a root file that registers the user's composition.
    Returns None if the script already calls registerRoot()."""
    # Check if script already calls registerRoot (not just imports it)
    # Must import from remotion AND actually call registerRoot(...)
    has_remotion_import = 'from \'remotion\'' in script_content or 'from "remotion"' in script_content or \
                          'from \'@remotion/root\'' in script_content or 'from "@remotion/root"' in script_content
    has_register_root_call = 'registerRoot(' in script_content

    if has_remotion_import and has_register_root_call:
        return None

    # Create wrapper that imports the composition and registers it
    # registerRoot should receive the component directly, not an object
    wrapper = f'''import {{registerRoot}} from 'remotion';
import Composition from './Composition';

registerRoot(Composition);
'''
    return wrapper


def _setup_temp_dir(script_content: str) -> Tuple[str, str, str]:
    """Setup temporary directory for rendering."""
    # Ensure project temp directory exists
    if not os.path.exists(PROJECT_TEMP_DIR):
        os.makedirs(PROJECT_TEMP_DIR, exist_ok=True)

    temp_dir = os.path.join(PROJECT_TEMP_DIR, REMOTION_TEMP_DIR_NAME)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    os.makedirs(temp_dir, exist_ok=True)

    # Create src directory
    src_dir = os.path.join(temp_dir, REMOTION_SRC_DIR)
    os.makedirs(src_dir, exist_ok=True)

    # Check if we need a wrapper or if user's script already has registerRoot
    root_wrapper = _create_root_wrapper(script_content)

    if root_wrapper is None:
        # User script already contains registerRoot, use it directly as entry point
        entry_file = os.path.join(src_dir, REMOTION_ENTRY_FILE)
        with open(entry_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        composition_file = entry_file
    else:
        # Wrap user's script with registerRoot
        # The user's script should define a component that we export
        # Wrap it properly to export as default and register
        composition_file = os.path.join(src_dir, "Composition.tsx")

        # Check if script has a default export, add one if not
        modified_script = script_content
        if 'export default' not in script_content:
            # Try to find the component name (typically the function name after const or function)
            import re
            component_match = re.search(r'(?:const|function)\s+(\w+)\s*[=\(]', script_content)
            if component_match:
                component_name = component_match.group(1)
                # Add export default at the end
                modified_script = script_content + f"\n\nexport default {component_name};\n"
            else:
                # Fallback: wrap the whole script in a way that works
                modified_script = script_content + "\n\n// Auto-export for Remotion\nexport default SimpleAnimation;\n"

        with open(composition_file, 'w', encoding='utf-8') as f:
            f.write(modified_script)

        # Create index.tsx with wrapper
        entry_file = os.path.join(src_dir, REMOTION_ENTRY_FILE)
        with open(entry_file, 'w', encoding='utf-8') as f:
            f.write(root_wrapper)

    # Copy package.json and package-lock.json from tools/remotion
    for pkg_file in ["package.json", "package-lock.json"]:
        src = os.path.join(TOOLS_REMOTION, pkg_file)
        if os.path.exists(src):
            dst = os.path.join(temp_dir, pkg_file)
            shutil.copy2(src, dst)

    # Copy or create tsconfig.json
    tsconfig_src = os.path.join(TOOLS_REMOTION, "tsconfig.json")
    if os.path.exists(tsconfig_src):
        shutil.copy2(tsconfig_src, os.path.join(temp_dir, "tsconfig.json"))
    else:
        # Create a basic tsconfig for Remotion
        tsconfig_content = {
            "compilerOptions": {
                "target": "es2020",
                "module": "es2020",
                "jsx": "react",
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

    # Copy node_modules fully (do not preserve symlinks) to ensure all package files are accessible
    src_node_modules = os.path.join(TOOLS_REMOTION, "node_modules")
    dst_node_modules = os.path.join(temp_dir, "node_modules")
    if os.path.exists(src_node_modules):
        if os.path.islink(dst_node_modules) or os.path.exists(dst_node_modules):
            shutil.rmtree(dst_node_modules)
        # Copy everything, following symlinks to actual files
        shutil.copytree(src_node_modules, dst_node_modules, symlinks=False)

    return temp_dir, entry_file, composition_file


def _build_render_args(
    entry_file: str,
    output_path: str,
    render_settings: dict
) -> List[str]:
    """Build command line arguments for remotion render."""
    args = ["remotion", "render", entry_file, output_path]

    # Video settings
    if render_settings.get('codec') and render_settings['codec'] != 'h264':
        args.extend(['--codec', render_settings['codec']])
    if render_settings.get('pixel_format') and render_settings['pixel_format'] != 'yuv420p':
        args.extend(['--pixel-format', render_settings['pixel_format']])
    if render_settings.get('width', 0) > 0:
        args.extend(['--width', str(render_settings['width'])])
    if render_settings.get('height', 0) > 0:
        args.extend(['--height', str(render_settings['height'])])
    if render_settings.get('fps', 0) > 0:
        args.extend(['--fps', str(render_settings['fps'])])
    if render_settings.get('duration', 0) > 0:
        args.extend(['--duration', str(render_settings['duration'])])
    if render_settings.get('scale', 1.0) != 1.0:
        args.extend(['--scale', str(render_settings['scale'])])
    if render_settings.get('image_format') and render_settings['image_format'] != 'jpeg':
        args.extend(['--image-format', render_settings['image_format']])
    if render_settings.get('sequence', False):
        args.append('--sequence')
    if render_settings.get('frames'):
        args.extend(['--frames', render_settings['frames']])
    if render_settings.get('every_nth_frame', 1) > 1:
        args.extend(['--every-nth-frame', str(render_settings['every_nth_frame'])])

    # Audio settings
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

    # Quality settings
    if render_settings.get('crf', 0) > 0:
        args.extend(['--crf', str(render_settings['crf'])])
    if render_settings.get('video_bitrate'):
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

    # Performance settings
    if render_settings.get('concurrency', 0) > 0:
        args.extend(['--concurrency', str(render_settings['concurrency'])])
    if render_settings.get('hardware_acceleration') and render_settings['hardware_acceleration'] != 'none':
        args.extend(['--hardware-acceleration', render_settings['hardware_acceleration']])
    if render_settings.get('disallow_parallel_encoding', False):
        args.append('--disallow-parallel-encoding')

    # Browser settings
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

    # Advanced settings
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
    if render_settings.get('overwrite', True) is False:
        args.append('--overwrite=false')

    return args


def _cleanup_temp_dir(temp_dir: Optional[str]):
    """Cleanup temporary directory after rendering."""
    if not temp_dir:
        return
    try:
        if os.path.exists(temp_dir):
            # On Windows, sometimes files are locked. Try to force cleanup.
            if platform.system() == "Windows":
                # Use robocopy to mirror empty dir or just ignore errors
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    # As last resort, try to delete on next reboot (not ideal but better than crash)
                    pass
            else:
                shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"[WARN] Failed to cleanup temp directory: {e}")


def render_video(
    script_content: str,
    output_path: str,
    render_settings: dict,
    progress_callback=None
) -> Tuple[bool, str]:
    """
    Render a video using Remotion.

    Args:
        script_content: TypeScript/React code for the composition
        output_path: Full path to output file (including filename and extension)
        render_settings: Dictionary of render settings from RenderSettingsTabWidget.
                         Should include 'overwrite' key (bool) to control overwrite behavior.
        progress_callback: Optional callback(percentage, message) for progress updates

    Returns:
        (success: bool, message: str)
    """
    if not script_content or not script_content.strip():
        return False, "Script content is empty"

    # Debug: print first 500 chars of script
    print(f"[DEBUG] Script (first 500 chars):\n{script_content[:500]}{'...' if len(script_content) > 500 else ''}")

    output_path = output_path.strip()
    if not output_path:
        return False, "Output path is empty"

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            return False, f"Failed to create output directory: {e}"

    # Find Node.js and npx
    node = _find_node()
    if not node:
        return False, "Node.js not found. Please ensure tools/nodejs is available."

    npm_cmd = _find_npm_cmd()
    if not npm_cmd:
        return False, "npm not found. Please ensure tools/nodejs is complete."

    npx_runner = _find_npx_runner(node)
    if not npx_runner:
        return False, "npx not found. Please ensure tools/nodejs is complete."

    temp_dir = None

    try:
        # Setup temp dir with script and dependencies
        if progress_callback:
            progress_callback(0, "Setting up temporary directory...")
        temp_dir, entry_file, _ = _setup_temp_dir(script_content)

        print(f"[DEBUG] Temp directory: {temp_dir}")
        print(f"[DEBUG] Entry file: {entry_file}")

        # Build command using the entry file returned by setup
        args = _build_render_args(entry_file, output_path, render_settings)
        print(f"[DEBUG] Render args: {args}")

        # Execute
        if progress_callback:
            progress_callback(10, "Starting render...")

        env = os.environ.copy()
        env["NODE_ENV"] = "development"
        env["PATH"] = os.path.dirname(node) + os.pathsep + env.get("PATH", "")

        # Add REMCTION_LOG_LEVEL for more detailed errors
        env["REMOTION_LOG_LEVEL"] = "debug"

        # On Windows, handle npm.cmd properly - but npx_runner already includes proper command
        cmd = npx_runner + args

        print(f"[DEBUG] Running command: {' '.join(cmd)}")
        print(f"[DEBUG] Working directory: {temp_dir}")

        # Run process and capture output
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

        # Read output line by line
        output_lines = []
        if proc.stdout:
            while True:
                line = proc.stdout.readline()
                if line == '' and proc.poll() is not None:
                    break
                if line:
                    output_lines.append(line.strip())
                    # Simple progress parsing from remotion output
                    if progress_callback and ('%' in line or 'Rendering' in line or 'frame' in line.lower()):
                        # Try to extract percentage
                        match = re.search(r'(\d+)%', line)
                        if match:
                            pct = int(match.group(1))
                            # Map 0-100% to 20-100% of our progress bar
                            progress = 20 + int(pct * 0.8)
                            progress_callback(progress, f"Rendering: {pct}%")
                        else:
                            progress_callback(None, line.strip())

        proc.wait()

        if proc.returncode == 0:
            if progress_callback:
                progress_callback(100, "Render complete!")
            return True, "Render completed successfully"
        else:
            # Capture full output
            full_output = "\n".join(output_lines) if output_lines else "Unknown error"
            error_msg = "\n".join(output_lines[-20:]) if output_lines else "Unknown error"
            # Print to console for easier debugging
            print(f"[REmotion Render Error] Failed with exit code {proc.returncode}")
            print(f"[REmotion Render Error] Full output:\n{full_output}")
            return False, f"Render failed with exit code {proc.returncode}\nOutput:\n{error_msg}"

    except Exception as e:
        # Print to console for easier debugging
        print(f"[REmotion Render Exception] {str(e)}")
        return False, f"Render error: {str(e)}"

    finally:
        # Cleanup
        if progress_callback:
            progress_callback(100, "Cleaning up...")
        if temp_dir:
            _cleanup_temp_dir(temp_dir)
