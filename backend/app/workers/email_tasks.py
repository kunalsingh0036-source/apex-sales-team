"""
Celery tasks for email operations.
Handles scheduled sending, reply checking, and sequence advancement.
"""

import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.workers.celery_app import celery_app


def run_async(coro):
    """Helper to run async functions from sync Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.email_tasks.send_email")
def send_email(message_id: str):
    """Send a single queued email message."""
    from app.services.email_service import gmail_service
    from app.core.rate_limiter import rate_limiter
    from app.dependencies import async_session
    from app.models.message import Message
    from app.models.lead import Lead
    from app.models.activity import Activity

    async def _send():
        async with async_session() as db:
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
            if not lead or not lead.email:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "no email"}

            if lead.do_not_contact:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "reason": "do_not_contact"}

            can_send = await rate_limiter.can_send("email")
            if not can_send:
                return {"status": "rate_limited"}

            try:
                gmail_result = await gmail_service.send_email(
                    to=lead.email,
                    subject=message.subject or "The Apex Human Company",
                    body=message.body,
                )

                message.status = "sent"
                message.sent_at = datetime.now(timezone.utc)
                message.external_id = gmail_result.get("message_id")
                await rate_limiter.record_send("email")

                activity = Activity(
                    lead_id=lead.id,
                    type="email_sent",
                    channel="email",
                    description=f"Email sent: {message.subject or message.body[:60]}",
                )
                db.add(activity)
                await db.commit()
                return {"status": "sent", "gmail_id": gmail_result.get("message_id")}

            except Exception as e:
                message.status = "failed"
                await db.commit()
                return {"status": "failed", "error": str(e)}

    return run_async(_send())


@celery_app.task(name="app.workers.email_tasks.process_scheduled_sends")
def process_scheduled_sends():
    """Dispatch queued email messages that are scheduled for now."""
    from app.dependencies import async_session
    from app.models.message import Message

    async def _process():
        async with async_session() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Message)
                .where(
                    Message.status == "queued",
                    Message.channel == "email",
                    Message.scheduled_at <= now,
                )
                .limit(20)
            )
            messages = result.scalars().all()
            dispatched = 0
            for msg in messages:
                send_email.delay(str(msg.id))
                dispatched += 1
            return {"dispatched": dispatched}

    return run_async(_process())


@celery_app.task(name="app.workers.email_tasks.check_replies")
def check_replies():
    """Periodic task: check inbox for new replies and classify them."""
    from app.services.email_service import gmail_service
    from app.services.outreach_orchestrator import orchestrator
    from app.dependencies import async_session
    from app.models.message import Message
    from app.models.lead import Lead

    async def _check():
        async with async_session() as db:
            replies = await gmail_service.check_replies()
            processed = 0

            for reply in replies:
                sender_email = reply.get("from", "")
                if "<" in sender_email:
                    sender_email = sender_email.split("<")[1].rstrip(">")

                lead_result = await db.execute(
                    select(Lead).where(Lead.email == sender_email)
                )
                lead = lead_result.scalar_one_or_none()
                if not lead:
                    continue

                # Skip if already processed
                existing = await db.execute(
                    select(Message).where(
                        Message.external_id == reply["message_id"],
                        Message.direction == "inbound",
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                await orchestrator.handle_reply(
                    lead_id=lead.id,
                    message_text=reply["body"],
                    channel="email",
                    db=db,
                )
                processed += 1

            return {"checked": len(replies), "processed": processed}

    return run_async(_check())


@celery_app.task(name="app.workers.email_tasks.advance_sequences")
def advance_sequences():
    """Advance campaign enrollments that are due for their next step."""
    from app.services.outreach_orchestrator import orchestrator
    from app.dependencies import async_session
    from app.models.sequence import CampaignEnrollment

    async def _advance():
        async with async_session() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(CampaignEnrollment)
                .where(
                    CampaignEnrollment.status == "active",
                    CampaignEnrollment.next_step_at <= now,
                )
                .limit(50)
            )
            enrollments = result.scalars().all()
            advanced = 0

            for enrollment in enrollments:
                try:
                    queued = await orchestrator.advance_enrollment(enrollment, db)
                    if queued:
                        advanced += 1
                except Exception as e:
                    print(f"Error advancing enrollment {enrollment.id}: {e}")

            await db.commit()
            return {"checked": len(enrollments), "advanced": advanced}

    return run_async(_advance())
