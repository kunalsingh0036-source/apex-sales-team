"""
Outreach Orchestrator — the brain of the outreach system.
Manages sequence state machine, cross-channel coordination, anti-spam logic.
"""

import logging
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


logger = logging.getLogger(__name__)


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

        # DRIP GATE: If there's already an outbound message for this enrollment that
        # hasn't been sent yet (still in review / draft / queued / failed), don't
        # generate the next step. Wait for the prior step to actually go out first —
        # otherwise step N+1's content references an email that may still be edited
        # or rejected. The next_step_at is set to None so the worker won't re-pick
        # this enrollment until `schedule_next_step_after_send` reschedules it.
        prior_msg_q = await db.execute(
            select(Message)
            .where(
                Message.enrollment_id == enrollment.id,
                Message.direction == "outbound",
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        prior = prior_msg_q.scalar_one_or_none()
        if prior and prior.status != "sent":
            enrollment.next_step_at = None
            logger.info(
                f"Drip gate held enrollment {enrollment.id}: prior step is {prior.status}, "
                f"not sent. Will retry when prior step sends."
            )
            return False

        step = steps[current_step_idx]
        channel = step.get("channel", sequence.channel)

        # Check rate limit (per channel)
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

        # Contact guard check
        from app.services.contact_guard import can_contact
        allowed, reason = await can_contact(lead, db)
        if not allowed:
            logger.info(f"Contact guard blocked {lead.email}: {reason}")
            return False

        # NOTE: No cross-channel cooldown check here — deliberate sequence steps
        # have their own `delay_days` timing, which is the source of truth.
        # The cooldown rule (CROSS_CHANNEL_RULES) exists to prevent opportunistic
        # multi-channel spam, not to block coordinated follow-ups.

        # Load company info
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
                industry = company.industry or "Other"

        # Always generate fresh, personalized content per lead.
        variant = "A" if hash(str(enrollment.id)) % 2 == 0 else "B"
        message_type = step.get("type", "cold_intro")
        subject = None
        body = ""

        # Pre-compute metadata for this message
        extra_data: dict = {}
        message_status = "content_review"
        last_error: str | None = None

        # LinkedIn-specific path: needs linkedin_url on the lead
        if channel == "linkedin":
            extra_data["linkedin_type"] = "connection_request"
            extra_data["linkedin_status"] = "pending_approval"
            if lead.linkedin_url:
                extra_data["profile_url"] = lead.linkedin_url
            else:
                # Hold for human review — don't block future email steps
                extra_data["needs_linkedin_url"] = True
                last_error = "Lead has no linkedin_url on record"

        # Build AI context (for linkedin follow-up, reference the last sent email)
        prior_email_context = ""
        if channel == "linkedin":
            prior_email_q = await db.execute(
                select(Message)
                .where(
                    Message.lead_id == lead.id,
                    Message.channel == "email",
                    Message.direction == "outbound",
                    Message.status == "sent",
                )
                .order_by(Message.sent_at.desc())
                .limit(1)
            )
            prior_email = prior_email_q.scalar_one_or_none()
            if prior_email:
                prior_email_context = (
                    f"You sent this person this email yesterday:\n"
                    f"Subject: {prior_email.subject or '(no subject)'}\n"
                    f"Body: {(prior_email.body or '')[:500]}"
                )

        custom_instructions = ""
        if channel == "linkedin":
            custom_instructions = (
                "Hard limit: 300 characters including signature. "
                "Reference the email you sent yesterday naturally. "
                "Warm, human, conversational. Sign with 'Radhika' only — "
                "no company, no phone (those are visible on the LinkedIn profile)."
            )

        try:
            ai_result = await ai_engine.generate_outreach_message(
                lead_name=lead.full_name,
                lead_title=lead.job_title,
                lead_company=company_name,
                lead_industry=industry,
                channel=channel,
                message_type=message_type,
                context=prior_email_context,
                custom_instructions=custom_instructions,
            )
            body = ai_result.get("body", "") or ""
            subject = ai_result.get("subject") or subject

            # Enforce 300-char limit for LinkedIn connection requests
            if channel == "linkedin" and message_type == "connection_request" and len(body) > 300:
                # Regenerate once with stricter prompt
                try:
                    retry = await ai_engine.generate_outreach_message(
                        lead_name=lead.full_name,
                        lead_title=lead.job_title,
                        lead_company=company_name,
                        lead_industry=industry,
                        channel=channel,
                        message_type=message_type,
                        context=prior_email_context,
                        custom_instructions=custom_instructions + " You went over 300 chars on the first try — be much tighter this time. Count characters.",
                    )
                    retry_body = retry.get("body", "") or ""
                    if retry_body and len(retry_body) <= 300:
                        body = retry_body
                except Exception:
                    pass
                # Last resort: truncate with ellipsis
                if len(body) > 300:
                    body = body[:297].rstrip() + "..."
        except Exception as e:
            logger.error(f"AI generation failed for {lead.email}: {e}")
            return False  # don't send generic content

        # Create the message
        message = Message(
            lead_id=lead.id,
            campaign_id=enrollment.campaign_id,
            enrollment_id=enrollment.id,
            channel=channel,
            direction="outbound",
            subject=subject,
            body=body,
            status=message_status,
            variant=variant,
            scheduled_at=enrollment.next_step_at or datetime.now(timezone.utc),
            extra_data=extra_data,
        )
        if last_error:
            message.extra_data = {**message.extra_data, "last_error": last_error}
        db.add(message)

        # Update enrollment
        enrollment.current_step = current_step_idx + 1
        enrollment.last_step_at = datetime.now(timezone.utc)

        # PARK: next_step_at starts NULL. `schedule_next_step_after_send` will
        # populate it based on the real sent_at + next step's delay_days, so the
        # drip timer begins from when the email actually went out — not when the
        # AI drafted it (which could be days before approval).
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

    async def schedule_next_step_after_send(
        self, message: Message, db: AsyncSession
    ):
        """Called immediately after a message is successfully sent.

        Looks up the message's enrollment (if any) and schedules the next step
        based on the REAL sent_at + next step's delay_days. This is how drip
        actually drips — the timer for step N+1 starts ticking from step N's
        send time, not from step N's generation time.

        No-ops when: message has no enrollment, enrollment is not active,
        sequence is complete, or sequence has no more steps.
        """
        if not message.enrollment_id or not message.sent_at:
            return

        enrollment_q = await db.execute(
            select(CampaignEnrollment).where(
                CampaignEnrollment.id == message.enrollment_id
            )
        )
        enrollment = enrollment_q.scalar_one_or_none()
        if not enrollment or enrollment.status != "active":
            return

        seq_q = await db.execute(
            select(Sequence).where(Sequence.id == enrollment.sequence_id)
        )
        sequence = seq_q.scalar_one_or_none()
        if not sequence or not sequence.steps:
            return

        steps = sequence.steps
        next_idx = enrollment.current_step  # already incremented past the step that just sent

        if next_idx >= len(steps):
            # Sequence complete — mark enrollment finished so drip stops.
            enrollment.status = "completed"
            enrollment.next_step_at = None
            return

        next_step = steps[next_idx]
        delay_days = next_step.get("delay_days", 3)
        next_time = message.sent_at + timedelta(days=delay_days)
        enrollment.next_step_at = next_send_window(next_time)
        logger.info(
            f"Enrollment {enrollment.id} step {next_idx + 1} scheduled for {enrollment.next_step_at} "
            f"(sent_at={message.sent_at} + {delay_days}d)"
        )

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
