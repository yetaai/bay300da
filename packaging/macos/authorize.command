#!/bin/sh
set -eu
bay300da="$HOME/Library/Application Support/Bay300/DevicesAdmin/venv/bin/bay300da"
test -x "$bay300da" || { echo 'Run install.command first.' >&2; exit 1; }
exec "$bay300da" authorize --url https://bay300.com
