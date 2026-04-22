import uuid
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.models.message import Message
from app.models.lead import Lead
from app.models.activity import Activity
from app.schemas.message import (
    MessageResponse, SendMessageRequest, GenerateMessageRequest,
    ApproveBatchRequest, RegenerateRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.ai_engine import ai_engine
from app.services.email_service import gmail_service
from app.core.rate_limiter import rate_limiter

router = APIRouter()


@router.get("", response_model=PaginatedResponse[MessageResponse])
async def list_messages(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    lead_id: uuid.UUID | None = None,
    channel: str | None = None,
    direction: str | None = None,
    status: str | None = None,
    classification: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Message)
    count_query = select(func.count()).select_from(Message)

    if lead_id:
        query = query.where(Message.lead_id == lead_id)
        count_query = count_query.where(Message.lead_id == lead_id)
    if channel:
        query = query.where(Message.channel == channel)
        count_query = count_query.where(Message.channel == channel)
    if direction:
        query = query.where(Message.direction == direction)
        count_query = count_query.where(Message.direction == direction)
    if status:
        query = query.where(Message.status == status)
        count_query = count_query.where(Message.status == status)
    if classification:
        query = query.where(Message.classification == classification)
        count_query = count_query.where(Message.classification == classification)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(Message.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[MessageResponse.model_validate(m) for m in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get("/pending-replies")
async def pending_replies(db: AsyncSession = Depends(get_db)):
    """Get inbound messages that need human attention."""
    result = await db.execute(
        select(Message)
        .where(
            Message.direction == "inbound",
            Message.classification.in_(["interested", "meeting_request", "requesting_info"]),
        )
        .order_by(Message.created_at.desc())
        .limit(50)
    )
    items = result.scalars().all()
    return [MessageResponse.model_validate(m) for m in items]


@router.post("/retry-failed")
async def retry_failed_messages(db: AsyncSession = Depends(get_db)):
    """Re-queue all failed outbound email messages for retry."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Message).where(
            Message.status == "failed",
            Message.direction == "outbound",
            Message.channel == "email",
        )
    )
    messages = result.scalars().all()
    count = 0
    for msg in messages:
        msg.status = "queued"
        msg.scheduled_at = now
        count += 1
    await db.commit()
    return {"requeued": count}


@router.post("/send", response_model=MessageResponse, status_code=201)
async def send_message(data: SendMessageRequest, db: AsyncSession = Depends(get_db)):
    """Manually send a message to a lead."""
    # Verify lead
    lead_result = await db.execute(
        select(Lead).options(selectinload(Lead.company)).where(Lead.id == data.lead_id)
    )
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.do_not_contact:
        raise HTTPException(status_code=400, detail="Lead is marked do-not-contact")

    # Contact guard check
    from app.services.contact_guard import can_contact
    allowed, reason = await can_contact(lead, db)
    if not allowed:
        raise HTTPException(status_code=409, detail=f"Contact guard: {reason}")

    if data.channel == "email":
        if not lead.email:
            raise HTTPException(status_code=400, detail="Lead has no email address")

        # Check rate limit
        can_send = await rate_limiter.can_send("email")
        if not can_send:
            raise HTTPException(status_code=429, detail="Email daily limit reached")

        # Send via Gmail
        result = await gmail_service.send_email(
            to=lead.email,
            subject=data.subject or "The Apex Human Company",
            body=data.body,
        )

        await rate_limiter.record_send("email")

        message = Message(
            lead_id=lead.id,
            channel="email",
            direction="outbound",
            subject=data.subject,
            body=data.body,
            status="sent",
            sent_at=datetime.now(timezone.utc),
            external_id=result.get("message_id"),
        )
    else:
        # Non-email channels: queue for Phase 3
        message = Message(
            lead_id=lead.id,
            channel=data.channel,
            direction="outbound",
            subject=data.subject,
            body=data.body,
            status="queued",
            scheduled_at=data.schedule_at,
        )

    db.add(message)

    # Log activity
    activity = Activity(
        lead_id=lead.id,
        type=f"{data.channel}_sent",
        channel=data.channel,
        description=f"Message sent via {data.channel}: {(data.subject or data.body[:50])}",
    )
    db.add(activity)

    await db.commit()
    await db.refresh(message)
    return MessageResponse.model_validate(message)


@router.post("/generate")
async def generate_message(data: GenerateMessageRequest, db: AsyncSession = Depends(get_db)):
    """Generate a personalized message using Claude AI."""
    lead_result = await db.execute(
        select(Lead).options(selectinload(Lead.company)).where(Lead.id == data.lead_id)
    )
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    company_name = lead.company.name if lead.company else "their company"
    industry = lead.company.industry if lead.company else "Other"

    result = await ai_engine.generate_outreach_message(
        lead_name=lead.full_name,
        lead_title=lead.job_title,
        lead_company=company_name,
        lead_industry=industry,
        channel=data.channel,
        message_type=data.message_type,
        context=data.context,
        custom_instructions=data.custom_instructions,
    )

    return {
        "subject": result.get("subject"),
        "body": result.get("body", ""),
        "notes": result.get("notes", ""),
        "lead": {"id": str(lead.id), "name": lead.full_name},
    }


@router.post("/{message_id}/attachments")
async def upload_attachment(
    message_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload file attachments to a message. Files are stored in message extra_data."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.status not in ("content_review", "draft"):
        raise HTTPException(status_code=400, detail=f"Cannot add attachments to a {message.status} message")

    import base64
    attachments = message.extra_data.get("attachments", [])
    for f in files:
        content = await f.read()
        if len(content) > 10 * 1024 * 1024:  # 10MB limit per file
            raise HTTPException(status_code=400, detail=f"File {f.filename} exceeds 10MB limit")
        attachments.append({
            "filename": f.filename,
            "content_type": f.content_type or "application/octet-stream",
            "size": len(content),
            "data": base64.b64encode(content).decode(),
        })

    message.extra_data = {**message.extra_data, "attachments": attachments}
    await db.commit()
    return {
        "status": "uploaded",
        "attachments": [{"filename": a["filename"], "size": a["size"], "content_type": a["content_type"]} for a in attachments],
    }


@router.delete("/{message_id}/attachments/{filename}")
async def remove_attachment(
    message_id: uuid.UUID,
    filename: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove an attachment from a message."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    attachments = message.extra_data.get("attachments", [])
    attachments = [a for a in attachments if a["filename"] != filename]
    message.extra_data = {**message.extra_data, "attachments": attachments}
    await db.commit()
    return {"status": "removed", "remaining": len(attachments)}


class ApproveRequest(BaseModel):
    schedule_at: Optional[datetime] = None


@router.post("/{message_id}/approve")
async def approve_message(message_id: uuid.UUID, data: Optional[ApproveRequest] = None, db: AsyncSession = Depends(get_db)):
    """Approve a message. Channel-aware:
    - Email: sends via Gmail immediately (or schedules).
    - LinkedIn: queues for the LinkedIn worker (process_linkedin_queue picks up every 15 min).
    If schedule_at is provided, the message is queued with that scheduled time regardless of channel.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.status not in ("content_review", "failed"):
        raise HTTPException(status_code=400, detail=f"Message is {message.status}, cannot approve")

    lead_result = await db.execute(select(Lead).where(Lead.id == message.lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=400, detail="Lead not found")

    channel = message.channel or "email"

    # Channel-specific recipient validation
    if channel == "email":
        if not lead.email:
            message.extra_data = {**(message.extra_data or {}), "last_error": "Lead has no email"}
            await db.commit()
            raise HTTPException(status_code=400, detail="Lead has no email")
    elif channel == "linkedin":
        if not lead.linkedin_url:
            message.extra_data = {
                **(message.extra_data or {}),
                "last_error": "Lead has no linkedin_url on record",
                "needs_linkedin_url": True,
            }
            await db.commit()
            raise HTTPException(status_code=409, detail="Lead has no linkedin_url — update the lead record before approving")
    else:
        raise HTTPException(status_code=400, detail=f"Approval for channel={channel} is not yet supported")

    if lead.do_not_contact:
        message.extra_data = {**(message.extra_data or {}), "last_error": "Lead is marked do_not_contact"}
        await db.commit()
        raise HTTPException(status_code=400, detail="Lead is do_not_contact")

    # Contact guard check. Bypassed when the message is part of an active enrollment
    # because the sequence's timing is a deliberate coordinated choice — the guard
    # exists to prevent opportunistic double-touches, not scheduled follow-ups.
    if not message.enrollment_id:
        from app.services.contact_guard import can_contact
        allowed, reason = await can_contact(lead, db)
        if not allowed:
            message.extra_data = {**(message.extra_data or {}), "last_error": f"Contact guard: {reason}"}
            await db.commit()
            raise HTTPException(status_code=409, detail=f"Contact guard: {reason}")

    # If schedule_at provided, queue for the relevant worker regardless of channel
    if data and data.schedule_at:
        message.status = "queued"
        message.scheduled_at = data.schedule_at
        extra = {**(message.extra_data or {}), "last_error": None, "approved_by": "human"}
        if channel == "linkedin":
            extra["linkedin_status"] = "queued"
        message.extra_data = extra
        await db.commit()
        return {"status": "scheduled", "scheduled_at": data.schedule_at.isoformat(), "channel": channel}

    # LinkedIn: queue for the LinkedIn worker (never send inline from the API process)
    if channel == "linkedin":
        message.status = "queued"
        message.scheduled_at = datetime.now(timezone.utc)
        message.extra_data = {
            **(message.extra_data or {}),
            "last_error": None,
            "approved_by": "human",
            "linkedin_status": "queued",
        }
        await db.commit()
        return {"status": "queued_for_linkedin", "channel": "linkedin"}

    # Email: send now
    can_send = await rate_limiter.can_send("email")
    if not can_send:
        message.extra_data = {**(message.extra_data or {}), "last_error": "Email daily limit reached"}
        await db.commit()
        raise HTTPException(status_code=429, detail="Email daily limit reached")

    try:
        # Build attachments from stored data
        import base64 as b64
        stored_atts = (message.extra_data or {}).get("attachments", [])
        atts = [{"filename": a["filename"], "content": b64.b64decode(a["data"]), "content_type": a["content_type"]} for a in stored_atts] if stored_atts else None

        gmail_result = await gmail_service.send_email(
            to=lead.email,
            subject=message.subject or "The Apex Human Company",
            body=message.body,
            attachments=atts,
        )
        message.status = "sent"
        message.sent_at = datetime.now(timezone.utc)
        message.external_id = gmail_result.get("message_id")
        message.extra_data = {**(message.extra_data or {}), "last_error": None}
        await rate_limiter.record_send("email")

        # Update last_contacted_at
        from app.services.contact_guard import update_last_contacted
        await update_last_contacted(lead, db)

        activity = Activity(
            lead_id=lead.id,
            type="email_sent",
            channel="email",
            description=f"Email approved and sent: {message.subject or message.body[:60]}",
        )
        db.add(activity)
        await db.commit()
        return {"status": "sent", "gmail_id": gmail_result.get("message_id"), "channel": "email"}
    except Exception as e:
        # Keep in content_review so user can retry — don't mark as failed
        message.extra_data = {**(message.extra_data or {}), "last_error": f"Send failed: {str(e)}"}
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve-batch")
async def approve_batch(data: ApproveBatchRequest, db: AsyncSession = Depends(get_db)):
    """Approve multiple content_review messages. Email sends immediately; LinkedIn queues for the worker."""
    results = []
    for mid in data.message_ids:
        result = await db.execute(select(Message).where(Message.id == mid))
        message = result.scalar_one_or_none()
        if not message or message.status != "content_review":
            results.append({"id": str(mid), "status": "skipped", "reason": "not in content_review"})
            continue

        lead_result = await db.execute(select(Lead).where(Lead.id == message.lead_id))
        lead = lead_result.scalar_one_or_none()
        if not lead:
            results.append({"id": str(mid), "status": "skipped", "reason": "lead not found"})
            continue

        channel = message.channel or "email"

        if channel == "email" and not lead.email:
            results.append({"id": str(mid), "status": "skipped", "reason": "no email"})
            continue
        if channel == "linkedin" and not lead.linkedin_url:
            results.append({"id": str(mid), "status": "skipped", "reason": "no linkedin_url"})
            continue
        if channel not in ("email", "linkedin"):
            results.append({"id": str(mid), "status": "skipped", "reason": f"channel {channel} not supported"})
            continue

        # Contact guard check — bypassed for messages inside an active enrollment
        # (deliberate sequence timing takes precedence over the opportunistic guard)
        if not message.enrollment_id:
            from app.services.contact_guard import can_contact
            allowed, reason = await can_contact(lead, db)
            if not allowed:
                results.append({"id": str(mid), "status": "blocked", "reason": f"contact_guard: {reason}"})
                continue

        # LinkedIn path: queue for worker
        if channel == "linkedin":
            message.status = "queued"
            message.scheduled_at = datetime.now(timezone.utc)
            message.extra_data = {
                **(message.extra_data or {}),
                "approved_by": "human",
                "last_error": None,
                "linkedin_status": "queued",
            }
            results.append({"id": str(mid), "status": "queued_for_linkedin"})
            continue

        # Email path: send now
        can_send = await rate_limiter.can_send("email")
        if not can_send:
            results.append({"id": str(mid), "status": "rate_limited"})
            continue

        try:
            # Load user-uploaded attachments from extra_data (brief is auto-added by email_service)
            import base64 as b64
            stored_atts = (message.extra_data or {}).get("attachments", [])
            atts = [{"filename": a["filename"], "content": b64.b64decode(a["data"]), "content_type": a["content_type"]} for a in stored_atts] if stored_atts else None

            gmail_result = await gmail_service.send_email(
                to=lead.email,
                subject=message.subject or "The Apex Human Company",
                body=message.body,
                attachments=atts,
            )
            message.status = "sent"
            message.sent_at = datetime.now(timezone.utc)
            message.external_id = gmail_result.get("message_id")
            await rate_limiter.record_send("email")

            # Mark lead as contacted
            from app.services.contact_guard import update_last_contacted
            await update_last_contacted(lead, db)

            activity = Activity(
                lead_id=lead.id,
                type="email_sent",
                channel="email",
                description=f"Email approved and sent: {message.subject or message.body[:60]}",
            )
            db.add(activity)
            results.append({"id": str(mid), "status": "sent"})
        except Exception as e:
            # Keep in content_review so user can retry
            message.extra_data = {**(message.extra_data or {}), "last_error": f"Send failed: {str(e)}"}
            results.append({"id": str(mid), "status": "error", "reason": str(e)})

    await db.commit()
    sent_count = sum(1 for r in results if r["status"] == "sent")
    queued_count = sum(1 for r in results if r["status"] == "queued_for_linkedin")
    return {"results": results, "sent": sent_count, "queued_for_linkedin": queued_count, "total": len(data.message_ids)}


class LinkedinStatusRequest(BaseModel):
    status: str  # "accepted" | "declined"


@router.post("/{message_id}/linkedin-status")
async def mark_linkedin_status(
    message_id: uuid.UUID,
    data: LinkedinStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually mark a LinkedIn connection request as accepted or declined.
    Automatic detection via LinkedIn /v2/invitations polling is deferred until
    Partner API access is granted."""
    if data.status not in ("accepted", "declined"):
        raise HTTPException(status_code=400, detail="status must be 'accepted' or 'declined'")

    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.channel != "linkedin":
        raise HTTPException(status_code=400, detail=f"Only LinkedIn messages can be marked — this is {message.channel}")

    message.extra_data = {**(message.extra_data or {}), "linkedin_status": data.status}

    activity = Activity(
        lead_id=message.lead_id,
        type=f"linkedin_connection_{data.status}",
        channel="linkedin",
        description=f"Connection request marked as {data.status}",
    )
    db.add(activity)
    await db.commit()
    return {"status": "ok", "linkedin_status": data.status, "message_id": str(message_id)}


@router.post("/{message_id}/reject")
async def reject_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Reject a content_review message. Sets status to draft."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.status != "content_review":
        raise HTTPException(status_code=400, detail=f"Message is {message.status}, not content_review")

    message.status = "draft"
    await db.commit()
    return {"status": "rejected", "message_id": str(message_id)}


class MessageUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


@router.patch("/{message_id}")
async def update_message(message_id: uuid.UUID, data: MessageUpdate, db: AsyncSession = Depends(get_db)):
    """Edit a message's subject and/or body."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.status not in ("content_review", "draft"):
        raise HTTPException(status_code=400, detail=f"Cannot edit a {message.status} message")
    if data.subject is not None:
        message.subject = data.subject
    if data.body is not None:
        message.body = data.body
    await db.commit()
    return {"status": "updated", "id": str(message.id), "subject": message.subject, "body": message.body}


@router.post("/{message_id}/regenerate")
async def regenerate_message(
    message_id: uuid.UUID,
    data: RegenerateRequest = RegenerateRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate message content using AI. Keeps status as content_review."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.status not in ("content_review", "draft"):
        raise HTTPException(status_code=400, detail=f"Message is {message.status}, cannot regenerate")

    lead_result = await db.execute(
        select(Lead).options(selectinload(Lead.company)).where(Lead.id == message.lead_id)
    )
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    company_name = lead.company.name if lead.company else ""
    industry = lead.company.industry if lead.company else "Other"

    ai_result = await ai_engine.generate_outreach_message(
        lead_name=lead.full_name,
        lead_title=lead.job_title or "",
        lead_company=company_name,
        lead_industry=industry,
        channel=message.channel,
        message_type="follow_up_1",
        custom_instructions=data.custom_instructions,
    )

    body = ai_result.get("body", "")
    if body and len(body.strip()) > 50:
        message.body = body
        message.subject = ai_result.get("subject") or message.subject
        message.status = "content_review"
        await db.commit()
        return {"status": "regenerated", "subject": message.subject, "body": message.body}
    else:
        raise HTTPException(status_code=500, detail="AI generation returned insufficient content")


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return MessageResponse.model_validate(message)


@router.get("/{message_id}/suggest-reply")
async def suggest_reply(message_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get AI-suggested reply for an inbound message."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.direction != "inbound":
        raise HTTPException(status_code=400, detail="Can only suggest replies for inbound messages")

    # Find the original outbound message in the same thread
    lead_result = await db.execute(
        select(Lead).options(selectinload(Lead.company)).where(Lead.id == message.lead_id)
    )
    lead = lead_result.scalar_one_or_none()

    # Get last outbound message to this lead
    outbound = await db.execute(
        select(Message)
        .where(Message.lead_id == message.lead_id, Message.direction == "outbound")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    original = outbound.scalar_one_or_none()

    reply = await ai_engine.suggest_reply(
        original_message=original.body if original else "",
        response_text=message.body,
        lead_name=lead.full_name if lead else "Unknown",
        lead_company=lead.company.name if lead and lead.company else "Unknown",
        classification=message.classification or "interested",
    )

    return {"suggested_reply": reply, "message_id": str(message.id)}


@router.post("/{message_id}/classify")
async def classify_message(
    message_id: uuid.UUID,
    classification: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Manually override AI classification."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    valid = [
        "interested", "not_interested", "out_of_office", "wrong_person",
        "requesting_info", "meeting_request", "objection", "referral", "unsubscribe",
    ]
    if classification not in valid:
        raise HTTPException(status_code=400, detail=f"Must be one of: {valid}")

    message.classification = classification
    message.classification_confidence = 1.0  # Manual = 100% confidence

    await db.commit()
    return {"success": True, "classification": classification}
