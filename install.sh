#!/bin/sh
set -eu

python_command=${PYTHON:-python3}
source_url=${BAY300DA_SOURCE:-https://github.com/yetaai/bay300da/archive/refs/heads/main.tar.gz}

if ! command -v "$python_command" >/dev/null 2>&1; then
  echo 'Python 3.11 or newer is required.' >&2
  exit 1
fi
"$python_command" -c 'import sys; assert sys.version_info >= (3,11)' || {
  echo 'Python 3.11 or newer is required.' >&2
  exit 1
}
if [ "${BAY300DA_HEADLESS:-0}" != 1 ]; then
  "$python_command" -c 'import tkinter' >/dev/null 2>&1 || {
    echo 'Tkinter is required for graphical Devices Admin.' >&2
    echo 'Debian/Ubuntu: sudo apt install python3-venv python3-tk' >&2
    echo 'macOS: install a current Python build from https://www.python.org/downloads/macos/' >&2
    echo 'For a headless-only installation, set BAY300DA_HEADLESS=1.' >&2
    exit 1
  }
fi

case $(uname -s) in
  Darwin) default_root="$HOME/Library/Application Support/Bay300/DevicesAdmin" ;;
  Linux) default_root="${XDG_DATA_HOME:-$HOME/.local/share}/bay300/devices-admin" ;;
  *)
    echo 'This one-line installer supports Linux and macOS. Use the Windows package on Windows.' >&2
    exit 1
    ;;
esac

install_root=${BAY300DA_INSTALL_ROOT:-$default_root}
bin_dir=${BAY300DA_BIN_DIR:-$HOME/.local/bin}
venv="$install_root/venv"
launcher="$bin_dir/bay300da"

mkdir -p "$install_root" "$bin_dir"
if ! "$python_command" -m venv "$venv"; then
  echo 'Could not create the Python environment.' >&2
  echo 'On Debian/Ubuntu run: sudo apt install python3-venv' >&2
  exit 1
fi
"$venv/bin/python" -m pip install --upgrade "$source_url"

if [ -e "$launcher" ] && [ ! -L "$launcher" ]; then
  echo "Cannot create $launcher because a non-symlink file already exists." >&2
  exit 1
fi
ln -sfn "$venv/bin/bay300da" "$launcher"

echo "Bay300 Devices Admin installed at $install_root."
echo "Run: $launcher authorize --url https://bay300.com"
if ! command -v bay300da >/dev/null 2>&1; then
  echo "Add $bin_dir to PATH to run: bay300da"
fi
