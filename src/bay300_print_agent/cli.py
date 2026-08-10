from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path

from .agent import PrintAgent
from .client import Bay300Client


def default_config_path() -> Path:
    return Path(os.environ.get("BAY300_PRINT_AGENT_CONFIG", "~/.config/bay300-print-agent/config.json")).expanduser()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Configuration not found: {path}. Run 'bay300-print-agent enroll' first.")
    if os.name=='posix' and path.stat().st_mode & 0o077:
        raise SystemExit(f"Configuration is readable by another account: {path}. Run chmod 600 on it.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bay300 store Bill print agent")
    parser.add_argument("--config", type=Path, default=default_config_path())
    sub = parser.add_subparsers(dest="command", required=True)
    enroll = sub.add_parser("enroll", help="Enroll this store machine with a one-time code")
    enroll.add_argument("--url", default="https://bay300.com")
    enroll.add_argument("--code")
    enroll.add_argument("--name", default=socket.gethostname())
    enroll.add_argument("--printer", help="CUPS printer name; omit to use the default printer")
    sub.add_parser("once", help="Poll and handle at most one job")
    sub.add_parser("run", help="Run the polling loop")
    sub.add_parser("doctor", help="Check configuration and local print command")
    args = parser.parse_args()

    if args.command == "enroll":
        code = args.code or getpass.getpass("One-time enrollment code: ")
        response = Bay300Client(args.url).enroll(code, args.name)
        print_command = f"lp -d {args.printer} {{file}}" if args.printer else "lp {file}"
        save_config(args.config, {
            "base_url": args.url.rstrip("/"),
            "agent_id": response["agentId"],
            "store_id": response["storeId"],
            "device_name": response["deviceName"],
            "device_token": response["deviceToken"],
            "work_directory": "~/.local/share/bay300-print-agent",
            "poll_seconds": 5,
            "print_command": print_command,
        })
        print(f"Enrolled {response['deviceName']} for store {response['storeId']}. Config: {args.config}")
        return

    config = load_config(args.config)
    agent = PrintAgent(config)
    if args.command == "once":
        print("Handled one job." if agent.run_once() else "No queued print job.")
    elif args.command == "run":
        agent.run_forever()
    else:
        print(f"Python: {platform.python_version()}")
        print(f"Config permissions: {oct(args.config.stat().st_mode & 0o777)}")
        print(f"Store: {config['store_id']} · Agent: {config['agent_id']}")
        print(f"Print command: {config.get('print_command') or '(render only)'}")
        if config.get("print_command") and not shutil.which("lp"):
            raise SystemExit("CUPS 'lp' command is not installed or not on PATH")
        if shutil.which("lpstat"):
            check=subprocess.run(["lpstat","-d"],capture_output=True,text=True,check=False)
            print((check.stdout or check.stderr).strip())
