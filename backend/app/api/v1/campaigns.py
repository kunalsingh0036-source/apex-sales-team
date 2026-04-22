import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.models.sequence import Sequence, Campaign, CampaignEnrollment
from app.models.lead import Lead
from app.models.activity import Activity
from app.schemas.sequence import (
    CampaignCreate, CampaignUpdate, CampaignResponse, EnrollmentResponse,
    EnrollLeadsRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.outreach_orchestrator import orchestrator

router = APIRouter()


@router.get("", response_model=PaginatedResponse[CampaignResponse])
async def list_campaigns(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Campaign).options(selectinload(Campaign.sequence))
    count_query = select(func.count()).select_from(Campaign)

    if status:
        query = query.where(Campaign.status == status)
        count_query = count_query.where(Campaign.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(Campaign.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[CampaignResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(data: CampaignCreate, db: AsyncSession = Depends(get_db)):
    # Verify sequence exists
    seq_result = await db.execute(
        select(Sequence).where(Sequence.id == data.sequence_id)
    )
    if not seq_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Sequence not found")

    campaign = Campaign(
        name=data.name,
        sequence_id=data.sequence_id,
        target_filter=data.target_filter,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.sequence))
        .where(Campaign.id == campaign.id)
    )
    campaign = result.scalar_one()
    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.sequence))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.put("/{campaign_id}/status", response_model=CampaignResponse)
async def update_campaign_status(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.sequence))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    valid_statuses = ["draft", "active", "paused", "completed"]
    if data.status and data.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    if data.status == "active" and campaign.status in ("draft", "paused", "completed"):
        if not campaign.started_at:
            campaign.started_at = datetime.now(timezone.utc)
        campaign.completed_at = None  # Clear completed timestamp on reactivation
    elif data.status == "completed":
        campaign.completed_at = datetime.now(timezone.utc)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)

    await db.commit()
    await db.refresh(campaign)
    return CampaignResponse.model_validate(campaign)


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a campaign and all its enrollments."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status == "active":
        raise HTTPException(status_code=400, detail="Cannot delete an active campaign. Pause or complete it first.")

    # Delete enrollments first
    await db.execute(
        select(CampaignEnrollment).where(CampaignEnrollment.campaign_id == campaign_id)
    )
    enrollments = (await db.execute(
        select(CampaignEnrollment).where(CampaignEnrollment.campaign_id == campaign_id)
    )).scalars().all()
    for enrollment in enrollments:
        await db.delete(enrollment)

    await db.delete(campaign)
    await db.commit()
    return {"message": "Campaign deleted", "id": str(campaign_id)}


@router.post("/{campaign_id}/enroll", status_code=201)
async def enroll_leads(
    campaign_id: uuid.UUID,
    data: EnrollLeadsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enroll leads into a campaign."""
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.sequence))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    enrolled = 0
    skipped = 0

    for lead_id in data.lead_ids:
        # Check lead exists
        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalar_one_or_none()
        if not lead:
            skipped += 1
            continue

        # Check not already enrolled
        existing = await db.execute(
            select(CampaignEnrollment).where(
                CampaignEnrollment.campaign_id == campaign_id,
                CampaignEnrollment.lead_id == lead_id,
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        # Check do_not_contact
        if lead.do_not_contact:
            skipped += 1
            continue

        # Contact guard check
        from app.services.contact_guard import can_contact
        allowed, reason = await can_contact(lead, db)
        if not allowed:
            skipped += 1
            continue

        # Calculate first step send time
        from app.core.indian_calendar import next_send_window
        next_send = next_send_window()

        enrollment = CampaignEnrollment(
            campaign_id=campaign_id,
            lead_id=lead_id,
            sequence_id=campaign.sequence_id,
            current_step=0,
            status="active",
            next_step_at=next_send,
        )
        db.add(enrollment)

        # Log activity
        activity = Activity(
            lead_id=lead_id,
            type="campaign_enrolled",
            channel=campaign.sequence.channel if campaign.sequence else None,
            description=f"Enrolled in campaign: {campaign.name}",
        )
        db.add(activity)

        # Update lead stage if still prospect
        if lead.stage == "prospect":
            lead.stage = "contacted"

        enrolled += 1

    # Update campaign total
    campaign.total_leads = (campaign.total_leads or 0) + enrolled

    await db.commit()

    return {
        "success": True,
        "enrolled": enrolled,
        "skipped": skipped,
        "total_in_campaign": campaign.total_leads,
    }


@router.get("/{campaign_id}/enrollments")
async def list_enrollments(
    campaign_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(CampaignEnrollment)
        .where(CampaignEnrollment.campaign_id == campaign_id)
    )
    count_query = select(func.count()).select_from(CampaignEnrollment).where(
        CampaignEnrollment.campaign_id == campaign_id
    )

    if status:
        query = query.where(CampaignEnrollment.status == status)
        count_query = count_query.where(CampaignEnrollment.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(CampaignEnrollment.enrolled_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    # Load lead details for each enrollment
    from app.schemas.sequence import EnrollmentLeadSummary
    enriched = []
    for e in items:
        lead_result = await db.execute(
            select(Lead)
            .options(selectinload(Lead.company))
            .where(Lead.id == e.lead_id)
        )
        lead = lead_result.scalar_one_or_none()

        resp = EnrollmentResponse.model_validate(e)
        if lead:
            resp.lead = EnrollmentLeadSummary(
                id=lead.id,
                lead_code=lead.lead_code,
                full_name=lead.full_name,
                email=lead.email,
                job_title=lead.job_title,
                company_name=lead.company.name if lead.company else None,
                lead_score=lead.lead_score,
                stage=lead.stage,
            )
        enriched.append(resp)

    return PaginatedResponse(
        items=enriched,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("/enrollments/{enrollment_id}/force-advance")
async def force_advance_enrollment(
    enrollment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Bump an enrollment's next_step_at to now and advance it immediately.
    Useful when the team wants to push a lead forward without waiting for the scheduled delay,
    or for QA/testing to verify the next step in the sequence.
    """
    result = await db.execute(
        select(CampaignEnrollment).where(CampaignEnrollment.id == enrollment_id)
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if enrollment.status != "active":
        raise HTTPException(status_code=400, detail=f"Enrollment is {enrollment.status}, cannot advance")

    # Bump next_step_at to now so advance_enrollment will process it
    enrollment.next_step_at = datetime.now(timezone.utc)
    await db.flush()

    prev_step = enrollment.current_step
    advanced = await orchestrator.advance_enrollment(enrollment, db)
    await db.commit()
    return {
        "status": "advanced" if advanced else "skipped",
        "enrollment_id": str(enrollment.id),
        "previous_step": prev_step,
        "current_step": enrollment.current_step,
        "next_step_at": enrollment.next_step_at.isoformat() if enrollment.next_step_at else None,
    }
