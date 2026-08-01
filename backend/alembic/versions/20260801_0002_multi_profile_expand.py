"""Add multi-Profile entities, discovery, audit and persistent Trap state.

The schema in this revision is static by design. Do not replace these
definitions with imports from app.models or Base.metadata.
"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa


revision = "20260801_0002"
down_revision = "20260801_0001"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "device_entities",
    "discovery_config",
    "discovery_jobs",
    "audit_logs",
    "trap_events",
)

EXPECTED_COLUMNS = {
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

PRIMARY_KEYS = {table_name: ("id",) for table_name in NEW_TABLES}

UNIQUE_COLUMN_SETS = {
    "device_entities": {
        ("device_id", "profile_id", "table_id", "entity_key")
    },
    "trap_events": {("alert_id",)},
}

EXPANDED_COLUMN_FACTORIES = {
    "devices": {
        "profile_id": lambda: sa.Column(
            "profile_id", sa.String(length=128), nullable=True
        ),
        "profile_version": lambda: sa.Column(
            "profile_version", sa.String(length=64), nullable=True
        ),
        "profile_evidence_version": lambda: sa.Column(
            "profile_evidence_version", sa.String(length=160), nullable=True
        ),
        "serial_number": lambda: sa.Column(
            "serial_number", sa.String(length=128), nullable=True
        ),
        "mac_addresses": lambda: sa.Column(
            "mac_addresses", sa.JSON(), nullable=True
        ),
        "discovery_source": lambda: sa.Column(
            "discovery_source", sa.String(length=32), nullable=True
        ),
        "last_discovered_at": lambda: sa.Column(
            "last_discovered_at", sa.DateTime(timezone=True), nullable=True
        ),
        "last_health_latency_ms": lambda: sa.Column(
            "last_health_latency_ms", sa.Float(), nullable=True
        ),
        "last_full_poll_status": lambda: sa.Column(
            "last_full_poll_status", sa.String(length=32), nullable=True
        ),
        "profile_scalar_states": lambda: sa.Column(
            "profile_scalar_states", sa.JSON(), nullable=True
        ),
    },
    "alerts": {
        "entity_key": lambda: sa.Column(
            "entity_key", sa.String(length=256), nullable=True
        ),
        "trap_level": lambda: sa.Column(
            "trap_level", sa.Integer(), nullable=True
        ),
        "trap_oid": lambda: sa.Column(
            "trap_oid", sa.String(length=256), nullable=True
        ),
    },
}


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _unique_column_sets(
    inspector: sa.Inspector, table_name: str
) -> set[tuple[str, ...]]:
    unique_sets = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints(table_name)
        if item.get("column_names")
    }
    unique_sets.update(
        tuple(item["column_names"])
        for item in inspector.get_indexes(table_name)
        if item.get("unique") and item.get("column_names")
    )
    return unique_sets


def _validate_existing_table(
    inspector: sa.Inspector, table_name: str
) -> None:
    missing = EXPECTED_COLUMNS[table_name] - _column_names(
        inspector, table_name
    )
    if missing:
        formatted = ", ".join(sorted(missing))
        raise RuntimeError(
            f"Cannot resume multi-Profile migration: existing table "
            f"'{table_name}' is incomplete (missing {formatted})."
        )

    actual_pk = tuple(
        inspector.get_pk_constraint(table_name).get("constrained_columns") or ()
    )
    expected_pk = PRIMARY_KEYS[table_name]
    if actual_pk != expected_pk:
        raise RuntimeError(
            f"Cannot resume multi-Profile migration: table '{table_name}' "
            f"has primary key {actual_pk or '<none>'}, expected {expected_pk}."
        )

    required_unique = UNIQUE_COLUMN_SETS.get(table_name, set())
    missing_unique = required_unique - _unique_column_sets(inspector, table_name)
    if missing_unique:
        formatted = ", ".join(str(columns) for columns in sorted(missing_unique))
        raise RuntimeError(
            f"Cannot resume multi-Profile migration: table '{table_name}' "
            f"is missing unique key(s) {formatted}."
        )


def _ensure_index(
    table_name: str,
    index_name: str,
    columns: Iterable[str],
    *,
    unique: bool = False,
) -> None:
    inspector = sa.inspect(op.get_bind())
    expected_columns = tuple(columns)
    for item in inspector.get_indexes(table_name):
        existing_columns = tuple(item.get("column_names") or ())
        if item.get("name") == index_name:
            return
        if (
            existing_columns == expected_columns
            and bool(item.get("unique")) == unique
        ):
            return
    op.create_index(index_name, table_name, list(expected_columns), unique=unique)


def _create_device_entities() -> None:
    op.create_table(
        "device_entities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("table_id", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_key", sa.String(length=256), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=True),
        sa.Column("index_key", sa.JSON(), nullable=False),
        sa.Column("raw_values", sa.JSON(), nullable=False),
        sa.Column("normalized_values", sa.JSON(), nullable=False),
        sa.Column("field_states", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_present", sa.Boolean(), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id",
            "profile_id",
            "table_id",
            "entity_key",
            name="uq_device_entity_identity",
        ),
    )


def _create_discovery_config() -> None:
    op.create_table(
        "discovery_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cidr", sa.String(length=64), nullable=False),
        sa.Column("community", sa.String(length=128), nullable=False),
        sa.Column("snmp_port", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("scan_on_startup", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_discovery_jobs() -> None:
    op.create_table(
        "discovery_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("cidr", sa.String(length=64), nullable=False),
        sa.Column("snmp_port", sa.Integer(), nullable=False),
        sa.Column("total_hosts", sa.Integer(), nullable=False),
        sa.Column("scanned_hosts", sa.Integer(), nullable=False),
        sa.Column("responded_hosts", sa.Integer(), nullable=False),
        sa.Column("recognized_hosts", sa.Integer(), nullable=False),
        sa.Column("imported_devices", sa.Integer(), nullable=False),
        sa.Column("updated_devices", sa.Integer(), nullable=False),
        sa.Column("unsupported_devices", sa.Integer(), nullable=False),
        sa.Column("no_response_hosts", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_audit_logs() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("actor_role", sa.String(length=16), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("change_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_trap_events() -> None:
    op.create_table(
        "trap_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=False),
        sa.Column("notification_oid", sa.String(length=256), nullable=True),
        sa.Column("raw_level", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("varbinds", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["alert_id"], ["alerts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id"),
    )


CREATE_TABLE = {
    "device_entities": _create_device_entities,
    "discovery_config": _create_discovery_config,
    "discovery_jobs": _create_discovery_jobs,
    "audit_logs": _create_audit_logs,
    "trap_events": _create_trap_events,
}

INDEXES = (
    ("devices", "ix_devices_profile_id", ("profile_id",), False),
    ("devices", "ix_devices_serial_number", ("serial_number",), False),
    ("alerts", "ix_alerts_entity_key", ("entity_key",), False),
    (
        "device_entities",
        "ix_device_entities_device_id",
        ("device_id",),
        False,
    ),
    (
        "device_entities",
        "ix_device_entities_profile_id",
        ("profile_id",),
        False,
    ),
    (
        "device_entities",
        "ix_device_entities_table_id",
        ("table_id",),
        False,
    ),
    (
        "device_entities",
        "ix_device_entities_entity_type",
        ("entity_type",),
        False,
    ),
    ("discovery_jobs", "ix_discovery_jobs_status", ("status",), False),
    (
        "discovery_jobs",
        "ix_discovery_jobs_created_at",
        ("created_at",),
        False,
    ),
    ("audit_logs", "ix_audit_logs_actor_id", ("actor_id",), False),
    ("audit_logs", "ix_audit_logs_action", ("action",), False),
    (
        "audit_logs",
        "ix_audit_logs_target_type",
        ("target_type",),
        False,
    ),
    ("audit_logs", "ix_audit_logs_target_id", ("target_id",), False),
    ("audit_logs", "ix_audit_logs_result", ("result",), False),
    ("audit_logs", "ix_audit_logs_created_at", ("created_at",), False),
    ("trap_events", "ix_trap_events_device_id", ("device_id",), False),
    ("trap_events", "ix_trap_events_created_at", ("created_at",), False),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    for table_name in NEW_TABLES:
        if table_name not in table_names:
            CREATE_TABLE[table_name]()
            table_names.add(table_name)
            continue
        _validate_existing_table(inspector, table_name)

    for table_name, column_factories in EXPANDED_COLUMN_FACTORIES.items():
        inspector = sa.inspect(bind)
        if table_name not in inspector.get_table_names():
            raise RuntimeError(
                f"Cannot apply multi-Profile migration: required baseline "
                f"table '{table_name}' does not exist."
            )
        existing = _column_names(inspector, table_name)
        for column_name, column_factory in column_factories.items():
            if column_name not in existing:
                op.add_column(table_name, column_factory())
                existing.add(column_name)

    for table_name, index_name, columns, unique in INDEXES:
        _ensure_index(
            table_name,
            index_name,
            columns,
            unique=unique,
        )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade from the multi-Profile schema is intentionally unsupported. "
        "The migration adds persistent entities, discovery history, audit logs "
        "and Trap evidence; restore a database backup instead of dropping them."
    )
