"""Add indexes used by operational retention cleanup.

Revision ID: 20260802_0003
Revises: 20260801_0002
"""
from alembic import op
import sqlalchemy as sa


revision = "20260802_0003"
down_revision = "20260801_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    index_names = {item["name"] for item in inspector.get_indexes("alerts")}
    if "ix_alerts_resolved_at" not in index_names:
        op.create_index("ix_alerts_resolved_at", "alerts", ["resolved_at"])


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade from the data-retention schema is intentionally unsupported. "
        "Restore a database backup instead of changing production history in place."
    )
