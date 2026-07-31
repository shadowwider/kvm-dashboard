from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor

import pytest

import simulator.runtime_state as runtime_state_module
from simulator.profile_catalog import get_profile
from simulator.profile_fixture import DEFAULT_FIXTURES, FixtureSpec
from simulator.runtime_paths import (
    PLATFORM_STRING_MAX_UTF8_BYTES,
    RuntimePathError,
    RuntimeTransitionError,
    RuntimeValueError,
    format_row_key,
    parse_row_key,
)
from simulator.runtime_state import (
    EVENT_HISTORY_LIMIT,
    INITIAL_REVISION,
    Availability,
    RuntimeAction,
    RuntimeDeviceSpec,
    RuntimeState,
)


def _runtime(profile_id: str = "dp12_mux_atc") -> RuntimeState:
    return RuntimeState.single(
        f"device-{profile_id}",
        get_profile(profile_id),
        DEFAULT_FIXTURES[profile_id],
        host="127.0.0.1",
        snmp_port=11161,
    )


def _dp_fixture_with_selected_channel(value: int = 1) -> FixtureSpec:
    payload = DEFAULT_FIXTURES["dp12_mux_atc"].model_dump(mode="python")
    payload["enabled_optional_groups"] = frozenset(
        {"optional_selected_channel"}
    )
    payload["scalar_values"] = (
        *payload["scalar_values"],
        ("selected_channel", value),
    )
    return FixtureSpec.model_validate(payload)


def _dp_fixture_with_composite_row(
    cpu_channel_index: int,
    video_index: int,
) -> FixtureSpec:
    payload = DEFAULT_FIXTURES["dp12_mux_atc"].model_dump(mode="python")
    tables = []
    for table in payload["tables"]:
        current = dict(table)
        if current["table_id"] == "cpu_channel_video_table":
            row = dict(current["rows"][0])
            row["indexes"] = (
                ("cpu_channel_index", cpu_channel_index),
                ("cpu_channel_video_index", video_index),
            )
            current["rows"] = (row,)
        tables.append(current)
    payload["tables"] = tuple(tables)
    return FixtureSpec.model_validate(payload)


@pytest.mark.parametrize("profile_id", sorted(DEFAULT_FIXTURES))
def test_all_l2_default_fixtures_construct_and_render(profile_id):
    fixture = DEFAULT_FIXTURES[profile_id]
    runtime = RuntimeState.single(
        f"device-{profile_id}",
        get_profile(profile_id),
        fixture,
    )

    rendered = runtime.renderable_snapshot(f"device-{profile_id}")["device"]
    assert rendered["system_oid"] == get_profile(profile_id).sys_object_id
    assert set(rendered["scalars"]) == set(fixture.scalar_map)
    assert {
        table_id: len(rows)
        for table_id, rows in rendered["tables"].items()
    } == {
        table.table_id: len(table.rows)
        for table in fixture.tables
    }


def test_runtime_builds_registry_only_from_actual_fixture_leaves():
    runtime = _runtime()
    registry = runtime.path_registry("device-dp12_mux_atc")

    read_only_vendor_leaf = registry.get("scalars.main_power")
    assert read_only_vendor_leaf.runtime_writable is True
    assert read_only_vendor_leaf.vendor_snmp_writable is False

    assert "identity.device_id" in registry.readonly_paths
    assert "runtime.availability" in registry.readonly_paths
    assert (
        "tables.cpu_channel_video_table[1,1]"
        ".indexes.cpu_channel_video_index"
    ) in registry.readonly_paths

    # Optional schema exists in L2, but this fixture did not enable or
    # instantiate it, so it has no runtime path.
    with pytest.raises(RuntimePathError):
        registry.get("scalars.selected_channel")


def test_legal_batch_patch_commits_once_with_exact_changed_paths():
    runtime = _runtime()
    before_events = runtime.events()

    result = runtime.patch(
        "device-dp12_mux_atc",
        [
            ("scalars.main_power", 0),
            ("scalars.temperature1", "41.5"),
        ],
    )

    assert result.revision == INITIAL_REVISION + 1
    assert result.changed_paths == (
        "scalars.main_power",
        "scalars.temperature1",
    )
    assert result.changed is True
    assert result.committed_values == (
        ("scalars.main_power", 0),
        ("scalars.temperature1", "41.5"),
    )
    assert runtime.read("device-dp12_mux_atc", "scalars.main_power") == 0
    assert runtime.read("device-dp12_mux_atc", "scalars.temperature1") == "41.5"
    assert len(runtime.events()) == len(before_events) + 1
    assert runtime.events()[-1].changed_paths == result.changed_paths


def test_legal_table_patch_updates_only_the_addressed_instance():
    runtime = _runtime()
    path = "tables.fan_table[1].fan_speed"
    before = runtime.renderable_snapshot("device-dp12_mux_atc")

    result = runtime.patch("device-dp12_mux_atc", {path: 3300})
    after = runtime.renderable_snapshot("device-dp12_mux_atc")

    assert result.changed_paths == (path,)
    assert runtime.read("device-dp12_mux_atc", path) == 3300
    assert (
        after["device"]["tables"]["fan_table"]["1"]["values"]["fan_speed"]
        == 3300
    )
    assert after["device"]["scalars"] == before["device"]["scalars"]


def test_batch_patch_rolls_back_state_revision_events_and_render_snapshot():
    runtime = _runtime()
    before_state = runtime.snapshot()
    before_render = runtime.renderable_snapshot()
    before_revision = runtime.revision
    before_events = runtime.events()

    with pytest.raises(RuntimeValueError):
        runtime.patch(
            "device-dp12_mux_atc",
            [
                ("scalars.main_power", 0),
                ("scalars.network_interface0", 99),
            ],
        )

    assert runtime.snapshot() == before_state
    assert runtime.renderable_snapshot() == before_render
    assert runtime.revision == before_revision
    assert runtime.events() == before_events


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("scalars.main_power", True),
        ("scalars.main_power", "0"),
        ("scalars.main_power", 7),
        ("scalars.temperature1", b"41.0"),
    ],
)
def test_runtime_value_type_and_enum_validation_is_fail_closed(path, value):
    runtime = _runtime()
    before = runtime.snapshot()

    with pytest.raises(RuntimeValueError):
        runtime.patch("device-dp12_mux_atc", [(path, value)])

    assert runtime.snapshot() == before


def test_explicit_range_and_optional_capability_are_enforced():
    profile = get_profile("dp12_mux_atc")
    enabled = RuntimeState.single(
        "dp-enabled",
        profile,
        _dp_fixture_with_selected_channel(1),
    )
    enabled.patch("dp-enabled", {"scalars.selected_channel": 4})
    assert enabled.read("dp-enabled", "scalars.selected_channel") == 4
    assert (
        enabled.path_registry("dp-enabled")
        .get("scalars.selected_channel")
        .vendor_snmp_writable
        is True
    )
    assert enabled.renderable_snapshot("dp-enabled")["device"][
        "enabled_optional_groups"
    ] == ["optional_selected_channel"]

    before = enabled.snapshot()
    with pytest.raises(RuntimeValueError):
        enabled.patch("dp-enabled", {"scalars.selected_channel": 5})
    assert enabled.snapshot() == before

    disabled = _runtime()
    with pytest.raises(RuntimePathError):
        disabled.patch(
            "device-dp12_mux_atc",
            {"scalars.selected_channel": 1},
        )


def test_string_limit_is_utf8_platform_policy_not_vendor_size():
    runtime = _runtime()
    path = "scalars.device_cl"
    registry_entry = runtime.path_registry("device-dp12_mux_atc").get(path)
    assert registry_entry.max_utf8_bytes == PLATFORM_STRING_MAX_UTF8_BYTES
    assert (
        registry_entry.length_policy
        == "platform-runtime-policy-not-vendor-mib-size"
    )

    runtime.patch(
        "device-dp12_mux_atc",
        {path: "a" * PLATFORM_STRING_MAX_UTF8_BYTES},
    )
    before = runtime.snapshot()
    with pytest.raises(RuntimeValueError):
        runtime.patch(
            "device-dp12_mux_atc",
            {path: "界" * ((PLATFORM_STRING_MAX_UTF8_BYTES // 3) + 1)},
        )
    assert runtime.snapshot() == before


def test_unknown_l2_syntax_fails_during_runtime_construction():
    profile = get_profile("dp12_mux_atc")
    bad_scalar = profile.scalars[1].model_copy(
        update={"syntax": "FutureOpaqueSyntax"}
    )
    bad_profile = profile.model_copy(
        update={
            "scalars": (
                profile.scalars[0],
                bad_scalar,
                *profile.scalars[2:],
            )
        }
    )

    with pytest.raises(RuntimeValueError, match="unsupported fixture syntax"):
        RuntimeState.single(
            "bad-syntax",
            bad_profile,
            DEFAULT_FIXTURES["dp12_mux_atc"],
        )


def test_composite_row_key_is_ordered_canonical_and_reversible():
    profile = get_profile("dp12_mux_atc")
    fixture = _dp_fixture_with_composite_row(2, 1)
    runtime = RuntimeState.single("dp-composite", profile, fixture)
    expected_path = (
        "tables.cpu_channel_video_table[2,1].cpu_channel_video_cable"
    )

    assert format_row_key((2, 1)) == "2,1"
    assert parse_row_key("2,1") == (2, 1)
    assert runtime.read("dp-composite", expected_path) == 1
    assert (
        runtime.read(
            "dp-composite",
            "tables.cpu_channel_video_table[2,1]"
            ".indexes.cpu_channel_index",
        )
        == 2
    )
    assert (
        runtime.read(
            "dp-composite",
            "tables.cpu_channel_video_table[2,1]"
            ".indexes.cpu_channel_video_index",
        )
        == 1
    )
    with pytest.raises(RuntimePathError):
        runtime.read(
            "dp-composite",
            "tables.cpu_channel_video_table[1,2]"
            ".cpu_channel_video_cable",
        )


@pytest.mark.parametrize("row_key", ["", "01", "+1", "-0", "1,", "1, 2", "1.2"])
def test_noncanonical_row_keys_are_rejected(row_key):
    with pytest.raises(RuntimePathError):
        parse_row_key(row_key)


def test_duplicate_composite_fixture_row_rejects_entire_construction():
    fixture = _dp_fixture_with_composite_row(2, 1)
    payload = fixture.model_dump(mode="python")
    tables = []
    for table in payload["tables"]:
        current = dict(table)
        if current["table_id"] == "cpu_channel_video_table":
            current["rows"] = (current["rows"][0], current["rows"][0])
        tables.append(current)
    payload["tables"] = tuple(tables)

    with pytest.raises(RuntimeValueError, match="duplicate fixture row"):
        RuntimeState.single(
            "duplicate-row",
            get_profile("dp12_mux_atc"),
            FixtureSpec.model_validate(payload),
        )


def test_composite_fixture_index_name_order_is_not_dict_order():
    fixture = _dp_fixture_with_composite_row(2, 1)
    payload = fixture.model_dump(mode="python")
    tables = []
    for table in payload["tables"]:
        current = dict(table)
        if current["table_id"] == "cpu_channel_video_table":
            row = dict(current["rows"][0])
            row["indexes"] = tuple(reversed(row["indexes"]))
            current["rows"] = (row,)
        tables.append(current)
    payload["tables"] = tuple(tables)

    with pytest.raises(RuntimeValueError, match="indexes must be exactly"):
        RuntimeState.single(
            "wrong-index-order",
            get_profile("dp12_mux_atc"),
            FixtureSpec.model_validate(payload),
        )


@pytest.mark.parametrize(
    "path",
    [
        "identity.device_id",
        "identity.profile_id",
        "identity.profile_version",
        "identity.host",
        "identity.snmp_port",
        "identity.system_oid",
        "runtime.availability",
        "tables.cpu_channel_video_table[1,1]"
        ".indexes.cpu_channel_index",
    ],
)
def test_structural_fields_and_indexes_are_read_only(path):
    runtime = _runtime()
    before = runtime.snapshot()

    with pytest.raises(RuntimePathError, match="read-only"):
        runtime.patch("device-dp12_mux_atc", [(path, "mutate")])

    assert runtime.snapshot() == before


def test_duplicate_patch_path_is_rejected_without_last_write_wins():
    runtime = _runtime()
    before = runtime.snapshot()

    with pytest.raises(RuntimePathError, match="duplicate patch path"):
        runtime.patch(
            "device-dp12_mux_atc",
            [
                ("scalars.main_power", 0),
                ("scalars.main_power", 1),
            ],
        )

    assert runtime.snapshot() == before


def test_noop_patch_is_idempotent():
    runtime = _runtime()
    before = runtime.snapshot()

    result = runtime.patch(
        "device-dp12_mux_atc",
        {"scalars.main_power": 1},
    )

    assert result.changed_paths == ()
    assert result.changed is False
    assert result.committed_values == ()
    assert result.event is None
    assert runtime.snapshot() == before


def test_reset_restores_values_and_availability_in_one_commit():
    runtime = _runtime()
    runtime.patch("device-dp12_mux_atc", {"scalars.main_power": 0})
    runtime.action("device-dp12_mux_atc", RuntimeAction.DISCONNECT)
    revision_before_reset = runtime.revision
    events_before_reset = len(runtime.events())

    result = runtime.reset("device-dp12_mux_atc")

    assert result.revision == revision_before_reset + 1
    assert set(result.changed_paths) == {
        "scalars.main_power",
        "runtime.availability",
    }
    assert runtime.read("device-dp12_mux_atc", "scalars.main_power") == 1
    assert (
        runtime.read("device-dp12_mux_atc", "runtime.availability")
        == Availability.CONNECTED.value
    )
    assert len(runtime.events()) == events_before_reset + 1
    assert runtime.reset("device-dp12_mux_atc").event is None


def test_action_transition_table_and_idempotency():
    runtime = _runtime()
    device_id = "device-dp12_mux_atc"

    assert runtime.action(device_id, "restore").event is None
    disconnected = runtime.action(device_id, "disconnect")
    assert disconnected.availability == "disconnected"
    assert runtime.action(device_id, "disconnect").event is None

    powered_off = runtime.action(device_id, "power_off")
    assert powered_off.previous_availability == "disconnected"
    assert powered_off.availability == "powered_off"
    assert powered_off.changed is True
    assert powered_off.committed_values == (
        ("runtime.availability", "powered_off"),
    )
    before_invalid = runtime.snapshot()
    with pytest.raises(RuntimeTransitionError):
        runtime.action(device_id, "disconnect")
    assert runtime.snapshot() == before_invalid

    restored = runtime.action(device_id, "restore")
    assert restored.availability == "connected"
    assert [event.revision for event in runtime.events()] == [2, 3, 4]


def test_actions_never_guess_profile_power_field_names():
    runtime = _runtime()
    before = runtime.renderable_snapshot("device-dp12_mux_atc")

    runtime.action("device-dp12_mux_atc", "power_off")
    after = runtime.renderable_snapshot("device-dp12_mux_atc")

    assert (
        after["device"]["scalars"]["main_power"]
        == before["device"]["scalars"]["main_power"]
    )
    assert after["device"]["availability"] == "powered_off"


def test_multi_device_runtime_has_one_global_revision_and_event_stream():
    profile = get_profile("visionxs_cpu")
    fixture = DEFAULT_FIXTURES["visionxs_cpu"]
    runtime = RuntimeState(
        [
            RuntimeDeviceSpec("cpu-a", profile, fixture),
            RuntimeDeviceSpec("cpu-b", profile, fixture),
        ]
    )

    first = runtime.patch("cpu-a", {"scalars.main_power": 0})
    second = runtime.patch("cpu-b", {"scalars.main_power": 0})

    assert (first.revision, second.revision, runtime.revision) == (2, 3, 3)
    assert [event.device_id for event in runtime.events()] == ["cpu-a", "cpu-b"]
    assert runtime.snapshot("cpu-a")["revision"] == 3
    assert runtime.snapshot("cpu-b")["revision"] == 3
    assert "revision" not in runtime.snapshot("cpu-a")["device"]


def test_concurrent_multi_device_writers_share_one_gapless_revision_stream():
    profile = get_profile("visionxs_cpu")
    fixture = DEFAULT_FIXTURES["visionxs_cpu"]
    device_ids = tuple(f"cpu-{index}" for index in range(4))
    runtime = RuntimeState(
        [
            RuntimeDeviceSpec(device_id, profile, fixture)
            for device_id in device_ids
        ]
    )

    def writer(device_id: str) -> None:
        for value in [0, 1] * 25:
            runtime.patch(device_id, {"scalars.main_power": value})

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(writer, device_id)
            for device_id in device_ids
        ]
        for future in futures:
            future.result()

    events = runtime.events()
    assert len(events) == EVENT_HISTORY_LIMIT
    assert runtime.revision == INITIAL_REVISION + 200
    assert [event.revision for event in events] == list(range(102, 202))
    assert all(
        runtime.read(device_id, "scalars.main_power") == 1
        for device_id in device_ids
    )


def test_snapshot_registry_and_rendered_values_do_not_leak_mutable_state():
    runtime = _runtime()
    snapshot = runtime.snapshot("device-dp12_mux_atc")
    rendered = runtime.renderable_snapshot("device-dp12_mux_atc")
    registry = runtime.path_registry("device-dp12_mux_atc").to_dict()

    snapshot["device"]["scalars"]["main_power"] = 99
    snapshot["device"]["path_registry"]["writable_paths"].clear()
    rendered["device"]["scalars"]["main_power"] = 88
    registry["paths"].clear()

    assert runtime.read("device-dp12_mux_atc", "scalars.main_power") == 1
    assert runtime.path_registry("device-dp12_mux_atc").writable_paths


def test_path_registry_returns_a_defensive_registry_copy():
    runtime = _runtime()
    exposed = runtime.path_registry("device-dp12_mux_atc")
    expected = exposed.writable_paths

    exposed._ordered = ()
    exposed._specs = {}

    assert runtime.path_registry("device-dp12_mux_atc").writable_paths == expected


def test_registry_order_comes_from_profile_schema_and_numeric_row_keys():
    profile = get_profile("dp12_mux_atc")
    fixture = DEFAULT_FIXTURES["dp12_mux_atc"]
    payload = fixture.model_dump(mode="python")
    payload["scalar_values"] = tuple(reversed(payload["scalar_values"]))
    reversed_tables = []
    for table in reversed(payload["tables"]):
        current = dict(table)
        rows = []
        for row in reversed(current["rows"]):
            current_row = dict(row)
            current_row["values"] = tuple(
                reversed(current_row["values"])
            )
            rows.append(current_row)
        current["rows"] = tuple(rows)
        reversed_tables.append(current)
    payload["tables"] = tuple(reversed_tables)
    reordered = FixtureSpec.model_validate(payload)

    canonical = RuntimeState.single("d", profile, fixture)
    shuffled = RuntimeState.single("d", profile, reordered)
    canonical_paths = [
        item.path for item in canonical.path_registry("d")
    ]
    shuffled_paths = [
        item.path for item in shuffled.path_registry("d")
    ]

    assert shuffled_paths == canonical_paths
    assert (
        shuffled.renderable_snapshot("d")["device"]
        == canonical.renderable_snapshot("d")["device"]
    )
    first_table_path = next(
        index
        for index, path in enumerate(canonical_paths)
        if path.startswith("tables.")
    )
    first_column_path = next(
        index
        for index, spec in enumerate(canonical.path_registry("d"))
        if spec.kind == "column"
    )
    assert canonical.path_registry("d").to_dict()["paths"][
        first_table_path
    ]["kind"] == "index"
    assert first_table_path < first_column_path


def test_public_patch_and_reset_apis_cannot_inject_changed_paths():
    runtime = _runtime()

    with pytest.raises(TypeError):
        runtime.patch(
            "device-dp12_mux_atc",
            {"scalars.main_power": 0},
            additional_changed_paths=("forged.path",),
        )
    with pytest.raises(TypeError):
        runtime.reset_all(additional_changed_paths=("forged.path",))
    assert not hasattr(runtime, "record_domain_change")
    assert runtime.revision == 1
    assert runtime.events() == ()


def test_patch_batch_limit_accepts_100_distinct_paths_and_rejects_101():
    runtime = _runtime("ccdm_matrix")
    device_id = "device-ccdm_matrix"
    writable_paths = runtime.path_registry(device_id).writable_paths
    assert len(writable_paths) >= 101

    accepted = [
        (path, runtime.read(device_id, path))
        for path in writable_paths[:100]
    ]
    before = runtime.snapshot()
    result = runtime.patch(device_id, accepted)
    assert result.changed is False
    assert runtime.snapshot() == before

    rejected = [
        (path, runtime.read(device_id, path))
        for path in writable_paths[:101]
    ]
    with pytest.raises(RuntimePathError, match="at most 100"):
        runtime.patch(device_id, rejected)
    assert runtime.snapshot() == before


def test_ccdc_empty_vendor_profile_builds_without_inventing_objects():
    profile = get_profile("ccdc_legacy")
    fixture = FixtureSpec(
        fixture_id="empty-ccdc",
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        evidence_version=profile.evidence_version,
    )
    runtime = RuntimeState.single("ccdc-empty", profile, fixture)

    rendered = runtime.renderable_snapshot("ccdc-empty")
    assert rendered["device"]["scalars"] == {}
    assert rendered["device"]["tables"] == {}
    assert runtime.path_registry("ccdc-empty").writable_paths == ()


def test_concurrent_batch_writes_and_snapshots_never_observe_half_state():
    runtime = _runtime()
    device_id = "device-dp12_mux_atc"

    def writer() -> None:
        for value in [0, 1] * 100:
            runtime.patch(
                device_id,
                [
                    ("scalars.main_power", value),
                    ("scalars.network_interface0", value),
                ],
            )

    def reader() -> None:
        for _ in range(400):
            snapshot = runtime.renderable_snapshot(device_id)["device"]["scalars"]
            assert snapshot["main_power"] == snapshot["network_interface0"]

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(writer)]
        futures.extend(executor.submit(reader) for _ in range(4))
        for future in futures:
            future.result()


def test_deterministic_random_invalid_batches_preserve_all_observables():
    # Hypothesis is not installed in the project environment.  Keep a seeded
    # adversarial loop so this gate remains deterministic and reproducible.
    runtime = _runtime()
    rng = random.Random(20260731)
    invalid_values = [
        True,
        "not-an-integer",
        -1,
        2,
        rng.randint(3, 10_000),
    ]

    for invalid in invalid_values * 20:
        before_state = runtime.snapshot()
        before_render = runtime.renderable_snapshot()
        before_events = runtime.events()
        before_revision = runtime.revision
        with pytest.raises(RuntimeValueError):
            runtime.patch(
                "device-dp12_mux_atc",
                [
                    ("scalars.temperature1", f"{rng.random():.6f}"),
                    ("scalars.main_power", invalid),
                ],
            )
        assert runtime.snapshot() == before_state
        assert runtime.renderable_snapshot() == before_render
        assert runtime.events() == before_events
        assert runtime.revision == before_revision


def test_deterministic_random_row_keys_and_legal_patches_are_consistent():
    # Reproducible property substitute while Hypothesis is not installed.
    rng = random.Random(20260731)
    for _ in range(500):
        indexes = tuple(
            rng.randint(-10_000, 10_000)
            for _ in range(rng.randint(1, 4))
        )
        encoded = format_row_key(indexes)
        assert parse_row_key(encoded) == indexes
        assert format_row_key(parse_row_key(encoded)) == encoded

    runtime = _runtime()
    device_id = "device-dp12_mux_atc"
    for _ in range(200):
        main_power = rng.choice((0, 1))
        temperature = f"{rng.uniform(-40, 125):.6f}"
        result = runtime.patch(
            device_id,
            [
                ("scalars.main_power", main_power),
                ("scalars.temperature1", temperature),
            ],
        )
        rendered = runtime.renderable_snapshot(device_id)
        snapshot = runtime.snapshot(device_id)
        assert runtime.read(device_id, "scalars.main_power") == main_power
        assert runtime.read(device_id, "scalars.temperature1") == temperature
        assert rendered["device"]["scalars"]["main_power"] == main_power
        assert rendered["device"]["scalars"]["temperature1"] == temperature
        assert snapshot["device"]["scalars"]["main_power"] == main_power
        assert snapshot["device"]["scalars"]["temperature1"] == temperature
        assert result.revision == rendered["revision"] == snapshot["revision"]


class _FailingDateTime:
    @classmethod
    def now(cls, _timezone):
        raise RuntimeError("injected timestamp failure")


def test_patch_event_materialization_failure_has_zero_side_effects(monkeypatch):
    runtime = _runtime()
    before = runtime.snapshot()
    monkeypatch.setattr(runtime_state_module, "datetime", _FailingDateTime)

    with pytest.raises(RuntimeError, match="injected timestamp failure"):
        runtime.patch(
            "device-dp12_mux_atc",
            {"scalars.main_power": 0},
        )

    assert runtime.snapshot() == before


def test_action_event_materialization_failure_has_zero_side_effects(monkeypatch):
    runtime = _runtime()
    before = runtime.snapshot()
    monkeypatch.setattr(runtime_state_module, "datetime", _FailingDateTime)

    with pytest.raises(RuntimeError, match="injected timestamp failure"):
        runtime.action("device-dp12_mux_atc", RuntimeAction.DISCONNECT)

    assert runtime.snapshot() == before


def test_reset_event_materialization_failure_has_zero_side_effects(monkeypatch):
    runtime = _runtime()
    runtime.patch("device-dp12_mux_atc", {"scalars.main_power": 0})
    before = runtime.snapshot()
    monkeypatch.setattr(runtime_state_module, "datetime", _FailingDateTime)

    with pytest.raises(RuntimeError, match="injected timestamp failure"):
        runtime.reset("device-dp12_mux_atc")

    assert runtime.snapshot() == before


def test_reset_all_event_materialization_failure_has_zero_side_effects(
    monkeypatch,
):
    runtime = _runtime()
    runtime.patch("device-dp12_mux_atc", {"scalars.main_power": 0})
    before = runtime.snapshot()
    monkeypatch.setattr(runtime_state_module, "datetime", _FailingDateTime)

    with pytest.raises(RuntimeError, match="injected timestamp failure"):
        runtime.reset_all()

    assert runtime.snapshot() == before


def test_event_history_is_bounded_without_changing_revision_truth():
    runtime = _runtime()
    device_id = "device-dp12_mux_atc"
    for value in [0, 1] * ((EVENT_HISTORY_LIMIT // 2) + 5):
        runtime.patch(device_id, {"scalars.main_power": value})

    assert len(runtime.events()) == EVENT_HISTORY_LIMIT
    assert runtime.events()[-1].revision == runtime.revision
    assert runtime.events()[0].revision == runtime.revision - EVENT_HISTORY_LIMIT + 1
