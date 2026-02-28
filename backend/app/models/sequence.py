import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin


class Sequence(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sequences"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    target_industry: Mapped[Optional[str]] = mapped_column(String(200))
    target_role: Mapped[Optional[str]] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    steps: Mapped[list] = mapped_column(JSONB, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="sequence")


class Campaign(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sequences.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="draft")
    target_filter: Mapped[dict] = mapped_column(JSONB, default=dict)
    total_leads: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    sequence: Mapped["Sequence"] = relationship(back_populates="campaigns")
    enrollments: Mapped[list["CampaignEnrollment"]] = relationship(
        back_populates="campaign"
    )


class CampaignEnrollment(Base, UUIDMixin):
    __tablename__ = "campaign_enrollments"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False
    )
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sequences.id"), nullable=False
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_step_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_step_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    campaign: Mapped["Campaign"] = relationship(back_populates="enrollments")
