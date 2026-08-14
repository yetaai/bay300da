from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import platform
import shlex
import socket
import sys
import time

from .agent import DeviceAgent
from .client import Bay300Client
from .config import authorization_path,load_authorization,save_authorization
from .devices import (CARD_READER_INTEGRATION_MESSAGE,CARD_READER_PROCESSOR_CATALOG,CAPABILITIES,
                      DEVICE_TYPE_CATALOG,DeviceRegistry)
from .gui_requirements import require_tkinter
from .local_devices import normalize_local_configuration


def authorize(args) -> None:
    contact=args.contact or input("Owner/OP email or telephone: ").strip()
    agent_name=args.name or f"{socket.gethostname()} Devices Admin"
    client=Bay300Client(args.url)
    pending=client.request_authorization(contact,agent_name)
    print("Authorization requested. Open Bay300 and approve the message at the top of your workspace.")
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        response=client.poll_authorization(pending["authorizationRequestId"],pending["pollingToken"])
        if response.get("status")=="authorized":break
        if response.get("status")=="denied":raise SystemExit("The operator denied this request.")
        time.sleep(3)
    else:raise SystemExit("Authorization expired. Run 'bay300da authorize' again.")
    target=save_authorization({
        "server":args.url.rstrip("/"),"storeId":response["storeId"],
        "storeName":response["storeName"],"agentId":response["agentId"],
        "agentName":response["agentName"],"userLogin":contact,
        "token":response["authorizationToken"],
        "tokenExpiresAt":response["credentialExpiresAt"],
    })
    if args.printer:
        DeviceRegistry().add(args.printer,"bill_printer",args.printer)
    print(f"Authorized {response['storeName']} Devices Admin. Authorization: {target}")


def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog="bay300da",description="Bay300 cross-platform store Devices Admin")
    sub=parser.add_subparsers(dest="command")
    auth=sub.add_parser("authorize",help="Authorize this Devices Admin for one store")
    auth.add_argument("--url",default="https://bay300.com");auth.add_argument("--contact")
    auth.add_argument("--name");auth.add_argument("--printer",help="Add an initial Bill printer")
    sub.add_parser("gui",help="Open the Devices Admin GUI app")
    sub.add_parser("version",help="Show the installed bay300da version")
    type_query=sub.add_parser("type",help="List device types and Card reader processors")
    type_query.add_argument("--json",action="store_true",help="Print machine-readable JSON")
    uninstall=sub.add_parser("uninstall",help="Remove the managed bay300da program")
    uninstall.add_argument("--yes",action="store_true",help="Skip the confirmation prompt")
    local=sub.add_parser("local",help="List locally discovered printers and document scanners")
    local.add_argument("--json",action="store_true",help="Print machine-readable JSON")
    sub.add_parser("run",help="Run continuous command-line polling")
    sub.add_parser("once",help="Synchronize devices and handle at most one task")
    sub.add_parser("poll",help="Synchronize devices and handle at most one task now")
    sub.add_parser("doctor",help="Check authorization and local device status")
    device=sub.add_parser("device",help="Manage local devices without the GUI app")
    actions=device.add_subparsers(dest="device_command",required=True)
    listing=actions.add_parser("list",help="List configured local devices")
    listing.add_argument("--json",action="store_true",help="Print machine-readable JSON")
    add=actions.add_parser("add",help="Add a local device")
    add.add_argument("--name",required=True);add.add_argument("--type",required=True,
        choices=tuple(DEVICE_TYPE_CATALOG))
    add.add_argument("--configuration",default="",help="Printer name, scanner identifier, or local configuration")
    add.add_argument("--processor",choices=tuple(CARD_READER_PROCESSOR_CATALOG),
                     help="Required when --type cardReader")
    add.add_argument("--processor-name",help="Required only when --processor other")
    add.add_argument("--json",action="store_true",help="Print machine-readable JSON")
    edit=actions.add_parser("edit",help="Edit a local device")
    edit.add_argument("device",help="Full device ID or unique case-insensitive name prefix")
    edit.add_argument("--name");edit.add_argument("--type",choices=tuple(DEVICE_TYPE_CATALOG))
    edit.add_argument("--configuration");edit.add_argument("--json",action="store_true",help="Print machine-readable JSON")
    edit.add_argument("--processor",choices=tuple(CARD_READER_PROCESSOR_CATALOG))
    edit.add_argument("--processor-name",help="Required only when --processor other")
    remove=actions.add_parser("remove",help="Remove a local device while retaining server task history")
    remove.add_argument("device",help="Full device ID or unique case-insensitive name prefix")
    remove.add_argument("--yes",action="store_true",help="Skip the confirmation prompt")
    for action_name in ("block","unblock","check"):
        action=actions.add_parser(action_name,help=f"{action_name.capitalize()} a local device")
        action.add_argument("device",help="Full device ID or unique case-insensitive name prefix")
        action.add_argument("--json",action="store_true",help="Print machine-readable JSON")
    return parser


def show_types(json_output: bool=False) -> None:
    rows=[{"kind":"device","name":name,"fullName":full_name}
          for name,(_,full_name) in DEVICE_TYPE_CATALOG.items()]
    rows.extend({"kind":"processor","name":name,"fullName":full_name}
                for name,(_,full_name) in CARD_READER_PROCESSOR_CATALOG.items())
    if json_output:print(json.dumps(rows,sort_keys=True));return
    print("KIND  NAME  FULL NAME")
    for row in rows:print(f"{row['kind']}  {row['name']}  {row['fullName']}")


def _print_device(row: dict,json_output: bool=False) -> None:
    if json_output:print(json.dumps(row,sort_keys=True));return
    detail=row.get("statusMessage","")
    processor=row.get("processorName","")
    device_type=next((name for name,(value,_) in DEVICE_TYPE_CATALOG.items()
                      if value==row["type"]),row["type"])
    status=(CARD_READER_INTEGRATION_MESSAGE if row["type"]=="card_reader"
            and row["status"]=="integration_required" else row["status"])
    print(f"{row['id']}  {row['name']}  {device_type}  {processor}  {status}  "
          f"{row.get('configuration','')}  {detail}")


def manage_device(args,authorization: dict) -> None:
    registry=DeviceRegistry()
    if args.device_command=="list":
        rows=registry.list()
        if args.json:print(json.dumps(rows,sort_keys=True))
        elif not rows:print("No local devices configured.")
        else:
            print("ID  NAME  TYPE  PROCESSOR  STATUS  CONFIGURATION  STATUS DETAIL")
            for row in rows:_print_device(row)
        return
    try:
        if args.device_command=="add":
            device_type=DEVICE_TYPE_CATALOG[args.type][0]
            processor=(CARD_READER_PROCESSOR_CATALOG[args.processor][0]
                       if args.processor else "")
            selector="" if device_type=="card_reader" else args.configuration or args.name
            configuration=normalize_local_configuration(selector,device_type)
            row=registry.add(args.name,device_type,configuration,processor,
                             args.processor_name or "")
        else:
            selected=registry.resolve(args.device)
            device_id=selected["id"]
        if args.device_command=="edit":
            device_type=(DEVICE_TYPE_CATALOG[args.type][0] if args.type else selected["type"])
            processor=(CARD_READER_PROCESSOR_CATALOG[args.processor][0]
                       if args.processor else None)
            configuration=(normalize_local_configuration(args.configuration,device_type)
                           if args.configuration is not None else None)
            changes={key:value for key,value in {
                "name":args.name,"type":device_type if args.type else None,
                "configuration":configuration,"processor":processor,
                "processorName":args.processor_name,
            }.items() if value is not None}
            if not changes:raise SystemExit(
                "Specify --name, --type, --configuration, or processor fields to edit."
            )
            row=registry.update(device_id,**changes)
        elif args.device_command=="remove":
            if not args.yes and input(f"Remove local device {selected['name']}? [y/N] ").strip().lower() not in {"y","yes"}:
                print("Device removal cancelled.");return
            registry.remove(device_id);row=None
        elif args.device_command=="block":row=registry.block(device_id,True)
        elif args.device_command=="unblock":row=registry.block(device_id,False)
        elif args.device_command=="check":row=registry.check(device_id)
    except (KeyError,ValueError) as error:
        message=error.args[0] if error.args else str(error)
        raise SystemExit(f"Device change failed: {message}") from error
    try:DeviceAgent(authorization,registry).sync()
    except Exception as error:
        raise SystemExit(f"Local device change was saved, but server synchronization failed: {error}") from error
    if row is None:print(f"Removed {selected['name']}; server task history is retained.")
    else:_print_device(row,args.json)


def dispatch(args) -> None:
    if args.command=="version":
        print(f"bay300da {importlib.metadata.version('bay300-device-agent')}");return
    if args.command=="type":show_types(args.json);return
    if args.command=="uninstall":
        from .uninstall import uninstall_managed
        try:uninstall_managed(args.yes)
        except RuntimeError as error:raise SystemExit(str(error)) from error
        return
    if args.command=="local":
        from .local_devices import discover_local_devices,print_local_devices
        print_local_devices(discover_local_devices(),args.json);return
    if args.command=="authorize":authorize(args);return
    if args.command=="gui":require_tkinter()
    try:authorization=load_authorization()
    except RuntimeError as error:raise SystemExit(str(error)) from error
    if args.command=="gui":
        from .gui import run_gui
        run_gui(authorization)
        return
    if args.command=="device":manage_device(args,authorization);return
    agent=DeviceAgent(authorization)
    if args.command=="run":agent.run_forever()
    elif args.command in {"once","poll"}:print("Handled one task." if agent.run_once() else "No compatible queued task.")
    else:
        print(f"Python: {platform.python_version()}")
        print(f"Authorization: {authorization_path()}")
        print(f"Store: {authorization['storeName']} ({authorization['storeId']})")
        print(f"Token expires: {authorization['tokenExpiresAt']}")
        registry=DeviceRegistry();rows=registry.list()
        print(f"Local devices: {len(rows)}")
        for row in rows:
            checked=registry.check(row["id"]);print(f"- {checked['name']}: {checked['status']} · {checked.get('statusMessage','')}")
        agent.sync()


def enable_shell_line_editing() -> bool:
    """Activate cursor movement and command history for Python's input prompt."""
    try:
        readline=importlib.import_module("readline")
    except ImportError:
        return False
    if hasattr(readline,"set_auto_history"):readline.set_auto_history(True)
    if hasattr(readline,"set_history_length"):readline.set_history_length(200)
    return True


def interactive_shell(parser: argparse.ArgumentParser) -> None:
    line_editing=enable_shell_line_editing()
    print("Bay300 Devices Admin command shell. Type 'help' for commands; 'exit' or 'quit' to close.")
    if not line_editing and getattr(sys.stdin,"isatty",lambda:False)():
        print("Terminal cursor editing is unavailable in this Python installation.")
    while True:
        try:line=input("bay300da> ").strip()
        except EOFError:
            print();return
        except KeyboardInterrupt:
            print("\nInput cancelled. Type 'exit' or 'quit' to close.");continue
        if not line:continue
        if line.lower() in {"exit","quit"}:
            print("Devices Admin shell closed.");return
        try:tokens=shlex.split(line)
        except ValueError as error:
            print(f"Command could not be parsed: {error}");continue
        if tokens[0].lower()=="help":
            if len(tokens)==1:parser.print_help();continue
            tokens=tokens[1:]+["--help"]
        try:
            args=parser.parse_args(tokens)
            if args.command is None:parser.print_help()
            else:dispatch(args)
        except KeyboardInterrupt:
            print("\nCommand interrupted. Returning to the bay300da prompt.")
        except SystemExit as error:
            if isinstance(error.code,str):print(error.code)


def main(argv=None) -> None:
    parser=build_parser();args=parser.parse_args(argv)
    if args.command is None:interactive_shell(parser);return
    dispatch(args)


if __name__=="__main__":main()
