"""ExtensionToken model — bearer tokens issued to the Chrome scraper extension.

The raw token is shown to the user exactly once at issuance and never stored.
Lookup uses SHA-256 of the presented token — constant-time-comparable, prevents
DB dumps from leaking usable credentials.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


# Token format: `apex_ext_<43-char-base64url>` — readable in logs.
# `secrets.token_urlsafe(32)` gives 43 chars (256 bits of entropy).
TOKEN_PREFIX = "apex_ext_"


def generate_token() -> tuple[str, str]:
    """Generate a new (raw_token, sha256_hash) pair.

    Caller stores the hash in the DB and shows the raw token to the user
    exactly once."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, h


def hash_token(raw_token: str) -> str:
    """SHA-256 of the raw token. Used for verification on inbound requests."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class ExtensionToken(Base, UUIDMixin):
    """Bearer token used by the Chrome scraper extension."""

    __tablename__ = "extension_tokens"

    label: Mapped[str] = mapped_column(String(200), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
