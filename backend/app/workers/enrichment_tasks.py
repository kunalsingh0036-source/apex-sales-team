"""
Celery tasks for lead/company enrichment and discovery.
Handles background enrichment, batch scoring, and lead import from Apollo.
"""

import asyncio
from sqlalchemy import select
from app.workers.celery_app import celery_app


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.enrichment_tasks.enrich_lead")
def enrich_lead(lead_id: str):
    """Run full enrichment pipeline for a single lead."""
    from app.services.enrichment_service import enrichment_service
    from app.dependencies import create_worker_session

    async def _enrich():
        async with create_worker_session()() as db:
            return await enrichment_service.enrich_lead(lead_id, db)

    return run_async(_enrich())


@celery_app.task(name="app.workers.enrichment_tasks.enrich_company")
def enrich_company(company_id: str):
    """Run enrichment pipeline for a company."""
    from app.services.enrichment_service import enrichment_service
    from app.dependencies import create_worker_session

    async def _enrich():
        async with create_worker_session()() as db:
            return await enrichment_service.enrich_company(company_id, db)

    return run_async(_enrich())


@celery_app.task(name="app.workers.enrichment_tasks.batch_score_leads")
def batch_score_leads():
    """Score all unscored leads (lead_score is None or 0)."""
    from app.services.lead_scoring import lead_scoring
    from app.dependencies import create_worker_session
    from app.models.lead import Lead, Company

    async def _batch():
        async with create_worker_session()() as db:
            result = await db.execute(
                select(Lead)
                .where(Lead.lead_score.is_(None) | (Lead.lead_score == 0))
                .limit(50)
            )
            leads = result.scalars().all()
            scored = 0

            for lead in leads:
                company_name = ""
                industry = "Other"
                employee_count = ""
                if lead.company_id:
                    comp_result = await db.execute(
                        select(Company).where(Company.id == lead.company_id)
                    )
                    company = comp_result.scalar_one_or_none()
                    if company:
                        company_name = company.name
                        industry = company.industry or "Other"
                        employee_count = str(company.employee_count or "")

                try:
                    score_result = await lead_scoring.score(
                        name=lead.full_name,
                        job_title=lead.job_title or "",
                        department=lead.department or "",
                        seniority=lead.seniority or "",
                        company_name=company_name,
                        industry=industry,
                        employee_count=employee_count,
                        city=lead.city or "",
                    )
                    lead.lead_score = score_result.get("score", 0)
                    scored += 1
                except Exception as e:
                    print(f"Error scoring lead {lead.id}: {e}")

            await db.commit()
            return {"total": len(leads), "scored": scored}

    return run_async(_batch())


@celery_app.task(name="app.workers.enrichment_tasks.import_from_apollo")
def import_from_apollo(search_params: dict):
    """
    Import leads from Apollo.io search results into the database.

    search_params: {
        job_titles: ["CEO", "Head of Procurement"],
        industries: ["technology"],
        locations: ["India"],
        company_sizes: ["51-200", "201-500"],
        max_results: 100,
    }
    """
    from app.services.lead_discovery import lead_discovery
    from app.dependencies import create_worker_session
    from app.models.lead import Lead, Company

    async def _import():
        max_results = search_params.pop("max_results", 100)
        imported = 0
        skipped = 0
        page = 1
        per_page = 25

        async with create_worker_session()() as db:
            while imported + skipped < max_results:
                result = await lead_discovery.search_people(
                    **search_params, page=page, per_page=per_page
                )
                people = result.get("people", [])
                if not people:
                    break

                for person in people:
                    email = person.get("email")

                    # Check for duplicates
                    if email:
                        existing = await db.execute(
                            select(Lead).where(Lead.email == email)
                        )
                        if existing.scalar_one_or_none():
                            skipped += 1
                            continue

                    # Create or find company
                    company_id = None
                    comp_data = person.get("company", {})
                    if comp_data.get("name"):
                        comp_result = await db.execute(
                            select(Company).where(Company.name == comp_data["name"])
                        )
                        company = comp_result.scalar_one_or_none()
                        if not company:
                            company = Company(
                                name=comp_data["name"],
                                domain=comp_data.get("domain"),
                                industry=comp_data.get("industry"),
                                employee_count=comp_data.get("employee_count"),
                                linkedin_url=comp_data.get("linkedin_url"),
                                city=comp_data.get("city"),
                            )
                            db.add(company)
                            await db.flush()
                        company_id = company.id

                    # Create lead
                    lead = Lead(
                        first_name=person.get("first_name", ""),
                        last_name=person.get("last_name", ""),
                        email=email,
                        phone=person.get("phone"),
                        linkedin_url=person.get("linkedin_url"),
                        job_title=person.get("title"),
                        seniority=person.get("seniority"),
                        department=person["departments"][0] if person.get("departments") else None,
                        city=person.get("city"),
                        company_id=company_id,
                        source="apollo",
                        stage="prospect",
                    )
                    db.add(lead)
                    imported += 1

                    if imported + skipped >= max_results:
                        break

                page += 1

            await db.commit()
            return {"imported": imported, "skipped": skipped, "total_checked": imported + skipped}

    return run_async(_import())
