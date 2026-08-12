#!/bin/sh
set -eu
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3.11 or newer is required.' >&2
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,11)' || {
  echo 'Python 3.11 or newer is required.' >&2
  exit 1
}
python3 -c 'import tkinter' >/dev/null 2>&1 || {
  echo 'Tkinter is required. On Debian/Ubuntu run: sudo apt install python3-tk' >&2
  exit 1
}
install_root="${XDG_DATA_HOME:-$HOME/.local/share}/bay300/devices-admin"
bin_dir="$HOME/.local/bin"
python3 -m venv "$install_root/venv"
"$install_root/venv/bin/python" -m pip install --upgrade "$(dirname "$0")/agent"
mkdir -p "$bin_dir"
ln -sfn "$install_root/venv/bin/bay300da" "$bin_dir/bay300da"
profile="$HOME/.profile"
case ${SHELL##*/} in
  bash) profile="$HOME/.bashrc" ;;
  zsh) profile="$HOME/.zshrc" ;;
esac
path_line='export PATH="$HOME/.local/bin:$PATH"'
touch "$profile"
if ! grep -Fqx "$path_line" "$profile"; then
  printf '\n%s\n%s\n' '# Added by Bay300 Devices Admin' "$path_line" >> "$profile"
fi
echo 'Bay300 Devices Admin installed.'
echo "Added $bin_dir to PATH in $profile. Open a new terminal to run bay300da by name."
echo 'Next run ./authorize.sh, then ./run.sh.'
