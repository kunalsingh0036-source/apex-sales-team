"""
Outreach Orchestrator — the brain of the outreach system.
Manages sequence state machine, cross-channel coordination, anti-spam logic.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sequence import Sequence, Campaign, CampaignEnrollment
from app.models.message import Message
from app.models.lead import Lead
from app.models.activity import Activity
from app.core.indian_calendar import next_send_window, IST
from app.core.rate_limiter import rate_limiter
from app.core.channel_registry import CHANNELS, CROSS_CHANNEL_RULES
from app.services.ai_engine import ai_engine
from app.services.template_engine import render_template


class OutreachOrchestrator:
    """Coordinates sequences across channels with anti-spam logic."""

    async def advance_enrollment(self, enrollment: CampaignEnrollment, db: AsyncSession):
        """Advance an enrollment to its next step. Returns True if a message was queued."""
        # Load the sequence
        seq_result = await db.execute(
            select(Sequence).where(Sequence.id == enrollment.sequence_id)
        )
        sequence = seq_result.scalar_one_or_none()
        if not sequence or not sequence.steps:
            enrollment.status = "completed"
            return False

        steps = sequence.steps
        current_step_idx = enrollment.current_step

        # Check if sequence is complete
        if current_step_idx >= len(steps):
            enrollment.status = "completed"
            return False

        step = steps[current_step_idx]
        channel = step.get("channel", sequence.channel)

        # Check rate limit
        can_send = await rate_limiter.can_send(channel)
        if not can_send:
            return False

        # Load lead
        lead_result = await db.execute(
            select(Lead).where(Lead.id == enrollment.lead_id)
        )
        lead = lead_result.scalar_one_or_none()
        if not lead or lead.do_not_contact:
            enrollment.status = "completed"
            return False

        # Check cross-channel cooldown
        if channel != "email":
            cooldown_ok = await self._check_cooldown(lead.id, channel, db)
            if not cooldown_ok:
                return False

        # Determine message content (A/B variant selection)
        variant = "A"
        subject_variants = step.get("subject_variants", [])
        body_variants = step.get("body_variants", [])

        if subject_variants and body_variants:
            # Simple A/B: alternate based on enrollment ID hash
            variant = "A" if hash(str(enrollment.id)) % 2 == 0 else "B"

        subject = None
        body = ""

        if subject_variants:
            idx = 0 if variant == "A" else min(1, len(subject_variants) - 1)
            subject = subject_variants[idx]
        if body_variants:
            idx = 0 if variant == "A" else min(1, len(body_variants) - 1)
            body = body_variants[idx]

        # If no variants, generate with AI
        if not body:
            company_name = ""
            industry = "Other"
            if lead.company_id:
                from app.models.lead import Company
                comp_result = await db.execute(
                    select(Company).where(Company.id == lead.company_id)
                )
                company = comp_result.scalar_one_or_none()
                if company:
                    company_name = company.name
                    industry = company.industry

            message_type = step.get("type", "cold_intro")
            ai_result = await ai_engine.generate_outreach_message(
                lead_name=lead.full_name,
                lead_title=lead.job_title,
                lead_company=company_name,
                lead_industry=industry,
                channel=channel,
                message_type=message_type,
            )
            subject = ai_result.get("subject")
            body = ai_result.get("body", "")

        # Apply template variables if body contains {{placeholders}}
        if "{{" in body:
            variables = {
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "full_name": lead.full_name,
                "job_title": lead.job_title,
                "company_name": company_name if "company_name" in body else "",
            }
            body = render_template(body, variables)
            if subject and "{{" in subject:
                subject = render_template(subject, variables)

        # Create the message
        message = Message(
            lead_id=lead.id,
            campaign_id=enrollment.campaign_id,
            enrollment_id=enrollment.id,
            channel=channel,
            direction="outbound",
            subject=subject,
            body=body,
            status="queued",
            variant=variant,
            scheduled_at=enrollment.next_step_at or datetime.now(timezone.utc),
        )
        db.add(message)

        # Update enrollment
        enrollment.current_step = current_step_idx + 1
        enrollment.last_step_at = datetime.now(timezone.utc)

        # Calculate next step time
        if current_step_idx + 1 < len(steps):
            next_step = steps[current_step_idx + 1]
            delay_days = next_step.get("delay_days", 3)
            next_time = datetime.now(timezone.utc) + timedelta(days=delay_days)
            enrollment.next_step_at = next_send_window(next_time)
        else:
            enrollment.next_step_at = None

        # Log activity
        activity = Activity(
            lead_id=lead.id,
            type=f"{channel}_queued",
            channel=channel,
            description=f"Step {current_step_idx + 1}/{len(steps)} queued: {subject or body[:60]}",
        )
        db.add(activity)

        return True

    async def handle_reply(
        self, lead_id, message_text: str, channel: str, db: AsyncSession
    ):
        """Handle an inbound reply — classify, stop sequences, create inbound message."""
        # Classify the response
        classification_result = await ai_engine.classify_response(message_text)
        classification = classification_result["classification"]
        confidence = classification_result.get("confidence", 0.85)

        # Create inbound message record
        message = Message(
            lead_id=lead_id,
            channel=channel,
            direction="inbound",
            body=message_text,
            status="received",
            classification=classification,
            classification_confidence=confidence,
        )
        db.add(message)

        # Stop all active enrollments for this lead if they replied
        enrollments = await db.execute(
            select(CampaignEnrollment).where(
                CampaignEnrollment.lead_id == lead_id,
                CampaignEnrollment.status == "active",
            )
        )
        for enrollment in enrollments.scalars().all():
            enrollment.status = "replied"

        # Update lead stage based on classification
        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalar_one_or_none()
        if lead:
            if classification in ("interested", "meeting_request", "requesting_info"):
                if lead.stage in ("prospect", "contacted"):
                    lead.stage = "engaged"
            elif classification == "unsubscribe":
                lead.do_not_contact = True
                lead.consent_status = "opted_out"

        # Generate AI suggested reply for hot leads
        ai_reply = None
        if classification in ("interested", "meeting_request", "requesting_info"):
            # Find last outbound message
            last_outbound = await db.execute(
                select(Message)
                .where(Message.lead_id == lead_id, Message.direction == "outbound")
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            original = last_outbound.scalar_one_or_none()

            ai_reply = await ai_engine.suggest_reply(
                original_message=original.body if original else "",
                response_text=message_text,
                lead_name=lead.full_name if lead else "Unknown",
                lead_company=lead.company.name if lead and lead.company_id else "Unknown",
                classification=classification,
            )
            message.ai_suggested_reply = ai_reply

        # Log activity
        activity = Activity(
            lead_id=lead_id,
            type=f"{channel}_received",
            channel=channel,
            description=f"Reply received — classified as: {classification}",
            extra_data={
                "classification": classification,
                "confidence": confidence,
                "has_suggested_reply": ai_reply is not None,
            },
        )
        db.add(activity)

        await db.commit()

        return {
            "classification": classification,
            "confidence": confidence,
            "ai_suggested_reply": ai_reply,
            "sequences_stopped": True,
        }

    async def _check_cooldown(
        self, lead_id, channel: str, db: AsyncSession
    ) -> bool:
        """Check cross-channel cooldown — ensure min gap between channel touches."""
        min_gap_hours = CROSS_CHANNEL_RULES["min_gap_hours"]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=min_gap_hours)

        result = await db.execute(
            select(Message).where(
                Message.lead_id == lead_id,
                Message.direction == "outbound",
                Message.created_at >= cutoff,
                Message.channel != channel,
            ).limit(1)
        )
        recent_on_other_channel = result.scalar_one_or_none()
        return recent_on_other_channel is None


orchestrator = OutreachOrchestrator()
