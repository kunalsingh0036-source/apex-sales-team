"""Extension auth tokens for the Chrome scraper.

The browser extension authenticates against the agent with a long-lived
bearer token issued from the dashboard. One token per team member (or per
device). Tokens are recorded by SHA-256 hash, never stored in plaintext —
the dashboard shows the raw token exactly once at issuance, then never again.

Schema:
- id              UUID primary key
- label           String — human-readable ("Radhika's Chrome", "Office iMac")
- token_hash      String(64) — SHA-256 of the bearer token, indexed for lookup
- created_at      timestamptz
- last_used_at    timestamptz — bumped on every successful auth so we can
                  see stale tokens and revoke them
- revoked_at      timestamptz — soft-delete; revoked tokens stay in the
                  table for audit but auth is rejected

Token format: `apex_ext_<43-char-base64url>` so it's recognizable in logs
and easy to grep.

Revision ID: 011_extension_tokens
Revises: 010_profile_source
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "011_extension_tokens"
down_revision = "010_profile_source"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extension_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, index=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("extension_tokens")
