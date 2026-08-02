import asyncio
import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.discovery import DiscoveryConfig, DiscoveryJob
from app.services import discovery as discovery_module
from app.services.discovery import (
    DiscoveryAlreadyRunning,
    DiscoveryProbeResult,
    DiscoveryService,
    DiscoveryValidationError,
    SYS_OBJECT_ID,
    SYS_OBJECT_ID_TUPLE,
    identify_profile,
    probe_sys_object_id,
    validate_ipv4_cidr,
)
from kvm_profiles import PROFILE_CATALOG


@pytest_asyncio.fixture
async def discovery_session_factory(tmp_path):
    database_path = tmp_path / "discovery.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[
                    Device.__table__,
                    DiscoveryConfig.__table__,
                    DiscoveryJob.__table__,
                    AuditLog.__table__,
                ],
            )
        )
    yield factory
    await engine.dispose()


def test_ipv4_cidr_is_limited_to_256_usable_hosts():
    network, hosts = validate_ipv4_cidr("192.0.2.19/24")

    assert network.with_prefixlen == "192.0.2.0/24"
    assert len(hosts) == 254

    with pytest.raises(DiscoveryValidationError) as too_large:
        validate_ipv4_cidr("192.0.2.0/23")
    assert too_large.value.fields == {
        "cidr": "Maximum 256 usable hosts"
    }

    with pytest.raises(DiscoveryValidationError, match="IPv4"):
        validate_ipv4_cidr("2001:db8::/120")


def test_loopback_cidrs_scan_usable_hosts_and_allow_single_host_probe():
    network, hosts = validate_ipv4_cidr("127.0.0.0/24")

    assert network.with_prefixlen == "127.0.0.0/24"
    assert len(hosts) == 254
    assert hosts[0] == "127.0.0.1"
    assert hosts[-1] == "127.0.0.254"
    assert "127.0.0.0" not in hosts
    assert "127.0.0.255" not in hosts

    single_network, single_hosts = validate_ipv4_cidr("127.0.0.2/32")
    assert single_network.with_prefixlen == "127.0.0.2/32"
    assert single_hosts == ("127.0.0.2",)


@pytest.mark.asyncio
async def test_loopback_single_host_discovery_imports_mocked_snmp_agent(
    discovery_session_factory,
):
    profile = PROFILE_CATALOG["visionxs_con"]
    probe_calls = []

    async def fake_probe(host, port, community, **kwargs):
        probe_calls.append((host, port, community, kwargs))
        if host == "127.0.0.2":
            return DiscoveryProbeResult(
                sys_object_id=profile.sys_object_id,
                identity={"serial_number": "LOOPBACK-CON-01"},
            )
        return None

    service = DiscoveryService(
        discovery_session_factory,
        fake_probe,
        _noop_initial_poll,
    )
    async with discovery_session_factory() as db:
        await service.update_config(
            db,
            {
                "cidr": "127.0.0.2/32",
                "community": "loopback-private-value",
                "snmp_port": 161,
                "timeout_seconds": 0.2,
                "retries": 0,
                "concurrency": 1,
                "enabled": True,
                "scan_on_startup": False,
            },
        )
        job = await service.create_scan_job(db, requested_by=4)
        job_id = job.id

    await service.run_job(job_id)

    async with discovery_session_factory() as db:
        completed = await db.get(DiscoveryJob, job_id)
        devices = list((await db.execute(select(Device))).scalars())

    assert probe_calls == [
        (
            "127.0.0.2",
            161,
            "loopback-private-value",
            {"timeout": 0.2, "retries": 0},
        )
    ]
    assert completed.status == "completed"
    assert completed.total_hosts == 1
    assert completed.recognized_hosts == 1
    assert completed.imported_devices == 1
    assert completed.results["hosts"][0]["host"] == "127.0.0.2"
    assert completed.results["hosts"][0]["initial_poll"] == "completed"
    assert "loopback-private-value" not in json.dumps(completed.results["hosts"])
    assert len(devices) == 1
    assert devices[0].host == "127.0.0.2"
    assert devices[0].port == 161


def test_identification_matches_exactly_the_five_catalog_profiles():
    identified = {
        identify_profile(profile.sys_object_id).profile_id
        for profile in PROFILE_CATALOG.values()
    }

    assert identified == {
        "ccdc_legacy",
        "ccdm_matrix",
        "dp12_mux_atc",
        "visionxs_con",
        "visionxs_cpu",
    }
    assert identify_profile("1.3.6.1.4.1.32828.3.257") is None
    assert identify_profile("1.3.6.1.4.1.32828.3.257.16.1") is None


def test_normalize_sys_object_id_unwraps_pysnmp_object_identity():
    profile = PROFILE_CATALOG["ccdc_legacy"]

    value = _OidIdentityValue(profile.sys_object_id)

    assert discovery_module.normalize_sys_object_id(value) == profile.sys_object_id
    assert identify_profile(value).profile_id == profile.profile_id


@pytest.mark.asyncio
async def test_probe_uses_v2c_for_sys_object_id_and_identity_scalars(
    monkeypatch,
):
    calls = {"community": [], "get_cmd": [], "identities": []}
    profile = PROFILE_CATALOG["ccdm_matrix"]

    class DummyEngine:
        transportDispatcher = None

    def fake_community(value, **kwargs):
        calls["community"].append((value, kwargs))
        return ("community", value, kwargs)

    def fake_target(value, **kwargs):
        calls["target"] = (value, kwargs)
        return ("target", value, kwargs)

    def fake_identity(*value):
        calls["identities"].append(value)
        return ("identity", value)

    def fake_object_type(value):
        calls.setdefault("object_types", []).append(value)
        return ("object_type", value)

    async def fake_get_cmd(*args):
        calls["get_cmd"].append(args)
        if len(calls["get_cmd"]) == 1:
            return None, 0, 0, [
                (SYS_OBJECT_ID, _OidValue(profile.sys_object_id))
            ]
        return None, 0, 0, [
            ("device_type", _OidValue("ControlCenter-Digital")),
            ("serial_number", _OidValue("CCDM-SERIAL-01")),
            ("ether_address0", _OidValue("00-11-22-33-44-55")),
            ("ether_address1", _OidValue("00-11-22-33-44-66")),
            ("firmware_version", _OidValue("1.2.3")),
        ]

    monkeypatch.setattr(discovery_module, "SnmpEngine", DummyEngine)
    monkeypatch.setattr(discovery_module, "CommunityData", fake_community)
    monkeypatch.setattr(discovery_module, "UdpTransportTarget", fake_target)
    monkeypatch.setattr(discovery_module, "ContextData", lambda: "context")
    monkeypatch.setattr(discovery_module, "ObjectIdentity", fake_identity)
    monkeypatch.setattr(discovery_module, "ObjectType", fake_object_type)
    monkeypatch.setattr(discovery_module, "getCmd", fake_get_cmd)

    result = await probe_sys_object_id(
        "192.0.2.10",
        161,
        "private-value",
        timeout=0.5,
        retries=0,
    )

    assert result == DiscoveryProbeResult(
        sys_object_id=profile.sys_object_id,
        identity={
            "device_type": "ControlCenter-Digital",
            "serial_number": "CCDM-SERIAL-01",
            "ether_address0": "00-11-22-33-44-55",
            "ether_address1": "00-11-22-33-44-66",
            "firmware_version": "1.2.3",
        },
    )
    assert calls["community"] == [
        ("private-value", {"mpModel": 1}),
        ("private-value", {"mpModel": 1}),
    ]
    assert calls["target"] == (
        ("192.0.2.10", 161),
        {"timeout": 0.5, "retries": 0},
    )
    assert calls["identities"][0] == (SYS_OBJECT_ID_TUPLE,)
    assert len(calls["identities"]) == 6
    assert calls["object_types"][0] == (
        "identity",
        (SYS_OBJECT_ID_TUPLE,),
    )
    assert len(calls["get_cmd"]) == 2
    assert len(calls["get_cmd"][0]) == 5
    assert len(calls["get_cmd"][1]) == 9


@pytest.mark.asyncio
async def test_scan_imports_all_five_profiles_and_persists_safe_results(
    discovery_session_factory,
):
    profile_oids = [
        profile.sys_object_id for profile in PROFILE_CATALOG.values()
    ]
    observed_calls = []
    initial_poll_calls = []

    async def fake_probe(host, port, community, **kwargs):
        observed_calls.append((host, port, community, kwargs))
        host_index = int(host.rsplit(".", 1)[1]) - 1
        if host_index < len(profile_oids):
            return profile_oids[host_index]
        return "1.3.6.1.4.1.32828.999.1"

    async def fake_initial_poll(device_id):
        initial_poll_calls.append(device_id)

    service = DiscoveryService(
        discovery_session_factory,
        fake_probe,
        fake_initial_poll,
    )
    async with discovery_session_factory() as db:
        await service.update_config(
            db,
            {
                "cidr": "192.0.2.0/29",
                "community": "private-value",
                "snmp_port": 1161,
                "timeout_seconds": 0.25,
                "retries": 0,
                "concurrency": 6,
                "enabled": True,
                "scan_on_startup": False,
            },
        )
        job = await service.create_scan_job(db, requested_by=7)
        job_id = job.id

    await service.run_job(job_id)

    async with discovery_session_factory() as db:
        job = await db.get(DiscoveryJob, job_id)
        devices = list(
            (
                await db.execute(select(Device).order_by(Device.profile_id))
            ).scalars()
        )

    assert job.status == "completed"
    assert job.total_hosts == 6
    assert job.scanned_hosts == 6
    assert job.responded_hosts == 6
    assert job.recognized_hosts == 5
    assert job.imported_devices == 5
    assert job.updated_devices == 0
    assert job.unsupported_devices == 1
    assert job.no_response_hosts == 0
    assert job.error_count == 0
    assert {device.profile_id for device in devices} == set(PROFILE_CATALOG)
    assert all(device.discovery_source == "auto" for device in devices)
    assert all(device.community == "private-value" for device in devices)
    assert all(call[1] == 1161 for call in observed_calls)
    assert all(call[3] == {"timeout": 0.25, "retries": 0}
               for call in observed_calls)
    assert set(initial_poll_calls) == {device.id for device in devices}
    assert {
        item["initial_poll"]
        for item in job.results["hosts"]
        if item.get("action") == "imported"
    } == {"completed"}
    public_results = json.dumps(job.results["hosts"])
    assert "private-value" not in public_results
    assert "community" not in public_results
    assert job.results["config_snapshot"]["community"] == "private-value"


@pytest.mark.asyncio
async def test_scan_updates_existing_device_without_replacing_its_id(
    discovery_session_factory,
):
    profile = PROFILE_CATALOG["visionxs_cpu"]

    async def fake_probe(host, port, community, **kwargs):
        if host == "198.51.100.1":
            return profile.sys_object_id
        return None

    service = DiscoveryService(
        discovery_session_factory,
        fake_probe,
        _noop_initial_poll,
    )
    async with discovery_session_factory() as db:
        db.add(
            Device(
                id="existing-device",
                name="Existing",
                host="198.51.100.1",
                port=161,
                community="old-value",
            )
        )
        await db.commit()
        await service.update_config(
            db,
            {
                "cidr": "198.51.100.0/30",
                "community": "new-private-value",
                "snmp_port": 161,
                "timeout_seconds": 0.2,
                "retries": 0,
                "concurrency": 2,
                "enabled": True,
                "scan_on_startup": False,
            },
        )
        job = await service.create_scan_job(db, requested_by=None)
        job_id = job.id

    await service.run_job(job_id)

    async with discovery_session_factory() as db:
        job = await db.get(DiscoveryJob, job_id)
        devices = list((await db.execute(select(Device))).scalars())

    assert job.imported_devices == 0
    assert job.updated_devices == 1
    assert job.no_response_hosts == 1
    assert len(devices) == 1
    assert devices[0].id == "existing-device"
    assert devices[0].profile_id == "visionxs_cpu"
    assert devices[0].community == "new-private-value"


@pytest.mark.asyncio
async def test_running_progress_is_committed_and_second_job_is_rejected(
    discovery_session_factory,
):
    release_second_host = asyncio.Event()
    first_host_returned = asyncio.Event()
    profile = PROFILE_CATALOG["ccdm_matrix"]

    async def controlled_probe(host, port, community, **kwargs):
        if host == "203.0.113.1":
            first_host_returned.set()
            return profile.sys_object_id
        await release_second_host.wait()
        return None

    service = DiscoveryService(
        discovery_session_factory,
        controlled_probe,
        _noop_initial_poll,
    )
    async with discovery_session_factory() as db:
        await service.update_config(
            db,
            {
                "cidr": "203.0.113.0/30",
                "community": "private-value",
                "snmp_port": 161,
                "timeout_seconds": 0.2,
                "retries": 0,
                "concurrency": 2,
                "enabled": True,
                "scan_on_startup": False,
            },
        )
        job = await service.create_scan_job(db, requested_by=1)
        job_id = job.id
        with pytest.raises(DiscoveryAlreadyRunning) as conflict:
            await service.create_scan_job(db, requested_by=1)
        assert conflict.value.job.id == job_id

    run_task = asyncio.create_task(service.run_job(job_id))
    await asyncio.wait_for(first_host_returned.wait(), timeout=1)

    persisted_progress = None
    for _ in range(100):
        async with discovery_session_factory() as db:
            persisted_progress = await db.get(DiscoveryJob, job_id)
            if persisted_progress.scanned_hosts == 1:
                break
        await asyncio.sleep(0.01)

    assert persisted_progress.status == "running"
    assert persisted_progress.scanned_hosts == 1
    assert persisted_progress.recognized_hosts == 1

    release_second_host.set()
    await asyncio.wait_for(run_task, timeout=1)
    async with discovery_session_factory() as db:
        completed = await db.get(DiscoveryJob, job_id)
    assert completed.status == "completed"
    assert completed.scanned_hosts == 2


@pytest.mark.asyncio
async def test_scan_uses_the_complete_creation_time_config_snapshot(
    discovery_session_factory,
):
    observed_calls = []
    profile = PROFILE_CATALOG["visionxs_con"]

    async def fake_probe(host, port, community, **kwargs):
        observed_calls.append((host, port, community, kwargs))
        return profile.sys_object_id if host.endswith(".1") else None

    service = DiscoveryService(
        discovery_session_factory,
        fake_probe,
        _noop_initial_poll,
    )
    async with discovery_session_factory() as db:
        await service.update_config(
            db,
            {
                "cidr": "192.0.2.0/30",
                "community": "snapshot-community",
                "snmp_port": 1161,
                "timeout_seconds": 0.25,
                "retries": 1,
                "concurrency": 2,
                "enabled": True,
                "scan_on_startup": False,
            },
        )
        job = await service.create_scan_job(db, requested_by=11)
        job_id = job.id
        await service.update_config(
            db,
            {
                "cidr": "198.51.100.0/30",
                "community": "new-community",
                "snmp_port": 2161,
                "timeout_seconds": 1.5,
                "retries": 3,
                "concurrency": 1,
                "enabled": False,
                "scan_on_startup": True,
            },
        )

    await service.run_job(job_id)

    assert {call[0] for call in observed_calls} == {
        "192.0.2.1",
        "192.0.2.2",
    }
    assert all(call[1] == 1161 for call in observed_calls)
    assert all(call[2] == "snapshot-community" for call in observed_calls)
    assert all(
        call[3] == {"timeout": 0.25, "retries": 1}
        for call in observed_calls
    )
    async with discovery_session_factory() as db:
        completed = await db.get(DiscoveryJob, job_id)
    assert completed.results["config_snapshot"] == {
        "cidr": "192.0.2.0/30",
        "community": "snapshot-community",
        "snmp_port": 1161,
        "timeout_seconds": 0.25,
        "retries": 1,
        "concurrency": 2,
        "enabled": True,
        "scan_on_startup": False,
        "config_updated_at": completed.results["config_snapshot"][
            "config_updated_at"
        ],
    }


@pytest.mark.asyncio
async def test_identity_deduplicates_across_addresses_and_audits_each_outcome(
    discovery_session_factory,
):
    profile = PROFILE_CATALOG["ccdm_matrix"]
    initial_poll_calls = []

    async def fake_probe(host, port, community, **kwargs):
        if host.endswith(".1") or host.endswith(".2"):
            return DiscoveryProbeResult(
                sys_object_id=profile.sys_object_id,
                identity={
                    "device_type": "ControlCenter-Digital",
                    "serial_number": "Shared-Serial-01",
                    "ether_address0": "00-11-22-33-44-55",
                },
            )
        if host.endswith(".3"):
            return "1.3.6.1.4.1.32828.999.1"
        raise RuntimeError("probe failed")

    async def fake_initial_poll(device_id):
        initial_poll_calls.append(device_id)

    service = DiscoveryService(
        discovery_session_factory,
        fake_probe,
        fake_initial_poll,
    )
    async with discovery_session_factory() as db:
        await service.update_config(
            db,
            {
                "cidr": "203.0.113.0/29",
                "community": "identity-community",
                "snmp_port": 161,
                "timeout_seconds": 0.2,
                "retries": 0,
                "concurrency": 6,
                "enabled": True,
                "scan_on_startup": False,
            },
        )
        job = await service.create_scan_job(db, requested_by=23)
        job_id = job.id

    await service.run_job(job_id)

    async with discovery_session_factory() as db:
        completed = await db.get(DiscoveryJob, job_id)
        devices = list((await db.execute(select(Device))).scalars())
        audits = list(
            (
                await db.execute(
                    select(AuditLog).order_by(AuditLog.id)
                )
            ).scalars()
        )

    assert len(devices) == 1
    assert devices[0].profile_id == profile.profile_id
    assert devices[0].serial_number == "Shared-Serial-01"
    assert devices[0].mac_addresses == ["00:11:22:33:44:55"]
    assert completed.imported_devices == 1
    assert completed.updated_devices == 1
    assert completed.unsupported_devices == 1
    assert completed.error_count == 3
    assert initial_poll_calls == [devices[0].id]
    host_results = completed.results["hosts"]
    recognized = [
        item for item in host_results
        if item.get("profile_id") == profile.profile_id
    ]
    assert {item["action"] for item in recognized} == {
        "imported",
        "updated",
    }
    assert {item["identity_key"] for item in recognized} == {
        "serial:shared-serial-01"
    }
    assert {
        item.get("initial_poll")
        for item in recognized
        if item["action"] == "imported"
    } == {"completed"}
    actions = [entry.action for entry in audits]
    assert actions.count("discovery.host.recognized") == 2
    assert actions.count("discovery.host.skipped") == 1
    assert actions.count("discovery.device.imported") == 1
    assert actions.count("discovery.device.updated") == 1
    assert actions.count("discovery.host.failed") == 3
    assert all(
        entry.actor_id == 23
        for entry in audits
        if entry.action.startswith("discovery.")
    )


async def _noop_initial_poll(device_id):
    return None


class _OidValue:
    def __init__(self, value):
        self.value = value

    def prettyPrint(self):
        return self.value


class _OidIdentityValue(_OidValue):
    def getOid(self):
        return tuple(int(arc) for arc in self.value.split("."))
