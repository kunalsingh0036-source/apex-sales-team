"""
Automation / Autopilot API endpoints.
Provides controls for the autonomous lead-to-campaign pipeline.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.user import SystemSetting
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
