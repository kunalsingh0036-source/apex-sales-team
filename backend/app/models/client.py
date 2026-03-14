import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, Integer, Boolean, Numeric, Date, DateTime, ForeignKey, func, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin


class Client(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "clients"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id")
    )

    # Primary contact
    primary_contact_name: Mapped[str] = mapped_column(String(300), nullable=False)
    primary_contact_email: Mapped[Optional[str]] = mapped_column(String(500))
    primary_contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    primary_contact_title: Mapped[Optional[str]] = mapped_column(String(300))

    # AMA (Annual Merchandise Agreement)
    ama_tier: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    ama_commitment: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    ama_start_date: Mapped[Optional[date]] = mapped_column(Date)
    ama_end_date: Mapped[Optional[date]] = mapped_column(Date)

    # Status & details
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    billing_address: Mapped[Optional[str]] = mapped_column(Text)
    shipping_address: Mapped[Optional[str]] = mapped_column(Text)
    gst_number: Mapped[Optional[str]] = mapped_column(String(20))
    payment_terms: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    company: Mapped["Company"] = relationship("Company")
    lead: Mapped[Optional["Lead"]] = relationship("Lead")
    contact_persons: Mapped[list["ClientContact"]] = relationship(
        "ClientContact", back_populates="client", cascade="all, delete-orphan"
    )
    brand_assets: Mapped[list["BrandAsset"]] = relationship(
        "BrandAsset", back_populates="client", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["Interaction"]] = relationship(
        "Interaction", back_populates="client", cascade="all, delete-orphan"
    )
    sample_kits: Mapped[list["SampleKit"]] = relationship(
        "SampleKit", back_populates="client", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="client")
    quotes: Mapped[list["Quote"]] = relationship("Quote", back_populates="client")


class ClientContact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_contacts"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(500))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    title: Mapped[Optional[str]] = mapped_column(String(300))
    department: Mapped[Optional[str]] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")

    client: Mapped["Client"] = relationship("Client", back_populates="contact_persons")


class BrandAsset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "brand_assets"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text)
    file_url: Mapped[Optional[str]] = mapped_column(String(1000))
    notes: Mapped[str] = mapped_column(Text, default="")

    client: Mapped["Client"] = relationship("Client", back_populates="brand_assets")


class Interaction(Base, UUIDMixin):
    __tablename__ = "interactions"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    interaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    performed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date)
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    client: Mapped["Client"] = relationship("Client", back_populates="interactions")


class SampleKit(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sample_kits"

    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), index=True
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id")
    )
    recipient_name: Mapped[str] = mapped_column(String(300), nullable=False)
    recipient_company: Mapped[Optional[str]] = mapped_column(String(500))
    kit_name: Mapped[str] = mapped_column(String(300), nullable=False)
    contents: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(50), default="preparing")
    sent_date: Mapped[Optional[date]] = mapped_column(Date)
    delivered_date: Mapped[Optional[date]] = mapped_column(Date)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(200))
    feedback: Mapped[str] = mapped_column(Text, default="")
    conversion_status: Mapped[Optional[str]] = mapped_column(String(50))
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    client: Mapped[Optional["Client"]] = relationship("Client", back_populates="sample_kits")
