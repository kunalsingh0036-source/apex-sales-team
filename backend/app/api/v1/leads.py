import uuid
import io
import hmac
import hashlib
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Header, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
from app.dependencies import get_db
from app.models.lead import Company, Lead
from app.models.activity import Activity
from app.models.user import SystemSetting
from app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadResponse, LeadStageUpdate, LeadFilter,
)
from app.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Inbound webhook (public — secured by HMAC of request body) ────────

class InboundWebhookPayload(BaseModel):
    """Shape the public website form sends to /leads/inbound-webhook.

    Mirrors the ConsultationForm fields so the website's submit handler
    can post the form data directly without remapping. All fields except
    name+email+company are optional — keep it forgiving so the website can
    evolve the form without breaking the agent."""
    name: str
    email: str
    company: str
    phone: Optional[str] = None
    interest: Optional[str] = None      # apparel | gifting | design | multiple | not-sure
    quantity: Optional[str] = None      # 25-50, 50-200, ... 1000+
    message: Optional[str] = None
    source_url: Optional[str] = None    # which page they submitted from
    referrer: Optional[str] = None      # http referrer for attribution


@router.post("/inbound-webhook", status_code=201)
async def inbound_lead_webhook(
    request: Request,
    payload: InboundWebhookPayload,
    x_apex_webhook_secret: str = Header(..., alias="X-Apex-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
):
    """Receive a lead from the public Apex website's contact form.

    Auth model: shared-secret header. The website holds a copy of the
    secret in its NEXT_PUBLIC_… env var (acceptable here because submission
    is browser-originated and rate-limited; the secret prevents random
    bots from finding the URL and spamming us). For higher-stakes use we
    can rotate the secret + move to a server-only proxy.

    Lead is stamped with the P-website-inbound profile so it shows up
    distinctly from Apollo discoveries. Each submission gets its own
    one-off batch (B-xxxx) for clean tracking — these are the highest-
    intent leads we have.
    """
    # 1. Verify the secret. We read from the INBOUND_WEBHOOK_SECRET env var
    # (set on Railway and matched by APEX_INBOUND_WEBHOOK_SECRET on the
    # public website's Vercel project). DB-backed secret is also accepted
    # as a fallback so an operator can rotate via system_settings without
    # restarting the API.
    import os as _os
    expected = _os.getenv("INBOUND_WEBHOOK_SECRET")
    if not expected:
        # Fallback: DB-stored secret seeded by migration 009
        secret_setting = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "inbound_webhook_secret")
        )
        setting = secret_setting.scalar_one_or_none()
        if setting and "secret" in setting.value:
            expected = setting.value["secret"]

    if not expected:
        logger.error("INBOUND_WEBHOOK_SECRET unset and no system_settings fallback")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    # constant-time compare so we don't leak info via timing
    if not hmac.compare_digest(x_apex_webhook_secret, expected):
        logger.warning(f"Inbound webhook auth failed from {request.client.host if request.client else '?'}")
        raise HTTPException(status_code=401, detail="Invalid secret")

    # 2. Find or create the company
    company = None
    if payload.company:
        result = await db.execute(
            select(Company).where(Company.name == payload.company.strip())
        )
        company = result.scalar_one_or_none()
        if not company:
            company = Company(
                name=payload.company.strip(),
                industry="Other",
            )
            db.add(company)
            await db.flush()

    # 3. Dedup by email — if this person already exists, log a fresh activity
    # ("they came back to the website") instead of creating a duplicate lead.
    existing_q = await db.execute(
        select(Lead).where(Lead.email == payload.email.lower())
    )
    existing = existing_q.scalar_one_or_none()
    if existing:
        db.add(Activity(
            lead_id=existing.id,
            type="website_form_repeat",
            channel="website",
            description=f"Repeat website form submission ({payload.interest or 'general'}, qty {payload.quantity or '?'})",
            extra_data={
                "interest": payload.interest,
                "quantity": payload.quantity,
                "message": payload.message,
                "source_url": payload.source_url,
            },
        ))
        # Bump stage if they were just a prospect — they're now actively engaging
        if existing.stage == "prospect":
            existing.stage = "engaged"
        await db.commit()
        return {
            "status": "duplicate_logged_as_activity",
            "lead_id": str(existing.id),
            "lead_code": existing.lead_code,
        }

    # 4. Create a one-off batch for this submission so it tracks distinctly
    from app.models.lead import LeadBatch, LeadProfile
    profile_q = await db.execute(
        select(LeadProfile).where(LeadProfile.code == "P-website-inbound")
    )
    inbound_profile = profile_q.scalar_one_or_none()
    inbound_batch = LeadBatch(
        triggered_by="website_inbound",
        target_lead_count=1,
        status="active",
        notes=f"Website submission — {payload.interest or 'general'}, qty {payload.quantity or '?'}",
        profile_id=inbound_profile.id if inbound_profile else None,
    )
    db.add(inbound_batch)
    await db.flush()

    # 5. Parse name into first/last (best-effort; the form has a single field)
    name_parts = payload.name.strip().split(maxsplit=1)
    first_name = name_parts[0] if name_parts else "Unknown"
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # 6. Create the lead — start at 'engaged' stage since they raised their hand
    lead = Lead(
        batch_id=inbound_batch.id,
        company_id=company.id if company else None,
        first_name=first_name,
        last_name=last_name,
        email=payload.email.lower(),
        phone=payload.phone,
        job_title="(from website form)",  # form doesn't ask for title
        country="India",
        source="website_inbound",
        stage="engaged",  # they came to us — start past prospect
        consent_status="opted_in",  # they submitted a contact form, that's consent
        tags=["website_inbound", payload.interest] if payload.interest else ["website_inbound"],
        notes=payload.message or "",
        enrichment_data={
            "interest": payload.interest,
            "quantity": payload.quantity,
            "source_url": payload.source_url,
            "referrer": payload.referrer,
            "submitted_at": str(func.now()),
        },
    )
    db.add(lead)
    await db.flush()

    # 7. Activity log entry so the team can see it on the lead's timeline
    db.add(Activity(
        lead_id=lead.id,
        type="website_form_submission",
        channel="website",
        description=f"Submitted contact form. Interest: {payload.interest or '—'}, qty: {payload.quantity or '—'}.",
        extra_data={
            "interest": payload.interest,
            "quantity": payload.quantity,
            "message": payload.message,
            "source_url": payload.source_url,
            "referrer": payload.referrer,
        },
    ))

    await db.commit()
    await db.refresh(lead)

    logger.info(f"Website lead created: {lead.lead_code} {payload.email} ({payload.company})")
    return {
        "status": "created",
        "lead_id": str(lead.id),
        "lead_code": lead.lead_code,
        "batch_code": inbound_batch.batch_code,
    }


@router.get("", response_model=PaginatedResponse[LeadResponse])
async def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    stage: str | None = None,
    industry: str | None = None,
    seniority: str | None = None,
    department: str | None = None,
    min_score: int | None = None,
    source: str | None = None,
    has_email: bool | None = None,
    search: str | None = None,
    sort: str | None = Query(
        None,
        description="Sort order: score_desc (default), number_asc, number_desc, created_asc, created_desc",
    ),
    db: AsyncSession = Depends(get_db),
):
    query = select(Lead).options(selectinload(Lead.company), selectinload(Lead.batch))
    count_query = select(func.count()).select_from(Lead)

    if stage:
        query = query.where(Lead.stage == stage)
        count_query = count_query.where(Lead.stage == stage)
    if seniority:
        query = query.where(Lead.seniority == seniority)
        count_query = count_query.where(Lead.seniority == seniority)
    if department:
        query = query.where(Lead.department == department)
        count_query = count_query.where(Lead.department == department)
    if min_score is not None:
        query = query.where(Lead.lead_score >= min_score)
        count_query = count_query.where(Lead.lead_score >= min_score)
    if source:
        query = query.where(Lead.source == source)
        count_query = count_query.where(Lead.source == source)
    if has_email is True:
        query = query.where(Lead.email.isnot(None), Lead.email != "")
        count_query = count_query.where(Lead.email.isnot(None), Lead.email != "")
    elif has_email is False:
        query = query.where(or_(Lead.email.is_(None), Lead.email == ""))
        count_query = count_query.where(or_(Lead.email.is_(None), Lead.email == ""))
    if industry:
        query = query.join(Company).where(Company.industry == industry)
        count_query = count_query.join(Company).where(Company.industry == industry)
    if search:
        search_filter = or_(
            Lead.first_name.ilike(f"%{search}%"),
            Lead.last_name.ilike(f"%{search}%"),
            Lead.email.ilike(f"%{search}%"),
            Lead.job_title.ilike(f"%{search}%"),
            Lead.lead_code.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page

    # Sort selection — default remains score-first for backwards compat
    if sort == "number_asc":
        query = query.order_by(Lead.lead_number.asc())
    elif sort == "number_desc":
        query = query.order_by(Lead.lead_number.desc())
    elif sort == "created_asc":
        query = query.order_by(Lead.created_at.asc())
    elif sort == "created_desc":
        query = query.order_by(Lead.created_at.desc())
    else:
        query = query.order_by(Lead.lead_score.desc(), Lead.created_at.desc())

    query = query.offset(offset).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[LeadResponse.model_validate(lead) for lead in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(data: LeadCreate, db: AsyncSession = Depends(get_db)):
    lead = Lead(**data.model_dump())
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    # Load company relationship
    if lead.company_id:
        await db.refresh(lead, ["company"])

    # Log activity
    activity = Activity(
        lead_id=lead.id,
        type="lead_created",
        description=f"Lead {lead.full_name} created from source: {lead.source}",
    )
    db.add(activity)
    await db.commit()

    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Lead).options(selectinload(Lead.company), selectinload(Lead.batch)).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse.model_validate(lead)


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Lead).options(selectinload(Lead.company), selectinload(Lead.batch)).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = data.model_dump(exclude_unset=True)
    old_stage = lead.stage

    for key, value in update_data.items():
        setattr(lead, key, value)

    # Log stage change
    if "stage" in update_data and update_data["stage"] != old_stage:
        activity = Activity(
            lead_id=lead.id,
            type="stage_changed",
            description=f"Stage changed from {old_stage} to {update_data['stage']}",
            extra_data={"old_stage": old_stage, "new_stage": update_data["stage"]},
        )
        db.add(activity)

    await db.commit()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.delete("/{lead_id}")
async def delete_lead(lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.models.activity import Activity
    from app.models.message import Message
    from app.models.sequence import CampaignEnrollment

    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Delete related records to avoid foreign key constraints
    await db.execute(delete(Activity).where(Activity.lead_id == lead_id))
    await db.execute(delete(Message).where(Message.lead_id == lead_id))
    await db.execute(delete(CampaignEnrollment).where(CampaignEnrollment.lead_id == lead_id))
    await db.delete(lead)
    await db.commit()
    return {"message": "Lead deleted", "success": True}


@router.put("/{lead_id}/stage", response_model=LeadResponse)
async def update_lead_stage(
    lead_id: uuid.UUID,
    data: LeadStageUpdate,
    db: AsyncSession = Depends(get_db),
):
    valid_stages = [
        "prospect", "contacted", "engaged", "qualified",
        "proposal_sent", "negotiation", "won", "lost", "nurture",
    ]
    if data.stage not in valid_stages:
        raise HTTPException(
            status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}"
        )

    result = await db.execute(
        select(Lead).options(selectinload(Lead.company), selectinload(Lead.batch)).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    old_stage = lead.stage
    lead.stage = data.stage

    activity = Activity(
        lead_id=lead.id,
        type="stage_changed",
        description=f"Stage changed from {old_stage} to {data.stage}",
        extra_data={"old_stage": old_stage, "new_stage": data.stage},
    )
    db.add(activity)
    await db.commit()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}/timeline")
async def get_lead_timeline(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    # Verify lead exists
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Lead not found")

    activities = await db.execute(
        select(Activity)
        .where(Activity.lead_id == lead_id)
        .order_by(Activity.created_at.desc())
        .limit(100)
    )
    items = activities.scalars().all()
    return [
        {
            "id": str(a.id),
            "type": a.type,
            "channel": a.channel,
            "description": a.description,
            "metadata": a.extra_data,
            "created_at": a.created_at.isoformat(),
        }
        for a in items
    ]


@router.get("/{lead_id}/profile")
async def get_lead_profile(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Unified lead profile: lead + active enrollments + all messages + all activities.
    Used by the lead detail page to render the full outreach story in one fetch."""
    from app.models.message import Message
    from app.models.sequence import Sequence, Campaign, CampaignEnrollment

    # Lead (with company)
    lead_result = await db.execute(
        select(Lead).options(selectinload(Lead.company), selectinload(Lead.batch)).where(Lead.id == lead_id)
    )
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Enrollments with campaign + sequence (active first, then others)
    enr_result = await db.execute(
        select(CampaignEnrollment, Campaign, Sequence)
        .join(Campaign, CampaignEnrollment.campaign_id == Campaign.id)
        .join(Sequence, CampaignEnrollment.sequence_id == Sequence.id)
        .where(CampaignEnrollment.lead_id == lead_id)
        .order_by(CampaignEnrollment.enrolled_at.desc())
    )
    enrollments_out = []
    for enr, camp, seq in enr_result.all():
        steps = seq.steps or []
        total_steps = len(steps)
        current_idx = enr.current_step or 0
        next_step = steps[current_idx] if current_idx < total_steps else None
        enrollments_out.append({
            "id": str(enr.id),
            "campaign_id": str(camp.id),
            "campaign_name": camp.name,
            "sequence_id": str(seq.id),
            "sequence_name": seq.name,
            "status": enr.status,
            "current_step": current_idx,
            "total_steps": total_steps,
            "next_step_at": enr.next_step_at.isoformat() if enr.next_step_at else None,
            "next_step_channel": next_step.get("channel") if next_step else None,
            "next_step_type": next_step.get("type") if next_step else None,
            "last_step_at": enr.last_step_at.isoformat() if enr.last_step_at else None,
            "enrolled_at": enr.enrolled_at.isoformat() if enr.enrolled_at else None,
        })

    # All messages for this lead (most recent first)
    msg_result = await db.execute(
        select(Message)
        .where(Message.lead_id == lead_id)
        .order_by(Message.created_at.desc())
    )
    messages_out = []
    for m in msg_result.scalars().all():
        messages_out.append({
            "id": str(m.id),
            "channel": m.channel,
            "direction": m.direction,
            "subject": m.subject,
            "body": m.body,
            "status": m.status,
            "classification": m.classification,
            "external_id": m.external_id,
            "extra_data": m.extra_data or {},
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    # Non-message activities (stage changes, enrollment events, etc.)
    act_result = await db.execute(
        select(Activity)
        .where(Activity.lead_id == lead_id)
        .order_by(Activity.created_at.desc())
        .limit(200)
    )
    activities_out = []
    for a in act_result.scalars().all():
        activities_out.append({
            "id": str(a.id),
            "type": a.type,
            "channel": a.channel,
            "description": a.description,
            "metadata": a.extra_data,
            "created_at": a.created_at.isoformat(),
        })

    # Lead response
    company = None
    if lead.company:
        company = {
            "id": str(lead.company.id),
            "name": lead.company.name,
            "domain": lead.company.domain,
            "industry": lead.company.industry,
            "employee_count": lead.company.employee_count,
        }

    return {
        "lead": {
            "id": str(lead.id),
            "lead_number": lead.lead_number,
            "lead_code": lead.lead_code,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "full_name": lead.full_name,
            "email": lead.email,
            "phone": lead.phone,
            "whatsapp_number": lead.whatsapp_number,
            "linkedin_url": lead.linkedin_url,
            "job_title": lead.job_title,
            "department": lead.department,
            "seniority": lead.seniority,
            "city": lead.city,
            "state": lead.state,
            "country": lead.country,
            "source": lead.source,
            "lead_score": lead.lead_score,
            "stage": lead.stage,
            "tags": lead.tags,
            "notes": lead.notes,
            "consent_status": lead.consent_status,
            "do_not_contact": lead.do_not_contact,
            "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
            "company": company,
        },
        "enrollments": enrollments_out,
        "messages": messages_out,
        "activities": activities_out,
    }


@router.post("/bulk-import")
async def bulk_import_leads(
    file: UploadFile = File(...),
    batch_label: str = Query("", description="Optional human label for the batch (e.g. 'LinkedIn Sales Nav export 2026-05', 'Trade Show 2026 attendees')"),
    db: AsyncSession = Depends(get_db),
):
    """Import leads from CSV or Excel file.

    Each upload creates a fresh batch tagged with the P-manual-upload
    profile. Leads in the file land in that batch with source='csv_import'
    so they're trackable end-to-end alongside Apollo-discovered batches.

    Expected columns: first_name, last_name, email, phone, job_title,
    department, seniority, company_name, industry, city, state, source
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(
                status_code=400, detail="File must be CSV or Excel (.xlsx/.xls)"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Create a batch for this upload so the leads are tracked alongside
    # autopilot batches. Stamps with P-manual-upload profile if it exists
    # (falls back to NULL profile_id if the profile somehow got deleted).
    from app.models.lead import LeadBatch, LeadProfile
    profile_q = await db.execute(
        select(LeadProfile).where(LeadProfile.code == "P-manual-upload")
    )
    upload_profile = profile_q.scalar_one_or_none()

    batch_notes = f"CSV upload: {file.filename}"
    if batch_label:
        batch_notes = f"{batch_notes} — {batch_label}"

    upload_batch = LeadBatch(
        triggered_by="manual_csv_upload",
        target_lead_count=20,  # not really applicable; kept for schema consistency
        status="active",
        notes=batch_notes,
        profile_id=upload_profile.id if upload_profile else None,
    )
    db.add(upload_batch)
    await db.flush()
    await db.refresh(upload_batch)

    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required = ["first_name", "last_name", "job_title"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing}. Required: {required}",
        )

    created_count = 0
    skipped_count = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            # Handle company — find or create
            company = None
            company_name = row.get("company_name") or row.get("company")
            if pd.notna(company_name) and company_name:
                industry = row.get("industry", "Other")
                if pd.isna(industry):
                    industry = "Other"

                result = await db.execute(
                    select(Company).where(Company.name == str(company_name))
                )
                company = result.scalar_one_or_none()

                if not company:
                    company = Company(
                        name=str(company_name),
                        industry=str(industry),
                        domain=str(row.get("domain", "")) if pd.notna(row.get("domain")) else None,
                    )
                    db.add(company)
                    await db.flush()

            # Check for duplicate by email
            email = row.get("email")
            if pd.notna(email) and email:
                existing = await db.execute(
                    select(Lead).where(Lead.email == str(email))
                )
                if existing.scalar_one_or_none():
                    skipped_count += 1
                    continue

            lead = Lead(
                batch_id=upload_batch.id,
                first_name=str(row["first_name"]),
                last_name=str(row["last_name"]),
                email=str(email) if pd.notna(email) else None,
                phone=str(row.get("phone", "")) if pd.notna(row.get("phone")) else None,
                whatsapp_number=str(row.get("whatsapp", "")) if pd.notna(row.get("whatsapp")) else None,
                linkedin_url=str(row.get("linkedin_url", "")) if pd.notna(row.get("linkedin_url")) else None,
                job_title=str(row["job_title"]),
                department=str(row.get("department", "")) if pd.notna(row.get("department")) else None,
                seniority=str(row.get("seniority", "")) if pd.notna(row.get("seniority")) else None,
                city=str(row.get("city", "")) if pd.notna(row.get("city")) else None,
                state=str(row.get("state", "")) if pd.notna(row.get("state")) else None,
                country=str(row.get("country", "India")) if pd.notna(row.get("country")) else "India",
                source=str(row.get("source", "csv_import")) if pd.notna(row.get("source")) else "csv_import",
                company_id=company.id if company else None,
            )
            db.add(lead)
            created_count += 1

        except Exception as e:
            errors.append({"row": idx + 2, "error": str(e)})

    await db.commit()

    # Refresh to load the auto-generated batch_code from the trigger
    await db.refresh(upload_batch)

    return {
        "success": True,
        "created": created_count,
        "skipped_duplicates": skipped_count,
        "errors": errors[:20],  # Cap error reporting
        "total_rows": len(df),
        "batch": {
            "id": str(upload_batch.id),
            "batch_code": upload_batch.batch_code,
            "notes": upload_batch.notes,
        },
    }
