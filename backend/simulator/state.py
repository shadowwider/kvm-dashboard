from __future__ import annotations

import copy
import threading
from dataclasses import dataclass

from .models import EndpointStatePatch, OnlineState, RouteStatePatch, ScenarioDefinition, TrapRequest


@dataclass
class TransitionResult:
    revision: int
    device_id: str
    trap: TrapRequest | None = None


class ScenarioState:
    """Thread-safe, deterministic source of truth for one loaded simulation scenario."""

    def __init__(self, definition: ScenarioDefinition):
        self.definition = definition
        self._baseline = definition.model_dump(mode="json")
        self._state = definition.model_dump(mode="json")
        self._revision = 1
        self._lock = threading.RLock()
        self._paused_devices: set[str] = set()
        self._events: list[dict] = []

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy({
                "scenario": self._state,
                "revision": self._revision,
                "paused_devices": sorted(self._paused_devices),
                "events": self._events[-50:],
            })

    def device(self, device_id: str) -> dict:
        with self._lock:
            for device in self._state["devices"]:
                if device["id"] == device_id:
                    return device
        raise KeyError(device_id)

    def is_paused(self, device_id: str) -> bool:
        with self._lock:
            return device_id in self._paused_devices

    def pause_device(self, device_id: str, paused: bool) -> TransitionResult:
        self.device(device_id)
        with self._lock:
            if paused:
                self._paused_devices.add(device_id)
            else:
                self._paused_devices.discard(device_id)
            return self._record(device_id, "device_reachability", {"paused": paused})

    def patch_endpoint(self, device_id: str, endpoint_id: str, patch: EndpointStatePatch) -> TransitionResult:
        with self._lock:
            device = self.device(device_id)
            endpoint = next((item for item in device["endpoints"] if item["id"] == endpoint_id), None)
            if not endpoint:
                raise KeyError(endpoint_id)
            values = patch.model_dump(exclude_none=True)
            endpoint.update(values)
            trap = None
            if "status" in values:
                message = self._endpoint_message(device, endpoint, values["status"])
                trap = TrapRequest(level=3 if values["status"] == OnlineState.OFFLINE else 5, message=message, state_backed=True)
            return self._record(device_id, "endpoint_state", {"endpoint_id": endpoint_id, **values}, trap)

    def patch_route(self, device_id: str, route_id: str, patch: RouteStatePatch) -> TransitionResult:
        with self._lock:
            device = self.device(device_id)
            route = next((item for item in device["routes"] if item["id"] == route_id), None)
            if not route:
                raise KeyError(route_id)
            route.update(patch.model_dump())
            return self._record(device_id, "route_state", {"route_id": route_id, **patch.model_dump()})

    def reset(self) -> None:
        with self._lock:
            self._state = copy.deepcopy(self._baseline)
            self._paused_devices.clear()
            self._revision += 1
            self._events.append({"revision": self._revision, "action": "reset"})

    def _record(self, device_id: str, action: str, payload: dict, trap: TrapRequest | None = None) -> TransitionResult:
        self._revision += 1
        self._events.append({"revision": self._revision, "device_id": device_id, "action": action, "payload": payload})
        return TransitionResult(revision=self._revision, device_id=device_id, trap=trap)

    @staticmethod
    def _endpoint_message(device: dict, endpoint: dict, status: int) -> str:
        prefix = "CPU" if endpoint["module_type"] == "cpu" else "CON"
        action = "went offline" if status == OnlineState.OFFLINE else "came online"
        return f"{prefix} module {endpoint['id']} {action}"
