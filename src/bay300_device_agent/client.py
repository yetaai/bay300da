from __future__ import annotations

import json
import urllib.error
import urllib.request


class ApiError(RuntimeError):
    pass


class Bay300Client:
    def __init__(self, base_url: str, token: str | None = None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def post(self, path: str, body: dict | None = None, agent_auth: bool = True) -> dict:
        headers = {"Content-Type": "application/json", "User-Agent": "bay300-device-agent/0.2"}
        if agent_auth:
            if not self.token:
                raise ApiError("Device credential is not configured")
            headers["X-Device-Credential"] = self.token
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body or {}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise ApiError(f"Bay300 API returned HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise ApiError(f"Cannot reach Bay300: {error.reason}") from error

    def request_authorization(self, contact: str, agent_name: str) -> dict:
        return self.post("/api/devices/authorization-requests", {
            "contact": contact, "agentName": agent_name,
        }, agent_auth=False)

    def poll_authorization(self, request_id: str, polling_token: str) -> dict:
        original=self.token
        try:
            self.token=None
            headers = {"Content-Type": "application/json", "User-Agent": "bay300-device-agent/0.2",
                       "X-Device-Poll-Token": polling_token}
            request = urllib.request.Request(
                self.base_url + f"/api/devices/authorization-requests/{request_id}/poll",
                data=b"{}", headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail=error.read().decode("utf-8",errors="replace")
            raise ApiError(f"Bay300 API returned HTTP {error.code}: {detail}") from error
        finally:
            self.token=original

    def sync_devices(self,devices: list[dict]) -> dict:
        return self.post("/api/device-agent/devices/sync",{"devices":devices})

    def claim(self,device_id: str) -> dict:
        return self.post("/api/devices/jobs/claim",{"deviceId":device_id}).get("job") or {}

    def task_state(self,job_id: str) -> dict:
        return self.post(f"/api/device-agent/jobs/{job_id}/state")

    def spooled(self, job_id: str, output_file: str) -> dict:
        return self.post(f"/api/devices/jobs/{job_id}/completed", {"outputFile": output_file})

    def failed(self, job_id: str, message: str) -> dict:
        return self.post(f"/api/devices/jobs/{job_id}/failed", {"message": message})
