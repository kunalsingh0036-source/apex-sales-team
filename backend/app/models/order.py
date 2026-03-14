import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, Integer, Numeric, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin


ORDER_STAGES = ["brief", "design", "tech_spec", "sampling", "production", "qc", "delivery"]

VALID_STAGE_TRANSITIONS = {
    "brief": ["design"],
    "design": ["tech_spec", "brief"],
    "tech_spec": ["sampling", "design"],
    "sampling": ["production", "tech_spec"],
    "production": ["qc"],
    "qc": ["delivery", "production"],
    "delivery": [],
}


class Order(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "orders"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    quote_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotes.id")
    )
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # 7-stage pipeline
    stage: Mapped[str] = mapped_column(String(50), default="brief", index=True)

    # Financial
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    gst_rate: Mapped[float] = mapped_column(Numeric(4, 2), default=18.0)
    gst_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    # Dates
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_delivery_date: Mapped[Optional[date]] = mapped_column(Date)
    brief_received_date: Mapped[Optional[date]] = mapped_column(Date)

    # Addresses
    shipping_address: Mapped[Optional[str]] = mapped_column(Text)
    billing_address: Mapped[Optional[str]] = mapped_column(Text)

    # Meta
    notes: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="orders")
    quote: Mapped[Optional["Quote"]] = relationship("Quote", foreign_keys=[quote_id])
    line_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    stage_history: Mapped[list["OrderStageLog"]] = relationship(
        "OrderStageLog", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base, UUIDMixin):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"),
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

    # Customization details
    size_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    color: Mapped[Optional[str]] = mapped_column(String(100))
    gsm: Mapped[Optional[int]] = mapped_column(Integer)
    customization_type: Mapped[Optional[str]] = mapped_column(String(100))
    customization_details: Mapped[str] = mapped_column(Text, default="")
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    order: Mapped["Order"] = relationship("Order", back_populates="line_items")
    product: Mapped[Optional["Product"]] = relationship("Product")


class OrderStageLog(Base, UUIDMixin):
    __tablename__ = "order_stage_logs"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    from_stage: Mapped[Optional[str]] = mapped_column(String(50))
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order: Mapped["Order"] = relationship("Order", back_populates="stage_history")
