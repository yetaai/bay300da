from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

MARKER=".bay300da-managed-install"


def managed_install_root(
    prefix: Path | None=None,home: Path | None=None,system: str | None=None,
    local_app_data: str | None=None,
) -> Path:
    prefix=(prefix or Path(sys.prefix)).resolve()
    home=(home or Path.home()).resolve();system=system or platform.system()
    candidate=prefix.parent
    if prefix.name.lower()!="venv":
        raise RuntimeError("This bay300da copy is not in a managed installation. Remove it with the package manager that installed it.")
    if system=="Darwin":expected=home/"Library/Application Support/Bay300/DevicesAdmin"
    elif system=="Windows":
        base=Path(local_app_data or os.environ.get("LOCALAPPDATA",home/"AppData/Local"))
        expected=base/"Bay300/DevicesAdmin"
    else:expected=Path(os.environ.get("XDG_DATA_HOME",home/".local/share"))/"bay300/devices-admin"
    if candidate.resolve()==expected.resolve() or (candidate/MARKER).is_file():return candidate
    raise RuntimeError("This bay300da copy is not marked as a managed installation. Remove it with the package manager that installed it.")


def _schedule_windows_removal(root: Path) -> None:
    script=Path(tempfile.gettempdir())/f"bay300da-uninstall-{uuid.uuid4().hex}.cmd"
    script.write_text(
        "@echo off\r\ntimeout /t 2 /nobreak >nul\r\n"
        f'rmdir /s /q "{root}"\r\n'
        'del /q "%~f0"\r\n',encoding="utf-8",
    )
    subprocess.Popen(
        [os.environ.get("COMSPEC","cmd.exe"),"/c",str(script)],
        creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
            | getattr(subprocess,"DETACHED_PROCESS",0),
        close_fds=True,
    )


def uninstall_managed(
    assume_yes: bool=False,prefix: Path | None=None,home: Path | None=None,
    system: str | None=None,local_app_data: str | None=None,
) -> None:
    home=(home or Path.home()).resolve();system=system or platform.system()
    root=managed_install_root(prefix,home,system,local_app_data)
    if not assume_yes:
        answer=input(
            f"Remove the bay300da program from {root}? Local data under {home/'.bay300'} will be preserved. [y/N] "
        ).strip().lower()
        if answer not in {"y","yes"}:
            print("Uninstall cancelled.");return
    launcher=home/".local/bin/bay300da"
    if launcher.is_symlink():
        expected=(root/"venv/bin/bay300da").resolve()
        if launcher.resolve()==expected:launcher.unlink()
    if system=="Windows":
        _schedule_windows_removal(root)
        print(f"bay300da removal scheduled for {root}.")
    else:
        shutil.rmtree(root)
        print(f"bay300da removed from {root}.")
    print(f"Local authorization, devices, and work were preserved in {home/'.bay300'}.")
    print("If this computer is being retired, revoke its authorization from Bay300 Device Monitor.")
