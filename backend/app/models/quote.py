import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, Integer, Numeric, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin


class Quote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "quotes"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    quote_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)

    # Financial
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    gst_rate: Mapped[float] = mapped_column(Numeric(4, 2), default=18.0)
    gst_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    # Validity
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)

    # Terms
    payment_terms: Mapped[Optional[str]] = mapped_column(String(200))
    delivery_terms: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    terms_and_conditions: Mapped[str] = mapped_column(Text, default="")

    # Conversion tracking
    converted_to_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="quotes")
    line_items: Mapped[list["QuoteItem"]] = relationship(
        "QuoteItem", back_populates="quote", cascade="all, delete-orphan"
    )


class QuoteItem(Base, UUIDMixin):
    __tablename__ = "quote_items"

    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id")
    )
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Customization
    size_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    color: Mapped[Optional[str]] = mapped_column(String(100))
    gsm: Mapped[Optional[int]] = mapped_column(Integer)
    customization_type: Mapped[Optional[str]] = mapped_column(String(100))
    customization_details: Mapped[str] = mapped_column(Text, default="")

    quote: Mapped["Quote"] = relationship("Quote", back_populates="line_items")
    product: Mapped[Optional["Product"]] = relationship("Product")
