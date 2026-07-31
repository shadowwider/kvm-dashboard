"""Build the L1 simulator object golden manifests from repository evidence.

The declarations in this file are a machine-readable transcription of:

* docs/reference/docs/devices/ccdm-controlcenter-digital.md
* docs/reference/docs/devices/visionxs-cpu-con.md
* docs/reference/docs/devices/dp12-mux-atc.md

It deliberately does not import simulator profiles or read source material
outside this repository.  The generated JSON is the independent L1 protocol
fact source used by later layers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "backend" / "tests" / "golden" / "simulator"

CCDM_DOC = "docs/reference/docs/devices/ccdm-controlcenter-digital.md"
VISION_DOC = "docs/reference/docs/devices/visionxs-cpu-con.md"
DP_DOC = "docs/reference/docs/devices/dp12-mux-atc.md"
COMPAT_DOC = "docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md"

P = "1.3.6.1.4.1.32828.3.257.10"
C = "1.3.6.1.4.1.32828.3.768.768"
K = "1.3.6.1.4.1.32828.3.769.768"
D = "1.3.6.1.4.1.32828.3.1792.17"


ENUMS: dict[str, dict[str, int]] = {
    "Boolean": {"false": 0, "true": 1},
    "PowerStatus": {"off": 0, "on": 1},
    "PowerSupplyStatus": {"off": 0, "on": 1, "absent": 2, "failure": 3},
    "NetworkInterfaceStatus": {"down": 0, "up": 1},
    "CatPortStatus": {"down": 0, "up": 1},
    "FiberPortStatus": {"noModule": 0, "deactivated": 1, "down": 2, "up": 3},
    "MultiPortStatus": {"noModule": 0, "deactivated": 1, "down": 2, "up": 3},
    "TrunkPortStatus": {"noModule": 0, "deactivated": 1, "down": 2, "up": 3},
    "FunctionStatus": {"failure": 0, "ok": 1},
    "DeviceStatus2": {"offline": 0, "online": 1},
    "DeviceStatus3": {"offline": 0, "online": 1, "ready": 2},
    "RaidStatus": {
        "failure": 0,
        "resync": 1,
        "recover": 2,
        "check": 3,
        "repair": 4,
        "ok": 5,
    },
    "ConnectionStatus": {"notConnected": 0, "connected": 1},
    "KeyboardMouseStatus": {"none": 0, "keyboard": 1, "mouse": 2, "keyboardMouse": 3},
    "GpioValue": {"inactive": 0, "low": 1, "high": 2},
    "UsbHidStatus": {"notConnected": 0, "connected": 1, "initialized": 2},
    "AccessStatus": {"local": 0, "remote": 1, "localExclusive": 2, "remoteExclusive": 3},
    "VideoType": {"none": 0, "vga": 1, "dvisl": 2, "dvidl": 3, "dmdp": 4, "dp": 5, "hdmi": 6},
    "LinkStatus": {"down": 0, "up": 1, "crossed": 2},
    "TransparentUsbLinkStatus": {"down": 0, "up": 1},
    "Usb20Status": {"inactive": 0, "active": 1},
    "Usb30Status": {"inactive": 0, "active": 1},
    "SfpModuleStatus": {"noModule": 0, "moduleDeactivated": 1, "down": 2, "up": 3},
}


def doc_source(path: str, line: int, vendor_reference: str) -> dict[str, Any]:
    return {
        "document": path,
        "line_start": line,
        "line_end": line,
        "upstream_reference_as_recorded": vendor_reference,
        "upstream_reference_reverified_in_this_run": False,
    }


def enum_for(syntax: str, enum_name: str | None = None) -> dict[str, int] | None:
    key = enum_name or syntax
    values = ENUMS.get(key)
    return dict(values) if values else None


def unit(value: str, evidence: str) -> dict[str, str]:
    return {"value": value, "evidence": evidence}


class ManifestBuilder:
    def __init__(
        self,
        profile_id: str,
        product: str,
        sys_object_id: str,
        source_documents: list[str],
        sys_source: dict[str, Any],
        *,
        evidence_status: str = "local-device-dictionary-snapshot",
        source_authority: str = "local-curated-device-dictionary-snapshot",
    ) -> None:
        self.profile_id = profile_id
        self.product = product
        self.sys_object_id = sys_object_id
        self.source_document_paths = source_documents
        self.sys_source = sys_source
        self.evidence_status = evidence_status
        self.source_authority = source_authority
        self.objects: list[dict[str, Any]] = []
        self.tables: list[dict[str, Any]] = []

    def add_object(
        self,
        *,
        name: str,
        module: str,
        oid: str,
        kind: str,
        syntax: str | None,
        max_access: str,
        index_order: list[str] | None,
        compliance: str | None,
        source: dict[str, Any],
        enum_name: str | None = None,
        value_range: tuple[int, int] | None = None,
        value_unit: dict[str, str] | None = None,
    ) -> None:
        gettable = kind in {"scalar", "column"} and max_access != "not-accessible"
        if kind == "scalar":
            get_oid_template = f"{oid}.0"
            instance_rule = "scalar-zero"
        elif kind == "column":
            suffix = ".".join(f"{{{item}}}" for item in (index_order or []))
            get_oid_template = f"{oid}.{suffix}" if suffix else oid
            instance_rule = "index-suffix"
        else:
            get_oid_template = None
            instance_rule = "none"

        optional_group: bool | None
        if compliance == "optional":
            optional_group = True
        elif compliance == "mandatory":
            optional_group = False
        else:
            optional_group = None

        self.objects.append(
            {
                "name": name,
                "qualified_name": f"{module}::{name}",
                "module": module,
                "oid": oid,
                "kind": kind,
                "syntax": syntax,
                "max_access": max_access,
                "enum": enum_for(syntax, enum_name),
                "range": (
                    {"min": value_range[0], "max": value_range[1]}
                    if value_range is not None
                    else None
                ),
                "unit": value_unit,
                "default": None,
                "index_order": index_order or [],
                "compliance": compliance or "unlisted",
                "optional_group": optional_group,
                "gettable": gettable,
                "writable": max_access in {"read-write", "read-create", "write-only"},
                "instance_rule": instance_rule,
                "get_oid_template": get_oid_template,
                "source": source,
            }
        )

    def scalar(
        self,
        name: str,
        module: str,
        oid: str,
        syntax: str,
        source: dict[str, Any],
        *,
        compliance: str = "mandatory",
        max_access: str = "read-only",
        enum_name: str | None = None,
        value_range: tuple[int, int] | None = None,
        value_unit: dict[str, str] | None = None,
    ) -> None:
        self.add_object(
            name=name,
            module=module,
            oid=oid,
            kind="scalar",
            syntax=syntax,
            max_access=max_access,
            index_order=[],
            compliance=compliance,
            source=source,
            enum_name=enum_name,
            value_range=value_range,
            value_unit=value_unit,
        )

    def table(
        self,
        *,
        module: str,
        name: str,
        entry_name: str,
        oid: str,
        indexes: list[tuple[str, tuple[int, int] | None]],
        defined_indexes: list[str],
        columns: list[tuple[str, int, str, str | None, tuple[int, int] | None, dict[str, str] | None]],
        source: dict[str, Any],
        compliance: str = "mandatory",
    ) -> None:
        index_names = [item[0] for item in indexes]
        self.add_object(
            name=name,
            module=module,
            oid=oid,
            kind="table",
            syntax=None,
            max_access="not-accessible",
            index_order=index_names,
            compliance=None,
            source=source,
        )
        self.add_object(
            name=entry_name,
            module=module,
            oid=f"{oid}.1",
            kind="entry",
            syntax=None,
            max_access="not-accessible",
            index_order=index_names,
            compliance=None,
            source=source,
        )

        index_map = dict(indexes)
        for position, index_name in enumerate(defined_indexes, start=1):
            self.add_object(
                name=index_name,
                module=module,
                oid=f"{oid}.1.{position}",
                kind="index",
                syntax="Integer32",
                max_access="not-accessible",
                index_order=index_names,
                compliance=None,
                source=source,
                value_range=index_map[index_name],
            )

        first_column = 1 + len(defined_indexes)
        for offset, (column_name, column_number, syntax, enum_name, value_range, value_unit) in enumerate(columns):
            del offset
            if column_number < first_column:
                raise ValueError(f"{module}::{column_name} overlaps a locally defined index")
            self.add_object(
                name=column_name,
                module=module,
                oid=f"{oid}.1.{column_number}",
                kind="column",
                syntax=syntax,
                max_access="read-only",
                index_order=index_names,
                compliance=compliance,
                source=source,
                enum_name=enum_name,
                value_range=value_range,
                value_unit=value_unit,
            )

        self.tables.append(
            {
                "name": name,
                "qualified_name": f"{module}::{name}",
                "module": module,
                "oid": oid,
                "entry_name": entry_name,
                "entry_oid": f"{oid}.1",
                "index_order": index_names,
                "index_ranges": {
                    index_name: (
                        {"min": bounds[0], "max": bounds[1]} if bounds is not None else None
                    )
                    for index_name, bounds in indexes
                },
                "source": source,
            }
        )

    def build(self) -> dict[str, Any]:
        source_documents = []
        for relative in self.source_document_paths:
            path = REPO_ROOT / relative
            raw = path.read_bytes()
            source_documents.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "line_count": len(raw.decode("utf-8").splitlines()),
                }
            )
        ordered_objects = sorted(self.objects, key=lambda item: tuple(int(part) for part in item["oid"].split(".")))
        return {
            "schema_version": 1,
            "manifest_kind": "simulator-mib-object-golden",
            "profile_id": self.profile_id,
            "product": self.product,
            "evidence_status": self.evidence_status,
            "source_contract": {
                "authority": self.source_authority,
                "source_assurance": (
                    "local-curated-snapshot-not-verified-against-original-mib-in-this-run"
                ),
                "generator": "backend/tools/build_simulator_mib_golden.py",
                "independent_of_simulator_profiles": True,
                "prohibited_inputs": [
                    "backend/simulator/profiles.py",
                    "PROFILE_DEFINITIONS",
                    "repository-external-source-paths",
                ],
            },
            "source_documents": source_documents,
            "sys_object_id": {
                "oid": self.sys_object_id,
                "match": "exact",
                "source": self.sys_source,
            },
            "object_count": len(ordered_objects),
            "gettable_count": sum(1 for item in ordered_objects if item["gettable"]),
            "not_accessible_count": sum(
                1 for item in ordered_objects if item["max_access"] == "not-accessible"
            ),
            "table_count": len(self.tables),
            "tables": sorted(self.tables, key=lambda item: tuple(int(part) for part in item["oid"].split("."))),
            "objects": ordered_objects,
            "boundaries": [
                "Object definitions are distinct from runtime table rows.",
                "Index ranges are syntax bounds, not evidence that every row exists.",
                "No fixture rows or simulator defaults are part of this manifest.",
            ],
        }


def ccdm_manifest() -> dict[str, Any]:
    b = ManifestBuilder(
        "ccdm_matrix",
        "ControlCenter-Digital matrix",
        P,
        [CCDM_DOC],
        doc_source(CCDM_DOC, 5, "ccdm/GUD-SMI-MIB.txt:26-31,45-49,90-94,108-112"),
    )
    module = "GUD-CCDM-MIB"
    base_scalars = [
        ("deviceId", f"{P}.2.1.1", "DisplayString", 38, "ccdm/GUD-CCDM-MIB.txt:193-199", None, None, None),
        ("deviceCl", f"{P}.2.1.2", "DisplayString", 39, "ccdm/GUD-CCDM-MIB.txt:201-207", None, None, None),
        ("deviceType", f"{P}.2.1.3", "DisplayString", 40, "ccdm/GUD-CCDM-MIB.txt:209-215", None, None, None),
        ("serialNumber", f"{P}.2.1.4", "DisplayString", 41, "ccdm/GUD-CCDM-MIB.txt:217-223", None, None, None),
        ("etherAddress0", f"{P}.2.1.5", "PhysAddress", 42, "ccdm/GUD-CCDM-MIB.txt:225-239", None, None, None),
        ("etherAddress1", f"{P}.2.1.6", "PhysAddress", 42, "ccdm/GUD-CCDM-MIB.txt:225-239", None, None, None),
        ("firmwareVersion", f"{P}.2.2.1", "DisplayString", 43, "ccdm/GUD-CCDM-MIB.txt:243-249", None, None, None),
        ("switchTemperature", f"{P}.2.3.4", "DisplayString", 44, "ccdm/GUD-CCDM-MIB.txt:253-260", None, None, unit("Deg C", "commented-units")),
        ("controllerTemperature", f"{P}.2.3.5", "DisplayString", 45, "ccdm/GUD-CCDM-MIB.txt:262-269", None, None, unit("Deg C", "commented-units")),
        ("raidStatusDevice1", f"{P}.2.3.6", "RaidStatus", 46, "ccdm/GUD-CCDM-MIB.txt:115-126,271-285", None, None, None),
        ("raidStatusDevice2", f"{P}.2.3.7", "RaidStatus", 46, "ccdm/GUD-CCDM-MIB.txt:115-126,271-285", None, None, None),
        ("functionSwitch", f"{P}.2.3.9", "FunctionStatus", 47, "ccdm/GUD-CCDM-MIB.txt:97-104,287-293", None, None, None),
        ("powerCurrent", f"{P}.2.3.500", "DisplayString", 48, "ccdm/GUD-CCDM-MIB.txt:968-975", None, None, unit("A", "commented-units")),
        ("networkInterface0", f"{P}.2.3.506", "NetworkInterfaceStatus", 49, "ccdm/GUD-CCDM-MIB.txt:46-53,977-991", None, None, None),
        ("networkInterface1", f"{P}.2.3.507", "NetworkInterfaceStatus", 49, "ccdm/GUD-CCDM-MIB.txt:46-53,977-991", None, None, None),
        ("generalErrorCode", f"{P}.2.1000.1", "Integer32", 50, "ccdm/GUD-CCDM-MIB.txt:994-1008", None, None, None),
        ("generalErrorMessage", f"{P}.2.1000.2", "DisplayString", 50, "ccdm/GUD-CCDM-MIB.txt:994-1008", None, None, None),
    ]
    for name, oid, syntax, line, vendor_ref, enum_name, value_range, value_unit in base_scalars:
        compliance = "optional" if name.startswith("generalError") else "mandatory"
        b.scalar(
            name,
            module,
            oid,
            syntax,
            doc_source(CCDM_DOC, line, vendor_ref),
            compliance=compliance,
            enum_name=enum_name,
            value_range=value_range,
            value_unit=value_unit,
        )

    base_tables = [
        (
            "fanTable", "fanTableEntry", f"{P}.2.3.1000", [("fanIndex", (1, 20))],
            [("fanName", 2, "DisplayString", None, None, None), ("fanSpeed", 3, "Integer32", None, (0, 10000), unit("RPM", "description"))],
            56, "ccdm/GUD-CCDM-MIB.txt:299-344",
        ),
        (
            "powerSupplyTable", "powerSupplyTableEntry", f"{P}.2.3.1001", [("powerSupplyIndex", (1, 3))],
            [
                ("powerSupplyStatus", 2, "PowerSupplyStatus", None, None, None),
                ("powerSupplyTemperature", 3, "DisplayString", None, None, None),
                ("powerSupplyVoltage", 4, "DisplayString", None, None, None),
                ("powerSupplyFanFunction", 5, "FunctionStatus", None, None, None),
            ],
            57, "ccdm/GUD-CCDM-MIB.txt:35-44,97-104,350-413",
        ),
    ]
    card_specs = [
        ("Cat", 1002, 1003, "CatPortStatus", 58, 59, 1),
        ("Fiber", 1004, 1005, "FiberPortStatus", 60, 61, 4),
        ("Multi", 1006, 1007, "MultiPortStatus", 62, 63, 4),
        ("Trunk", 1008, 1009, "TrunkPortStatus", 64, 65, 4),
    ]
    card_references = {
        "Cat": "ccdm/GUD-CCDM-MIB.txt:106-113,97-104,419-491",
        "Fiber": "ccdm/GUD-CCDM-MIB.txt:97-113,536-608",
        "Multi": "ccdm/GUD-CCDM-MIB.txt:97-113,680-752",
        "Trunk": "ccdm/GUD-CCDM-MIB.txt:97-113,824-896",
    }
    for table_name, entry_name, oid, indexes, columns, line, vendor_ref in base_tables:
        b.table(
            module=module,
            name=table_name,
            entry_name=entry_name,
            oid=oid,
            indexes=indexes,
            defined_indexes=[indexes[-1][0]],
            columns=columns,
            source=doc_source(CCDM_DOC, line, vendor_ref),
        )
    for family, card_no, port_no, status_syntax, card_line, port_line, port_column_count in card_specs:
        prefix = f"ioCard{family}"
        b.table(
            module=module,
            name=f"{prefix}Table",
            entry_name=f"{prefix}Entry",
            oid=f"{P}.2.3.{card_no}",
            indexes=[(f"{prefix}Index", (1, 19))],
            defined_indexes=[f"{prefix}Index"],
            columns=[
                (f"{prefix}Id", 2, "Integer32", None, None, None),
                (f"{prefix}Status", 3, "DeviceStatus", "DeviceStatus2", None, None),
                (f"{prefix}Function", 4, "FunctionStatus", None, None, None),
                (f"{prefix}Temperature", 5, "DisplayString", None, None, None),
                (f"{prefix}MatrixSlot", 6, "Integer32", None, None, None),
            ],
            source=doc_source(
                CCDM_DOC,
                card_line,
                card_references[family],
            ),
        )
        port_columns = [(f"{prefix}PortStatus", 2, status_syntax, None, None, None)]
        if port_column_count == 4:
            port_columns.extend(
                [
                    (f"{prefix}TxPower", 3, "DisplayString", None, None, None),
                    (f"{prefix}RxPower", 4, "DisplayString", None, None, None),
                    (f"{prefix}SfpType", 5, "DisplayString", None, None, None),
                ]
            )
        b.table(
            module=module,
            name=f"{prefix}PortTable",
            entry_name=f"{prefix}PortEntry",
            oid=f"{P}.2.3.{port_no}",
            indexes=[(f"{prefix}Index", (1, 19)), (f"{prefix}PortIndex", (1, 16))],
            defined_indexes=[f"{prefix}PortIndex"],
            columns=port_columns,
            source=doc_source(
                CCDM_DOC,
                port_line,
                {
                    "Cat": "ccdm/GUD-CCDM-MIB.txt:55-62,493-530",
                    "Fiber": "ccdm/GUD-CCDM-MIB.txt:64-73,610-674",
                    "Multi": "ccdm/GUD-CCDM-MIB.txt:75-84,754-818",
                    "Trunk": "ccdm/GUD-CCDM-MIB.txt:86-95,898-962",
                }[family],
            ),
        )

    def module_main_table(
        module_name: str,
        table_name: str,
        entry_name: str,
        root: str,
        index_name: str,
        line: int,
        vendor_ref: str,
        columns: list[tuple[str, int, str, str | None, tuple[int, int] | None, dict[str, str] | None]],
    ) -> None:
        b.table(
            module=module_name,
            name=table_name,
            entry_name=entry_name,
            oid=f"{root}.1000",
            indexes=[(index_name, (1, 2000))],
            defined_indexes=[index_name],
            columns=columns,
            source=doc_source(CCDM_DOC, line, vendor_ref),
        )

    con = "GUD-CCDMCON-MIB"
    con_columns = [
        ("id", 2, "DisplayString", None, None, None),
        ("cl", 3, "DisplayString", None, None, None),
        ("name", 4, "DisplayString", None, None, None),
        ("deviceStatus", 5, "DeviceStatus", "DeviceStatus3", None, None),
        ("mainPower", 6, "PowerStatus", None, None, None),
        ("redundantPower", 7, "PowerStatus", None, None, None),
        ("temperature1", 8, "DisplayString", None, None, None),
        ("consolePS2Connection", 9, "KeyboardMouseStatus", None, None, None),
        ("consoleUSBConnection", 10, "KeyboardMouseStatus", None, None, None),
        ("displayConnection", 11, "ConnectionStatus", None, None, None),
        ("displayConnection1", 12, "ConnectionStatus", None, None, None),
        ("displayConnection2", 13, "ConnectionStatus", None, None, None),
        ("displayType", 14, "DisplayString", None, None, None),
        ("displayType1", 15, "DisplayString", None, None, None),
        ("displayType2", 16, "DisplayString", None, None, None),
        ("freeze", 17, "Boolean", None, None, None),
        ("freeze1", 18, "Boolean", None, None, None),
        ("freeze2", 19, "Boolean", None, None, None),
        ("sfpTxPower", 20, "Integer32", None, None, unit("uW", "description")),
        ("sfpTxPower1", 21, "Integer32", None, None, unit("uW", "description")),
        ("sfpTxPower2", 22, "Integer32", None, None, unit("uW", "description")),
        ("sfpRxPower", 23, "Integer32", None, None, unit("uW", "description")),
        ("sfpRxPower1", 24, "Integer32", None, None, unit("uW", "description")),
        ("sfpRxPower2", 25, "Integer32", None, None, unit("uW", "description")),
        ("sfpType", 26, "DisplayString", None, None, None),
        ("sfpType1", 27, "DisplayString", None, None, None),
        ("sfpType2", 28, "DisplayString", None, None, None),
        ("activeTransmissionPort", 29, "Integer32", None, (1, 2), None),
        ("networkInterface0", 30, "NetworkInterfaceStatus", None, None, None),
    ]
    module_main_table(
        con, "userModuleTable", "userModuleEntry", f"{P}.1.1.2.3",
        "userModuleIndex", 69, "ccdm/GUD-CCDMCON-MIB.txt:103-113,138-194", con_columns,
    )
    b.table(
        module=con, name="fanTable", entry_name="fanTableEntry", oid=f"{P}.1.1.2.3.1001",
        indexes=[("userModuleIndex", (1, 2000)), ("fanIndex", (1, 10))],
        defined_indexes=["fanIndex"],
        columns=[("fanName", 2, "DisplayString", None, None, None), ("fanSpeed", 3, "Integer32", None, (0, 10000), unit("RPM", "description"))],
        source=doc_source(CCDM_DOC, 89, "ccdm/GUD-CCDMCON-MIB.txt:432-477"),
    )
    b.table(
        module=con, name="gpioTable", entry_name="gpioTableEntry", oid=f"{P}.1.1.2.3.1002",
        indexes=[("userModuleIndex", (1, 2000)), ("gpioIndex", (1, 4))],
        defined_indexes=["gpioIndex"],
        columns=[("gpioName", 2, "DisplayString", None, None, None), ("gpioValue", 3, "GpioValue", None, None, None)],
        source=doc_source(CCDM_DOC, 90, "ccdm/GUD-CCDMCON-MIB.txt:88-96,483-528"),
    )

    cpu = "GUD-CCDMCPU-MIB"
    cpu_columns = [
        ("id", 2, "DisplayString", None, None, None),
        ("cl", 3, "DisplayString", None, None, None),
        ("name", 4, "DisplayString", None, None, None),
        ("deviceStatus", 5, "DeviceStatus", "DeviceStatus3", None, None),
        ("mainPower", 6, "PowerStatus", None, None, None),
        ("redundantPower", 7, "PowerStatus", None, None, None),
        ("temperature1", 8, "DisplayString", None, None, None),
        ("consolePS2Connection", 9, "KeyboardMouseStatus", None, None, None),
        ("consoleUSBConnection", 10, "KeyboardMouseStatus", None, None, None),
        ("targetPS2Connection", 11, "KeyboardMouseStatus", None, None, None),
        ("targetUsbHid", 12, "UsbHidStatus", None, None, None),
        ("targetVideoCable", 13, "ConnectionStatus", None, None, None),
        ("targetVideoCable1", 14, "ConnectionStatus", None, None, None),
        ("targetVideoCable2", 15, "ConnectionStatus", None, None, None),
        ("targetVideoSignal", 16, "VideoType", None, None, None),
        ("targetVideoSignal1", 17, "VideoType", None, None, None),
        ("targetVideoSignal2", 18, "VideoType", None, None, None),
        ("targetPower", 19, "PowerStatus", None, None, None),
        ("targetAccess", 20, "AccessStatus", None, None, None),
        ("sfpTxPower", 21, "Integer32", None, None, unit("uW", "description")),
        ("sfpRxPower", 22, "Integer32", None, None, unit("uW", "description")),
        ("sfpType", 23, "DisplayString", None, None, None),
        ("networkInterface0", 24, "NetworkInterfaceStatus", None, None, None),
    ]
    module_main_table(
        cpu, "targetModuleTable", "targetModuleEntry", f"{P}.1.2.2.3",
        "targetModuleIndex", 94, "ccdm/GUD-CCDMCPU-MIB.txt:130-140,166-216", cpu_columns,
    )
    b.table(
        module=cpu, name="fanTable", entry_name="fanTableEntry", oid=f"{P}.1.2.2.3.1001",
        indexes=[("targetModuleIndex", (1, 2000)), ("fanIndex", (1, 10))],
        defined_indexes=["fanIndex"],
        columns=[("fanName", 2, "DisplayString", None, None, None), ("fanSpeed", 3, "Integer32", None, (0, 10000), unit("RPM", "description"))],
        source=doc_source(CCDM_DOC, 114, "ccdm/GUD-CCDMCPU-MIB.txt:406-451"),
    )
    b.table(
        module=cpu, name="gpioTable", entry_name="gpioTableEntry", oid=f"{P}.1.2.2.3.1002",
        indexes=[("targetModuleIndex", (1, 2000)), ("gpioIndex", (1, 4))],
        defined_indexes=["gpioIndex"],
        columns=[("gpioName", 2, "DisplayString", None, None, None), ("gpioValue", 3, "GpioValue", None, None, None)],
        source=doc_source(CCDM_DOC, 115, "ccdm/GUD-CCDMCPU-MIB.txt:106-114,457-502"),
    )

    dwc = "GUD-CCDMDWC-MIB"
    dwc_columns = [
        ("id", 2, "DisplayString", None, None, None),
        ("cl", 3, "DisplayString", None, None, None),
        ("name", 4, "DisplayString", None, None, None),
        ("deviceStatus", 5, "DeviceStatus", "DeviceStatus3", None, None),
        ("mainPower", 6, "PowerStatus", None, None, None),
        ("redundantPower", 7, "PowerStatus", None, None, None),
        ("temperature1", 8, "DisplayString", None, None, None),
        ("consoleUSBConnection", 9, "KeyboardMouseStatus", None, None, None),
        ("networkInterface0", 10, "NetworkInterfaceStatus", None, None, None),
        ("networkInterface1", 11, "NetworkInterfaceStatus", None, None, None),
    ]
    module_main_table(
        dwc, "dynamicUserModuleTable", "dynamicUserModuleEntry", f"{P}.1.3.2.3",
        "dynamicUserModuleIndex", 119, "ccdm/GUD-CCDMDWC-MIB.txt:93-103,128-165", dwc_columns,
    )
    b.table(
        module=dwc, name="fanTable", entry_name="fanTableEntry", oid=f"{P}.1.3.2.3.1001",
        indexes=[("dynamicUserModuleIndex", (1, 2000)), ("fanIndex", (1, 10))],
        defined_indexes=["fanIndex"],
        columns=[("fanName", 2, "DisplayString", None, None, None), ("fanSpeed", 3, "Integer32", None, (0, 10000), unit("RPM", "description"))],
        source=doc_source(CCDM_DOC, 132, "ccdm/GUD-CCDMDWC-MIB.txt:251-296"),
    )
    b.table(
        module=dwc, name="videoChannelTable", entry_name="videoChannelEntry", oid=f"{P}.1.3.2.3.1002",
        indexes=[("dynamicUserModuleIndex", (1, 2000)), ("videoChannelIndex", (1, 4))],
        defined_indexes=["videoChannelIndex"],
        columns=[("displayConnection", 2, "ConnectionStatus", None, None, None), ("displayType", 3, "DisplayString", None, None, None)],
        source=doc_source(CCDM_DOC, 133, "ccdm/GUD-CCDMDWC-MIB.txt:68-75,302-347"),
    )
    b.table(
        module=dwc, name="linkChannelTable", entry_name="linkChannelEntry", oid=f"{P}.1.3.2.3.1003",
        indexes=[("dynamicUserModuleIndex", (1, 2000)), ("linkChannelIndex", (1, 8))],
        defined_indexes=["linkChannelIndex"],
        columns=[
            ("conid", 2, "DisplayString", None, None, None),
            ("concl", 3, "DisplayString", None, None, None),
            ("conname", 4, "DisplayString", None, None, None),
            ("linkChannelStatus", 5, "DeviceStatus", "DeviceStatus3", None, None),
            ("activeTransmissionPort", 6, "Integer32", None, (1, 2), None),
            ("sfpTxPower1", 7, "Integer32", None, None, unit("uW", "description")),
            ("sfpTxPower2", 8, "Integer32", None, None, unit("uW", "description")),
            ("sfpRxPower1", 9, "Integer32", None, None, unit("uW", "description")),
            ("sfpRxPower2", 10, "Integer32", None, None, unit("uW", "description")),
            ("sfpType1", 11, "DisplayString", None, None, None),
            ("sfpType2", 12, "DisplayString", None, None, None),
            ("freeze", 13, "Boolean", None, None, None),
        ],
        source=doc_source(CCDM_DOC, 134, "ccdm/GUD-CCDMDWC-MIB.txt:31-38,58-66,354-489"),
    )
    return b.build()


def vision_manifest(cpu: bool) -> dict[str, Any]:
    prefix = C if cpu else K
    role = "CPU" if cpu else "CON"
    module = f"GUD-VISIONXS{role}-MIB"
    profile = f"visionxs_{role.lower()}"
    b = ManifestBuilder(
        profile,
        f"VisionXS {role} independent endpoint",
        prefix,
        [VISION_DOC],
        doc_source(
            VISION_DOC,
            17 if cpu else 18,
            (
                "vision/GUD-SMI-MIB.txt:26-31,45-49,178-184,268-274"
                if cpu
                else "vision/GUD-SMI-MIB.txt:26-31,45-49,187-193,277-283"
            ),
        ),
    )
    if cpu:
        scalars = [
            ("deviceId", f"{prefix}.2.1.1", "DisplayString", 39, "vision/GUD-VISIONXSCPU-MIB.txt:191-197", "mandatory", None, None),
            ("deviceCl", f"{prefix}.2.1.2", "DisplayString", 40, "vision/GUD-VISIONXSCPU-MIB.txt:199-205", "mandatory", None, None),
            ("deviceType", f"{prefix}.2.1.3", "DisplayString", 41, "vision/GUD-VISIONXSCPU-MIB.txt:207-213", "mandatory", None, None),
            ("serialNumber", f"{prefix}.2.1.4", "DisplayString", 42, "vision/GUD-VISIONXSCPU-MIB.txt:215-221", "mandatory", None, None),
            ("etherAddress0", f"{prefix}.2.1.5", "PhysAddress", 43, "vision/GUD-VISIONXSCPU-MIB.txt:223-229", "mandatory", None, None),
            ("firmwareVersion", f"{prefix}.2.2.1", "DisplayString", 44, "vision/GUD-VISIONXSCPU-MIB.txt:232-238", "mandatory", None, None),
            ("mainPower", f"{prefix}.2.3.1", "PowerStatus", 45, "vision/GUD-VISIONXSCPU-MIB.txt:30-37,241-247", "mandatory", None, None),
            ("redundantPower", f"{prefix}.2.3.2", "PowerStatus", 46, "vision/GUD-VISIONXSCPU-MIB.txt:30-37,249-255", "mandatory", None, None),
            ("temperature1", f"{prefix}.2.3.3", "DisplayString", 47, "vision/GUD-VISIONXSCPU-MIB.txt:257-264", "mandatory", None, unit("Deg C", "commented-units")),
            ("fan1", f"{prefix}.2.3.502", "DisplayString", 48, "vision/GUD-VISIONXSCPU-MIB.txt:266-273", "mandatory", None, unit("RPM", "commented-units")),
            ("networkInterface0", f"{prefix}.2.3.506", "NetworkInterfaceStatus", 49, "vision/GUD-VISIONXSCPU-MIB.txt:39-46,275-281", "mandatory", None, None),
            ("transparentUsbLink", f"{prefix}.2.3.10", "TransparentUsbLinkStatus", 50, "vision/GUD-VISIONXSCPU-MIB.txt:67-74,283-289", None, None, None),
            ("targetPower", f"{prefix}.2.3.11", "PowerStatus", 51, "vision/GUD-VISIONXSCPU-MIB.txt:30-37,291-297", "mandatory", None, None),
            ("targetUsbHid", f"{prefix}.2.3.13", "UsbHidStatus", 52, "vision/GUD-VISIONXSCPU-MIB.txt:101-109,299-305", "mandatory", None, None),
            ("targetUsb20", f"{prefix}.2.3.15", "Usb20Status", 53, "vision/GUD-VISIONXSCPU-MIB.txt:111-118,307-313", "mandatory", None, None),
            ("transparentUsbSfpModule", f"{prefix}.2.3.16", "SfpModuleStatus", 54, "vision/GUD-VISIONXSCPU-MIB.txt:120-129,315-321", None, None, None),
            ("transparentUsbTxPower", f"{prefix}.2.3.17", "Integer32", 55, "vision/GUD-VISIONXSCPU-MIB.txt:323-329", None, None, unit("uW", "description")),
            ("transparentUsbRxPower", f"{prefix}.2.3.18", "Integer32", 56, "vision/GUD-VISIONXSCPU-MIB.txt:331-337", None, None, unit("uW", "description")),
            ("transparentUsbSfpType", f"{prefix}.2.3.19", "DisplayString", 57, "vision/GUD-VISIONXSCPU-MIB.txt:339-345", None, None, None),
            ("generalErrorCode", f"{prefix}.2.1000.1", "Integer32", 58, "vision/GUD-VISIONXSCPU-MIB.txt:482-488", "optional", None, None),
            ("generalErrorMessage", f"{prefix}.2.1000.2", "DisplayString", 59, "vision/GUD-VISIONXSCPU-MIB.txt:490-496", "optional", None, None),
        ]
    else:
        scalars = [
            ("deviceId", f"{prefix}.2.1.1", "DisplayString", 73, "vision/GUD-VISIONXSCON-MIB.txt:168-206", "mandatory", None, None),
            ("deviceCl", f"{prefix}.2.1.2", "DisplayString", 73, "vision/GUD-VISIONXSCON-MIB.txt:168-206", "mandatory", None, None),
            ("deviceType", f"{prefix}.2.1.3", "DisplayString", 73, "vision/GUD-VISIONXSCON-MIB.txt:168-206", "mandatory", None, None),
            ("serialNumber", f"{prefix}.2.1.4", "DisplayString", 73, "vision/GUD-VISIONXSCON-MIB.txt:168-206", "mandatory", None, None),
            ("etherAddress0", f"{prefix}.2.1.5", "PhysAddress", 73, "vision/GUD-VISIONXSCON-MIB.txt:168-206", "mandatory", None, None),
            ("firmwareVersion", f"{prefix}.2.2.1", "DisplayString", 74, "vision/GUD-VISIONXSCON-MIB.txt:209-215", "mandatory", None, None),
            ("mainPower", f"{prefix}.2.3.1", "PowerStatus", 75, "vision/GUD-VISIONXSCON-MIB.txt:40-47,218-232", "mandatory", None, None),
            ("redundantPower", f"{prefix}.2.3.2", "PowerStatus", 75, "vision/GUD-VISIONXSCON-MIB.txt:40-47,218-232", "mandatory", None, None),
            ("temperature1", f"{prefix}.2.3.3", "DisplayString", 76, "vision/GUD-VISIONXSCON-MIB.txt:234-250", "mandatory", None, unit("Deg C", "commented-units")),
            ("fan1", f"{prefix}.2.3.502", "DisplayString", 76, "vision/GUD-VISIONXSCON-MIB.txt:234-250", "mandatory", None, unit("RPM", "commented-units")),
            ("networkInterface0", f"{prefix}.2.3.506", "NetworkInterfaceStatus", 77, "vision/GUD-VISIONXSCON-MIB.txt:49-56,252-258", "mandatory", None, None),
            ("consoleUSBConnection", f"{prefix}.2.3.9", "KeyboardMouseStatus", 78, "vision/GUD-VISIONXSCON-MIB.txt:86-95,260-266", "mandatory", None, None),
            ("transparentUsbLink", f"{prefix}.2.3.10", "TransparentUsbLinkStatus", 79, "vision/GUD-VISIONXSCON-MIB.txt:77-84,268-274", None, None, None),
            ("transparentUsbSfpModule", f"{prefix}.2.3.16", "SfpModuleStatus", 80, "vision/GUD-VISIONXSCON-MIB.txt:97-106,276-306", None, None, None),
            ("transparentUsbTxPower", f"{prefix}.2.3.17", "Integer32", 80, "vision/GUD-VISIONXSCON-MIB.txt:97-106,276-306", None, None, unit("uW", "description")),
            ("transparentUsbRxPower", f"{prefix}.2.3.18", "Integer32", 80, "vision/GUD-VISIONXSCON-MIB.txt:97-106,276-306", None, None, unit("uW", "description")),
            ("transparentUsbSfpType", f"{prefix}.2.3.19", "DisplayString", 80, "vision/GUD-VISIONXSCON-MIB.txt:97-106,276-306", None, None, None),
            ("generalErrorCode", f"{prefix}.2.1000.1", "Integer32", 81, "vision/GUD-VISIONXSCON-MIB.txt:449-463", "optional", None, None),
            ("generalErrorMessage", f"{prefix}.2.1000.2", "DisplayString", 81, "vision/GUD-VISIONXSCON-MIB.txt:449-463", "optional", None, None),
        ]
    for name, oid, syntax, line, vendor_ref, compliance, value_range, value_unit in scalars:
        b.scalar(
            name,
            module,
            oid,
            syntax,
            doc_source(VISION_DOC, line, vendor_ref),
            compliance=compliance or "unlisted",
            value_range=value_range,
            value_unit=value_unit,
        )
        if compliance is None:
            b.objects[-1]["compliance"] = "defined-not-in-compliance-group"
            b.objects[-1]["optional_group"] = None

    video_columns = (
        [
            ("targetVideoCable", 2, "ConnectionStatus", None, None, None),
            ("targetVideoSignal", 3, "VideoType", None, None, None),
        ]
        if cpu
        else [
            ("displayConnection", 2, "ConnectionStatus", None, None, None),
            ("displayType", 3, "DisplayString", None, None, None),
            ("freeze", 4, "Boolean", None, None, None),
        ]
    )
    b.table(
        module=module,
        name="videoChannelTable",
        entry_name="videoChannelEntry",
        oid=f"{prefix}.2.3.1000",
        indexes=[("videoChannelIndex", (1, 4))],
        defined_indexes=["videoChannelIndex"],
        columns=video_columns,
        source=doc_source(
            VISION_DOC,
            61 if cpu else 83,
            (
                "vision/GUD-VISIONXSCPU-MIB.txt:48-88,351-396"
                if cpu
                else "vision/GUD-VISIONXSCON-MIB.txt:31-38,58-65,312-366"
            ),
        ),
    )
    b.table(
        module=module,
        name="linkChannelTable",
        entry_name="linkChannelEntry",
        oid=f"{prefix}.2.3.1001",
        indexes=[("linkChannelIndex", (1, 8))],
        defined_indexes=["linkChannelIndex"],
        columns=[
            ("link", 2, "LinkStatus", None, None, None),
            ("sfpModule", 3, "SfpModuleStatus", None, None, None),
            ("sfpTxPower", 4, "Integer32", None, None, unit("uW", "description")),
            ("sfpRxPower", 5, "Integer32", None, None, unit("uW", "description")),
            ("sfpType", 6, "DisplayString", None, None, None),
        ],
        source=doc_source(
            VISION_DOC,
            63 if cpu else 85,
            (
                "vision/GUD-VISIONXSCPU-MIB.txt:57-65,120-129,403-475"
                if cpu
                else "vision/GUD-VISIONXSCON-MIB.txt:67-75,97-106,373-445"
            ),
        ),
    )
    return b.build()


def dp_manifest() -> dict[str, Any]:
    module = "GUD-DP12MUXATC-MIB"
    b = ManifestBuilder(
        "dp12_mux_atc",
        "DP1.2-MUX-ATC",
        D,
        [DP_DOC],
        doc_source(DP_DOC, 15, "dp/GUD-SMI-MIB.txt:26-31,45-49,315-319,340-346"),
    )
    scalars = [
        ("deviceId", f"{D}.2.1.1", "DisplayString", 44, "dp/GUD-DP12MUXATC-MIB.txt:183-189", "mandatory", "read-only", None, None),
        ("deviceCl", f"{D}.2.1.2", "DisplayString", 45, "dp/GUD-DP12MUXATC-MIB.txt:191-197", "mandatory", "read-only", None, None),
        ("deviceType", f"{D}.2.1.3", "DisplayString", 46, "dp/GUD-DP12MUXATC-MIB.txt:199-205", "mandatory", "read-only", None, None),
        ("serialNumber", f"{D}.2.1.4", "DisplayString", 47, "dp/GUD-DP12MUXATC-MIB.txt:207-213", "mandatory", "read-only", None, None),
        ("etherAddress0", f"{D}.2.1.5", "PhysAddress", 48, "dp/GUD-DP12MUXATC-MIB.txt:215-221", "mandatory", "read-only", None, None),
        ("etherAddress1", f"{D}.2.1.6", "PhysAddress", 49, "dp/GUD-DP12MUXATC-MIB.txt:223-229", "mandatory", "read-only", None, None),
        ("firmwareVersion", f"{D}.2.2.1", "DisplayString", 50, "dp/GUD-DP12MUXATC-MIB.txt:233-239", "mandatory", "read-only", None, None),
        ("mainPower", f"{D}.2.3.1", "PowerStatus", 58, "dp/GUD-DP12MUXATC-MIB.txt:243-249", "mandatory", "read-only", None, None),
        ("redundantPower", f"{D}.2.3.2", "PowerStatus", 59, "dp/GUD-DP12MUXATC-MIB.txt:251-257", "mandatory", "read-only", None, None),
        ("temperature1", f"{D}.2.3.3", "DisplayString", 60, "dp/GUD-DP12MUXATC-MIB.txt:259-266", "mandatory", "read-only", None, unit("Deg C", "description")),
        ("powerCurrent", f"{D}.2.3.500", "DisplayString", 61, "dp/GUD-DP12MUXATC-MIB.txt:268-275", "mandatory", "read-only", None, unit("A", "comment")),
        ("powerVoltage", f"{D}.2.3.501", "DisplayString", 62, "dp/GUD-DP12MUXATC-MIB.txt:277-284", "mandatory", "read-only", None, unit("V", "comment")),
        ("consolePS2Connection", f"{D}.2.3.7", "KeyboardMouseStatus", 63, "dp/GUD-DP12MUXATC-MIB.txt:286-292", "mandatory", "read-only", None, None),
        ("consoleUSBConnection", f"{D}.2.3.8", "KeyboardMouseStatus", 64, "dp/GUD-DP12MUXATC-MIB.txt:294-300", "mandatory", "read-only", None, None),
        ("networkInterface0", f"{D}.2.3.506", "NetworkInterfaceStatus", 65, "dp/GUD-DP12MUXATC-MIB.txt:302-308", "mandatory", "read-only", None, None),
        ("networkInterface1", f"{D}.2.3.507", "NetworkInterfaceStatus", 66, "dp/GUD-DP12MUXATC-MIB.txt:310-316", "mandatory", "read-only", None, None),
        ("selectedChannel", f"{D}.2.4.1", "Integer32", 130, "dp/GUD-DP12MUXATC-MIB.txt:550-557", "optional", "read-write", (1, 4), None),
        ("disableSwitching", f"{D}.2.5.1", "Boolean", 131, "dp/GUD-DP12MUXATC-MIB.txt:561-568", "optional", "read-write", None, None),
        ("disableFrontkeys", f"{D}.2.5.2", "Boolean", 132, "dp/GUD-DP12MUXATC-MIB.txt:570-577", "optional", "read-write", None, None),
        ("disableHotkeys", f"{D}.2.5.3", "Boolean", 133, "dp/GUD-DP12MUXATC-MIB.txt:579-586", "optional", "read-write", None, None),
        ("disableSerialPort", f"{D}.2.5.4", "Boolean", 134, "dp/GUD-DP12MUXATC-MIB.txt:588-595", "optional", "read-write", None, None),
        ("disableRemoteControlApi", f"{D}.2.5.5", "Boolean", 135, "dp/GUD-DP12MUXATC-MIB.txt:597-604", "optional", "read-write", None, None),
        ("generalErrorCode", f"{D}.2.1000.1", "Integer32", 111, "dp/GUD-DP12MUXATC-MIB.txt:607-613", "optional", "read-only", None, None),
        ("generalErrorMessage", f"{D}.2.1000.2", "DisplayString", 112, "dp/GUD-DP12MUXATC-MIB.txt:615-621", "optional", "read-only", None, None),
    ]
    for name, oid, syntax, line, vendor_ref, compliance, access, value_range, value_unit in scalars:
        b.scalar(
            name,
            module,
            oid,
            syntax,
            doc_source(DP_DOC, line, vendor_ref),
            compliance=compliance,
            max_access=access,
            value_range=value_range,
            value_unit=value_unit,
        )
    b.table(
        module=module, name="cpuChannelTable", entry_name="cpuChannelEntry", oid=f"{D}.2.3.1000",
        indexes=[("cpuChannelIndex", (1, 4))], defined_indexes=["cpuChannelIndex"],
        columns=[
            ("cpuChannelTargetUsbHid", 2, "UsbHidStatus", None, None, None),
            ("cpuChannelTargetDevice", 3, "DisplayString", None, None, None),
            ("cpuChannelTargetPower", 4, "PowerStatus", None, None, None),
            ("cpuChannelTargetPS2", 5, "ConnectionStatus", None, None, None),
            ("cpuChannelTargetUsb30", 6, "Usb30Status", None, None, None),
        ],
        source=doc_source(DP_DOC, 68, "dp/GUD-DP12MUXATC-MIB.txt:322-394"),
    )
    b.table(
        module=module, name="cpuChannelVideoTable", entry_name="cpuChannelVideoEntry", oid=f"{D}.2.3.1001",
        indexes=[("cpuChannelIndex", (1, 4)), ("cpuChannelVideoIndex", (1, 4))],
        defined_indexes=["cpuChannelVideoIndex"],
        columns=[
            ("cpuChannelVideoCable", 2, "ConnectionStatus", None, None, None),
            ("cpuChannelVideoSignal", 3, "VideoType", None, None, None),
        ],
        source=doc_source(DP_DOC, 80, "dp/GUD-DP12MUXATC-MIB.txt:400-445"),
    )
    b.table(
        module=module, name="consoleVideoTable", entry_name="consoleVideoEntry", oid=f"{D}.2.3.1002",
        indexes=[("consoleVideoIndex", (1, 4))], defined_indexes=["consoleVideoIndex"],
        columns=[
            ("displayConnection", 2, "ConnectionStatus", None, None, None),
            ("displayType", 3, "DisplayString", None, None, None),
            ("freeze", 4, "Boolean", None, None, None),
        ],
        source=doc_source(DP_DOC, 89, "dp/GUD-DP12MUXATC-MIB.txt:451-505"),
    )
    b.table(
        module=module, name="fanTable", entry_name="fanTableEntry", oid=f"{D}.2.3.1003",
        indexes=[("fanIndex", (1, 20))], defined_indexes=["fanIndex"],
        columns=[("fanSpeed", 2, "Integer32", None, (0, 10000), unit("RPM", "description"))],
        source=doc_source(DP_DOC, 99, "dp/GUD-DP12MUXATC-MIB.txt:511-547"),
    )
    return b.build()


def legacy_manifest() -> dict[str, Any]:
    b = ManifestBuilder(
        "ccdc_legacy",
        "ControlCenter-Compact historical compatibility profile",
        "1.3.6.1.4.1.32828.3.257.16",
        [COMPAT_DOC],
        doc_source(COMPAT_DOC, 73, "project compatibility classification; vendor object MIB absent"),
        evidence_status="legacy-unverified",
        source_authority="project-compatibility-plan-legacy-boundary",
    )
    result = b.build()
    result["boundaries"] = [
        "No CCDC/CCC object definition is promoted to vendor fact.",
        "The current evidence package lacks CCDC/CCC device, CPU, CON, and DWC MIB dictionaries.",
        "Do not derive CCDC objects by replacing the CCDM product prefix.",
        "Admission requires live GET/WALK evidence and the missing vendor MIB.",
    ]
    return result


def manifests() -> dict[str, dict[str, Any]]:
    return {
        "ccdm.objects.json": ccdm_manifest(),
        "visionxs_cpu.objects.json": vision_manifest(True),
        "visionxs_con.objects.json": vision_manifest(False),
        "dp12_mux_atc.objects.json": dp_manifest(),
        "ccdc_legacy.objects.json": legacy_manifest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if committed JSON differs")
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failed: list[str] = []
    for filename, payload in manifests().items():
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        target = OUTPUT_DIR / filename
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                failed.append(filename)
        else:
            target.write_text(rendered, encoding="utf-8", newline="\n")
    if failed:
        print("out-of-date:", ", ".join(failed))
        return 1
    print("checked" if args.check else "generated", len(manifests()), "object manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
