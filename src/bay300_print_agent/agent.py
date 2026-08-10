from __future__ import annotations

import hashlib
import json
import shutil
import shlex
import sqlite3
import subprocess
import time
from pathlib import Path

from .client import Bay300Client
from .render import write_html,write_pdf


class PrintAgent:
    def __init__(self, config: dict):
        self.config = config
        self.root = Path(config["work_directory"]).expanduser()
        self.client = Bay300Client(config["base_url"], config["device_token"])
        self.database = self.root / "agent.sqlite3"
        self._initialize()

    def _initialize(self) -> None:
        for name in ("Pending", "Printed", "Failed"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database) as db:
            db.execute("""create table if not exists jobs(
                job_id text primary key, document_sha256 text not null, status text not null,
                output_file text, updated_at text not null default current_timestamp)""")

    def run_once(self) -> bool:
        job = self.client.claim()
        if not job:
            return False
        job_id = job["jobId"]
        pending_html=None;pending_pdf=None
        try:
            raw = job["documentJson"]
            actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if actual != job["documentSha256"]:
                raise RuntimeError("Bill checksum mismatch; refusing to print")
            document = json.loads(raw)
            if document.get("schemaVersion") != "bay300.bill-print.v1":
                raise RuntimeError(f"Unsupported schema {document.get('schemaVersion')!r}")
            prior = self._status(job_id)
            if prior == "spooled":
                self.client.spooled(job_id, "already-spooled-locally")
                return True
            safe_number = "".join(c if c.isalnum() or c in "-_" else "-" for c in document["billNumber"])
            filename = f"{safe_number}-v{job['documentVersion']}-copy{job['copyNumber']}-{job_id}.html"
            pending_html = write_html(document, job["copyNumber"], self.root / "Pending" / filename)
            pending_pdf = write_pdf(document,job["copyNumber"],pending_html.with_suffix(".pdf"))
            self._record(job_id, actual, "rendered", str(pending_pdf))
            self._print(pending_pdf)
            printed_pdf = self.root / "Printed" / pending_pdf.name
            printed_html = self.root / "Printed" / pending_html.name
            shutil.move(str(pending_pdf), printed_pdf);shutil.move(str(pending_html),printed_html)
            self._record(job_id, actual, "spooled", str(printed_pdf))
            self.client.spooled(job_id, str(printed_pdf))
            return True
        except Exception as error:
            for pending in (pending_pdf,pending_html):
                if pending and pending.exists():shutil.move(str(pending),self.root/"Failed"/pending.name)
            self._record(job_id, job.get("documentSha256", "unknown"), "failed", str(error))
            try:
                self.client.failed(job_id, str(error))
            except Exception:
                pass
            raise

    def run_forever(self) -> None:
        interval = max(2, int(self.config.get("poll_seconds", 5)))
        while True:
            try:
                worked = self.run_once()
                if not worked:
                    time.sleep(interval)
            except KeyboardInterrupt:
                return
            except Exception as error:
                print(f"Print job failed: {error}", flush=True)
                time.sleep(interval)

    def _print(self, path: Path) -> None:
        command = self.config.get("print_command", "lp {file}")
        if not command:
            return
        parts=shlex.split(command)
        args = [part.replace("{file}", str(path)) for part in parts]
        if all("{file}" not in part for part in parts):
            args.append(str(path))
        subprocess.run(args, check=True, timeout=90)

    def _status(self, job_id: str) -> str | None:
        with sqlite3.connect(self.database) as db:
            row = db.execute("select status from jobs where job_id=?", (job_id,)).fetchone()
            return row[0] if row else None

    def _record(self, job_id: str, digest: str, status: str, output: str) -> None:
        with sqlite3.connect(self.database) as db:
            db.execute("""insert into jobs(job_id,document_sha256,status,output_file)
                values(?,?,?,?) on conflict(job_id) do update set
                document_sha256=excluded.document_sha256,status=excluded.status,
                output_file=excluded.output_file,updated_at=current_timestamp""",
                (job_id, digest, status, output))
