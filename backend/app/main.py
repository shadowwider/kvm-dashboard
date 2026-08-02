"""
FastAPI 应用入口。
负责：
  1. 应用生命周期管理（数据库初始化、TimescaleDB 超表、种子数据、调度器）
  2. 路由注册
  3. 中间件（CORS）
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text

from app.config import get_settings
from app.database import engine, AsyncSessionLocal
from app.db_migrations import upgrade_database
from app.models import *  # noqa: 注册所有模型到 Base
from app.api.router import api_router
from app.api.simulator import reap_expired_simulator_runs
from app.services.discovery import DiscoveryAlreadyRunning, discovery_service
from app.services.data_retention import database_capacity_status, run_retention_cleanup
from app.snmp.poller import (
    flush_health_heartbeats,
    health_monitor_state,
    run_endpoint_status_probe_cycle,
    run_health_probe_cycle,
    run_poll_cycle,
)
from app.snmp.trap_receiver import start_trap_receiver, trap_receiver_status
from app.auth.jwt import hash_password
from app.models.user import User
from app.models.oid_registry import OIDRegistry
from app.snmp.oid_map import SEED_OID_REGISTRY

settings = get_settings()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format=LOG_FORMAT,
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
FULL_POLL_CHECK_INTERVAL_SECONDS = 1


def _register_scheduler_jobs(target_scheduler, first_run_at: datetime) -> None:
    """Register every immediate job under APScheduler max-instance control."""
    target_scheduler.add_job(
        run_poll_cycle,
        trigger="interval",
        seconds=FULL_POLL_CHECK_INTERVAL_SECONDS,
        id="snmp_poll",
        max_instances=1,
        coalesce=True,
        next_run_time=first_run_at,
    )
    if settings.snmp_health_poll_enabled:
        target_scheduler.add_job(
            run_health_probe_cycle,
            trigger="interval",
            seconds=settings.snmp_health_poll_interval,
            id="snmp_health_probe",
            max_instances=1,
            coalesce=True,
            next_run_time=first_run_at,
        )
        target_scheduler.add_job(
            flush_health_heartbeats,
            trigger="interval",
            seconds=settings.snmp_health_heartbeat_flush_interval,
            id="snmp_health_heartbeat_flush",
            max_instances=1,
            coalesce=True,
            next_run_time=first_run_at,
        )
    if settings.simulator_bridge_enabled:
        target_scheduler.add_job(
            reap_expired_simulator_runs,
            trigger="interval",
            seconds=max(5, settings.simulator_bridge_lease_seconds // 2),
            id="simulator_bridge_lease_cleanup",
            max_instances=1,
            coalesce=True,
            next_run_time=first_run_at,
        )
    if settings.snmp_endpoint_status_poll_enabled:
        target_scheduler.add_job(
            run_endpoint_status_probe_cycle,
            trigger="interval",
            seconds=settings.snmp_endpoint_status_poll_interval,
            id="snmp_endpoint_status_probe",
            max_instances=1,
            coalesce=True,
            next_run_time=first_run_at,
        )
    if settings.data_retention_cleanup_enabled:
        target_scheduler.add_job(
            run_retention_cleanup,
            trigger="interval",
            hours=24,
            id="data_retention_cleanup",
            max_instances=1,
            coalesce=True,
            # Do not delete data as an incidental side effect of an upgrade.
            next_run_time=first_run_at + timedelta(days=1),
        )


def _restore_application_logging() -> None:
    """Alembic fileConfig 后恢复应用及 Uvicorn 已注册 logger。"""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
    for registered in logging.root.manager.loggerDict.values():
        if isinstance(registered, logging.Logger):
            registered.disabled = False


async def _init_database():
    """先执行 Alembic，再配置数据库运行期能力。"""
    logger.info("开始执行数据库 Alembic 迁移...")
    await asyncio.to_thread(upgrade_database)
    _restore_application_logging()
    logger.info("数据库 Alembic 迁移完成")

    async with engine.begin() as conn:
        # SQLite WAL 模式：允许读写并发，解决 API 被 poller 写锁阻塞的问题
        if settings.is_sqlite:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))

        # TimescaleDB 超表配置（仅 PostgreSQL 模式）
        if not settings.is_sqlite:
            try:
                await conn.execute(text(
                    "SELECT create_hypertable('status_metrics', 'time', "
                    "if_not_exists => TRUE, migrate_data => TRUE);"
                ))
                await conn.execute(text(
                    "SELECT add_compression_policy('status_metrics', "
                    "INTERVAL '7 days', if_not_exists => TRUE);"
                ))
                # init.sql establishes the safe 90-day default for a brand-new
                # cluster. Reconcile it here so a configured retention period
                # takes effect on later application restarts as well.
                await conn.execute(text(
                    "SELECT remove_retention_policy('status_metrics', "
                    "if_exists => TRUE);"
                ))
                await conn.execute(text(
                    "SELECT add_retention_policy('status_metrics', "
                    f"INTERVAL '{settings.metrics_retention_days} days', "
                    "if_not_exists => TRUE);"
                ))
                logger.info("TimescaleDB 超表配置完成")
            except Exception as e:
                logger.warning(f"TimescaleDB 配置跳过: {e}")
        else:
            logger.info("SQLite 测试模式，跳过 TimescaleDB 配置")

    logger.info(f"数据库初始化完成 (模式: {settings.db_mode})")


async def _seed_data():
    """写入初始数据（管理员账号 + OID 注册表）"""
    async with AsyncSessionLocal() as db:
        # 创建初始管理员
        result = await db.execute(select(User).where(User.username == settings.admin_username))
        if not result.scalar_one_or_none():
            db.add(User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            ))
            logger.info(f"创建初始管理员账号: {settings.admin_username}")

        # 写入 OID 注册表种子数据
        for seed in SEED_OID_REGISTRY:
            name = seed["name"]
            result = await db.execute(select(OIDRegistry).where(OIDRegistry.name == name))
            if result.scalar_one_or_none():
                continue  # 已存在，跳过

            # 构建 OID（表类型没有独立 OID 字段）
            oid = seed.get("oid", f"table.{seed.get('table_base_oid','')}.{seed.get('table_column','')}")
            db.add(OIDRegistry(
                oid=oid,
                name=name,
                display_name=seed.get("display_name", name),
                category=seed.get("category", "device"),
                data_type=seed.get("data_type", "string"),
                unit=seed.get("unit"),
                enum_map=seed.get("enum_map"),
                is_table=seed.get("is_table", False),
                table_base_oid=seed.get("table_base_oid"),
                table_column=seed.get("table_column"),
                alert_enabled=seed.get("alert_enabled", False),
                alert_gt=seed.get("alert_gt"),
                alert_lt=seed.get("alert_lt"),
                alert_eq_str=seed.get("alert_eq_str"),
                alert_ne_str=seed.get("alert_ne_str"),
                alert_severity=seed.get("alert_severity", "warning"),
                poll_enabled=seed.get("poll_enabled", True),
                archive_enabled=seed.get("archive_enabled", True),
                display_enabled=seed.get("display_enabled", True),
                display_order=seed.get("display_order", 0),
            ))

        await db.commit()
        logger.info("种子数据写入完成")


async def _run_startup_discovery() -> None:
    """按持久化配置创建并执行一次启动发现任务。"""
    try:
        async with AsyncSessionLocal() as db:
            config = await discovery_service.get_config(db)
            if not config.enabled or not config.scan_on_startup:
                logger.info("启动自动发现未启用，跳过局域网扫描")
                return

            try:
                job = await discovery_service.create_scan_job(
                    db,
                    requested_by=None,
                )
            except DiscoveryAlreadyRunning as exc:
                logger.info(
                    "已有自动发现任务正在执行，跳过启动扫描 (job_id=%s, status=%s)",
                    exc.job.id,
                    exc.job.status,
                )
                return

        logger.info("已安排启动自动发现扫描 (job_id=%s, cidr=%s)", job.id, job.cidr)
        await discovery_service.run_job(job.id)
        logger.info("启动自动发现扫描结束 (job_id=%s)", job.id)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("启动自动发现扫描失败")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动 → 运行 → 关闭"""
    logger.info("KVM 监控系统后端启动...")

    await _init_database()
    await _seed_data()

    # 启动 SNMP Trap 接收器
    await start_trap_receiver()

    # 让立即执行也由 APScheduler 跟踪，避免手工 create_task 与首个 interval 重叠。
    _register_scheduler_jobs(scheduler, datetime.now(timezone.utc))
    scheduler.start()
    logger.info(
        "SNMP 完整轮询调度器已启动（每秒检查、按设备 poll_interval 间隔执行）"
    )
    if settings.snmp_health_poll_enabled:
        logger.info(
            "SNMP 可达性探测调度器已启动（间隔 %ss，超时 %ss，重试 %s，并发 %s）",
            settings.snmp_health_poll_interval,
            settings.snmp_health_timeout,
            settings.snmp_health_retries,
            settings.snmp_health_concurrency,
        )

    startup_discovery_task = asyncio.create_task(_run_startup_discovery())

    try:
        yield
    finally:
        logger.info("KVM 监控系统后端关闭...")
        scheduler.shutdown(wait=False)

        if not startup_discovery_task.done():
            startup_discovery_task.cancel()
        await asyncio.gather(startup_discovery_task, return_exceptions=True)
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="KVM 监控系统 API",
        description="上海机场 G&D KVM 设备实时监控平台",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境改为实际前端地址
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    # 健康检查 (无需认证, Docker/LB 用)
    @app.get("/health", tags=["运维"])
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/health", tags=["运维"])
    async def health_detailed():
        """带数据库连通性校验的健康检查"""
        db_ok = False
        database_capacity = None
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
                database_capacity = await database_capacity_status(db)
                db_ok = True
        except Exception:
            pass
        return {
            "status": "ok" if db_ok else "degraded",
            "database": "connected" if db_ok else "disconnected",
            "database_capacity": database_capacity,
            "scheduler": scheduler.running,
            "trap_receiver": trap_receiver_status(),
            "health_probe": {
                "enabled": settings.snmp_health_poll_enabled,
                "interval_seconds": settings.snmp_health_poll_interval,
                "timeout_seconds": settings.snmp_health_timeout,
                "retries": settings.snmp_health_retries,
                "concurrency": settings.snmp_health_concurrency,
                "failure_threshold": settings.snmp_health_failure_threshold,
                **health_monitor_state,
            },
        }

    return app


app = create_app()

