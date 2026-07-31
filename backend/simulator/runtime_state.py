"""L3 typed, transactional, scenario-level runtime state.

``RuntimeState`` is deliberately the single commit point for all devices in a
loaded scenario: one lock, one revision, and one event stream.  Internal
per-device records do not expose a revision or commit method, preventing a
second visible truth when the existing ``ScenarioState`` is migrated later.

This layer consumes L2 Profile/fixture contracts only.  It does not render OIDs
or ASN.1, start an SNMP Agent, send Trap packets, persist a topology, or expose
REST/WebSocket/UI behavior.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .profile_fixture import FixtureSpec, validate_fixture_schema
from .profile_model import ColumnDef, ProfileDef, ScalarDef
from .runtime_paths import (
    PathSpec,
    RuntimePathError,
    RuntimePathRegistry,
    RuntimeStateError,
    RuntimeTransitionError,
    RuntimeValueError,
    format_row_key,
    parse_runtime_path,
    path_spec_for_leaf,
    validate_runtime_value,
)


INITIAL_REVISION = 1
EVENT_HISTORY_LIMIT = 100
RUNTIME_STATE_SCHEMA_VERSION = 1


class Availability(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    POWERED_OFF = "powered_off"


class RuntimeAction(str, Enum):
    DISCONNECT = "disconnect"
    POWER_OFF = "power_off"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class RuntimeDeviceSpec:
    """Construction input for one explicit L2 fixture instance."""

    device_id: str
    profile: ProfileDef
    fixture: FixtureSpec | Mapping[str, Any]
    host: str | None = None
    snmp_port: int | None = None


@dataclass(frozen=True, slots=True)
class StateEvent:
    event_id: str
    revision: int
    timestamp: str
    device_id: str | None
    kind: str
    changed_paths: tuple[str, ...] = ()
    action: str | None = None
    previous_availability: str | None = None
    availability: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PatchResult:
    revision: int
    device_id: str | None
    changed_paths: tuple[str, ...]
    committed_values: tuple[tuple[str, Any], ...] = ()
    event: StateEvent | None = None

    @property
    def changed(self) -> bool:
        return self.event is not None


@dataclass(frozen=True, slots=True)
class ActionResult:
    revision: int
    device_id: str
    action: str
    previous_availability: str
    availability: str
    changed_paths: tuple[str, ...]
    committed_values: tuple[tuple[str, Any], ...] = ()
    event: StateEvent | None = None

    @property
    def changed(self) -> bool:
        return self.event is not None


@dataclass(slots=True)
class _DeviceRecord:
    identity: dict[str, Any]
    availability: Availability
    scalars: dict[str, Any]
    tables: dict[str, dict[str, dict[str, Any]]]
    baseline_scalars: dict[str, Any]
    baseline_tables: dict[str, dict[str, dict[str, Any]]]
    profile: ProfileDef
    fixture: FixtureSpec
    registry: RuntimePathRegistry
    leaf_definitions: dict[str, ScalarDef | ColumnDef] = field(default_factory=dict)


_ACTION_TRANSITIONS: dict[
    Availability, dict[RuntimeAction, Availability]
] = {
    Availability.CONNECTED: {
        RuntimeAction.DISCONNECT: Availability.DISCONNECTED,
        RuntimeAction.POWER_OFF: Availability.POWERED_OFF,
        RuntimeAction.RESTORE: Availability.CONNECTED,
    },
    Availability.DISCONNECTED: {
        RuntimeAction.DISCONNECT: Availability.DISCONNECTED,
        RuntimeAction.POWER_OFF: Availability.POWERED_OFF,
        RuntimeAction.RESTORE: Availability.CONNECTED,
    },
    Availability.POWERED_OFF: {
        RuntimeAction.POWER_OFF: Availability.POWERED_OFF,
        RuntimeAction.RESTORE: Availability.CONNECTED,
    },
}


class RuntimeState:
    """The only L3 revision/event commit point for a loaded scenario."""

    def __init__(self, devices: Iterable[RuntimeDeviceSpec]):
        records: dict[str, _DeviceRecord] = {}
        for spec in tuple(devices):
            self._validate_device_spec(spec)
            if spec.device_id in records:
                raise RuntimeValueError(
                    f"duplicate runtime device_id {spec.device_id!r}"
                )
            records[spec.device_id] = self._build_device_record(spec)
        if not records:
            raise RuntimeValueError("RuntimeState requires at least one device")

        self._devices = records
        self._revision = INITIAL_REVISION
        self._events: list[StateEvent] = []
        self._lock = threading.RLock()

    @classmethod
    def single(
        cls,
        device_id: str,
        profile: ProfileDef,
        fixture: FixtureSpec | Mapping[str, Any],
        *,
        host: str | None = None,
        snmp_port: int | None = None,
    ) -> RuntimeState:
        return cls(
            [
                RuntimeDeviceSpec(
                    device_id=device_id,
                    profile=profile,
                    fixture=fixture,
                    host=host,
                    snmp_port=snmp_port,
                )
            ]
        )

    @staticmethod
    def _validate_device_spec(spec: RuntimeDeviceSpec) -> None:
        if not isinstance(spec, RuntimeDeviceSpec):
            raise RuntimeValueError("devices must contain RuntimeDeviceSpec values")
        if (
            not isinstance(spec.device_id, str)
            or not spec.device_id.strip()
            or len(spec.device_id) > 128
        ):
            raise RuntimeValueError("device_id must be a non-empty string <= 128 chars")
        if not isinstance(spec.profile, ProfileDef):
            raise RuntimeValueError("profile must be an immutable L2 ProfileDef")
        if spec.host is not None and (
            not isinstance(spec.host, str) or not spec.host.strip()
        ):
            raise RuntimeValueError("host must be a non-empty string when provided")
        if spec.snmp_port is not None and (
            not isinstance(spec.snmp_port, int)
            or isinstance(spec.snmp_port, bool)
            or not 1 <= spec.snmp_port <= 65535
        ):
            raise RuntimeValueError("snmp_port must be a strict integer in 1..65535")

    @staticmethod
    def _build_device_record(spec: RuntimeDeviceSpec) -> _DeviceRecord:
        try:
            fixture = validate_fixture_schema(spec.profile, spec.fixture)
        except Exception as exc:
            raise RuntimeValueError(
                f"invalid L2 fixture for {spec.device_id!r}: {exc}"
            ) from exc

        identity = {
            "device_id": spec.device_id,
            "profile_id": spec.profile.profile_id,
            "profile_version": spec.profile.profile_version,
            "host": spec.host,
            "snmp_port": spec.snmp_port,
            "system_oid": spec.profile.sys_object_id,
        }
        scalars: dict[str, Any] = {}
        tables: dict[str, dict[str, dict[str, Any]]] = {}
        path_specs: list[PathSpec] = [
            PathSpec(
                path=f"identity.{field_id}",
                kind="identity",
                field_id=field_id,
                runtime_writable=False,
                vendor_snmp_writable=None,
                syntax=None,
            )
            for field_id in identity
        ]
        path_specs.append(
            PathSpec(
                path="runtime.availability",
                kind="availability",
                field_id="availability",
                runtime_writable=False,
                vendor_snmp_writable=None,
                syntax=None,
            )
        )
        leaf_definitions: dict[str, ScalarDef | ColumnDef] = {}

        scalar_values = dict(fixture.scalar_values)
        for definition in spec.profile.scalars:
            field_id = definition.canonical_field
            if field_id not in scalar_values:
                continue
            value = scalar_values[field_id]
            validate_runtime_value(definition, value)
            path = f"scalars.{field_id}"
            scalars[field_id] = copy.deepcopy(value)
            leaf_definitions[path] = definition
            path_specs.append(
                path_spec_for_leaf(path=path, item=definition, kind="scalar")
            )

        fixture_tables = {
            item.table_id: item for item in fixture.tables
        }
        for table in spec.profile.tables:
            fixture_table = fixture_tables.get(table.canonical_field)
            if fixture_table is None:
                continue
            rows: dict[str, dict[str, Any]] = {}
            ordered_indexes = tuple(
                sorted(table.indexes, key=lambda item: item.position)
            )

            def numeric_index_tuple(fixture_row) -> tuple[int, ...]:
                index_map = fixture_row.index_map
                index_values = tuple(
                    index_map[item.canonical_field] for item in ordered_indexes
                )
                if any(
                    not isinstance(value, int) or isinstance(value, bool)
                    for value in index_values
                ):
                    raise RuntimeValueError(
                        f"{fixture_table.table_id} row indexes must be strict integers"
                    )
                return index_values

            for fixture_row in sorted(
                fixture_table.rows,
                key=numeric_index_tuple,
            ):
                index_values = numeric_index_tuple(fixture_row)
                row_key = format_row_key(index_values)
                if row_key in rows:
                    raise RuntimeValueError(
                        f"duplicate runtime row {fixture_table.table_id}[{row_key}]"
                    )
                for index, value in zip(ordered_indexes, index_values):
                    path_specs.append(
                        PathSpec(
                            path=(
                                f"tables.{fixture_table.table_id}[{row_key}]"
                                f".indexes.{index.canonical_field}"
                            ),
                            kind="index",
                            field_id=index.canonical_field,
                            runtime_writable=False,
                            vendor_snmp_writable=None,
                            syntax=index.syntax,
                            minimum=(
                                index.value_range.minimum
                                if index.value_range is not None
                                else None
                            ),
                            maximum=(
                                index.value_range.maximum
                                if index.value_range is not None
                                else None
                            ),
                            table_id=fixture_table.table_id,
                            row_key=row_key,
                            index_values=index_values,
                            index_position=index.position,
                        )
                    )
                values: dict[str, Any] = {}
                row_values = dict(fixture_row.values)
                for definition in table.columns:
                    field_id = definition.canonical_field
                    if field_id not in row_values:
                        continue
                    value = row_values[field_id]
                    validate_runtime_value(definition, value)
                    path = (
                        f"tables.{fixture_table.table_id}[{row_key}].{field_id}"
                    )
                    values[field_id] = copy.deepcopy(value)
                    leaf_definitions[path] = definition
                    path_specs.append(
                        path_spec_for_leaf(
                            path=path,
                            item=definition,
                            kind="column",
                            table_id=fixture_table.table_id,
                            row_key=row_key,
                            index_values=index_values,
                        )
                    )
                rows[row_key] = {
                    "indexes": index_values,
                    "values": values,
                }
            tables[fixture_table.table_id] = rows

        return _DeviceRecord(
            identity=identity,
            availability=Availability.CONNECTED,
            scalars=scalars,
            tables=tables,
            baseline_scalars=copy.deepcopy(scalars),
            baseline_tables=copy.deepcopy(tables),
            profile=spec.profile,
            fixture=fixture,
            registry=RuntimePathRegistry(path_specs),
            leaf_definitions=leaf_definitions,
        )

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def device_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._devices)

    def events(self) -> tuple[StateEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def path_registry(self, device_id: str) -> RuntimePathRegistry:
        with self._lock:
            # Do not expose the registry instance retained by the mutable
            # device record.  PathSpec is frozen and the registry constructor
            # rebuilds its mapping/tuple containers, so callers can inspect
            # this value without gaining a handle that can corrupt L3 state.
            return RuntimePathRegistry(self._device(device_id).registry)

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            if device_id is not None:
                return copy.deepcopy(
                    {
                        "schema_version": RUNTIME_STATE_SCHEMA_VERSION,
                        "revision": self._revision,
                        "device": self._snapshot_device(self._device(device_id)),
                        "events": [event.to_dict() for event in self._events],
                    }
                )
            return copy.deepcopy(
                {
                    "schema_version": RUNTIME_STATE_SCHEMA_VERSION,
                    "revision": self._revision,
                    "devices": {
                        current_id: self._snapshot_device(record)
                        for current_id, record in self._devices.items()
                    },
                    "events": [event.to_dict() for event in self._events],
                }
            )

    def renderable_snapshot(
        self, device_id: str | None = None
    ) -> dict[str, Any]:
        """Return canonical L4 input without OID/ASN.1 rendering."""

        with self._lock:
            if device_id is not None:
                return copy.deepcopy(
                    {
                        "schema_version": RUNTIME_STATE_SCHEMA_VERSION,
                        "revision": self._revision,
                        "device": self._renderable_device(self._device(device_id)),
                    }
                )
            return copy.deepcopy(
                {
                    "schema_version": RUNTIME_STATE_SCHEMA_VERSION,
                    "revision": self._revision,
                    "devices": {
                        current_id: self._renderable_device(record)
                        for current_id, record in self._devices.items()
                    },
                }
            )

    def read(self, device_id: str, path: str) -> Any:
        with self._lock:
            record = self._device(device_id)
            spec = record.registry.get(path)
            return copy.deepcopy(self._read_unlocked(record, spec))

    def patch(
        self,
        device_id: str,
        changes: Mapping[str, Any] | Sequence[tuple[str, Any]],
    ) -> PatchResult:
        """Validate a complete batch on a working copy, then commit once."""

        return self._patch(
            device_id,
            changes,
            additional_changed_paths=(),
            event_kind="patch",
        )

    def _patch_with_domain_change(
        self,
        device_id: str,
        changes: Mapping[str, Any] | Sequence[tuple[str, Any]],
        *,
        additional_changed_paths: Sequence[str],
        event_kind: str,
    ) -> PatchResult:
        """Scenario-facade adapter; not part of the public L3 patch API."""

        return self._patch(
            device_id,
            changes,
            additional_changed_paths=additional_changed_paths,
            event_kind=event_kind,
        )

    def _patch(
        self,
        device_id: str,
        changes: Mapping[str, Any] | Sequence[tuple[str, Any]],
        *,
        additional_changed_paths: Sequence[str],
        event_kind: str,
    ) -> PatchResult:
        items = self._normalize_changes(changes)
        domain_paths = self._normalize_domain_paths(additional_changed_paths)
        with self._lock:
            record = self._device(device_id)
            working_scalars = copy.deepcopy(record.scalars)
            working_tables = copy.deepcopy(record.tables)
            changed_paths: list[str] = []

            for path, value in items:
                spec = record.registry.get(path)
                if not spec.runtime_writable:
                    raise RuntimePathError(f"runtime path {path!r} is read-only")
                definition = record.leaf_definitions[path]
                validate_runtime_value(definition, value)
                current = self._read_values_unlocked(
                    working_scalars, working_tables, spec
                )
                if current == value and type(current) is type(value):
                    continue
                self._write_values_unlocked(
                    working_scalars, working_tables, spec, value
                )
                changed_paths.append(path)

            committed_paths = self._merge_changed_paths(
                tuple(changed_paths), domain_paths
            )
            if not committed_paths:
                return PatchResult(
                    revision=self._revision,
                    device_id=device_id,
                    changed_paths=(),
                    event=None,
                )

            committed_values = tuple(
                (
                    path,
                    copy.deepcopy(
                        self._read_values_unlocked(
                            working_scalars,
                            working_tables,
                            record.registry.get(path),
                        )
                    ),
                )
                for path in changed_paths
            )
            event = self._prepare_event(
                device_id=device_id,
                kind=event_kind,
                changed_paths=committed_paths,
            )
            record.scalars = working_scalars
            record.tables = working_tables
            self._commit_event(event)
            return PatchResult(
                revision=self._revision,
                device_id=device_id,
                changed_paths=committed_paths,
                committed_values=committed_values,
                event=event,
            )

    def _record_domain_change(
        self,
        device_id: str,
        *,
        kind: str,
        changed_paths: Sequence[str],
    ) -> PatchResult:
        """Commit a typed scenario-only change into the same global event clock."""

        normalized = self._normalize_domain_paths(changed_paths)
        if not normalized:
            raise RuntimePathError("domain change must contain a changed path")
        with self._lock:
            self._device(device_id)
            event = self._prepare_event(
                device_id=device_id,
                kind=kind,
                changed_paths=normalized,
            )
            self._commit_event(event)
            return PatchResult(
                revision=self._revision,
                device_id=device_id,
                changed_paths=normalized,
                event=event,
            )

    def reset(self, device_id: str) -> PatchResult:
        with self._lock:
            record = self._device(device_id)
            changed_paths: list[str] = []
            for path in record.registry.writable_paths:
                spec = record.registry.get(path)
                current = self._read_unlocked(record, spec)
                baseline = self._read_values_unlocked(
                    record.baseline_scalars, record.baseline_tables, spec
                )
                if current != baseline or type(current) is not type(baseline):
                    changed_paths.append(path)
            if record.availability != Availability.CONNECTED:
                changed_paths.append("runtime.availability")

            if not changed_paths:
                return PatchResult(
                    revision=self._revision,
                    device_id=device_id,
                    changed_paths=(),
                    event=None,
                )

            committed_values = tuple(
                (
                    path,
                    (
                        Availability.CONNECTED.value
                        if path == "runtime.availability"
                        else copy.deepcopy(
                            self._read_values_unlocked(
                                record.baseline_scalars,
                                record.baseline_tables,
                                record.registry.get(path),
                            )
                        )
                    ),
                )
                for path in changed_paths
            )
            event = self._prepare_event(
                device_id=device_id,
                kind="reset",
                changed_paths=tuple(changed_paths),
            )
            record.scalars = copy.deepcopy(record.baseline_scalars)
            record.tables = copy.deepcopy(record.baseline_tables)
            record.availability = Availability.CONNECTED
            self._commit_event(event)
            return PatchResult(
                revision=self._revision,
                device_id=device_id,
                changed_paths=tuple(changed_paths),
                committed_values=committed_values,
                event=event,
            )

    def reset_all(self) -> PatchResult:
        """Reset the whole scenario with one revision and one global event."""

        return self._reset_all(additional_changed_paths=())

    def _reset_all_with_domain_change(
        self, *, additional_changed_paths: Sequence[str]
    ) -> PatchResult:
        """Scenario-facade adapter; not part of the public L3 reset API."""

        return self._reset_all(
            additional_changed_paths=additional_changed_paths
        )

    def _reset_all(
        self, *, additional_changed_paths: Sequence[str]
    ) -> PatchResult:
        domain_paths = self._normalize_domain_paths(additional_changed_paths)
        with self._lock:
            changed_paths: list[str] = []
            committed_values: list[tuple[str, Any]] = []
            for device_id, record in self._devices.items():
                prefix = f"devices[{device_id}]."
                for path in record.registry.writable_paths:
                    spec = record.registry.get(path)
                    current = self._read_unlocked(record, spec)
                    baseline = self._read_values_unlocked(
                        record.baseline_scalars, record.baseline_tables, spec
                    )
                    if current != baseline or type(current) is not type(baseline):
                        qualified_path = f"{prefix}{path}"
                        changed_paths.append(qualified_path)
                        committed_values.append(
                            (qualified_path, copy.deepcopy(baseline))
                        )
                if record.availability != Availability.CONNECTED:
                    availability_path = f"{prefix}runtime.availability"
                    changed_paths.append(availability_path)
                    committed_values.append(
                        (
                            availability_path,
                            Availability.CONNECTED.value,
                        )
                    )

            committed_paths = self._merge_changed_paths(
                tuple(changed_paths), domain_paths
            )
            if not committed_paths:
                return PatchResult(
                    revision=self._revision,
                    device_id=None,
                    changed_paths=(),
                    event=None,
                )

            event = self._prepare_event(
                device_id=None,
                kind="reset",
                changed_paths=committed_paths,
            )
            for record in self._devices.values():
                record.scalars = copy.deepcopy(record.baseline_scalars)
                record.tables = copy.deepcopy(record.baseline_tables)
                record.availability = Availability.CONNECTED
            self._commit_event(event)
            return PatchResult(
                revision=self._revision,
                device_id=None,
                changed_paths=committed_paths,
                committed_values=tuple(committed_values),
                event=event,
            )

    def action(
        self, device_id: str, action: RuntimeAction | str
    ) -> ActionResult:
        try:
            normalized = (
                action if isinstance(action, RuntimeAction) else RuntimeAction(action)
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeTransitionError(f"unknown runtime action {action!r}") from exc

        with self._lock:
            record = self._device(device_id)
            previous = record.availability
            target = _ACTION_TRANSITIONS.get(previous, {}).get(normalized)
            if target is None:
                raise RuntimeTransitionError(
                    f"action {normalized.value!r} is not allowed from "
                    f"{previous.value!r}"
                )
            if target == previous:
                return ActionResult(
                    revision=self._revision,
                    device_id=device_id,
                    action=normalized.value,
                    previous_availability=previous.value,
                    availability=target.value,
                    changed_paths=(),
                    committed_values=(),
                    event=None,
                )

            event = self._prepare_event(
                device_id=device_id,
                kind="action",
                changed_paths=("runtime.availability",),
                action=normalized.value,
                previous_availability=previous.value,
                availability=target.value,
            )
            record.availability = target
            self._commit_event(event)
            return ActionResult(
                revision=self._revision,
                device_id=device_id,
                action=normalized.value,
                previous_availability=previous.value,
                availability=target.value,
                changed_paths=("runtime.availability",),
                committed_values=(("runtime.availability", target.value),),
                event=event,
            )

    @staticmethod
    def _normalize_changes(
        changes: Mapping[str, Any] | Sequence[tuple[str, Any]],
    ) -> tuple[tuple[str, Any], ...]:
        if isinstance(changes, Mapping):
            items = tuple(changes.items())
        elif isinstance(changes, Sequence) and not isinstance(
            changes, (str, bytes, bytearray)
        ):
            normalized: list[tuple[str, Any]] = []
            for item in changes:
                if (
                    not isinstance(item, Sequence)
                    or isinstance(item, (str, bytes, bytearray))
                    or len(item) != 2
                ):
                    raise RuntimePathError(
                        "patch sequence items must be (path, value) pairs"
                    )
                normalized.append((item[0], item[1]))
            items = tuple(normalized)
        else:
            raise RuntimePathError("changes must be a mapping or path/value sequence")
        if not items:
            raise RuntimePathError("patch batch must not be empty")
        if len(items) > 100:
            raise RuntimePathError("patch batch must contain at most 100 items")

        seen: set[str] = set()
        for path, _ in items:
            if not isinstance(path, str):
                raise RuntimePathError("patch paths must be strings")
            parse_runtime_path(path)
            if path in seen:
                raise RuntimePathError(f"duplicate patch path {path!r}")
            seen.add(path)
        return items

    @staticmethod
    def _normalize_domain_paths(paths: Sequence[str]) -> tuple[str, ...]:
        if isinstance(paths, (str, bytes, bytearray)) or not isinstance(
            paths, Sequence
        ):
            raise RuntimePathError("changed paths must be a sequence of strings")
        normalized: list[str] = []
        seen: set[str] = set()
        for path in paths:
            if not isinstance(path, str) or not path:
                raise RuntimePathError("changed paths must be non-empty strings")
            if path in seen:
                raise RuntimePathError(f"duplicate changed path {path!r}")
            seen.add(path)
            normalized.append(path)
        return tuple(normalized)

    @staticmethod
    def _merge_changed_paths(
        primary: tuple[str, ...], additional: tuple[str, ...]
    ) -> tuple[str, ...]:
        merged = list(primary)
        seen = set(primary)
        for path in additional:
            if path not in seen:
                merged.append(path)
                seen.add(path)
        return tuple(merged)

    def _device(self, device_id: str) -> _DeviceRecord:
        try:
            return self._devices[device_id]
        except KeyError as exc:
            raise RuntimePathError(f"unknown runtime device {device_id!r}") from exc

    @staticmethod
    def _snapshot_device(record: _DeviceRecord) -> dict[str, Any]:
        return {
            "identity": copy.deepcopy(record.identity),
            "runtime": {"availability": record.availability.value},
            "enabled_optional_groups": sorted(
                record.fixture.enabled_optional_groups
            ),
            "scalars": copy.deepcopy(record.scalars),
            "tables": copy.deepcopy(record.tables),
            "path_registry": record.registry.to_dict(),
        }

    @staticmethod
    def _renderable_device(record: _DeviceRecord) -> dict[str, Any]:
        return {
            "device_id": record.identity["device_id"],
            "profile_id": record.identity["profile_id"],
            "profile_version": record.identity["profile_version"],
            "system_oid": record.identity["system_oid"],
            "availability": record.availability.value,
            "enabled_optional_groups": sorted(
                record.fixture.enabled_optional_groups
            ),
            "scalars": copy.deepcopy(record.scalars),
            "tables": copy.deepcopy(record.tables),
        }

    @staticmethod
    def _read_unlocked(record: _DeviceRecord, spec: PathSpec) -> Any:
        if spec.kind == "identity":
            return record.identity[spec.field_id]
        if spec.kind == "availability":
            return record.availability.value
        if spec.kind == "index":
            if spec.index_position is None:
                raise RuntimePathError(
                    f"index path {spec.path!r} has no canonical position"
                )
            return record.tables[spec.table_id][spec.row_key]["indexes"][
                spec.index_position
            ]
        return RuntimeState._read_values_unlocked(
            record.scalars, record.tables, spec
        )

    @staticmethod
    def _read_values_unlocked(
        scalars: dict[str, Any],
        tables: dict[str, dict[str, dict[str, Any]]],
        spec: PathSpec,
    ) -> Any:
        if spec.kind == "scalar":
            return scalars[spec.field_id]
        if spec.kind == "column":
            return tables[spec.table_id][spec.row_key]["values"][spec.field_id]
        raise RuntimePathError(f"path {spec.path!r} is not a writable leaf")

    @staticmethod
    def _write_values_unlocked(
        scalars: dict[str, Any],
        tables: dict[str, dict[str, dict[str, Any]]],
        spec: PathSpec,
        value: Any,
    ) -> None:
        if spec.kind == "scalar":
            scalars[spec.field_id] = copy.deepcopy(value)
            return
        if spec.kind == "column":
            tables[spec.table_id][spec.row_key]["values"][
                spec.field_id
            ] = copy.deepcopy(value)
            return
        raise RuntimePathError(f"path {spec.path!r} is not a writable leaf")

    def _prepare_event(
        self,
        *,
        device_id: str | None,
        kind: str,
        changed_paths: tuple[str, ...],
        action: str | None = None,
        previous_availability: str | None = None,
        availability: str | None = None,
    ) -> StateEvent:
        """Materialize a complete event before mutating any live state."""

        next_revision = self._revision + 1
        return StateEvent(
            event_id=f"l3-{next_revision}",
            revision=next_revision,
            timestamp=datetime.now(timezone.utc).isoformat(),
            device_id=device_id,
            kind=kind,
            changed_paths=changed_paths,
            action=action,
            previous_availability=previous_availability,
            availability=availability,
        )

    def _commit_event(self, event: StateEvent) -> None:
        """Publish a pre-built event inside the caller's commit critical section."""

        if event.revision != self._revision + 1:
            raise RuntimeStateError("prepared event revision is stale")
        self._events.append(event)
        self._revision = event.revision
        if len(self._events) > EVENT_HISTORY_LIMIT:
            del self._events[:-EVENT_HISTORY_LIMIT]


__all__ = [
    "ActionResult",
    "Availability",
    "EVENT_HISTORY_LIMIT",
    "INITIAL_REVISION",
    "PatchResult",
    "RUNTIME_STATE_SCHEMA_VERSION",
    "RuntimeAction",
    "RuntimeDeviceSpec",
    "RuntimeState",
    "StateEvent",
]
