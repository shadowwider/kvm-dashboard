from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from simulator.profile_model import (
    ColumnDef,
    EnumDef,
    IndexDef,
    L0_CONTRACT_PATH,
    L0_CONTRACT_STATUS,
    L1_GOLDEN_CONTRACT_PATH,
    L1_GOLDEN_CONTRACT_STATUS,
    L1_GOLDEN_SCHEMA_VERSION,
    L1_OBJECT_MANIFEST_GLOB,
    L1_SOURCE_ASSURANCE,
    NumericRangeDef,
    ProfileDef,
    ScalarDef,
    SourceRef,
    TableDef,
)


SOURCE = SourceRef(
    document="docs/reference/docs/devices/visionxs-cpu-con.md",
    line_start=61,
    line_end=61,
)
STATUS_ENUM = EnumDef(
    name="ConnectionStatus",
    values={"notConnected": 0, "connected": 1},
)


def scalar(**overrides) -> ScalarDef:
    values = {
        "module": "GUD-TEST-MIB",
        "vendor_name": "deviceStatus",
        "canonical_field": "device_status",
        "ui_label": "Device status",
        "source": SOURCE,
        "oid": "1.3.6.1.4.1.32828.3.999.2.1",
        "syntax": "ConnectionStatus",
        "max_access": "read-only",
        "enum": STATUS_ENUM,
        "compliance": "mandatory",
    }
    values.update(overrides)
    return ScalarDef(**values)


def index(**overrides) -> IndexDef:
    values = {
        "module": "GUD-TEST-MIB",
        "vendor_name": "channelIndex",
        "canonical_field": "channel_index",
        "ui_label": "Channel index",
        "source": SOURCE,
        "oid": "1.3.6.1.4.1.32828.3.999.2.3.1000.1.1",
        "syntax": "Integer32",
        "value_range": {"min": 1, "max": 4},
        "position": 0,
    }
    values.update(overrides)
    return IndexDef(**values)


def column(**overrides) -> ColumnDef:
    values = {
        "module": "GUD-TEST-MIB",
        "vendor_name": "videoSignal",
        "canonical_field": "video_signal",
        "ui_label": "Video signal",
        "source": SOURCE,
        "oid": "1.3.6.1.4.1.32828.3.999.2.3.1000.1.2",
        "syntax": "ConnectionStatus",
        "max_access": "read-only",
        "enum": STATUS_ENUM,
        "compliance": "mandatory",
        "column": 2,
        "table_id": "video_channels",
        "index_order": ("channelIndex",),
    }
    values.update(overrides)
    return ColumnDef(**values)


def table(**overrides) -> TableDef:
    values = {
        "module": "GUD-TEST-MIB",
        "vendor_name": "videoTable",
        "canonical_field": "video_channels",
        "ui_label": "Video channels",
        "source": SOURCE,
        "oid": "1.3.6.1.4.1.32828.3.999.2.3.1000",
        "entry_vendor_name": "videoEntry",
        "entry_oid": "1.3.6.1.4.1.32828.3.999.2.3.1000.1",
        "indexes": (index(),),
        "columns": (column(),),
    }
    values.update(overrides)
    return TableDef(**values)


def profile(**overrides) -> ProfileDef:
    values = {
        "profile_id": "test_device",
        "product": "Test device",
        "profile_version": "1.0.0",
        "schema_version": L1_GOLDEN_SCHEMA_VERSION,
        "sys_object_id": "1.3.6.1.4.1.32828.3.999",
        "evidence_status": "local-device-dictionary-snapshot",
        "evidence_version": "l1-golden-schema-v1",
        "source_manifest": "backend/tests/golden/simulator/test.objects.json",
        "source_manifest_sha256": "a" * 64,
        "scalars": (scalar(),),
        "tables": (table(),),
    }
    values.update(overrides)
    return ProfileDef(**values)


def test_l2_model_records_accepted_l0_l1_dependency_boundary() -> None:
    assert L0_CONTRACT_PATH == (
        "docs/simulator/layers/L00_BASELINE_AND_ENVIRONMENT.md"
    )
    assert L0_CONTRACT_STATUS == "Accepted for Windows local port mode"
    assert L1_GOLDEN_CONTRACT_PATH == (
        "docs/simulator/layers/L01_MIB_GOLDEN_CONTRACT.md"
    )
    assert L1_GOLDEN_CONTRACT_STATUS == (
        "Accepted for local curated device dictionary snapshot"
    )
    assert L1_GOLDEN_SCHEMA_VERSION == 1
    assert L1_OBJECT_MANIFEST_GLOB == (
        "backend/tests/golden/simulator/*.objects.json"
    )
    assert L1_SOURCE_ASSURANCE == (
        "local-curated-snapshot-not-verified-against-original-mib-in-this-run"
    )


def test_vendor_canonical_and_ui_names_are_separate_fields() -> None:
    definition = scalar()

    assert definition.vendor_name == "deviceStatus"
    assert definition.canonical_field == "device_status"
    assert definition.ui_label == "Device status"
    assert definition.qualified_vendor_name == "GUD-TEST-MIB::deviceStatus"
    assert definition.instance_oid.endswith(".0")

    with pytest.raises(ValidationError, match="lower_snake_case"):
        scalar(canonical_field="deviceStatus")


def test_models_are_deeply_immutable() -> None:
    definition = scalar()

    with pytest.raises(ValidationError, match="frozen"):
        definition.ui_label = "Changed"
    with pytest.raises(TypeError):
        definition.enum.values[0] = ("broken", 9)
    assert definition.enum.value_map == {"notConnected": 0, "connected": 1}


@pytest.mark.parametrize(
    "bad_oid",
    [
        ".1.3.6.1",
        "1.03.6.1",
        "3.1.6.1",
        "1.40.6.1",
        "1.3.text.1",
    ],
)
def test_oid_must_be_canonical_numeric_form(bad_oid: str) -> None:
    with pytest.raises(ValidationError, match="OID|arc"):
        scalar(oid=bad_oid)


def test_scalar_definition_rejects_instance_suffix() -> None:
    with pytest.raises(ValidationError, match="instance suffix"):
        scalar(oid="1.3.6.1.4.1.32828.3.999.2.1.0")


def test_enum_and_range_reject_invalid_fixture_values_without_storing_defaults() -> None:
    enum_leaf = scalar()
    enum_leaf.validate_fixture_value(1)
    with pytest.raises(ValueError, match="not in enum"):
        enum_leaf.validate_fixture_value(3)
    with pytest.raises(ValueError, match="not in enum"):
        enum_leaf.validate_fixture_value(True)

    ranged_leaf = scalar(
        syntax="Integer32",
        enum=None,
        value_range={"min": 1, "max": 4},
    )
    ranged_leaf.validate_fixture_value(4)
    with pytest.raises(ValueError, match="outside"):
        ranged_leaf.validate_fixture_value(5)

    with pytest.raises(ValidationError, match="extra_forbidden"):
        scalar(default=1)


def test_enum_values_and_ranges_must_be_unambiguous() -> None:
    with pytest.raises(ValidationError, match="duplicate enum values"):
        EnumDef(name="BrokenStatus", values=(("off", 0), ("down", 0)))
    with pytest.raises(ValidationError):
        EnumDef(name="BrokenStatus", values=(("off", True),))
    with pytest.raises(ValidationError, match="maximum"):
        NumericRangeDef(minimum=5, maximum=4)


def test_optional_objects_require_explicit_group_and_are_not_fixture_rows() -> None:
    optional = scalar(
        compliance="optional",
        optional_group="general_errors",
    )
    catalog = profile(scalars=(optional,))

    assert catalog.optional_groups == ("general_errors",)
    assert "rows" not in type(optional).model_fields
    assert "default" not in type(optional).model_fields

    with pytest.raises(ValidationError, match="explicit optional_group"):
        scalar(compliance="optional")
    with pytest.raises(ValidationError, match="only valid"):
        scalar(optional_group="general_errors")


def test_table_rejects_duplicate_base_oid_column_pair() -> None:
    duplicate = column(
        vendor_name="secondSignal",
        canonical_field="second_signal",
    )
    with pytest.raises(ValidationError, match=r"duplicate \(base_oid, column\)"):
        table(columns=(column(), duplicate))


def test_table_oids_modules_and_index_ranges_are_validated() -> None:
    definition = table()

    assert definition.index_order == ("channelIndex",)
    assert (
        definition.instance_oid("video_signal", (2,))
        == "1.3.6.1.4.1.32828.3.999.2.3.1000.1.2.2"
    )
    with pytest.raises(ValueError, match="outside"):
        definition.instance_oid("video_signal", (5,))
    with pytest.raises(ValueError, match="requires 1"):
        definition.instance_oid("video_signal", ())
    with pytest.raises(KeyError, match="unknown column"):
        definition.instance_oid("missing", (1,))

    with pytest.raises(ValidationError, match="entry_oid"):
        table(entry_oid="1.3.6.1.4.1.32828.3.999.2.3.1000.2")
    with pytest.raises(ValidationError, match="column number"):
        table(columns=(column(oid="1.3.6.1.4.1.32828.3.999.2.3.1000.1.3"),))
    with pytest.raises(ValidationError, match="modules must match"):
        table(indexes=(index(module="GUD-OTHER-MIB"),))


def test_table_can_reference_an_index_defined_by_a_parent_table() -> None:
    inherited = index(
        oid="1.3.6.1.4.1.32828.3.999.2.3.999.1.1",
        defined_here=False,
    )
    definition = table(indexes=(inherited,))

    assert definition.indexes[0].defined_here is False
    assert definition.instance_oid("video_signal", (1,)).endswith(".2.1")


def test_profile_requires_exact_versioned_evidence_and_unique_objects() -> None:
    definition = profile()

    assert definition.sys_object_id_match == "exact"
    assert definition.profile_version == "1.0.0"
    assert definition.source_assurance == L1_SOURCE_ASSURANCE
    assert definition.gettable_leaf_count == 2

    with pytest.raises(ValidationError, match="semantic versioning"):
        profile(profile_version="v1")
    with pytest.raises(ValidationError, match="L1 repository-local"):
        profile(source_manifest=r"H:\WORK\I\raw\device.objects.json")
    with pytest.raises(ValidationError, match="SHA-256"):
        profile(source_manifest_sha256="not-a-hash")
    with pytest.raises(ValidationError, match="duplicate object definition OIDs"):
        profile(
            scalars=(
                scalar(),
                scalar(
                    vendor_name="otherStatus",
                    canonical_field="other_status",
                ),
            )
        )


def test_ccdc_legacy_vendor_schema_cannot_promote_compatibility_objects() -> None:
    empty = profile(
        profile_id="ccdc_legacy",
        evidence_status="legacy-unverified",
        source_manifest="backend/tests/golden/simulator/ccdc_legacy.objects.json",
        scalars=(),
        tables=(),
    )
    assert empty.gettable_leaf_count == 0

    with pytest.raises(ValidationError, match="vendor schema must remain empty"):
        profile(
            profile_id="ccdc_legacy",
            evidence_status="legacy-unverified",
            source_manifest=(
                "backend/tests/golden/simulator/ccdc_legacy.objects.json"
            ),
            tables=(),
        )


def test_source_ref_rejects_raw_or_repository_external_inputs() -> None:
    with pytest.raises(ValidationError, match="repository-relative"):
        SourceRef(document=r"H:\WORK\I\kvm\new\raw.mib", line_start=1, line_end=1)
    with pytest.raises(ValidationError, match="L1-approved"):
        SourceRef(document="docs/reference/raw.mib", line_start=1, line_end=1)
    with pytest.raises(ValidationError, match="line_end"):
        SourceRef(
            document="docs/reference/docs/devices/dp12-mux-atc.md",
            line_start=10,
            line_end=9,
        )


def test_schema_metadata_is_definition_only_and_does_not_expand_index_ranges() -> None:
    definition = profile()
    metadata = definition.schema_metadata()
    encoded = json.dumps(metadata, separators=(",", ":"))

    assert metadata["profile_id"] == "test_device"
    assert len(metadata["tables"]) == 1
    assert len(metadata["tables"][0]["columns"]) == 1
    assert '"rows"' not in encoded
    assert '"fixture"' not in encoded
    assert len(encoded) < 10_000


def test_table_definition_forbids_fixture_instance_fields() -> None:
    values = table().model_dump()
    values["rows"] = [{"channel_index": 1}]

    with pytest.raises(ValidationError, match="extra_forbidden"):
        TableDef(**values)
