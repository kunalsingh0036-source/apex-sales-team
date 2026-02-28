"""
Celery tasks for AI operations.
Handles batch scoring, message generation, and trend analysis.
"""

import asyncio
from app.workers.celery_app import celery_app


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.ai_tasks.score_lead")
def score_lead(
    lead_id: str,
    name: str,
    job_title: str,
    department: str,
    seniority: str,
    company_name: str,
    industry: str,
    employee_count: str,
    city: str = "",
    events: str = "",
):
    """Score a single lead using Claude."""
    from app.services.ai_engine import ai_engine

    async def _score():
        result = await ai_engine.score_lead(
            name=name,
            job_title=job_title,
            department=department,
            seniority=seniority,
            company_name=company_name,
            industry=industry,
            employee_count=employee_count,
            city=city,
            events=events,
        )
        return {"lead_id": lead_id, **result}

    return run_async(_score())


@celery_app.task(name="app.workers.ai_tasks.generate_message")
def generate_message(
    lead_name: str,
    lead_title: str,
    lead_company: str,
    lead_industry: str,
    channel: str,
    message_type: str = "cold_intro",
    context: str = "",
):
    """Generate a personalized outreach message."""
    from app.services.ai_engine import ai_engine

    async def _generate():
        return await ai_engine.generate_outreach_message(
            lead_name=lead_name,
            lead_title=lead_title,
            lead_company=lead_company,
            lead_industry=lead_industry,
            channel=channel,
            message_type=message_type,
            context=context,
        )

    return run_async(_generate())


@celery_app.task(name="app.workers.ai_tasks.classify_response")
def classify_response(message_text: str):
    """Classify an inbound message."""
    from app.services.ai_engine import ai_engine

    async def _classify():
        return await ai_engine.classify_response(message_text)

    return run_async(_classify())
