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

from app.models.lead import Lead, Company
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

    # ─── Stage 1: Discover Leads ──────────────────────────────

    async def discover_leads(self, db: AsyncSession) -> dict:
        icp = await self.get_icp(db)
        settings = await self.get_settings(db)
        aggr = AGGRESSIVENESS_MAP.get(settings.get("aggressiveness", "normal"), AGGRESSIVENESS_MAP["normal"])
        max_results = min(icp.get("max_results", 50), aggr["max_results"])

        search_result = await lead_discovery.search_people(
            job_titles=icp.get("job_titles"),
            industries=icp.get("industries"),
            locations=icp.get("locations"),
            company_sizes=icp.get("company_sizes"),
            keywords=icp.get("keywords"),
            per_page=max_results,
        )

        if "error" in search_result and search_result["error"]:
            return {"error": search_result["error"], "discovered": 0, "skipped": 0}

        people = search_result.get("people", [])
        discovered = 0
        skipped = 0

        for person in people:
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
                description=f"Auto-discovered via Apollo (autopilot)",
                extra_data={"source": "autopilot", "company": company_data.get("name", "")},
            ))
            discovered += 1

        await db.commit()
        result = {"discovered": discovered, "skipped": skipped, "total_searched": len(people)}
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

    async def ensure_sequences(self, db: AsyncSession) -> dict:
        """Ensure one universal sequence per channel exists.
        Sequences only define timing and step types. Actual message
        content is generated fresh per lead by the AI engine."""
        channels = ["email"]  # LinkedIn cold DMs not supported
        checked = 0
        created = 0

        for channel in channels:
            checked += 1
            existing = await db.execute(
                select(Sequence).where(
                    and_(
                        Sequence.target_industry == "all",
                        Sequence.channel == channel,
                        Sequence.is_active == True,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Universal 4-step sequence — timing only, no template content
            steps = [
                {"channel": channel, "type": "cold_intro", "delay_days": 0},
                {"channel": channel, "type": "follow_up_1", "delay_days": 3},
                {"channel": channel, "type": "follow_up_2", "delay_days": 5},
                {"channel": channel, "type": "breakup", "delay_days": 7},
            ]

            sequence = Sequence(
                name=f"Autopilot: Universal ({channel})",
                description=f"Universal {channel} sequence. Content is AI-generated fresh per lead.",
                target_industry="all",
                channel=channel,
                is_active=True,
                steps=steps,
                settings={"source": "autopilot", "generated_at": datetime.now(IST).isoformat()},
            )
            db.add(sequence)
            created += 1

        await db.commit()
        result = {"checked": checked, "created": created}
        await self._log_run(db, "sequences", result)
        return result

    # ─── Stage 4: Create Campaigns ────────────────────────────

    async def create_campaigns(self, db: AsyncSession) -> dict:
        settings = await self.get_settings(db)
        aggr_config = AGGRESSIVENESS_MAP.get(settings.get("aggressiveness", "normal"), AGGRESSIVENESS_MAP["normal"])

        # Get lead IDs already in active campaigns
        enrolled_subq = (
            select(CampaignEnrollment.lead_id)
            .where(CampaignEnrollment.status == "active")
            .subquery()
        )

        # Get eligible autopilot leads (eagerly load company to avoid lazy-load crashes)
        query = (
            select(Lead)
            .options(selectinload(Lead.company))
            .where(
                and_(
                    Lead.source == "autopilot",
                    Lead.lead_score > 0,
                    Lead.do_not_contact == False,
                    Lead.consent_status != "opted_out",
                    Lead.consent_status != "invalid_email",
                    Lead.id.notin_(enrolled_subq),
                )
            )
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

        for tier, group_leads in groups.items():
            channels, delay_mult = TIER_STRATEGY[tier]

            for channel in channels:
                # Skip LinkedIn — API doesn't support cold DMs to non-connections
                if channel == "linkedin":
                    continue

                # Find the universal sequence for this channel
                seq_result = await db.execute(
                    select(Sequence).where(
                        and_(
                            Sequence.target_industry == "all",
                            Sequence.channel == channel,
                            Sequence.is_active == True,
                        )
                    )
                )
                sequence = seq_result.scalar_one_or_none()
                if not sequence:
                        continue

                # Verify sequence has actual message content
                if not sequence.steps or not any(
                    step.get("body_variants") for step in sequence.steps
                ):
                    continue

                # Check rate limits before creating
                remaining = await rate_limiter.remaining(channel)
                max_enroll = min(len(group_leads), remaining)
                if max_enroll <= 0:
                    continue

                campaign = Campaign(
                    name=f"Autopilot: {tier} leads ({today})",
                    sequence_id=sequence.id,
                    status="active",
                    target_filter={
                        "industry": industry,
                        "tier": tier,
                        "source": "autopilot",
                        "channel": channel,
                    },
                    total_leads=max_enroll,
                    started_at=datetime.now(IST),
                )
                db.add(campaign)
                await db.flush()

                now = datetime.now(IST)
                for lead in group_leads[:max_enroll]:
                    # Calculate first step time with delay multiplier
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
        result = {"campaigns_created": campaigns_created, "leads_enrolled": leads_enrolled}
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

    async def run_full_cycle(self, db: AsyncSession) -> dict:
        if not await self.is_enabled(db):
            return {"skipped": True, "reason": "autopilot_disabled"}

        results = {}

        # Step 1: Discover
        try:
            results["discover"] = await self.discover_leads(db)
        except Exception as e:
            logger.error(f"Autopilot discover failed: {e}")
            results["discover"] = {"error": str(e)}

        # Step 2: Enrich unscored autopilot leads
        try:
            unscored = await db.execute(
                select(Lead.id).where(
                    and_(Lead.source == "autopilot", Lead.lead_score == 0)
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

        # Step 3: Ensure sequences
        try:
            results["sequences"] = await self.ensure_sequences(db)
        except Exception as e:
            logger.error(f"Autopilot sequences failed: {e}")
            results["sequences"] = {"error": str(e)}

        # Step 4: Campaigns (always run — pipeline refills when approval queue is empty)
        try:
            results["campaigns"] = await self.create_campaigns(db)
        except Exception as e:
            logger.error(f"Autopilot campaigns failed: {e}")
            results["campaigns"] = {"error": str(e)}

        return results


automation_engine = AutomationEngine()
