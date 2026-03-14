"""CRM tables — clients, products, orders, quotes.

Revision ID: 002_crm
Revises: 001_initial
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_crm"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Product Categories
    op.create_table(
        "product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_categories.id")),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Products
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("sku", sa.String(100), unique=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_categories.id"), nullable=False, index=True),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("gsm_range", sa.String(50)),
        sa.Column("available_sizes", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("available_colors", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("available_customizations", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("base_price", sa.Numeric(10, 2)),
        sa.Column("pricing_tiers", postgresql.JSONB, server_default="{}"),
        sa.Column("min_order_qty", sa.Integer(), server_default="50"),
        sa.Column("lead_time_days", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("image_urls", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Clients
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id")),
        sa.Column("primary_contact_name", sa.String(300), nullable=False),
        sa.Column("primary_contact_email", sa.String(500)),
        sa.Column("primary_contact_phone", sa.String(50)),
        sa.Column("primary_contact_title", sa.String(300)),
        sa.Column("ama_tier", sa.String(50), index=True),
        sa.Column("ama_commitment", sa.Numeric(14, 2)),
        sa.Column("ama_start_date", sa.Date()),
        sa.Column("ama_end_date", sa.Date()),
        sa.Column("status", sa.String(50), server_default="active", index=True),
        sa.Column("billing_address", sa.Text()),
        sa.Column("shipping_address", sa.Text()),
        sa.Column("gst_number", sa.String(20)),
        sa.Column("payment_terms", sa.String(100)),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("tags", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Client Contacts
    op.create_table(
        "client_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("email", sa.String(500)),
        sa.Column("phone", sa.String(50)),
        sa.Column("title", sa.String(300)),
        sa.Column("department", sa.String(200)),
        sa.Column("is_primary", sa.Boolean(), server_default="false"),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Brand Assets
    op.create_table(
        "brand_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("value", sa.Text()),
        sa.Column("file_url", sa.String(1000)),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Interactions
    op.create_table(
        "interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("interaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("follow_up_date", sa.Date()),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Sample Kits
    op.create_table(
        "sample_kits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL"), index=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id")),
        sa.Column("recipient_name", sa.String(300), nullable=False),
        sa.Column("recipient_company", sa.String(500)),
        sa.Column("kit_name", sa.String(300), nullable=False),
        sa.Column("contents", postgresql.JSONB, server_default="[]"),
        sa.Column("status", sa.String(50), server_default="preparing"),
        sa.Column("sent_date", sa.Date()),
        sa.Column("delivered_date", sa.Date()),
        sa.Column("follow_up_date", sa.Date()),
        sa.Column("tracking_number", sa.String(200)),
        sa.Column("feedback", sa.Text(), server_default=""),
        sa.Column("conversion_status", sa.String(50)),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Quotes
    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("quote_number", sa.String(50), unique=True, nullable=False),
        sa.Column("status", sa.String(50), server_default="draft", index=True),
        sa.Column("subtotal", sa.Numeric(14, 2), server_default="0"),
        sa.Column("gst_rate", sa.Numeric(4, 2), server_default="18.0"),
        sa.Column("gst_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("discount_percent", sa.Numeric(5, 2), server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("payment_terms", sa.String(200)),
        sa.Column("delivery_terms", sa.String(200)),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("terms_and_conditions", sa.Text(), server_default=""),
        sa.Column("converted_to_order_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("viewed_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Quote Items
    op.create_table(
        "quote_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("product_name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("size_breakdown", postgresql.JSONB, server_default="{}"),
        sa.Column("color", sa.String(100)),
        sa.Column("gsm", sa.Integer()),
        sa.Column("customization_type", sa.String(100)),
        sa.Column("customization_details", sa.Text(), server_default=""),
    )

    # Orders
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quotes.id")),
        sa.Column("order_number", sa.String(50), unique=True, nullable=False),
        sa.Column("stage", sa.String(50), server_default="brief", index=True),
        sa.Column("subtotal", sa.Numeric(14, 2), server_default="0"),
        sa.Column("gst_rate", sa.Numeric(4, 2), server_default="18.0"),
        sa.Column("gst_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("discount_percent", sa.Numeric(5, 2), server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column("expected_delivery_date", sa.Date()),
        sa.Column("actual_delivery_date", sa.Date()),
        sa.Column("brief_received_date", sa.Date()),
        sa.Column("shipping_address", sa.Text()),
        sa.Column("billing_address", sa.Text()),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Order Items
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("product_name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("size_breakdown", postgresql.JSONB, server_default="{}"),
        sa.Column("color", sa.String(100)),
        sa.Column("gsm", sa.Integer()),
        sa.Column("customization_type", sa.String(100)),
        sa.Column("customization_details", sa.Text(), server_default=""),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
    )

    # Order Stage Logs
    op.create_table(
        "order_stage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_stage", sa.String(50)),
        sa.Column("to_stage", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("order_stage_logs")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("quote_items")
    op.drop_table("quotes")
    op.drop_table("sample_kits")
    op.drop_table("interactions")
    op.drop_table("brand_assets")
    op.drop_table("client_contacts")
    op.drop_table("clients")
    op.drop_table("products")
    op.drop_table("product_categories")
