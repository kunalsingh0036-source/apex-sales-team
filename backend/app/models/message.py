import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, Numeric, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from app.models.base import Base, UUIDMixin, TimestampMixin


class MessageTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "message_templates"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    subject: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    tone: Mapped[str] = mapped_column(String(100), default="authoritative_warm")
    industry_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    role_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    performance: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )


class Message(Base, UUIDMixin):
    __tablename__ = "messages"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id")
    )
    enrollment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_enrollments.id")
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_templates.id")
    )
    variant: Mapped[Optional[str]] = mapped_column(String(10))
    subject: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    classification: Mapped[Optional[str]] = mapped_column(String(50))
    classification_confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    ai_suggested_reply: Mapped[Optional[str]] = mapped_column(Text)
    external_id: Mapped[Optional[str]] = mapped_column(String(500))
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="messages")
