from __future__ import annotations

import json
import os
import threading
import time
import uuid
from urllib import request

from .state import ScenarioState


class DashboardBridge:
    """Optional local bridge; all failures remain visible to the simulator operator."""

    def __init__(self):
        self.base_url = os.environ.get("SIM_DASHBOARD_URL", "http://127.0.0.1:8000/api/v1")
        self.run_id = os.environ.get("SIM_RUN_ID", "local-simulator")
        self.requested_session_id = os.environ.get("SIM_SESSION_ID", uuid.uuid4().hex)
        self.session_started_at = int(time.time_ns())
        self.session_id: str | None = None
        self.token = os.environ.get("SIMULATOR_BRIDGE_TOKEN", "")
        self._reconcile_lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def start_session(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "detail": "SIMULATOR_BRIDGE_TOKEN is not configured"}
        result = self._request("POST", f"/simulator/runs/{self.run_id}/sessions", {
            "session_id": self.requested_session_id,
            "session_started_at": self.session_started_at,
        })
        if result.get("ok") and result["response"].get("session_id") == self.requested_session_id:
            self.session_id = self.requested_session_id
            return result
        if result.get("ok"):
            return {
                "enabled": True,
                "ok": False,
                "detail": "a newer simulator session already owns this run ID",
                "response": result["response"],
            }
        return result

    def reconcile(self, state: ScenarioState) -> dict:
        if self.enabled and not self.session_id:
            session = self.start_session()
            if not session.get("ok"):
                return session
        return self._request("PUT", f"/simulator/runs/{self.run_id}/manifest", self._manifest(state))

    def sync(self) -> dict:
        return self._request("POST", f"/simulator/runs/{self.run_id}/sync", {})

    def _manifest(self, state: ScenarioState) -> dict:
        snapshot = state.snapshot()
        return {
            "scenario_id": snapshot["scenario"]["id"],
            "session_id": self.session_id,
            "revision": snapshot["revision"],
            "scenario": snapshot["scenario"],
        }

    def _request(self, method: str, path: str, payload: dict) -> dict:
        if not self.enabled:
            return {"enabled": False, "detail": "SIMULATOR_BRIDGE_TOKEN is not configured"}
        # Serializing a process's outbound PUTs preserves revision order end-to-end.
        with self._reconcile_lock:
            body = json.dumps(payload).encode("utf-8")
            req = request.Request(
                f"{self.base_url}{path}",
                data=body,
                method=method,
                headers={
                    "Content-Type": "application/json",
                    "X-Simulator-Token": self.token,
                },
            )
            try:
                with request.urlopen(req, timeout=10) as response:
                    return {"enabled": True, "ok": True, "response": json.loads(response.read())}
            except Exception as exc:
                return {"enabled": True, "ok": False, "detail": str(exc)}
