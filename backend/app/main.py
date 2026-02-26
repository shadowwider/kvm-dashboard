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
from app.snmp.poller import run_poll_cycle
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


async def _init_database():
    """创建所有表，配置 TimescaleDB 超表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
        seconds=60,
        id="snmp_poll",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("SNMP 轮询调度器已启动（间隔 60s，各设备可独立配置）")

    # 启动时立即执行一次轮询
    asyncio.create_task(run_poll_cycle())

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
        }

    return app


app = create_app()

