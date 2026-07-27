import json
import locale
import os
import platform
import uuid

import requests
from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QSettings, qVersion

from config import BASE_PATH
from helpers.members_helper.members_helper import get_supabase_public_config


FEEDBACK_TYPES = ("bug_report", "request", "feedback")
FIELD_LIMITS = {"name": 100, "title": 200, "message": 10_000}
DIAGNOSTIC_KEYS = (
    "app_version",
    "os_name",
    "os_release",
    "architecture",
    "python_version",
    "qt_version",
    "pyside_version",
    "locale",
)
REQUEST_TIMEOUT = 15


class FeedbackError(Exception):
    def __init__(self, message, code="submission_failed", retryable=True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def get_client_token():
    """Return a random installation token stored by the operating system."""
    settings = QSettings("Desainia Studio", "Image Tea")
    token = settings.value("feedback/client_token", "", type=str)
    if isinstance(token, str) and len(token) == 32:
        return token
    token = uuid.uuid4().hex
    settings.setValue("feedback/client_token", token)
    settings.sync()
    return token


def _bounded_string(value, limit=200):
    return str(value or "").strip()[:limit]


def collect_diagnostics():
    version = "unknown"
    try:
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as config_file:
            version = json.load(config_file).get("version", version)
    except (OSError, ValueError, TypeError):
        pass

    try:
        locale_name = locale.getlocale()[0] or "unknown"
    except (ValueError, TypeError):
        locale_name = "unknown"

    diagnostics = {
        "app_version": version,
        "os_name": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "qt_version": qVersion(),
        "pyside_version": PYSIDE_VERSION,
        "locale": locale_name,
    }
    return {key: _bounded_string(diagnostics[key]) for key in DIAGNOSTIC_KEYS}


def diagnostics_summary(diagnostics=None):
    values = diagnostics or collect_diagnostics()
    return "\n".join(
        (
            f"Image Tea: {values.get('app_version', 'unknown')}",
            f"Operating system: {values.get('os_name', 'unknown')} {values.get('os_release', '')}".rstrip(),
            f"Architecture: {values.get('architecture', 'unknown')}",
            f"Python: {values.get('python_version', 'unknown')}",
            f"Qt / PySide: {values.get('qt_version', 'unknown')} / {values.get('pyside_version', 'unknown')}",
            f"Locale: {values.get('locale', 'unknown')}",
        )
    )


def build_feedback_payload(name, title, feedback_type, message, diagnostics=None):
    fields = {
        "name": str(name or "").strip(),
        "title": str(title or "").strip(),
        "type": str(feedback_type or "").strip(),
        "message": str(message or "").strip(),
    }
    for field in ("name", "title", "message"):
        if not fields[field]:
            raise FeedbackError(f"{field.replace('_', ' ').title()} is required.", "validation_error", False)
        if len(fields[field]) > FIELD_LIMITS[field]:
            raise FeedbackError(
                f"{field.replace('_', ' ').title()} must be {FIELD_LIMITS[field]:,} characters or fewer.",
                "validation_error",
                False,
            )
    if fields["type"] not in FEEDBACK_TYPES:
        raise FeedbackError("Select a valid feedback type.", "validation_error", False)

    raw_diagnostics = diagnostics if diagnostics is not None else collect_diagnostics()
    fields["device_properties"] = {
        key: _bounded_string(raw_diagnostics.get(key))
        for key in DIAGNOSTIC_KEYS
        if key in raw_diagnostics
    }
    return fields


def get_feedback_endpoint():
    config = get_supabase_public_config()
    url = str(config.get("url") or "").rstrip("/")
    anon_key = str(config.get("anon_key") or "")
    if not url or not anon_key:
        raise FeedbackError("Feedback service is not configured.", "configuration_error")
    return (
        f"{url}/rest/v1/rpc/submit_feedback",
        {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
        },
    )


def _error_details(data):
    if not isinstance(data, dict):
        return "", ""
    error = data.get("error")
    if isinstance(error, dict):
        return _bounded_string(error.get("code"), 100), _bounded_string(error.get("message"), 500)
    return (
        _bounded_string(data.get("code"), 100),
        _bounded_string(data.get("message") or data.get("error_description"), 500),
    )


def _response_message(message, fallback):
    return _bounded_string(message, 500) or fallback


def submit_feedback(payload, timeout=REQUEST_TIMEOUT):
    url, headers = get_feedback_endpoint()
    rpc_payload = {
        "p_name": payload.get("name"),
        "p_title": payload.get("title"),
        "p_type": payload.get("type"),
        "p_message": payload.get("message"),
        "p_device_properties": payload.get("device_properties", {}),
        # Random installation token: no hostname, hardware ID, account, or file data.
        "p_client_token": get_client_token(),
    }
    try:
        response = requests.post(url, headers=headers, json=rpc_payload, timeout=timeout)
    except requests.Timeout as exc:
        raise FeedbackError("Feedback was not sent because the request timed out. Please retry.", "timeout") from exc
    except requests.ConnectionError as exc:
        raise FeedbackError("Feedback was not sent. Check your internet connection and retry.", "network_error") from exc
    except requests.RequestException as exc:
        raise FeedbackError("Feedback was not sent because the service could not be reached. Please retry.", "network_error") from exc

    if 200 <= response.status_code < 300:
        try:
            data = response.json()
        except (ValueError, TypeError) as exc:
            raise FeedbackError("Feedback was not sent because the service returned an invalid response. Please retry.", "invalid_response") from exc
        row = data[0] if isinstance(data, list) and data else data
        if not isinstance(row, dict) or not row.get("id") or not row.get("created_at"):
            raise FeedbackError("Feedback was not sent because confirmation was invalid. Please retry.", "invalid_response")
        return {"id": str(row["id"]), "created_at": str(row["created_at"])}

    try:
        data = response.json()
    except (ValueError, TypeError):
        data = {}
    code, message = _error_details(data)
    normalized_code = code.upper()
    if response.status_code == 429 or normalized_code == "P0001" or message == "feedback_rate_limited":
        raise FeedbackError(
            "Too many feedback submissions. Please wait and try again later.",
            "rate_limited",
        )
    if response.status_code in (400, 422):
        raise FeedbackError(
            "Some feedback fields were rejected. Review the form and retry.",
            code or "validation_error",
            False,
        )
    raise FeedbackError(
        "Feedback was not sent because the service is temporarily unavailable. Please retry later.",
        code or "server_error",
    )
