"""Generate the production L2 Profile catalog from the Accepted L1 goldens.

The generated JSON is a checked-in runtime artifact.  Production code reads
only ``backend/simulator/catalog/l2_profiles.json``; it never imports or opens
``backend/tests/golden``.  This tool is the explicit, reviewable build bridge
between the two layers and rejects any unreviewed L1 digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_ROOT = REPO_ROOT / "backend" / "tests" / "golden" / "simulator"
OUTPUT = REPO_ROOT / "backend" / "simulator" / "catalog" / "l2_profiles.json"

ACCEPTED_MANIFESTS = {
    "ccdm.objects.json": "dc2fa2a8ef223348be2a49cf2456094099680a54ad58ee60838294ec042a952d",
    "visionxs_cpu.objects.json": "1fa9a8c4ca001cc33ec7c9fe6d7949fe8bb31472f505e028acdbecf1b9d0a08a",
    "visionxs_con.objects.json": "d40bcf845ae091ef09071d335187bf8f49393b6226bc46c2be728f5581900b40",
    "dp12_mux_atc.objects.json": "8225e8ecc2d86c2a7c85ebd02040d2bdbbdd0e8b998880e25da77a128c1c81cf",
    "ccdc_legacy.objects.json": "f8027d3567ac23259718f20a63363be2391599652c2255cf532b603a6d52d858",
}


def _snake(name: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    if not value or not value[0].isalpha():
        raise ValueError(f"cannot build canonical ID for {name!r}")
    return value


def _source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "document": source["document"],
        "line_start": source["line_start"],
        "line_end": source["line_end"],
        "upstream_reference_as_recorded": source.get(
            "upstream_reference_as_recorded"
        ),
        "upstream_reference_reverified_in_this_run": source.get(
            "upstream_reference_reverified_in_this_run", False
        ),
    }


def _leaf(item: dict[str, Any], *, canonical: str) -> dict[str, Any]:
    optional_group = (
        f"optional_{canonical}" if item["compliance"] == "optional" else None
    )
    return {
        "module": item["module"],
        "vendor_name": item["name"],
        "canonical_field": canonical,
        "ui_label": f"simulator.fields.{canonical}",
        "source": _source(item["source"]),
        "oid": item["oid"],
        "syntax": item["syntax"],
        "max_access": item["max_access"],
        "enum": (
            {"name": item["syntax"], "values": item["enum"]}
            if item["enum"] is not None
            else None
        ),
        "value_range": item["range"],
        "unit": item["unit"],
        "compliance": item["compliance"],
        "optional_group": optional_group,
    }


def _build_profile(filename: str) -> dict[str, Any]:
    path = GOLDEN_ROOT / filename
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    accepted = ACCEPTED_MANIFESTS[filename]
    if digest != accepted:
        raise ValueError(
            f"{filename} digest changed: expected {accepted}, actual {digest}; "
            "return to L1 review before rebuilding L2"
        )
    golden = json.loads(raw)
    objects = golden["objects"]
    by_oid = {item["oid"]: item for item in objects}
    table_name_counts = Counter(_snake(item["name"]) for item in golden["tables"])

    scalars = [
        _leaf(item, canonical=_snake(item["name"]))
        for item in objects
        if item["kind"] == "scalar"
    ]
    tables: list[dict[str, Any]] = []
    for table in golden["tables"]:
        table_id = _snake(table["name"])
        if table_name_counts[table_id] > 1:
            table_id = f"{_snake(table['module'])}_{table_id}"

        ordered_indexes = []
        for position, index_name in enumerate(table["index_order"]):
            candidates = [
                item
                for item in objects
                if item["kind"] == "index"
                and item["module"] == table["module"]
                and item["name"] == index_name
            ]
            if len(candidates) != 1:
                raise ValueError(
                    f"{golden['profile_id']} {table['name']} index {index_name}: "
                    f"expected one object, found {len(candidates)}"
                )
            item = candidates[0]
            ordered_indexes.append(
                {
                    "module": item["module"],
                    "vendor_name": item["name"],
                    "canonical_field": _snake(item["name"]),
                    "ui_label": f"simulator.fields.{_snake(item['name'])}",
                    "source": _source(item["source"]),
                    "oid": item["oid"],
                    "syntax": item["syntax"],
                    "value_range": item["range"],
                    "position": position,
                    "defined_here": item["oid"].startswith(f"{table['entry_oid']}."),
                }
            )

        prefix = f"{table['entry_oid']}."
        columns = [
            _leaf(item, canonical=_snake(item["name"]))
            | {
                "column": int(item["oid"][len(prefix) :]),
                "table_id": table_id,
                "index_order": table["index_order"],
            }
            for item in objects
            if item["kind"] == "column"
            and item["module"] == table["module"]
            and item["oid"].startswith(prefix)
            and "." not in item["oid"][len(prefix) :]
        ]
        columns.sort(key=lambda item: item["column"])
        tables.append(
            {
                "module": table["module"],
                "vendor_name": table["name"],
                "canonical_field": table_id,
                "ui_label": f"simulator.tables.{table_id}",
                "source": _source(table["source"]),
                "oid": table["oid"],
                "entry_vendor_name": table["entry_name"],
                "entry_oid": table["entry_oid"],
                "indexes": ordered_indexes,
                "columns": columns,
            }
        )

    return {
        "profile_id": golden["profile_id"],
        "product": golden["product"],
        "profile_version": "1.0.0",
        "schema_version": 1,
        "sys_object_id": golden["sys_object_id"]["oid"],
        "sys_object_id_match": golden["sys_object_id"]["match"],
        "evidence_status": golden["evidence_status"],
        "evidence_version": f"schema=1;sha256={digest}",
        "source_assurance": golden["source_contract"]["source_assurance"],
        "source_manifest": (
            f"backend/tests/golden/simulator/{filename}"
        ),
        "source_manifest_sha256": digest,
        "scalars": scalars,
        "tables": tables,
    }


def build_catalog() -> dict[str, Any]:
    profiles = [
        _build_profile(filename)
        for filename in ACCEPTED_MANIFESTS
    ]
    profiles.sort(key=lambda item: item["profile_id"])
    return {
        "catalog_schema_version": 1,
        "catalog_kind": "simulator-l2-profile-catalog",
        "generator": "backend/tools/build_simulator_profile_catalog.py",
        "source_contract": (
            "Accepted L1 local curated device dictionary snapshot; "
            "original MIB not reverified in this run"
        ),
        "profiles": profiles,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(
        build_catalog(), ensure_ascii=False, indent=2, sort_keys=False
    ) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"runtime catalog is stale: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
