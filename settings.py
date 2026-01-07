"""Common environment-backed configuration values for both helper scripts."""

from __future__ import annotations

import base64
import os
from binascii import Error as BinasciiError
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - best effort and optional
    def load_dotenv(*args, **kwargs):
        return False

ROOT_DIR = Path(__file__).resolve().parent
DOTENV_PATH = ROOT_DIR / ".env"
print(f"Loading environment from {DOTENV_PATH}")
load_dotenv(DOTENV_PATH)


def _required_env(name: str) -> str:
    """Ensure secrets and host configuration are supplied rather than defaulted."""
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable {name}. "
            f"Create {DOTENV_PATH.name} or export {name} before starting."
        )
    return value


def _int_env(name: str) -> int:
    raw = _required_env(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got: {raw}") from exc


def _str_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is not None:
        return value
    return default


def _write_base64_env_to_file(
    env_name: str,
    destination: Path,
    file_mode: int,
    dir_mode: int = 0o700,
) -> None:
    raw = os.getenv(env_name)
    if not raw:
        return
    value = raw.strip()
    if not value:
        return
    try:
        decoded = base64.b64decode(value, validate=True)
    except BinasciiError as exc:
        raise ValueError(f"Environment variable {env_name} must be valid base64") from exc
    destination.parent.mkdir(mode=dir_mode, parents=True, exist_ok=True)
    destination.parent.chmod(dir_mode)
    destination.write_bytes(decoded)
    os.chmod(destination, file_mode)


MQTT_PORT = _int_env("MQTT_PORT")
MQTT_BROKER = _required_env("MQTT_BROKER")
MQTT_USER = _required_env("MQTT_USER")
MQTT_PASSWORD = _required_env("MQTT_PASSWORD")
HA_DISCOVERY_PREFIX = _str_env("HA_DISCOVERY_PREFIX", "homeassistant")
DEVICE_NAME = _required_env("DEVICE_NAME")
ANDROID_PASSWORD = _required_env("ANDROID_PASSWORD")
TELNET_HOST = _required_env("TELNET_HOST")
TELNET_PORT = _int_env("TELNET_PORT")
MAP_UPLOAD_TARGET = _str_env("MAP_UPLOAD_TARGET", f"{MQTT_BROKER}:/root/config/www/")
MAP_UPLOAD_SSH_KEY_PATH = _str_env("MAP_UPLOAD_SSH_KEY_PATH", "/root/.ssh/id_adb_ecovacs")
MAP_UPLOAD_SSH_KNOWN_HOSTS_PATH = _str_env("MAP_UPLOAD_SSH_KNOWN_HOSTS_PATH", "/root/.ssh/known_hosts")

if MAP_UPLOAD_SSH_KEY_PATH:
    _write_base64_env_to_file(
        "SSH_PRIVATE_KEY_BASE64",
        Path(MAP_UPLOAD_SSH_KEY_PATH),
        file_mode=0o600,
    )

if MAP_UPLOAD_SSH_KNOWN_HOSTS_PATH:
    _write_base64_env_to_file(
        "SSH_KNOWN_HOSTS_BASE64",
        Path(MAP_UPLOAD_SSH_KNOWN_HOSTS_PATH),
        file_mode=0o644,
    )
