"""Add last_contacted_at to leads and backfill from messages.

Revision ID: 004_dedup
Revises: 003_sync
"""
from alembic import op
import sqlalchemy as sa

revision = "004_dedup"
down_revision = "003_sync"
branch_labels = None
depends_on = None


def column_exists(table, column):
    """Check if a column exists in a table."""
    from alembic import context
    conn = context.get_context().connection
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :column"
    ), {"table": table, "column": column})
    return result.fetchone() is not None


def add_col(table, column, col_type, **kwargs):
    """Add column if it doesn't exist."""
    if not column_exists(table, column):
        op.add_column(table, sa.Column(column, col_type, **kwargs))


def upgrade():
    conn = op.get_bind()

    # ─── Add last_contacted_at column ────────────────────────
    add_col("leads", "last_contacted_at", sa.DateTime(timezone=True))

    # ─── Backfill from most recent outbound sent message ─────
    conn.execute(sa.text("""
        UPDATE leads SET last_contacted_at = sub.max_sent
        FROM (
            SELECT lead_id, MAX(sent_at) as max_sent
            FROM messages
            WHERE direction = 'outbound' AND status = 'sent' AND sent_at IS NOT NULL
            GROUP BY lead_id
        ) sub
        WHERE leads.id = sub.lead_id AND leads.last_contacted_at IS NULL
    """))


def downgrade():
    if column_exists("leads", "last_contacted_at"):
        op.drop_column("leads", "last_contacted_at")
