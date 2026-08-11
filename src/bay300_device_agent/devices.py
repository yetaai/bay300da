from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import uuid

from .config import load_devices,save_devices


CAPABILITIES={
    "bill_printer":["bill_print"],"check_printer":["check_print"],
    "printer":["bill_print","check_print"],"scanner":["scan"],"other":[],
}


class DeviceRegistry:
    def __init__(self):self.lock=threading.RLock()
    def list(self) -> list[dict]:
        with self.lock:return load_devices()

    def save(self,devices: list[dict]) -> None:
        with self.lock:save_devices(devices)

    def add(self,name: str,device_type: str,configuration: str="") -> dict:
        with self.lock:
            devices=self.list()
            row={"id":uuid.uuid4().hex,"name":name.strip(),"type":device_type,
                 "capabilities":CAPABILITIES[device_type],"status":"ready",
                 "configuration":configuration.strip(),"statusMessage":"Not checked yet"}
            devices.append(row);self.save(devices);return row

    def update(self,device_id: str,**changes) -> dict:
        with self.lock:
            devices=self.list();match=None
            for row in devices:
                if row["id"]==device_id:
                    row.update({key:value for key,value in changes.items() if value is not None})
                    if "type" in changes:row["capabilities"]=CAPABILITIES[changes["type"]]
                    match=row
            if not match:raise KeyError(device_id)
            self.save(devices);return match

    def remove(self,device_id: str) -> None:
        with self.lock:
            devices=[row for row in self.list() if row["id"]!=device_id]
            self.save(devices)

    def block(self,device_id: str,blocked: bool=True) -> dict:
        return self.update(device_id,status="blocked" if blocked else "ready",
                           statusMessage="Blocked locally" if blocked else "Ready")

    def check(self,device_id: str) -> dict:
        row=next((item for item in self.list() if item["id"]==device_id),None)
        if not row:raise KeyError(device_id)
        if row["status"]=="blocked":return row
        configuration=row.get("configuration","")
        try:
            if row["type"] in {"bill_printer","check_printer","printer"}:
                if os.name=="nt":
                    command=["powershell","-NoProfile","-Command",
                             f"Get-Printer -Name '{configuration}' -ErrorAction Stop | Out-Null"]
                elif shutil.which("lpstat") and configuration:
                    command=["lpstat","-p",configuration]
                elif shutil.which("lpstat"): command=["lpstat","-d"]
                else: raise RuntimeError("No supported local print command was found")
                subprocess.run(command,capture_output=True,text=True,timeout=15,check=True)
            elif row["type"]=="scanner" and not configuration:
                raise RuntimeError("Scanner configuration is empty")
            return self.update(device_id,status="ready",statusMessage=f"Available on {platform.system()}")
        except Exception as error:
            return self.update(device_id,status="error",statusMessage=str(error)[:500])

    def server_rows(self) -> list[dict]:
        return [{key:row.get(key) for key in
                 ("id","name","type","capabilities","status","statusMessage")}
                for row in self.list()]
