from __future__ import annotations

import getpass
import json
import os
import subprocess
from pathlib import Path


def authorization_path() -> Path:
    return Path(os.environ.get("BAY300DA_AUTHORIZATION", "~/.bay300/authorization")).expanduser()


def devices_path() -> Path:
    return Path(os.environ.get("BAY300DA_DEVICES", "~/.bay300/devices.json")).expanduser()


def work_path() -> Path:
    return Path(os.environ.get("BAY300DA_WORK", "~/.bay300/work")).expanduser()


def protect(path: Path) -> None:
    if os.name == "posix":
        os.chmod(path, 0o600)
        return
    if os.name == "nt":
        user = getpass.getuser()
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(R,W)"],
            capture_output=True, check=False,
        )


def save_authorization(value: dict, path: Path | None = None) -> Path:
    target=path or authorization_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
    protect(target)
    return target


def load_authorization(path: Path | None = None) -> dict:
    target=path or authorization_path()
    if not target.exists():
        raise RuntimeError(f"Authorization not found: {target}. Run 'bay300da authorize'.")
    if os.name=="posix" and target.stat().st_mode & 0o077:
        raise RuntimeError(f"Authorization permissions must be 600: {target}")
    value=json.loads(target.read_text(encoding="utf-8"))
    if not value.get("token") or not value.get("storeId"):
        raise RuntimeError("Authorization file is incomplete")
    return value


def save_devices(devices: list[dict], path: Path | None = None) -> Path:
    target=path or devices_path();target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(devices,indent=2)+"\n",encoding="utf-8")
    protect(target);return target


def load_devices(path: Path | None = None) -> list[dict]:
    target=path or devices_path()
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else []
