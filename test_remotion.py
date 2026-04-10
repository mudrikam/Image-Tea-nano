#!/usr/bin/env python
"""Test script for remotion render"""
import os
import sys

# Add parent dir to path
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_PATH)

from helpers.remotion_helper.remotion_helper import (
    _find_node,
    _find_remotion_executable,
    _setup_temp_dir,
    _build_render_args,
    _detect_composition_id,
    _script_has_register_root,
    _script_has_composition
)

# Test 1: Find node
print("=" * 50)
print("Test 1: Finding Node.js")
node = _find_node()
print(f"  Node path: {node}")
print(f"  Node exists: {os.path.exists(node) if node else False}")

# Test 2: Find remotion executable
print("=" * 50)
print("Test 2: Finding Remotion executable")
remotion_exe, exec_type = _find_remotion_executable()
print(f"  Remotion path: {remotion_exe}")
print(f"  Exec type: {exec_type}")
print(f"  Remotion exists: {os.path.exists(remotion_exe) if remotion_exe else False}")

# Test 3: Setup temp dir with test script
print("=" * 50)
print("Test 3: Setup temp directory")
test_script = '''import React from 'react';
import { useCurrentFrame } from 'remotion';

export const MyVideo = () => {
  const frame = useCurrentFrame();
  return (
    <div style={{ backgroundColor: 'red', width: '100%', height: '100%' }}>
      <h1 style={{ color: 'white' }}>Frame: {frame}</h1>
    </div>
  );
};
'''

render_settings = {'fps': 30, 'duration': 2, 'width': 1920, 'height': 1080}

try:
    temp_dir, entry_file = _setup_temp_dir(test_script, render_settings)
    print(f"  Temp dir: {temp_dir}")
    print(f"  Entry file: {entry_file}")
    print(f"  Temp dir exists: {os.path.exists(temp_dir)}")
    print(f"  Entry file exists: {os.path.exists(entry_file)}")
    
    # List files in temp dir
    if os.path.exists(temp_dir):
        print(f"  Files in temp dir:")
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, temp_dir)
                print(f"    - {rel_path}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Build render args
print("=" * 50)
print("Test 4: Build render args")
try:
    entry_relative = os.path.relpath(entry_file, temp_dir).replace("\\", "/")
    composition_id = _detect_composition_id(test_script)
    if not _script_has_register_root(test_script) and not _script_has_composition(test_script):
        composition_id = "main"
    
    output_path = os.path.join(temp_dir, "test_output.mp4")
    args = _build_render_args(entry_relative, composition_id, output_path, render_settings)
    print(f"  Entry relative: {entry_relative}")
    print(f"  Composition ID: {composition_id}")
    print(f"  Output path: {output_path}")
    print(f"  Render args: {args}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Build actual command
print("=" * 50)
print("Test 5: Build actual command")
if remotion_exe and exec_type:
    if exec_type == 'cmd':
        cmd = ['cmd', '/c', remotion_exe] + args
    elif exec_type == 'ps1':
        cmd = ['powershell', '-NoProfile', '-File', remotion_exe] + args
    elif exec_type == 'js':
        cmd = [node, remotion_exe] + args
    elif exec_type == 'shell':
        cmd = [remotion_exe] + args
    else:
        cmd = [node, remotion_exe] + args
    
    print(f"  Command: {' '.join(cmd)}")
    print(f"  Working dir: {temp_dir}")
else:
    print("  ERROR: Cannot build command - remotion executable not found")

# Test 6: Dry run - just check if command can be executed
print("=" * 50)
print("Test 6: Dry run check")
try:
    if exec_type == 'cmd':
        # Just test if cmd.exe can be invoked
        import subprocess
        result = subprocess.run(['cmd', '/c', 'echo', 'test'], capture_output=True, text=True, timeout=5)
        print(f"  cmd.exe test: {'OK' if result.returncode == 0 else 'FAILED'}")
    elif exec_type == 'js' and node:
        # Test if node can run
        import subprocess
        result = subprocess.run([node, '--version'], capture_output=True, text=True, timeout=5)
        print(f"  Node.js version: {result.stdout.strip()}")
except Exception as e:
    print(f"  ERROR: {e}")

print("=" * 50)
print("Test complete")
