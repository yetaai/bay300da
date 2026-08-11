#!/bin/sh
set -eu
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3.11 or newer is required. Install it from https://www.python.org/downloads/macos/' >&2
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,11)' || {
  echo 'Python 3.11 or newer is required.' >&2
  exit 1
}
python3 -c 'import tkinter' >/dev/null 2>&1 || {
  echo 'This Python installation does not include Tkinter. Use the current python.org macOS installer.' >&2
  exit 1
}
install_root="$HOME/Library/Application Support/Bay300/DevicesAdmin"
python3 -m venv "$install_root/venv"
"$install_root/venv/bin/python" -m pip install --upgrade "$(dirname "$0")/agent"
echo 'Bay300 Devices Admin installed.'
echo 'Next run authorize.command, then run.command.'
