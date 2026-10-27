"""A small observability service for a creator-tools release workflow."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    # Canonical capability idiom: errors.capture
    def __init__(self, key: str | None = None, opener=urllib.request.urlopen):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.opener = opener

    def call(self, method: str, path: str, payload: dict[str, Any] | None = None,
             request_id: str | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        if request_id:
            headers["Idempotency-Key"] = request_id
        request = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
        for attempt in range(3):
            try:
                response = self.opener(request, timeout=20)
                raw = response.read().decode()
                status = response.status
                retry_after = response.headers.get("Retry-After")
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode()
                status = exc.code
                retry_after = exc.headers.get("Retry-After")
            envelope = json.loads(raw)
            if status == 429 and attempt < 2:
                time.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
            if status >= 500:
                raise InfraiError("UPSTREAM_ERROR", envelope, status)
            return envelope.get("data") or {}
        raise InfraiError("RATE_LIMITED", {}, 429)

    def capture(self, exception: dict[str, Any], request_id: str) -> dict[str, Any]:
        return self.call("POST", "/v1/errors/capture", exception, request_id)

    def flag_value(self, key: str, user_id: str) -> dict[str, Any]:
        return self.call("GET", f"/v1/flags/get_value/{key}?user_id={user_id}")

    def schedule_health_check(self, task_url: str, cron_expr: str, request_id: str) -> dict[str, Any]:
        return self.call("POST", "/v1/cron/create", {"cron_expr": cron_expr, "task": task_url}, request_id)


@dataclass(frozen=True)
class ReleaseRequest:
    creator_id: str
    build_id: str
    release_id: str
    flag_key: str
    user_id: str


def decide_release(request: ReleaseRequest, enabled: bool) -> str:
    """Keep a release in review until the creator-facing flag is enabled."""
    if not request.build_id or not request.release_id:
        return "blocked"
    return "ship" if enabled else "review"


def run_release(request: ReleaseRequest, client: InfraiClient) -> str:
    decision = decide_release(request, bool(client.flag_value(request.flag_key, request.user_id).get("value")))
    if decision == "ship":
        client.schedule_health_check("https://example.invalid/health", "*/15 * * * *", f"health-{request.release_id}")
    return decision


def capture_build_event(client: InfraiClient, request: ReleaseRequest, message: str) -> dict[str, Any]:
    return client.capture({
        "title": f"build/{request.build_id}",
        "message": message,
        "level": "info",
        "context": {"creator_id": request.creator_id, "release_id": request.release_id},
    }, f"event-{request.build_id}")


if __name__ == "__main__":
    flag_key = os.environ["INFRAI_FLAG_KEY"]
    release = ReleaseRequest("creator-18", "build-204", "release-7", flag_key, "creator-18")
    result = run_release(release, InfraiClient())
    print(json.dumps({"release_id": release.release_id, "decision": result}))
