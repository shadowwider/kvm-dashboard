"""Independent L1 Trap golden checks.

These tests intentionally load JSON fixtures only.  They must not import the
simulator runtime or PROFILE_DEFINITIONS, otherwise the expected values would
no longer be independent of the implementation under review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GOLDEN_DIR = Path(__file__).parent / "golden" / "simulator"
FORMAL_PATH = GOLDEN_DIR / "trap_formal.json"
LEGACY_PATH = GOLDEN_DIR / "trap_legacy_dashboard_v1.json"

FORMAL_NOTIFICATION = "1.3.6.1.4.1.32828.2.1.0.4"
FORMAL_LEVEL = "1.3.6.1.4.1.32828.2.1.0.2"
FORMAL_MESSAGE = "1.3.6.1.4.1.32828.2.1.0.3"
LEGACY_NOTIFICATION = "1.3.6.1.4.1.32828.5.0.4"
LEGACY_LEVEL = "1.3.6.1.4.1.32828.5.1.0.2"
LEGACY_MESSAGE = "1.3.6.1.4.1.32828.5.1.0.3"
KNOWN_WRONG_LEGACY_NOTIFICATION = "1.3.6.1.4.1.32828.5.1.0.4"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _objects_by_name(document: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in document[key]}


def test_formal_trap_contract_is_local_snapshot_derived() -> None:
    formal = _load(FORMAL_PATH)

    assert formal["schema_version"] == 1
    assert formal["layout_id"] == "gud-general-notification-formal"
    assert (
        formal["evidence_status"]
        == "local-device-dictionary-snapshot-and-field-capture-confirmed"
    )
    assert (
        formal["source_assurance"]
        == "local-curated-snapshot-not-verified-against-original-mib-in-this-run"
    )
    assert formal["notification"] == {
        "name": "generalNotification",
        "oid": FORMAL_NOTIFICATION,
        "syntax": "NOTIFICATION-TYPE",
        "vendor_objects_in_declared_order": ["level", "message"],
    }

    envelope = _objects_by_name(formal, "snmpv2_notification_envelope")
    assert envelope["snmpTrapOID.0"]["expected_value"] == FORMAL_NOTIFICATION

    objects = _objects_by_name(formal, "vendor_objects")
    assert set(objects) == {"level", "message"}
    assert objects["level"]["oid"] == FORMAL_LEVEL
    assert objects["level"]["syntax"] == "Integer32"
    assert objects["level"]["enum"] is None
    assert objects["level"]["severity_mapping"] is None
    assert objects["message"]["oid"] == FORMAL_MESSAGE
    assert objects["message"]["syntax"] == "DisplayString"

    matching = formal["matching_contract"]
    assert matching["notification_oid_must_equal"] == FORMAL_NOTIFICATION
    assert matching["required_vendor_varbind_oids"] == [
        FORMAL_LEVEL,
        FORMAL_MESSAGE,
    ]
    assert matching["single_oid_match_is_sufficient"] is False
    assert matching["unknown_varbinds"] == "preserve"

    applicability = formal["profile_applicability"]
    assert set(applicability["local_device_dictionary_defined"]) == {
        "ccdm_matrix",
        "visionxs_cpu",
        "visionxs_con",
        "dp12_mux_atc",
    }
    assert applicability["capture_observed_only"] == ["ccdc_legacy"]


def test_legacy_trap_contract_is_capture_only_and_separate() -> None:
    legacy = _load(LEGACY_PATH)

    assert legacy["schema_version"] == 1
    assert legacy["layout_id"] == "legacy-dashboard-simulator-v1"
    assert legacy["evidence_status"] == "project-capture-derived-not-vendor-mib"
    assert (
        legacy["source_assurance"]
        == "repository-compatibility-plan-and-local-capture-only"
    )
    assert legacy["profile_applicability"]["vendor_mib_defined"] == []
    assert legacy["profile_applicability"]["project_compatibility_only"] == [
        "ccdc_legacy"
    ]
    assert legacy["notification"]["oid"] == LEGACY_NOTIFICATION

    envelope = _objects_by_name(legacy, "snmpv2_notification_envelope")
    assert envelope["snmpTrapOID.0"]["expected_value"] == LEGACY_NOTIFICATION

    objects = _objects_by_name(legacy, "capture_derived_objects")
    assert set(objects) == {"legacyLevel", "legacyMessage"}
    assert objects["legacyLevel"]["oid"] == LEGACY_LEVEL
    assert objects["legacyLevel"]["enum"] is None
    assert objects["legacyLevel"]["severity_mapping"] is None
    assert objects["legacyMessage"]["oid"] == LEGACY_MESSAGE

    matching = legacy["matching_contract"]
    assert matching["notification_oid_must_equal"] == LEGACY_NOTIFICATION
    assert matching["required_capture_varbind_oids"] == [
        LEGACY_LEVEL,
        LEGACY_MESSAGE,
    ]
    assert (
        matching["known_incompatible_implementation_notification_oid"]
        == KNOWN_WRONG_LEGACY_NOTIFICATION
    )
    assert matching["single_oid_match_is_sufficient"] is False
    assert legacy["semantic_limits"]["physical_device_compatibility_claimed"] is False

    assert LEGACY_NOTIFICATION != FORMAL_NOTIFICATION
    assert LEGACY_LEVEL != FORMAL_LEVEL
    assert LEGACY_MESSAGE != FORMAL_MESSAGE


def test_trap_golden_has_no_external_or_raw_mib_provenance() -> None:
    forbidden_fragments = (
        "h:\\work\\i\\kvm\\new",
        "docs/reference/docs/evidence",
        "gud-generaltraps-mib.txt:",
    )

    for path in (FORMAL_PATH, LEGACY_PATH):
        values = tuple(item.casefold() for item in _strings(_load(path)))
        for forbidden in forbidden_fragments:
            assert all(forbidden not in item for item in values), (
                f"{path.name} contains forbidden provenance {forbidden!r}"
            )

    formal = _load(FORMAL_PATH)
    sources = formal["repository_document_evidence"]["repository_sources"]
    assert sources
    assert all(
        source.startswith("docs/reference/docs/devices/") for source in sources
    )
    assert (
        formal["repository_document_evidence"]["interaction_boundary_source"]
        == "docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md:136-162"
    )
