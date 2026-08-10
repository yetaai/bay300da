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
        headers = {"Content-Type": "application/json", "User-Agent": "bay300-print-agent/0.1"}
        if agent_auth:
            if not self.token:
                raise ApiError("Print-agent token is not configured")
            headers["X-Print-Agent-Token"] = self.token
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

    def enroll(self, code: str, device_name: str) -> dict:
        return self.post("/api/print-agents/enroll", {
            "enrollmentCode": code,
            "deviceName": device_name,
        }, agent_auth=False)

    def claim(self) -> dict:
        return self.post("/api/print-agents/jobs/claim").get("job") or {}

    def spooled(self, job_id: str, output_file: str) -> dict:
        return self.post(f"/api/print-agents/jobs/{job_id}/spooled", {"outputFile": output_file})

    def failed(self, job_id: str, message: str) -> dict:
        return self.post(f"/api/print-agents/jobs/{job_id}/failed", {"message": message})
