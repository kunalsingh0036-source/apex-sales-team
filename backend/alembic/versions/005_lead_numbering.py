"""Sequential human-readable lead numbers (L-0001, L-0002, …).

Adds:
- leads.lead_number  — globally unique monotonically increasing integer,
                       populated by the lead_number_seq Postgres sequence.
- leads.lead_code    — formatted string 'L-0042' kept in sync by a BEFORE
                       INSERT/UPDATE trigger, so application code never
                       has to compute it.

Backfills both columns for existing rows in created_at ASC order, then
initializes the sequence at MAX(lead_number) + 1. Numbers never recycle:
if a lead is deleted, its number stays retired.

Revision ID: 005_numbering
Revises: 004_dedup
"""
from alembic import op
import sqlalchemy as sa


revision = "005_numbering"
down_revision = "004_dedup"
branch_labels = None
depends_on = None


def column_exists(table, column):
    from alembic import context
    conn = context.get_context().connection
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :column"
    ), {"table": table, "column": column})
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    # ─── 1. Add columns (nullable so backfill can run) ─────────────
    if not column_exists("leads", "lead_number"):
        op.add_column("leads", sa.Column("lead_number", sa.BigInteger(), nullable=True))
    if not column_exists("leads", "lead_code"):
        op.add_column("leads", sa.Column("lead_code", sa.String(20), nullable=True))

    # ─── 2. Backfill lead_number for existing rows, in created_at ASC order ────
    conn.execute(sa.text("""
        WITH numbered AS (
            SELECT id,
                   ROW_NUMBER() OVER (ORDER BY created_at ASC, id ASC) AS rn
            FROM leads
            WHERE lead_number IS NULL
        )
        UPDATE leads
        SET lead_number = numbered.rn
        FROM numbered
        WHERE leads.id = numbered.id;
    """))

    # ─── 3. Backfill lead_code from lead_number ────────────────────
    conn.execute(sa.text("""
        UPDATE leads
        SET lead_code = 'L-' || LPAD(lead_number::text, 4, '0')
        WHERE lead_code IS NULL;
    """))

    # ─── 4. Create the sequence starting after the current MAX ─────
    max_row = conn.execute(sa.text(
        "SELECT COALESCE(MAX(lead_number), 0) AS m FROM leads"
    )).fetchone()
    start_from = int(max_row.m or 0) + 1
    # idempotent creation
    conn.execute(sa.text(
        f"CREATE SEQUENCE IF NOT EXISTS lead_number_seq START {start_from} OWNED BY leads.lead_number"
    ))
    # If the sequence already existed (re-running migration), bump it
    conn.execute(sa.text(
        f"SELECT setval('lead_number_seq', GREATEST({start_from - 1}, (SELECT last_value FROM lead_number_seq)), true)"
    ))

    # ─── 5. Wire the sequence as the column default ────────────────
    op.alter_column(
        "leads", "lead_number",
        server_default=sa.text("nextval('lead_number_seq'::regclass)"),
    )

    # ─── 6. Create trigger that keeps lead_code = 'L-XXXX' ─────────
    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION set_lead_code() RETURNS trigger AS $$
        BEGIN
            NEW.lead_code := 'L-' || LPAD(NEW.lead_number::text, 4, '0');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    conn.execute(sa.text("DROP TRIGGER IF EXISTS leads_set_code ON leads"))
    conn.execute(sa.text("""
        CREATE TRIGGER leads_set_code
            BEFORE INSERT OR UPDATE OF lead_number ON leads
            FOR EACH ROW EXECUTE FUNCTION set_lead_code()
    """))

    # ─── 7. Lock the columns down now that they're fully populated ──
    op.alter_column("leads", "lead_number", nullable=False)
    op.alter_column("leads", "lead_code", nullable=False)

    # ─── 8. Add a unique index on lead_number + non-unique on lead_code ─
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_leads_lead_number ON leads (lead_number)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_leads_lead_code ON leads (lead_code)"
    ))


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DROP TRIGGER IF EXISTS leads_set_code ON leads"))
    conn.execute(sa.text("DROP FUNCTION IF EXISTS set_lead_code()"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_leads_lead_code"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_leads_lead_number"))
    if column_exists("leads", "lead_code"):
        op.drop_column("leads", "lead_code")
    if column_exists("leads", "lead_number"):
        op.drop_column("leads", "lead_number")
    conn.execute(sa.text("DROP SEQUENCE IF EXISTS lead_number_seq"))
