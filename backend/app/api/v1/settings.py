"""
System settings API endpoints.
Manages brand voice, rate limits, API config, and festive calendar.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.models.user import SystemSetting
from app.config import get_settings
from app.core.rate_limiter import rate_limiter
from app.core.indian_calendar import get_active_seasons, FESTIVE_SEASONS
from app.core.brand_voice import BRAND_VOICE_SYSTEM_PROMPT, INDUSTRY_VOICE_OVERRIDES

router = APIRouter()


class SettingUpdate(BaseModel):
    value: dict


@router.get("")
async def list_settings(db: AsyncSession = Depends(get_db)):
    """Get all system settings."""
    result = await db.execute(select(SystemSetting))
    items = result.scalars().all()
    return {item.key: item.value for item in items}


@router.get("/{key}")
async def get_setting(key: str, db: AsyncSession = Depends(get_db)):
    """Get a specific system setting."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    item = result.scalar_one_or_none()
    if not item:
        return {"key": key, "value": None}
    return {"key": item.key, "value": item.value}


@router.put("/{key}")
async def update_setting(key: str, data: SettingUpdate, db: AsyncSession = Depends(get_db)):
    """Update or create a system setting."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    item = result.scalar_one_or_none()
    if item:
        item.value = data.value
    else:
        item = SystemSetting(key=key, value=data.value)
        db.add(item)
    await db.commit()
    return {"key": key, "value": data.value}


@router.get("/info/config")
async def get_config_info():
    """Get current configuration (non-sensitive)."""
    settings = get_settings()
    return {
        "sender_email": settings.gmail_sender_email,
        "rate_limits": {
            "email": settings.email_daily_limit,
            "linkedin": settings.linkedin_daily_limit,
            "whatsapp": settings.whatsapp_daily_limit,
            "instagram": settings.instagram_daily_limit,
        },
        "integrations": {
            "anthropic": bool(settings.anthropic_api_key),
            "gmail": bool(settings.gmail_client_id),
            "linkedin": bool(settings.linkedin_access_token),
            "whatsapp": bool(settings.whatsapp_access_token),
            "instagram": bool(settings.meta_access_token),
            "gmb": bool(settings.gmb_access_token),
            "apollo": bool(settings.apollo_api_key),
            "hunter": bool(settings.hunter_api_key),
            "proxycurl": bool(settings.proxycurl_api_key),
        },
    }


@router.get("/info/rate-limits")
async def get_rate_limits():
    """Get remaining rate limits for all channels."""
    remaining = await rate_limiter.get_all_remaining()
    return remaining


@router.get("/info/brand-voice")
async def get_brand_voice():
    """Get the current brand voice configuration."""
    return {
        "system_prompt": BRAND_VOICE_SYSTEM_PROMPT[:500] + "...",
        "industry_overrides": list(INDUSTRY_VOICE_OVERRIDES.keys()),
        "traits": [
            "Authoritative", "Transparent", "Confident", "Warm",
            "Factory-direct", "No middlemen", "220 GSM Supima cotton",
        ],
    }


@router.get("/info/seasons")
async def get_seasons():
    """Get active and upcoming festive seasons."""
    active = get_active_seasons()
    return {
        "active_seasons": [
            {"name": s["name"], "type": s["type"]}
            for s in active
        ],
        "all_seasons": list(FESTIVE_SEASONS.keys()),
    }
