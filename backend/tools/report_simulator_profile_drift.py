"""Full-semantic L2 Profile drift report against independent L1 goldens."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
GOLDEN_ROOT = BACKEND_ROOT / "tests" / "golden" / "simulator"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PROFILE_GOLDENS = {
    "ccdc_legacy": "ccdc_legacy.objects.json",
    "ccdm_matrix": "ccdm.objects.json",
    "visionxs_cpu": "visionxs_cpu.objects.json",
    "visionxs_con": "visionxs_con.objects.json",
    "dp12_mux_atc": "dp12_mux_atc.objects.json",
}


def _load_golden(filename: str) -> dict[str, Any]:
    return json.loads((GOLDEN_ROOT / filename).read_text(encoding="utf-8"))


def _object_differences(
    golden: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    golden_by_oid = {item["oid"]: item for item in golden}
    current_by_oid = {item["oid"]: item for item in current}
    differences: list[dict[str, Any]] = []
    for oid in sorted(
        set(golden_by_oid) & set(current_by_oid),
        key=lambda value: tuple(int(arc) for arc in value.split(".")),
    ):
        expected = golden_by_oid[oid]
        actual = current_by_oid[oid]
        fields = {
            key: {"golden": expected.get(key), "current": actual.get(key)}
            for key in expected
            if expected.get(key) != actual.get(key)
        }
        if fields:
            differences.append({"oid": oid, "fields": fields})
    return differences


def build_report() -> dict[str, Any]:
    from simulator.profile_catalog import (
        CATALOG_PATH,
        CATALOG_SHA256,
        PROFILE_CATALOG,
        profile_schema_metadata,
        project_l1_manifest,
        runtime_catalog_read_paths,
    )
    from simulator.profile_fixture import (
        DEFAULT_FIXTURE_PATH,
        DEFAULT_FIXTURE_SHA256,
        runtime_fixture_read_paths,
        validate_fixture_schema,
    )
    from simulator.profiles import (
        DEFAULT_FIXTURES,
        default_row_provenance,
    )

    results: dict[str, Any] = {}
    for profile_id, filename in PROFILE_GOLDENS.items():
        golden = _load_golden(filename)
        profile = PROFILE_CATALOG[profile_id]
        projected = project_l1_manifest(profile)
        golden_by_oid = {item["oid"]: item for item in golden["objects"]}
        current_by_oid = {item["oid"]: item for item in projected["objects"]}

        fixture_errors: list[str] = []
        fixture = DEFAULT_FIXTURES.get(profile_id)
        if fixture is not None:
            try:
                validate_fixture_schema(profile, fixture)
            except (TypeError, ValueError) as exc:
                fixture_errors.append(str(exc))
        explicit_fixture_tables = []
        if fixture is not None:
            explicit_fixture_tables = [
                {
                    "table": table.table_id,
                    "row_source": "explicit-fixture",
                    "configured_row_count": len(table.rows),
                    "index_tuples": [
                        [value for _, value in row.indexes]
                        for row in table.rows
                    ],
                }
                for table in fixture.tables
            ]
        row_provenance = default_row_provenance(profile_id)

        metadata = json.dumps(
            profile_schema_metadata(profile),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        result = {
            "profile_id": profile_id,
            "golden_file": str(
                (GOLDEN_ROOT / filename).relative_to(REPO_ROOT)
            ).replace("\\", "/"),
            "golden_evidence_status": golden["evidence_status"],
            "profile_version": profile.profile_version,
            "evidence_version": profile.evidence_version,
            "source_manifest_sha256": profile.source_manifest_sha256,
            "golden_table_count": golden["table_count"],
            "current_table_count": len(profile.tables),
            "golden_gettable_leaf_count": golden["gettable_count"],
            "current_declared_leaf_count": profile.gettable_leaf_count,
            "missing_definition_oids": sorted(
                set(golden_by_oid) - set(current_by_oid)
            ),
            "unexpected_definition_oids": sorted(
                set(current_by_oid) - set(golden_by_oid)
            ),
            "duplicate_definition_oids": (
                []
                if len(current_by_oid) == len(projected["objects"])
                else ["duplicate-present"]
            ),
            "semantic_differences": _object_differences(
                golden["objects"], projected["objects"]
            ),
            "table_semantics_match": projected["tables"] == golden["tables"],
            "sys_object_id_matches": (
                projected["sys_object_id"] == golden["sys_object_id"]["oid"]
            ),
            "evidence_status_matches": (
                projected["evidence_status"] == golden["evidence_status"]
            ),
            "invalid_literal_defaults": fixture_errors,
            "fixture_validation_errors": fixture_errors,
            "explicit_fixture_row_tables": explicit_fixture_tables,
            "default_row_provenance": row_provenance,
            "implicit_derived_tables": sorted(
                table_id
                for table_id, source in row_provenance.items()
                if source
                not in {
                    "explicit-static-fixture",
                    "explicit-static-fixture-filtered-by-scenario-endpoint",
                    "no-default-rows",
                    "project-legacy-scenario-entities",
                }
            ),
            "metadata_compact_bytes": len(metadata),
        }
        result["matches_l1_golden"] = not any(
            [
                result["golden_table_count"] != result["current_table_count"],
                result["missing_definition_oids"],
                result["unexpected_definition_oids"],
                result["duplicate_definition_oids"],
                result["semantic_differences"],
                not result["table_semantics_match"],
                not result["sys_object_id_matches"],
                not result["evidence_status_matches"],
                result["fixture_validation_errors"],
                result["implicit_derived_tables"],
            ]
        )
        results[profile_id] = result

    runtime_read_paths = (
        *runtime_catalog_read_paths(),
        *runtime_fixture_read_paths(),
    )
    production_reads_test_goldens = any(
        "backend/tests/golden" in str(path).replace("\\", "/")
        for path in runtime_read_paths
    )
    return {
        "schema_version": 2,
        "purpose": (
            "L1-to-L2 full-semantic Profile catalog and explicit fixture drift"
        ),
        "golden_source_policy": (
            "local curated device dictionary snapshot; original MIB not "
            "reverified in this run"
        ),
        "runtime_catalog": str(CATALOG_PATH.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "runtime_catalog_sha256": CATALOG_SHA256,
        "runtime_fixture_artifact": str(
            DEFAULT_FIXTURE_PATH.relative_to(REPO_ROOT)
        ).replace("\\", "/"),
        "runtime_fixture_sha256": DEFAULT_FIXTURE_SHA256,
        "production_loader_read_paths": [
            str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for path in runtime_read_paths
        ],
        "production_loader_reads_test_goldens": production_reads_test_goldens,
        "profiles": results,
        "ok": all(item["matches_l1_golden"] for item in results.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report typed Simulator Profile drift from L1 golden"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
