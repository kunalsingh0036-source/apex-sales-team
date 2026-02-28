"""
Lead discovery & enrichment API endpoints.
Search for leads via Apollo.io, verify emails, enrich profiles, and import leads.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db

router = APIRouter()


class PeopleSearchRequest(BaseModel):
    job_titles: list[str] | None = None
    industries: list[str] | None = None
    locations: list[str] | None = None
    company_sizes: list[str] | None = None
    keywords: list[str] | None = None
    page: int = 1
    per_page: int = 25


class CompanySearchRequest(BaseModel):
    industries: list[str] | None = None
    locations: list[str] | None = None
    sizes: list[str] | None = None
    keywords: list[str] | None = None
    page: int = 1
    per_page: int = 25


class ImportRequest(BaseModel):
    job_titles: list[str] | None = None
    industries: list[str] | None = None
    locations: list[str] | None = None
    company_sizes: list[str] | None = None
    keywords: list[str] | None = None
    max_results: int = 100


# ─── Apollo Search ──────────────────────────────────────────────

@router.post("/search/people")
async def search_people(data: PeopleSearchRequest):
    """Search Apollo.io for people matching criteria."""
    from app.services.lead_discovery import lead_discovery
    return await lead_discovery.search_people(
        job_titles=data.job_titles,
        industries=data.industries,
        locations=data.locations,
        company_sizes=data.company_sizes,
        keywords=data.keywords,
        page=data.page,
        per_page=data.per_page,
    )


@router.post("/search/companies")
async def search_companies(data: CompanySearchRequest):
    """Search Apollo.io for companies matching criteria."""
    from app.services.lead_discovery import lead_discovery
    return await lead_discovery.search_companies(
        industries=data.industries,
        locations=data.locations,
        sizes=data.sizes,
        keywords=data.keywords,
        page=data.page,
        per_page=data.per_page,
    )


# ─── Import from Apollo ────────────────────────────────────────

@router.post("/import")
async def import_from_apollo(data: ImportRequest):
    """Import leads from Apollo.io search results into the database (async via Celery)."""
    from app.workers.enrichment_tasks import import_from_apollo
    task = import_from_apollo.delay(data.model_dump())
    return {"task_id": task.id, "status": "started", "max_results": data.max_results}


# ─── Email Verification ────────────────────────────────────────

@router.get("/verify-email")
async def verify_email(email: str = Query(...)):
    """Verify an email address using Hunter.io."""
    from app.services.lead_discovery import lead_discovery
    return await lead_discovery.verify_email(email)


@router.get("/find-email")
async def find_email(
    domain: str = Query(...),
    first_name: str = Query(...),
    last_name: str = Query(...),
):
    """Find a professional email using Hunter.io."""
    from app.services.lead_discovery import lead_discovery
    return await lead_discovery.find_email(domain, first_name, last_name)


@router.get("/domain-search")
async def domain_search(domain: str = Query(...), limit: int = Query(10)):
    """Find all emails for a domain using Hunter.io."""
    from app.services.lead_discovery import lead_discovery
    return await lead_discovery.domain_search(domain, limit=limit)


# ─── Enrichment ─────────────────────────────────────────────────

@router.post("/enrich/lead/{lead_id}")
async def enrich_lead(lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Run full enrichment pipeline for a lead."""
    from app.services.enrichment_service import enrichment_service
    return await enrichment_service.enrich_lead(str(lead_id), db)


@router.post("/enrich/company/{company_id}")
async def enrich_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Run enrichment pipeline for a company."""
    from app.services.enrichment_service import enrichment_service
    return await enrichment_service.enrich_company(str(company_id), db)


@router.post("/enrich/lead/{lead_id}/async")
async def enrich_lead_async(lead_id: uuid.UUID):
    """Run enrichment in background via Celery."""
    from app.workers.enrichment_tasks import enrich_lead
    task = enrich_lead.delay(str(lead_id))
    return {"task_id": task.id, "status": "started"}


@router.post("/score/batch")
async def batch_score():
    """Score all unscored leads in background."""
    from app.workers.enrichment_tasks import batch_score_leads
    task = batch_score_leads.delay()
    return {"task_id": task.id, "status": "started"}
