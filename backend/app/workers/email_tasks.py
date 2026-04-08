"""
Celery tasks for email operations.
Handles scheduled sending, reply checking, and sequence advancement.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from sqlalchemy import select
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

GENERIC_PATTERNS = [
    r"reaching out about a potential partnership",
    r"Regarding .+ partnership",
    r"reaching out about a potential collaboration",
    r"I wanted to reach out",
    r"I hope this email finds you well",
    r"just checking in",
    r"touching base",
]
GENERIC_RE = re.compile("|".join(GENERIC_PATTERNS), re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"\{\{.+?\}\}|\[Your [Nn]ame\]|\[Contact\]|\[Company\]|\[Phone\]|\[Email\]|\[Name\]|\[Title\]")
MIN_BODY_LENGTH = 100


def _content_passes_quality(subject: str | None, body: str) -> tuple[bool, str]:
    """Check if message content is good enough to send.

    No generic templates, no placeholders, no bot-like content.
    If it doesn't pass, it stays in content_review for a human.
    Returns (passes, reason).
    """
    if not body or len(body.strip()) < MIN_BODY_LENGTH:
        return False, f"body too short ({len(body.strip())} chars, min {MIN_BODY_LENGTH})"
    if GENERIC_RE.search(body):
        return False, "body matches generic pattern"
    if subject and GENERIC_RE.search(subject):
        return False, "subject matches generic pattern"
    if PLACEHOLDER_RE.search(body):
        return False, "body contains unresolved placeholders"
    if subject and PLACEHOLDER_RE.search(subject):
        return False, "subject contains unresolved placeholders"
    return True, ""


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
            if not lead or not lead.email:
                message.status = "content_review"
                message.extra_data = {**message.extra_data, "last_error": "Lead has no email address"}
                await db.commit()
                return {"status": "held", "reason": "no email"}

            if lead.do_not_contact:
                message.status = "content_review"
                message.extra_data = {**message.extra_data, "last_error": "Lead is marked do not contact"}
                await db.commit()
                return {"status": "held", "reason": "do_not_contact"}

            # Contact guard check
            from app.services.contact_guard import can_contact
            allowed, reason = await can_contact(lead, db)
            if not allowed:
                message.status = "content_review"
                message.extra_data = {**message.extra_data, "last_error": f"Contact guard: {reason}"}
                await db.commit()
                logger.info(f"Contact guard blocked {lead.email}: {reason}")
                return {"status": "held", "reason": f"contact_guard: {reason}"}

            # Content quality gate — reject generic/placeholder messages
            passes, reason = _content_passes_quality(message.subject, message.body)
            if not passes:
                message.status = "content_review"
                await db.commit()
                logger.warning(
                    f"Message {message_id} held for content review: {reason}"
                )
                return {"status": "content_review", "reason": reason}

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

                from app.services.contact_guard import update_last_contacted
                await update_last_contacted(lead, db)

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
                # Keep in content_review so user can retry
                message.status = "content_review"
                message.extra_data = {**message.extra_data, "last_error": f"Send failed: {str(e)}"}
                await db.commit()
                return {"status": "held", "error": str(e)}

    return run_async(_send())


@celery_app.task(name="app.workers.email_tasks.process_scheduled_sends")
def process_scheduled_sends():
    """Dispatch queued email messages that are scheduled for now."""
    from app.dependencies import create_worker_session
    from app.models.message import Message

    async def _process():
        async with create_worker_session()() as db:
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
    from app.dependencies import create_worker_session
    from app.models.message import Message
    from app.models.lead import Lead

    async def _check():
        async with create_worker_session()() as db:
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


@celery_app.task(name="app.workers.email_tasks.sync_gmail_sent")
def sync_gmail_sent():
    """Sync Gmail sent folder — detect externally sent emails and track contacts."""
    from app.services.email_service import gmail_service
    from app.dependencies import create_worker_session
    from app.models.message import Message
    from app.models.lead import Lead
    from app.models.activity import Activity
    from app.models.user import SystemSetting
    from datetime import timedelta
    from email.utils import parsedate_to_datetime

    async def _sync():
        async with create_worker_session()() as db:
            # 1. Read last sync timestamp from SystemSetting
            setting_result = await db.execute(
                select(SystemSetting).where(SystemSetting.key == "gmail_sent_last_sync")
            )
            setting = setting_result.scalar_one_or_none()

            if setting and setting.value.get("timestamp"):
                after_epoch = str(int(setting.value["timestamp"]))
            else:
                # Default to 30 days ago
                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                after_epoch = str(int(thirty_days_ago.timestamp()))

            # 2. Fetch sent messages from Gmail
            sent_messages = await gmail_service.get_sent_messages(after_timestamp=after_epoch)

            synced = 0
            skipped = 0
            new_leads_created = 0

            for msg in sent_messages:
                # 3a. Skip if already tracked
                existing = await db.execute(
                    select(Message).where(
                        Message.external_id == msg["message_id"],
                        Message.direction == "outbound",
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                recipient_email = msg["to"].lower().strip()
                if not recipient_email:
                    skipped += 1
                    continue

                # Parse gmail date
                try:
                    gmail_date = parsedate_to_datetime(msg["date"])
                    if gmail_date.tzinfo is None:
                        gmail_date = gmail_date.replace(tzinfo=timezone.utc)
                except Exception:
                    gmail_date = datetime.now(timezone.utc)

                # 3c. Look up existing lead
                lead_result = await db.execute(
                    select(Lead).where(Lead.email == recipient_email)
                )
                lead = lead_result.scalar_one_or_none()

                if lead:
                    # 3d. Existing lead — update timestamps and stage
                    if not lead.last_contacted_at or gmail_date > lead.last_contacted_at:
                        lead.last_contacted_at = gmail_date
                    if lead.stage == "prospect":
                        lead.stage = "contacted"
                else:
                    # 3e. New lead from sent email
                    to_raw = msg.get("to_raw", recipient_email)
                    if "<" in to_raw:
                        name_part = to_raw.split("<")[0].strip().strip('"')
                    else:
                        name_part = recipient_email.split("@")[0]

                    # Split name into first/last
                    name_parts = name_part.split() if name_part else [recipient_email.split("@")[0]]
                    first_name = name_parts[0] if name_parts else "Unknown"
                    last_name = name_parts[-1] if len(name_parts) > 1 else ""

                    lead = Lead(
                        first_name=first_name,
                        last_name=last_name,
                        email=recipient_email,
                        source="gmail_sync",
                        stage="contacted",
                        job_title="Unknown",
                        last_contacted_at=gmail_date,
                    )
                    db.add(lead)
                    await db.flush()  # Get lead.id
                    new_leads_created += 1

                # Create Message record
                message = Message(
                    lead_id=lead.id,
                    direction="outbound",
                    status="sent",
                    channel="email",
                    sent_at=gmail_date,
                    external_id=msg["message_id"],
                    body=msg["body"] or "(no body)",
                    subject=msg["subject"],
                )
                db.add(message)

                # Log activity
                activity = Activity(
                    lead_id=lead.id,
                    type="email_sent",
                    channel="email",
                    description=f"Gmail sync: sent email to {recipient_email} — {msg['subject'] or '(no subject)'}",
                )
                db.add(activity)
                synced += 1

            # 4. Update last sync timestamp
            now_ts = datetime.now(timezone.utc).timestamp()
            if setting:
                setting.value = {"timestamp": now_ts}
            else:
                db.add(SystemSetting(key="gmail_sent_last_sync", value={"timestamp": now_ts}))

            await db.commit()
            logger.info(f"Gmail sent sync complete: synced={synced}, skipped={skipped}, new_leads={new_leads_created}")
            return {"synced": synced, "skipped": skipped, "new_leads_created": new_leads_created}

    return run_async(_sync())


@celery_app.task(name="app.workers.email_tasks.advance_sequences")
def advance_sequences():
    """Advance campaign enrollments that are due for their next step."""
    from app.services.outreach_orchestrator import orchestrator
    from app.dependencies import create_worker_session
    from app.models.sequence import CampaignEnrollment

    async def _advance():
        async with create_worker_session()() as db:
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
