"""
Celery tasks for autopilot automation.
Handles scheduled and manual triggers for lead discovery, enrichment,
sequence generation, and campaign creation.
"""

import asyncio
import logging
from sqlalchemy import select, and_, func
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.automation_tasks.autopilot_daily")
def autopilot_daily():
    """Daily autopilot run: discover + enrich + ensure sequences. Runs at 8 AM IST."""
    from app.services.automation_engine import automation_engine
    from app.dependencies import create_worker_session
    from app.models.lead import Lead

    async def _run():
        async with create_worker_session()() as db:
            if not await automation_engine.is_enabled(db):
                return {"skipped": True, "reason": "autopilot_disabled"}

            results = {}

            # Discover
            try:
                results["discover"] = await automation_engine.discover_leads(db)
            except Exception as e:
                results["discover"] = {"error": str(e)}

            # Enrich unscored autopilot leads
            try:
                unscored = await db.execute(
                    select(Lead.id).where(
                        and_(Lead.source == "autopilot", Lead.lead_score == 0)
                    )
                )
                lead_ids = [str(lid) for lid in unscored.scalars().all()]
                if lead_ids:
                    results["enrich"] = await automation_engine.enrich_and_score_leads(lead_ids, db)
                else:
                    results["enrich"] = {"enriched": 0, "note": "no_unscored_leads"}
            except Exception as e:
                results["enrich"] = {"error": str(e)}

            # Ensure sequences
            try:
                results["sequences"] = await automation_engine.ensure_sequences(db)
            except Exception as e:
                results["sequences"] = {"error": str(e)}

            return results

    return run_async(_run())


@celery_app.task(name="app.workers.automation_tasks.autopilot_weekly")
def autopilot_weekly():
    """Weekly campaign creation. Runs Monday 7:30 AM IST."""
    from app.services.automation_engine import automation_engine
    from app.dependencies import create_worker_session

    async def _run():
        async with create_worker_session()() as db:
            if not await automation_engine.is_enabled(db):
                return {"skipped": True, "reason": "autopilot_disabled"}
            return await automation_engine.create_campaigns(db)

    return run_async(_run())


@celery_app.task(name="app.workers.automation_tasks.autopilot_full_cycle")
def autopilot_full_cycle():
    """Full autopilot cycle — all stages in sequence."""
    from app.services.automation_engine import automation_engine
    from app.dependencies import create_worker_session

    async def _run():
        async with create_worker_session()() as db:
            return await automation_engine.run_full_cycle(db)

    return run_async(_run())


@celery_app.task(name="app.workers.automation_tasks.ensure_review_queue")
def ensure_review_queue():
    """Keep the content_review queue full. If empty, trigger pipeline to refill."""
    from app.services.automation_engine import automation_engine
    from app.services.outreach_orchestrator import orchestrator
    from app.dependencies import create_worker_session
    from app.models.message import Message
    from app.models.sequence import CampaignEnrollment

    async def _run():
        async with create_worker_session()() as db:
            if not await automation_engine.is_enabled(db):
                return {"skipped": True, "reason": "autopilot_disabled"}

            # Count messages waiting for review
            review_count = (await db.execute(
                select(func.count()).select_from(Message).where(
                    Message.status == "content_review",
                    Message.direction == "outbound",
                )
            )).scalar() or 0

            if review_count > 0:
                return {"status": "queue_has_items", "review_count": review_count}

            # Count active enrollments with pending steps
            active_enrollments = (await db.execute(
                select(func.count()).select_from(CampaignEnrollment).where(
                    CampaignEnrollment.status == "active",
                )
            )).scalar() or 0

            if active_enrollments > 0:
                # Advance existing enrollments to generate messages
                logger.info(
                    f"Review queue empty, {active_enrollments} active enrollments. Advancing sequences."
                )
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                result = await db.execute(
                    select(CampaignEnrollment).where(
                        CampaignEnrollment.status == "active",
                        CampaignEnrollment.next_step_at <= now,
                    ).limit(50)
                )
                enrollments = result.scalars().all()
                advanced = 0
                for enrollment in enrollments:
                    try:
                        if await orchestrator.advance_enrollment(enrollment, db):
                            advanced += 1
                    except Exception as e:
                        logger.error(f"Error advancing enrollment {enrollment.id}: {e}")
                await db.commit()
                return {"status": "advanced_enrollments", "advanced": advanced}

            # Both empty: run full pipeline
            logger.info("Review queue AND pipeline empty. Running full autopilot cycle.")
            return await automation_engine.run_full_cycle(db)

    return run_async(_run())


@celery_app.task(name="app.workers.automation_tasks.autopilot_trigger")
def autopilot_trigger(stage: str):
    """Manual trigger for individual autopilot stages."""
    from app.services.automation_engine import automation_engine
    from app.dependencies import create_worker_session
    from app.models.lead import Lead

    async def _run():
        async with create_worker_session()() as db:
            if stage == "discover":
                return await automation_engine.discover_leads(db)
            elif stage == "enrich":
                unscored = await db.execute(
                    select(Lead.id).where(
                        and_(Lead.source == "autopilot", Lead.lead_score == 0)
                    )
                )
                lead_ids = [str(lid) for lid in unscored.scalars().all()]
                if lead_ids:
                    return await automation_engine.enrich_and_score_leads(lead_ids, db)
                return {"enriched": 0, "note": "no_unscored_leads"}
            elif stage == "sequences":
                return await automation_engine.ensure_sequences(db)
            elif stage == "campaigns":
                return await automation_engine.create_campaigns(db)
            elif stage == "full":
                return await automation_engine.run_full_cycle(db)
            else:
                return {"error": f"Unknown stage: {stage}"}

    return run_async(_run())
