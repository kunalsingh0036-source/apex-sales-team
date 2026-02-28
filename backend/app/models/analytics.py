import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Integer, Date, Numeric, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin


class DailyMetric(Base, UUIDMixin):
    __tablename__ = "daily_metrics"
    __table_args__ = (
        UniqueConstraint("date", "channel", "campaign_id", name="uq_daily_metrics"),
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id")
    )
    sent: Mapped[int] = mapped_column(Integer, default=0)
    delivered: Mapped[int] = mapped_column(Integer, default=0)
    opened: Mapped[int] = mapped_column(Integer, default=0)
    clicked: Mapped[int] = mapped_column(Integer, default=0)
    replied: Mapped[int] = mapped_column(Integer, default=0)
    positive_replies: Mapped[int] = mapped_column(Integer, default=0)
    meetings_booked: Mapped[int] = mapped_column(Integer, default=0)
    bounced: Mapped[int] = mapped_column(Integer, default=0)
    unsubscribed: Mapped[int] = mapped_column(Integer, default=0)


class ABTestResult(Base, UUIDMixin):
    __tablename__ = "ab_test_results"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_a_sent: Mapped[int] = mapped_column(Integer, default=0)
    variant_a_opened: Mapped[int] = mapped_column(Integer, default=0)
    variant_a_replied: Mapped[int] = mapped_column(Integer, default=0)
    variant_b_sent: Mapped[int] = mapped_column(Integer, default=0)
    variant_b_opened: Mapped[int] = mapped_column(Integer, default=0)
    variant_b_replied: Mapped[int] = mapped_column(Integer, default=0)
    winner: Mapped[Optional[str]] = mapped_column(String(10))
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
