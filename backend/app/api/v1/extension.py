"""
Extension API — backs the Chrome scraper extension.

Two flavors of endpoint:
- /extension/tokens/* — token management. Called by the dashboard, no
  bearer-token auth (relies on the dashboard's existing session cookie).
- /extension/leads — lead intake. Called by the extension itself, requires
  `Authorization: Bearer apex_ext_<...>` header. Each successful request
  bumps last_used_at on the token row so stale tokens are visible.

Lead intake creates a fresh LeadBatch tagged with the P-manual-upload
profile (same one CSV uploads use) so extension-sourced leads flow
through the same enrollment pipeline.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.activity import Activity
from app.models.extension_token import (
    ExtensionToken,
    generate_token,
    hash_token,
    TOKEN_PREFIX,
)
from app.models.lead import Company, Lead, LeadBatch, LeadProfile

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Token management (dashboard-side) ────────────────────────


class TokenCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)


class TokenInfo(BaseModel):
    id: str
    label: str
    created_at: str
    last_used_at: Optional[str] = None
    revoked_at: Optional[str] = None


@router.post("/tokens", status_code=201)
async def create_token(body: TokenCreateRequest, db: AsyncSession = Depends(get_db)):
    """Mint a new extension token. The raw token value is in the response
    exactly once — neither the DB nor any subsequent API call exposes it again."""
    raw, h = generate_token()

    tok = ExtensionToken(label=body.label.strip(), token_hash=h)
    db.add(tok)
    await db.commit()
    await db.refresh(tok)

    return {
        "id": str(tok.id),
        "label": tok.label,
        "token": raw,  # shown once — user must copy now
        "created_at": tok.created_at.isoformat() if tok.created_at else None,
        "warning": "Save this token now — it cannot be retrieved later. If lost, revoke + re-issue.",
    }


@router.get("/tokens")
async def list_tokens(db: AsyncSession = Depends(get_db)):
    """List all tokens. Hash and raw value are never returned — only metadata."""
    result = await db.execute(
        select(ExtensionToken).order_by(ExtensionToken.created_at.desc())
    )
    tokens = result.scalars().all()
    return {
        "tokens": [
            TokenInfo(
                id=str(t.id),
                label=t.label,
                created_at=t.created_at.isoformat() if t.created_at else None,
                last_used_at=t.last_used_at.isoformat() if t.last_used_at else None,
                revoked_at=t.revoked_at.isoformat() if t.revoked_at else None,
            ).model_dump()
            for t in tokens
        ],
        "total": len(tokens),
    }


@router.delete("/tokens/{token_id}")
async def revoke_token(token_id: str, db: AsyncSession = Depends(get_db)):
    """Soft-revoke a token. Hard-delete is intentionally not exposed — we
    keep revoked tokens for audit (so we can answer 'when was Radhika's
    Chrome token last used' even after revoking)."""
    try:
        tid = uuid.UUID(token_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token id")

    result = await db.execute(select(ExtensionToken).where(ExtensionToken.id == tid))
    tok = result.scalar_one_or_none()
    if not tok:
        raise HTTPException(status_code=404, detail="Token not found")
    if tok.revoked_at is None:
        tok.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return {"status": "revoked", "id": str(tok.id), "label": tok.label}


# ─── Lead intake (extension-side) ─────────────────────────────


class ExtensionLead(BaseModel):
    """A single lead the extension scraped. Maps to the same RawLead shape
    our backend adapters produce — keeps the ingestion path uniform."""
    first_name: str
    last_name: str = ""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    job_title: str = ""
    department: Optional[str] = None
    seniority: Optional[str] = None
    city: str = ""
    state: str = ""
    country: str = "India"
    company_name: str = ""
    company_domain: Optional[str] = None
    company_industry: Optional[str] = None
    extra_data: dict = Field(default_factory=dict)


class ExtensionLeadBatch(BaseModel):
    """One batch of leads from the extension. `source` records which page
    type the team member captured (fhrai, schools_org_in, gem, linkedin)."""
    source: str = Field(..., min_length=1, max_length=50)
    source_url: Optional[str] = None
    label: Optional[str] = None  # human-readable batch note
    leads: list[ExtensionLead]


async def _validate_token(
    db: AsyncSession,
    auth_header: Optional[str],
) -> ExtensionToken:
    """Look up the bearer token. Returns the row or raises 401."""
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    raw = auth_header[len("Bearer ") :].strip()
    if not raw.startswith(TOKEN_PREFIX):
        raise HTTPException(status_code=401, detail="Token has wrong prefix")

    h = hash_token(raw)
    result = await db.execute(
        select(ExtensionToken).where(ExtensionToken.token_hash == h)
    )
    tok = result.scalar_one_or_none()
    if not tok:
        raise HTTPException(status_code=401, detail="Token not recognized")
    if tok.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Token revoked")

    # Bump last_used_at — best effort, don't block the request on it.
    tok.last_used_at = datetime.now(timezone.utc)
    return tok


@router.post("/leads", status_code=201)
async def receive_extension_leads(
    body: ExtensionLeadBatch,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Receive a batch of leads scraped by the extension.

    Same downstream effect as a CSV upload: creates a fresh LeadBatch
    tagged with the P-manual-upload profile, dedupes by email, attaches
    the extension token's label to the batch.notes for auditability.
    """
    tok = await _validate_token(db, authorization)

    if not body.leads:
        return {"status": "ok", "created": 0, "skipped": 0, "batch": None}

    # Find or create the P-manual-upload profile to stamp the batch
    profile_q = await db.execute(
        select(LeadProfile).where(LeadProfile.code == "P-manual-upload")
    )
    profile = profile_q.scalar_one_or_none()

    notes_parts = [f"Extension upload from {tok.label}"]
    if body.label:
        notes_parts.append(body.label)
    notes_parts.append(f"source={body.source}")

    batch = LeadBatch(
        triggered_by="extension_upload",
        target_lead_count=len(body.leads),
        status="active",
        notes=" — ".join(notes_parts),
        profile_id=profile.id if profile else None,
        extra_data={
            "extension_token_id": str(tok.id),
            "extension_token_label": tok.label,
            "source": body.source,
            "source_url": body.source_url,
        },
    )
    db.add(batch)
    await db.flush()

    created = 0
    skipped = 0

    for raw in body.leads:
        # Dedup by email if present. Without an email we can't reliably
        # dedupe — count those as creates and let the team review duplicates
        # via the dashboard.
        if raw.email:
            existing_q = await db.execute(
                select(Lead).where(Lead.email == raw.email.lower())
            )
            if existing_q.scalar_one_or_none():
                skipped += 1
                continue

        # Find or create company
        company = None
        if raw.company_name:
            cresult = await db.execute(
                select(Company).where(Company.name == raw.company_name.strip())
            )
            company = cresult.scalar_one_or_none()
            if not company:
                company = Company(
                    name=raw.company_name.strip(),
                    domain=raw.company_domain,
                    industry=raw.company_industry or "Other",
                )
                db.add(company)
                await db.flush()

        lead = Lead(
            batch_id=batch.id,
            company_id=company.id if company else None,
            first_name=raw.first_name or "Unknown",
            last_name=raw.last_name or "",
            email=raw.email.lower() if raw.email else None,
            phone=raw.phone,
            linkedin_url=raw.linkedin_url,
            job_title=raw.job_title or "(from extension)",
            department=raw.department,
            seniority=raw.seniority,
            city=raw.city,
            state=raw.state,
            country=raw.country,
            source=f"extension_{body.source}",
            stage="prospect",
            tags=["extension_upload", body.source],
            enrichment_data=raw.extra_data,
        )
        db.add(lead)
        await db.flush()

        db.add(Activity(
            lead_id=lead.id,
            type="extension_capture",
            channel="system",
            description=f"Captured by extension from {body.source} ({tok.label})",
            extra_data={
                "source": body.source,
                "source_url": body.source_url,
                "token_label": tok.label,
            },
        ))
        created += 1

    await db.commit()
    await db.refresh(batch)

    logger.info(
        f"Extension upload: {created} created, {skipped} skipped (duplicates) "
        f"into batch {batch.batch_code} from {tok.label} ({body.source})"
    )

    return {
        "status": "ok",
        "created": created,
        "skipped": skipped,
        "batch": {
            "id": str(batch.id),
            "batch_code": batch.batch_code,
            "notes": batch.notes,
        },
    }


@router.get("/whoami")
async def whoami(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Token validation probe. Extension calls this on first run to verify
    its token is wired correctly before attempting captures."""
    tok = await _validate_token(db, authorization)
    return {
        "id": str(tok.id),
        "label": tok.label,
        "created_at": tok.created_at.isoformat() if tok.created_at else None,
    }
