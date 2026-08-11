from __future__ import annotations

import hashlib
import json
import os
import shutil
import shlex
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from .client import Bay300Client
from .config import work_path
from .devices import DeviceRegistry
from .render import write_html,write_pdf


class DeviceAgent:
    def __init__(self, authorization: dict, registry: DeviceRegistry | None=None):
        self.authorization=authorization
        self.registry=registry or DeviceRegistry()
        self.root=work_path()
        self.client=Bay300Client(authorization["server"],authorization["token"])
        self.database=self.root/"agent.sqlite3"
        self.wake=threading.Event();self.stop_event=threading.Event()
        self._initialize()

    def _initialize(self) -> None:
        for name in ("Pending","Printed","Failed"):(self.root/name).mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.database) as db:
            db.execute("""create table if not exists jobs(
                job_id text primary key, document_sha256 text not null, status text not null,
                output_file text, updated_at text not null default current_timestamp)""")

    def sync(self) -> None:self.client.sync_devices(self.registry.server_rows())

    def poll_now(self) -> None:self.wake.set()

    def run_once(self) -> bool:
        self.sync()
        for device in self.registry.list():
            if device.get("status")!="ready" or "bill_print" not in device.get("capabilities",[]):continue
            job=self.client.claim(device["id"])
            if job:self._handle(job,device);return True
        return False

    def _handle(self,job: dict,device: dict) -> None:
        job_id=job["jobId"]
        if job.get("jobType")!="bill_print":
            self.client.failed(job_id,f"Unsupported device job type: {job.get('jobType')!r}");return
        pending_html=None;pending_pdf=None
        try:
            if self.client.task_state(job_id).get("cancellationRequested"):return
            raw=job["documentJson"];actual=hashlib.sha256(raw.encode()).hexdigest()
            if actual!=job["documentSha256"]:raise RuntimeError("Bill checksum mismatch; refusing to print")
            document=json.loads(raw)
            if document.get("schemaVersion")!="bay300.bill-print.v1":
                raise RuntimeError(f"Unsupported schema {document.get('schemaVersion')!r}")
            if self._status(job_id)=="completed":
                self.client.spooled(job_id,"already-completed-locally");return
            safe="".join(c if c.isalnum() or c in "-_" else "-" for c in document["billNumber"])
            filename=f"{safe}-v{job['documentVersion']}-copy{job['copyNumber']}-{job_id}.html"
            pending_html=write_html(document,job["copyNumber"],self.root/"Pending"/filename)
            pending_pdf=write_pdf(document,job["copyNumber"],pending_html.with_suffix(".pdf"))
            self._record(job_id,actual,"rendered",str(pending_pdf))
            if self.client.task_state(job_id).get("cancellationRequested"):
                for path in (pending_html,pending_pdf):
                    if path.exists():path.unlink()
                return
            self._print(pending_pdf,device)
            printed_pdf=self.root/"Printed"/pending_pdf.name
            printed_html=self.root/"Printed"/pending_html.name
            shutil.move(str(pending_pdf),printed_pdf);shutil.move(str(pending_html),printed_html)
            self._record(job_id,actual,"completed",str(printed_pdf))
            self.client.spooled(job_id,str(printed_pdf))
        except Exception as error:
            for pending in (pending_pdf,pending_html):
                if pending and pending.exists():shutil.move(str(pending),self.root/"Failed"/pending.name)
            self._record(job_id,job.get("documentSha256","unknown"),"failed",str(error))
            try:self.client.failed(job_id,str(error))
            except Exception:pass
            raise

    def run_forever(self) -> None:
        backoff=2
        while not self.stop_event.is_set():
            try:
                worked=self.run_once();backoff=2 if worked else min(60,max(2,backoff*2))
            except Exception as error:
                print(f"Device task failed: {error}",flush=True);backoff=min(60,max(2,backoff*2))
            self.wake.wait(backoff);self.wake.clear()

    def stop(self) -> None:self.stop_event.set();self.wake.set()

    def _print(self,path: Path,device: dict) -> None:
        configuration=device.get("configuration","")
        if os.name=="nt":
            os.startfile(path,"print");return
        command=f"lp -d {shlex.quote(configuration)} {{file}}" if configuration else "lp {file}"
        parts=shlex.split(command);args=[part.replace("{file}",str(path)) for part in parts]
        subprocess.run(args,check=True,timeout=90)

    def _status(self,job_id: str) -> str|None:
        with sqlite3.connect(self.database) as db:
            row=db.execute("select status from jobs where job_id=?",(job_id,)).fetchone()
            return row[0] if row else None

    def _record(self,job_id: str,digest: str,status: str,output: str) -> None:
        with sqlite3.connect(self.database) as db:
            db.execute("""insert into jobs(job_id,document_sha256,status,output_file)
                values(?,?,?,?) on conflict(job_id) do update set
                document_sha256=excluded.document_sha256,status=excluded.status,
                output_file=excluded.output_file,updated_at=current_timestamp""",
                (job_id,digest,status,output))


PrintAgent=DeviceAgent
