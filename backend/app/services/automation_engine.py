"""
Automation Engine — fully autonomous lead discovery, enrichment, sequence generation,
and campaign creation pipeline. Reads configuration from system_settings table.
"""

import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, Company, LeadBatch
from app.models.sequence import Sequence, Campaign, CampaignEnrollment
from app.models.activity import Activity
from app.models.user import SystemSetting
from app.services.lead_discovery import lead_discovery
from app.services.enrichment_service import enrichment_service
from app.services.ai_engine import ai_engine
from app.core.rate_limiter import rate_limiter
from app.core.indian_calendar import get_active_seasons

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

DEFAULT_ICP = {
    "job_titles": [
        "Head of Procurement", "VP Operations", "HR Director", "Admin Manager",
        "Brand Manager", "Marketing Head", "CPO", "CHRO", "CMO", "General Manager",
    ],
    "industries": [
        "Technology & SaaS", "Banking & Financial Services", "Pharma & Healthcare",
        "FMCG & Retail", "Real Estate", "Hospitality & Luxury Hotels", "Defence & Government",
    ],
    "locations": ["India"],
    "company_sizes": ["201-500", "501-1000", "1001-5000", "5001-10000"],
    "keywords": [],
    "max_results": 50,
}

DEFAULT_SETTINGS = {
    "campaign_day": 0,  # 0=Monday
    "aggressiveness": "normal",  # low, normal, high
}

AGGRESSIVENESS_MAP = {
    "low": {"max_results": 25, "include_cold": False},
    "normal": {"max_results": 50, "include_cold": True},
    "high": {"max_results": 100, "include_cold": True},
}

TIER_STRATEGY = {
    # tier: (channels, delay_multiplier)
    "hot": (["email", "linkedin"], 1),
    "warm": (["email"], 1),
    "medium": (["email"], 2),
    "cold": (["email"], 3),
}

# Hard cap on how many leads autopilot processes per batch. Going wide is
# tempting but makes tracking impossible — the team has explicitly chosen
# 20-at-a-time so each batch B-xxxx is a coherent wave they can manage end-
# to-end before the next one starts.
BATCH_SIZE = 20

# Auto-trigger cadence for the next batch when the previous one is still
# active. If the latest batch was created more than this many days ago, the
# daily check fires the next batch even if the prior one isn't fully done.
ALTERNATE_DAY_GAP_HOURS = 36  # 1.5 days — accommodates "every alternate day"


def _score_tier(score: int) -> str:
    if score >= 80:
        return "hot"
    if score >= 60:
        return "warm"
    if score >= 40:
        return "medium"
    return "cold"


class AutomationEngine:
    """Core autopilot orchestration — wires existing services into an autonomous pipeline."""

    # ─── Config helpers ────────────────────────────────────────

    async def _get_setting(self, db: AsyncSession, key: str, default: dict | None = None) -> dict:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            return setting.value
        return default or {}

    async def _upsert_setting(self, db: AsyncSession, key: str, value: dict) -> None:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
        await db.commit()

    async def is_enabled(self, db: AsyncSession) -> bool:
        data = await self._get_setting(db, "autopilot_enabled", {"enabled": False})
        return data.get("enabled", False)

    async def get_icp(self, db: AsyncSession) -> dict:
        return await self._get_setting(db, "autopilot_icp", DEFAULT_ICP)

    async def get_settings(self, db: AsyncSession) -> dict:
        return await self._get_setting(db, "autopilot_settings", DEFAULT_SETTINGS)

    # ─── Run history ───────────────────────────────────────────

    async def _log_run(self, db: AsyncSession, stage: str, result: dict) -> None:
        history = await self._get_setting(db, "autopilot_history", {"runs": []})
        runs = history.get("runs", [])
        runs.append({
            "stage": stage,
            "timestamp": datetime.now(IST).isoformat(),
            "result": result,
        })
        # Keep last 50 entries
        history["runs"] = runs[-50:]
        await self._upsert_setting(db, "autopilot_history", history)

    # ─── Batch helpers ────────────────────────────────────────

    async def create_new_batch(
        self,
        db: AsyncSession,
        triggered_by: str = "manual",
        notes: str = "",
    ) -> LeadBatch:
        """Create a new LeadBatch row. The DB sequence + trigger fill in
        batch_number and batch_code automatically — we just commit."""
        batch = LeadBatch(
            triggered_by=triggered_by,
            target_lead_count=BATCH_SIZE,
            status="active",
            notes=notes,
        )
        db.add(batch)
        await db.flush()
        await db.refresh(batch)
        logger.info(f"Created batch {batch.batch_code} (triggered_by={triggered_by})")
        return batch

    async def get_latest_batch(self, db: AsyncSession) -> LeadBatch | None:
        result = await db.execute(
            select(LeadBatch).order_by(LeadBatch.batch_number.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def is_batch_complete(self, batch: LeadBatch, db: AsyncSession) -> bool:
        """A batch is complete when no leads in it have an active enrollment.

        That covers all the real cases: replied (enrollment.status='replied'),
        finished the sequence (enrollment.status='completed'), DNC'd, no email
        in the first place, never enrolled at all. If even one enrollment is
        still 'active' we keep the batch open."""
        active_q = await db.execute(
            select(func.count(CampaignEnrollment.id))
            .join(Lead, CampaignEnrollment.lead_id == Lead.id)
            .where(
                Lead.batch_id == batch.id,
                CampaignEnrollment.status == "active",
            )
        )
        active_count = active_q.scalar() or 0
        return active_count == 0

    async def mark_batch_complete(self, batch: LeadBatch, db: AsyncSession) -> None:
        batch.status = "complete"
        batch.completed_at = datetime.now(IST)
        await db.flush()

    async def reconcile_batch_completion(self, db: AsyncSession) -> dict:
        """Sweep all active batches; mark any that have finished as complete.
        Called by the daily trigger before deciding whether to create a new batch."""
        result = await db.execute(
            select(LeadBatch).where(LeadBatch.status == "active")
        )
        batches = result.scalars().all()
        marked = 0
        for batch in batches:
            if await self.is_batch_complete(batch, db):
                await self.mark_batch_complete(batch, db)
                marked += 1
        if marked:
            await db.commit()
        return {"checked": len(batches), "marked_complete": marked}

    # ─── Stage 1: Discover Leads ──────────────────────────────

    async def discover_leads(
        self,
        db: AsyncSession,
        batch: LeadBatch | None = None,
    ) -> dict:
        """Discover up to BATCH_SIZE leads and stamp them with the given batch.

        If `batch` is None, a new one is created with triggered_by='manual'.
        Apollo is still asked for a wide pool (since we de-dupe against
        existing leads) but we stop ingesting after BATCH_SIZE NEW leads
        land in the DB — extras are discarded, not held."""
        if batch is None:
            batch = await self.create_new_batch(db, triggered_by="manual")
            await db.commit()

        icp = await self.get_icp(db)
        # Ask Apollo for ~3x the batch size so dedup-skips don't starve the batch.
        # We hard-cap the actual leads inserted at BATCH_SIZE below.
        per_page = min(BATCH_SIZE * 3, 100)

        search_result = await lead_discovery.search_people(
            job_titles=icp.get("job_titles"),
            industries=icp.get("industries"),
            locations=icp.get("locations"),
            company_sizes=icp.get("company_sizes"),
            keywords=icp.get("keywords"),
            per_page=per_page,
        )

        if "error" in search_result and search_result["error"]:
            return {"error": search_result["error"], "discovered": 0, "skipped": 0}

        people = search_result.get("people", [])
        discovered = 0
        skipped = 0

        for person in people:
            # Hard stop once the batch is full. We don't keep extras for next
            # time — next batch will run a fresh Apollo search with current ICP.
            if discovered >= BATCH_SIZE:
                break

            email = person.get("email")
            linkedin = person.get("linkedin_url")

            # Deduplicate by email or linkedin_url
            if email:
                existing = await db.execute(select(Lead.id).where(Lead.email == email))
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue
            if linkedin:
                existing = await db.execute(select(Lead.id).where(Lead.linkedin_url == linkedin))
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

            # Find or create company
            company_data = person.get("company", {})
            company_id = None
            domain = company_data.get("domain")
            if domain:
                comp_result = await db.execute(select(Company).where(Company.domain == domain))
                company = comp_result.scalar_one_or_none()
                if not company:
                    company = Company(
                        name=company_data.get("name", "Unknown"),
                        domain=domain,
                        industry=company_data.get("industry", "Other"),
                        employee_count=str(company_data.get("employee_count", "")) if company_data.get("employee_count") else None,
                        linkedin_url=company_data.get("linkedin_url"),
                    )
                    db.add(company)
                    await db.flush()
                company_id = company.id

            lead = Lead(
                company_id=company_id,
                batch_id=batch.id,
                first_name=person.get("first_name", "Unknown"),
                last_name=person.get("last_name", ""),
                email=email,
                linkedin_url=linkedin,
                phone=person.get("phone"),
                job_title=person.get("title", "Unknown"),
                seniority=person.get("seniority"),
                department=person.get("departments", [None])[0] if person.get("departments") else None,
                city=person.get("city", ""),
                state=person.get("state", ""),
                country=person.get("country", "India"),
                source="autopilot",
                stage="prospect",
                tags=["autopilot"],
            )
            db.add(lead)
            await db.flush()

            db.add(Activity(
                lead_id=lead.id,
                type="autopilot_discovery",
                channel="system",
                description=f"Auto-discovered via Apollo into batch {batch.batch_code}",
                extra_data={
                    "source": "autopilot",
                    "company": company_data.get("name", ""),
                    "batch_code": batch.batch_code,
                },
            ))
            discovered += 1

        await db.commit()
        result = {
            "discovered": discovered,
            "skipped": skipped,
            "total_searched": len(people),
            "batch_id": str(batch.id),
            "batch_code": batch.batch_code,
        }
        await self._log_run(db, "discover", result)
        return result

    # ─── Stage 2: Enrich & Score ──────────────────────────────

    async def enrich_and_score_leads(self, lead_ids: list[str], db: AsyncSession) -> dict:
        enriched = 0
        failed = 0
        tiers = {"hot": 0, "warm": 0, "medium": 0, "cold": 0}

        # Process in batches of 10
        for i in range(0, len(lead_ids), 10):
            batch = lead_ids[i:i + 10]
            for lead_id in batch:
                try:
                    result = await enrichment_service.enrich_lead(str(lead_id), db)
                    if "error" not in result:
                        enriched += 1
                        score = result.get("lead_score", 0)
                        tier = _score_tier(score)
                        tiers[tier] += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Enrichment failed for lead {lead_id}: {e}")
                    failed += 1

        result = {"enriched": enriched, "failed": failed, "tiers": tiers}
        await self._log_run(db, "enrich", result)
        return result

    # ─── Stage 3: Ensure Sequences ────────────────────────────

    UNIVERSAL_SEQUENCE_NAME = "Autopilot: Universal (multi-channel)"

    @staticmethod
    def _universal_steps() -> list[dict]:
        """Single multi-channel sequence: email → linkedin follow-up → more emails.

        LinkedIn step is a 1-day follow-up after the cold intro email, deliberately
        warm and brief (300-char connection request note referencing the email).
        """
        return [
            {"channel": "email",    "type": "cold_intro",         "delay_days": 0},
            {"channel": "linkedin", "type": "connection_request", "delay_days": 1},
            {"channel": "email",    "type": "follow_up_1",        "delay_days": 3},
            {"channel": "email",    "type": "follow_up_2",        "delay_days": 5},
            {"channel": "email",    "type": "breakup",            "delay_days": 7},
        ]

    async def _get_or_create_universal_sequence(self, db: AsyncSession) -> Sequence:
        """Return the active multi-channel universal sequence, creating it if missing."""
        existing = await db.execute(
            select(Sequence).where(
                and_(
                    Sequence.name == self.UNIVERSAL_SEQUENCE_NAME,
                    Sequence.is_active == True,
                )
            )
        )
        sequence = existing.scalar_one_or_none()
        if sequence:
            return sequence

        sequence = Sequence(
            name=self.UNIVERSAL_SEQUENCE_NAME,
            description="Universal multi-channel sequence: email cold intro, LinkedIn follow-up 1 day later, then email follow-ups and breakup. Content is AI-generated fresh per lead.",
            target_industry="all",
            channel="email",  # primary channel; individual steps have their own
            is_active=True,
            steps=self._universal_steps(),
            settings={
                "source": "autopilot",
                "multi_channel": True,
                "generated_at": datetime.now(IST).isoformat(),
            },
        )
        db.add(sequence)
        await db.flush()
        return sequence

    async def ensure_sequences(self, db: AsyncSession) -> dict:
        """Ensure the single universal multi-channel sequence exists.
        Sequences only define timing and step types (email/linkedin per step).
        Actual message content is generated fresh per lead by the AI engine."""
        checked = 1
        created = 0

        existing = await db.execute(
            select(Sequence).where(
                and_(
                    Sequence.name == self.UNIVERSAL_SEQUENCE_NAME,
                    Sequence.is_active == True,
                )
            )
        )
        if not existing.scalar_one_or_none():
            await self._get_or_create_universal_sequence(db)
            created = 1

        await db.commit()
        result = {"checked": checked, "created": created}
        await self._log_run(db, "sequences", result)
        return result

    # ─── Stage 4: Create Campaigns ────────────────────────────

    async def create_campaigns(
        self,
        db: AsyncSession,
        batch: LeadBatch | None = None,
    ) -> dict:
        """Enroll eligible leads into tier campaigns.

        When `batch` is provided, only leads belonging to that batch are
        considered — keeps batches as discrete waves. When None, falls back
        to the legacy behavior (any unenrolled autopilot lead) which is now
        only used by manual ad-hoc operations.
        """
        settings = await self.get_settings(db)
        aggr_config = AGGRESSIVENESS_MAP.get(settings.get("aggressiveness", "normal"), AGGRESSIVENESS_MAP["normal"])

        # Get lead IDs already in active campaigns
        enrolled_subq = (
            select(CampaignEnrollment.lead_id)
            .where(CampaignEnrollment.status == "active")
            .subquery()
        )

        # Get eligible autopilot leads (eagerly load company to avoid lazy-load crashes)
        conditions = [
            Lead.source == "autopilot",
            Lead.lead_score > 0,
            Lead.do_not_contact == False,
            Lead.consent_status != "opted_out",
            Lead.consent_status != "invalid_email",
            Lead.email.isnot(None),
            Lead.email != "",
            Lead.id.notin_(enrolled_subq),
        ]
        if batch is not None:
            conditions.append(Lead.batch_id == batch.id)

        query = (
            select(Lead)
            .options(selectinload(Lead.company))
            .where(and_(*conditions))
        )
        result = await db.execute(query)
        leads = result.scalars().all()

        # Contact guard filter
        from app.services.contact_guard import can_contact
        filtered_leads = []
        contact_guard_blocked = 0
        for lead in leads:
            allowed, _reason = await can_contact(lead, db)
            if allowed:
                filtered_leads.append(lead)
            else:
                contact_guard_blocked += 1
        if contact_guard_blocked:
            logger.info(f"Contact guard filtered out {contact_guard_blocked} leads from campaign creation")
        leads = filtered_leads

        if not leads:
            r = {"campaigns_created": 0, "leads_enrolled": 0, "reason": "no_eligible_leads"}
            await self._log_run(db, "campaigns", r)
            return r

        # Group by tier only (sequences are universal, not per-industry)
        groups: dict[str, list] = {}
        for lead in leads:
            tier = _score_tier(lead.lead_score)
            if tier == "cold" and not aggr_config["include_cold"]:
                continue
            groups.setdefault(tier, []).append(lead)

        campaigns_created = 0
        leads_enrolled = 0
        today = date.today().isoformat()
        debug_info = {"eligible_leads": len(leads), "groups": {t: len(g) for t, g in groups.items()}}

        # Use the single universal multi-channel sequence (email + linkedin steps)
        sequence = await self._get_or_create_universal_sequence(db)

        for tier, group_leads in groups.items():
            _channels, delay_mult = TIER_STRATEGY[tier]

            # Rate limit is capped by email daily limit since step 0 is email
            remaining = await rate_limiter.remaining("email")
            max_enroll = min(len(group_leads), remaining)
            if max_enroll <= 0:
                continue

            batch_label = f" {batch.batch_code}" if batch is not None else ""
            target_filter = {
                "tier": tier,
                "source": "autopilot",
            }
            if batch is not None:
                target_filter["batch_id"] = str(batch.id)
                target_filter["batch_code"] = batch.batch_code

            campaign = Campaign(
                name=f"Autopilot:{batch_label} {tier} leads ({today})",
                sequence_id=sequence.id,
                status="active",
                target_filter=target_filter,
                total_leads=max_enroll,
                started_at=datetime.now(IST),
            )
            db.add(campaign)
            await db.flush()

            now = datetime.now(IST)
            for lead in group_leads[:max_enroll]:
                first_step = sequence.steps[0] if sequence.steps else {}
                base_delay = first_step.get("delay_days", 0)
                next_step_at = now + timedelta(days=base_delay * delay_mult)

                enrollment = CampaignEnrollment(
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    sequence_id=sequence.id,
                    current_step=0,
                    status="active",
                    next_step_at=next_step_at,
                )
                db.add(enrollment)
                leads_enrolled += 1

            campaigns_created += 1

        await db.commit()
        result = {"campaigns_created": campaigns_created, "leads_enrolled": leads_enrolled, "debug": debug_info}
        await self._log_run(db, "campaigns", result)
        return result

    # ─── Status ───────────────────────────────────────────────

    async def get_status(self, db: AsyncSession) -> dict:
        enabled = await self.is_enabled(db)
        icp = await self.get_icp(db)
        settings = await self.get_settings(db)
        history = await self._get_setting(db, "autopilot_history", {"runs": []})

        today = date.today()

        # Leads discovered today
        today_count = await db.execute(
            select(func.count(Lead.id)).where(
                and_(
                    Lead.source == "autopilot",
                    func.date(Lead.created_at) == today,
                )
            )
        )
        leads_today = today_count.scalar() or 0

        # Leads in pipeline
        pipeline_count = await db.execute(
            select(func.count(Lead.id)).where(
                and_(
                    Lead.source == "autopilot",
                    Lead.stage.in_(["prospect", "contacted", "engaged", "qualified"]),
                )
            )
        )
        pipeline = pipeline_count.scalar() or 0

        # Active auto-campaigns
        camp_count = await db.execute(
            select(func.count(Campaign.id)).where(
                and_(
                    Campaign.status == "active",
                    Campaign.name.like("Autopilot:%"),
                )
            )
        )
        active_campaigns = camp_count.scalar() or 0

        return {
            "enabled": enabled,
            "leads_today": leads_today,
            "pipeline": pipeline,
            "active_campaigns": active_campaigns,
            "history": history.get("runs", [])[-5:],
            "icp": icp,
            "settings": settings,
        }

    # ─── Full Cycle ───────────────────────────────────────────

    async def run_full_cycle(
        self,
        db: AsyncSession,
        triggered_by: str = "manual",
        force: bool = False,
    ) -> dict:
        """Run one batch end-to-end: create batch → discover 20 → enrich →
        ensure sequences → enroll into campaigns. Each invocation produces
        exactly one B-xxxx batch.

        `triggered_by` is recorded on the LeadBatch row for auditability:
        - "manual" — user clicked the Generate Batch button
        - "auto_alternate_day" — daily timer fired because it's been ~2d
        - "auto_after_completion" — daily timer fired because prior batch done
        - "backfill" — only used by migration 007
        `force=True` skips the autopilot-disabled check (used by manual button)."""
        if not force and not await self.is_enabled(db):
            return {"skipped": True, "reason": "autopilot_disabled"}

        results: dict = {}

        # Create the new batch row first so every downstream step can scope to it.
        try:
            batch = await self.create_new_batch(db, triggered_by=triggered_by)
            await db.commit()
            results["batch"] = {
                "id": str(batch.id),
                "batch_code": batch.batch_code,
                "triggered_by": triggered_by,
            }
        except Exception as e:
            logger.error(f"Autopilot batch creation failed: {e}")
            return {"error": f"batch_creation_failed: {e}"}

        # Step 1: Discover up to 20 leads INTO this batch
        try:
            results["discover"] = await self.discover_leads(db, batch=batch)
        except Exception as e:
            logger.error(f"Autopilot discover failed: {e}")
            results["discover"] = {"error": str(e)}

        # Step 2: Enrich just this batch's unscored leads (not the whole DB)
        try:
            unscored = await db.execute(
                select(Lead.id).where(
                    and_(
                        Lead.batch_id == batch.id,
                        Lead.lead_score == 0,
                    )
                )
            )
            lead_ids = [str(lid) for lid in unscored.scalars().all()]
            if lead_ids:
                results["enrich"] = await self.enrich_and_score_leads(lead_ids, db)
            else:
                results["enrich"] = {"enriched": 0, "skipped": "no_unscored_leads"}
        except Exception as e:
            logger.error(f"Autopilot enrich failed: {e}")
            results["enrich"] = {"error": str(e)}

        # Step 3: Ensure sequences (singleton — universal multi-channel)
        try:
            results["sequences"] = await self.ensure_sequences(db)
        except Exception as e:
            logger.error(f"Autopilot sequences failed: {e}")
            results["sequences"] = {"error": str(e)}

        # Step 4: Enroll only THIS batch's leads into tier campaigns.
        try:
            results["campaigns"] = await self.create_campaigns(db, batch=batch)
        except Exception as e:
            logger.error(f"Autopilot campaigns failed: {e}")
            results["campaigns"] = {"error": str(e)}

        return results

    async def maybe_run_next_batch(self, db: AsyncSession) -> dict:
        """Daily decision: should a new batch be created right now?

        Rules:
        1. If there's no batch yet → fire one (triggered_by='auto_alternate_day').
        2. Reconcile: mark any active batches as complete if their leads have
           no remaining active enrollments.
        3. If the latest batch is now complete → fire one
           (triggered_by='auto_after_completion').
        4. Else if the latest batch was created more than ALTERNATE_DAY_GAP_HOURS
           ago → fire one (triggered_by='auto_alternate_day').
        5. Otherwise skip — too early.
        """
        if not await self.is_enabled(db):
            return {"skipped": True, "reason": "autopilot_disabled"}

        # Step 1 + 2: reconcile completion state up front
        await self.reconcile_batch_completion(db)

        latest = await self.get_latest_batch(db)
        if latest is None:
            logger.info("No batches yet — firing first batch via auto trigger")
            return await self.run_full_cycle(db, triggered_by="auto_alternate_day", force=True)

        if latest.status == "complete":
            logger.info(
                f"Latest batch {latest.batch_code} is complete — firing next batch"
            )
            return await self.run_full_cycle(db, triggered_by="auto_after_completion", force=True)

        # Still active — check the alternate-day timer
        now = datetime.now(IST)
        created = latest.created_at
        if created.tzinfo is None:
            # treat naive timestamps as UTC then convert
            created = created.replace(tzinfo=ZoneInfo("UTC"))
        age_hours = (now - created.astimezone(IST)).total_seconds() / 3600.0
        if age_hours >= ALTERNATE_DAY_GAP_HOURS:
            logger.info(
                f"Latest batch {latest.batch_code} is {age_hours:.1f}h old — alternate-day trigger firing"
            )
            return await self.run_full_cycle(db, triggered_by="auto_alternate_day", force=True)

        return {
            "skipped": True,
            "reason": "too_early",
            "latest_batch_code": latest.batch_code,
            "latest_batch_status": latest.status,
            "latest_batch_age_hours": round(age_hours, 1),
            "next_trigger_at_hours": ALTERNATE_DAY_GAP_HOURS,
        }


automation_engine = AutomationEngine()
