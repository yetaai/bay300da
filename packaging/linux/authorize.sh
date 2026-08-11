#!/bin/sh
set -eu
bay300da="${XDG_DATA_HOME:-$HOME/.local/share}/bay300/devices-admin/venv/bin/bay300da"
test -x "$bay300da" || { echo 'Run install.sh first.' >&2; exit 1; }
exec "$bay300da" authorize --url https://bay300.com
