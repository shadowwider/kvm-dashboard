from __future__ import annotations

import copy
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
from .profile_catalog import get_profile, normalize_catalog_profile_id
from .profiles import scenario_runtime_fixture
from .runtime_paths import RuntimePathError
from .runtime_state import (
    ActionResult,
    Availability,
    PatchResult,
    RuntimeAction,
    RuntimeDeviceSpec,
    RuntimeState,
    StateEvent,
)


@dataclass(frozen=True, slots=True)
class TransitionResult:
    revision: int
    device_id: str | None
    changed_paths: tuple[str, ...] = ()
    committed_values: tuple[tuple[str, Any], ...] = ()
    idempotent: bool = False
    trap: TrapRequest | None = None
    event: dict[str, Any] | None = None
    lifecycle_intent: str | None = None


class ScenarioState:
    """The only public, scenario-aware facade over the L3 state core."""

    def __init__(self, definition: ScenarioDefinition):
        if not isinstance(definition, ScenarioDefinition):
            raise ValueError("definition must be a validated ScenarioDefinition")
        dumped = definition.model_dump(mode="json")
        specs: list[RuntimeDeviceSpec] = []
        for device in dumped["devices"]:
            profile = get_profile(device["profile"])
            fixture = scenario_runtime_fixture(device)
            specs.append(
                RuntimeDeviceSpec(
                    device_id=device["id"],
                    profile=profile,
                    fixture=fixture,
                    host=device["host"],
                    snmp_port=device["snmp_port"],
                )
            )

        self._definition = definition.model_copy(deep=True)
        self._baseline = copy.deepcopy(dumped)
        self._state = copy.deepcopy(dumped)
        self._runtime = RuntimeState(specs)
        self._lock = threading.RLock()

    @property
    def definition(self) -> ScenarioDefinition:
        with self._lock:
            return self._definition.model_copy(deep=True)

    @property
    def revision(self) -> int:
        with self._lock:
            return self._runtime.revision

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            renderable = self._runtime.renderable_snapshot()
            scenario = self._merged_scenario(renderable)
            paused, powered_off = self._availability_sets(renderable)
            return copy.deepcopy(
                {
                    "scenario": scenario,
                    "topology": scenario,
                    "revision": renderable["revision"],
                    "paused_devices": paused,
                    "powered_off_devices": powered_off,
                    "events": [
                        self._event_dict(event)
                        for event in self._runtime.events()
                    ],
                }
            )

    def renderable_snapshot(
        self, device_id: str | None = None
    ) -> dict[str, Any]:
        """Return device structure plus complete canonical state for L4."""

        with self._lock:
            if device_id is not None:
                self._device_ref(device_id)
                runtime = self._runtime.renderable_snapshot(device_id)
                structure = copy.deepcopy(self._device_ref(device_id))
                self._merge_runtime_device(structure, runtime["device"])
                return {
                    "schema_version": runtime["schema_version"],
                    "revision": runtime["revision"],
                    "device": structure,
                }
            runtime = self._runtime.renderable_snapshot()
            return {
                "schema_version": runtime["schema_version"],
                "revision": runtime["revision"],
                "scenario": self._merged_scenario(runtime),
            }

    def device(self, device_id: str) -> dict[str, Any]:
        with self._lock:
            self._device_ref(device_id)
            runtime = self._runtime.renderable_snapshot(device_id)["device"]
            result = copy.deepcopy(self._device_ref(device_id))
            self._merge_runtime_device(result, runtime)
            return result

    def profile_state(self, device_id: str) -> dict[str, Any]:
        with self._lock:
            self._device_ref(device_id)
            runtime = self._runtime.renderable_snapshot(device_id)["device"]
            return copy.deepcopy(self._canonical_profile_state(runtime))

    def is_paused(self, device_id: str) -> bool:
        with self._lock:
            availability = self._runtime.read(
                device_id, "runtime.availability"
            )
            return availability != Availability.CONNECTED.value

    def pause_device(
        self, device_id: str, paused: bool
    ) -> TransitionResult:
        if not isinstance(paused, bool):
            raise ValueError("paused must be a strict boolean")
        action = (
            RuntimeDeviceAction.PAUSE
            if paused
            else RuntimeDeviceAction.RESTORE
        )
        return self._device_action(action, device_id=device_id, emit_trap=False)

    def device_action(
        self, device_id: str, action: RuntimeDeviceAction
    ) -> TransitionResult:
        return self._device_action(action, device_id=device_id, emit_trap=True)

    def _device_action(
        self,
        action: RuntimeDeviceAction,
        *,
        device_id: str,
        emit_trap: bool,
    ) -> TransitionResult:
        if not isinstance(action, RuntimeDeviceAction):
            raise ValueError(f"unknown device action {action!r}")
        normalized = {
            RuntimeDeviceAction.DISCONNECT: RuntimeAction.DISCONNECT,
            RuntimeDeviceAction.PAUSE: RuntimeAction.DISCONNECT,
            RuntimeDeviceAction.POWER_OFF: RuntimeAction.POWER_OFF,
            RuntimeDeviceAction.RESTORE: RuntimeAction.RESTORE,
        }[action]
        with self._lock:
            device = self._device_ref(device_id)
            result = self._runtime.action(device_id, normalized)
            idempotent = result.event is None
            trap = None
            if emit_trap and not idempotent:
                if action in (
                    RuntimeDeviceAction.DISCONNECT,
                    RuntimeDeviceAction.PAUSE,
                ):
                    level, suffix = 3, "disconnected"
                elif action == RuntimeDeviceAction.POWER_OFF:
                    level, suffix = 2, "powered off"
                else:
                    level, suffix = 5, "restored"
                trap = TrapRequest(
                    level=level,
                    message=f"Device {device['name']} {suffix}",
                    state_backed=True,
                    device_id=device_id,
                )
            lifecycle_intent = {
                RuntimeDeviceAction.POWER_OFF: "stop_agent",
                RuntimeDeviceAction.RESTORE: "ensure_agent_running",
            }.get(action)
            return self._transition(
                result,
                action_name="device_action",
                payload={
                    "action": action.value,
                    "availability": result.availability,
                },
                trap=trap,
                lifecycle_intent=lifecycle_intent,
            )

    def patch_device_state(
        self, device_id: str, patch: RuntimeStatePatch
    ) -> TransitionResult:
        with self._lock:
            self._device_ref(device_id)
            changes = [(item.path, item.value) for item in patch.patches]
            result = self._runtime.patch(device_id, changes)
            trap = None
            if patch.emit_trap and result.event is not None:
                device = self._device_ref(device_id)
                trap = TrapRequest(
                    level=5,
                    message=f"Runtime state changed on {device['name']}",
                    state_backed=True,
                    device_id=device_id,
                )
            return self._transition(
                result,
                action_name="runtime_state_patch",
                payload={
                    "patches": [
                        {"path": path, "value": value}
                        for path, value in changes
                    ]
                },
                trap=trap,
            )

    def patch_endpoint(
        self,
        device_id: str,
        endpoint_id: str,
        patch: EndpointStatePatch,
    ) -> TransitionResult:
        with self._lock:
            current = self._device_ref(device_id)
            working = copy.deepcopy(current)
            endpoint = next(
                (
                    item
                    for item in working["endpoints"]
                    if item["id"] == endpoint_id
                ),
                None,
            )
            if endpoint is None:
                raise KeyError(endpoint_id)
            values = patch.model_dump(mode="json", exclude_none=True)
            changed = [
                f"endpoints[{endpoint_id}].{field}"
                for field, value in values.items()
                if endpoint[field] != value
                or type(endpoint[field]) is not type(value)
            ]
            if not changed:
                return TransitionResult(
                    revision=self._runtime.revision,
                    device_id=device_id,
                    changed_paths=(),
                    idempotent=True,
                )
            endpoint.update(values)
            ScenarioDefinition.model_validate(
                {**self._state, "devices": [
                    working if item["id"] == device_id else item
                    for item in self._state["devices"]
                ]}
            )

            core_changes: list[tuple[str, Any]] = []
            canonical = normalize_catalog_profile_id(working["profile"])
            table_id = {
                ("ccdm_matrix", "cpu"): "target_module_table",
                ("ccdm_matrix", "con"): "user_module_table",
            }.get((canonical, endpoint["module_type"]))
            if table_id is not None and "status" in values:
                path = (
                    f"tables.{table_id}[{endpoint['row']}].device_status"
                )
                try:
                    self._runtime.path_registry(device_id).get(path)
                except RuntimePathError:
                    pass
                else:
                    core_changes.append((path, int(values["status"])))

            if core_changes:
                result = self._runtime._patch_with_domain_change(
                    device_id,
                    core_changes,
                    additional_changed_paths=changed,
                    event_kind="endpoint_state",
                )
            else:
                result = self._runtime._record_domain_change(
                    device_id,
                    kind="endpoint_state",
                    changed_paths=changed,
                )
            self._replace_device(device_id, working)

            trap = None
            if "status" in values:
                status = OnlineState(values["status"])
                trap = TrapRequest(
                    level=3 if status == OnlineState.OFFLINE else 5,
                    message=self._endpoint_message(working, endpoint, status),
                    state_backed=True,
                    device_id=device_id,
                )
            return self._transition(
                result,
                action_name="endpoint_state",
                payload={"endpoint_id": endpoint_id, **values},
                trap=trap,
            )

    def patch_route(
        self, device_id: str, route_id: str, patch: RouteStatePatch
    ) -> TransitionResult:
        with self._lock:
            current = self._device_ref(device_id)
            working = copy.deepcopy(current)
            route = next(
                (item for item in working["routes"] if item["id"] == route_id),
                None,
            )
            if route is None:
                raise KeyError(route_id)
            values = patch.model_dump(mode="json")
            path = f"routes[{route_id}].state"
            if route["state"] == values["state"]:
                return TransitionResult(
                    revision=self._runtime.revision,
                    device_id=device_id,
                    changed_paths=(),
                    idempotent=True,
                )
            route.update(values)
            ScenarioDefinition.model_validate(
                {**self._state, "devices": [
                    working if item["id"] == device_id else item
                    for item in self._state["devices"]
                ]}
            )
            result = self._runtime._record_domain_change(
                device_id,
                kind="route_state",
                changed_paths=(path,),
            )
            self._replace_device(device_id, working)
            return self._transition(
                result,
                action_name="route_state",
                payload={"route_id": route_id, **values},
            )

    def reset(self) -> TransitionResult:
        with self._lock:
            scenario_paths = self._scenario_reset_paths()
            result = self._runtime._reset_all_with_domain_change(
                additional_changed_paths=scenario_paths
            )
            if result.event is not None:
                self._state = copy.deepcopy(self._baseline)
            return self._transition(
                result,
                action_name="reset",
                payload={},
            )

    def _device_ref(self, device_id: str) -> dict[str, Any]:
        for device in self._state["devices"]:
            if device["id"] == device_id:
                return device
        raise KeyError(device_id)

    def _replace_device(
        self, device_id: str, replacement: dict[str, Any]
    ) -> None:
        for index, device in enumerate(self._state["devices"]):
            if device["id"] == device_id:
                self._state["devices"][index] = replacement
                return
        raise KeyError(device_id)

    def _merged_scenario(self, runtime: dict[str, Any]) -> dict[str, Any]:
        scenario = copy.deepcopy(self._state)
        for device in scenario["devices"]:
            self._merge_runtime_device(
                device, runtime["devices"][device["id"]]
            )
        return scenario

    @classmethod
    def _merge_runtime_device(
        cls, device: dict[str, Any], runtime: dict[str, Any]
    ) -> None:
        device["profile_state"] = cls._canonical_profile_state(runtime)
        device["availability"] = runtime["availability"]

    @staticmethod
    def _canonical_profile_state(runtime: dict[str, Any]) -> dict[str, Any]:
        return {
            "scalars": copy.deepcopy(runtime["scalars"]),
            "tables": {
                table_id: {
                    row_key: copy.deepcopy(row["values"])
                    for row_key, row in rows.items()
                }
                for table_id, rows in runtime["tables"].items()
            },
        }

    @staticmethod
    def _availability_sets(
        runtime: dict[str, Any],
    ) -> tuple[list[str], list[str]]:
        paused: list[str] = []
        powered_off: list[str] = []
        for device_id, device in runtime["devices"].items():
            if device["availability"] != Availability.CONNECTED.value:
                paused.append(device_id)
            if device["availability"] == Availability.POWERED_OFF.value:
                powered_off.append(device_id)
        return sorted(paused), sorted(powered_off)

    def _scenario_reset_paths(self) -> tuple[str, ...]:
        changed: list[str] = []
        baseline_devices = {
            device["id"]: device for device in self._baseline["devices"]
        }
        for device in self._state["devices"]:
            device_id = device["id"]
            baseline = baseline_devices[device_id]
            baseline_endpoints = {
                endpoint["id"]: endpoint
                for endpoint in baseline["endpoints"]
            }
            for endpoint in device["endpoints"]:
                expected = baseline_endpoints[endpoint["id"]]
                for field in (
                    "status",
                    "display_name",
                    "video_connected",
                    "display_connected",
                    "frozen",
                ):
                    if endpoint[field] != expected[field] or type(
                        endpoint[field]
                    ) is not type(expected[field]):
                        changed.append(
                            f"devices[{device_id}]."
                            f"endpoints[{endpoint['id']}].{field}"
                        )
            baseline_routes = {
                route["id"]: route for route in baseline["routes"]
            }
            for route in device["routes"]:
                if route["state"] != baseline_routes[route["id"]]["state"]:
                    changed.append(
                        f"devices[{device_id}].routes[{route['id']}].state"
                    )
        return tuple(changed)

    @staticmethod
    def _event_dict(
        event: StateEvent,
        *,
        action_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = event.to_dict()
        result["action"] = action_name or event.kind
        result["payload"] = copy.deepcopy(payload or {})
        return result

    @classmethod
    def _transition(
        cls,
        result: PatchResult | ActionResult,
        *,
        action_name: str,
        payload: dict[str, Any],
        trap: TrapRequest | None = None,
        lifecycle_intent: str | None = None,
    ) -> TransitionResult:
        event = (
            cls._event_dict(
                result.event,
                action_name=action_name,
                payload=payload,
            )
            if result.event is not None
            else None
        )
        return TransitionResult(
            revision=result.revision,
            device_id=result.device_id,
            changed_paths=result.changed_paths,
            committed_values=result.committed_values,
            idempotent=result.event is None,
            trap=trap,
            event=event,
            lifecycle_intent=lifecycle_intent,
        )

    @staticmethod
    def _endpoint_message(
        device: dict[str, Any],
        endpoint: dict[str, Any],
        status: OnlineState,
    ) -> str:
        del device
        prefix = "CPU" if endpoint["module_type"] == "cpu" else "CON"
        action = (
            "went offline"
            if status == OnlineState.OFFLINE
            else "came online"
        )
        return f"{prefix} module {endpoint['id']} {action}"
