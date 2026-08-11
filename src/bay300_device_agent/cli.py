from __future__ import annotations

import argparse
import platform
import socket
import time

from .agent import DeviceAgent
from .client import Bay300Client
from .config import authorization_path,load_authorization,save_authorization
from .devices import DeviceRegistry


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


def main() -> None:
    parser=argparse.ArgumentParser(prog="bay300da",description="Bay300 cross-platform store Devices Admin")
    sub=parser.add_subparsers(dest="command")
    auth=sub.add_parser("authorize",help="Authorize this Devices Admin for one store")
    auth.add_argument("--url",default="https://bay300.com");auth.add_argument("--contact")
    auth.add_argument("--name");auth.add_argument("--printer",help="Add an initial Bill printer")
    sub.add_parser("run",help="Run continuous command-line polling")
    sub.add_parser("once",help="Synchronize devices and handle at most one task")
    sub.add_parser("doctor",help="Check authorization and local device status")
    args=parser.parse_args()
    if args.command=="authorize":authorize(args);return
    try:authorization=load_authorization()
    except RuntimeError as error:raise SystemExit(str(error)) from error
    if args.command is None:
        try:
            from .gui import run_gui
            run_gui(authorization)
        except ImportError as error:raise SystemExit("Tkinter is required for the graphical Devices Admin") from error
        return
    agent=DeviceAgent(authorization)
    if args.command=="run":agent.run_forever()
    elif args.command=="once":print("Handled one task." if agent.run_once() else "No compatible queued task.")
    else:
        print(f"Python: {platform.python_version()}")
        print(f"Authorization: {authorization_path()}")
        print(f"Store: {authorization['storeName']} ({authorization['storeId']})")
        print(f"Token expires: {authorization['tokenExpiresAt']}")
        registry=DeviceRegistry();rows=registry.list()
        print(f"Local devices: {len(rows)}")
        for row in rows:
            checked=registry.check(row["id"]);print(f"- {checked['name']}: {checked['status']} · {checked.get('statusMessage','')}")


if __name__=="__main__":main()
