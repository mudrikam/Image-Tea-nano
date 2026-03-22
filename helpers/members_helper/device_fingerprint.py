import subprocess
import hashlib
import platform


def _wmic(args: list) -> str:
    try:
        result = subprocess.check_output(
            ["wmic"] + args,
            text=True,
            timeout=8,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000
        )
        lines = [l.strip() for l in result.strip().splitlines() if l.strip()]
        return lines[-1] if len(lines) >= 2 else ""
    except Exception as e:
        print(f"[DeviceFingerprint] wmic {' '.join(args)} failed: {e}")
        return ""


def get_device_fingerprint() -> str:
    parts = []

    cpu_id = _wmic(["cpu", "get", "ProcessorId"])
    if cpu_id:
        parts.append(f"CPU:{cpu_id}")

    mb_uuid = _wmic(["csproduct", "get", "UUID"])
    if mb_uuid:
        parts.append(f"MB:{mb_uuid}")

    mb_serial = _wmic(["baseboard", "get", "SerialNumber"])
    if mb_serial:
        parts.append(f"MBS:{mb_serial}")

    gpu_id = _wmic(["path", "win32_VideoController", "get", "PNPDeviceID"])
    if gpu_id:
        parts.append(f"GPU:{gpu_id}")

    if not parts:
        parts.append(f"NODE:{platform.node()}")
        parts.append(f"PROC:{platform.processor()}")

    combined = "|".join(parts)
    fingerprint = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    print(f"[DeviceFingerprint] components={len(parts)} hash={fingerprint[:12]}...")
    return fingerprint
