import json
import os
import hashlib
import requests
from config import BASE_PATH

CREDENTIALS_CONFIG_PATH = os.path.join(BASE_PATH, "configs", "member_credentials.json")
_SUPABASE_CONFIG_PATH = os.path.join(BASE_PATH, "configs", "supabase_config.json")
_ENV_PATH = os.path.join(BASE_PATH, ".env")

MEMBER_SESSION = {
    "logged_in": False,
    "email": None,
    "nama": None,
    "license": None,
    "_api_endpoint": None,
    "_api_key": None,
    "_model": None,
    "_service_type": None,
    "status": None,
    "expires_at": None,
    "registered_at": None,
    "renewed_at": None,
}


def _load_supabase_config() -> dict:
    import base64
    _k = b'im4g3t34_s3cr3t_k3y_2026'
    def _d(s):
        xored = base64.b64decode(s)
        return bytes([b ^ _k[i % len(_k)] for i, b in enumerate(xored)]).decode('utf-8')
    with open(_SUPABASE_CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {"url": _d(raw["u"]), "anon_key": _d(raw["k"])}


def verify_member(email: str, license_key: str) -> dict:
    from helpers.members_helper.device_fingerprint import get_device_fingerprint
    cfg = _load_supabase_config()
    url = cfg["url"]
    anon_key = cfg["anon_key"]

    device_hash = get_device_fingerprint()

    response = requests.post(
        f"{url}/rest/v1/rpc/verify_member",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
        },
        json={"p_email": email, "p_license": license_key, "p_device_hash": device_hash},
        timeout=10,
    )

    if response.status_code != 200:
        print(f"[MemberHelper] verify_member failed status={response.status_code} body={response.text}")
        return None

    rows = response.json()
    if not rows:
        return None

    row = rows[0]

    if row.get("login_error") == "device_locked":
        print(f"[MemberHelper] Device locked for email={email}")
        return {"_error": "device_locked"}

    return {
        "id": row["id"],
        "nama": row["nama"],
        "email": row["email"],
        "license": row["license"],
        "_api_endpoint": row["api_endpoint"],
        "_api_key": row["api_key"],
        "_model": row["model"],
        "_service_type": row.get("service_type") or "custom",
        "status": row["status"],
        "expires_at": row.get("expires_at"),
        "registered_at": row.get("registered_at"),
        "renewed_at": row.get("renewed_at"),
    }


def login_member(email: str, license_key: str) -> dict:
    member = verify_member(email, license_key)
    if member is None:
        print(f"[MemberHelper] Login failed: email={email}")
        return None

    if member.get("_error") == "device_locked":
        return {"_error": "device_locked"}

    MEMBER_SESSION["logged_in"] = True
    MEMBER_SESSION["email"] = member["email"]
    MEMBER_SESSION["nama"] = member["nama"]
    MEMBER_SESSION["license"] = member["license"]
    MEMBER_SESSION["_api_endpoint"] = member["_api_endpoint"]
    MEMBER_SESSION["_api_key"] = member["_api_key"]
    MEMBER_SESSION["_model"] = member["_model"]
    MEMBER_SESSION["_service_type"] = member["_service_type"]
    MEMBER_SESSION["status"] = member["status"]
    MEMBER_SESSION["expires_at"] = member["expires_at"]
    MEMBER_SESSION["registered_at"] = member["registered_at"]
    MEMBER_SESSION["renewed_at"] = member["renewed_at"]

    print(f"[MemberHelper] Login success: {member['email']} ({member['nama']})")
    return {
        "email": member["email"],
        "nama": member["nama"],
        "status": member["status"],
        "expires_at": member["expires_at"],
    }


def logout_member():
    for key in MEMBER_SESSION:
        MEMBER_SESSION[key] = False if key == "logged_in" else None
    print("[MemberHelper] Logged out.")


def get_session() -> dict:
    return MEMBER_SESSION


def is_logged_in() -> bool:
    return MEMBER_SESSION["logged_in"] is True


def get_member_api_config() -> dict:
    if not is_logged_in():
        return None
    return {
        "endpoint": MEMBER_SESSION["_api_endpoint"],
        "api_key": MEMBER_SESSION["_api_key"],
        "model": MEMBER_SESSION["_model"],
        "service_type": MEMBER_SESSION["_service_type"] or "custom",
    }


def _read_member_secret_from_env() -> str:
    if not os.path.exists(_ENV_PATH):
        return None
    with open(_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.upper().startswith("MEMBER_SECRET="):
                value = line[len("MEMBER_SECRET="):]
                return value if value else None
    return None


def verify_member_secret() -> bool:
    plaintext = _read_member_secret_from_env()
    if not plaintext:
        print("[MemberHelper] MEMBER_SECRET not found or empty in .env")
        return False
    secret_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    try:
        cfg = _load_supabase_config()
        response = requests.post(
            f"{cfg['url']}/rest/v1/rpc/verify_member_secret",
            headers={
                "apikey": cfg["anon_key"],
                "Authorization": f"Bearer {cfg['anon_key']}",
                "Content-Type": "application/json",
            },
            json={"p_secret_hash": secret_hash},
            timeout=10,
        )
        if response.status_code != 200:
            print(f"[MemberHelper] verify_member_secret failed status={response.status_code}")
            return False
        result = response.json()
        return result is True
    except Exception as e:
        print(f"[MemberHelper] verify_member_secret error: {e}")
        return False


def is_member_secret_valid() -> bool:
    return verify_member_secret()


def save_credentials(email: str, license_key: str):
    data = {"email": email, "license": license_key}
    with open(CREDENTIALS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[MemberHelper] Credentials saved.")


def load_saved_credentials() -> dict:
    if not os.path.exists(CREDENTIALS_CONFIG_PATH):
        return None
    with open(CREDENTIALS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_saved_credentials():
    if os.path.exists(CREDENTIALS_CONFIG_PATH):
        os.remove(CREDENTIALS_CONFIG_PATH)
        print("[MemberHelper] Saved credentials cleared.")
