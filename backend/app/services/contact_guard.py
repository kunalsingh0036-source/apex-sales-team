"""Contact guard — prevents duplicate outreach to leads."""

from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.message import Message

DEFAULT_COOLDOWN_DAYS = 14


async def can_contact(lead, db: AsyncSession, cooldown_days: int = DEFAULT_COOLDOWN_DAYS) -> tuple[bool, str]:
    """Check if a lead can be contacted. Returns (allowed, reason)."""
    if lead.do_not_contact:
        return False, "do_not_contact"
    if lead.consent_status in ("opted_out", "invalid_email"):
        return False, f"consent_{lead.consent_status}"
    if lead.last_contacted_at:
        days_since = (datetime.now(timezone.utc) - lead.last_contacted_at).days
        if days_since < cooldown_days:
            return False, f"contacted_{days_since}_days_ago"
    return True, ""


async def update_last_contacted(lead, db: AsyncSession, contacted_at: datetime | None = None):
    """Update lead's last_contacted_at timestamp."""
    lead.last_contacted_at = contacted_at or datetime.now(timezone.utc)
