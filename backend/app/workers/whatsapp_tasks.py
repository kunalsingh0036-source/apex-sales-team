"""
Celery tasks for WhatsApp Business API operations.
Handles template messages, session messages, and webhook processing.
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


@celery_app.task(name="app.workers.whatsapp_tasks.send_whatsapp_message")
def send_whatsapp_message(message_id: str):
    """Send a WhatsApp message (template or session)."""
    from app.services.whatsapp_service import whatsapp_service
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
            if not lead or not lead.phone:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "no phone number"}

            if lead.do_not_contact:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "do_not_contact"}

            can_send = await rate_limiter.can_send("whatsapp")
            if not can_send:
                return {"status": "rate_limited"}

            try:
                msg_meta = message.extra_data or {}
                template_name = msg_meta.get("whatsapp_template")

                if template_name:
                    # Send as template message (for cold outreach)
                    components = msg_meta.get("template_components", [])
                    wa_result = await whatsapp_service.send_template_message(
                        phone=lead.phone,
                        template_name=template_name,
                        components=components,
                    )
                else:
                    # Send as text message (within 24hr session window)
                    wa_result = await whatsapp_service.send_text_message(
                        phone=lead.phone,
                        body=message.body,
                    )

                if wa_result.get("status") == "sent":
                    message.status = "sent"
                    message.sent_at = datetime.now(timezone.utc)
                    message.external_id = wa_result.get("message_id")
                    await rate_limiter.record_send("whatsapp")

                    activity = Activity(
                        lead_id=lead.id,
                        type="whatsapp_sent",
                        channel="whatsapp",
                        description=f"WhatsApp sent: {message.body[:60]}",
                    )
                    db.add(activity)
                    await db.commit()
                    return {"status": "sent", "wa_id": wa_result.get("message_id")}
                else:
                    message.status = "failed"
                    await db.commit()
                    return {"status": "failed", "error": wa_result.get("error")}

            except Exception as e:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "error": str(e)}

    return run_async(_send())


@celery_app.task(name="app.workers.whatsapp_tasks.process_whatsapp_queue")
def process_whatsapp_queue():
    """Dispatch queued WhatsApp messages that are scheduled for now."""
    from app.dependencies import create_worker_session
    from app.models.message import Message

    async def _process():
        async with create_worker_session()() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Message)
                .where(
                    Message.status == "queued",
                    Message.channel == "whatsapp",
                    Message.scheduled_at <= now,
                )
                .limit(20)
            )
            messages = result.scalars().all()
            dispatched = 0
            for msg in messages:
                send_whatsapp_message.delay(str(msg.id))
                dispatched += 1
            return {"dispatched": dispatched}

    return run_async(_process())


@celery_app.task(name="app.workers.whatsapp_tasks.process_whatsapp_webhook")
def process_whatsapp_webhook(payload: dict):
    """Process an incoming WhatsApp webhook (message received)."""
    from app.services.outreach_orchestrator import orchestrator
    from app.dependencies import create_worker_session
    from app.models.lead import Lead

    async def _process():
        entries = payload.get("entry", [])
        processed = 0

        async with create_worker_session()() as db:
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])

                    for msg in messages:
                        sender_phone = msg.get("from", "")
                        msg_body = ""

                        if msg.get("type") == "text":
                            msg_body = msg.get("text", {}).get("body", "")
                        elif msg.get("type") == "button":
                            msg_body = msg.get("button", {}).get("text", "")

                        if not sender_phone or not msg_body:
                            continue

                        # Find lead by phone
                        lead_result = await db.execute(
                            select(Lead).where(Lead.phone == sender_phone)
                        )
                        lead = lead_result.scalar_one_or_none()
                        if not lead:
                            # Try with +prefix
                            lead_result = await db.execute(
                                select(Lead).where(Lead.phone.contains(sender_phone[-10:]))
                            )
                            lead = lead_result.scalar_one_or_none()

                        if not lead:
                            continue

                        await orchestrator.handle_reply(
                            lead_id=lead.id,
                            message_text=msg_body,
                            channel="whatsapp",
                            db=db,
                        )
                        processed += 1

        return {"processed": processed}

    return run_async(_process())
