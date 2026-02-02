import os
import json
import requests
import zipfile
import tempfile
from datetime import datetime
from config import BASE_PATH

class ReleaseNotFoundError(Exception):
    pass

CACHE_NAME = "health_checker_cache.json"
HEALTH_FLAG = ".is_health_verified"
ZIP_NAME = "Image-Tea-nano.zip"
IGNORE_DIRS = {"temp", ".git", "__pycache__"}

# load ignore patterns from .gitignore to better match repository ignores
import fnmatch

def _load_gitignore_patterns():
    gitignore = os.path.join(BASE_PATH, '.gitignore')
    patterns = []
    if os.path.exists(gitignore):
        try:
            with open(gitignore, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    # normalize trailing slash and ignore comments
                    patterns.append(line.rstrip('/'))
        except Exception:
            pass
    return patterns

IGNORE_PATTERNS = _load_gitignore_patterns()


def _app_config():
    cfg_path = os.path.join(BASE_PATH, "configs", "app_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _tag_from_config():
    cfg = _app_config()
    tag = cfg.get("version", "")
    if not tag.startswith("v"):
        tag = "v" + tag
    return tag


def cache_path():
    return os.path.join(BASE_PATH, "temp", CACHE_NAME)


def health_flag_path():
    return os.path.join(BASE_PATH, "temp", HEALTH_FLAG)


def _download_release_zip(tag, dest_path, progress_reporter=None):
    cfg = _app_config()
    repo = cfg.get("links", {}).get("repo", "")
    if repo.endswith("/"):
        repo = repo[:-1]
    parts = repo.rstrip("/").split("/")
    if len(parts) < 2:
        raise RuntimeError("Invalid repo URL in config")
    owner, repo_name = parts[-2], parts[-1]
    url = f"https://github.com/{owner}/{repo_name}/releases/download/{tag}/{ZIP_NAME}"
    resp = requests.get(url, stream=True, timeout=30)
    if resp.status_code == 404:
        raise ReleaseNotFoundError(f"Release {tag} not found at {url}")
    resp.raise_for_status()
    total = resp.headers.get('Content-Length')
    try:
        total_length = int(total) if total else 0
    except Exception:
        total_length = 0
    downloaded = 0
    chunk_size = 1024 * 64
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if callable(progress_reporter) and total_length:
                    try:
                        percent = int((downloaded * 100) / total_length)
                        progress_reporter(percent)
                    except Exception:
                        pass
    if callable(progress_reporter):
        try:
            progress_reporter(100)
        except Exception:
            pass
    return dest_path


def is_development():
    """Return True if a .env file exists with DEVELOPMENT=true (case-insensitive)."""
    env_path = os.path.join(BASE_PATH, '.env')
    if not os.path.exists(env_path):
        return False
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip().upper() == 'DEVELOPMENT' and v.strip().lower() == 'true':
                        return True
    except Exception:
        pass
    return False


def _list_files_in_zip(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        if names:
            first = names[0]
            if '/' in first:
                top = first.split('/')[0] + '/'
                names = [n[len(top):] if n.startswith(top) else n for n in names]
        return sorted(names)


def build_remote_cache(force_refresh=False, progress_reporter=None):
    tag = _tag_from_config()
    cache_file = cache_path()
    old_cache = None

    if is_development():
        return {'tag': tag, 'fetched_at': datetime.utcnow().isoformat() + 'Z', 'files': []}

    if os.path.exists(cache_file) and not force_refresh:
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('tag') == tag and cache.get('files'):
                old_cache = cache
                fetched = cache.get('fetched_at')
                if fetched:
                    try:
                        fetched_dt = datetime.fromisoformat(fetched.rstrip('Z'))
                        age_seconds = (datetime.utcnow() - fetched_dt).total_seconds()
                        if age_seconds < 24 * 3600:
                            return cache
                    except Exception:
                        pass
                else:
                    pass
        except Exception:
            old_cache = None

    tmp_zip = os.path.join(tempfile.gettempdir(), f"health_{tag}.zip")
    try:
        try:
            _download_release_zip(tag, tmp_zip, progress_reporter=progress_reporter)
        except ReleaseNotFoundError as e:
            if old_cache is not None:
                try:
                    print(f"Warning: release not found ({e}), using existing cache.")
                except Exception:
                    pass
                return old_cache
            empty_cache = {'tag': tag, 'fetched_at': datetime.utcnow().isoformat() + 'Z', 'files': []}
            try:
                print(f"Warning: release not found ({e}), creating empty cache.")
            except Exception:
                pass
            return empty_cache
        except Exception as e:
            if old_cache is not None:
                try:
                    print(f"Warning: failed to refresh remote cache ({e}), using existing cache.")
                except Exception:
                    pass
                return old_cache
            raise

        files = _list_files_in_zip(tmp_zip)
        cache = {
            'tag': tag,
            'fetched_at': datetime.utcnow().isoformat() + 'Z',
            'files': files
        }
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        return cache
    finally:
        try:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
        except Exception:
            pass


def load_cache():
    p = cache_path()
    if not os.path.exists(p):
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def local_file_set():
    files = []
    for root, dirs, filenames in os.walk(BASE_PATH):
        # skip ignored dirs (first component)
        relroot = os.path.relpath(root, BASE_PATH)
        parts = relroot.split(os.sep)
        if parts and parts[0] in IGNORE_DIRS:
            continue
        for fn in filenames:
            rel = os.path.relpath(os.path.join(root, fn), BASE_PATH).replace('\\', '/')
            # apply .gitignore patterns (basic matching)
            skip = False
            for pat in IGNORE_PATTERNS:
                try:
                    if fnmatch.fnmatch(rel, pat) or rel.startswith(pat + '/') or rel == pat:
                        skip = True
                        break
                except Exception:
                    continue
            if skip:
                continue
            files.append(rel)
    return set(sorted(files))


def compare_with_cache(cache=None, unit_callback=None):
    if cache is None:
        cache = load_cache()
    if not cache:
        raise RuntimeError("No cache available. Run build_remote_cache() first.")
    remote_files = list(cache.get('files', []))
    local_files = local_file_set()
    missing = []
    for f in remote_files:
        if callable(unit_callback):
            unit_callback()
        if f not in local_files:
            missing.append(f)
    extra = sorted(list(local_files - set(remote_files)))
    return {
        'tag': cache.get('tag'),
        'missing': missing,
        'extra': extra,
        'remote_count': len(remote_files),
        'local_count': len(local_files)
    }


def repair_missing(missing_files, tag=None):
    if not missing_files:
        return {'repaired': 0}
    if not tag:
        tag = _tag_from_config()
    tmp_zip = os.path.join(tempfile.gettempdir(), f"health_{tag}.zip")
    try:
        _download_release_zip(tag, tmp_zip)
    except ReleaseNotFoundError as e:
        try:
            print(f"Warning: release not found ({e}), cannot repair missing files.")
        except Exception:
            pass
        return {'repaired': 0}
    repaired = 0
    try:
        with zipfile.ZipFile(tmp_zip, 'r') as z:
            # determine top-level prefix
            allnames = [n for n in z.namelist() if not n.endswith('/')]
            top = ''
            if allnames and '/' in allnames[0]:
                top = allnames[0].split('/')[0] + '/'
            for need in missing_files:
                member = top + need if top else need
                if member in z.namelist():
                    target_path = os.path.join(BASE_PATH, need.replace('/', os.sep))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with z.open(member) as src, open(target_path, 'wb') as dst:
                        dst.write(src.read())
                    repaired += 1
                else:
                    print(f"Warning: {need} not found inside release zip")
    finally:
        try:
            os.remove(tmp_zip)
        except Exception:
            pass
    return {'repaired': repaired}


def write_health_flag(tag):
    p = health_flag_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'tag': tag, 'verified_at': datetime.utcnow().isoformat() + 'Z'}, f)


def run_check(repair=False, force_refresh=False, verbose=True, cache=None, unit_callback=None, progress_reporter=None):
    if is_development():
        if verbose:
            print("Development mode detected (.env DEVELOPMENT=true) - skipping health check.")
        return {'skipped': True}

    tag = _tag_from_config()
    if cache is None:
        cache = build_remote_cache(force_refresh=force_refresh, progress_reporter=progress_reporter)
    if verbose:
        print(f"Health checker: using tag {cache.get('tag')} (fetched {cache.get('fetched_at')})")
    report = compare_with_cache(cache, unit_callback=unit_callback)
    if report['missing']:
        if verbose:
            print(f"Missing {len(report['missing'])} files:")
            for m in report['missing'][:20]:
                print('  -', m)
        if repair:
            res = repair_missing(report['missing'], tag=cache.get('tag'))
            if verbose:
                print(f"Repaired {res.get('repaired')} files.")
            # re-compare
            report = compare_with_cache(cache, unit_callback=unit_callback)
    if not report['missing']:
        write_health_flag(cache.get('tag'))
        if verbose:
            print("Health check OK. .is_health_verified written.")
    else:
        if verbose:
            print("Health check failed: some files are still missing.")
    return report


if __name__ == '__main__':
    # simple CLI
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--repair', action='store_true')
    p.add_argument('--force', action='store_true', help='Force refresh remote cache')
    args = p.parse_args()
    r = run_check(repair=args.repair, force_refresh=args.force, verbose=True)
    print(json.dumps(r, indent=2))
