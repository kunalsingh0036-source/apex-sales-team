"""Lead batches: group leads in waves of 20 with B-xxxx codes.

Adds:
- lead_batches table with batch_number (sequence) and batch_code ("B-0001")
  populated by a BEFORE INSERT/UPDATE trigger.
- leads.batch_id FK to lead_batches.

Backfills the existing 88 leads into 5 batches by created_at ASC:
  L-0001..L-0020 -> B-0001
  L-0021..L-0040 -> B-0002
  L-0041..L-0060 -> B-0003
  L-0061..L-0080 -> B-0004
  L-0081..L-0088 -> B-0005 (partial; only this one ever can be partial)

Going forward, autopilot creates a new B-xxxx every cycle, exactly 20 leads.

Revision ID: 007_batches
Revises: 006_drip_cleanup
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "007_batches"
down_revision = "006_drip_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. Sequence for batch_number (mirrors lead_number_seq).
    conn.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS lead_batch_number_seq START 1"))

    # 2. lead_batches table.
    op.create_table(
        "lead_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "batch_number",
            sa.BigInteger,
            nullable=False,
            unique=True,
            server_default=sa.text("nextval('lead_batch_number_seq'::regclass)"),
        ),
        sa.Column("batch_code", sa.String(20), nullable=False, index=True, server_default=sa.text("''")),
        sa.Column("triggered_by", sa.String(50), nullable=False, server_default="manual"),
        # ^ "manual" | "auto_alternate_day" | "auto_after_completion" | "backfill"
        sa.Column("target_lead_count", sa.Integer, nullable=False, server_default="20"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        # ^ "active" (still being worked) | "complete" (no active enrollments left)
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("extra_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # 3. Trigger to keep batch_code in sync with batch_number ("B-0001" format).
    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION set_lead_batch_code()
        RETURNS trigger AS $$
        BEGIN
            NEW.batch_code := 'B-' || LPAD(NEW.batch_number::text, 4, '0');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    conn.execute(sa.text("""
        DROP TRIGGER IF EXISTS lead_batches_set_code ON lead_batches;
        CREATE TRIGGER lead_batches_set_code
            BEFORE INSERT OR UPDATE OF batch_number ON lead_batches
            FOR EACH ROW
            EXECUTE FUNCTION set_lead_batch_code();
    """))

    # 4. Add batch_id to leads.
    op.add_column(
        "leads",
        sa.Column("batch_id", UUID(as_uuid=True), sa.ForeignKey("lead_batches.id"), nullable=True),
    )
    op.create_index("ix_leads_batch_id", "leads", ["batch_id"])

    # 5. Backfill existing leads into batches of 20 by created_at ASC.
    # Each group of 20 (or remainder for the last one) gets a fresh batch.
    conn.execute(sa.text("""
        WITH numbered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (ORDER BY created_at ASC, lead_number ASC) AS rn
            FROM leads
        )
        SELECT 1
    """))

    # Compute how many backfill batches we need.
    total = conn.execute(sa.text("SELECT COUNT(*) FROM leads")).scalar() or 0
    if total > 0:
        num_batches = (total + 19) // 20  # ceil division
        for _ in range(num_batches):
            conn.execute(sa.text("""
                INSERT INTO lead_batches (triggered_by, status)
                VALUES ('backfill', 'active')
            """))

        # Walk the leads in order and stamp batch_id by 20s.
        # Use a window-function-driven UPDATE so it's one query.
        conn.execute(sa.text("""
            WITH numbered_leads AS (
                SELECT
                    id,
                    ((ROW_NUMBER() OVER (ORDER BY created_at ASC, lead_number ASC) - 1) / 20) + 1 AS batch_seq
                FROM leads
            ),
            numbered_batches AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY batch_number ASC) AS rn
                FROM lead_batches
                WHERE triggered_by = 'backfill'
            )
            UPDATE leads l
            SET batch_id = b.id
            FROM numbered_leads nl
            JOIN numbered_batches b ON b.rn = nl.batch_seq
            WHERE l.id = nl.id
        """))


def downgrade():
    op.drop_index("ix_leads_batch_id", table_name="leads")
    op.drop_column("leads", "batch_id")
    op.drop_table("lead_batches")
    op.get_bind().execute(sa.text("DROP FUNCTION IF EXISTS set_lead_batch_code() CASCADE"))
    op.get_bind().execute(sa.text("DROP SEQUENCE IF EXISTS lead_batch_number_seq"))
