from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox,simpledialog,ttk

from .agent import DeviceAgent
from .devices import (CARD_READER_INTEGRATION_MESSAGE,CARD_READER_PROCESSOR_CATALOG,
                      DEVICE_TYPE_CATALOG,DeviceRegistry)
from .local_devices import normalize_local_configuration


class DevicesAdmin:
    def __init__(self,authorization: dict):
        self.authorization=authorization;self.registry=DeviceRegistry()
        self.agent=DeviceAgent(authorization,self.registry)
        self.root=tk.Tk();self.root.title(f"{authorization['storeName']} Devices Admin")
        self.status=tk.StringVar(value="Starting…")
        self.tree=ttk.Treeview(self.root,columns=("name","type","processor","status","message"),show="headings")
        for key,label,width in (("name","Name",180),("type","Type",130),
            ("processor","Processor",170),("status","Status",280),("message","Status detail",300)):
            self.tree.heading(key,text=label);self.tree.column(key,width=width)
        self.tree.pack(fill="both",expand=True,padx=12,pady=12)
        bar=ttk.Frame(self.root);bar.pack(fill="x",padx=12)
        for label,command in (("Add new device",self.add),("Remove device",self.remove),
            ("Edit / Config device",self.edit),("Block / Unblock device",self.block),
            ("Check device status",self.check),("Poll server now",self.poll_now)):
            ttk.Button(bar,text=label,command=command).pack(side="left",padx=3)
        ttk.Label(self.root,textvariable=self.status).pack(anchor="w",padx=12,pady=8)
        self.root.protocol("WM_DELETE_WINDOW",self.close);self.refresh()
        self.worker=threading.Thread(target=self.agent.run_forever,daemon=True);self.worker.start()
        self.root.after(3000,self.periodic)

    def selected(self):
        values=self.tree.selection();return values[0] if values else None

    def refresh(self):
        selected=self.selected();self.tree.delete(*self.tree.get_children())
        for row in self.registry.list():
            status=(CARD_READER_INTEGRATION_MESSAGE if row["type"]=="card_reader"
                    and row["status"]=="integration_required" else row["status"])
            self.tree.insert("", "end",iid=row["id"],values=(row["name"],row["type"],
                row.get("processorName",""),status,row.get("statusMessage","")))
        if selected and self.tree.exists(selected):self.tree.selection_set(selected)

    def ask_type(self,current="bill_printer"):
        current_name=next((name for name,(value,_) in DEVICE_TYPE_CATALOG.items()
                           if value==current),"printer")
        value=simpledialog.askstring("Device type",
            f"Type: {', '.join(DEVICE_TYPE_CATALOG)}",initialvalue=current_name,
            parent=self.root)
        if value not in DEVICE_TYPE_CATALOG:
            messagebox.showerror("Invalid type","Choose a listed device type.");return None
        return DEVICE_TYPE_CATALOG[value][0]

    def ask_processor(self,current="helcim_smart_terminal",current_name=""):
        current_short=next((name for name,(value,_) in CARD_READER_PROCESSOR_CATALOG.items()
                            if value==current),"helcm")
        value=simpledialog.askstring("Card reader processor",
            f"Processor: {', '.join(CARD_READER_PROCESSOR_CATALOG)}",
            initialvalue=current_short,
            parent=self.root)
        if value not in CARD_READER_PROCESSOR_CATALOG:
            messagebox.showerror("Invalid processor","Choose a listed Card reader processor.")
            return None
        name=""
        if value=="other":
            name=simpledialog.askstring("Processor name","Processor name",
                initialvalue=current_name,parent=self.root) or ""
            if not name.strip():
                messagebox.showerror("Processor name","Enter the Card reader processor name.")
                return None
        return CARD_READER_PROCESSOR_CATALOG[value][0],name

    def add(self):
        name=simpledialog.askstring("Add device","Device name",parent=self.root)
        if not name:return
        device_type=self.ask_type()
        if not device_type:return
        processor=("","")
        if device_type=="card_reader":
            processor=self.ask_processor()
            if not processor:return
            config=""
        else:
            config=simpledialog.askstring("Local configuration","Printer name, scanner identifier, or local configuration",parent=self.root) or ""
        try:
            selector="" if device_type=="card_reader" else config or name
            configuration=normalize_local_configuration(selector,device_type)
            self.registry.add(name,device_type,configuration,*processor);self.changed()
        except ValueError as error:messagebox.showerror("Local device selection",str(error))

    def remove(self):
        item=self.selected()
        if not item:return
        if messagebox.askyesno("Remove device","Remove this local device? Server task history is retained."):
            self.registry.remove(item);self.changed()

    def edit(self):
        item=self.selected()
        if not item:return
        row=next(value for value in self.registry.list() if value["id"]==item)
        name=simpledialog.askstring("Edit device","Device name",initialvalue=row["name"],parent=self.root)
        if not name:return
        device_type=self.ask_type(row["type"])
        if not device_type:return
        processor=("","")
        if device_type=="card_reader":
            processor=self.ask_processor(row.get("processor","helcim_smart_terminal"),
                                         row.get("processorName",""))
            if not processor:return
            config=""
        else:
            config=simpledialog.askstring("Local configuration","Printer name, scanner identifier, or local configuration",initialvalue=row.get("configuration",""),parent=self.root)
        try:
            configuration=normalize_local_configuration(config or "",device_type)
            self.registry.update(item,name=name,type=device_type,configuration=configuration,
                                 processor=processor[0],processorName=processor[1]);self.changed()
        except ValueError as error:messagebox.showerror("Local device selection",str(error))

    def block(self):
        item=self.selected()
        if not item:return
        row=next(value for value in self.registry.list() if value["id"]==item)
        self.registry.block(item,row["status"]!="blocked");self.changed()

    def check(self):
        item=self.selected()
        if not item:return
        result=self.registry.check(item);self.changed()
        messagebox.showinfo("Device status",result.get("statusMessage",result["status"]))

    def changed(self):
        self.refresh();self.agent.poll_now();self.status.set("Local configuration changed; server poll requested.")

    def poll_now(self):self.agent.poll_now();self.status.set("Polling cycle reset and requested immediately.")

    def periodic(self):
        self.refresh();self.status.set("Background polling active · exponential idle backoff up to 60 seconds")
        self.root.after(5000,self.periodic)

    def close(self):self.agent.stop();self.root.destroy()
    def run(self):self.root.mainloop()


def run_gui(authorization: dict):DevicesAdmin(authorization).run()
