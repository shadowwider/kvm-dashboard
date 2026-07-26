from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 数据库模式: "postgres" | "sqlite" (测试用)
    db_mode: str = "sqlite"

    # PostgreSQL (生产)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "kvm_monitor"
    postgres_user: str = "kvm_user"
    postgres_password: str = "change_me"

    # SQLite (测试)
    sqlite_path: str = "kvm_test.db"

    # 认证
    secret_key: str = "change_me_to_a_random_64_char_string"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"

    # SNMP
    snmp_trap_port: int = 162
    snmp_default_community: str = "public"
    # 完整指标轮询：GET/WALK、指标归档和阈值告警。不要为可达性检测降低此值。
    snmp_poll_interval: int = 45
    # 轻量可达性探测：每台设备只读取 sysObjectID，用于 1–2 秒设备失联检测。
    snmp_health_poll_enabled: bool = True
    snmp_health_poll_interval: float = Field(default=1.0, gt=0, le=60)
    snmp_health_timeout: float = Field(default=0.25, gt=0, le=10)
    snmp_health_retries: int = Field(default=1, ge=0, le=5)
    snmp_health_concurrency: int = Field(default=20, ge=1, le=200)
    snmp_health_failure_threshold: int = Field(default=1, ge=1, le=10)
    # 已知 CPU/CON 和物理端口的状态列；不依赖未验证的模块-端口索引映射。
    snmp_endpoint_status_poll_enabled: bool = True

    # 本地模拟器桥接：默认关闭，生产环境不得启用。
    simulator_bridge_enabled: bool = False
    simulator_bridge_token: str = "change_me_simulator_token"

    # 原始 SNMP 数据日志（Trap + 轮询，写入 logs/ 目录，可通过 SNMP_RAW_LOG_ENABLED=false 关闭）
    snmp_raw_log_enabled: bool = True

    # 服务
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    log_level: str = "INFO"

    # 初始管理员
    admin_username: str = "admin"
    admin_password: str = "admin123"

    @property
    def resolved_sqlite_path(self) -> str:
        if self.sqlite_path == ":memory:":
            return self.sqlite_path
        path = Path(self.sqlite_path)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path.resolve().as_posix()

    @property
    def database_url(self) -> str:
        if self.db_mode == "sqlite":
            return f"sqlite+aiosqlite:///{self.resolved_sqlite_path}"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Alembic 使用同步驱动"""
        if self.db_mode == "sqlite":
            return f"sqlite:///{self.resolved_sqlite_path}"
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.db_mode == "sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
