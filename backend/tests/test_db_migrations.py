from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import create_engine, inspect, text

from app import db_migrations
from app.database import Base
import app.models  # noqa: F401


EXPECTED_TABLES = (
    set(db_migrations.LEGACY_TABLE_COLUMNS)
    | set(db_migrations.NEW_TABLE_COLUMNS)
    | {"alembic_version"}
)

EXPECTED_INDEXES = {
    "users": {"ix_users_username"},
    "devices": {"ix_devices_profile_id", "ix_devices_serial_number"},
    "endpoints": {"ix_endpoints_device_id"},
    "status_metrics": {
        "ix_status_metrics_time",
        "ix_status_metrics_device_oid_time",
        "ix_status_metrics_endpoint_time",
    },
    "alerts": {
        "ix_alerts_device_id",
        "ix_alerts_endpoint_id",
        "ix_alerts_created_at",
        "ix_alerts_entity_key",
    },
    "device_entities": {
        "ix_device_entities_device_id",
        "ix_device_entities_profile_id",
        "ix_device_entities_table_id",
        "ix_device_entities_entity_type",
    },
    "discovery_jobs": {
        "ix_discovery_jobs_status",
        "ix_discovery_jobs_created_at",
    },
    "audit_logs": {
        "ix_audit_logs_actor_id",
        "ix_audit_logs_action",
        "ix_audit_logs_target_type",
        "ix_audit_logs_target_id",
        "ix_audit_logs_result",
        "ix_audit_logs_created_at",
    },
    "trap_events": {
        "ix_trap_events_device_id",
        "ix_trap_events_created_at",
    },
    "simulator_runs": {"ix_simulator_runs_lease_expires_at"},
}


def _database_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def _upgrade(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    monkeypatch.setattr(
        db_migrations,
        "get_settings",
        lambda: SimpleNamespace(database_url_sync=database_url),
    )
    db_migrations.upgrade_database()


def _revision(database_url: str) -> str | None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            if "alembic_version" not in tables:
                return None
            return connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def _drop_version_table(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    finally:
        engine.dispose()


def test_empty_database_upgrades_to_head_and_is_repeatable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database_url(tmp_path, "empty.db")

    assert (
        db_migrations.inspect_database_state(database_url)
        == db_migrations.DatabaseSchemaState.EMPTY
    )

    _upgrade(monkeypatch, database_url)
    assert _revision(database_url) == db_migrations.HEAD_REVISION

    engine = create_engine(database_url)
    try:
        db_inspector = inspect(engine)
        assert set(db_inspector.get_table_names()) == EXPECTED_TABLES
        for table_name, expected_indexes in EXPECTED_INDEXES.items():
            actual_indexes = {
                item["name"] for item in db_inspector.get_indexes(table_name)
            }
            assert expected_indexes <= actual_indexes
    finally:
        engine.dispose()

    _upgrade(monkeypatch, database_url)
    assert _revision(database_url) == db_migrations.HEAD_REVISION
    assert (
        db_migrations.inspect_database_state(database_url)
        == db_migrations.DatabaseSchemaState.VERSIONED
    )


def test_complete_unversioned_legacy_database_is_adopted_without_data_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database_url(tmp_path, "complete-legacy.db")
    command.upgrade(
        db_migrations._config(database_url),
        db_migrations.BASELINE_REVISION,
    )

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO devices (
                        id, name, host, port, community, is_active,
                        poll_interval, endpoint_count, created_at, updated_at
                    ) VALUES (
                        'legacy-1', 'Legacy Matrix', '192.0.2.10', 161,
                        'public', 1, 60, 0,
                        '2026-07-31 00:00:00', '2026-07-31 00:00:00'
                    )
                    """
                )
            )
    finally:
        engine.dispose()
    _drop_version_table(database_url)

    assert (
        db_migrations.inspect_database_state(database_url)
        == db_migrations.DatabaseSchemaState.COMPLETE_LEGACY
    )

    _upgrade(monkeypatch, database_url)

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT name FROM devices WHERE id = 'legacy-1'"
                )
            ).scalar_one() == "Legacy Matrix"
            assert "device_entities" in inspect(connection).get_table_names()
    finally:
        engine.dispose()
    assert _revision(database_url) == db_migrations.HEAD_REVISION


def test_compatible_partial_legacy_schema_is_repaired_additively(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database_url(tmp_path, "partial-legacy.db")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE devices (
                        id VARCHAR(64) PRIMARY KEY,
                        name VARCHAR(128) NOT NULL,
                        host VARCHAR(64) NOT NULL,
                        port INTEGER NOT NULL,
                        community VARCHAR(64) NOT NULL,
                        location VARCHAR(128),
                        description TEXT,
                        is_active BOOLEAN NOT NULL,
                        poll_interval INTEGER NOT NULL,
                        last_poll DATETIME,
                        last_status VARCHAR(16),
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO devices (
                        id, name, host, port, community, is_active,
                        poll_interval, created_at, updated_at
                    ) VALUES (
                        'v1-device', 'V1 Matrix', '192.0.2.20', 161,
                        'public', 1, 60,
                        '2026-07-31 00:00:00', '2026-07-31 00:00:00'
                    )
                    """
                )
            )
    finally:
        engine.dispose()

    assert (
        db_migrations.inspect_database_state(database_url)
        == db_migrations.DatabaseSchemaState.PARTIAL_LEGACY
    )

    _upgrade(monkeypatch, database_url)

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            device_columns = {
                item["name"]
                for item in inspect(connection).get_columns("devices")
            }
            assert db_migrations.LEGACY_TABLE_COLUMNS["devices"] <= (
                device_columns
            )
            assert db_migrations.HEAD_EXTRA_COLUMNS["devices"] <= (
                device_columns
            )
            row = connection.execute(
                text(
                    """
                    SELECT name, endpoint_count
                    FROM devices
                    WHERE id = 'v1-device'
                    """
                )
            ).one()
            assert row == ("V1 Matrix", 0)
            assert set(inspect(connection).get_table_names()) == EXPECTED_TABLES
    finally:
        engine.dispose()


def test_incompatible_partial_schema_fails_before_alembic_version_is_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database_url(tmp_path, "incompatible.db")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE devices (
                        id VARCHAR(64) PRIMARY KEY,
                        name VARCHAR(128) NOT NULL
                    )
                    """
                )
            )
    finally:
        engine.dispose()

    with pytest.raises(
        db_migrations.MigrationSchemaError,
        match="missing core columns",
    ):
        _upgrade(monkeypatch, database_url)

    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert tables == {"devices"}
        assert "alembic_version" not in tables
    finally:
        engine.dispose()


def test_incomplete_multi_profile_table_fails_before_migration_starts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database_url(tmp_path, "incomplete-new-table.db")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE device_entities (
                        id INTEGER PRIMARY KEY
                    )
                    """
                )
            )
    finally:
        engine.dispose()

    with pytest.raises(
        db_migrations.MigrationSchemaError,
        match="device_entities.*incomplete",
    ):
        _upgrade(monkeypatch, database_url)

    engine = create_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == {"device_entities"}
    finally:
        engine.dispose()


def test_unversioned_current_schema_can_be_adopted_repeatedly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database_url(tmp_path, "unversioned-current.db")
    command.upgrade(db_migrations._config(database_url), "head")
    _drop_version_table(database_url)

    assert (
        db_migrations.inspect_database_state(database_url)
        == db_migrations.DatabaseSchemaState.UNVERSIONED_CURRENT
    )

    _upgrade(monkeypatch, database_url)
    assert _revision(database_url) == db_migrations.HEAD_REVISION


def test_migrated_empty_database_matches_current_orm_metadata(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path, "metadata-compare.db")
    command.upgrade(db_migrations._config(database_url), "head")

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={"compare_type": True},
            )
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("upgrade_target", "downgrade_target"),
    [
        (db_migrations.BASELINE_REVISION, "base"),
        (db_migrations.HEAD_REVISION, db_migrations.BASELINE_REVISION),
    ],
)
def test_downgrade_is_explicitly_rejected_without_schema_changes(
    tmp_path: Path,
    upgrade_target: str,
    downgrade_target: str,
) -> None:
    database_url = _database_url(
        tmp_path,
        f"downgrade-{upgrade_target}.db",
    )
    config = db_migrations._config(database_url)
    command.upgrade(config, upgrade_target)

    engine = create_engine(database_url)
    try:
        tables_before = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="intentionally unsupported"):
        command.downgrade(config, downgrade_target)

    engine = create_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == tables_before
    finally:
        engine.dispose()
    assert _revision(database_url) == upgrade_target


def test_historical_revisions_do_not_import_live_application_metadata() -> None:
    versions_dir = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions"
    )
    for path in sorted(versions_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        app_imports = [
            node
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("app")
            )
            or (
                isinstance(node, ast.Import)
                and any(alias.name.startswith("app") for alias in node.names)
            )
        ]
        assert app_imports == [], f"{path.name} imports live app metadata"

    assert "command.stamp" not in (
        Path(db_migrations.__file__).read_text(encoding="utf-8")
    )
