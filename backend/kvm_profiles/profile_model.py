"""Immutable L2 Profile schema definitions.

This module is deliberately limited to protocol/profile metadata.  It does not
load fixture rows, hold runtime values, render ASN.1, open sockets, or expose UI
state.

Evidence boundary:

* L0 runtime/path boundary:
  ``docs/simulator/layers/L00_BASELINE_AND_ENVIRONMENT.md``
* Accepted L1 object contract:
  ``docs/simulator/layers/L01_MIB_GOLDEN_CONTRACT.md``
* Accepted L1 object manifests:
  ``backend/tests/golden/simulator/*.objects.json``

The accepted L1 source assurance is copied here as a constant so an L2 catalog
can record the exact evidence boundary without reading repository-external MIB
or evidence files.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)


L0_CONTRACT_PATH = "docs/simulator/layers/L00_BASELINE_AND_ENVIRONMENT.md"
L0_CONTRACT_STATUS = "Accepted for Windows local port mode"
L1_GOLDEN_CONTRACT_PATH = "docs/simulator/layers/L01_MIB_GOLDEN_CONTRACT.md"
L1_GOLDEN_CONTRACT_STATUS = (
    "Accepted for local curated device dictionary snapshot"
)
L1_GOLDEN_SCHEMA_VERSION = 1
L1_SOURCE_ASSURANCE = (
    "local-curated-snapshot-not-verified-against-original-mib-in-this-run"
)
L1_OBJECT_MANIFEST_GLOB = "backend/tests/golden/simulator/*.objects.json"

_OID_RE = re.compile(r"^(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*)){1,}$")
_CANONICAL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_VENDOR_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
_ENUM_LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EvidenceStatus = Literal[
    "local-device-dictionary-snapshot",
    "legacy-unverified",
]
MaxAccess = Literal["read-only", "read-write"]
Compliance = Literal[
    "mandatory",
    "optional",
    "defined-not-in-compliance-group",
    "unlisted",
]


def _validate_oid(value: str, *, label: str) -> str:
    if not _OID_RE.fullmatch(value):
        raise ValueError(f"{label} must be a canonical numeric OID")
    arcs = tuple(int(arc) for arc in value.split("."))
    if arcs[0] > 2:
        raise ValueError(f"{label} first arc must be 0, 1, or 2")
    if arcs[0] < 2 and arcs[1] > 39:
        raise ValueError(f"{label} second arc must be <= 39 when first arc is {arcs[0]}")
    return value


def _validate_canonical_name(value: str, *, label: str) -> str:
    if not _CANONICAL_NAME_RE.fullmatch(value):
        raise ValueError(f"{label} must use lower_snake_case")
    return value


def _duplicates(values: Sequence[Any]) -> set[Any]:
    seen: set[Any] = set()
    duplicates: set[Any] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


class _FrozenDefinition(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class SourceRef(_FrozenDefinition):
    """Repository-local L1 provenance copied into an L2 definition."""

    document: str = Field(min_length=1, max_length=512)
    line_start: StrictInt = Field(ge=1)
    line_end: StrictInt = Field(ge=1)
    upstream_reference_as_recorded: str | None = Field(
        default=None, min_length=1, max_length=512
    )
    upstream_reference_reverified_in_this_run: bool = False

    @field_validator("document")
    @classmethod
    def validate_document(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if (
            normalized.startswith("/")
            or re.match(r"^[A-Za-z]:", normalized)
            or ".." in normalized.split("/")
        ):
            raise ValueError("source document must be a repository-relative path")
        allowed = (
            normalized.startswith("docs/reference/docs/devices/")
            or normalized == "docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md"
        )
        if not allowed:
            raise ValueError(
                "source document must be an L1-approved local device dictionary "
                "or the repository compatibility plan"
            )
        return normalized

    @model_validator(mode="after")
    def validate_lines(self) -> SourceRef:
        if self.line_end < self.line_start:
            raise ValueError("source line_end must be >= line_start")
        return self


class UnitDef(_FrozenDefinition):
    value: str = Field(min_length=1, max_length=32)
    evidence: Literal["description", "comment", "commented-units"]


class NumericRangeDef(_FrozenDefinition):
    minimum: StrictInt
    maximum: StrictInt

    @model_validator(mode="before")
    @classmethod
    def normalize_l1_shape(cls, value: Any) -> Any:
        if isinstance(value, Mapping) and ("min" in value or "max" in value):
            return {
                "minimum": value.get("min"),
                "maximum": value.get("max"),
            }
        return value

    @model_validator(mode="after")
    def validate_order(self) -> NumericRangeDef:
        if self.maximum < self.minimum:
            raise ValueError("range maximum must be >= minimum")
        return self

    def contains(self, value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and (
            self.minimum <= value <= self.maximum
        )


class EnumDef(_FrozenDefinition):
    """A deeply immutable integer enumeration."""

    name: str = Field(min_length=1, max_length=128)
    values: tuple[tuple[str, StrictInt], ...] = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not _VENDOR_NAME_RE.fullmatch(value):
            raise ValueError("enum name must be a stable vendor or canonical identifier")
        return value

    @field_validator("values", mode="before")
    @classmethod
    def normalize_values(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(value.items())
        return value

    @model_validator(mode="after")
    def validate_values(self) -> EnumDef:
        labels = [label for label, _ in self.values]
        values = [value for _, value in self.values]
        invalid_labels = [label for label in labels if not _ENUM_LABEL_RE.fullmatch(label)]
        if invalid_labels:
            raise ValueError(f"invalid enum labels: {invalid_labels}")
        if duplicates := _duplicates(labels):
            raise ValueError(f"duplicate enum labels: {sorted(duplicates)}")
        if duplicates := _duplicates(values):
            raise ValueError(f"duplicate enum values: {sorted(duplicates)}")
        return self

    @property
    def value_map(self) -> dict[str, int]:
        """Return a defensive copy for serialization or lookup."""

        return dict(self.values)

    @property
    def type_name(self) -> str:
        return self.name

    @property
    def labels_to_values(self) -> dict[str, int]:
        return self.value_map

    def contains(self, value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and any(
            enum_value == value for _, enum_value in self.values
        )


class _NamedDefinition(_FrozenDefinition):
    module: str = Field(min_length=1, max_length=128)
    vendor_name: str = Field(min_length=1, max_length=128)
    canonical_field: str = Field(min_length=1, max_length=128)
    ui_label: str = Field(min_length=1, max_length=128)
    source: SourceRef

    @field_validator("module", "vendor_name")
    @classmethod
    def validate_vendor_identifier(cls, value: str) -> str:
        if not _VENDOR_NAME_RE.fullmatch(value):
            raise ValueError("module/vendor name must be a stable identifier")
        return value

    @field_validator("canonical_field")
    @classmethod
    def validate_canonical_field(cls, value: str) -> str:
        return _validate_canonical_name(value, label="canonical_field")

    @property
    def qualified_vendor_name(self) -> str:
        return f"{self.module}::{self.vendor_name}"

    @property
    def field_id(self) -> str:
        return self.canonical_field

    @property
    def label_key(self) -> str:
        return self.ui_label


class _LeafDefinition(_NamedDefinition):
    oid: str
    syntax: str = Field(min_length=1, max_length=128)
    max_access: MaxAccess
    enum: EnumDef | None = None
    value_range: NumericRangeDef | None = None
    unit: UnitDef | None = None
    compliance: Compliance
    optional_group: str | None = Field(default=None, max_length=128)

    @field_validator("oid")
    @classmethod
    def validate_oid(cls, value: str) -> str:
        return _validate_oid(value, label="object OID")

    @field_validator("optional_group")
    @classmethod
    def validate_optional_group(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_canonical_name(value, label="optional_group")

    @model_validator(mode="after")
    def validate_optional_contract(self) -> _LeafDefinition:
        if self.compliance == "optional" and self.optional_group is None:
            raise ValueError("optional compliance requires an explicit optional_group")
        if self.optional_group is not None and self.compliance != "optional":
            raise ValueError("optional_group is only valid for optional compliance")
        return self

    def validate_fixture_value(self, value: Any) -> None:
        """Validate enum/range constraints without storing an instance value."""

        if self.enum is not None and not self.enum.contains(value):
            raise ValueError(
                f"{self.canonical_field} value {value!r} is not in enum "
                f"{sorted(self.enum.value_map.values())}"
            )
        if self.value_range is not None and not self.value_range.contains(value):
            raise ValueError(
                f"{self.canonical_field} value {value!r} is outside "
                f"{self.value_range.minimum}..{self.value_range.maximum}"
            )


class ScalarDef(_LeafDefinition):
    """A scalar object definition; the instance ``.0`` is derived, not stored."""

    kind: Literal["scalar"] = "scalar"

    @model_validator(mode="after")
    def validate_definition_oid(self) -> ScalarDef:
        if self.oid.endswith(".0"):
            raise ValueError("scalar definition OID must not contain the .0 instance suffix")
        return self

    @property
    def instance_oid(self) -> str:
        return f"{self.oid}.0"


class IndexDef(_NamedDefinition):
    """A table index definition. Tuple order in ``TableDef.indexes`` is INDEX order."""

    kind: Literal["index"] = "index"
    oid: str
    syntax: str = Field(min_length=1, max_length=128)
    value_range: NumericRangeDef | None = None
    position: StrictInt = Field(ge=0)
    defined_here: bool = True

    @field_validator("oid")
    @classmethod
    def validate_oid(cls, value: str) -> str:
        return _validate_oid(value, label="index OID")

    def validate_fixture_value(self, value: Any) -> None:
        if self.value_range is not None and not self.value_range.contains(value):
            raise ValueError(
                f"{self.canonical_field} index {value!r} is outside "
                f"{self.value_range.minimum}..{self.value_range.maximum}"
            )


class ColumnDef(_LeafDefinition):
    kind: Literal["column"] = "column"
    column: StrictInt = Field(ge=1)
    table_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    index_order: tuple[str, ...] = Field(min_length=1)


class TableDef(_NamedDefinition):
    """A table schema. Runtime/fixture rows are intentionally not representable."""

    kind: Literal["table"] = "table"
    oid: str
    entry_vendor_name: str = Field(min_length=1, max_length=128)
    entry_oid: str
    indexes: tuple[IndexDef, ...] = Field(min_length=1)
    columns: tuple[ColumnDef, ...] = Field(min_length=1)

    @field_validator("oid", "entry_oid")
    @classmethod
    def validate_oid(cls, value: str) -> str:
        return _validate_oid(value, label="table OID")

    @field_validator("entry_vendor_name")
    @classmethod
    def validate_entry_vendor_name(cls, value: str) -> str:
        if not _VENDOR_NAME_RE.fullmatch(value):
            raise ValueError("entry_vendor_name must be a stable vendor identifier")
        return value

    @model_validator(mode="after")
    def validate_structure(self) -> TableDef:
        if self.entry_oid != f"{self.oid}.1":
            raise ValueError("entry_oid must be the table OID followed by .1")

        index_vendor_names = [item.vendor_name for item in self.indexes]
        index_fields = [item.canonical_field for item in self.indexes]
        positions = [item.position for item in self.indexes]
        if duplicates := _duplicates(index_vendor_names):
            raise ValueError(f"duplicate index vendor names: {sorted(duplicates)}")
        if duplicates := _duplicates(index_fields):
            raise ValueError(f"duplicate index canonical fields: {sorted(duplicates)}")
        if positions != list(range(len(self.indexes))):
            raise ValueError("index positions must be contiguous and follow INDEX order")
        for index in self.indexes:
            if index.module != self.module:
                raise ValueError("table and index modules must match")
            if index.defined_here:
                if not index.oid.startswith(f"{self.entry_oid}."):
                    raise ValueError(
                        "locally defined index OID must be a direct child of the table entry"
                    )
                if index.oid.count(".") != self.entry_oid.count(".") + 1:
                    raise ValueError(
                        "locally defined index OID must be a direct child of the table entry"
                    )

        column_numbers = [item.column for item in self.columns]
        column_fields = [item.canonical_field for item in self.columns]
        column_oids = [item.oid for item in self.columns]
        if duplicates := _duplicates(column_numbers):
            raise ValueError(
                f"duplicate (base_oid, column) for {self.oid}: {sorted(duplicates)}"
            )
        if duplicates := _duplicates(column_fields):
            raise ValueError(f"duplicate column canonical fields: {sorted(duplicates)}")
        if duplicates := _duplicates(column_oids):
            raise ValueError(f"duplicate column OIDs: {sorted(duplicates)}")
        for column in self.columns:
            if column.module != self.module:
                raise ValueError("table and column modules must match")
            if column.table_id != self.canonical_field:
                raise ValueError("column table_id must match its TableDef")
            if column.index_order != self.index_order:
                raise ValueError("column index_order must match its TableDef")
            if column.oid != f"{self.entry_oid}.{column.column}":
                raise ValueError(
                    f"column {column.vendor_name} OID does not match its column number"
                )

        return self

    @property
    def index_order(self) -> tuple[str, ...]:
        return tuple(index.vendor_name for index in self.indexes)

    @property
    def table_id(self) -> str:
        return self.canonical_field

    @property
    def entry_qualified_vendor_name(self) -> str:
        return f"{self.module}::{self.entry_vendor_name}"

    def validate_fixture_indexes(self, values: Sequence[Any]) -> None:
        if len(values) != len(self.indexes):
            raise ValueError(
                f"{self.canonical_field} requires {len(self.indexes)} index values"
            )
        for index, value in zip(self.indexes, values):
            index.validate_fixture_value(value)

    def instance_oid(self, column_field: str, index_values: Sequence[Any]) -> str:
        """Build an instance OID after validating explicit fixture indexes."""

        self.validate_fixture_indexes(index_values)
        column = next(
            (item for item in self.columns if item.canonical_field == column_field),
            None,
        )
        if column is None:
            raise KeyError(f"unknown column field {column_field!r}")
        suffix = ".".join(str(value) for value in index_values)
        return f"{column.oid}.{suffix}"


class ProfileDef(_FrozenDefinition):
    """Versioned object schema consumable by L3 without carrying runtime state."""

    profile_id: str = Field(min_length=1, max_length=128)
    product: str = Field(min_length=1, max_length=256)
    profile_version: str = Field(min_length=1, max_length=64)
    schema_version: StrictInt = Field(ge=1)
    sys_object_id: str
    sys_object_id_match: Literal["exact"] = "exact"
    evidence_status: EvidenceStatus
    evidence_version: str = Field(min_length=1, max_length=128)
    source_assurance: Literal[
        "local-curated-snapshot-not-verified-against-original-mib-in-this-run"
    ] = L1_SOURCE_ASSURANCE
    source_manifest: str = Field(min_length=1, max_length=512)
    source_manifest_sha256: str
    scalars: tuple[ScalarDef, ...] = ()
    tables: tuple[TableDef, ...] = ()

    @field_validator("profile_id")
    @classmethod
    def validate_profile_id(cls, value: str) -> str:
        return _validate_canonical_name(value, label="profile_id")

    @field_validator("profile_version")
    @classmethod
    def validate_profile_version(cls, value: str) -> str:
        if not _SEMVER_RE.fullmatch(value):
            raise ValueError("profile_version must be semantic versioning")
        return value

    @field_validator("sys_object_id")
    @classmethod
    def validate_sys_object_id(cls, value: str) -> str:
        return _validate_oid(value, label="sysObjectID")

    @field_validator("source_manifest")
    @classmethod
    def validate_source_manifest(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if (
            normalized.startswith("/")
            or re.match(r"^[A-Za-z]:", normalized)
            or ".." in normalized.split("/")
            or not normalized.startswith("backend/tests/golden/simulator/")
            or not normalized.endswith(".objects.json")
        ):
            raise ValueError(
                "source_manifest must be an L1 repository-local object manifest"
            )
        return normalized

    @field_validator("source_manifest_sha256")
    @classmethod
    def validate_manifest_hash(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("source_manifest_sha256 must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_object_namespace(self) -> ProfileDef:
        if self.profile_id == "ccdc_legacy" and (self.scalars or self.tables):
            raise ValueError(
                "ccdc_legacy vendor schema must remain empty until an Accepted "
                "L1 vendor object manifest exists; legacy compatibility objects "
                "belong in a separate adapter"
            )

        scalar_fields = [item.canonical_field for item in self.scalars]
        table_fields = [item.canonical_field for item in self.tables]
        if duplicates := _duplicates(scalar_fields):
            raise ValueError(f"duplicate scalar canonical fields: {sorted(duplicates)}")
        if duplicates := _duplicates(table_fields):
            raise ValueError(f"duplicate table canonical fields: {sorted(duplicates)}")
        if overlap := set(scalar_fields) & set(table_fields):
            raise ValueError(
                f"scalar/table canonical fields overlap: {sorted(overlap)}"
            )

        definition_oids: list[str] = []
        qualified_names: list[str] = []
        for scalar in self.scalars:
            definition_oids.append(scalar.oid)
            qualified_names.append(scalar.qualified_vendor_name)
        for table in self.tables:
            definition_oids.extend(
                [
                    table.oid,
                    table.entry_oid,
                    *(index.oid for index in table.indexes if index.defined_here),
                    *(column.oid for column in table.columns),
                ]
            )
            qualified_names.extend(
                [
                    table.qualified_vendor_name,
                    f"{table.module}::{table.entry_vendor_name}",
                    *(
                        index.qualified_vendor_name
                        for index in table.indexes
                        if index.defined_here
                    ),
                    *(column.qualified_vendor_name for column in table.columns),
                ]
            )
        if duplicates := _duplicates(definition_oids):
            raise ValueError(f"duplicate object definition OIDs: {sorted(duplicates)}")
        if duplicates := _duplicates(qualified_names):
            raise ValueError(
                f"duplicate qualified vendor object names: {sorted(duplicates)}"
            )
        return self

    @property
    def optional_groups(self) -> tuple[str, ...]:
        groups = {
            item.optional_group
            for item in self.scalars
            if item.optional_group is not None
        }
        for table in self.tables:
            groups.update(
                item.optional_group
                for item in table.columns
                if item.optional_group is not None
            )
        return tuple(sorted(groups))

    @property
    def model_schema_version(self) -> int:
        return self.schema_version

    @property
    def evidence_revision(self) -> str:
        return self.evidence_version

    @property
    def gettable_leaf_count(self) -> int:
        return len(self.scalars) + sum(len(table.columns) for table in self.tables)

    def schema_metadata(self) -> dict[str, Any]:
        """Return schema-only metadata; never expand fixture rows or indexes."""

        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "schema_version": self.schema_version,
            "sys_object_id": self.sys_object_id,
            "sys_object_id_match": self.sys_object_id_match,
            "evidence_status": self.evidence_status,
            "evidence_version": self.evidence_version,
            "source_assurance": self.source_assurance,
            "source_manifest": self.source_manifest,
            "source_manifest_sha256": self.source_manifest_sha256,
            "scalars": [item.model_dump(mode="json") for item in self.scalars],
            "tables": [item.model_dump(mode="json") for item in self.tables],
        }


__all__ = [
    "ColumnDef",
    "Compliance",
    "EnumDef",
    "EvidenceStatus",
    "IndexDef",
    "L0_CONTRACT_PATH",
    "L0_CONTRACT_STATUS",
    "L1_GOLDEN_CONTRACT_PATH",
    "L1_GOLDEN_CONTRACT_STATUS",
    "L1_GOLDEN_SCHEMA_VERSION",
    "L1_OBJECT_MANIFEST_GLOB",
    "L1_SOURCE_ASSURANCE",
    "MaxAccess",
    "NumericRangeDef",
    "ProfileDef",
    "ScalarDef",
    "SourceRef",
    "TableDef",
    "UnitDef",
]
