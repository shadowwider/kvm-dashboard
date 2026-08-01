import csv
import io
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import alerts as alerts_api
from app.auth.deps import get_current_user
from app.database import Base, get_db
from app.models.alert import Alert


NOW = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def api_client(tmp_path):
    database_path = tmp_path / "alerts-api.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[Alert.__table__],
            )
        )

    async with factory() as db:
        db.add(
            Alert(
                device_id="=device",
                endpoint_id="+endpoint",
                entity_key="-entity",
                oid_name="@oid",
                alert_type="+trap",
                severity="=critical",
                message="@message",
                raw_value="=1+1",
                trap_level=3,
                trap_oid="-1.3.6.1.4.1.32828",
                is_resolved=False,
                created_at=NOW,
            )
        )
        await db.commit()

    app = FastAPI()
    app.include_router(alerts_api.router, prefix="/api/v1/alerts")

    async def override_db():
        async with factory() as db:
            yield db

    async def allow_user():
        return SimpleNamespace(id=1, username="admin", role="admin")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = allow_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client

    await engine.dispose()


@pytest.mark.asyncio
async def test_alert_csv_escapes_every_snmp_controlled_text_column(api_client):
    response = await api_client.get("/api/v1/alerts/export")

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    row = rows[0]
    assert row["设备ID"] == "'=device"
    assert row["终端ID"] == "'+endpoint"
    assert row["实体键"] == "'-entity"
    assert row["指标"] == "'@oid"
    assert row["级别"] == "'=critical"
    assert row["告警类型"] == "'+trap"
    assert row["Trap OID"] == "'-1.3.6.1.4.1.32828"
    assert row["消息"] == "'@message"
    assert row["原始值"] == "'=1+1"
    assert row["Trap Level"] == "3"
