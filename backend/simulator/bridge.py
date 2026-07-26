from __future__ import annotations

import json
import os
from urllib import request

from .state import ScenarioState


class DashboardBridge:
    """Optional local bridge; all failures remain visible to the simulator operator."""

    def __init__(self):
        self.base_url = os.environ.get("SIM_DASHBOARD_URL", "http://127.0.0.1:8000/api/v1")
        self.run_id = os.environ.get("SIM_RUN_ID", "local-simulator")
        self.token = os.environ.get("SIMULATOR_BRIDGE_TOKEN", "")

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def reconcile(self, state: ScenarioState) -> dict:
        return self._request("PUT", f"/simulator/runs/{self.run_id}/manifest", self._manifest(state))

    def sync(self) -> dict:
        return self._request("POST", f"/simulator/runs/{self.run_id}/sync", {})

    def _manifest(self, state: ScenarioState) -> dict:
        snapshot = state.snapshot()
        return {
            "scenario_id": snapshot["scenario"]["id"],
            "revision": snapshot["revision"],
            "scenario": snapshot["scenario"],
        }

    def _request(self, method: str, path: str, payload: dict) -> dict:
        if not self.enabled:
            return {"enabled": False, "detail": "SIMULATOR_BRIDGE_TOKEN is not configured"}
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
