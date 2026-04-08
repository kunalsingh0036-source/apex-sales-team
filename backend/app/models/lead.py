import uuid
from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import String, Text, Integer, Boolean, Numeric, Date, DateTime, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin


class Company(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(500), unique=True)
    industry: Mapped[str] = mapped_column(String(200), nullable=False)
    sub_industry: Mapped[Optional[str]] = mapped_column(String(200))
    employee_count: Mapped[Optional[str]] = mapped_column(String(50))
    headquarters: Mapped[Optional[str]] = mapped_column(String(500))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    annual_revenue: Mapped[Optional[str]] = mapped_column(String(100))
    enrichment_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    leads: Mapped[list["Lead"]] = relationship(back_populates="company")
    events: Mapped[list["LeadEvent"]] = relationship(back_populates="company")


class Lead(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "leads"

    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id")
    )
    first_name: Mapped[str] = mapped_column(String(200), nullable=False)
    last_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(500))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    whatsapp_number: Mapped[Optional[str]] = mapped_column(String(50))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    instagram_handle: Mapped[Optional[str]] = mapped_column(String(200))
    job_title: Mapped[str] = mapped_column(String(300), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(200))
    seniority: Mapped[Optional[str]] = mapped_column(String(50))
    city: Mapped[Optional[str]] = mapped_column(String(200))
    state: Mapped[Optional[str]] = mapped_column(String(200))
    country: Mapped[str] = mapped_column(String(100), default="India")
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    score_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    stage: Mapped[str] = mapped_column(String(50), default="prospect")
    deal_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    lost_reason: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    consent_status: Mapped[str] = mapped_column(String(20), default="unknown")
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    enrichment_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    company: Mapped[Optional["Company"]] = relationship(back_populates="leads")
    activities: Mapped[list["Activity"]] = relationship("Activity", back_populates="lead")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="lead")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class LeadEvent(Base, UUIDMixin):
    __tablename__ = "lead_events"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id")
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_name: Mapped[str] = mapped_column(String(500), nullable=False)
    event_date: Mapped[Optional[date]] = mapped_column(Date)
    relevance: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    detected_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    company: Mapped[Optional["Company"]] = relationship(back_populates="events")
