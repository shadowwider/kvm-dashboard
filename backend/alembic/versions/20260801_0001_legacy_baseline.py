"""Create or adopt the last single-Profile dashboard schema.

This revision is intentionally self-contained. Historical revisions must not
import the application's live ORM metadata because future model changes would
silently change the meaning of this baseline.
"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa


revision = "20260801_0001"
down_revision = None
branch_labels = None
depends_on = None

LEGACY_TABLES = (
    "users",
    "devices",
    "endpoints",
    "oid_registry",
    "status_metrics",
    "alerts",
    "device_aliases",
    "simulator_runs",
)

CORE_COLUMNS = {
    "users": {
        "id",
        "username",
        "password_hash",
        "role",
        "is_active",
        "created_at",
    },
    "devices": {
        "id",
        "name",
        "host",
        "port",
        "community",
        "location",
        "description",
        "is_active",
        "poll_interval",
        "last_poll",
        "last_status",
        "created_at",
        "updated_at",
    },
    "endpoints": {
        "id",
        "device_id",
        "name",
        "index",
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
        "revision",
        "manifest",
        "created_at",
        "updated_at",
    },
}

PRIMARY_KEYS = {
    "users": ("id",),
    "devices": ("id",),
    "endpoints": ("id",),
    "oid_registry": ("id",),
    "status_metrics": ("id",),
    "alerts": ("id",),
    "device_aliases": ("target_id",),
    "simulator_runs": ("id",),
}

UNIQUE_COLUMN_SETS = {
    "users": {("username",)},
    "oid_registry": {("oid",), ("name",)},
}

# ``backend/init.sql`` was the supported pre-Alembic PostgreSQL bootstrap.
# It made ``status_metrics`` Timescale-ready without an ``id`` primary key and
# omitted the OID unique index.  The baseline can safely adopt that shape and
# add the OID index below; other schema deviations remain a hard failure.
POSTGRES_PRIMARY_KEY_EXCEPTIONS = {
    "status_metrics": {()},
}
ADOPTABLE_UNIQUE_OMISSIONS = {
    "oid_registry": {("oid",)},
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
    missing_core = CORE_COLUMNS[table_name] - _column_names(inspector, table_name)
    if missing_core:
        missing = ", ".join(sorted(missing_core))
        raise RuntimeError(
            f"Cannot adopt legacy table '{table_name}': missing core columns "
            f"{missing}. Restore a supported backup or repair the schema "
            "before retrying."
        )

    actual_pk = tuple(
        inspector.get_pk_constraint(table_name).get("constrained_columns") or ()
    )
    expected_pk = PRIMARY_KEYS[table_name]
    accepted_primary_keys = {expected_pk}
    if inspector.bind.dialect.name == "postgresql":
        accepted_primary_keys.update(
            POSTGRES_PRIMARY_KEY_EXCEPTIONS.get(table_name, set())
        )
    if actual_pk not in accepted_primary_keys:
        raise RuntimeError(
            f"Cannot adopt legacy table '{table_name}': primary key is "
            f"{actual_pk or '<none>'}, expected {expected_pk}."
        )

    required_unique = UNIQUE_COLUMN_SETS.get(table_name, set())
    missing_unique = required_unique - _unique_column_sets(inspector, table_name)
    if inspector.bind.dialect.name == "postgresql":
        missing_unique -= ADOPTABLE_UNIQUE_OMISSIONS.get(table_name, set())
    if missing_unique:
        formatted = ", ".join(str(columns) for columns in sorted(missing_unique))
        raise RuntimeError(
            f"Cannot adopt legacy table '{table_name}': missing unique key(s) "
            f"{formatted}."
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


def _ensure_unique_constraint(
    table_name: str,
    constraint_name: str,
    columns: Iterable[str],
) -> None:
    """Add a PostgreSQL unique constraint only when the old bootstrap lacks it."""
    inspector = sa.inspect(op.get_bind())
    expected_columns = tuple(columns)
    existing = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints(table_name)
        if item.get("column_names")
    }
    existing.update(
        tuple(item["column_names"])
        for item in inspector.get_indexes(table_name)
        if item.get("unique") and item.get("column_names")
    )
    if expected_columns not in existing:
        op.create_unique_constraint(constraint_name, table_name, list(columns))


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_devices() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("host", sa.String(length=64), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("community", sa.String(length=64), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_oid", sa.String(length=256), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("poll_interval", sa.Integer(), nullable=False),
        sa.Column("last_poll", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_metrics", sa.JSON(), nullable=True),
        sa.Column("endpoint_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_endpoints() -> None:
    op.create_table(
        "endpoints",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column(
            "module_type",
            sa.String(length=16),
            server_default="cpu",
            nullable=False,
        ),
        sa.Column("last_status", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_oid_registry() -> None:
    op.create_table(
        "oid_registry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("oid", sa.String(length=256), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=True),
        sa.Column("enum_map", sa.JSON(), nullable=True),
        sa.Column("is_table", sa.Boolean(), nullable=False),
        sa.Column("table_base_oid", sa.String(length=256), nullable=True),
        sa.Column("table_column", sa.Integer(), nullable=True),
        sa.Column("alert_enabled", sa.Boolean(), nullable=False),
        sa.Column("alert_gt", sa.Float(), nullable=True),
        sa.Column("alert_lt", sa.Float(), nullable=True),
        sa.Column("alert_eq_str", sa.String(length=64), nullable=True),
        sa.Column("alert_ne_str", sa.String(length=64), nullable=True),
        sa.Column("alert_severity", sa.String(length=16), nullable=False),
        sa.Column("poll_enabled", sa.Boolean(), nullable=False),
        sa.Column("archive_enabled", sa.Boolean(), nullable=False),
        sa.Column("display_enabled", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("oid"),
    )


def _create_status_metrics() -> None:
    op.create_table(
        "status_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("endpoint_id", sa.String(length=128), nullable=True),
        sa.Column("oid_name", sa.String(length=64), nullable=False),
        sa.Column("value_str", sa.String(length=256), nullable=True),
        sa.Column("value_num", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_alerts() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("endpoint_id", sa.String(length=128), nullable=True),
        sa.Column("oid_name", sa.String(length=64), nullable=True),
        sa.Column("alert_type", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_device_aliases() -> None:
    op.create_table(
        "device_aliases",
        sa.Column("target_id", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("target_id"),
    )


def _create_simulator_runs() -> None:
    op.create_table(
        "simulator_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("session_epoch", sa.String(length=64), nullable=True),
        sa.Column("session_started_at", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


CREATE_TABLE = {
    "users": _create_users,
    "devices": _create_devices,
    "endpoints": _create_endpoints,
    "oid_registry": _create_oid_registry,
    "status_metrics": _create_status_metrics,
    "alerts": _create_alerts,
    "device_aliases": _create_device_aliases,
    "simulator_runs": _create_simulator_runs,
}


def _repair_known_legacy_columns(table_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    existing = _column_names(inspector, table_name)

    additions: dict[str, sa.Column] = {}
    if table_name == "users":
        additions = {
            "updated_at": sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("'1970-01-01 00:00:00+00:00'"),
                nullable=False,
            )
        }
    elif table_name == "devices":
        additions = {
            "system_oid": sa.Column(
                "system_oid", sa.String(length=256), nullable=True
            ),
            "model_name": sa.Column(
                "model_name", sa.String(length=128), nullable=True
            ),
            "last_health_check": sa.Column(
                "last_health_check", sa.DateTime(timezone=True), nullable=True
            ),
            "last_metrics": sa.Column("last_metrics", sa.JSON(), nullable=True),
            "endpoint_count": sa.Column(
                "endpoint_count",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            ),
        }
    elif table_name == "endpoints":
        additions = {
            "module_type": sa.Column(
                "module_type",
                sa.String(length=16),
                server_default="cpu",
                nullable=False,
            )
        }
    elif table_name == "oid_registry":
        additions = {
            "archive_enabled": sa.Column(
                "archive_enabled",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            )
        }
    elif table_name == "simulator_runs":
        additions = {
            "session_id": sa.Column(
                "session_id", sa.String(length=64), nullable=True
            ),
            "session_epoch": sa.Column(
                "session_epoch", sa.String(length=64), nullable=True
            ),
            "session_started_at": sa.Column(
                "session_started_at",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            ),
            "lease_expires_at": sa.Column(
                "lease_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        }

    for column_name, column in additions.items():
        if column_name not in existing:
            op.add_column(table_name, column)
            existing.add(column_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table_name in LEGACY_TABLES:
        if table_name not in existing_tables:
            CREATE_TABLE[table_name]()
            existing_tables.add(table_name)
            continue

        _validate_existing_table(inspector, table_name)
        _repair_known_legacy_columns(table_name)
        inspector = sa.inspect(bind)

    _ensure_index("users", "ix_users_username", ("username",), unique=True)
    if bind.dialect.name == "postgresql":
        _ensure_unique_constraint(
            "oid_registry", "uq_oid_registry_oid", ("oid",)
        )
    _ensure_index("endpoints", "ix_endpoints_device_id", ("device_id",))
    _ensure_index("status_metrics", "ix_status_metrics_time", ("time",))
    _ensure_index(
        "status_metrics",
        "ix_status_metrics_device_oid_time",
        ("device_id", "oid_name", "time"),
    )
    _ensure_index(
        "status_metrics",
        "ix_status_metrics_endpoint_time",
        ("endpoint_id", "oid_name", "time"),
    )
    _ensure_index("alerts", "ix_alerts_device_id", ("device_id",))
    _ensure_index("alerts", "ix_alerts_endpoint_id", ("endpoint_id",))
    _ensure_index("alerts", "ix_alerts_created_at", ("created_at",))
    _ensure_index(
        "simulator_runs",
        "ix_simulator_runs_lease_expires_at",
        ("lease_expires_at",),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade from the legacy baseline is intentionally unsupported. "
        "Dropping adopted production tables is unsafe; restore a database "
        "backup instead."
    )
