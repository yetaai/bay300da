from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess


def _run(command: list[str]) -> str:
    try:
        return subprocess.run(
            command,capture_output=True,text=True,timeout=20,check=False,
        ).stdout.strip()
    except (OSError,subprocess.SubprocessError):
        return ""


def _cups_printers() -> list[dict]:
    if not shutil.which("lpstat"):return []
    default_output=_run(["lpstat","-d"])
    default=default_output.partition(":")[2].strip() if ":" in default_output else ""
    rows=[]
    for line in _run(["lpstat","-p"]).splitlines():
        match=re.match(r"^printer\s+(\S+)\s+(.+)$",line)
        if not match:continue
        name,detail=match.groups()
        rows.append({"kind":"printer","name":name,"identifier":name,"source":"CUPS",
                     "default":name==default,"detail":detail})
    return rows


def _sane_scanners() -> list[dict]:
    if not shutil.which("scanimage"):return []
    rows=[]
    for line in _run(["scanimage","-L"]).splitlines():
        match=re.match(r"^device [`'](.+?)['] is (.+)$",line.strip())
        if match:
            identifier,name=match.groups()
            rows.append({"kind":"scanner","name":name,"identifier":identifier,
                         "source":"SANE","default":False,"detail":""})
    return rows


def _windows_devices() -> list[dict]:
    if not shutil.which("powershell") and not shutil.which("powershell.exe"):return []
    shell=shutil.which("powershell") or shutil.which("powershell.exe")
    script="""
$items = @()
Get-Printer -ErrorAction SilentlyContinue | ForEach-Object {
  $items += [PSCustomObject]@{kind='printer';name=$_.Name;identifier=$_.Name;source='Windows Print';default=$false;detail=$_.PrinterStatus.ToString()}
}
Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object {$_.Class -in @('Image','Camera')} | ForEach-Object {
  $items += [PSCustomObject]@{kind='scanner';name=$_.FriendlyName;identifier=$_.InstanceId;source='Windows PnP';default=$false;detail=$_.Status}
}
$items | ConvertTo-Json -Compress
"""
    raw=_run([shell,"-NoProfile","-Command",script])
    if not raw:return []
    try:value=json.loads(raw)
    except json.JSONDecodeError:return []
    return value if isinstance(value,list) else [value]


def discover_local_devices(system: str | None=None) -> list[dict]:
    system=system or platform.system()
    if system=="Windows":return _windows_devices()
    return _cups_printers()+_sane_scanners()


def normalize_local_configuration(selector: str,device_type: str,
                                  rows: list[dict] | None=None) -> str:
    """Expand one case-insensitive local-device prefix to its complete identifier."""
    clean=selector.strip()
    if not clean:return ""
    kind="scanner" if device_type=="scanner" else (
        "printer" if device_type in {"bill_printer","check_printer","printer"} else None)
    if kind is None:return clean
    local_rows=discover_local_devices() if rows is None else rows
    folded=clean.casefold()
    matches=[row for row in local_rows if row.get("kind")==kind and any(
        str(row.get(key) or "").casefold().startswith(folded) for key in ("name","identifier")
    )]
    if len(matches)==1:return str(matches[0]["identifier"])
    if len(matches)>1:
        names=", ".join(sorted(str(row.get("name") or row.get("identifier")) for row in matches))
        raise ValueError(f"Local {kind} prefix '{clean}' is ambiguous: {names}")
    return clean


def print_local_devices(rows: list[dict],json_output: bool=False) -> None:
    if json_output:
        print(json.dumps(rows,sort_keys=True));return
    if not rows:
        print("No local printers or document scanners were discovered.")
        print("Discovery requires CUPS lpstat for printers and SANE scanimage for scanners on Linux/macOS.")
        return
    print("KIND  NAME  IDENTIFIER  SOURCE  DEFAULT  DETAIL")
    for row in rows:
        print(f"{row['kind']}  {row['name']}  {row['identifier']}  {row['source']}  "
              f"{'yes' if row.get('default') else 'no'}  {row.get('detail','')}")
    print("Discovery does not add or authorize a Bay300 device.")
    print("Currently only bill_printer tasks are implemented.")
