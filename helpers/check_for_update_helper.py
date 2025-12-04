import os
import json
import requests
from datetime import datetime
from config import BASE_PATH

def get_app_config():
    config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_app_config(config):
    config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def get_update_config():
    update_path = os.path.join(BASE_PATH, "configs", "update_config.json")
    if os.path.exists(update_path):
        with open(update_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_update_config(update_config):
    update_path = os.path.join(BASE_PATH, "configs", "update_config.json")
    with open(update_path, "w", encoding="utf-8") as f:
        json.dump(update_config, f, ensure_ascii=False, indent=4)

def get_dev_github_token():
    token_path = os.path.join(BASE_PATH, "configs", "dev_github_token.json")
    if os.path.exists(token_path):
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["token"]
    return None

def fetch_latest_tag_and_commit():
    config = get_app_config()
    repo_url = config["links"]["repo"]
    if repo_url.endswith("/"):
        repo_url = repo_url[:-1]
    try:
        parts = repo_url.rstrip("/").split("/")
        owner = parts[-2]
        repo = parts[-1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=1"
        dev_token = get_dev_github_token()
        github_token = os.environ.get("GITHUB_TOKEN")
        token = dev_token or github_token
        if token:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "image-tea-updater"
            }
        else:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "image-tea-updater"
            }
        response = requests.get(api_url, headers=headers, timeout=10)
        remain = response.headers.get("X-RateLimit-Remaining")
        token_type = "dev_github_token" if dev_token else ("GITHUB_TOKEN" if github_token else "user token")
        print(f"GitHub API token type: {token_type}, Remaining tokens: {remain}")
        if response.status_code == 403:
            reset = response.headers.get("X-RateLimit-Reset")
            msg = response.json().get("message", "")
            print(f"GitHub API 403: {msg}. Remaining={remain}, Reset={reset}")
            return None, None
        response.raise_for_status()
        data = response.json()
        if not data:
            print("No tags found in the repository.")
            return None, None
        tag = data[0]["name"]
        sha = data[0]["commit"]["sha"][:7]
        return tag, sha
    except Exception as e:
        print(f"Error fetching latest tag and commit: {e}")
        return None, None


def fetch_release_notes_for_tag(tag):
    """Fetch release notes (body) for a specific tag using GitHub Releases API.
    Returns release body string or None.
    """
    config = get_app_config()
    repo_url = config["links"]["repo"]
    if repo_url.endswith("/"):
        repo_url = repo_url[:-1]
    try:
        parts = repo_url.rstrip("/").split("/")
        owner = parts[-2]
        repo = parts[-1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
        dev_token = get_dev_github_token()
        github_token = os.environ.get("GITHUB_TOKEN")
        token = dev_token or github_token
        if token:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "image-tea-updater"
            }
        else:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "image-tea-updater"
            }
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("body", "")
        # not found or other
        return None
    except Exception as e:
        print(f"Error fetching release notes for tag {tag}: {e}")
        return None

def get_local_tag_and_commit():
    config = get_app_config()
    version = config["version"]
    tag = version
    if not tag.startswith("v"):
        tag = "v" + tag
    commit_hash = None
    git_dir = os.path.join(BASE_PATH, ".git")
    if os.path.exists(git_dir):
        try:
            import subprocess
            result = subprocess.run(
                ["git", "-C", BASE_PATH, "rev-list", "-n", "1", tag],
                capture_output=True, text=True, check=True
            )
            if result.returncode == 0 and result.stdout:
                commit_hash = result.stdout.strip()[:7]
            else:
                print(f"Tag {tag} not found in local repository.")
        except subprocess.CalledProcessError:
            print(f"Tag {tag} not found in local repository.")
        except Exception as e:
            print(f"Error getting local commit hash for tag {tag}: {e}")
    else:
        print("No .git directory found in BASE_PATH.")
    return tag, commit_hash

def update_update_config(remote_tag, remote_hash, local_tag, local_hash):
    update_config = get_update_config()
    now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    if "update" not in update_config:
        update_config["update"] = {}
    update_config["commit_hash"] = {
        "remote": remote_hash,
        "local": local_hash
    }
    update_config["update"]["last_checked"] = now_iso
    if "last_update" not in update_config["update"]:
        update_config["update"]["last_update"] = now_iso
    update_config["tag_remote"] = remote_tag
    update_config["tag_local"] = local_tag
    save_update_config(update_config)

def check_for_update():
    remote_tag, remote_hash = fetch_latest_tag_and_commit()
    local_tag, local_hash = get_local_tag_and_commit()
    update_update_config(remote_tag, remote_hash, local_tag, local_hash)
    if not remote_tag:
        print("Failed to fetch remote tag.")
        return
    if not local_tag:
        print("Local tag not found.")
        return
    if (remote_tag != local_tag) or (remote_hash and local_hash and remote_hash != local_hash):
        print("Update available.")
    else:
        print("You are already using the latest version.")


def show_update_dialog_if_available(parent=None):
    remote_tag, remote_hash = fetch_latest_tag_and_commit()
    local_tag, local_hash = get_local_tag_and_commit()
    update_update_config(remote_tag, remote_hash, local_tag, local_hash)

    if not remote_tag or not local_tag:
        return

    if (remote_tag == local_tag) and (not (remote_hash and local_hash and remote_hash != local_hash)):
        return

    update_cfg = get_update_config()
    skipped = None
    try:
        skipped = update_cfg.get('update', {}).get('skipped_tag')
    except Exception:
        skipped = None
    if skipped and skipped == remote_tag:
        return

    release_notes = fetch_release_notes_for_tag(remote_tag) or ""

    update_cfg = get_update_config()
    checked_time = None
    try:
        checked_time = update_cfg.get('update', {}).get('last_checked')
    except Exception:
        checked_time = None

    try:
        from dialogs.update_notice_dialog import UpdateNoticeDialog
        dialog = UpdateNoticeDialog(parent=parent, local_tag=local_tag, remote_tag=remote_tag, remote_hash=remote_hash, release_notes=release_notes, checked_time=checked_time)
        result = dialog.exec()
        action = getattr(dialog, 'result_action', None)
        if action == 'skip':
            cfg = get_update_config()
            now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
            if 'update' not in cfg:
                cfg['update'] = {}
            cfg['update']['skipped_tag'] = remote_tag
            cfg['update']['skipped_at'] = now_iso
            save_update_config(cfg)
        elif action == 'update':
            try:
                import subprocess
                updater_path = os.path.join(BASE_PATH, "Image Tea Updater.exe")
                if os.name == 'nt':
                    subprocess.Popen(f'powershell -Command "Start-Process -Verb runAs -FilePath \\"{updater_path}\\""', shell=True)
                else:
                    subprocess.Popen([updater_path])
            except Exception as e:
                print(f"Failed to launch updater: {e}")
    except Exception as e:
        print(f"Update available: {remote_tag} (local: {local_tag}), commit: {remote_hash}. Error showing dialog: {e}")