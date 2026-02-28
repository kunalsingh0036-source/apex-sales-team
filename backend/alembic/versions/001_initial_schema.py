"""Initial database schema — all tables for Apex Outreach Agent.

Revision ID: 001_initial
Revises:
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(500), unique=True, nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("role", sa.String(50), server_default="admin"),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # System Settings
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", postgresql.JSONB, nullable=False),
    )

    # Companies
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False, index=True),
        sa.Column("domain", sa.String(500)),
        sa.Column("industry", sa.String(200)),
        sa.Column("sub_industry", sa.String(200)),
        sa.Column("employee_count", sa.Integer()),
        sa.Column("annual_revenue", sa.String(100)),
        sa.Column("city", sa.String(200)),
        sa.Column("state", sa.String(200)),
        sa.Column("country", sa.String(200), server_default="India"),
        sa.Column("website", sa.String(500)),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("phone", sa.String(100)),
        sa.Column("enrichment_data", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Leads
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("first_name", sa.String(200), nullable=False),
        sa.Column("last_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(500), index=True),
        sa.Column("phone", sa.String(100)),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("job_title", sa.String(300)),
        sa.Column("department", sa.String(200)),
        sa.Column("seniority", sa.String(100)),
        sa.Column("city", sa.String(200)),
        sa.Column("state", sa.String(200)),
        sa.Column("country", sa.String(200), server_default="India"),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id")),
        sa.Column("lead_score", sa.Integer()),
        sa.Column("stage", sa.String(50), server_default="prospect", index=True),
        sa.Column("source", sa.String(200)),
        sa.Column("consent_status", sa.String(50), server_default="unknown"),
        sa.Column("do_not_contact", sa.Boolean(), server_default="false"),
        sa.Column("deal_value", sa.Numeric(12, 2)),
        sa.Column("social_handles", postgresql.JSONB, server_default="{}"),
        sa.Column("enrichment_data", postgresql.JSONB, server_default="{}"),
        sa.Column("tags", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Lead Events
    op.create_table(
        "lead_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("event_date", sa.Date()),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("relevance_score", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Sequences
    op.create_table(
        "sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("target_industry", sa.String(200)),
        sa.Column("target_role", sa.String(200)),
        sa.Column("channel", sa.String(50), server_default="email"),
        sa.Column("steps", postgresql.JSONB, server_default="[]"),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Campaigns
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sequences.id"), nullable=False),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("total_leads", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Campaign Enrollments
    op.create_table(
        "campaign_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sequences.id"), nullable=False),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("current_step", sa.Integer(), server_default="0"),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_step_at", sa.DateTime(timezone=True)),
        sa.Column("next_step_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_lead"),
    )

    # Message Templates
    op.create_table(
        "message_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("channel", sa.String(50), server_default="email"),
        sa.Column("type", sa.String(100)),
        sa.Column("subject", sa.String(1000)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column("target_industry", sa.String(200)),
        sa.Column("target_role", sa.String(200)),
        sa.Column("performance", postgresql.JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id")),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign_enrollments.id")),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("message_templates.id")),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(1000)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("external_id", sa.String(500)),
        sa.Column("classification", sa.String(100)),
        sa.Column("classification_confidence", sa.Numeric(3, 2)),
        sa.Column("ai_suggested_reply", sa.Text()),
        sa.Column("variant", sa.String(10)),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_lead_id", "messages", ["lead_id"])
    op.create_index("ix_messages_channel_status", "messages", ["channel", "status"])

    # Activities
    op.create_table(
        "activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(50)),
        sa.Column("description", sa.Text()),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activities_lead_id", "activities", ["lead_id"])

    # Daily Metrics
    op.create_table(
        "daily_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id")),
        sa.Column("sent", sa.Integer(), server_default="0"),
        sa.Column("delivered", sa.Integer(), server_default="0"),
        sa.Column("opened", sa.Integer(), server_default="0"),
        sa.Column("clicked", sa.Integer(), server_default="0"),
        sa.Column("replied", sa.Integer(), server_default="0"),
        sa.Column("positive_replies", sa.Integer(), server_default="0"),
        sa.Column("meetings_booked", sa.Integer(), server_default="0"),
        sa.Column("bounced", sa.Integer(), server_default="0"),
        sa.Column("unsubscribed", sa.Integer(), server_default="0"),
        sa.UniqueConstraint("date", "channel", "campaign_id", name="uq_daily_metrics"),
    )

    # A/B Test Results
    op.create_table(
        "ab_test_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("variant_a_sent", sa.Integer(), server_default="0"),
        sa.Column("variant_a_opened", sa.Integer(), server_default="0"),
        sa.Column("variant_a_replied", sa.Integer(), server_default="0"),
        sa.Column("variant_b_sent", sa.Integer(), server_default="0"),
        sa.Column("variant_b_opened", sa.Integer(), server_default="0"),
        sa.Column("variant_b_replied", sa.Integer(), server_default="0"),
        sa.Column("winner", sa.String(10)),
        sa.Column("confidence", sa.Numeric(3, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ab_test_results")
    op.drop_table("daily_metrics")
    op.drop_table("activities")
    op.drop_table("messages")
    op.drop_table("message_templates")
    op.drop_table("campaign_enrollments")
    op.drop_table("campaigns")
    op.drop_table("sequences")
    op.drop_table("lead_events")
    op.drop_table("leads")
    op.drop_table("companies")
    op.drop_table("system_settings")
    op.drop_table("users")
