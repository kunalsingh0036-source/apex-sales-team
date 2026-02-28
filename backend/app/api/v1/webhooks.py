"""
Webhook endpoints for receiving inbound messages from external services.
Handles WhatsApp and Instagram webhook verification and message processing.
"""

from fastapi import APIRouter, Request, Query, HTTPException
from app.config import get_settings

router = APIRouter()


# ─── WhatsApp Webhook ──────────────────────────────────────────────

@router.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp webhook verification (GET). Meta sends this to verify endpoint."""
    settings = get_settings()
    verify_token = settings.api_secret_key  # Use API secret as verify token

    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    WhatsApp webhook receiver (POST).
    Receives inbound messages and status updates from WhatsApp Business API.
    """
    payload = await request.json()

    # Dispatch to Celery for async processing
    from app.workers.whatsapp_tasks import process_whatsapp_webhook
    process_whatsapp_webhook.delay(payload)

    return {"status": "received"}


# ─── Instagram Webhook ──────────────────────────────────────────────

@router.get("/instagram")
async def instagram_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Instagram webhook verification (GET)."""
    settings = get_settings()
    verify_token = settings.api_secret_key

    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/instagram")
async def instagram_webhook(request: Request):
    """
    Instagram webhook receiver (POST).
    Receives inbound DMs from Instagram Messaging API.
    """
    payload = await request.json()

    from app.workers.social_tasks import process_instagram_webhook
    process_instagram_webhook.delay(payload)

    return {"status": "received"}
