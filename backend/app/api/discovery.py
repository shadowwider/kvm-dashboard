from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_admin
from app.database import get_db
from app.models.discovery import DiscoveryConfig, DiscoveryJob
from app.models.user import User
from app.services.audit import record_audit_log
from app.services.discovery import (
    DiscoveryAlreadyRunning,
    DiscoveryJobNotFound,
    DiscoveryValidationError,
    discovery_service,
    job_host_results,
)


router = APIRouter()


class DiscoveryConfigUpdate(BaseModel):
    cidr: str = Field(min_length=1, max_length=64)
    community: SecretStr | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    snmp_port: int = Field(default=161, ge=1, le=65535)
    timeout_seconds: float = Field(default=0.5, ge=0.05, le=30)
    retries: int = Field(default=0, ge=0, le=5)
    concurrency: int = Field(default=64, ge=1, le=256)
    enabled: bool = True
    scan_on_startup: bool = True


class DiscoveryConfigOut(BaseModel):
    cidr: str
    snmp_port: int
    timeout_seconds: float
    retries: int
    concurrency: int
    enabled: bool
    scan_on_startup: bool
    credential_configured: bool
    updated_at: datetime


class DiscoveryScanAccepted(BaseModel):
    job_id: int
    status: Literal["queued"]


class DiscoveryResultOut(BaseModel):
    host: str
    status: Literal["recognized", "unsupported", "no_response", "error"]
    sys_object_id: str | None = None
    profile_id: str | None = None
    device_id: str | None = None
    action: Literal["imported", "updated"] | None = None
    identity: dict[str, Any] = Field(default_factory=dict)
    identity_key: str | None = None
    initial_poll: Literal["queued", "completed", "failed"] | None = None
    initial_poll_error: str | None = None
    error: str | None = None


class DiscoveryJobOut(BaseModel):
    id: int
    status: Literal["queued", "running", "completed", "failed"]
    cidr: str
    snmp_port: int
    total_hosts: int
    scanned_hosts: int
    responded_hosts: int
    recognized_hosts: int
    imported_devices: int
    updated_devices: int
    unsupported_devices: int
    no_response_hosts: int
    error_count: int
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class DiscoveryJobDetailOut(DiscoveryJobOut):
    results: list[DiscoveryResultOut]


class DiscoveryJobPage(BaseModel):
    items: list[DiscoveryJobOut]
    total: int
    page: int
    page_size: int


def _validation_error(exc: DiscoveryValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "validation_error",
            "message": str(exc),
            "fields": exc.fields,
            "retryable": False,
        },
    )


def _config_dto(config: DiscoveryConfig) -> DiscoveryConfigOut:
    return DiscoveryConfigOut(
        cidr=config.cidr,
        snmp_port=config.snmp_port,
        timeout_seconds=config.timeout_seconds,
        retries=config.retries,
        concurrency=config.concurrency,
        enabled=config.enabled,
        scan_on_startup=config.scan_on_startup,
        credential_configured=bool(config.community),
        updated_at=config.updated_at,
    )


def _job_values(job: DiscoveryJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "cidr": job.cidr,
        "snmp_port": job.snmp_port,
        "total_hosts": job.total_hosts,
        "scanned_hosts": job.scanned_hosts,
        "responded_hosts": job.responded_hosts,
        "recognized_hosts": job.recognized_hosts,
        "imported_devices": job.imported_devices,
        "updated_devices": job.updated_devices,
        "unsupported_devices": job.unsupported_devices,
        "no_response_hosts": job.no_response_hosts,
        "error_count": job.error_count,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "last_error": job.last_error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _job_dto(job: DiscoveryJob) -> DiscoveryJobOut:
    return DiscoveryJobOut(**_job_values(job))


def _job_detail_dto(job: DiscoveryJob) -> DiscoveryJobDetailOut:
    return DiscoveryJobDetailOut(
        **_job_values(job),
        results=[
            DiscoveryResultOut.model_validate(item)
            for item in job_host_results(job)
        ],
    )


@router.get("/config", response_model=DiscoveryConfigOut)
async def get_discovery_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DiscoveryConfigOut:
    config = await discovery_service.get_config(db)
    return _config_dto(config)


@router.put("/config", response_model=DiscoveryConfigOut)
async def put_discovery_config(
    body: DiscoveryConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DiscoveryConfigOut:
    current_config = await discovery_service.get_config(db)
    values = body.model_dump(exclude={"community"})
    if body.community is not None:
        values["community"] = body.community.get_secret_value()
    public_after = {
        "cidr": body.cidr,
        "snmp_port": body.snmp_port,
        "timeout_seconds": body.timeout_seconds,
        "retries": body.retries,
        "concurrency": body.concurrency,
        "enabled": body.enabled,
        "scan_on_startup": body.scan_on_startup,
    }
    await record_audit_log(
        db,
        action="discovery.config_update",
        actor=current_user,
        target_type="discovery_config",
        target_id=current_config.id,
        request=request,
        change_summary={
            "before": {
                "cidr": current_config.cidr,
                "snmp_port": current_config.snmp_port,
                "timeout_seconds": current_config.timeout_seconds,
                "retries": current_config.retries,
                "concurrency": current_config.concurrency,
                "enabled": current_config.enabled,
                "scan_on_startup": current_config.scan_on_startup,
            },
            "after": public_after,
            "snmp_access_changed": body.community is not None,
        },
    )
    try:
        config = await discovery_service.update_config(db, values)
    except DiscoveryValidationError as exc:
        raise _validation_error(exc) from exc
    return _config_dto(config)


@router.post(
    "/scan",
    response_model=DiscoveryScanAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_discovery_scan(
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DiscoveryScanAccepted:
    try:
        job = await discovery_service.create_scan_job(
            db,
            requested_by=current_user.id,
        )
    except DiscoveryValidationError as exc:
        raise _validation_error(exc) from exc
    except DiscoveryAlreadyRunning as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "discovery_already_running",
                "message": "A discovery job is already running",
                "fields": {"job_id": str(exc.job.id)},
                "retryable": True,
            },
        ) from exc

    await record_audit_log(
        db,
        action="discovery.scan",
        actor=current_user,
        target_type="discovery_job",
        target_id=job.id,
        request=request,
        change_summary={
            "cidr": job.cidr,
            "snmp_port": job.snmp_port,
            "trigger": "manual",
        },
        commit=True,
    )
    background_tasks.add_task(discovery_service.run_job, job.id)
    return DiscoveryScanAccepted(job_id=job.id, status="queued")


@router.get("/jobs", response_model=DiscoveryJobPage)
async def list_discovery_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DiscoveryJobPage:
    jobs, total = await discovery_service.list_jobs(
        db,
        page=page,
        page_size=page_size,
    )
    return DiscoveryJobPage(
        items=[_job_dto(job) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/jobs/{job_id}", response_model=DiscoveryJobDetailOut)
async def get_discovery_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DiscoveryJobDetailOut:
    try:
        job = await discovery_service.get_job(db, job_id)
    except DiscoveryJobNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": "Discovery job was not found",
                "fields": {"job_id": str(job_id)},
                "retryable": False,
            },
        ) from exc
    return _job_detail_dto(job)


__all__ = ["router"]
