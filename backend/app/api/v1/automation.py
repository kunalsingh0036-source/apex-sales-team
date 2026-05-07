"""
Automation / Autopilot API endpoints.
Provides controls for the autonomous lead-to-campaign pipeline.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.user import SystemSetting
from app.models.lead import Lead, LeadBatch, LeadProfile
from app.models.sequence import CampaignEnrollment
from app.models.message import Message
from app.services.automation_engine import automation_engine

router = APIRouter()


# ─── Request Schemas ──────────────────────────────────────────

class AutopilotToggle(BaseModel):
    enabled: bool


class ICPUpdate(BaseModel):
    job_titles: list[str]
    industries: list[str]
    locations: list[str] = ["India"]
    company_sizes: list[str] = ["201-500", "501-1000", "1001-5000", "5001-10000"]
    keywords: list[str] = []
    max_results: int = 50


class AutopilotSettingsUpdate(BaseModel):
    campaign_day: int = 0  # 0=Monday ... 6=Sunday
    aggressiveness: str = "normal"  # low, normal, high


# ─── Endpoints ────────────────────────────────────────────────

@router.get("/status")
async def autopilot_status(db: AsyncSession = Depends(get_db)):
    """Get full autopilot state and metrics."""
    return await automation_engine.get_status(db)


@router.put("/toggle")
async def autopilot_toggle(body: AutopilotToggle, db: AsyncSession = Depends(get_db)):
    """Enable or disable autopilot."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "autopilot_enabled")
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = {"enabled": body.enabled}
    else:
        db.add(SystemSetting(key="autopilot_enabled", value={"enabled": body.enabled}))
    await db.commit()
    return {"enabled": body.enabled, "message": f"Autopilot {'enabled' if body.enabled else 'disabled'}"}


@router.get("/icp")
async def get_icp(db: AsyncSession = Depends(get_db)):
    """Get the current Ideal Customer Profile."""
    return await automation_engine.get_icp(db)


@router.put("/icp")
async def update_icp(body: ICPUpdate, db: AsyncSession = Depends(get_db)):
    """Update the Ideal Customer Profile."""
    value = body.model_dump()
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "autopilot_icp")
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(SystemSetting(key="autopilot_icp", value=value))
    await db.commit()
    return {"message": "ICP updated", "icp": value}


@router.get("/history")
async def autopilot_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get autopilot run history."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "autopilot_history")
    )
    setting = result.scalar_one_or_none()
    if not setting:
        return {"runs": []}
    runs = setting.value.get("runs", [])
    return {"runs": runs[-limit:]}


@router.post("/trigger/{stage}")
async def trigger_stage(stage: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger an autopilot stage."""
    valid_stages = ["discover", "enrich", "sequences", "campaigns", "advance", "full"]
    if stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}")

    from app.workers.automation_tasks import autopilot_trigger
    task = autopilot_trigger.delay(stage)
    return {"task_id": task.id, "stage": stage, "message": f"Triggered {stage}"}


@router.get("/settings")
async def get_autopilot_settings(db: AsyncSession = Depends(get_db)):
    """Get autopilot settings."""
    return await automation_engine.get_settings(db)


@router.put("/settings")
async def update_autopilot_settings(
    body: AutopilotSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update autopilot settings."""
    if body.campaign_day not in range(7):
        raise HTTPException(status_code=400, detail="campaign_day must be 0-6 (Monday-Sunday)")
    if body.aggressiveness not in ("low", "normal", "high"):
        raise HTTPException(status_code=400, detail="aggressiveness must be low, normal, or high")

    value = body.model_dump()
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "autopilot_settings")
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(SystemSetting(key="autopilot_settings", value=value))
    await db.commit()
    return {"message": "Settings updated", "settings": value}


# ─── Batch endpoints ──────────────────────────────────────────

@router.get("/batches")
async def list_batches(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all batches with progress stats. Newest first.

    For each batch returns: lead count, how many have been enrolled,
    sent, replied, and the active-enrollment count (the number that
    still need to finish before the batch is considered complete)."""
    result = await db.execute(
        select(LeadBatch).order_by(LeadBatch.batch_number.desc()).limit(limit)
    )
    batches = result.scalars().all()

    out = []
    for b in batches:
        # Lead counts in this batch
        lead_q = await db.execute(
            select(func.count(Lead.id)).where(Lead.batch_id == b.id)
        )
        total_leads = lead_q.scalar() or 0

        # Active enrollments (drives the batch_complete check)
        active_enr_q = await db.execute(
            select(func.count(CampaignEnrollment.id))
            .join(Lead, CampaignEnrollment.lead_id == Lead.id)
            .where(
                Lead.batch_id == b.id,
                CampaignEnrollment.status == "active",
            )
        )
        active_enrollments = active_enr_q.scalar() or 0

        # Replied count
        replied_q = await db.execute(
            select(func.count(CampaignEnrollment.id))
            .join(Lead, CampaignEnrollment.lead_id == Lead.id)
            .where(
                Lead.batch_id == b.id,
                CampaignEnrollment.status == "replied",
            )
        )
        replied = replied_q.scalar() or 0

        # Messages sent across the batch
        sent_q = await db.execute(
            select(func.count(Message.id))
            .join(Lead, Message.lead_id == Lead.id)
            .where(
                Lead.batch_id == b.id,
                Message.status == "sent",
                Message.direction == "outbound",
            )
        )
        sent = sent_q.scalar() or 0

        # Profile summary for the batch (one extra query per batch — fine
        # at <100 batches; revisit if this list ever returns thousands)
        profile_summary = None
        if b.profile_id:
            pq = await db.execute(
                select(LeadProfile.code, LeadProfile.name).where(LeadProfile.id == b.profile_id)
            )
            row = pq.first()
            if row:
                profile_summary = {"code": row[0], "name": row[1]}

        out.append({
            "id": str(b.id),
            "batch_code": b.batch_code,
            "batch_number": b.batch_number,
            "status": b.status,
            "triggered_by": b.triggered_by,
            "target_lead_count": b.target_lead_count,
            "actual_lead_count": total_leads,
            "active_enrollments": active_enrollments,
            "replied": replied,
            "messages_sent": sent,
            "profile": profile_summary,
            "completed_at": b.completed_at.isoformat() if b.completed_at else None,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })

    return {"batches": out, "total": len(out)}


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: str, db: AsyncSession = Depends(get_db)):
    """Get one batch with its lead summaries."""
    import uuid as _uuid
    try:
        bid = _uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid batch id")
    result = await db.execute(select(LeadBatch).where(LeadBatch.id == bid))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    leads_q = await db.execute(
        select(Lead).where(Lead.batch_id == batch.id).order_by(Lead.lead_number.asc())
    )
    leads = leads_q.scalars().all()
    return {
        "id": str(batch.id),
        "batch_code": batch.batch_code,
        "batch_number": batch.batch_number,
        "status": batch.status,
        "triggered_by": batch.triggered_by,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "leads": [
            {
                "id": str(l.id),
                "lead_code": l.lead_code,
                "full_name": l.full_name,
                "email": l.email,
                "job_title": l.job_title,
                "lead_score": l.lead_score,
                "stage": l.stage,
            }
            for l in leads
        ],
    }


class GenerateBatchRequest(BaseModel):
    profile_id: Optional[str] = None  # If omitted, round-robin picks the LRU active profile


@router.post("/batches/generate")
async def generate_next_batch(
    body: Optional[GenerateBatchRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger the next batch (skips autopilot-enabled gate so the
    team can generate a batch even when autopilot is paused).

    Body is optional. If provided, `profile_id` overrides round-robin and
    forces this batch to use the named profile. Otherwise the active profile
    with the oldest last_used_at fires next."""
    import uuid as _uuid
    pid = None
    if body and body.profile_id:
        try:
            pid = _uuid.UUID(body.profile_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid profile_id")

    result = await automation_engine.run_full_cycle(
        db, triggered_by="manual", force=True, profile_id=pid
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ─── Profile endpoints ────────────────────────────────────────

class ProfileCreate(BaseModel):
    code: str
    name: str
    description: str = ""
    search_params: dict = {}
    is_active: bool = True
    rotation_priority: int = 100


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    search_params: Optional[dict] = None
    is_active: Optional[bool] = None
    rotation_priority: Optional[int] = None


@router.get("/profiles")
async def list_profiles(db: AsyncSession = Depends(get_db)):
    """List all lead profiles (segments). Active profiles enter the
    round-robin rotation; inactive ones don't but are kept for history."""
    result = await db.execute(
        select(LeadProfile).order_by(
            LeadProfile.is_active.desc(),
            LeadProfile.rotation_priority.asc(),
        )
    )
    profiles = result.scalars().all()

    out = []
    for p in profiles:
        # Aggregate stats: count batches, leads, sent, replied per profile
        batch_count_q = await db.execute(
            select(func.count(LeadBatch.id)).where(LeadBatch.profile_id == p.id)
        )
        batch_count = batch_count_q.scalar() or 0

        lead_count_q = await db.execute(
            select(func.count(Lead.id))
            .join(LeadBatch, Lead.batch_id == LeadBatch.id)
            .where(LeadBatch.profile_id == p.id)
        )
        lead_count = lead_count_q.scalar() or 0

        replied_q = await db.execute(
            select(func.count(CampaignEnrollment.id))
            .join(Lead, CampaignEnrollment.lead_id == Lead.id)
            .join(LeadBatch, Lead.batch_id == LeadBatch.id)
            .where(LeadBatch.profile_id == p.id, CampaignEnrollment.status == "replied")
        )
        replied = replied_q.scalar() or 0

        sent_q = await db.execute(
            select(func.count(Message.id))
            .join(Lead, Message.lead_id == Lead.id)
            .join(LeadBatch, Lead.batch_id == LeadBatch.id)
            .where(
                LeadBatch.profile_id == p.id,
                Message.direction == "outbound",
                Message.status == "sent",
            )
        )
        sent = sent_q.scalar() or 0

        out.append({
            "id": str(p.id),
            "code": p.code,
            "name": p.name,
            "description": p.description,
            "search_params": p.search_params,
            "is_active": p.is_active,
            "rotation_priority": p.rotation_priority,
            "last_used_at": p.last_used_at.isoformat() if p.last_used_at else None,
            "stats": {
                "batches_run": batch_count,
                "leads_generated": lead_count,
                "messages_sent": sent,
                "replied": replied,
                "response_rate": round(replied / sent * 100, 1) if sent > 0 else None,
            },
        })

    return {"profiles": out, "total": len(out)}


@router.post("/profiles", status_code=201)
async def create_profile(body: ProfileCreate, db: AsyncSession = Depends(get_db)):
    """Create a new lead profile. The `code` must be unique."""
    if not body.code or not body.name:
        raise HTTPException(status_code=400, detail="code and name are required")

    existing = await db.execute(select(LeadProfile).where(LeadProfile.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Profile with code '{body.code}' already exists")

    p = LeadProfile(
        code=body.code,
        name=body.name,
        description=body.description,
        search_params=body.search_params,
        is_active=body.is_active,
        rotation_priority=body.rotation_priority,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {
        "id": str(p.id),
        "code": p.code,
        "name": p.name,
        "is_active": p.is_active,
    }


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: str,
    body: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a profile in-place. Code is immutable; everything else is editable."""
    import uuid as _uuid
    try:
        pid = _uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile id")

    result = await db.execute(select(LeadProfile).where(LeadProfile.id == pid))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.search_params is not None:
        p.search_params = body.search_params
    if body.is_active is not None:
        p.is_active = body.is_active
    if body.rotation_priority is not None:
        p.rotation_priority = body.rotation_priority

    await db.commit()
    return {"status": "updated", "id": str(p.id), "code": p.code}


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a profile. Refuses if any batches reference it — deactivate
    the profile instead to remove it from rotation while keeping history."""
    import uuid as _uuid
    try:
        pid = _uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile id")

    result = await db.execute(select(LeadProfile).where(LeadProfile.id == pid))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    batch_count_q = await db.execute(
        select(func.count(LeadBatch.id)).where(LeadBatch.profile_id == pid)
    )
    if (batch_count_q.scalar() or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete profile with existing batches. Mark it inactive instead.",
        )

    await db.delete(p)
    await db.commit()
    return {"status": "deleted", "id": str(pid)}


@router.post("/batches/check-trigger")
async def check_batch_trigger(db: AsyncSession = Depends(get_db)):
    """Run the daily auto-trigger logic on demand. Used by the beat job
    and exposed here for manual debugging / forcing a re-evaluation."""
    return await automation_engine.maybe_run_next_batch(db)


@router.post("/batches/{batch_id}/enroll-orphans")
async def enroll_orphan_leads(batch_id: str, db: AsyncSession = Depends(get_db)):
    """Retro-enroll leads in a batch that were discovered + enriched but
    never made it into a campaign because the cron-driven create_campaigns
    silently failed. Calls create_campaigns scoped to this batch only."""
    import uuid as _uuid
    try:
        bid = _uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid batch id")

    from app.models.lead import LeadBatch as _LeadBatch
    result = await db.execute(select(_LeadBatch).where(_LeadBatch.id == bid))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Reset batch status to active so completion logic re-evaluates after enrollment
    batch.status = "active"
    batch.completed_at = None
    await automation_engine.ensure_sequences(db)
    res = await automation_engine.create_campaigns(db, batch=batch)
    return {
        "batch_code": batch.batch_code,
        "result": res,
    }


@router.post("/batches/repair-all-orphans")
async def repair_all_orphan_batches(db: AsyncSession = Depends(get_db)):
    """One-shot recovery: find every active batch with leads-but-no-enrollments
    and run create_campaigns on each. Used to fix the B-0007..B-0012 mess
    caused by the silent campaigns failure in cron context."""
    from app.models.lead import LeadBatch as _LeadBatch

    result = await db.execute(
        select(_LeadBatch).order_by(_LeadBatch.batch_number.asc())
    )
    batches = result.scalars().all()

    summaries = []
    for batch in batches:
        lead_count_q = await db.execute(
            select(func.count(Lead.id)).where(Lead.batch_id == batch.id)
        )
        lead_count = lead_count_q.scalar() or 0
        enr_count_q = await db.execute(
            select(func.count(CampaignEnrollment.id))
            .join(Lead, CampaignEnrollment.lead_id == Lead.id)
            .where(Lead.batch_id == batch.id)
        )
        enr_count = enr_count_q.scalar() or 0

        if lead_count > 0 and enr_count == 0 and batch.triggered_by != "backfill":
            # Reactivate so the workflow treats it as in-progress
            batch.status = "active"
            batch.completed_at = None
            res = await automation_engine.create_campaigns(db, batch=batch)
            summaries.append({
                "batch_code": batch.batch_code,
                "lead_count": lead_count,
                "result": res,
            })

    return {"repaired": summaries, "count": len(summaries)}
