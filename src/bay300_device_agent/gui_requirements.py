from __future__ import annotations

import platform
import sys
from pathlib import Path


def _linux_distribution() -> str:
    try:
        values={}
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                key,value=line.split("=",1);values[key]=value.strip().strip('"')
        return f"{values.get('ID','')} {values.get('ID_LIKE','')}".lower()
    except OSError:
        return ""


def tkinter_installation_help(system: str | None=None,linux_distribution: str | None=None) -> str:
    system=system or platform.system()
    if system=="Linux":
        distribution=_linux_distribution() if linux_distribution is None else linux_distribution.lower()
        if any(name in distribution for name in ("debian","ubuntu")):
            command="sudo apt install python3-tk"
        elif any(name in distribution for name in ("fedora","rhel","centos")):
            command="sudo dnf install python3-tkinter"
        elif "arch" in distribution:
            command="sudo pacman -S tk"
        elif any(name in distribution for name in ("suse","opensuse")):
            command="sudo zypper install python3-tk"
        else:
            command="Install your Linux distribution's Tkinter/Tcl-Tk package (usually with sudo)."
        return ("Tkinter is not installed, so the GUI cannot start.\n"
                f"Install it for this Python interpreter, then run 'bay300da gui' again:\n  {command}\n"
                "The CLI commands remain available without Tkinter.")
    if system=="Darwin":
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}"
        return ("Tkinter is not installed, so the GUI cannot start.\n"
                "If this Python was installed with Homebrew, run:\n"
                f"  brew install python-tk@{python_version}\n"
                "Then run 'bay300da gui' again. If Homebrew does not manage this Python, install "
                "a current Python build from https://www.python.org/downloads/macos/ and reinstall "
                "bay300da. sudo is normally not needed on macOS.\n"
                "Ask Bay300 Help: How do I install Tkinter for bay300da on macOS?\n"
                "The CLI commands remain available without Tkinter.")
    if system=="Windows":
        return ("Tkinter is not installed, so the GUI cannot start.\n"
                "Open the official Python installer, choose Modify, and enable 'tcl/tk and IDLE'; "
                "then reinstall bay300da and run 'bay300da gui' again.\n"
                "Download Python from https://www.python.org/downloads/windows/ if needed. "
                "Administrator access is normally not required for a per-user installation.")
    return ("Tkinter is not installed, so the GUI cannot start. Install Tcl/Tk and the Tkinter "
            "module supplied for this Python interpreter, then run 'bay300da gui' again. "
            "The CLI commands remain available.")


def require_tkinter() -> None:
    try:
        import tkinter  # noqa: F401
    except ImportError as error:
        raise SystemExit(tkinter_installation_help()) from error
