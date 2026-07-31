"""Canonical L3 runtime paths and value validation.

This module consumes only the immutable L2 Profile definitions.  It does not
render OIDs, encode ASN.1, open sockets, or infer runtime instances from MIB
index ranges.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any, Iterable, Literal

from .profile_model import ColumnDef, ScalarDef


# L2 currently carries no vendor SIZE constraints.  This is therefore an
# explicit platform safety policy, not a G&D/MIB fact.
PLATFORM_STRING_MAX_UTF8_BYTES = 4096

_CANONICAL_NAME = r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*"
_SIGNED_DECIMAL = r"(?:0|[1-9]\d*|-[1-9]\d*)"
_ROW_KEY_RE = re.compile(rf"^{_SIGNED_DECIMAL}(?:,{_SIGNED_DECIMAL})*$")
_SCALAR_PATH_RE = re.compile(rf"^scalars\.(?P<field>{_CANONICAL_NAME})$")
_TABLE_VALUE_PATH_RE = re.compile(
    rf"^tables\.(?P<table>{_CANONICAL_NAME})"
    rf"\[(?P<row>{_SIGNED_DECIMAL}(?:,{_SIGNED_DECIMAL})*)\]"
    rf"\.(?P<field>{_CANONICAL_NAME})$"
)
_TABLE_INDEX_PATH_RE = re.compile(
    rf"^tables\.(?P<table>{_CANONICAL_NAME})"
    rf"\[(?P<row>{_SIGNED_DECIMAL}(?:,{_SIGNED_DECIMAL})*)\]"
    rf"\.indexes\.(?P<field>{_CANONICAL_NAME})$"
)
_IDENTITY_PATH_RE = re.compile(
    r"^identity\.(?P<field>"
    r"device_id|profile_id|profile_version|host|snmp_port|system_oid"
    r")$"
)
_AVAILABILITY_PATH = "runtime.availability"

_INTEGER_BOUNDS: dict[str, tuple[int, int]] = {
    "Integer": (-(2**31), (2**31) - 1),
    "Integer32": (-(2**31), (2**31) - 1),
    "Unsigned32": (0, (2**32) - 1),
    "Gauge32": (0, (2**32) - 1),
    "Counter32": (0, (2**32) - 1),
    "TimeTicks": (0, (2**32) - 1),
    "Counter64": (0, (2**64) - 1),
}
_STRING_SYNTAXES = {
    "DisplayString",
    "PhysAddress",
    "IpAddress",
    "OCTET STRING",
    "OctetString",
}

PathKind = Literal["identity", "availability", "scalar", "column", "index"]


class RuntimeStateError(ValueError):
    """Base error for the L3 state contract."""


class RuntimePathError(RuntimeStateError):
    """A path is malformed, absent, duplicated, or read-only."""


class RuntimeValueError(RuntimeStateError):
    """A value violates its L2 type or L3 platform safety policy."""


class RuntimeTransitionError(RuntimeStateError):
    """An action is not allowed from the current availability state."""


@dataclass(frozen=True, slots=True)
class ParsedPath:
    kind: PathKind
    field_id: str
    table_id: str | None = None
    row_key: str | None = None
    index_values: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PathSpec:
    """Immutable metadata for one actual runtime path."""

    path: str
    kind: PathKind
    field_id: str
    runtime_writable: bool
    vendor_snmp_writable: bool | None
    syntax: str | None
    optional_group: str | None = None
    enum_values: tuple[int, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    max_utf8_bytes: int | None = None
    length_policy: str | None = None
    table_id: str | None = None
    row_key: str | None = None
    index_values: tuple[int, ...] = ()
    index_position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuntimePathRegistry:
    """Read-only registry of actual fixture instances for one device."""

    __slots__ = ("_specs", "_ordered")

    def __init__(self, specs: Iterable[PathSpec]):
        by_path: dict[str, PathSpec] = {}
        ordered: list[PathSpec] = []
        for spec in specs:
            if spec.path in by_path:
                raise RuntimePathError(f"duplicate runtime path {spec.path!r}")
            by_path[spec.path] = spec
            ordered.append(spec)
        self._specs = MappingProxyType(by_path)
        self._ordered = tuple(ordered)

    def __len__(self) -> int:
        return len(self._ordered)

    def __iter__(self):
        return iter(self._ordered)

    def get(self, path: str) -> PathSpec:
        try:
            return self._specs[path]
        except KeyError as exc:
            raise RuntimePathError(f"unknown runtime path {path!r}") from exc

    @property
    def writable_paths(self) -> tuple[str, ...]:
        return tuple(spec.path for spec in self._ordered if spec.runtime_writable)

    @property
    def readonly_paths(self) -> tuple[str, ...]:
        return tuple(spec.path for spec in self._ordered if not spec.runtime_writable)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paths": [spec.to_dict() for spec in self._ordered],
            "writable_paths": list(self.writable_paths),
            "readonly_paths": list(self.readonly_paths),
        }


def format_row_key(index_values: Iterable[int]) -> str:
    """Return a canonical, reversible row key in IndexDef.position order."""

    values = tuple(index_values)
    if not values:
        raise RuntimePathError("row key requires at least one index")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
        raise RuntimePathError("row key indexes must be strict integers")
    return ",".join(str(value) for value in values)


def parse_row_key(row_key: str) -> tuple[int, ...]:
    """Parse only canonical signed-decimal tuples.

    Leading ``+``, leading zeroes, ``-0``, whitespace, empty items, and any
    non-decimal representation are rejected so one tuple has exactly one key.
    """

    if not isinstance(row_key, str) or not _ROW_KEY_RE.fullmatch(row_key):
        raise RuntimePathError(f"invalid canonical row key {row_key!r}")
    return tuple(int(item) for item in row_key.split(","))


def parse_runtime_path(path: str) -> ParsedPath:
    if not isinstance(path, str):
        raise RuntimePathError("runtime path must be a string")

    match = _SCALAR_PATH_RE.fullmatch(path)
    if match:
        return ParsedPath(kind="scalar", field_id=match.group("field"))

    match = _TABLE_VALUE_PATH_RE.fullmatch(path)
    if match:
        row_key = match.group("row")
        return ParsedPath(
            kind="column",
            field_id=match.group("field"),
            table_id=match.group("table"),
            row_key=row_key,
            index_values=parse_row_key(row_key),
        )

    match = _TABLE_INDEX_PATH_RE.fullmatch(path)
    if match:
        row_key = match.group("row")
        return ParsedPath(
            kind="index",
            field_id=match.group("field"),
            table_id=match.group("table"),
            row_key=row_key,
            index_values=parse_row_key(row_key),
        )

    match = _IDENTITY_PATH_RE.fullmatch(path)
    if match:
        return ParsedPath(kind="identity", field_id=match.group("field"))

    if path == _AVAILABILITY_PATH:
        return ParsedPath(kind="availability", field_id="availability")

    raise RuntimePathError(f"invalid runtime path {path!r}")


def path_spec_for_leaf(
    *,
    path: str,
    item: ScalarDef | ColumnDef,
    kind: Literal["scalar", "column"],
    table_id: str | None = None,
    row_key: str | None = None,
    index_values: tuple[int, ...] = (),
) -> PathSpec:
    minimum = None
    maximum = None
    if item.value_range is not None:
        minimum = item.value_range.minimum
        maximum = item.value_range.maximum
    elif item.syntax in _INTEGER_BOUNDS:
        minimum, maximum = _INTEGER_BOUNDS[item.syntax]

    is_string = item.syntax in _STRING_SYNTAXES
    return PathSpec(
        path=path,
        kind=kind,
        field_id=item.canonical_field,
        runtime_writable=True,
        vendor_snmp_writable=item.max_access == "read-write",
        syntax=item.syntax,
        optional_group=item.optional_group,
        enum_values=(
            tuple(value for _, value in item.enum.values)
            if item.enum is not None
            else ()
        ),
        minimum=minimum,
        maximum=maximum,
        max_utf8_bytes=PLATFORM_STRING_MAX_UTF8_BYTES if is_string else None,
        length_policy=(
            "platform-runtime-policy-not-vendor-mib-size" if is_string else None
        ),
        table_id=table_id,
        row_key=row_key,
        index_values=index_values,
    )


def validate_runtime_value(item: ScalarDef | ColumnDef, value: Any) -> None:
    """Validate a canonical value without guessing unsupported syntax."""

    if item.enum is not None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise RuntimeValueError(
                f"{item.canonical_field} requires a strict integer enum value"
            )
        if not item.enum.contains(value):
            raise RuntimeValueError(
                f"{item.canonical_field} value {value!r} is not in enum "
                f"{sorted(item.enum.value_map.values())}"
            )
    elif item.syntax in _INTEGER_BOUNDS:
        if not isinstance(value, int) or isinstance(value, bool):
            raise RuntimeValueError(
                f"{item.canonical_field} requires a strict integer"
            )
        syntax_minimum, syntax_maximum = _INTEGER_BOUNDS[item.syntax]
        if not syntax_minimum <= value <= syntax_maximum:
            raise RuntimeValueError(
                f"{item.canonical_field} is outside {item.syntax} bounds "
                f"{syntax_minimum}..{syntax_maximum}"
            )
    elif item.syntax in _STRING_SYNTAXES:
        if not isinstance(value, str):
            raise RuntimeValueError(
                f"{item.canonical_field} requires a canonical string value"
            )
        encoded_length = len(value.encode("utf-8"))
        if encoded_length > PLATFORM_STRING_MAX_UTF8_BYTES:
            raise RuntimeValueError(
                f"{item.canonical_field} exceeds the L3 platform UTF-8 safety "
                f"limit of {PLATFORM_STRING_MAX_UTF8_BYTES} bytes"
            )
        if item.syntax == "IpAddress":
            try:
                parsed = ipaddress.ip_address(value)
            except ValueError as exc:
                raise RuntimeValueError(
                    f"{item.canonical_field} requires an IPv4 address"
                ) from exc
            if parsed.version != 4:
                raise RuntimeValueError(
                    f"{item.canonical_field} requires an IPv4 address"
                )
    else:
        raise RuntimeValueError(
            f"{item.canonical_field} has unsupported runtime syntax "
            f"{item.syntax!r}"
        )

    if item.value_range is not None and not item.value_range.contains(value):
        raise RuntimeValueError(
            f"{item.canonical_field} value {value!r} is outside "
            f"{item.value_range.minimum}..{item.value_range.maximum}"
        )


__all__ = [
    "PLATFORM_STRING_MAX_UTF8_BYTES",
    "ParsedPath",
    "PathSpec",
    "RuntimePathError",
    "RuntimePathRegistry",
    "RuntimeStateError",
    "RuntimeTransitionError",
    "RuntimeValueError",
    "format_row_key",
    "parse_row_key",
    "parse_runtime_path",
    "path_spec_for_leaf",
    "validate_runtime_value",
]
