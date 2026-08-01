from __future__ import annotations

import json
import os
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from urllib import request
from urllib.parse import quote, urlsplit, urlunsplit

from .state import ScenarioState


class DashboardBridge:
    """Optional local bridge; all failures remain visible to the simulator operator."""

    def __init__(self):
        self.base_url = os.environ.get("SIM_DASHBOARD_URL", "http://127.0.0.1:8000/api/v1")
        self.run_id = os.environ.get("SIM_RUN_ID", "local-simulator")
        self.requested_session_id = os.environ.get("SIM_SESSION_ID", uuid.uuid4().hex)
        self.session_started_at = int(time.time_ns())
        self.session_id: str | None = None
        self.session_epoch: str | None = None
        self.token = os.environ.get("SIMULATOR_BRIDGE_TOKEN", "")
        self._reconcile_lock = threading.Lock()
        self._last_result: dict | None = None
        self._last_attempt_at: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _remember(self, result: dict) -> dict:
        self._last_result = deepcopy(result)
        self._last_attempt_at = datetime.now(timezone.utc).isoformat()
        return result

    @staticmethod
    def _safe_url(value: str) -> str:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return "<invalid-url>"
        hostname = parsed.hostname
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        try:
            port = f":{parsed.port}" if parsed.port is not None else ""
        except ValueError:
            return "<invalid-url>"
        query = "<redacted>" if parsed.query else ""
        return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, query, ""))

    def _public_result(self, result: dict | None) -> dict | None:
        if not isinstance(result, dict):
            return None
        public = {
            key: result[key]
            for key in ("enabled", "ok", "error_type")
            if key in result
        }
        if "detail" in result:
            detail = str(result["detail"])
            public["detail"] = detail.replace(
                self.base_url,
                self._safe_url(self.base_url),
            )
        response = result.get("response")
        if isinstance(response, dict):
            bindings = response.get("bindings")
            public["response"] = {
                key: response[key]
                for key in ("run_id", "revision")
                if key in response
            }
            if isinstance(bindings, list):
                public["response"]["binding_count"] = len(bindings)
        return public

    def status(self) -> dict:
        """Return redacted, read-only diagnostics for the L0 status endpoint."""
        with self._reconcile_lock:
            last_result = deepcopy(self._last_result)
            response = last_result.get("response", {}) if isinstance(last_result, dict) else {}
            bindings = response.get("bindings", []) if isinstance(response, dict) else []
            public_result = self._public_result(last_result)
            detail = public_result.get("detail") if isinstance(public_result, dict) else None
            return {
                "enabled": self.enabled,
                "dashboard_url": self._safe_url(self.base_url),
                "run_id": self.run_id,
                "session_established": bool(self.session_id and self.session_epoch),
                "last_attempt_at": self._last_attempt_at,
                "last_reconcile": public_result,
                "binding_count": len(bindings) if isinstance(bindings, list) else 0,
                "detail": detail,
            }

    def start_session(self) -> dict:
        if not self.enabled:
            return self._remember({"enabled": False, "detail": "SIMULATOR_BRIDGE_TOKEN is not configured"})
        result = self._request("POST", f"/simulator/runs/{self.run_id}/sessions", {
            "session_id": self.requested_session_id,
            "session_started_at": self.session_started_at,
        })
        if result.get("ok") and result["response"].get("session_id") == self.requested_session_id:
            self.session_id = self.requested_session_id
            self.session_epoch = result["response"]["session_epoch"]
            return result
        if result.get("ok"):
            return self._remember({
                "enabled": True,
                "ok": False,
                "detail": "a newer simulator session already owns this run ID",
                "response": result["response"],
            })
        return result

    def reconcile(self, state: ScenarioState) -> dict:
        if self.enabled and not self.session_id:
            session = self.start_session()
            if not session.get("ok"):
                return session
        return self._request("PUT", f"/simulator/runs/{self.run_id}/manifest", self._manifest(state))

    def sync(self) -> dict:
        return self._request("POST", f"/simulator/runs/{self.run_id}/sync", {})

    def heartbeat(self) -> dict:
        if not self.enabled:
            return self._remember({"enabled": False, "detail": "SIMULATOR_BRIDGE_TOKEN is not configured"})
        if not self.session_id or not self.session_epoch:
            return self._remember({"enabled": True, "ok": False, "detail": "bridge session is not established"})
        return self._request(
            "POST",
            f"/simulator/runs/{quote(self.run_id, safe='')}/sessions/{quote(self.session_id, safe='')}/heartbeat",
            {"session_epoch": self.session_epoch},
        )

    def cleanup(self) -> dict:
        """Release only the run owned by this exact bridge session.

        A simulator process must never use the Dashboard admin API (or an
        unscoped run delete) during shutdown: a delayed old process could
        otherwise erase a newer process's manifest.  The Dashboard endpoint
        checks both session id and epoch before it removes any resources.
        """
        if not self.enabled:
            return self._remember({"enabled": False, "detail": "SIMULATOR_BRIDGE_TOKEN is not configured"})
        if not self.session_id or not self.session_epoch:
            return self._remember({"enabled": True, "ok": True, "detail": "no bridge session to clean"})
        result = self._request(
            "DELETE",
            f"/simulator/runs/{quote(self.run_id, safe='')}/sessions/{quote(self.session_id, safe='')}",
            {"session_epoch": self.session_epoch},
        )
        if result.get("ok"):
            self.session_id = None
            self.session_epoch = None
        return result

    def _manifest(self, state: ScenarioState) -> dict:
        snapshot = state.snapshot()
        scenario = snapshot["scenario"]
        for device in scenario.get("devices", []):
            device.setdefault("host", "127.0.0.1")
        return {
            "scenario_id": scenario["id"],
            "session_id": self.session_id,
            "session_epoch": self.session_epoch,
            "revision": snapshot["revision"],
            "scenario": scenario,
        }

    def _request(self, method: str, path: str, payload: dict) -> dict:
        if not self.enabled:
            return self._remember({"enabled": False, "detail": "SIMULATOR_BRIDGE_TOKEN is not configured"})
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
                    raw_response = response.read()
                    return self._remember({
                        "enabled": True,
                        "ok": True,
                        "response": json.loads(raw_response) if raw_response else {},
                    })
            except Exception as exc:
                return self._remember({
                    "enabled": True,
                    "ok": False,
                    "detail": str(exc),
                    "error_type": type(exc).__name__,
                })
