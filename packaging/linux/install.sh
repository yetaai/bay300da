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
install_root="${XDG_DATA_HOME:-$HOME/.local/share}/bay300/devices-admin"
bin_dir="$HOME/.local/bin"
mkdir -p "$install_root"
: > "$install_root/.bay300da-managed-install"
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
if ! "$install_root/venv/bin/python" -c 'import tkinter' >/dev/null 2>&1; then
  echo
  echo 'Tkinter is not installed, so the GUI cannot start yet.'
  echo 'On Debian/Ubuntu install it, then run bay300da gui again:'
  echo '  sudo apt install python3-tk'
  echo 'Ask Bay300 Help: How do I install Tkinter for bay300da on Linux?'
  echo 'CLI commands are already available without Tkinter.'
fi
