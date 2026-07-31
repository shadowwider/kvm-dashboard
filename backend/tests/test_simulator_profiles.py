from __future__ import annotations

import importlib
import json
import time
from pathlib import Path

import pytest

from simulator.models import EvidenceStatus, ProfileId, ScenarioDevice
from simulator.profile_catalog import (
    ACCEPTED_L1_SHA256,
    CATALOG_PATH,
    PROFILE_CATALOG,
    get_profile,
    project_l1_manifest,
)
from simulator.profile_fixture import (
    DEFAULT_FIXTURE_PATH,
    DEFAULT_FIXTURE_SHA256,
    FixtureSpec,
    FixtureTable,
    build_explicit_fixture,
    validate_fixture_schema,
)
from simulator.profiles import (
    DEFAULT_FIXTURES,
    PROFILE_DEFINITIONS,
    PROJECT_LEGACY_COMPATIBILITY_ADAPTER,
    expected_oids_for_device,
    normalize_profile_id,
    profile_metadata,
    render_oid_map,
)
from simulator.scenarios import built_in_scenarios
from simulator.snmp_agent import SYS_OBJECT_ID, endpoint_oid_map


def _device_by_profile(profile_id: ProfileId) -> dict:
    for scenario in built_in_scenarios().values():
        for device in scenario.devices:
            if device.profile == profile_id:
                return device.model_dump(mode="json")
    raise AssertionError(f"missing fixture for {profile_id}")


def test_transport_profile_aliases_are_preserved_while_l2_ids_are_canonical():
    assert normalize_profile_id("ccdc_legacy") == ProfileId.CCDC_LEGACY.value
    assert normalize_profile_id("ccdc_legacy_unverified") == (
        ProfileId.CCDC_LEGACY.value
    )
    assert normalize_profile_id("dp12_mux_atc") == ProfileId.DP12_MUX.value
    assert normalize_profile_id("dp12_mux_atc_readonly") == (
        ProfileId.DP12_MUX.value
    )
    assert get_profile(ProfileId.CCDC_LEGACY).profile_id == "ccdc_legacy"
    assert get_profile(ProfileId.DP12_MUX).profile_id == "dp12_mux_atc"

    ccdc = ScenarioDevice(
        id="alias-ccdc",
        name="Alias CCDC",
        profile="ccdc_legacy",
        snmp_port=12001,
        system_oid=PROFILE_DEFINITIONS[ProfileId.CCDC_LEGACY]["system_oid"],
        evidence=EvidenceStatus.LEGACY_COMPATIBILITY,
    )
    dp = ScenarioDevice(
        id="alias-dp",
        name="Alias DP",
        profile="dp12_mux_atc",
        snmp_port=12002,
        system_oid=PROFILE_DEFINITIONS[ProfileId.DP12_MUX]["system_oid"],
        evidence=EvidenceStatus.VENDOR_BACKED,
    )
    assert ccdc.profile == ProfileId.CCDC_LEGACY
    assert dp.profile == ProfileId.DP12_MUX


def test_catalog_is_pinned_and_projects_every_l1_semantic(tmp_path):
    filenames = {
        "ccdc_legacy": "ccdc_legacy.objects.json",
        "ccdm_matrix": "ccdm.objects.json",
        "visionxs_cpu": "visionxs_cpu.objects.json",
        "visionxs_con": "visionxs_con.objects.json",
        "dp12_mux_atc": "dp12_mux_atc.objects.json",
    }
    golden_root = (
        __import__("pathlib").Path(__file__).parent / "golden" / "simulator"
    )
    for profile_id, profile in PROFILE_CATALOG.items():
        golden = json.loads(
            (golden_root / filenames[profile_id]).read_text(encoding="utf-8")
        )
        projection = project_l1_manifest(profile)

        assert profile.source_manifest_sha256 == ACCEPTED_L1_SHA256[profile_id]
        assert projection["objects"] == golden["objects"]
        assert projection["tables"] == golden["tables"]
        assert projection["sys_object_id"] == golden["sys_object_id"]["oid"]
        assert projection["evidence_status"] == golden["evidence_status"]


def test_production_catalog_loader_does_not_open_test_goldens(monkeypatch):
    import simulator.profile_catalog as loader

    original_read_bytes = Path.read_bytes
    original_open = Path.open
    reads: list[Path] = []
    opens: list[Path] = []

    def audited_read_bytes(path: Path) -> bytes:
        reads.append(path.resolve())
        return original_read_bytes(path)

    def audited_open(path: Path, *args, **kwargs):
        opens.append(path.resolve())
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", audited_read_bytes)
    monkeypatch.setattr(Path, "open", audited_open)
    importlib.reload(loader)

    assert CATALOG_PATH.parent.name == "catalog"
    assert CATALOG_PATH.name == "l2_profiles.json"
    assert reads == [CATALOG_PATH.resolve()]
    assert opens == [CATALOG_PATH.resolve()]
    assert not any(
        "backend/tests/golden" in str(path).replace("\\", "/")
        for path in reads
    )


def test_all_builtin_fixture_values_validate_and_have_only_explicit_rows():
    for profile_id, fixture in DEFAULT_FIXTURES.items():
        assert validate_fixture_schema(profile_id, fixture) is fixture
        assert fixture.enabled_optional_groups == frozenset()
        for table in fixture.tables:
            assert table.rows
            assert len({tuple(row.indexes) for row in table.rows}) == len(table.rows)

    ccdm = DEFAULT_FIXTURES["ccdm_matrix"]
    assert len(ccdm.table_map["io_card_cat_port_table"]) == 1
    assert len(ccdm.table_map["io_card_fiber_port_table"]) == 1
    assert len(ccdm.table_map["io_card_multi_port_table"]) == 1
    assert len(ccdm.table_map["io_card_trunk_port_table"]) == 1
    assert len(DEFAULT_FIXTURE_SHA256) == 64
    assert DEFAULT_FIXTURE_PATH.name == "l2_default_fixtures.json"

    dp = DEFAULT_FIXTURES["dp12_mux_atc"].scalar_map
    assert dp["ether_address0"] == "02:00:00:00:40:01"
    assert dp["ether_address1"] == "02:00:00:00:40:02"
    assert dp["ether_address0"] != dp["ether_address1"]

    fiber = ccdm.table_map["io_card_fiber_port_table"][0].value_map
    multi = ccdm.table_map["io_card_multi_port_table"][0].value_map
    trunk = ccdm.table_map["io_card_trunk_port_table"][0].value_map
    for values in (fiber, multi, trunk):
        assert values[next(key for key in values if "tx_power" in key)] == "500"
        assert values[next(key for key in values if "rx_power" in key)] == "480"


def test_optional_objects_are_schema_only_until_explicitly_enabled():
    profile = get_profile("dp12_mux_atc")
    default_fixture = DEFAULT_FIXTURES["dp12_mux_atc"]
    assert default_fixture.enabled_optional_groups == frozenset()
    assert "selected_channel" not in default_fixture.scalar_map
    assert "disable_switching" not in default_fixture.scalar_map

    group = next(
        scalar.optional_group
        for scalar in profile.scalars
        if scalar.canonical_field == "selected_channel"
    )
    enabled = build_explicit_fixture(
        profile,
        fixture_id="dp12-selected-channel",
        enabled_optional_groups=(group,),
        scalar_values={
            **default_fixture.scalar_map,
            "selected_channel": 1,
        },
    )
    assert enabled.scalar_map["selected_channel"] == 1
    assert validate_fixture_schema(profile, enabled) is enabled


def test_fixture_rejects_invalid_enum_range_index_order_and_duplicate_rows():
    profile = get_profile("visionxs_cpu")
    base = DEFAULT_FIXTURES["visionxs_cpu"]
    video = next(
        item for item in base.tables if item.table_id == "video_channel_table"
    )
    row = video.rows[0]

    invalid_enum = row.model_copy(
        update={
            "values": tuple(
                (name, 99 if name == "target_video_cable" else value)
                for name, value in row.values
            )
        }
    )
    with pytest.raises(ValueError, match="not in enum"):
        validate_fixture_schema(
            profile,
            base.model_copy(
                update={
                    "tables": (
                        FixtureTable(
                            table_id="video_channel_table",
                            rows=(invalid_enum,),
                        ),
                    )
                }
            ),
        )

    wrong_order = row.model_copy(
        update={"indexes": (("wrong_index", 1),)}
    )
    with pytest.raises(ValueError, match="indexes must be exactly"):
        validate_fixture_schema(
            profile,
            base.model_copy(
                update={
                    "tables": (
                        FixtureTable(
                            table_id="video_channel_table",
                            rows=(wrong_order,),
                        ),
                    )
                }
            ),
        )

    out_of_range = row.model_copy(
        update={"indexes": (("video_channel_index", 5),)}
    )
    with pytest.raises(ValueError, match="outside"):
        validate_fixture_schema(
            profile,
            base.model_copy(
                update={
                    "tables": (
                        FixtureTable(
                            table_id="video_channel_table",
                            rows=(out_of_range,),
                        ),
                    )
                }
            ),
        )

    with pytest.raises(ValueError, match="duplicate fixture row"):
        validate_fixture_schema(
            profile,
            base.model_copy(
                update={
                    "tables": (
                        FixtureTable(
                            table_id="video_channel_table",
                            rows=(row, row),
                        ),
                    )
                }
            ),
        )


def test_fixture_requires_all_mandatory_values_and_enabled_optional_values():
    profile = get_profile("visionxs_cpu")
    base = DEFAULT_FIXTURES["visionxs_cpu"]
    with pytest.raises(ValueError, match="missing required fixture scalars"):
        validate_fixture_schema(
            profile,
            base.model_copy(update={"scalar_values": base.scalar_values[1:]}),
        )

    table = base.tables[0]
    row = table.rows[0]
    with pytest.raises(ValueError, match="missing required fixture columns"):
        validate_fixture_schema(
            profile,
            base.model_copy(
                update={
                    "tables": (
                        table.model_copy(
                            update={
                                "rows": (
                                    row.model_copy(
                                        update={"values": row.values[1:]}
                                    ),
                                )
                            }
                        ),
                    )
                }
            ),
        )

    dp_profile = get_profile("dp12_mux_atc")
    dp = DEFAULT_FIXTURES["dp12_mux_atc"]
    optional_group = next(
        item.optional_group
        for item in dp_profile.scalars
        if item.canonical_field == "selected_channel"
    )
    with pytest.raises(ValueError, match="missing required fixture scalars"):
        validate_fixture_schema(
            dp_profile,
            dp.model_copy(
                update={"enabled_optional_groups": frozenset({optional_group})}
            ),
        )


def test_fixture_public_api_rejects_arbitrary_dict_and_unknown_syntax():
    profile = get_profile("visionxs_cpu")
    with pytest.raises(Exception):
        validate_fixture_schema(profile, {"arbitrary": {"nested": True}})

    base = DEFAULT_FIXTURES["visionxs_cpu"]
    scalar = profile.scalars[0].model_copy(update={"syntax": "UnknownSyntax"})
    modified_profile = profile.model_copy(
        update={"scalars": (scalar, *profile.scalars[1:])}
    )
    with pytest.raises(ValueError, match="unsupported fixture syntax"):
        validate_fixture_schema(modified_profile, base)


def test_empty_endpoint_and_empty_table_config_produce_zero_table_rows():
    ccdm = _device_by_profile(ProfileId.CCDM_MATRIX)
    ccdm["endpoints"] = []
    rendered = render_oid_map(ccdm)
    profile = get_profile("ccdm_matrix")
    for table_id in ("user_module_table", "target_module_table"):
        table = next(
            item for item in profile.tables if item.canonical_field == table_id
        )
        assert not any(
            oid.startswith(f"{table.entry_oid}.") for oid in rendered
        )

    profile = get_profile("visionxs_cpu")
    empty = FixtureSpec(
        fixture_id="empty-vision",
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        evidence_version=profile.evidence_version,
    )
    with pytest.raises(ValueError, match="missing required fixture scalars"):
        validate_fixture_schema(profile, empty)

    ccdc = get_profile("ccdc_legacy")
    empty_ccdc = FixtureSpec(
        fixture_id="empty-ccdc",
        profile_id=ccdc.profile_id,
        profile_version=ccdc.profile_version,
        evidence_version=ccdc.evidence_version,
    )
    assert validate_fixture_schema(ccdc, empty_ccdc).table_map == {}


def test_renderer_instantiates_all_mandatory_leaves_without_optional_objects():
    expected_counts = {
        ProfileId.CCDM_MATRIX: 133,
        ProfileId.VISIONXS_CPU: 27,
        ProfileId.VISIONXS_CON: 26,
        ProfileId.DP12_MUX: 28,
    }
    for transport_id, expected_count in expected_counts.items():
        device = _device_by_profile(transport_id)
        rendered = render_oid_map(device)
        profile = get_profile(transport_id)
        assert len(rendered) == expected_count
        assert rendered[SYS_OBJECT_ID] == profile.sys_object_id
        for scalar in profile.scalars:
            assert (scalar.instance_oid in rendered) is (
                scalar.optional_group is None
            )
        instantiated_table_ids = set(DEFAULT_FIXTURES[profile.profile_id].table_map)
        for table in profile.tables:
            for column in table.columns:
                if (
                    column.optional_group is None
                    and table.canonical_field in instantiated_table_ids
                ):
                    assert any(
                        oid.startswith(f"{column.oid}.") for oid in rendered
                    )
        assert expected_oids_for_device(device) == set(
            endpoint_oid_map(device)
        )

    ccdm = _device_by_profile(ProfileId.CCDM_MATRIX)
    rendered = render_oid_map(ccdm)
    assert rendered[
        "1.3.6.1.4.1.32828.3.257.10.1.2.2.3.1000.1.12.1"
    ] == 2
    for column in (13, 14, 15):
        assert rendered[
            f"1.3.6.1.4.1.32828.3.257.10.1.2.2.3.1000.1.{column}.1"
        ] == 1

    profile = get_profile("ccdm_matrix")
    for table_id in (
        "gud_ccdmcon_mib_fan_table",
        "gud_ccdmcon_mib_gpio_table",
        "gud_ccdmcpu_mib_fan_table",
        "gud_ccdmcpu_mib_gpio_table",
    ):
        table = next(
            item for item in profile.tables if item.canonical_field == table_id
        )
        assert not any(
            oid.startswith(f"{table.entry_oid}.") for oid in rendered
        )


def test_all_profiles_reject_system_oid_override_and_accept_profile_default():
    for profile_id in ProfileId:
        device = _device_by_profile(profile_id)
        expected = get_profile(profile_id).sys_object_id
        mismatched = dict(device)
        mismatched["system_oid"] = "1.3.6.1.4.1.32828.999.1"
        with pytest.raises(ValueError, match="exact Profile sysObjectID"):
            render_oid_map(mismatched)

        without_override = dict(device)
        without_override.pop("system_oid", None)
        assert render_oid_map(without_override)[SYS_OBJECT_ID] == expected


def test_ccdc_vendor_schema_is_empty_and_adapter_is_explicitly_project_legacy():
    vendor = get_profile("ccdc_legacy")
    assert vendor.scalars == ()
    assert vendor.tables == ()
    assert vendor.evidence_status == "legacy-unverified"
    assert PROJECT_LEGACY_COMPATIBILITY_ADAPTER["adapter_id"] == (
        "project-legacy-compatibility"
    )
    assert PROJECT_LEGACY_COMPATIBILITY_ADAPTER["vendor_object_count"] == 0

    device = _device_by_profile(ProfileId.CCDC_LEGACY)
    rendered = render_oid_map(device)
    sys_oid = device["system_oid"]
    assert f"{sys_oid}.2.3.508.0" in rendered
    assert f"{sys_oid}.2.3.509.0" in rendered
    assert f"{sys_oid}.2.3.1000.1.4.1" in rendered
    assert f"{sys_oid}.2.3.1000.1.5.1" in rendered
    assert f"{sys_oid}.2.3.1000.1.6.1" in rendered


def test_profile_metadata_is_schema_only_stable_and_within_budget():
    started = time.perf_counter()
    metadata = profile_metadata()
    elapsed_ms = (time.perf_counter() - started) * 1000
    encoded = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))

    assert '"rows"' not in encoded
    assert '"fixture"' not in encoded
    assert '"path"' not in encoded
    assert len(encoded.encode("utf-8")) < 512 * 1024
    assert (
        len(
            json.dumps(
                metadata["profiles"]["ccdm_matrix"],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        < 256 * 1024
    )
    assert elapsed_ms < 100

    before = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    base = DEFAULT_FIXTURES["visionxs_cpu"]
    many_tables = []
    for table in base.tables:
        template = table.rows[0]
        indexes = (1, 2, 3, 4) if table.table_id == "video_channel_table" else (1, 2)
        many_tables.append(
            table.model_copy(
                update={
                    "rows": tuple(
                        template.model_copy(
                            update={
                                "indexes": (
                                    (template.indexes[0][0], index),
                                )
                            }
                        )
                        for index in indexes
                    )
                }
            )
        )
    many_explicit_rows = base.model_copy(
        update={
            "fixture_id": "many-explicit-rows",
            "tables": tuple(many_tables),
        }
    )
    assert validate_fixture_schema("visionxs_cpu", many_explicit_rows)
    after = json.dumps(profile_metadata(), sort_keys=True, separators=(",", ":"))
    assert before == after
