from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.discovery import DiscoveryConfig, DiscoveryJob
from app.models.oid_registry import OIDRegistry
from app.services.audit import record_audit_log
from kvm_profiles import PROFILE_CATALOG
from kvm_profiles.profile_model import ProfileDef


logger = logging.getLogger(__name__)

SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
SYS_OBJECT_ID_TUPLE = tuple(int(arc) for arc in SYS_OBJECT_ID.split("."))
MAX_USABLE_HOSTS = 256
ACTIVE_JOB_STATUSES = ("queued", "running")
_OID_RE = re.compile(r"^(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*)){1,}$")
_HEX_RE = re.compile(r"^[0-9a-f]+$")
_JOB_SNAPSHOT_KEY = "config_snapshot"
_JOB_RESULTS_KEY = "hosts"
_IDENTITY_FIELDS = {
    "device_type",
    "serial_number",
    "firmware_version",
}
_PROFILE_BY_SYS_OBJECT_ID = {
    profile.sys_object_id: profile for profile in PROFILE_CATALOG.values()
}


class DiscoveryValidationError(ValueError):
    def __init__(self, message: str, fields: Mapping[str, str]):
        super().__init__(message)
        self.fields = dict(fields)


class DiscoveryAlreadyRunning(RuntimeError):
    def __init__(self, job: DiscoveryJob):
        super().__init__(f"Discovery job {job.id} is already {job.status}")
        self.job = job


class DiscoveryJobNotFound(LookupError):
    pass


class DiscoveryProbeError(RuntimeError):
    pass


class DiscoveryIdentityConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class DiscoveryConfigSnapshot:
    cidr: str
    community: str
    snmp_port: int
    timeout_seconds: float
    retries: int
    concurrency: int
    enabled: bool
    scan_on_startup: bool
    config_updated_at: str

    @classmethod
    def from_config(
        cls,
        config: DiscoveryConfig,
        *,
        cidr: str,
    ) -> DiscoveryConfigSnapshot:
        return cls(
            cidr=cidr,
            community=config.community,
            snmp_port=config.snmp_port,
            timeout_seconds=config.timeout_seconds,
            retries=config.retries,
            concurrency=config.concurrency,
            enabled=config.enabled,
            scan_on_startup=config.scan_on_startup,
            config_updated_at=config.updated_at.isoformat(),
        )

    @classmethod
    def from_storage(
        cls,
        value: Mapping[str, Any],
    ) -> DiscoveryConfigSnapshot:
        return cls(
            cidr=str(value["cidr"]),
            community=str(value["community"]),
            snmp_port=int(value["snmp_port"]),
            timeout_seconds=float(value["timeout_seconds"]),
            retries=int(value["retries"]),
            concurrency=int(value["concurrency"]),
            enabled=bool(value["enabled"]),
            scan_on_startup=bool(value["scan_on_startup"]),
            config_updated_at=str(value["config_updated_at"]),
        )

    def to_storage(self) -> dict[str, Any]:
        return {
            "cidr": self.cidr,
            "community": self.community,
            "snmp_port": self.snmp_port,
            "timeout_seconds": self.timeout_seconds,
            "retries": self.retries,
            "concurrency": self.concurrency,
            "enabled": self.enabled,
            "scan_on_startup": self.scan_on_startup,
            "config_updated_at": self.config_updated_at,
        }


@dataclass(frozen=True)
class DiscoveryProbeResult:
    sys_object_id: str
    identity: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HostProbeOutcome:
    host: str
    status: str
    sys_object_id: str | None = None
    profile_id: str | None = None
    identity: Mapping[str, str] = field(default_factory=dict)
    error_code: str | None = None


ProbeCallable = Callable[
    ...,
    Awaitable[DiscoveryProbeResult | str | Mapping[str, Any] | None],
]
InitialPollCallable = Callable[[str], Awaitable[None]]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_ipv4_cidr(
    cidr: str,
) -> tuple[ipaddress.IPv4Network, tuple[str, ...]]:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        raise DiscoveryValidationError(
            "Invalid IPv4 CIDR",
            {"cidr": "A valid IPv4 CIDR is required"},
        ) from exc

    if not isinstance(network, ipaddress.IPv4Network):
        raise DiscoveryValidationError(
            "Only IPv4 CIDR is supported",
            {"cidr": "IPv6 networks are not supported"},
        )

    if network.prefixlen <= 30:
        usable_host_count = network.num_addresses - 2
    else:
        usable_host_count = network.num_addresses
    if usable_host_count > MAX_USABLE_HOSTS:
        raise DiscoveryValidationError(
            "CIDR contains too many hosts",
            {"cidr": f"Maximum {MAX_USABLE_HOSTS} usable hosts"},
        )

    return network, tuple(str(host) for host in network.hosts())


def normalize_sys_object_id(value: Any) -> str:
    get_oid = getattr(value, "getOid", None)
    if callable(get_oid):
        oid_value = get_oid()
        rendered = ".".join(str(arc) for arc in oid_value)
    else:
        rendered = (
            value.prettyPrint()
            if hasattr(value, "prettyPrint")
            else str(value)
        )
    normalized = rendered.strip().lstrip(".")
    if not _OID_RE.fullmatch(normalized):
        raise DiscoveryProbeError("invalid_sys_object_id")
    return normalized


def identify_profile(sys_object_id: Any) -> ProfileDef | None:
    try:
        normalized = normalize_sys_object_id(sys_object_id)
    except DiscoveryProbeError:
        return None
    return _PROFILE_BY_SYS_OBJECT_ID.get(normalized)


def _identity_scalars(profile: ProfileDef):
    return tuple(
        scalar
        for scalar in profile.scalars
        if (
            scalar.canonical_field in _IDENTITY_FIELDS
            or scalar.canonical_field.startswith("ether_address")
        )
    )


def _identity_value(value: Any) -> str | None:
    if value is None or type(value).__name__ in {
        "NoSuchObject",
        "NoSuchInstance",
        "EndOfMibView",
    }:
        return None
    rendered = (
        value.prettyPrint()
        if hasattr(value, "prettyPrint")
        else str(value)
    )
    normalized = rendered.strip()
    return normalized or None


def normalize_mac_address(value: Any) -> str | None:
    rendered = _identity_value(value)
    if rendered is None:
        return None
    lowered = rendered.casefold()
    if lowered.startswith("0x"):
        lowered = lowered[2:]
    compact = re.sub(r"[^0-9a-f]", "", lowered)
    if len(compact) == 12 and _HEX_RE.fullmatch(compact):
        return ":".join(
            compact[index:index + 2] for index in range(0, 12, 2)
        )
    return rendered.casefold()


async def probe_sys_object_id(
    host: str,
    port: int,
    community: str,
    *,
    timeout: float,
    retries: int,
) -> DiscoveryProbeResult | None:
    """Read sysObjectID.0 and the recognized profile's identity scalars."""

    engine = SnmpEngine()
    try:
        target = UdpTransportTarget(
            (host, port),
            timeout=timeout,
            retries=retries,
        )
        error_indication, error_status, _, var_binds = await getCmd(
            engine,
            CommunityData(community, mpModel=1),
            target,
            ContextData(),
            ObjectType(ObjectIdentity(SYS_OBJECT_ID_TUPLE)),
        )
        if error_indication:
            return None
        if error_status:
            raise DiscoveryProbeError("snmp_agent_error")
        if not var_binds:
            return None
        sys_object_id = normalize_sys_object_id(var_binds[0][1])
        profile = _PROFILE_BY_SYS_OBJECT_ID.get(sys_object_id)
        if profile is None:
            return DiscoveryProbeResult(sys_object_id=sys_object_id)

        identity_scalars = _identity_scalars(profile)
        if not identity_scalars:
            return DiscoveryProbeResult(sys_object_id=sys_object_id)

        identity_response = await getCmd(
            engine,
            CommunityData(community, mpModel=1),
            target,
            ContextData(),
            *(
                ObjectType(
                    ObjectIdentity(
                        tuple(
                            int(arc)
                            for arc in scalar.instance_oid.split(".")
                        )
                    )
                )
                for scalar in identity_scalars
            ),
        )
        identity_error, identity_status, _, identity_var_binds = (
            identity_response
        )
        identity: dict[str, str] = {}
        if not identity_error and not identity_status:
            for scalar, var_bind in zip(
                identity_scalars,
                identity_var_binds,
            ):
                value = _identity_value(var_bind[1])
                if value is not None:
                    identity[scalar.canonical_field] = value
        return DiscoveryProbeResult(
            sys_object_id=sys_object_id,
            identity=identity,
        )
    except DiscoveryProbeError:
        raise
    except Exception as exc:
        raise DiscoveryProbeError("snmp_probe_failed") from exc
    finally:
        dispatcher = getattr(engine, "transportDispatcher", None)
        if dispatcher is not None:
            try:
                dispatcher.closeDispatcher()
            except Exception:
                pass


def job_host_results(job: DiscoveryJob) -> list[dict[str, Any]]:
    payload = job.results
    if isinstance(payload, dict):
        hosts = payload.get(_JOB_RESULTS_KEY, [])
        return list(hosts) if isinstance(hosts, list) else []
    return list(payload) if isinstance(payload, list) else []


class DiscoveryService:
    def __init__(
        self,
        session_factory=AsyncSessionLocal,
        probe: ProbeCallable = probe_sys_object_id,
        initial_poll: InitialPollCallable | None = None,
    ):
        self._session_factory = session_factory
        self._probe = probe
        self._initial_poll = initial_poll or self._poll_imported_device
        self._job_creation_lock = asyncio.Lock()
        self._run_lock = asyncio.Lock()
        self._initial_poll_status_lock = asyncio.Lock()

    async def get_config(self, db: AsyncSession) -> DiscoveryConfig:
        config = await db.get(DiscoveryConfig, 1)
        if config is None:
            config = DiscoveryConfig(id=1)
            db.add(config)
            await db.commit()
            await db.refresh(config)
        return config

    async def update_config(
        self,
        db: AsyncSession,
        values: Mapping[str, Any],
    ) -> DiscoveryConfig:
        config = await self.get_config(db)
        candidate = {
            "cidr": values.get("cidr", config.cidr),
            "community": values.get("community", config.community),
            "snmp_port": values.get("snmp_port", config.snmp_port),
            "timeout_seconds": values.get(
                "timeout_seconds", config.timeout_seconds
            ),
            "retries": values.get("retries", config.retries),
            "concurrency": values.get("concurrency", config.concurrency),
            "enabled": values.get("enabled", config.enabled),
            "scan_on_startup": values.get(
                "scan_on_startup", config.scan_on_startup
            ),
        }
        network, _ = validate_ipv4_cidr(str(candidate["cidr"]))
        self._validate_config_values(candidate)

        config.cidr = network.with_prefixlen
        config.community = str(candidate["community"])
        config.snmp_port = int(candidate["snmp_port"])
        config.timeout_seconds = float(candidate["timeout_seconds"])
        config.retries = int(candidate["retries"])
        config.concurrency = int(candidate["concurrency"])
        config.enabled = bool(candidate["enabled"])
        config.scan_on_startup = bool(candidate["scan_on_startup"])
        config.updated_at = utcnow()
        await db.commit()
        await db.refresh(config)
        return config

    async def create_scan_job(
        self,
        db: AsyncSession,
        *,
        requested_by: int | None,
    ) -> DiscoveryJob:
        async with self._job_creation_lock:
            active_result = await db.execute(
                select(DiscoveryJob)
                .where(DiscoveryJob.status.in_(ACTIVE_JOB_STATUSES))
                .order_by(DiscoveryJob.id.desc())
                .limit(1)
            )
            active_job = active_result.scalars().first()
            if active_job is not None:
                raise DiscoveryAlreadyRunning(active_job)

            config = await self.get_config(db)
            network, hosts = validate_ipv4_cidr(config.cidr)
            self._validate_config_values(
                {
                    "community": config.community,
                    "snmp_port": config.snmp_port,
                    "timeout_seconds": config.timeout_seconds,
                    "retries": config.retries,
                    "concurrency": config.concurrency,
                }
            )
            snapshot = DiscoveryConfigSnapshot.from_config(
                config,
                cidr=network.with_prefixlen,
            )
            job = DiscoveryJob(
                status="queued",
                cidr=snapshot.cidr,
                snmp_port=snapshot.snmp_port,
                total_hosts=len(hosts),
                results={
                    _JOB_SNAPSHOT_KEY: snapshot.to_storage(),
                    _JOB_RESULTS_KEY: [],
                },
                requested_by=requested_by,
            )
            db.add(job)
            await db.flush()
            await self._audit(
                db,
                job,
                action="discovery.job.queued",
                target_type="discovery_job",
                target_id=job.id,
                change_summary={
                    "cidr": snapshot.cidr,
                    "snmp_port": snapshot.snmp_port,
                    "timeout_seconds": snapshot.timeout_seconds,
                    "retries": snapshot.retries,
                    "concurrency": snapshot.concurrency,
                },
            )
            await db.commit()
            await db.refresh(job)
            return job

    async def run_job(self, job_id: int) -> None:
        async with self._run_lock:
            try:
                await self._run_job_locked(job_id)
            except asyncio.CancelledError:
                await self._mark_failed(job_id, "discovery_task_cancelled")
                raise
            except Exception:
                logger.exception("Discovery job %s failed", job_id)
                await self._mark_failed(job_id, "discovery_job_failed")

    async def list_jobs(
        self,
        db: AsyncSession,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[DiscoveryJob], int]:
        total = await db.scalar(select(func.count()).select_from(DiscoveryJob))
        result = await db.execute(
            select(DiscoveryJob)
            .order_by(DiscoveryJob.created_at.desc(), DiscoveryJob.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_job(
        self,
        db: AsyncSession,
        job_id: int,
    ) -> DiscoveryJob:
        job = await db.get(DiscoveryJob, job_id)
        if job is None:
            raise DiscoveryJobNotFound(f"Discovery job {job_id} was not found")
        return job

    async def _run_job_locked(self, job_id: int) -> None:
        tasks: list[asyncio.Task[HostProbeOutcome]] = []
        initial_poll_ids: list[str] = []
        async with self._session_factory() as db:
            job = await db.get(DiscoveryJob, job_id)
            if job is None:
                raise DiscoveryJobNotFound(
                    f"Discovery job {job_id} was not found"
                )
            if job.status != "queued":
                return

            snapshot = self._snapshot_from_job(job)
            _, hosts = validate_ipv4_cidr(snapshot.cidr)
            self._validate_config_values(snapshot.to_storage())
            concurrency = min(
                snapshot.concurrency,
                max(len(hosts), 1),
            )

            now = utcnow()
            job.status = "running"
            job.started_at = now
            job.updated_at = now
            job.total_hosts = len(hosts)
            job.scanned_hosts = 0
            job.responded_hosts = 0
            job.recognized_hosts = 0
            job.imported_devices = 0
            job.updated_devices = 0
            job.unsupported_devices = 0
            job.no_response_hosts = 0
            job.error_count = 0
            self._set_job_results(job, snapshot, [])
            await db.commit()

            semaphore = asyncio.Semaphore(concurrency)
            tasks = [
                asyncio.create_task(
                    self._probe_host(
                        host,
                        snapshot.snmp_port,
                        snapshot.community,
                        timeout=snapshot.timeout_seconds,
                        retries=snapshot.retries,
                        semaphore=semaphore,
                    )
                )
                for host in hosts
            ]

            try:
                for completed in asyncio.as_completed(tasks):
                    outcome = await completed
                    try:
                        public_result, initial_poll_id = (
                            await self._apply_outcome(
                                db,
                                job,
                                outcome,
                                snapshot=snapshot,
                            )
                        )
                    except Exception as exc:
                        await db.rollback()
                        job = await db.get(DiscoveryJob, job_id)
                        if job is None:
                            raise DiscoveryJobNotFound(
                                f"Discovery job {job_id} was not found"
                            ) from exc
                        public_result = await self._record_outcome_failure(
                            db,
                            job,
                            outcome,
                            error_code=self._outcome_error_code(exc),
                        )
                        initial_poll_id = None

                    job.scanned_hosts += 1
                    results = job_host_results(job)
                    results.append(public_result)
                    self._set_job_results(job, snapshot, results)
                    job.updated_at = utcnow()
                    await db.commit()
                    if initial_poll_id is not None:
                        initial_poll_ids.append(initial_poll_id)

                job.status = "completed"
                job.finished_at = utcnow()
                job.updated_at = job.finished_at
                await db.commit()
            finally:
                pending = [task for task in tasks if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

        if initial_poll_ids:
            await asyncio.gather(
                *(
                    self._run_initial_poll(job_id, device_id)
                    for device_id in dict.fromkeys(initial_poll_ids)
                )
            )

    async def _probe_host(
        self,
        host: str,
        port: int,
        community: str,
        *,
        timeout: float,
        retries: int,
        semaphore: asyncio.Semaphore,
    ) -> HostProbeOutcome:
        async with semaphore:
            try:
                raw_result = await self._probe(
                    host,
                    port,
                    community,
                    timeout=timeout,
                    retries=retries,
                )
            except DiscoveryProbeError as exc:
                return HostProbeOutcome(
                    host=host,
                    status="error",
                    error_code=str(exc) or "snmp_probe_failed",
                )
            except Exception:
                return HostProbeOutcome(
                    host=host,
                    status="error",
                    error_code="snmp_probe_failed",
                )

        if raw_result is None:
            return HostProbeOutcome(host=host, status="no_response")

        try:
            probe_result = self._coerce_probe_result(raw_result)
            normalized_oid = normalize_sys_object_id(
                probe_result.sys_object_id
            )
        except DiscoveryProbeError:
            return HostProbeOutcome(
                host=host,
                status="error",
                error_code="invalid_sys_object_id",
            )
        profile = _PROFILE_BY_SYS_OBJECT_ID.get(normalized_oid)
        if profile is None:
            return HostProbeOutcome(
                host=host,
                status="unsupported",
                sys_object_id=normalized_oid,
            )
        allowed_fields = {
            scalar.canonical_field
            for scalar in _identity_scalars(profile)
        }
        identity = {
            str(key): value
            for key, raw_value in probe_result.identity.items()
            if str(key) in allowed_fields
            and (value := _identity_value(raw_value)) is not None
        }
        return HostProbeOutcome(
            host=host,
            status="recognized",
            sys_object_id=normalized_oid,
            profile_id=profile.profile_id,
            identity=identity,
        )

    async def _apply_outcome(
        self,
        db: AsyncSession,
        job: DiscoveryJob,
        outcome: HostProbeOutcome,
        *,
        snapshot: DiscoveryConfigSnapshot,
    ) -> tuple[dict[str, Any], str | None]:
        result: dict[str, Any] = {
            "host": outcome.host,
            "status": outcome.status,
        }
        if outcome.status == "no_response":
            job.no_response_hosts += 1
            await self._audit(
                db,
                job,
                action="discovery.host.skipped",
                target_type="discovery_host",
                target_id=outcome.host,
                change_summary={"reason": "no_response"},
            )
            return result, None
        if outcome.status == "error":
            job.error_count += 1
            error_code = outcome.error_code or "snmp_probe_failed"
            result["error"] = error_code
            await self._audit(
                db,
                job,
                action="discovery.host.failed",
                target_type="discovery_host",
                target_id=outcome.host,
                result="failure",
                change_summary={"error": error_code},
            )
            return result, None

        job.responded_hosts += 1
        result["sys_object_id"] = outcome.sys_object_id
        if outcome.status == "unsupported":
            job.unsupported_devices += 1
            await self._audit(
                db,
                job,
                action="discovery.host.skipped",
                target_type="discovery_host",
                target_id=outcome.host,
                change_summary={
                    "reason": "unsupported_profile",
                    "sys_object_id": outcome.sys_object_id,
                },
            )
            return result, None

        profile = PROFILE_CATALOG[outcome.profile_id]
        identity = self._identity_details(
            outcome.identity,
            host=outcome.host,
            port=snapshot.snmp_port,
        )
        await self._audit(
            db,
            job,
            action="discovery.host.recognized",
            target_type="discovery_host",
            target_id=outcome.host,
            change_summary={
                "profile_id": profile.profile_id,
                "sys_object_id": outcome.sys_object_id,
                "identity_key": identity["identity_key"],
            },
        )
        device, created = await self._upsert_device(
            db,
            host=outcome.host,
            port=snapshot.snmp_port,
            community=snapshot.community,
            profile=profile,
            sys_object_id=outcome.sys_object_id or profile.sys_object_id,
            identity=identity,
        )
        job.recognized_hosts += 1
        if created:
            job.imported_devices += 1
            action = "imported"
            initial_poll_status = "queued"
            audit_action = "discovery.device.imported"
        else:
            job.updated_devices += 1
            action = "updated"
            initial_poll_status = None
            audit_action = "discovery.device.updated"
        await self._audit(
            db,
            job,
            action=audit_action,
            target_type="device",
            target_id=device.id,
            change_summary={
                "host": outcome.host,
                "profile_id": profile.profile_id,
                "identity_key": identity["identity_key"],
                "initial_poll": initial_poll_status,
            },
        )
        if created:
            await self._audit(
                db,
                job,
                action="discovery.device.initial_poll_queued",
                target_type="device",
                target_id=device.id,
                change_summary={"job_id": job.id},
            )
        public_identity = {
            key: value
            for key, value in identity["public"].items()
            if value not in (None, [], "")
        }
        result.update(
            {
                "profile_id": profile.profile_id,
                "device_id": device.id,
                "action": action,
                "identity": public_identity,
                "identity_key": identity["identity_key"],
                "initial_poll": initial_poll_status,
            }
        )
        return result, device.id if created else None

    async def _record_outcome_failure(
        self,
        db: AsyncSession,
        job: DiscoveryJob,
        outcome: HostProbeOutcome,
        *,
        error_code: str,
    ) -> dict[str, Any]:
        if outcome.sys_object_id is not None:
            job.responded_hosts += 1
        if outcome.profile_id is not None:
            job.recognized_hosts += 1
            await self._audit(
                db,
                job,
                action="discovery.host.recognized",
                target_type="discovery_host",
                target_id=outcome.host,
                change_summary={
                    "profile_id": outcome.profile_id,
                    "sys_object_id": outcome.sys_object_id,
                },
            )
        job.error_count += 1
        await self._audit(
            db,
            job,
            action="discovery.host.failed",
            target_type="discovery_host",
            target_id=outcome.host,
            result="failure",
            change_summary={"error": error_code},
        )
        return {
            "host": outcome.host,
            "status": "error",
            "sys_object_id": outcome.sys_object_id,
            "profile_id": outcome.profile_id,
            "error": error_code,
        }

    async def _upsert_device(
        self,
        db: AsyncSession,
        *,
        host: str,
        port: int,
        community: str,
        profile: ProfileDef,
        sys_object_id: str,
        identity: Mapping[str, Any],
    ) -> tuple[Device, bool]:
        devices = list(
            (
                await db.execute(select(Device).order_by(Device.id))
            ).scalars()
        )
        device = self._match_device(
            devices,
            host=host,
            port=port,
            profile_id=profile.profile_id,
            serial_number=identity["serial_number"],
            mac_addresses=identity["mac_addresses"],
        )

        now = utcnow()
        created = device is None
        model_name = (
            identity["public"].get("device_type")
            or profile.product
        )
        if created:
            device = Device(
                id=self._device_id(
                    profile.profile_id,
                    host=host,
                    port=port,
                    serial_number=identity["serial_number"],
                    mac_addresses=identity["mac_addresses"],
                ),
                name=f"{model_name} {host}",
                host=host,
                port=port,
                community=community,
            )
            db.add(device)

        device.host = host
        device.port = port
        device.community = community
        device.system_oid = sys_object_id
        device.model_name = model_name
        device.profile_id = profile.profile_id
        device.profile_version = profile.profile_version
        device.profile_evidence_version = profile.evidence_version
        if identity["serial_number"] is not None:
            device.serial_number = identity["serial_number"]
        if identity["mac_addresses"]:
            device.mac_addresses = identity["mac_addresses"]
        device.discovery_source = "auto"
        device.last_discovered_at = now
        device.last_health_check = now
        device.last_status = "online"
        device.is_active = True
        device.updated_at = now
        await db.flush()
        return device, created

    async def _poll_imported_device(self, device_id: str) -> None:
        async with self._session_factory() as db:
            device = await db.get(Device, device_id)
            if device is None:
                raise LookupError(f"device {device_id!r} no longer exists")
            oid_configs = list(
                (
                    await db.execute(
                        select(OIDRegistry).where(
                            OIDRegistry.poll_enabled.is_(True)
                        )
                    )
                ).scalars()
            )
        from app.snmp.poller import poll_device

        await poll_device(device, oid_configs)

    async def _run_initial_poll(
        self,
        job_id: int,
        device_id: str,
    ) -> None:
        try:
            await self._initial_poll(device_id)
        except Exception:
            logger.exception(
                "Initial discovery poll failed for device %s",
                device_id,
            )
            await self._set_initial_poll_status(
                job_id,
                device_id,
                status="failed",
                error_code="initial_poll_failed",
            )
        else:
            await self._set_initial_poll_status(
                job_id,
                device_id,
                status="completed",
            )

    async def _set_initial_poll_status(
        self,
        job_id: int,
        device_id: str,
        *,
        status: str,
        error_code: str | None = None,
    ) -> None:
        async with self._initial_poll_status_lock:
            async with self._session_factory() as db:
                job = await db.get(DiscoveryJob, job_id)
                if job is None:
                    return
                snapshot = self._snapshot_from_job(job)
                results = []
                for stored_item in job_host_results(job):
                    item = dict(stored_item)
                    if (
                        item.get("device_id") == device_id
                        and item.get("action") == "imported"
                    ):
                        item["initial_poll"] = status
                        if error_code is not None:
                            item["initial_poll_error"] = error_code
                        else:
                            item.pop("initial_poll_error", None)
                    results.append(item)
                self._set_job_results(job, snapshot, results)
                await self._audit(
                    db,
                    job,
                    action=(
                        "discovery.device.initial_poll_completed"
                        if status == "completed"
                        else "discovery.device.initial_poll_failed"
                    ),
                    target_type="device",
                    target_id=device_id,
                    result="success" if status == "completed" else "failure",
                    change_summary={
                        "job_id": job.id,
                        "error": error_code,
                    },
                )
                await db.commit()

    async def _mark_failed(self, job_id: int, error_code: str) -> None:
        async with self._session_factory() as db:
            job = await db.get(DiscoveryJob, job_id)
            if job is None or job.status == "completed":
                return
            job.status = "failed"
            job.last_error = error_code
            job.finished_at = utcnow()
            job.updated_at = job.finished_at
            await self._audit(
                db,
                job,
                action="discovery.job.failed",
                target_type="discovery_job",
                target_id=job.id,
                result="failure",
                change_summary={"error": error_code},
            )
            await db.commit()

    async def _audit(
        self,
        db: AsyncSession,
        job: DiscoveryJob,
        *,
        action: str,
        target_type: str,
        target_id: object,
        result: str = "success",
        change_summary: Mapping[str, Any] | None = None,
    ) -> None:
        await record_audit_log(
            db,
            action=action,
            actor_id=job.requested_by,
            target_type=target_type,
            target_id=target_id,
            result=result,
            change_summary={
                "job_id": job.id,
                **dict(change_summary or {}),
            },
        )

    @staticmethod
    def _snapshot_from_job(
        job: DiscoveryJob,
    ) -> DiscoveryConfigSnapshot:
        payload = job.results
        if not isinstance(payload, dict):
            raise DiscoveryProbeError("missing_config_snapshot")
        snapshot = payload.get(_JOB_SNAPSHOT_KEY)
        if not isinstance(snapshot, Mapping):
            raise DiscoveryProbeError("missing_config_snapshot")
        try:
            return DiscoveryConfigSnapshot.from_storage(snapshot)
        except (KeyError, TypeError, ValueError) as exc:
            raise DiscoveryProbeError(
                "invalid_config_snapshot"
            ) from exc

    @staticmethod
    def _set_job_results(
        job: DiscoveryJob,
        snapshot: DiscoveryConfigSnapshot,
        results: list[dict[str, Any]],
    ) -> None:
        job.results = {
            _JOB_SNAPSHOT_KEY: snapshot.to_storage(),
            _JOB_RESULTS_KEY: results,
        }

    @staticmethod
    def _coerce_probe_result(value: Any) -> DiscoveryProbeResult:
        if isinstance(value, DiscoveryProbeResult):
            return value
        if isinstance(value, str):
            return DiscoveryProbeResult(sys_object_id=value)
        if isinstance(value, Mapping):
            sys_object_id = value.get("sys_object_id")
            if sys_object_id is None:
                raise DiscoveryProbeError("invalid_sys_object_id")
            identity = value.get("identity", {})
            return DiscoveryProbeResult(
                sys_object_id=str(sys_object_id),
                identity=identity if isinstance(identity, Mapping) else {},
            )
        return DiscoveryProbeResult(sys_object_id=str(value))

    @staticmethod
    def _identity_details(
        identity: Mapping[str, Any],
        *,
        host: str,
        port: int,
    ) -> dict[str, Any]:
        public: dict[str, Any] = {}
        for key in _IDENTITY_FIELDS:
            value = _identity_value(identity.get(key))
            if value is not None:
                public[key] = value
        mac_addresses = sorted(
            {
                normalized
                for key, value in identity.items()
                if str(key).startswith("ether_address")
                and (normalized := normalize_mac_address(value)) is not None
            }
        )
        if mac_addresses:
            public["mac_addresses"] = mac_addresses
        serial_number = public.get("serial_number")
        if serial_number is not None:
            identity_key = f"serial:{serial_number.casefold()}"
        elif mac_addresses:
            identity_key = f"mac:{mac_addresses[0]}"
        else:
            identity_key = f"address:{host}:{port}"
        return {
            "serial_number": serial_number,
            "mac_addresses": mac_addresses,
            "identity_key": identity_key,
            "public": public,
        }

    @classmethod
    def _match_device(
        cls,
        devices: list[Device],
        *,
        host: str,
        port: int,
        profile_id: str,
        serial_number: str | None,
        mac_addresses: list[str],
    ) -> Device | None:
        candidates = [
            device
            for device in devices
            if device.profile_id in {None, profile_id}
        ]
        serial_key = (
            serial_number.strip().casefold()
            if serial_number is not None
            else None
        )
        mac_keys = set(mac_addresses)
        identity_matches = []
        if serial_key is not None or mac_keys:
            for device in candidates:
                existing_serial = (
                    device.serial_number.strip().casefold()
                    if device.serial_number
                    else None
                )
                existing_macs = {
                    normalized
                    for value in (device.mac_addresses or [])
                    if (normalized := normalize_mac_address(value))
                    is not None
                }
                if (
                    serial_key is not None
                    and existing_serial == serial_key
                ) or (mac_keys and existing_macs.intersection(mac_keys)):
                    identity_matches.append(device)
        if identity_matches:
            return cls._select_single_match(
                identity_matches,
                host=host,
                port=port,
                reason="duplicate_identity",
            )

        address_matches = [
            device for device in candidates if device.host == host
        ]
        if serial_key is not None or mac_keys:
            address_matches = [
                device
                for device in address_matches
                if not device.serial_number
                and not (device.mac_addresses or [])
            ]
        if not address_matches:
            return None
        return cls._select_single_match(
            address_matches,
            host=host,
            port=port,
            reason="duplicate_address",
        )

    @staticmethod
    def _select_single_match(
        devices: list[Device],
        *,
        host: str,
        port: int,
        reason: str,
    ) -> Device:
        exact = [
            device
            for device in devices
            if device.host == host and device.port == port
        ]
        if len(exact) == 1:
            return exact[0]
        if len(devices) == 1:
            return devices[0]
        raise DiscoveryIdentityConflict(reason)

    @staticmethod
    def _outcome_error_code(exc: Exception) -> str:
        if isinstance(exc, DiscoveryIdentityConflict):
            return str(exc) or "identity_conflict"
        return "device_upsert_failed"

    @staticmethod
    def _device_id(
        profile_id: str,
        *,
        host: str,
        port: int,
        serial_number: str | None,
        mac_addresses: list[str],
    ) -> str:
        identity = (
            f"serial:{serial_number.casefold()}"
            if serial_number is not None
            else (
                f"mac:{mac_addresses[0]}"
                if mac_addresses
                else f"address:{host}:{port}"
            )
        )
        digest = hashlib.sha256(
            f"{profile_id}|{identity}".encode("utf-8")
        ).hexdigest()[:16]
        return f"auto-{profile_id}-{digest}"

    @staticmethod
    def _validate_config_values(values: Mapping[str, Any]) -> None:
        fields: dict[str, str] = {}
        community = str(values.get("community") or "")
        if not community or len(community) > 64:
            fields["community"] = "Must contain between 1 and 64 characters"

        try:
            port = int(values["snmp_port"])
            if not 1 <= port <= 65535:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            fields["snmp_port"] = "Must be between 1 and 65535"

        try:
            timeout = float(values["timeout_seconds"])
            if not 0.05 <= timeout <= 30:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            fields["timeout_seconds"] = "Must be between 0.05 and 30 seconds"

        try:
            retries = int(values["retries"])
            if not 0 <= retries <= 5:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            fields["retries"] = "Must be between 0 and 5"

        try:
            concurrency = int(values["concurrency"])
            if not 1 <= concurrency <= MAX_USABLE_HOSTS:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            fields["concurrency"] = (
                f"Must be between 1 and {MAX_USABLE_HOSTS}"
            )

        if fields:
            raise DiscoveryValidationError(
                "Invalid discovery configuration",
                fields,
            )


discovery_service = DiscoveryService()


__all__ = [
    "ACTIVE_JOB_STATUSES",
    "DiscoveryAlreadyRunning",
    "DiscoveryJobNotFound",
    "DiscoveryProbeError",
    "DiscoveryService",
    "DiscoveryValidationError",
    "MAX_USABLE_HOSTS",
    "SYS_OBJECT_ID",
    "discovery_service",
    "identify_profile",
    "normalize_sys_object_id",
    "probe_sys_object_id",
    "validate_ipv4_cidr",
]
