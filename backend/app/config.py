from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 数据库
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "kvm_monitor"
    postgres_user: str = "kvm_user"
    postgres_password: str = "change_me"

    # 认证
    secret_key: str = "change_me_to_a_random_64_char_string"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"

    # SNMP
    snmp_trap_port: int = 162
    snmp_default_community: str = "public"

    # 服务
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    log_level: str = "INFO"

    # 初始管理员
    admin_username: str = "admin"
    admin_password: str = "admin123"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Alembic 使用同步驱动"""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
