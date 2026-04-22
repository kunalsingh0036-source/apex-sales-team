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
                # Hold for human review — don't silently fail
                message.status = "content_review"
                message.extra_data = {
                    **(message.extra_data or {}),
                    "linkedin_status": "pending_approval",
                    "needs_linkedin_url": True,
                    "last_error": "Lead has no linkedin_url on record",
                }
                await db.commit()
                return {"status": "held", "reason": "no linkedin_url"}

            if lead.do_not_contact:
                message.status = "content_review"
                message.extra_data = {
                    **(message.extra_data or {}),
                    "linkedin_status": "pending_approval",
                    "last_error": "Lead is marked do_not_contact",
                }
                await db.commit()
                return {"status": "held", "reason": "do_not_contact"}

            # Contact guard — bypassed for messages inside an active enrollment.
            # Deliberate sequence timing takes precedence over the opportunistic guard.
            from app.services.contact_guard import can_contact, update_last_contacted
            if not message.enrollment_id:
                allowed, reason = await can_contact(lead, db)
                if not allowed:
                    message.status = "content_review"
                    message.extra_data = {
                        **(message.extra_data or {}),
                        "linkedin_status": "pending_approval",
                        "last_error": f"Contact guard: {reason}",
                    }
                    await db.commit()
                    return {"status": "held", "reason": f"contact_guard: {reason}"}

            can_send = await rate_limiter.can_send("linkedin")
            if not can_send:
                return {"status": "rate_limited"}

            try:
                # Determine message type from metadata
                msg_type = (message.extra_data or {}).get("linkedin_type", "connection_request")
                profile_urn = (message.extra_data or {}).get("profile_urn", "") or (message.extra_data or {}).get("profile_url", "")

                if not profile_urn:
                    profile_urn = lead.linkedin_url

                if msg_type == "connection_request":
                    result = await linkedin_service.send_connection_request(
                        profile_urn=profile_urn,
                        note=(message.body or "")[:300],
                    )
                elif msg_type == "inmail":
                    result = await linkedin_service.send_inmail(
                        recipient_urn=profile_urn,
                        subject=message.subject or "The Apex Human Company",
                        body=message.body or "",
                    )
                else:
                    result = await linkedin_service.send_message(
                        recipient_urn=profile_urn,
                        body=message.body or "",
                        subject=message.subject,
                    )

                if result.get("status") == "sent":
                    message.status = "sent"
                    message.sent_at = datetime.now(timezone.utc)
                    external = result.get("invitation_id") or result.get("message_id") or result.get("id")
                    if external:
                        message.external_id = str(external)
                    message.extra_data = {
                        **(message.extra_data or {}),
                        "linkedin_status": "sent",
                        "last_error": None,
                    }
                    await rate_limiter.record_send("linkedin")
                    await update_last_contacted(lead, db)

                    # Drip: schedule the next sequence step based on this real sent_at
                    from app.services.outreach_orchestrator import orchestrator
                    await orchestrator.schedule_next_step_after_send(message, db)

                    activity = Activity(
                        lead_id=lead.id,
                        type=f"linkedin_{msg_type}_sent",
                        channel="linkedin",
                        description=f"LinkedIn {msg_type}: {(message.body or '')[:60]}",
                    )
                    db.add(activity)
                    await db.commit()
                    return {"status": "sent", "type": msg_type}
                else:
                    # Hold for retry instead of marking failed
                    err = result.get("error") or "LinkedIn API returned non-sent status"
                    message.status = "content_review"
                    message.extra_data = {
                        **(message.extra_data or {}),
                        "linkedin_status": "pending_approval",
                        "last_error": f"LinkedIn send failed: {err}",
                    }
                    await db.commit()
                    return {"status": "held", "error": err}

            except Exception as e:
                # Hold for retry instead of marking failed
                message.status = "content_review"
                message.extra_data = {
                    **(message.extra_data or {}),
                    "linkedin_status": "pending_approval",
                    "last_error": f"LinkedIn send exception: {str(e)}",
                }
                await db.commit()
                return {"status": "held", "error": str(e)}

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
