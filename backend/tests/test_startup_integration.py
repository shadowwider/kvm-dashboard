from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import main
from app.api.router import api_router


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _DiscoveryService:
    def __init__(self, *, enabled: bool, scan_on_startup: bool):
        self.config = SimpleNamespace(
            enabled=enabled,
            scan_on_startup=scan_on_startup,
        )
        self.created = []
        self.ran = []

    async def get_config(self, db):
        return self.config

    async def create_scan_job(self, db, *, requested_by):
        self.created.append(requested_by)
        return SimpleNamespace(id=17, cidr="192.168.1.0/24")

    async def run_job(self, job_id):
        self.ran.append(job_id)


def test_router_registers_multi_profile_admin_routes():
    paths = {route.path for route in api_router.routes}

    assert "/profiles" in paths
    assert "/discovery/config" in paths
    assert "/audit-logs" in paths


def test_full_poll_scheduler_uses_one_second_due_check_tick():
    assert main.FULL_POLL_CHECK_INTERVAL_SECONDS == 1


def test_immediate_scheduler_jobs_are_tracked_by_max_instances(monkeypatch):
    jobs = []
    scheduler = SimpleNamespace(
        add_job=lambda func, **kwargs: jobs.append((func, kwargs))
    )
    first_run_at = datetime.now(timezone.utc)
    monkeypatch.setattr(main.settings, "simulator_bridge_enabled", True)
    monkeypatch.setattr(main.settings, "snmp_health_poll_enabled", True)
    monkeypatch.setattr(main.settings, "snmp_endpoint_status_poll_enabled", True)

    main._register_scheduler_jobs(scheduler, first_run_at)

    assert {kwargs["id"] for _, kwargs in jobs} == {
        "data_retention_cleanup",
        "snmp_poll",
        "snmp_health_probe",
        "snmp_health_heartbeat_flush",
        "simulator_bridge_lease_cleanup",
        "snmp_endpoint_status_probe",
    }
    assert all(kwargs["max_instances"] == 1 for _, kwargs in jobs)
    assert all(kwargs["coalesce"] is True for _, kwargs in jobs)
    jobs_by_id = {kwargs["id"]: kwargs for _, kwargs in jobs}
    assert jobs_by_id["data_retention_cleanup"]["next_run_time"] == (
        first_run_at + timedelta(days=1)
    )
    assert all(
        kwargs["next_run_time"] is first_run_at
        for job_id, kwargs in jobs_by_id.items()
        if job_id != "data_retention_cleanup"
    )


def test_application_logging_is_restored_after_alembic():
    probe = logging.getLogger("app.startup_test")
    original_disabled = probe.disabled
    original_level = logging.getLogger().level
    try:
        probe.disabled = True
        logging.getLogger().setLevel(logging.WARNING)

        main._restore_application_logging()

        assert probe.disabled is False
        assert logging.getLogger().level == logging.INFO
    finally:
        probe.disabled = original_disabled
        logging.getLogger().setLevel(original_level)


@pytest.mark.asyncio
async def test_startup_discovery_runs_when_enabled(monkeypatch):
    service = _DiscoveryService(enabled=True, scan_on_startup=True)
    monkeypatch.setattr(main, "AsyncSessionLocal", _SessionContext)
    monkeypatch.setattr(main, "discovery_service", service)

    await main._run_startup_discovery()

    assert service.created == [None]
    assert service.ran == [17]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled", "scan_on_startup"),
    [(False, True), (True, False), (False, False)],
)
async def test_startup_discovery_skips_when_disabled(
    monkeypatch,
    enabled,
    scan_on_startup,
):
    service = _DiscoveryService(
        enabled=enabled,
        scan_on_startup=scan_on_startup,
    )
    monkeypatch.setattr(main, "AsyncSessionLocal", _SessionContext)
    monkeypatch.setattr(main, "discovery_service", service)

    await main._run_startup_discovery()

    assert service.created == []
    assert service.ran == []
