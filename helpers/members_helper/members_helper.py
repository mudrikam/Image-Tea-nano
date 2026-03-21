import json
import os
import requests
from config import BASE_PATH

CREDENTIALS_CONFIG_PATH = os.path.join(BASE_PATH, "configs", "member_credentials.json")
_SUPABASE_CONFIG_PATH = os.path.join(BASE_PATH, "configs", "supabase_config.json")

MEMBER_SESSION = {
    "logged_in": False,
    "email": None,
    "nama": None,
    "license": None,
    "api_endpoint": None,
    "api_key": None,
    "status": None,
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

    print(f"[MemberHelper] verify_member status={response.status_code}")

    if response.status_code != 200:
        print(f"[MemberHelper] Error response: {response.text}")
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
        "api_endpoint": row["api_endpoint"],
        "api_key": row["api_key"],
        "status": row["status"],
    }


def login_member(email: str, license_key: str) -> dict:
    member = verify_member(email, license_key)
    if member is None:
        print(f"[MemberHelper] Login failed: email={email} license={license_key[:6]}...")
        return None

    if member.get("_error") == "device_locked":
        return {"_error": "device_locked"}

    MEMBER_SESSION["logged_in"] = True
    MEMBER_SESSION["email"] = member["email"]
    MEMBER_SESSION["nama"] = member["nama"]
    MEMBER_SESSION["license"] = member["license"]
    MEMBER_SESSION["api_endpoint"] = member["api_endpoint"]
    MEMBER_SESSION["api_key"] = member["api_key"]
    MEMBER_SESSION["status"] = member["status"]

    print(f"[MemberHelper] Login success: {member['email']} ({member['nama']})")
    return member


def logout_member():
    for key in MEMBER_SESSION:
        MEMBER_SESSION[key] = False if key == "logged_in" else None
    print("[MemberHelper] Logged out.")


def get_session() -> dict:
    return MEMBER_SESSION


def is_logged_in() -> bool:
    return MEMBER_SESSION["logged_in"] is True


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
