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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, AsyncSessionLocal, Base
from app.models import *  # noqa: 注册所有模型到 Base
from app.api.router import api_router
from app.snmp.poller import health_monitor_state, run_health_probe_cycle, run_poll_cycle
from app.snmp.trap_receiver import start_trap_receiver
from app.auth.jwt import hash_password
from app.models.user import User
from app.models.oid_registry import OIDRegistry
from app.snmp.oid_map import SEED_OID_REGISTRY
from sqlalchemy import select

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


async def _migrate_columns():
    """动态补全新增列，兼容旧数据库（无需重建）"""
    migrations = [
        # (table, column, ddl)
        # DDL 仅在列不存在时执行；SQLite 用 create_all 建表已含所有列，以下 DDL 只会跑到 PostgreSQL
        ("endpoints",      "module_type",   "ALTER TABLE endpoints ADD COLUMN module_type TEXT NOT NULL DEFAULT 'cpu'"),
        ("devices",        "model_name",    "ALTER TABLE devices ADD COLUMN model_name VARCHAR(128)"),
        ("devices",        "last_metrics",  "ALTER TABLE devices ADD COLUMN last_metrics TEXT"),
        ("devices",        "endpoint_count","ALTER TABLE devices ADD COLUMN endpoint_count INTEGER DEFAULT 0"),
        ("devices",        "last_health_check", "ALTER TABLE devices ADD COLUMN last_health_check TIMESTAMP WITH TIME ZONE"),
        ("users",          "updated_at",    "ALTER TABLE users ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"),
        ("status_metrics", "id",            "ALTER TABLE status_metrics ADD COLUMN id BIGSERIAL"),
        ("alerts",         "endpoint_id",   "ALTER TABLE alerts ADD COLUMN endpoint_id VARCHAR(128)"),
        ("simulator_runs", "session_id",    "ALTER TABLE simulator_runs ADD COLUMN session_id VARCHAR(64)"),
    ]
    async with engine.begin() as conn:
        if settings.is_sqlite:
            for table, column, ddl in migrations:
                rows = await conn.execute(text(f"PRAGMA table_info({table})"))
                cols = {row[1] for row in rows.fetchall()}
                if column not in cols:
                    await conn.execute(text(ddl))
                    logger.info(f"迁移: {table}.{column} 列已添加")
        else:
            # PostgreSQL: information_schema
            for table, column, ddl in migrations:
                result = await conn.execute(text(
                    "SELECT 1 FROM information_schema.columns "
                    f"WHERE table_name='{table}' AND column_name='{column}'"
                ))
                if not result.fetchone():
                    await conn.execute(text(ddl))
                    logger.info(f"迁移: {table}.{column} 列已添加")

            # 列类型变更（ALTER TYPE，幂等可重复执行）
            type_migrations = [
                "ALTER TABLE alerts ALTER COLUMN raw_value TYPE TEXT",
            ]
            for ddl in type_migrations:
                try:
                    await conn.execute(text(ddl))
                except Exception as e:
                    logger.debug(f"列类型迁移跳过 ({e})")


async def _init_database():
    """创建所有表，配置 TimescaleDB 超表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
                await conn.execute(text(
                    "SELECT add_retention_policy('status_metrics', "
                    "INTERVAL '90 days', if_not_exists => TRUE);"
                ))
                logger.info("TimescaleDB 超表配置完成")
            except Exception as e:
                logger.warning(f"TimescaleDB 配置跳过: {e}")
        else:
            logger.info("SQLite 测试模式，跳过 TimescaleDB 配置")

    await _migrate_columns()
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动 → 运行 → 关闭"""
    logger.info("KVM 监控系统后端启动...")

    await _init_database()
    await _seed_data()

    # 启动 SNMP Trap 接收器
    await start_trap_receiver()

    # 启动定时轮询调度器
    scheduler.add_job(
        run_poll_cycle,
        trigger="interval",
        seconds=settings.snmp_poll_interval,
        id="snmp_poll",
        max_instances=1,
        coalesce=True,
    )
    if settings.snmp_health_poll_enabled:
        scheduler.add_job(
            run_health_probe_cycle,
            trigger="interval",
            seconds=settings.snmp_health_poll_interval,
            id="snmp_health_probe",
            max_instances=1,
            coalesce=True,
        )
    scheduler.start()
    logger.info(f"SNMP 完整轮询调度器已启动（间隔 {settings.snmp_poll_interval}s）")
    if settings.snmp_health_poll_enabled:
        logger.info(
            "SNMP 可达性探测调度器已启动（间隔 %ss，超时 %ss，重试 %s，并发 %s）",
            settings.snmp_health_poll_interval,
            settings.snmp_health_timeout,
            settings.snmp_health_retries,
            settings.snmp_health_concurrency,
        )

    # 启动时立即执行一次完整轮询及一次轻量可达性探测。
    asyncio.create_task(run_poll_cycle())
    if settings.snmp_health_poll_enabled:
        asyncio.create_task(run_health_probe_cycle())

    yield

    logger.info("KVM 监控系统后端关闭...")
    scheduler.shutdown(wait=False)


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
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            pass
        return {
            "status": "ok" if db_ok else "degraded",
            "database": "connected" if db_ok else "disconnected",
            "scheduler": scheduler.running,
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

