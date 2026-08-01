from datetime import datetime, timedelta, timezone
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_admin
from app.config import get_settings
from app.database import AsyncSessionLocal, get_db
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.simulator_run import SimulatorRun
from app.models.user import User
from app.snmp.poller import poll_device
from app.models.oid_registry import OIDRegistry
from app.websocket.hub import ws_manager

router = APIRouter()
settings = get_settings()


class SimulatorManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)
    session_epoch: str = Field(min_length=1, max_length=64)
    revision: int = Field(ge=1)
    scenario: dict


class SimulatorSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)
    session_started_at: int = Field(ge=1)


class SimulatorSessionProof(BaseModel):
    """Proof required for a simulator-owned cleanup operation."""

    model_config = ConfigDict(extra="forbid")

    session_epoch: str = Field(min_length=1, max_length=64)


def _ensure_enabled(x_simulator_token: str | None) -> None:
    if not settings.simulator_bridge_enabled:
        raise HTTPException(404, "本地模拟器桥接未启用")
    if x_simulator_token != settings.simulator_bridge_token:
        raise HTTPException(403, "模拟器桥接令牌无效")


def _device_id(run_id: str, simulator_id: str) -> str:
    return f"sim_{run_id}_{simulator_id}"[:64]


def _lease_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=settings.simulator_bridge_lease_seconds)


async def _remove_run_resources(db: AsyncSession, run: SimulatorRun) -> None:
    """Delete a run and exactly the Dashboard records namespaced by that run."""
    prefix = f"sim_{run.id}_%"
    await db.execute(delete(Endpoint).where(Endpoint.device_id.like(prefix)))
    await db.execute(delete(Device).where(Device.id.like(prefix)))
    await db.delete(run)


@router.post("/runs/{run_id}/sessions")
async def start_session(
    run_id: str,
    body: SimulatorSessionRequest,
    x_simulator_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Make one bridge session authoritative; manifests from older sessions are rejected."""
    _ensure_enabled(x_simulator_token)
    run = await db.get(SimulatorRun, run_id)
    if not run:
        run = SimulatorRun(
            id=run_id,
            scenario_id="pending",
            session_id=body.session_id,
            session_epoch=secrets.token_urlsafe(24),
            session_started_at=body.session_started_at,
            lease_expires_at=_lease_expiry(),
            revision=0,
            manifest={},
        )
        db.add(run)
        try:
            await db.flush()
        except IntegrityError:
            # Another process won initial creation; reload it and arbitrate below.
            await db.rollback()
            run = await db.get(SimulatorRun, run_id)
            if not run:
                raise HTTPException(409, "无法建立模拟器会话")
        else:
            await db.commit()
            return {
                "run_id": run_id,
                "session_id": body.session_id,
                "session_epoch": run.session_epoch,
                "revision": 0,
            }

    # A delayed session-start from an older process may not supersede the active run.
    now = datetime.now(timezone.utc)
    epoch = secrets.token_urlsafe(24)
    claimed = await db.execute(
        update(SimulatorRun).where(
            SimulatorRun.id == run_id,
            or_(
                SimulatorRun.session_started_at <= body.session_started_at,
                SimulatorRun.lease_expires_at < now,
            ),
        ).values(
            session_id=body.session_id,
            session_epoch=epoch,
            session_started_at=body.session_started_at,
            revision=0,
            manifest={},
            lease_expires_at=_lease_expiry(),
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    if not claimed.rowcount:
        current = await db.get(SimulatorRun, run_id)
        return {
            "run_id": run_id,
            "session_id": current.session_id if current else None,
            "ignored_superseded_session": body.session_id,
            "revision": current.revision if current else None,
        }
    return {"run_id": run_id, "session_id": body.session_id, "session_epoch": epoch, "revision": 0}


@router.put("/runs/{run_id}/manifest")
async def reconcile_manifest(
    run_id: str,
    body: SimulatorManifest,
    x_simulator_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Idempotently reconcile only records owned by this simulator run."""
    _ensure_enabled(x_simulator_token)
    run = await db.get(SimulatorRun, run_id)
    if not run:
        # Callers must establish a session first; this avoids an in-flight stale
        # manifest creating or taking ownership of a run after a cleanup/restart.
        raise HTTPException(409, "模拟器会话尚未建立")
    if run.session_id != body.session_id or run.session_epoch != body.session_epoch:
        return {
            "run_id": run_id,
            "revision": run.revision,
            "ignored_superseded_session": body.session_id,
            "bindings": [],
        }

    # Atomically claim this revision before applying the manifest. A stale
    # request loses the conditional update and cannot overwrite newer state.
    claimed = await db.execute(
        update(SimulatorRun).where(
            SimulatorRun.id == run_id,
            SimulatorRun.session_id == body.session_id,
            SimulatorRun.session_epoch == body.session_epoch,
            SimulatorRun.revision <= body.revision,
        ).values(
            scenario_id=body.scenario_id,
            revision=body.revision,
            manifest=body.model_dump(),
            lease_expires_at=_lease_expiry(),
            updated_at=datetime.now(timezone.utc),
        )
    )
    if not claimed.rowcount:
        current = await db.get(SimulatorRun, run_id)
        return {
            "run_id": run_id,
            "revision": current.revision if current else None,
            "ignored_stale_revision": body.revision,
            "bindings": [],
        }

    desired_ids: set[str] = set()
    bindings: list[dict] = []
    for simulator_device in body.scenario.get("devices", []):
        simulator_id = simulator_device["id"]
        simulator_host = simulator_device.get("host", "127.0.0.1")
        simulator_port = simulator_device["snmp_port"]
        dashboard_id = _device_id(run_id, simulator_id)
        desired_ids.add(dashboard_id)
        device = await db.get(Device, dashboard_id)
        if not device:
            device = Device(
                id=dashboard_id,
                name=simulator_device["name"],
                host=simulator_host,
                port=simulator_port,
                community=settings.snmp_default_community,
                system_oid=simulator_device["system_oid"],
                model_name=f"SIMULATION / {simulator_device['profile']}",
                is_active=True,
                poll_interval=settings.snmp_poll_interval,
            )
            db.add(device)
        else:
            device.name = simulator_device["name"]
            device.host = simulator_host
            device.port = simulator_port
            device.system_oid = simulator_device["system_oid"]
            device.model_name = f"SIMULATION / {simulator_device['profile']}"
            device.is_active = True
            device.poll_interval = settings.snmp_poll_interval

        desired_endpoint_ids = set()
        for simulator_endpoint in simulator_device.get("endpoints", []):
            endpoint_id = f"{dashboard_id}_{simulator_endpoint['module_type']}_{simulator_endpoint['row']}"
            desired_endpoint_ids.add(endpoint_id)
            endpoint = await db.get(Endpoint, endpoint_id)
            status_key = "ep_device_status" if simulator_endpoint["module_type"] == "cpu" else "con_device_status"
            endpoint_identity_key = "ep_id" if simulator_endpoint["module_type"] == "cpu" else "con_id"
            last_status = {
                status_key: {0: "offline", 1: "online", 2: "ready"}[simulator_endpoint["status"]],
                endpoint_identity_key: simulator_endpoint["id"],
                "simulator_source": "simulation-declared",
            }
            if not endpoint:
                db.add(Endpoint(
                    id=endpoint_id,
                    device_id=dashboard_id,
                    name=simulator_endpoint.get("display_name") or simulator_endpoint["id"],
                    index=simulator_endpoint["port_index"],
                    module_type=simulator_endpoint["module_type"],
                    last_status=last_status,
                ))
            else:
                endpoint.name = simulator_endpoint.get("display_name") or simulator_endpoint["id"]
                endpoint.index = simulator_endpoint["port_index"]
                endpoint.last_status = last_status
                endpoint.updated_at = datetime.now(timezone.utc)
        await db.execute(delete(Endpoint).where(
            Endpoint.device_id == dashboard_id,
            ~Endpoint.id.in_(desired_endpoint_ids),
        ))
        bindings.append({
            "simulator_device_id": simulator_id,
            "dashboard_device_id": dashboard_id,
            "profile": simulator_device["profile"],
            "host": simulator_host,
            "port": simulator_port,
        })

    existing = await db.execute(select(Device).where(Device.id.like(f"sim_{run_id}_%")))
    for device in existing.scalars():
        if device.id not in desired_ids:
            await db.execute(delete(Endpoint).where(Endpoint.device_id == device.id))
            await db.delete(device)

    await db.commit()
    for binding in bindings:
        await ws_manager.broadcast({
            "type": "simulation_topology_update",
            "run_id": run_id,
            "device_id": binding["dashboard_device_id"],
            "revision": body.revision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return {"run_id": run_id, "revision": body.revision, "bindings": bindings}


@router.post("/runs/{run_id}/sessions/{session_id}/heartbeat")
async def heartbeat_owned_session(
    run_id: str,
    session_id: str,
    body: SimulatorSessionProof,
    x_simulator_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Renew a session lease without accepting a manifest from an old process."""
    _ensure_enabled(x_simulator_token)
    claimed = await db.execute(
        update(SimulatorRun).where(
            SimulatorRun.id == run_id,
            SimulatorRun.session_id == session_id,
            SimulatorRun.session_epoch == body.session_epoch,
        ).values(lease_expires_at=_lease_expiry(), updated_at=datetime.now(timezone.utc))
    )
    if not claimed.rowcount:
        raise HTTPException(409, "模拟器会话已失效或已被新进程接管")
    await db.commit()
    return {"run_id": run_id, "session_id": session_id, "lease_seconds": settings.simulator_bridge_lease_seconds}


async def cleanup_expired_runs(db: AsyncSession, now: datetime | None = None) -> int:
    """Remove stale simulator-owned resources after a missed lease heartbeat."""
    now = now or datetime.now(timezone.utc)
    expired = (await db.execute(
        select(SimulatorRun).where(
            SimulatorRun.lease_expires_at.is_not(None),
            SimulatorRun.lease_expires_at < now,
        )
    )).scalars().all()
    for run in expired:
        await _remove_run_resources(db, run)
    if expired:
        await db.commit()
    return len(expired)


async def reap_expired_simulator_runs() -> int:
    """Scheduler entry point for crash cleanup; no-op when bridge is disabled."""
    if not settings.simulator_bridge_enabled:
        return 0
    async with AsyncSessionLocal() as db:
        return await cleanup_expired_runs(db)


@router.post("/runs/{run_id}/sync")
async def sync_manifest(
    run_id: str,
    x_simulator_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _ensure_enabled(x_simulator_token)
    run = await db.get(SimulatorRun, run_id)
    if not run:
        raise HTTPException(404, "模拟器运行不存在")
    device_result = await db.execute(select(Device).where(Device.id.like(f"sim_{run_id}_%"), Device.is_active == True))
    devices = device_result.scalars().all()
    oid_result = await db.execute(select(OIDRegistry).where(OIDRegistry.poll_enabled == True))
    oid_configs = oid_result.scalars().all()
    manifest_devices = {item["id"]: item for item in run.manifest.get("scenario", {}).get("devices", [])}
    polled_devices = []
    for device in devices:
        simulator_id = device.id.removeprefix(f"sim_{run_id}_")
        # The current production poller is CCDC-shaped. Do not falsely claim it polls
        # vendor-backed profile fixtures until profile-aware collection is implemented.
        if manifest_devices.get(simulator_id, {}).get("profile") != "ccdc_legacy_unverified":
            continue
        await poll_device(device, oid_configs)
        polled_devices.append(device.id)
    for device_id in [*polled_devices, *[
        _device_id(run_id, item["id"])
        for item in manifest_devices.values()
        if _device_id(run_id, item["id"]) not in polled_devices
    ]]:
        await ws_manager.broadcast({
            "type": "simulation_topology_update",
            "run_id": run_id,
            "device_id": device_id,
            "revision": run.revision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return {"run_id": run_id, "synced_devices": polled_devices}


@router.get("/runs/{run_id}/status")
async def run_status(
    run_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not settings.simulator_bridge_enabled:
        raise HTTPException(404, "本地模拟器桥接未启用")
    run = await db.get(SimulatorRun, run_id)
    if not run:
        raise HTTPException(404, "模拟器运行不存在")
    devices = await db.execute(select(Device).where(Device.id.like(f"sim_{run_id}_%")))
    return {
        "run_id": run_id,
        "scenario_id": run.scenario_id,
        "revision": run.revision,
        "manifest": run.manifest,
        "devices": [
            {
                "id": device.id,
                "name": device.name,
                "host": device.host,
                "port": device.port,
                "system_oid": device.system_oid,
                "model_name": device.model_name,
                "last_status": device.last_status,
            }
            for device in devices.scalars()
        ],
    }


@router.delete("/runs/{run_id}/sessions/{session_id}", status_code=204)
async def cleanup_owned_session(
    run_id: str,
    session_id: str,
    body: SimulatorSessionProof,
    x_simulator_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Idempotently clean only the session that created this simulator run.

    This is intentionally bridge-token authenticated instead of admin-JWT
    authenticated.  A normal simulator shutdown has no interactive user, but
    it must not be able to delete a run that was superseded by another
    simulator process.
    """
    _ensure_enabled(x_simulator_token)
    run = await db.get(SimulatorRun, run_id)
    if not run:
        return None
    if run.session_id != session_id or run.session_epoch != body.session_epoch:
        raise HTTPException(409, "模拟器会话已被新的进程接管，拒绝清理")
    await _remove_run_resources(db, run)
    await db.commit()
    return None


@router.delete("/runs/{run_id}", status_code=204)
async def cleanup_run(
    run_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not settings.simulator_bridge_enabled:
        raise HTTPException(404, "本地模拟器桥接未启用")
    run = await db.get(SimulatorRun, run_id)
    if not run:
        raise HTTPException(404, "模拟器运行不存在")
    await _remove_run_resources(db, run)
    await db.commit()
