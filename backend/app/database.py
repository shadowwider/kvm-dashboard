from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# SQLite 需要特殊处理
engine_kwargs = {
    "echo": False,
}
if settings.is_sqlite:
    # SQLite 不支持 pool_size / max_overflow
    # WAL 模式允许并发读写，避免 API 查询被 poller 写锁阻塞
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": 30,  # 等锁最多 30 秒，而非立即报错
    }
else:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 40
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 1800  # 30 分钟回收连接

engine = create_async_engine(settings.database_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
