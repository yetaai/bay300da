from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import uuid

from .config import load_devices,save_devices


CAPABILITIES={
    "bill_printer":["bill_print"],"check_printer":[],
    "printer":[],"scanner":[],"card_reader":[],"other":[],
}
DEVICE_TYPE_CATALOG={
    "printer":("bill_printer","Printer"),
    "scanner":("scanner","Document scanner"),
    "cardReader":("card_reader","Card reader"),
}
CARD_READER_PROCESSOR_CATALOG={
    "helcm":("helcim_smart_terminal","Helcim Smart Terminal"),
    "squar":("square_terminal","Square Terminal"),
    "paypl":("paypal_point_of_sale","PayPal Point of Sale"),
    "other":("other","Other processor"),
}
CARD_READER_PROCESSORS={
    value:full_name for value,full_name in CARD_READER_PROCESSOR_CATALOG.values()
}
CARD_READER_INTEGRATION_MESSAGE=(
    "Card reader integration is available through Bay300 Support."
)


def processor_details(device_type: str,processor: str="",
                      processor_name: str="") -> tuple[str,str]:
    if device_type!="card_reader":
        if processor.strip() or processor_name.strip():
            raise ValueError("Processor is only used with type cardReader")
        return "",""
    code=processor.strip()
    if code not in CARD_READER_PROCESSORS:
        raise ValueError("Choose a supported Card reader processor")
    custom=processor_name.strip()
    if code=="other":
        if not custom:raise ValueError("Processor name is required when processor is other")
        if len(custom)>200:raise ValueError("Processor name must be 200 characters or fewer")
        return code,custom
    if custom:raise ValueError("Processor name is only used when processor is other")
    return code,CARD_READER_PROCESSORS[code]


class DeviceRegistry:
    def __init__(self):self.lock=threading.RLock()
    def list(self) -> list[dict]:
        with self.lock:
            return [{**row,"capabilities":CAPABILITIES.get(row.get("type"),[])}
                    for row in load_devices()]

    def save(self,devices: list[dict]) -> None:
        with self.lock:save_devices(devices)

    def add(self,name: str,device_type: str,configuration: str="",processor: str="",
            processor_name: str="") -> dict:
        with self.lock:
            clean_name=name.strip()
            if not clean_name:raise ValueError("Device name is required")
            if device_type not in CAPABILITIES:raise ValueError(f"Unsupported device type: {device_type}")
            processor_code,display_processor=processor_details(
                device_type,processor,processor_name
            )
            devices=self.list()
            row={"id":uuid.uuid4().hex,"name":clean_name,"type":device_type,
                 "capabilities":CAPABILITIES[device_type],"status":"ready",
                 "configuration":configuration.strip(),"statusMessage":"Not checked yet"}
            if device_type=="card_reader":row.update({
                "processor":processor_code,"processorName":display_processor,
                "status":"integration_required",
                "statusMessage":CARD_READER_INTEGRATION_MESSAGE,
            })
            devices.append(row);self.save(devices);return row

    def resolve(self,selector: str) -> dict:
        """Resolve an exact ID or one unambiguous case-insensitive device-name prefix."""
        clean_selector=selector.strip()
        if not clean_selector:raise ValueError("Device name or ID is required")
        devices=self.list()
        exact_id=next((row for row in devices if row["id"]==clean_selector),None)
        if exact_id:return exact_id
        folded=clean_selector.casefold()
        matches=[row for row in devices if row["name"].casefold().startswith(folded)]
        if len(matches)==1:return matches[0]
        if not matches:raise ValueError(f"No local device matches '{clean_selector}'")
        names=", ".join(sorted(row["name"] for row in matches))
        raise ValueError(f"Device name prefix '{clean_selector}' is ambiguous: {names}")

    def update(self,device_id: str,**changes) -> dict:
        with self.lock:
            if "name" in changes:
                changes["name"]=changes["name"].strip()
                if not changes["name"]:raise ValueError("Device name is required")
            if "type" in changes and changes["type"] not in CAPABILITIES:
                raise ValueError(f"Unsupported device type: {changes['type']}")
            devices=self.list();match=None
            for row in devices:
                if row["id"]==device_id:
                    next_type=changes.get("type",row.get("type"))
                    next_processor=changes.get("processor",row.get("processor",""))
                    next_processor_name=(changes.get("processorName","")
                        if "processor" in changes else changes.get(
                            "processorName",row.get("processorName","")
                        ))
                    processor_code,display_processor=processor_details(
                        next_type,next_processor,next_processor_name
                    )
                    row.update({key:value for key,value in changes.items() if value is not None})
                    row["capabilities"]=CAPABILITIES[next_type]
                    if next_type=="card_reader":
                        blocked=changes.get("status",row.get("status"))=="blocked"
                        row.update({
                            "processor":processor_code,"processorName":display_processor,
                            "status":"blocked" if blocked else "integration_required",
                            "statusMessage":"Blocked locally" if blocked
                                else CARD_READER_INTEGRATION_MESSAGE,
                        })
                    else:
                        row.pop("processor",None);row.pop("processorName",None)
                    match=row
            if not match:raise KeyError(device_id)
            self.save(devices);return match

    def remove(self,device_id: str) -> None:
        with self.lock:
            current=self.list();devices=[row for row in current if row["id"]!=device_id]
            if len(devices)==len(current):raise KeyError(device_id)
            self.save(devices)

    def block(self,device_id: str,blocked: bool=True) -> dict:
        row=next((item for item in self.list() if item["id"]==device_id),None)
        if not row:raise KeyError(device_id)
        if row["type"]=="card_reader" and not blocked:
            return self.update(device_id,status="integration_required",
                               statusMessage=CARD_READER_INTEGRATION_MESSAGE)
        return self.update(device_id,status="blocked" if blocked else "ready",
                           statusMessage="Blocked locally" if blocked else "Ready")

    def check(self,device_id: str) -> dict:
        row=next((item for item in self.list() if item["id"]==device_id),None)
        if not row:raise KeyError(device_id)
        if row["status"]=="blocked":return row
        if row["type"]=="card_reader":
            return self.update(device_id,status="integration_required",
                               statusMessage=CARD_READER_INTEGRATION_MESSAGE)
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
                 ("id","name","type","processor","processorName","capabilities",
                  "status","statusMessage")}
                for row in self.list()]
