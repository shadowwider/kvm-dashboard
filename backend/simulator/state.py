from __future__ import annotations

import copy
import re
import threading
from dataclasses import dataclass
from typing import Any

from .models import (
    EndpointStatePatch,
    OnlineState,
    RouteStatePatch,
    RuntimeDeviceAction,
    RuntimeStatePatch,
    ScenarioDefinition,
    TrapRequest,
)
from .profiles import mutable_field_index


@dataclass
class TransitionResult:
    revision: int
    device_id: str
    trap: TrapRequest | None = None
    event: dict | None = None


_PATH_RE = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\[(?P<key>[A-Za-z0-9_.:-]+)\])?")


class ScenarioState:
    """Thread-safe, topology-aware source of truth for one loaded simulation."""

    def __init__(self, definition: ScenarioDefinition):
        self.definition = definition
        self._baseline = definition.model_dump(mode="json")
        self._state = definition.model_dump(mode="json")
        self._revision = 1
        self._lock = threading.RLock()
        self._paused_devices: set[str] = set()
        self._powered_off_devices: set[str] = set()
        self._events: list[dict] = []

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy({
                "scenario": self._state,
                "topology": self._state,
                "revision": self._revision,
                "paused_devices": sorted(self._paused_devices),
                "powered_off_devices": sorted(self._powered_off_devices),
                "events": self._events[-100:],
            })

    def device(self, device_id: str) -> dict:
        with self._lock:
            for device in self._state["devices"]:
                if device["id"] == device_id:
                    return device
        raise KeyError(device_id)

    def profile_state(self, device_id: str) -> dict:
        with self._lock:
            device = self.device(device_id)
            return copy.deepcopy(device.setdefault("profile_state", {}))

    def is_paused(self, device_id: str) -> bool:
        with self._lock:
            return device_id in self._paused_devices or device_id in self._powered_off_devices

    def pause_device(self, device_id: str, paused: bool) -> TransitionResult:
        self.device(device_id)
        with self._lock:
            if paused:
                self._paused_devices.add(device_id)
            else:
                self._paused_devices.discard(device_id)
            return self._record(device_id, "device_reachability", {"paused": paused})

    def device_action(self, device_id: str, action: RuntimeDeviceAction) -> TransitionResult:
        device = self.device(device_id)
        trap = None
        with self._lock:
            if action in (RuntimeDeviceAction.DISCONNECT, RuntimeDeviceAction.PAUSE):
                self._paused_devices.add(device_id)
                payload = {"action": action.value, "paused": True}
                trap = TrapRequest(level=3, message=f"Device {device['name']} disconnected", state_backed=True, device_id=device_id)
            elif action == RuntimeDeviceAction.POWER_OFF:
                self._paused_devices.add(device_id)
                self._powered_off_devices.add(device_id)
                scalars = device.setdefault("profile_state", {}).setdefault("scalars", {})
                scalars.update({"main_power": 0, "mainPower": 0, "power_state": 0})
                payload = {"action": action.value, "paused": True, "powered_off": True}
                trap = TrapRequest(level=2, message=f"Device {device['name']} powered off", state_backed=True, device_id=device_id)
            elif action == RuntimeDeviceAction.RESTORE:
                self._paused_devices.discard(device_id)
                self._powered_off_devices.discard(device_id)
                scalars = device.setdefault("profile_state", {}).setdefault("scalars", {})
                scalars.update({"main_power": 1, "mainPower": 1, "power_state": 1})
                payload = {"action": action.value, "paused": False, "powered_off": False}
                trap = TrapRequest(level=5, message=f"Device {device['name']} restored", state_backed=True, device_id=device_id)
            else:
                raise ValueError(action)
            return self._record(device_id, "device_action", payload, trap)

    def patch_device_state(self, device_id: str, patch: RuntimeStatePatch) -> TransitionResult:
        with self._lock:
            device = self.device(device_id)
            working = copy.deepcopy(device)
            allowed = mutable_field_index(working["profile"])
            applied = []
            for item in patch.patches:
                if item.path.startswith(("scalars.", "tables.")) and item.path not in allowed:
                    raise ValueError(f"Unsupported or read-only runtime field path: {item.path}")
                self._apply_path(working, item.path, item.value)
                applied.append({"path": item.path, "value": item.value})
            device.clear()
            device.update(working)
            trap = None
            if patch.emit_trap:
                trap = TrapRequest(level=5, message=f"Runtime state changed on {device['name']}", state_backed=True, device_id=device_id)
            return self._record(device_id, "runtime_state_patch", {"patches": applied}, trap)

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
                trap = TrapRequest(level=3 if values["status"] == OnlineState.OFFLINE else 5, message=message, state_backed=True, device_id=device_id)
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
            self._powered_off_devices.clear()
            self._revision += 1
            self._events.append({"revision": self._revision, "action": "reset"})

    def _apply_path(self, device: dict, path: str, value: Any) -> None:
        parts = []
        for raw in path.split("."):
            match = _PATH_RE.fullmatch(raw)
            if not match:
                raise ValueError(f"Invalid runtime field path: {path}")
            parts.append((match.group("name"), match.group("key")))
        root, root_key = parts[0]
        if root == "endpoints":
            collection_parts = [(root, root_key), *parts[1:]] if root_key is not None else parts[1:]
            self._patch_collection(device["endpoints"], "id", collection_parts, value, path)
        elif root == "ports":
            collection_parts = [(root, root_key), *parts[1:]] if root_key is not None else parts[1:]
            self._patch_collection(device["ports"], "index", collection_parts, value, path)
        elif root in {"scalars", "tables"}:
            if root_key is not None:
                raise ValueError("Profile state root path segment must not be indexed")
            current = device.setdefault("profile_state", {}).setdefault(root, {})
            self._set_nested(current, parts[1:], value, path)
        else:
            raise ValueError(f"Unsupported runtime path root: {root}")

    def _patch_collection(self, collection: list[dict], key_field: str, parts: list[tuple[str, str | None]], value: Any, path: str) -> None:
        if not parts or parts[0][1] is None:
            raise ValueError(f"Indexed collection path required: {path}")
        _, key = parts[0]
        item = next((row for row in collection if str(row[key_field]) == key), None)
        if not item:
            raise KeyError(key)
        self._set_nested(item, parts[1:], value, path)

    def _set_nested(self, current: dict, parts: list[tuple[str, str | None]], value: Any, path: str) -> None:
        if not parts:
            raise ValueError(f"Missing terminal field in path: {path}")
        for name, key in parts[:-1]:
            if key is None:
                current = current.setdefault(name, {})
            else:
                current = current.setdefault(name, {}).setdefault(key, {})
        name, key = parts[-1]
        if key is None:
            current[name] = value
        else:
            current.setdefault(name, {})[key] = value

    def _record(self, device_id: str, action: str, payload: dict, trap: TrapRequest | None = None) -> TransitionResult:
        self._revision += 1
        event = {"revision": self._revision, "device_id": device_id, "action": action, "payload": payload}
        self._events.append(event)
        return TransitionResult(revision=self._revision, device_id=device_id, trap=trap, event=copy.deepcopy(event))

    @staticmethod
    def _endpoint_message(device: dict, endpoint: dict, status: int) -> str:
        prefix = "CPU" if endpoint["module_type"] == "cpu" else "CON"
        action = "went offline" if status == OnlineState.OFFLINE else "came online"
        return f"{prefix} module {endpoint['id']} {action}"
