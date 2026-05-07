"""Lead profiles: replace narrow ICP with wide rotating segments.

Apex sells uniforms and merchandise to organizations of every shape — schools,
hotels, banks, defence PSUs, FMCG corporates. The single-ICP model was
choking the funnel because every Apollo search hit the same narrow pool and
came back ~95% deduplicated. Profiles fix this by defining segment-shaped
search params (a profile = "Schools (India)" or "Hospitality Luxury Tier 1")
and rotating between them so each batch hits a fresh pool.

Adds:
- lead_profiles table (code, name, description, search_params JSONB,
  is_active, rotation_priority, last_used_at, stats JSONB)
- lead_batches.profile_id FK
- 8 seeded default profiles + 1 inactive "Legacy" profile for backfill
- Existing 13 batches stamped with the legacy profile so no NULL FKs

Revision ID: 008_profiles
Revises: 007_batches
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import json
import uuid


revision = "008_profiles"
down_revision = "007_batches"
branch_labels = None
depends_on = None


# Default profiles seeded on every fresh DB. Editable in the UI; rotation
# picks active ones round-robin by last_used_at. The search_params shape
# matches what app.services.lead_discovery.search_people consumes.
DEFAULT_PROFILES = [
    {
        "code": "P-schools-india",
        "name": "Schools (India)",
        "description": "Principals, directors of operations, and admin heads at K-12 schools, residential schools, and universities across India. Uniforms, sports kits, branded merchandise.",
        "rotation_priority": 10,
        "search_params": {
            "job_titles": ["Principal", "Headmaster", "Director Operations", "Director Administration", "School Administrator", "Vice Principal"],
            "industries": ["Education Management", "Primary/Secondary Education", "Higher Education"],
            "locations": ["India"],
            "company_sizes": ["51-200", "201-500", "501-1000"],
            "keywords": ["school", "academy", "education"],
        },
    },
    {
        "code": "P-hospitality-luxury",
        "name": "Hotels & Hospitality",
        "description": "GMs, F&B Heads, HR Heads at luxury hotels, resorts, and hospitality groups. Front-of-house uniforms, F&B staff wear, gifting.",
        "rotation_priority": 20,
        "search_params": {
            "job_titles": ["General Manager", "F&B Manager", "Director F&B", "HR Director", "Director of Operations", "Hotel Manager"],
            "industries": ["Hospitality", "Restaurants", "Leisure, Travel & Tourism"],
            "locations": ["India"],
            "company_sizes": ["201-500", "501-1000", "1001-5000"],
            "keywords": ["hotel", "resort", "hospitality"],
        },
    },
    {
        "code": "P-pharma-corporate",
        "name": "Pharma Corporate",
        "description": "CHRO, Admin, Procurement at pharma companies 500+ employees. Branded scrubs, manufacturing-floor wear, corporate gifting.",
        "rotation_priority": 30,
        "search_params": {
            "job_titles": ["Chief Human Resources Officer", "VP Human Resources", "Head of Procurement", "Admin Manager", "General Manager"],
            "industries": ["Pharmaceuticals", "Biotechnology", "Hospital & Health Care"],
            "locations": ["India"],
            "company_sizes": ["501-1000", "1001-5000", "5001-10000"],
            "keywords": [],
        },
    },
    {
        "code": "P-defence-govt",
        "name": "Defence & Government",
        "description": "Procurement, supply officers, and admin at defence PSUs and central/state govt orgs. High-volume uniform contracts.",
        "rotation_priority": 40,
        "search_params": {
            "job_titles": ["Director Procurement", "Head of Supply", "Admin Officer", "Joint Secretary", "Deputy Secretary"],
            "industries": ["Defense & Space", "Government Administration", "Public Safety"],
            "locations": ["India"],
            "company_sizes": ["1001-5000", "5001-10000", "10000+"],
            "keywords": ["defence", "ministry", "PSU"],
        },
    },
    {
        "code": "P-fmcg-retail",
        "name": "FMCG & Retail",
        "description": "Procurement, brand, and HR heads at FMCG/retail giants. Corporate gifting, employee merchandise, retail uniforms.",
        "rotation_priority": 50,
        "search_params": {
            "job_titles": ["Head of Procurement", "Brand Manager", "HR Director", "Marketing Director", "Procurement Manager"],
            "industries": ["Consumer Goods", "Retail", "Apparel & Fashion"],
            "locations": ["India"],
            "company_sizes": ["501-1000", "1001-5000", "5001-10000"],
            "keywords": [],
        },
    },
    {
        "code": "P-banking-financial",
        "name": "Banking & Financial",
        "description": "CHRO, Admin Heads, Branch Operations at banks and NBFCs. Branch-staff uniforms, corporate gifting at relationship-manager scale.",
        "rotation_priority": 60,
        "search_params": {
            "job_titles": ["Chief Human Resources Officer", "VP Human Resources", "Head of Administration", "Operations Director"],
            "industries": ["Banking", "Financial Services", "Insurance"],
            "locations": ["India"],
            "company_sizes": ["501-1000", "1001-5000", "5001-10000"],
            "keywords": [],
        },
    },
    {
        "code": "P-tech-saas",
        "name": "Technology & SaaS",
        "description": "People Ops, Employer Brand, and Admin at IT services and SaaS firms 500+ employees. Onboarding kits, swag, employer-brand merch.",
        "rotation_priority": 70,
        "search_params": {
            "job_titles": ["Head of People", "Employer Brand Manager", "VP People", "Chief People Officer", "Admin Manager"],
            "industries": ["Information Technology and Services", "Computer Software", "Internet"],
            "locations": ["India"],
            "company_sizes": ["501-1000", "1001-5000", "5001-10000"],
            "keywords": [],
        },
    },
    {
        "code": "P-realestate-developers",
        "name": "Real Estate & Construction",
        "description": "Project HR, site admin, and procurement at real-estate developers and construction giants. Site PPE, branded apparel, marketing-event merchandise.",
        "rotation_priority": 80,
        "search_params": {
            "job_titles": ["Project HR Manager", "Site Administrator", "Head of Procurement", "General Manager", "Director Operations"],
            "industries": ["Real Estate", "Construction", "Civil Engineering"],
            "locations": ["India"],
            "company_sizes": ["501-1000", "1001-5000", "5001-10000"],
            "keywords": [],
        },
    },
]


# Inactive profile for pre-existing batches so the FK isn't NULL.
LEGACY_PROFILE = {
    "code": "P-legacy",
    "name": "Legacy / Pre-profile",
    "description": "Catch-all for batches B-0001..B-0013 created before profiles existed. Inactive — never enters rotation.",
    "rotation_priority": 9999,
    "is_active": False,
    "search_params": {},
}


def upgrade():
    conn = op.get_bind()

    # 1. lead_profiles table
    op.create_table(
        "lead_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("search_params", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("rotation_priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # 2. profile_id on lead_batches
    op.add_column(
        "lead_batches",
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("lead_profiles.id"), nullable=True),
    )
    op.create_index("ix_lead_batches_profile_id", "lead_batches", ["profile_id"])

    # 3. Seed default profiles
    for p in DEFAULT_PROFILES:
        conn.execute(
            sa.text("""
                INSERT INTO lead_profiles (code, name, description, search_params, rotation_priority, is_active)
                VALUES (:code, :name, :description, CAST(:search_params AS JSONB), :rotation_priority, true)
                ON CONFLICT (code) DO NOTHING
            """),
            {
                "code": p["code"],
                "name": p["name"],
                "description": p["description"],
                "search_params": json.dumps(p["search_params"]),
                "rotation_priority": p["rotation_priority"],
            },
        )

    # 4. Seed legacy profile (inactive — never rotates)
    conn.execute(
        sa.text("""
            INSERT INTO lead_profiles (code, name, description, search_params, rotation_priority, is_active)
            VALUES (:code, :name, :description, CAST(:search_params AS JSONB), :rotation_priority, false)
            ON CONFLICT (code) DO NOTHING
        """),
        {
            "code": LEGACY_PROFILE["code"],
            "name": LEGACY_PROFILE["name"],
            "description": LEGACY_PROFILE["description"],
            "search_params": json.dumps(LEGACY_PROFILE["search_params"]),
            "rotation_priority": LEGACY_PROFILE["rotation_priority"],
        },
    )

    # 5. Backfill existing batches with the legacy profile so profile_id is never NULL
    conn.execute(
        sa.text("""
            UPDATE lead_batches
            SET profile_id = (SELECT id FROM lead_profiles WHERE code = 'P-legacy')
            WHERE profile_id IS NULL
        """)
    )


def downgrade():
    op.drop_index("ix_lead_batches_profile_id", table_name="lead_batches")
    op.drop_column("lead_batches", "profile_id")
    op.drop_table("lead_profiles")
