"""Sync database schema with current SQLAlchemy models.

Resolves drift from ad-hoc ALTER TABLE statements and model changes
since migrations 001 and 002. Uses IF EXISTS/IF NOT EXISTS guards
to be idempotent — safe to run on databases in any state.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "003_sync"
down_revision = "002_crm"
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


def upgrade():
    conn = op.get_bind()

    def add_col(table, column, col_type, **kwargs):
        """Add column if it doesn't exist."""
        if not column_exists(table, column):
            op.add_column(table, sa.Column(column, col_type, **kwargs))

    def drop_col(table, column):
        """Drop column if it exists."""
        if column_exists(table, column):
            op.drop_column(table, column)

    # ─── leads ────────────────────────────────────────────────
    add_col("leads", "email_verified", sa.Boolean(), server_default="false")
    add_col("leads", "whatsapp_number", sa.String(50))
    add_col("leads", "instagram_handle", sa.String(200))
    add_col("leads", "score_breakdown", JSONB, server_default="{}")
    add_col("leads", "lost_reason", sa.Text())
    add_col("leads", "assigned_to", UUID(as_uuid=True))
    drop_col("leads", "social_handles")

    # ─── companies ────────────────────────────────────────────
    add_col("companies", "headquarters", sa.String(500))
    # Fix employee_count type: INTEGER → VARCHAR(50)
    if column_exists("companies", "employee_count"):
        conn.execute(sa.text(
            "ALTER TABLE companies ALTER COLUMN employee_count TYPE VARCHAR(50) "
            "USING employee_count::VARCHAR"
        ))

    # ─── lead_events ──────────────────────────────────────────
    # Rename title → event_name
    if column_exists("lead_events", "title") and not column_exists("lead_events", "event_name"):
        op.alter_column("lead_events", "title", new_column_name="event_name")
    elif not column_exists("lead_events", "event_name"):
        add_col("lead_events", "event_name", sa.String(500), nullable=False, server_default="")

    # Rename/replace relevance_score → relevance
    drop_col("lead_events", "relevance_score")
    add_col("lead_events", "relevance", sa.Text())
    add_col("lead_events", "detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"))

    # Drop old description if it exists (replaced by relevance)
    if column_exists("lead_events", "description") and column_exists("lead_events", "relevance"):
        drop_col("lead_events", "description")

    # ─── message_templates ────────────────────────────────────
    # Rename type → category
    if column_exists("message_templates", "type") and not column_exists("message_templates", "category"):
        op.alter_column("message_templates", "type", new_column_name="category")
    elif not column_exists("message_templates", "category"):
        add_col("message_templates", "category", sa.String(100))

    drop_col("message_templates", "target_industry")
    drop_col("message_templates", "target_role")
    drop_col("message_templates", "is_active")
    add_col("message_templates", "tone", sa.String(100), server_default="authoritative_warm")
    add_col("message_templates", "industry_tags", sa.ARRAY(sa.String), server_default="{}")
    add_col("message_templates", "role_tags", sa.ARRAY(sa.String), server_default="{}")
    add_col("message_templates", "is_ai_generated", sa.Boolean(), server_default="false")
    add_col("message_templates", "created_by", UUID(as_uuid=True))

    # ─── messages ─────────────────────────────────────────────
    add_col("messages", "opened_at", sa.DateTime(timezone=True))
    add_col("messages", "replied_at", sa.DateTime(timezone=True))
    add_col("messages", "enrollment_id", UUID(as_uuid=True))
    add_col("messages", "variant", sa.String(10))
    add_col("messages", "classification_confidence", sa.Numeric(3, 2))
    add_col("messages", "ai_suggested_reply", sa.Text())

    # ─── sequences ────────────────────────────────────────────
    add_col("sequences", "created_by", UUID(as_uuid=True))
    add_col("sequences", "target_role", sa.String(200))
    add_col("sequences", "settings", JSONB, server_default="{}")

    # ─── campaigns ────────────────────────────────────────────
    add_col("campaigns", "target_filter", JSONB, server_default="{}")
    add_col("campaigns", "created_by", UUID(as_uuid=True))

    # ─── campaign_enrollments ─────────────────────────────────
    add_col("campaign_enrollments", "last_step_at", sa.DateTime(timezone=True))
    add_col("campaign_enrollments", "next_step_at", sa.DateTime(timezone=True))

    # ─── activities ───────────────────────────────────────────
    add_col("activities", "performed_by", UUID(as_uuid=True))
    add_col("activities", "channel", sa.String(50))

    # ─── system_settings (ensure exists) ──────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key VARCHAR(200) PRIMARY KEY,
            value JSONB NOT NULL
        )
    """))

    # ─── lead_events (ensure exists) ──────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS lead_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            company_id UUID REFERENCES companies(id),
            event_type VARCHAR(100) NOT NULL,
            event_name VARCHAR(500) NOT NULL DEFAULT '',
            event_date DATE,
            relevance TEXT,
            source_url VARCHAR(1000),
            detected_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    # ─── ab_test_results (ensure exists) ──────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ab_test_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID NOT NULL REFERENCES campaigns(id),
            step_number INTEGER NOT NULL,
            variant_a_sent INTEGER DEFAULT 0,
            variant_a_opened INTEGER DEFAULT 0,
            variant_a_replied INTEGER DEFAULT 0,
            variant_b_sent INTEGER DEFAULT 0,
            variant_b_opened INTEGER DEFAULT 0,
            variant_b_replied INTEGER DEFAULT 0,
            winner VARCHAR(10),
            confidence NUMERIC(3,2),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))


def downgrade():
    # This migration is a sync — downgrade just drops added columns
    # (renames and type changes are not reverted to keep data safe)
    for table, col in [
        ("activities", "performed_by"),
        ("activities", "channel"),
        ("campaign_enrollments", "last_step_at"),
        ("campaign_enrollments", "next_step_at"),
        ("campaigns", "target_filter"),
        ("campaigns", "created_by"),
        ("sequences", "created_by"),
        ("messages", "opened_at"),
        ("messages", "replied_at"),
        ("messages", "enrollment_id"),
        ("messages", "variant"),
        ("messages", "classification_confidence"),
        ("messages", "ai_suggested_reply"),
        ("message_templates", "tone"),
        ("message_templates", "industry_tags"),
        ("message_templates", "role_tags"),
        ("message_templates", "is_ai_generated"),
        ("message_templates", "created_by"),
        ("leads", "email_verified"),
        ("leads", "whatsapp_number"),
        ("leads", "instagram_handle"),
        ("leads", "score_breakdown"),
        ("leads", "lost_reason"),
        ("leads", "assigned_to"),
        ("companies", "headquarters"),
    ]:
        if column_exists(table, col):
            op.drop_column(table, col)
