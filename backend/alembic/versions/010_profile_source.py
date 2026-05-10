"""Add source column to lead_profiles, route passive profiles to passive adapters.

Replaces hardcoded Apollo dispatch with a per-profile source string. The
autopilot orchestrator now reads profile.source and looks up the matching
adapter in app.services.lead_sources.SOURCES.

Backfill:
- All existing 8 active profiles default to source='apollo' (their current
  behavior — unchanged).
- P-website-inbound → source='website_form' (passive; never auto-discovers)
- P-manual-upload → source='csv_upload' (passive; never auto-discovers)
- P-legacy → source='apollo' (inactive; doesn't matter, but defaulting
  keeps invariant "every profile has a source" intact)

Going forward, new scrapers (FHRAI, CBSE, GeM, Lusha) become valid values
for this column. Old profiles can be retargeted at any new source via
PUT /api/v1/automation/profiles/{id}.

Revision ID: 010_profile_source
Revises: 009_inbound
"""
from alembic import op
import sqlalchemy as sa


revision = "010_profile_source"
down_revision = "009_inbound"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. Add source column with default. server_default keeps existing
    # rows on Apollo until explicit migration UPDATEs below.
    op.add_column(
        "lead_profiles",
        sa.Column("source", sa.String(50), nullable=False, server_default="apollo"),
    )

    # 2. Route the two passive profiles seeded in migration 009 to their
    # passive adapters. If they don't exist (older DB without 009), the
    # UPDATE is a no-op — safe to re-run.
    conn.execute(sa.text("""
        UPDATE lead_profiles
        SET source = 'website_form'
        WHERE code = 'P-website-inbound'
    """))
    conn.execute(sa.text("""
        UPDATE lead_profiles
        SET source = 'csv_upload'
        WHERE code = 'P-manual-upload'
    """))


def downgrade():
    op.drop_column("lead_profiles", "source")
