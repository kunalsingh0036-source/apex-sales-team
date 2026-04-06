"""
Celery tasks for LinkedIn operations.
Handles connection requests, InMail, and profile engagement.
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


@celery_app.task(name="app.workers.linkedin_tasks.send_linkedin_message")
def send_linkedin_message(message_id: str):
    """Send a LinkedIn message (connection request, DM, or InMail)."""
    from app.services.linkedin_service import linkedin_service
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
            if not lead or not lead.linkedin_url:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "no linkedin_url"}

            if lead.do_not_contact:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "do_not_contact"}

            can_send = await rate_limiter.can_send("linkedin")
            if not can_send:
                return {"status": "rate_limited"}

            try:
                # Determine message type from metadata
                msg_type = (message.extra_data or {}).get("linkedin_type", "connection_request")
                profile_urn = (message.extra_data or {}).get("profile_urn", "")

                if not profile_urn:
                    # Extract from linkedin_url
                    profile_urn = lead.linkedin_url

                if msg_type == "connection_request":
                    result = await linkedin_service.send_connection_request(
                        profile_urn=profile_urn,
                        note=message.body[:300],
                    )
                elif msg_type == "inmail":
                    result = await linkedin_service.send_inmail(
                        recipient_urn=profile_urn,
                        subject=message.subject or "The Apex Human Company",
                        body=message.body,
                    )
                else:
                    result = await linkedin_service.send_message(
                        recipient_urn=profile_urn,
                        body=message.body,
                        subject=message.subject,
                    )

                if result.get("status") == "sent":
                    message.status = "sent"
                    message.sent_at = datetime.now(timezone.utc)
                    await rate_limiter.record_send("linkedin")

                    activity = Activity(
                        lead_id=lead.id,
                        type=f"linkedin_{msg_type}_sent",
                        channel="linkedin",
                        description=f"LinkedIn {msg_type}: {message.body[:60]}",
                    )
                    db.add(activity)
                    await db.commit()
                    return {"status": "sent", "type": msg_type}
                else:
                    message.status = "failed"
                    await db.commit()
                    return {"status": "failed", "error": result.get("error")}

            except Exception as e:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "error": str(e)}

    return run_async(_send())


@celery_app.task(name="app.workers.linkedin_tasks.process_linkedin_queue")
def process_linkedin_queue():
    """Dispatch queued LinkedIn messages that are scheduled for now."""
    from app.dependencies import create_worker_session
    from app.models.message import Message

    async def _process():
        async with create_worker_session()() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Message)
                .where(
                    Message.status == "queued",
                    Message.channel == "linkedin",
                    Message.scheduled_at <= now,
                )
                .limit(10)  # LinkedIn has tight daily limits
            )
            messages = result.scalars().all()
            dispatched = 0
            for msg in messages:
                send_linkedin_message.delay(str(msg.id))
                dispatched += 1
            return {"dispatched": dispatched}

    return run_async(_process())
