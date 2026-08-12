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
platform=$(uname -s)
case $platform in
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

path_profile="$HOME/.profile"
case $platform:${SHELL##*/} in
  Darwin:zsh) path_profile="$HOME/.zprofile" ;;
  Darwin:bash) path_profile="$HOME/.bash_profile" ;;
  Linux:bash) path_profile="$HOME/.bashrc" ;;
  Linux:zsh) path_profile="$HOME/.zshrc" ;;
esac
path_line='export PATH="$HOME/.local/bin:$PATH"'
if [ "$bin_dir" = "$HOME/.local/bin" ]; then
  touch "$path_profile"
  if ! grep -Fqx "$path_line" "$path_profile"; then
    {
      printf '\n%s\n' '# Added by Bay300 Devices Admin'
      printf '%s\n' "$path_line"
    } >> "$path_profile"
  fi
fi

echo "Bay300 Devices Admin installed at $install_root."
echo "Run: $launcher authorize --url https://bay300.com"
if [ "$bin_dir" = "$HOME/.local/bin" ]; then
  echo "Added $bin_dir to PATH in $path_profile. Open a new terminal, then run: bay300da"
elif ! command -v bay300da >/dev/null 2>&1; then
  echo "Custom launcher directory $bin_dir was not added to PATH."
fi
if [ "${BAY300DA_HEADLESS:-0}" != 1 ] && ! "$venv/bin/python" -c 'import tkinter' >/dev/null 2>&1; then
  echo
  echo 'Tkinter is not installed, so the GUI cannot start yet.'
  case $platform in
    Linux)
      if [ -r /etc/os-release ] && grep -Eiq '^(ID|ID_LIKE)=.*(debian|ubuntu)' /etc/os-release; then
        echo 'Install it, then run bay300da gui again: sudo apt install python3-tk'
      elif [ -r /etc/os-release ] && grep -Eiq '^(ID|ID_LIKE)=.*(fedora|rhel|centos)' /etc/os-release; then
        echo 'Install it, then run bay300da gui again: sudo dnf install python3-tkinter'
      elif [ -r /etc/os-release ] && grep -Eiq '^(ID|ID_LIKE)=.*arch' /etc/os-release; then
        echo 'Install it, then run bay300da gui again: sudo pacman -S tk'
      else
        echo "Install your Linux distribution's Tkinter/Tcl-Tk package, usually with sudo."
      fi ;;
    Darwin)
      python_version=$("$venv/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
      echo 'If this Python was installed with Homebrew, run:'
      echo "  brew install python-tk@$python_version"
      echo 'Then run bay300da gui again.'
      echo 'If Homebrew does not manage this Python, install a current Python from:'
      echo 'https://www.python.org/downloads/macos/'
      echo 'Then reinstall bay300da. sudo is normally not needed.' ;;
  esac
  echo "Ask Bay300 Help: How do I install Tkinter for bay300da on $platform?"
  echo 'CLI commands are already available without Tkinter.'
fi
