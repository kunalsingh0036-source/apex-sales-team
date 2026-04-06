"""
Celery tasks for Instagram DM operations.
Handles sending DMs, processing incoming messages, and engagement.
"""

import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.workers.celery_app import celery_app


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.social_tasks.send_instagram_dm")
def send_instagram_dm(message_id: str):
    """Send an Instagram DM."""
    from app.services.social_service import instagram_service
    from app.core.rate_limiter import rate_limiter
    from app.dependencies import create_worker_session
    from app.models.message import Message
    from app.models.lead import Lead
    from app.models.activity import Activity

    async def _send():
        async with create_worker_session()() as db:
            result = await db.execute(
                select(Message).where(Message.id == message_id)
            )
            message = result.scalar_one_or_none()
            if not message or message.status != "queued":
                return {"status": "skipped", "reason": "not queued"}

            lead_result = await db.execute(
                select(Lead).where(Lead.id == message.lead_id)
            )
            lead = lead_result.scalar_one_or_none()
            if not lead:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "lead not found"}

            if lead.do_not_contact:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "do_not_contact"}

            # Get Instagram recipient ID from message metadata or lead handle
            recipient_id = (message.extra_data or {}).get("instagram_recipient_id", "")
            if not recipient_id:
                recipient_id = lead.instagram_handle or ""

            if not recipient_id:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "no instagram recipient ID"}

            can_send = await rate_limiter.can_send("instagram")
            if not can_send:
                return {"status": "rate_limited"}

            try:
                msg_meta = message.extra_data or {}
                msg_type = msg_meta.get("instagram_type", "dm")

                if msg_type == "ice_breaker":
                    ig_result = await instagram_service.send_ice_breaker(
                        recipient_id=recipient_id,
                        question=message.body,
                    )
                elif msg_type == "media":
                    ig_result = await instagram_service.send_media_dm(
                        recipient_id=recipient_id,
                        media_url=msg_meta.get("media_url", ""),
                        media_type=msg_meta.get("media_type", "image"),
                    )
                else:
                    ig_result = await instagram_service.send_dm(
                        recipient_id=recipient_id,
                        message=message.body,
                    )

                if ig_result.get("status") == "sent":
                    message.status = "sent"
                    message.sent_at = datetime.now(timezone.utc)
                    message.external_id = ig_result.get("message_id")
                    await rate_limiter.record_send("instagram")

                    activity = Activity(
                        lead_id=lead.id,
                        type="instagram_dm_sent",
                        channel="instagram",
                        description=f"Instagram DM sent: {message.body[:60]}",
                    )
                    db.add(activity)
                    await db.commit()
                    return {"status": "sent", "type": msg_type}
                else:
                    message.status = "failed"
                    await db.commit()
                    return {"status": "failed", "error": ig_result.get("error")}

            except Exception as e:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "error": str(e)}

    return run_async(_send())


@celery_app.task(name="app.workers.social_tasks.process_instagram_queue")
def process_instagram_queue():
    """Dispatch queued Instagram DMs that are scheduled for now."""
    from app.dependencies import create_worker_session
    from app.models.message import Message

    async def _process():
        async with create_worker_session()() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Message)
                .where(
                    Message.status == "queued",
                    Message.channel == "instagram",
                    Message.scheduled_at <= now,
                )
                .limit(10)
            )
            messages = result.scalars().all()
            dispatched = 0
            for msg in messages:
                send_instagram_dm.delay(str(msg.id))
                dispatched += 1
            return {"dispatched": dispatched}

    return run_async(_process())


@celery_app.task(name="app.workers.social_tasks.process_instagram_webhook")
def process_instagram_webhook(payload: dict):
    """Process an incoming Instagram webhook (message received)."""
    from app.services.outreach_orchestrator import orchestrator
    from app.dependencies import create_worker_session
    from app.models.lead import Lead

    async def _process():
        entries = payload.get("entry", [])
        processed = 0

        async with create_worker_session()() as db:
            for entry in entries:
                messaging = entry.get("messaging", [])
                for event in messaging:
                    sender_id = event.get("sender", {}).get("id", "")
                    msg_data = event.get("message", {})
                    msg_text = msg_data.get("text", "")

                    if not sender_id or not msg_text:
                        continue

                    # Find lead by Instagram handle
                    lead_result = await db.execute(
                        select(Lead).where(Lead.instagram_handle == sender_id)
                    )
                    lead = lead_result.scalar_one_or_none()
                    if not lead:
                        continue

                    await orchestrator.handle_reply(
                        lead_id=lead.id,
                        message_text=msg_text,
                        channel="instagram",
                        db=db,
                    )
                    processed += 1

        return {"processed": processed}

    return run_async(_process())
