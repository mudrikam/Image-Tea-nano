import subprocess
import hashlib
import platform
import re
import os


_WMIC_INVALID = {
    "", "to be filled by o.e.m.", "none", "not specified",
    "not available", "default string", "system serial number",
    "00000000", "ffffffff",
}


def _wmic(args: list) -> str:
    try:
        result = subprocess.check_output(
            ["wmic"] + args,
            text=True,
            timeout=8,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
        )
        lines = [l.strip() for l in result.strip().splitlines() if l.strip()]
        val = lines[-1] if len(lines) >= 2 else ""
        return "" if val.lower() in _WMIC_INVALID else val
    except Exception as e:
        print(f"[DeviceFingerprint] wmic {' '.join(args)} failed: {e}")
        return ""


def _run(cmd: list, timeout: int = 8) -> str:
    try:
        return subprocess.check_output(
            cmd, text=True, timeout=timeout, stderr=subprocess.DEVNULL
        ).strip()
    except Exception as e:
        print(f"[DeviceFingerprint] {cmd[0]} failed: {e}")
        return ""


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _windows_fingerprint() -> str:
    # Primary: Motherboard UUID — firmware-level, never changes unless board replaced.
    # Intentionally EXCLUDED: GPU (changes on swap), hostname, OS version.
    mb_uuid = _wmic(["csproduct", "get", "UUID"])
    if mb_uuid:
        fp = _sha256(f"WIN_UUID:{mb_uuid}")
        print(f"[DeviceFingerprint] Windows MB_UUID ok hash={fp[:12]}...")
        return fp

    # Secondary: CPU ProcessorId + Baseboard Serial — still hardware-level.
    parts = []
    cpu_id = _wmic(["cpu", "get", "ProcessorId"])
    if cpu_id:
        parts.append(f"CPU:{cpu_id}")
    mb_serial = _wmic(["baseboard", "get", "SerialNumber"])
    if mb_serial:
        parts.append(f"MBS:{mb_serial}")
    if parts:
        fp = _sha256("WIN_HW:" + "|".join(parts))
        print(f"[DeviceFingerprint] Windows HW fallback hash={fp[:12]}...")
        return fp

    return None


def _macos_fingerprint() -> str:
    # IOPlatformUUID — definitive Apple hardware UUID, identical on Intel and Apple Silicon
    # (M1/M2/M3/M4). Survives OS reinstall, changes only on logic board replacement.
    ioreg = _run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"])
    if ioreg:
        uuid_m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', ioreg)
        serial_m = re.search(r'"IOPlatformSerialNumber"\s*=\s*"([^"]+)"', ioreg)
        hw_uuid = uuid_m.group(1) if uuid_m else ""
        hw_serial = serial_m.group(1) if serial_m else ""
        if hw_uuid:
            fp = _sha256(f"MAC:{hw_uuid}:{hw_serial}")
            print(f"[DeviceFingerprint] macOS IOPlatformUUID ok hash={fp[:12]}...")
            return fp

    # Secondary: system_profiler — slower but same data source.
    sp = _run(["system_profiler", "SPHardwareDataType"], timeout=15)
    if sp:
        uuid_m = re.search(r"Hardware UUID:\s*(\S+)", sp)
        serial_m = re.search(r"Serial Number.*?:\s*(\S+)", sp)
        hw_uuid = uuid_m.group(1) if uuid_m else ""
        hw_serial = serial_m.group(1) if serial_m else ""
        if hw_uuid:
            fp = _sha256(f"MAC_SP:{hw_uuid}:{hw_serial}")
            print(f"[DeviceFingerprint] macOS system_profiler ok hash={fp[:12]}...")
            return fp

    return None


def _linux_fingerprint() -> str:
    invalid_uuids = {
        "", "to be filled by o.e.m.", "none",
        "00000000-0000-0000-0000-000000000000",
    }

    # Primary: DMI product UUID — hardware-level, readable without root on modern kernels.
    try:
        dmi_uuid = open("/sys/class/dmi/id/product_uuid").read().strip()
        if dmi_uuid.lower() not in invalid_uuids:
            fp = _sha256(f"LNX_DMI:{dmi_uuid}")
            print(f"[DeviceFingerprint] Linux DMI UUID ok hash={fp[:12]}...")
            return fp
    except Exception:
        pass

    # Secondary: board serial + product serial combined.
    parts = []
    for path, key in [
        ("/sys/class/dmi/id/board_serial", "BOARD"),
        ("/sys/class/dmi/id/product_serial", "PROD"),
    ]:
        try:
            val = open(path).read().strip()
            if val.lower() not in invalid_uuids:
                parts.append(f"{key}:{val}")
        except Exception:
            pass
    if parts:
        fp = _sha256("LNX_HW:" + "|".join(parts))
        print(f"[DeviceFingerprint] Linux HW serial ok hash={fp[:12]}...")
        return fp

    # Tertiary: machine-id — stable per OS installation, not hardware, but better than
    # hostname. Changes on OS reinstall but not on reboot/kernel update.
    for mid_path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        try:
            mid = open(mid_path).read().strip()
            if mid:
                fp = _sha256(f"LNX_MID:{mid}")
                print(f"[DeviceFingerprint] Linux machine-id ok hash={fp[:12]}...")
                return fp
        except Exception:
            pass

    return None


def get_device_fingerprint() -> str:
    system = platform.system()
    fp = None

    if system == "Windows":
        fp = _windows_fingerprint()
    elif system == "Darwin":
        fp = _macos_fingerprint()
    elif system == "Linux":
        fp = _linux_fingerprint()

    if fp:
        return fp

    # Last resort — weak but never crashes. Only reached on exotic/unsupported platforms.
    raw = f"GENERIC:{platform.node()}:{platform.machine()}:{platform.processor()}"
    fp = _sha256(raw)
    print(f"[DeviceFingerprint] WARNING: generic fallback platform={system} hash={fp[:12]}...")
    return fp
