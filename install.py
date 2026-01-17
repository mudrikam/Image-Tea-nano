import os
import sys
import urllib.request
import zipfile
import shutil
import tempfile
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
ZIP_NAME = os.path.basename(PYTHON_URL)
TARGET_DIR = os.path.join(BASE_DIR, "python", "Windows")
REQUIREMENTS_FILE = os.path.join(BASE_DIR, "requirements.txt")

if os.name != "nt":
    print("This installer script is intended for Windows and must be run with a Windows Python.")
    sys.exit(1)

print("Image-Tea helper: downloading embedded Python. A stable internet connection is required.")
print("If download fails, manually download from: https://www.python.org/")

tmp_dir = tempfile.mkdtemp()
zip_path = os.path.join(tmp_dir, ZIP_NAME)

def reporthook(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0 and downloaded > total_size:
        downloaded = total_size
    if total_size > 0:
        percent = int(downloaded * 100 / total_size)
        print(f"Downloading... {percent}% ({downloaded}/{total_size} bytes)", end="\r")
    else:
        print(f"Downloading... ({downloaded} bytes)", end="\r")

try:
    urllib.request.urlretrieve(PYTHON_URL, zip_path, reporthook)
    print("\nDownload finished.")
except Exception as e:
    print(f"Failed to download embedded Python: {e}")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
    print("Downloaded file is missing or empty.")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

if os.path.exists(TARGET_DIR):
    shutil.rmtree(TARGET_DIR)
os.makedirs(TARGET_DIR, exist_ok=True)

try:
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(TARGET_DIR)
except Exception as e:
    print(f"Failed to extract embedded Python: {e}")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

os.remove(zip_path)

pth_files = []
for root, dirs, files in os.walk(TARGET_DIR):
    for f in files:
        if f.endswith('._pth'):
            pth_files.append(os.path.join(root, f))

site_packages = os.path.join(TARGET_DIR, 'Lib', 'site-packages')
os.makedirs(site_packages, exist_ok=True)

for pth in pth_files:
    try:
        with open(pth, 'r', encoding='utf-8') as fh:
            lines = fh.read().splitlines()
        existing = set(lines)
        additions = []
        if 'Lib' not in existing:
            additions.append('Lib')
        if os.name == 'nt' and 'Lib\\site-packages' not in existing:
            additions.append('Lib\\site-packages')
        if 'import site' not in existing:
            additions.append('import site')
        if additions:
            with open(pth, 'a', encoding='utf-8') as fh:
                fh.write('\n' + '\n'.join(additions) + '\n')
    except Exception as e:
        print(f"Failed to update pth file {pth}: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        sys.exit(1)

get_pip_url = 'https://bootstrap.pypa.io/get-pip.py'
get_pip_path = os.path.join(TARGET_DIR, 'get-pip.py')
try:
    urllib.request.urlretrieve(get_pip_url, get_pip_path)
    print('Downloaded get-pip.py')
except Exception as e:
    print(f"Failed to download get-pip.py: {e}")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

python_exe = os.path.join(TARGET_DIR, 'python.exe')
if not os.path.exists(python_exe):
    print('Embedded python executable not found after extraction.')
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

try:
    subprocess.check_call([python_exe, get_pip_path, '--no-warn-script-location'])
except subprocess.CalledProcessError:
    print('Failed to bootstrap pip into the embedded Python using get-pip.py.')
    print(f'Please run the following command with the embedded python executable (do NOT use system Python):\n{python_exe} {get_pip_path} --no-warn-script-location')
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

rv = subprocess.call([python_exe, '-m', 'pip', '--version'])
if rv != 0:
    print('pip is not importable after running get-pip.py.')
    print(f'Please run the following command with the embedded python executable (do NOT use system Python):\n{python_exe} {get_pip_path} --no-warn-script-location')
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

subprocess.check_call([python_exe, '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'])
if os.path.exists(REQUIREMENTS_FILE):
    try:
        subprocess.check_call([python_exe, '-m', 'pip', 'install', '-r', REQUIREMENTS_FILE, '--no-warn-script-location'])
    except subprocess.CalledProcessError as e:
        print(f"Failed to install requirements: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        sys.exit(1)

shutil.rmtree(tmp_dir, ignore_errors=True)
print('Embedded Python installed and configured successfully.')

launcher_bat = os.path.join(BASE_DIR, 'Launcher.bat')
if os.path.exists(launcher_bat):
    print('Launching application via Launcher.bat...')
    try:
        subprocess.call([launcher_bat], shell=True)
    except Exception as e:
        print(f'Failed to launch Launcher.bat automatically: {e}')
        print('You can start the app by running Launcher.bat manually.')
else:
    print('Launcher.bat not found. You can start the application with the embedded python executable:')
    print(f'{python_exe} {os.path.join(BASE_DIR, "main.py")}')

sys.exit(0)
