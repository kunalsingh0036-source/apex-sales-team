"""Clean up duplicate pending messages left behind by pre-drip orchestrator.

Before this migration, the orchestrator generated every step of a sequence
up-front — leaving 2-4 messages per lead sitting in content_review at once.
That creates a logical mess: approving step 3 before step 1 has been sent
means step 3 references an email that never actually went out.

This migration:
1. Finds every enrollment that has more than one outbound message in
   content_review / draft / failed / queued status.
2. Keeps the OLDEST pending message (the real step 1).
3. Marks the rest as `status = 'superseded'` so they're hidden from the
   review queue but still auditable.
4. Resets the enrollment's `current_step` to point at the kept step, and
   sets `next_step_at = NULL` so the drip gate will reschedule on the
   next real send.

Idempotent — safe to re-run.

Revision ID: 006_drip_cleanup
Revises: 005_numbering
"""
from alembic import op
import sqlalchemy as sa


revision = "006_drip_cleanup"
down_revision = "005_numbering"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # For each enrollment with multiple pending outbound messages, keep the
    # oldest one and mark the rest as "superseded".
    conn.execute(sa.text("""
        WITH pending AS (
            SELECT
                id,
                enrollment_id,
                ROW_NUMBER() OVER (
                    PARTITION BY enrollment_id
                    ORDER BY created_at ASC
                ) AS rn
            FROM messages
            WHERE enrollment_id IS NOT NULL
              AND direction = 'outbound'
              AND status IN ('content_review', 'draft', 'failed', 'queued')
        )
        UPDATE messages
        SET status = 'superseded',
            metadata = COALESCE(metadata, '{}'::jsonb)
                       || '{"superseded_reason": "drip_cleanup_006"}'::jsonb
        WHERE id IN (SELECT id FROM pending WHERE rn > 1)
    """))

    # Reset enrollment.current_step so advance_enrollment lands on the kept step,
    # and null out next_step_at so the drip gate reschedules on the next send.
    conn.execute(sa.text("""
        UPDATE campaign_enrollments ce
        SET current_step = COALESCE(sub.kept_step_idx, ce.current_step),
            next_step_at = NULL
        FROM (
            SELECT
                m.enrollment_id,
                -- The kept step's index is however many messages this enrollment
                -- has actually sent (or kept as pending step 1). Default to 0
                -- if nothing sent yet and one pending message exists.
                (
                    SELECT COUNT(*)
                    FROM messages m2
                    WHERE m2.enrollment_id = m.enrollment_id
                      AND m2.direction = 'outbound'
                      AND m2.status = 'sent'
                ) AS kept_step_idx
            FROM messages m
            WHERE m.enrollment_id IS NOT NULL
            GROUP BY m.enrollment_id
        ) sub
        WHERE ce.id = sub.enrollment_id
          AND ce.status = 'active'
    """))


def downgrade():
    # Restore superseded messages to content_review (best-effort)
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE messages
        SET status = 'content_review',
            metadata = metadata - 'superseded_reason'
        WHERE status = 'superseded'
          AND metadata ? 'superseded_reason'
          AND metadata->>'superseded_reason' = 'drip_cleanup_006'
    """))
