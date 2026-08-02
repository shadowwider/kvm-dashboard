from __future__ import annotations

from enum import Enum
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text

from app.config import get_settings


BASELINE_REVISION = "20260801_0001"
HEAD_REVISION = "20260802_0003"
BACKEND_DIR = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)

LEGACY_TABLE_COLUMNS = {
    "users": {
        "id",
        "username",
        "password_hash",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    },
    "devices": {
        "id",
        "name",
        "host",
        "port",
        "community",
        "location",
        "description",
        "system_oid",
        "model_name",
        "is_active",
        "poll_interval",
        "last_poll",
        "last_health_check",
        "last_status",
        "last_metrics",
        "endpoint_count",
        "created_at",
        "updated_at",
    },
    "endpoints": {
        "id",
        "device_id",
        "name",
        "index",
        "module_type",
        "last_status",
        "updated_at",
        "created_at",
    },
    "oid_registry": {
        "id",
        "oid",
        "name",
        "display_name",
        "description",
        "category",
        "data_type",
        "unit",
        "enum_map",
        "is_table",
        "table_base_oid",
        "table_column",
        "alert_enabled",
        "alert_gt",
        "alert_lt",
        "alert_eq_str",
        "alert_ne_str",
        "alert_severity",
        "poll_enabled",
        "archive_enabled",
        "display_enabled",
        "display_order",
        "created_at",
        "updated_at",
    },
    "status_metrics": {
        "id",
        "time",
        "device_id",
        "endpoint_id",
        "oid_name",
        "value_str",
        "value_num",
    },
    "alerts": {
        "id",
        "device_id",
        "endpoint_id",
        "oid_name",
        "alert_type",
        "severity",
        "message",
        "raw_value",
        "is_resolved",
        "resolved_at",
        "created_at",
    },
    "device_aliases": {
        "target_id",
        "target_type",
        "alias",
        "note",
        "updated_at",
    },
    "simulator_runs": {
        "id",
        "scenario_id",
        "session_id",
        "session_epoch",
        "session_started_at",
        "lease_expires_at",
        "revision",
        "manifest",
        "created_at",
        "updated_at",
    },
}

LEGACY_CORE_COLUMNS = {
    "users": LEGACY_TABLE_COLUMNS["users"] - {"updated_at"},
    "devices": LEGACY_TABLE_COLUMNS["devices"]
    - {
        "system_oid",
        "model_name",
        "last_health_check",
        "last_metrics",
        "endpoint_count",
    },
    "endpoints": LEGACY_TABLE_COLUMNS["endpoints"] - {"module_type"},
    "oid_registry": LEGACY_TABLE_COLUMNS["oid_registry"] - {"archive_enabled"},
    "status_metrics": LEGACY_TABLE_COLUMNS["status_metrics"],
    "alerts": LEGACY_TABLE_COLUMNS["alerts"],
    "device_aliases": LEGACY_TABLE_COLUMNS["device_aliases"],
    "simulator_runs": LEGACY_TABLE_COLUMNS["simulator_runs"]
    - {
        "session_id",
        "session_epoch",
        "session_started_at",
        "lease_expires_at",
    },
}

LEGACY_PRIMARY_KEYS = {
    "users": ("id",),
    "devices": ("id",),
    "endpoints": ("id",),
    "oid_registry": ("id",),
    "status_metrics": ("id",),
    "alerts": ("id",),
    "device_aliases": ("target_id",),
    "simulator_runs": ("id",),
}

LEGACY_UNIQUE_COLUMN_SETS = {
    "users": {("username",)},
    "oid_registry": {("oid",), ("name",)},
}

# The original PostgreSQL bootstrap script predates Alembic.  It created the
# metric table as a TimescaleDB hypertable candidate (therefore without an
# ``id`` primary key) and did not add the later ``oid_registry.oid`` unique
# index.  Both differences can be reconciled additively by the baseline
# migration; they must not make a supported bootstrap database unstartable.
_POSTGRES_LEGACY_PRIMARY_KEY_EXCEPTIONS = {
    "status_metrics": {()},
}
_LEGACY_UNIQUE_KEY_ADOPTIONS = {
    "oid_registry": {("oid",)},
}

NEW_TABLE_COLUMNS = {
    "device_entities": {
        "id",
        "device_id",
        "profile_id",
        "table_id",
        "entity_type",
        "entity_key",
        "label",
        "index_key",
        "raw_values",
        "normalized_values",
        "field_states",
        "status",
        "is_present",
        "is_stale",
        "first_seen_at",
        "last_seen_at",
        "updated_at",
    },
    "discovery_config": {
        "id",
        "cidr",
        "community",
        "snmp_port",
        "timeout_seconds",
        "retries",
        "concurrency",
        "enabled",
        "scan_on_startup",
        "updated_at",
    },
    "discovery_jobs": {
        "id",
        "status",
        "cidr",
        "snmp_port",
        "total_hosts",
        "scanned_hosts",
        "responded_hosts",
        "recognized_hosts",
        "imported_devices",
        "updated_devices",
        "unsupported_devices",
        "no_response_hosts",
        "error_count",
        "results",
        "last_error",
        "requested_by",
        "created_at",
        "started_at",
        "finished_at",
        "updated_at",
    },
    "audit_logs": {
        "id",
        "actor_id",
        "actor_username",
        "actor_role",
        "action",
        "target_type",
        "target_id",
        "result",
        "request_id",
        "ip_address",
        "user_agent",
        "change_summary",
        "created_at",
    },
    "trap_events": {
        "id",
        "alert_id",
        "device_id",
        "source_ip",
        "notification_oid",
        "raw_level",
        "message",
        "varbinds",
        "created_at",
    },
}

NEW_PRIMARY_KEYS = {
    table_name: ("id",) for table_name in NEW_TABLE_COLUMNS
}

NEW_UNIQUE_COLUMN_SETS = {
    "device_entities": {
        ("device_id", "profile_id", "table_id", "entity_key")
    },
    "trap_events": {("alert_id",)},
}

HEAD_EXTRA_COLUMNS = {
    "devices": {
        "profile_id",
        "profile_version",
        "profile_evidence_version",
        "serial_number",
        "mac_addresses",
        "discovery_source",
        "last_discovered_at",
        "last_health_latency_ms",
        "last_full_poll_status",
        "profile_scalar_states",
    },
    "alerts": {"entity_key", "trap_level", "trap_oid"},
}


class DatabaseSchemaState(str, Enum):
    EMPTY = "empty"
    COMPLETE_LEGACY = "complete_legacy"
    PARTIAL_LEGACY = "partial_legacy"
    UNVERSIONED_CURRENT = "unversioned_current"
    VERSIONED = "versioned"


class MigrationSchemaError(RuntimeError):
    """The existing application schema cannot be adopted additively."""


def _config(database_url: str | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        database_url or get_settings().database_url_sync,
    )
    return config


def _unique_column_sets(db_inspector, table_name: str) -> set[tuple[str, ...]]:
    unique_sets = {
        tuple(item["column_names"])
        for item in db_inspector.get_unique_constraints(table_name)
        if item.get("column_names")
    }
    unique_sets.update(
        tuple(item["column_names"])
        for item in db_inspector.get_indexes(table_name)
        if item.get("unique") and item.get("column_names")
    )
    return unique_sets


def _validate_legacy_tables(db_inspector, table_names: set[str]) -> None:
    dialect_name = db_inspector.bind.dialect.name
    for table_name in sorted(table_names & LEGACY_TABLE_COLUMNS.keys()):
        actual_columns = {
            column["name"] for column in db_inspector.get_columns(table_name)
        }
        missing_core = LEGACY_CORE_COLUMNS[table_name] - actual_columns
        if missing_core:
            missing = ", ".join(sorted(missing_core))
            raise MigrationSchemaError(
                f"Legacy table '{table_name}' is incompatible: missing core "
                f"columns {missing}. No migration or stamp was applied."
            )

        actual_pk = tuple(
            db_inspector.get_pk_constraint(table_name).get(
                "constrained_columns"
            )
            or ()
        )
        expected_pk = LEGACY_PRIMARY_KEYS[table_name]
        accepted_primary_keys = {expected_pk}
        if dialect_name == "postgresql":
            accepted_primary_keys.update(
                _POSTGRES_LEGACY_PRIMARY_KEY_EXCEPTIONS.get(
                    table_name, set()
                )
            )
        if actual_pk not in accepted_primary_keys:
            raise MigrationSchemaError(
                f"Legacy table '{table_name}' is incompatible: primary key "
                f"is {actual_pk or '<none>'}, expected {expected_pk}. "
                "No migration or stamp was applied."
            )

        expected_unique = LEGACY_UNIQUE_COLUMN_SETS.get(table_name, set())
        missing_unique = expected_unique - _unique_column_sets(
            db_inspector, table_name
        )
        if dialect_name == "postgresql":
            missing_unique -= _LEGACY_UNIQUE_KEY_ADOPTIONS.get(
                table_name, set()
            )
        if missing_unique:
            formatted = ", ".join(
                str(columns) for columns in sorted(missing_unique)
            )
            raise MigrationSchemaError(
                f"Legacy table '{table_name}' is incompatible: missing "
                f"unique key(s) {formatted}. No migration or stamp was applied."
            )


def _validate_new_tables(db_inspector, table_names: set[str]) -> None:
    for table_name in sorted(table_names & NEW_TABLE_COLUMNS.keys()):
        actual_columns = {
            column["name"] for column in db_inspector.get_columns(table_name)
        }
        missing = NEW_TABLE_COLUMNS[table_name] - actual_columns
        if missing:
            formatted = ", ".join(sorted(missing))
            raise MigrationSchemaError(
                f"Existing multi-Profile table '{table_name}' is incomplete: "
                f"missing columns {formatted}. No migration was applied."
            )

        actual_pk = tuple(
            db_inspector.get_pk_constraint(table_name).get(
                "constrained_columns"
            )
            or ()
        )
        expected_pk = NEW_PRIMARY_KEYS[table_name]
        if actual_pk != expected_pk:
            raise MigrationSchemaError(
                f"Existing multi-Profile table '{table_name}' is "
                f"incompatible: primary key is {actual_pk or '<none>'}, "
                f"expected {expected_pk}. No migration was applied."
            )

        expected_unique = NEW_UNIQUE_COLUMN_SETS.get(table_name, set())
        missing_unique = expected_unique - _unique_column_sets(
            db_inspector, table_name
        )
        if missing_unique:
            formatted = ", ".join(
                str(columns) for columns in sorted(missing_unique)
            )
            raise MigrationSchemaError(
                f"Existing multi-Profile table '{table_name}' is "
                f"incompatible: missing unique key(s) {formatted}. "
                "No migration was applied."
            )


def _is_complete(
    db_inspector,
    table_names: set[str],
    expected: dict[str, set[str]],
) -> bool:
    if not expected.keys() <= table_names:
        return False
    return all(
        columns
        <= {
            column["name"]
            for column in db_inspector.get_columns(table_name)
        }
        for table_name, columns in expected.items()
    )


def _read_revision(connection, table_names: set[str]) -> str | None:
    if "alembic_version" not in table_names:
        return None
    rows = list(
        connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalars()
    )
    if len(rows) > 1:
        raise MigrationSchemaError(
            "alembic_version contains multiple revisions; this repository "
            "expects one linear migration head."
        )
    return rows[0] if rows else None


def _inspect_database_state(engine: Engine) -> DatabaseSchemaState:
    with engine.connect() as connection:
        db_inspector = inspect(connection)
        table_names = set(db_inspector.get_table_names())
        current_revision = _read_revision(connection, table_names)
        if current_revision is not None:
            return DatabaseSchemaState.VERSIONED

        _validate_legacy_tables(db_inspector, table_names)
        _validate_new_tables(db_inspector, table_names)
        known_tables = (
            set(LEGACY_TABLE_COLUMNS) | set(NEW_TABLE_COLUMNS)
        ) & table_names
        if not known_tables:
            return DatabaseSchemaState.EMPTY

        current_expected = {
            **{
                table_name: columns
                | HEAD_EXTRA_COLUMNS.get(table_name, set())
                for table_name, columns in LEGACY_TABLE_COLUMNS.items()
            },
            **NEW_TABLE_COLUMNS,
        }
        if _is_complete(db_inspector, table_names, current_expected):
            return DatabaseSchemaState.UNVERSIONED_CURRENT

        if not (set(NEW_TABLE_COLUMNS) & table_names) and _is_complete(
            db_inspector,
            table_names,
            LEGACY_TABLE_COLUMNS,
        ):
            return DatabaseSchemaState.COMPLETE_LEGACY

        return DatabaseSchemaState.PARTIAL_LEGACY


def inspect_database_state(
    database_url: str | None = None,
) -> DatabaseSchemaState:
    """Classify an application database without changing it."""

    url = database_url or get_settings().database_url_sync
    engine = create_engine(url)
    try:
        return _inspect_database_state(engine)
    finally:
        engine.dispose()


def upgrade_database() -> None:
    """Upgrade an empty, legacy or interrupted additive schema to head."""

    database_url = get_settings().database_url_sync
    engine = create_engine(database_url)
    try:
        state = _inspect_database_state(engine)
    finally:
        engine.dispose()

    logger.info("Database schema state before migration: %s", state.value)
    command.upgrade(_config(database_url), "head")
