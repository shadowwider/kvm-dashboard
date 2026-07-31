from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest


GOLDEN_DIR = Path(__file__).parent / "golden" / "simulator"
REPO_ROOT = Path(__file__).resolve().parents[2]
OID_RE = re.compile(r"^\d+(?:\.\d+)+$")

EXPECTED = {
    "ccdm.objects.json": {
        "profile_id": "ccdm_matrix",
        "sys_object_id": "1.3.6.1.4.1.32828.3.257.10",
        "objects": 202,
        "gettable": 142,
        "not_accessible": 60,
        "tables": 20,
    },
    "visionxs_cpu.objects.json": {
        "profile_id": "visionxs_cpu",
        "sys_object_id": "1.3.6.1.4.1.32828.3.768.768",
        "objects": 34,
        "gettable": 28,
        "not_accessible": 6,
        "tables": 2,
    },
    "visionxs_con.objects.json": {
        "profile_id": "visionxs_con",
        "sys_object_id": "1.3.6.1.4.1.32828.3.769.768",
        "objects": 33,
        "gettable": 27,
        "not_accessible": 6,
        "tables": 2,
    },
    "dp12_mux_atc.objects.json": {
        "profile_id": "dp12_mux_atc",
        "sys_object_id": "1.3.6.1.4.1.32828.3.1792.17",
        "objects": 47,
        "gettable": 35,
        "not_accessible": 12,
        "tables": 4,
    },
    "ccdc_legacy.objects.json": {
        "profile_id": "ccdc_legacy",
        "sys_object_id": "1.3.6.1.4.1.32828.3.257.16",
        "objects": 0,
        "gettable": 0,
        "not_accessible": 0,
        "tables": 0,
    },
}


def load(filename: str) -> dict:
    return json.loads((GOLDEN_DIR / filename).read_text(encoding="utf-8"))


@pytest.mark.parametrize("filename", EXPECTED)
def test_manifest_schema_counts_and_evidence_boundary(filename: str) -> None:
    manifest = load(filename)
    expected = EXPECTED[filename]

    assert manifest["schema_version"] == 1
    assert manifest["manifest_kind"] == "simulator-mib-object-golden"
    assert manifest["profile_id"] == expected["profile_id"]
    assert manifest["sys_object_id"]["oid"] == expected["sys_object_id"]
    assert manifest["sys_object_id"]["match"] == "exact"
    assert manifest["object_count"] == expected["objects"] == len(manifest["objects"])
    assert manifest["gettable_count"] == expected["gettable"]
    assert manifest["not_accessible_count"] == expected["not_accessible"]
    assert manifest["table_count"] == expected["tables"] == len(manifest["tables"])

    contract = manifest["source_contract"]
    assert (
        contract["source_assurance"]
        == "local-curated-snapshot-not-verified-against-original-mib-in-this-run"
    )
    assert contract["independent_of_simulator_profiles"] is True
    assert "backend/simulator/profiles.py" in contract["prohibited_inputs"]
    assert "PROFILE_DEFINITIONS" in contract["prohibited_inputs"]

    if filename == "ccdc_legacy.objects.json":
        assert manifest["evidence_status"] == "legacy-unverified"
        assert (
            contract["authority"]
            == "project-compatibility-plan-legacy-boundary"
        )
        assert manifest["objects"] == []
        assert manifest["tables"] == []
    else:
        assert manifest["evidence_status"] == "local-device-dictionary-snapshot"
        assert contract["authority"] == "local-curated-device-dictionary-snapshot"
        assert manifest["source_documents"]
        assert all(
            source["path"].startswith("docs/reference/docs/devices/")
            for source in manifest["source_documents"]
        )


@pytest.mark.parametrize("filename", EXPECTED)
def test_source_metadata_is_repository_relative_and_auditable(filename: str) -> None:
    manifest = load(filename)
    source_paths = {source["path"] for source in manifest["source_documents"]}
    source_line_counts = {
        source["path"]: source["line_count"]
        for source in manifest["source_documents"]
    }

    for source in manifest["source_documents"]:
        assert not Path(source["path"]).is_absolute()
        assert ":" not in source["path"]
        assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        assert source["line_count"] > 0
        source_path = REPO_ROOT / source["path"]
        raw = source_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source["sha256"]
        assert len(raw.decode("utf-8").splitlines()) == source["line_count"]

    sources = [manifest["sys_object_id"]["source"]]
    sources.extend(item["source"] for item in manifest["objects"])
    sources.extend(item["source"] for item in manifest["tables"])
    for source in sources:
        assert source["document"] in source_paths
        assert 1 <= source["line_start"] <= source["line_end"]
        assert source["line_end"] <= source_line_counts[source["document"]]
        assert source["upstream_reference_as_recorded"]
        assert source["upstream_reference_reverified_in_this_run"] is False


@pytest.mark.parametrize("filename", EXPECTED)
def test_oids_kinds_access_and_instance_rules(filename: str) -> None:
    manifest = load(filename)
    objects = manifest["objects"]
    oids = [item["oid"] for item in objects]
    qualified_names = [item["qualified_name"] for item in objects]

    assert len(oids) == len(set(oids))
    assert len(qualified_names) == len(set(qualified_names))
    assert all(OID_RE.fullmatch(oid) for oid in oids)
    assert all(not oid.endswith(".0") for oid in oids)
    assert sum(item["gettable"] for item in objects) == manifest["gettable_count"]
    assert (
        sum(item["max_access"] == "not-accessible" for item in objects)
        == manifest["not_accessible_count"]
    )

    required = {
        "name",
        "qualified_name",
        "module",
        "oid",
        "kind",
        "syntax",
        "max_access",
        "enum",
        "range",
        "unit",
        "default",
        "index_order",
        "compliance",
        "optional_group",
        "gettable",
        "writable",
        "instance_rule",
        "get_oid_template",
        "source",
    }
    for item in objects:
        assert required <= item.keys()
        assert item["kind"] in {"scalar", "table", "entry", "index", "column"}
        if item["kind"] in {"table", "entry"}:
            assert item["syntax"] is None
        else:
            assert isinstance(item["syntax"], str) and item["syntax"]
        if item["max_access"] == "not-accessible":
            assert item["gettable"] is False
            assert item["get_oid_template"] is None
            assert item["kind"] in {"table", "entry", "index"}
        if item["kind"] == "scalar":
            assert item["gettable"] is True
            assert item["instance_rule"] == "scalar-zero"
            assert item["get_oid_template"] == f"{item['oid']}.0"
        if item["kind"] == "column":
            assert item["gettable"] is True
            assert item["instance_rule"] == "index-suffix"
            assert item["index_order"]
            expected_suffix = ".".join(f"{{{name}}}" for name in item["index_order"])
            assert item["get_oid_template"] == f"{item['oid']}.{expected_suffix}"
        if item["enum"] is not None:
            assert len(set(item["enum"].values())) == len(item["enum"])
        if item["default"] is not None and item["enum"] is not None:
            assert item["default"] in item["enum"].values()
        if item["range"] is not None:
            assert item["range"]["min"] <= item["range"]["max"]
        if item["unit"] is not None:
            assert item["unit"]["value"]
            assert item["unit"]["evidence"] in {
                "description",
                "comment",
                "commented-units",
            }
        if item["compliance"] == "optional":
            assert item["optional_group"] is True
        elif item["compliance"] == "mandatory":
            assert item["optional_group"] is False
        else:
            assert item["optional_group"] is None


@pytest.mark.parametrize("filename", EXPECTED)
def test_table_entries_indexes_and_column_numbers_are_consistent(filename: str) -> None:
    manifest = load(filename)
    objects = {item["qualified_name"]: item for item in manifest["objects"]}

    for table in manifest["tables"]:
        module = table["module"]
        table_object = objects[f"{module}::{table['name']}"]
        entry_object = objects[f"{module}::{table['entry_name']}"]
        assert table_object["kind"] == "table"
        assert entry_object["kind"] == "entry"
        assert table_object["oid"] == table["oid"]
        assert entry_object["oid"] == table["entry_oid"] == f"{table['oid']}.1"
        assert table_object["index_order"] == table["index_order"]
        assert entry_object["index_order"] == table["index_order"]

        prefix = f"{table['entry_oid']}."
        columns = [
            item
            for item in manifest["objects"]
            if item["module"] == module
            and item["kind"] == "column"
            and item["oid"].startswith(prefix)
            and item["oid"].count(".") == table["entry_oid"].count(".") + 1
        ]
        column_numbers = [int(item["oid"].rsplit(".", 1)[1]) for item in columns]
        assert columns
        assert len(column_numbers) == len(set(column_numbers))
        assert all(item["index_order"] == table["index_order"] for item in columns)


def find_object(manifest: dict, module: str, name: str) -> dict:
    return next(
        item
        for item in manifest["objects"]
        if item["module"] == module and item["name"] == name
    )


def test_compound_index_order_and_ccdm_twenty_table_coverage() -> None:
    ccdm = load("ccdm.objects.json")
    assert ccdm["table_count"] == 20
    table_names = {table["qualified_name"] for table in ccdm["tables"]}
    assert {
        "GUD-CCDM-MIB::fanTable",
        "GUD-CCDM-MIB::ioCardCatPortTable",
        "GUD-CCDMCON-MIB::fanTable",
        "GUD-CCDMCON-MIB::gpioTable",
        "GUD-CCDMCPU-MIB::fanTable",
        "GUD-CCDMCPU-MIB::gpioTable",
        "GUD-CCDMDWC-MIB::fanTable",
        "GUD-CCDMDWC-MIB::videoChannelTable",
        "GUD-CCDMDWC-MIB::linkChannelTable",
    } <= table_names

    assert find_object(
        ccdm, "GUD-CCDM-MIB", "ioCardFiberPortStatus"
    )["index_order"] == ["ioCardFiberIndex", "ioCardFiberPortIndex"]
    assert find_object(
        ccdm, "GUD-CCDMCON-MIB", "fanSpeed"
    )["index_order"] == ["userModuleIndex", "fanIndex"]
    assert find_object(
        ccdm, "GUD-CCDMCPU-MIB", "gpioValue"
    )["index_order"] == ["targetModuleIndex", "gpioIndex"]
    assert find_object(
        ccdm, "GUD-CCDMDWC-MIB", "freeze"
    )["index_order"] == ["dynamicUserModuleIndex", "linkChannelIndex"]

    dp = load("dp12_mux_atc.objects.json")
    assert find_object(
        dp, "GUD-DP12MUXATC-MIB", "cpuChannelVideoSignal"
    )["index_order"] == ["cpuChannelIndex", "cpuChannelVideoIndex"]


def test_dp_write_boundary_and_trap_objects_are_not_mixed_into_product_manifests() -> None:
    dp = load("dp12_mux_atc.objects.json")
    writable = {item["name"] for item in dp["objects"] if item["writable"]}
    assert writable == {
        "selectedChannel",
        "disableSwitching",
        "disableFrontkeys",
        "disableHotkeys",
        "disableSerialPort",
        "disableRemoteControlApi",
    }
    assert sum(item["max_access"] == "read-only" for item in dp["objects"]) == 29
    assert sum(item["max_access"] == "read-write" for item in dp["objects"]) == 6

    for filename in EXPECTED:
        names = {item["name"] for item in load(filename)["objects"]}
        assert "generalNotification" not in names
        assert "level" not in names
        assert "message" not in names


def test_vision_optional_and_string_measurement_boundaries() -> None:
    for filename, module in [
        ("visionxs_cpu.objects.json", "GUD-VISIONXSCPU-MIB"),
        ("visionxs_con.objects.json", "GUD-VISIONXSCON-MIB"),
    ]:
        manifest = load(filename)
        for name in ["generalErrorCode", "generalErrorMessage"]:
            item = find_object(manifest, module, name)
            assert item["compliance"] == "optional"
            assert item["optional_group"] is True
        for name in ["temperature1", "fan1"]:
            item = find_object(manifest, module, name)
            assert item["syntax"] == "DisplayString"
        for name in [
            "transparentUsbLink",
            "transparentUsbSfpModule",
            "transparentUsbTxPower",
            "transparentUsbRxPower",
            "transparentUsbSfpType",
        ]:
            item = find_object(manifest, module, name)
            assert item["compliance"] == "defined-not-in-compliance-group"
            assert item["optional_group"] is None
