"""L2 fixture definitions and validation, separate from vendor Profile schema."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from .profile_catalog import (
    PROFILE_CATALOG,
    get_profile,
    normalize_catalog_profile_id,
)
from .profile_model import ColumnDef, ProfileDef, ScalarDef


DEFAULT_FIXTURE_PATH = (
    Path(__file__).with_name("catalog") / "l2_default_fixtures.json"
)


class _FrozenFixture(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class FixtureRow(_FrozenFixture):
    indexes: tuple[tuple[str, StrictInt], ...] = Field(min_length=1)
    values: tuple[tuple[str, Any], ...] = Field(min_length=1)

    @field_validator("indexes", "values", mode="before")
    @classmethod
    def normalize_mapping(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(value.items())
        return value

    @property
    def index_map(self) -> dict[str, int]:
        return dict(self.indexes)

    @property
    def value_map(self) -> dict[str, Any]:
        return dict(self.values)


class FixtureTable(_FrozenFixture):
    table_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    rows: tuple[FixtureRow, ...] = ()


class FixtureSpec(_FrozenFixture):
    fixture_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$"
    )
    profile_id: str
    profile_version: str
    evidence_version: str
    enabled_optional_groups: frozenset[str] = frozenset()
    scalar_values: tuple[tuple[str, Any], ...] = ()
    tables: tuple[FixtureTable, ...] = ()

    @field_validator("profile_id", mode="before")
    @classmethod
    def canonical_profile_id(cls, value: Any) -> str:
        return normalize_catalog_profile_id(value)

    @field_validator("scalar_values", mode="before")
    @classmethod
    def normalize_scalar_mapping(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(value.items())
        return value

    @property
    def scalar_map(self) -> dict[str, Any]:
        return dict(self.scalar_values)

    @property
    def table_map(self) -> dict[str, tuple[FixtureRow, ...]]:
        return {item.table_id: item.rows for item in self.tables}


_INTEGER_SYNTAXES = {
    "Integer",
    "Integer32",
    "Unsigned32",
    "Gauge32",
    "Counter32",
    "Counter64",
    "TimeTicks",
}
_STRING_SYNTAXES = {
    "DisplayString",
    "PhysAddress",
    "IpAddress",
    "OCTET STRING",
    "OctetString",
}


def _validate_value_type(item: ScalarDef | ColumnDef, value: Any) -> None:
    if item.enum is not None or item.syntax in _INTEGER_SYNTAXES:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{item.canonical_field} requires an integer")
    elif item.syntax in _STRING_SYNTAXES:
        if not isinstance(value, str):
            raise ValueError(f"{item.canonical_field} requires a string")
    else:
        raise ValueError(
            f"{item.canonical_field} has unsupported fixture syntax "
            f"{item.syntax!r}"
        )
    item.validate_fixture_value(value)


def validate_fixture_schema(
    profile: ProfileDef | Any,
    fixture: FixtureSpec | Mapping[str, Any],
) -> FixtureSpec:
    definition = profile if isinstance(profile, ProfileDef) else get_profile(profile)
    validated = (
        fixture
        if isinstance(fixture, FixtureSpec)
        else FixtureSpec.model_validate(fixture)
    )
    if validated.profile_id != definition.profile_id:
        raise ValueError("fixture profile_id does not match ProfileDef")
    if validated.profile_version != definition.profile_version:
        raise ValueError("fixture profile_version does not match ProfileDef")
    if validated.evidence_version != definition.evidence_version:
        raise ValueError("fixture evidence_version does not match ProfileDef")

    unknown_groups = (
        set(validated.enabled_optional_groups) - set(definition.optional_groups)
    )
    if unknown_groups:
        raise ValueError(f"unknown optional groups: {sorted(unknown_groups)}")

    scalar_defs = {
        item.canonical_field: item for item in definition.scalars
    }
    scalar_values = validated.scalar_map
    if len(scalar_values) != len(validated.scalar_values):
        raise ValueError("duplicate fixture scalar field")
    for field_id, value in scalar_values.items():
        item = scalar_defs.get(field_id)
        if item is None:
            raise ValueError(f"unknown fixture scalar {field_id}")
        if (
            item.optional_group is not None
            and item.optional_group not in validated.enabled_optional_groups
        ):
            raise ValueError(
                f"optional scalar {field_id} requires {item.optional_group}"
            )
        _validate_value_type(item, value)
    required_scalars = {
        item.canonical_field
        for item in definition.scalars
        if item.optional_group is None
        or item.optional_group in validated.enabled_optional_groups
    }
    missing_scalars = required_scalars - set(scalar_values)
    if missing_scalars:
        raise ValueError(
            f"missing required fixture scalars: {sorted(missing_scalars)}"
        )

    table_defs = {
        item.canonical_field: item for item in definition.tables
    }
    table_map = validated.table_map
    if len(table_map) != len(validated.tables):
        raise ValueError("duplicate fixture table")
    for table_id, rows in table_map.items():
        table = table_defs.get(table_id)
        if table is None:
            raise ValueError(f"unknown fixture table {table_id}")
        row_keys: set[tuple[int, ...]] = set()
        for row in rows:
            expected_names = tuple(item.canonical_field for item in table.indexes)
            actual_names = tuple(name for name, _ in row.indexes)
            if actual_names != expected_names:
                raise ValueError(
                    f"{table_id} indexes must be exactly {expected_names} in order"
                )
            index_values = tuple(value for _, value in row.indexes)
            table.validate_fixture_indexes(index_values)
            if index_values in row_keys:
                raise ValueError(f"duplicate fixture row {table_id}{index_values}")
            row_keys.add(index_values)

            value_map = row.value_map
            if len(value_map) != len(row.values):
                raise ValueError(f"duplicate fixture column in {table_id}{index_values}")
            columns = {
                item.canonical_field: item for item in table.columns
            }
            for field_id, value in value_map.items():
                item = columns.get(field_id)
                if item is None:
                    raise ValueError(
                        f"unknown fixture column {table_id}.{field_id}"
                    )
                if (
                    item.optional_group is not None
                    and item.optional_group
                    not in validated.enabled_optional_groups
                ):
                    raise ValueError(
                        f"optional column {table_id}.{field_id} requires "
                        f"{item.optional_group}"
                    )
                _validate_value_type(item, value)
            required_columns = {
                item.canonical_field
                for item in table.columns
                if item.optional_group is None
                or item.optional_group in validated.enabled_optional_groups
            }
            missing_columns = required_columns - set(value_map)
            if missing_columns:
                raise ValueError(
                    f"missing required fixture columns for {table_id}"
                    f"{index_values}: {sorted(missing_columns)}"
                )
    return validated


def build_explicit_fixture(
    profile: ProfileDef | Any,
    *,
    fixture_id: str,
    scalar_values: Mapping[str, Any],
    table_rows: Mapping[
        str, Sequence[FixtureRow | Mapping[str, Any]]
    ] | None = None,
    enabled_optional_groups: Sequence[str] = (),
) -> FixtureSpec:
    """Validate caller-provided complete values without inventing defaults."""

    definition = profile if isinstance(profile, ProfileDef) else get_profile(profile)
    enabled = frozenset(enabled_optional_groups)
    tables: list[FixtureTable] = []
    for table_id, rows in (table_rows or {}).items():
        tables.append(
            FixtureTable(
                table_id=table_id,
                rows=tuple(
                    row
                    if isinstance(row, FixtureRow)
                    else FixtureRow.model_validate(row)
                    for row in rows
                ),
            )
        )
    fixture = FixtureSpec(
        fixture_id=fixture_id,
        profile_id=definition.profile_id,
        profile_version=definition.profile_version,
        evidence_version=definition.evidence_version,
        enabled_optional_groups=enabled,
        scalar_values=tuple(dict(scalar_values).items()),
        tables=tuple(tables),
    )
    return validate_fixture_schema(definition, fixture)


def _load_default_fixtures() -> tuple[dict[str, FixtureSpec], str]:
    raw = DEFAULT_FIXTURE_PATH.read_bytes()
    payload = json.loads(raw)
    if payload.get("fixture_schema_version") != 1:
        raise RuntimeError("Unsupported default fixture artifact schema")
    if payload.get("fixture_kind") != "simulator-l2-default-fixtures":
        raise RuntimeError("Unexpected default fixture artifact kind")
    fixtures: dict[str, FixtureSpec] = {}
    for item in payload.get("fixtures", []):
        fixture = FixtureSpec.model_validate(item)
        profile = get_profile(fixture.profile_id)
        validate_fixture_schema(profile, fixture)
        if fixture.profile_id == "ccdc_legacy":
            raise RuntimeError(
                "CCDC project legacy data must not enter vendor fixtures"
            )
        if fixture.profile_id in fixtures:
            raise RuntimeError(f"duplicate default fixture {fixture.profile_id}")
        fixtures[fixture.profile_id] = fixture
    expected = set(PROFILE_CATALOG) - {"ccdc_legacy"}
    if set(fixtures) != expected:
        raise RuntimeError(
            "default fixture artifact must contain exactly four vendor Profiles"
        )
    return fixtures, hashlib.sha256(raw).hexdigest()


_LOADED_DEFAULT_FIXTURES, DEFAULT_FIXTURE_SHA256 = _load_default_fixtures()
DEFAULT_FIXTURES = MappingProxyType(_LOADED_DEFAULT_FIXTURES)


def runtime_fixture_read_paths() -> tuple[Path, ...]:
    """Declare the only data file read by the production fixture loader."""

    return (DEFAULT_FIXTURE_PATH.resolve(),)


__all__ = [
    "FixtureRow",
    "FixtureSpec",
    "FixtureTable",
    "DEFAULT_FIXTURES",
    "DEFAULT_FIXTURE_PATH",
    "DEFAULT_FIXTURE_SHA256",
    "build_explicit_fixture",
    "runtime_fixture_read_paths",
    "validate_fixture_schema",
]
