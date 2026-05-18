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
    snmp_poll_interval: int = 45  # 可通过 SNMP_POLL_INTERVAL 环境变量覆盖；Trap 负责实时告警

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
