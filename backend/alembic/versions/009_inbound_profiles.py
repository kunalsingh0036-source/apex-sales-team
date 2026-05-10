"""Inbound source profiles + webhook secret.

Adds two new built-in profiles for non-Apollo lead sources:
- P-website-inbound: form submissions from theapexhumancompany.com
- P-manual-upload: CSV imports (from LinkedIn Sales Nav exports, trade-show
  attendee lists, referrals, etc.)

Both are flagged is_active=False so they don't enter Apollo round-robin
rotation — they're "passive" profiles that receive leads pushed in from
outside, not pulled from Apollo. The autopilot won't try to discover
into them.

Also seeds an `inbound_webhook_secret` SystemSetting (random hex). The
website form uses this in an X-Apex-Webhook-Secret header so we can
verify requests came from us, not random spam.

Revision ID: 009_inbound
Revises: 008_profiles
"""
from alembic import op
import sqlalchemy as sa
import json
import secrets


revision = "009_inbound"
down_revision = "008_profiles"
branch_labels = None
depends_on = None


PASSIVE_PROFILES = [
    {
        "code": "P-website-inbound",
        "name": "Website Inbound",
        "description": "Leads submitted via the consultation form on theapexhumancompany.com. Highest-intent source — these prospects asked to talk. Not part of Apollo rotation.",
        "search_params": {},
        "is_active": False,
        "rotation_priority": 1,  # if ever activated, runs first
    },
    {
        "code": "P-manual-upload",
        "name": "Manual / CSV Upload",
        "description": "Leads imported in bulk from CSV — LinkedIn Sales Navigator exports, trade-show attendee lists, conference registrations, partner referrals. Each upload creates a fresh batch.",
        "search_params": {},
        "is_active": False,
        "rotation_priority": 2,
    },
]


def upgrade():
    conn = op.get_bind()

    # 1. Seed passive profiles (idempotent)
    for p in PASSIVE_PROFILES:
        conn.execute(
            sa.text("""
                INSERT INTO lead_profiles (code, name, description, search_params, rotation_priority, is_active)
                VALUES (:code, :name, :description, CAST(:search_params AS JSONB), :rotation_priority, :is_active)
                ON CONFLICT (code) DO NOTHING
            """),
            {
                "code": p["code"],
                "name": p["name"],
                "description": p["description"],
                "search_params": json.dumps(p["search_params"]),
                "rotation_priority": p["rotation_priority"],
                "is_active": p["is_active"],
            },
        )

    # 2. Generate a webhook secret if it doesn't exist. Idempotent — never
    # overwrites an existing secret because that would break the deployed
    # website's hardcoded value.
    # NOTE: system_settings has `key` as its primary key — there is no `id`
    # column. Earlier version of this migration tried SELECT id ... and
    # crashed alembic on the prod DB, leaving 009 + 010 unapplied for days.
    row = conn.execute(
        sa.text("SELECT key FROM system_settings WHERE key = 'inbound_webhook_secret'")
    ).first()
    if not row:
        secret = secrets.token_urlsafe(32)
        conn.execute(
            sa.text("""
                INSERT INTO system_settings (key, value)
                VALUES ('inbound_webhook_secret', CAST(:value AS JSONB))
            """),
            {"value": json.dumps({"secret": secret, "created_at": "migration_009"})},
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM lead_profiles WHERE code IN ('P-website-inbound', 'P-manual-upload')")
    )
    conn.execute(
        sa.text("DELETE FROM system_settings WHERE key = 'inbound_webhook_secret'")
    )
