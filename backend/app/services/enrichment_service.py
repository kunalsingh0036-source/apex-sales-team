"""
Enrichment service — enriches lead and company data from external sources.
Combines Proxycurl (LinkedIn data), Apollo.io (contact data), and Hunter.io (email).
"""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models.lead import Lead, Company
from app.models.activity import Activity


class EnrichmentService:
    """Lead and company data enrichment from multiple sources."""

    PROXYCURL_BASE = "https://nubela.co/proxycurl/api"

    # ─── Proxycurl (LinkedIn Enrichment) ────────────────────────

    async def enrich_linkedin_profile(self, linkedin_url: str) -> dict:
        """
        Enrich a lead using their LinkedIn profile URL via Proxycurl.

        Returns structured data: headline, summary, experience, education, skills.
        """
        settings = get_settings()
        if not settings.proxycurl_api_key:
            return {"error": "Proxycurl API key not configured"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.PROXYCURL_BASE}/v2/linkedin",
                params={"url": linkedin_url, "use_cache": "if-present"},
                headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "first_name": data.get("first_name"),
                    "last_name": data.get("last_name"),
                    "headline": data.get("headline"),
                    "summary": data.get("summary"),
                    "city": data.get("city"),
                    "state": data.get("state"),
                    "country": data.get("country_full_name"),
                    "experiences": [
                        {
                            "title": exp.get("title"),
                            "company": exp.get("company"),
                            "starts_at": exp.get("starts_at"),
                            "ends_at": exp.get("ends_at"),
                            "description": exp.get("description"),
                        }
                        for exp in (data.get("experiences") or [])[:5]
                    ],
                    "education": [
                        {
                            "school": edu.get("school"),
                            "degree": edu.get("degree_name"),
                            "field": edu.get("field_of_study"),
                        }
                        for edu in (data.get("education") or [])[:3]
                    ],
                    "skills": data.get("skills", [])[:20],
                    "connections": data.get("connections"),
                    "profile_pic_url": data.get("profile_pic_url"),
                }
            return {"error": resp.text}

    async def enrich_linkedin_company(self, linkedin_url: str) -> dict:
        """Enrich a company using its LinkedIn company page URL."""
        settings = get_settings()
        if not settings.proxycurl_api_key:
            return {"error": "Proxycurl API key not configured"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.PROXYCURL_BASE}/linkedin/company",
                params={"url": linkedin_url, "use_cache": "if-present"},
                headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "industry": data.get("industry"),
                    "company_size": data.get("company_size_on_linkedin"),
                    "headquarters": data.get("hq", {}).get("city"),
                    "founded_year": data.get("founded_year"),
                    "website": data.get("website"),
                    "specialities": data.get("specialities", []),
                    "follower_count": data.get("follower_count"),
                }
            return {"error": resp.text}

    # ─── Full Enrichment Pipeline ───────────────────────────────

    async def enrich_lead(self, lead_id: str, db: AsyncSession) -> dict:
        """
        Run full enrichment pipeline for a lead:
        1. Proxycurl LinkedIn enrichment (if LinkedIn URL available)
        2. Apollo.io person details (if email available)
        3. Hunter.io email verification (if email available)
        4. AI lead scoring
        """
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            return {"error": "Lead not found"}

        enrichment_data = {}
        enriched_fields = []

        # 1. LinkedIn enrichment
        if lead.linkedin_url:
            linkedin_data = await self.enrich_linkedin_profile(lead.linkedin_url)
            if "error" not in linkedin_data:
                enrichment_data["linkedin"] = linkedin_data
                # Update lead fields if empty
                if not lead.job_title and linkedin_data.get("headline"):
                    lead.job_title = linkedin_data["headline"]
                    enriched_fields.append("job_title")
                if linkedin_data.get("city"):
                    lead.city = linkedin_data["city"]
                    enriched_fields.append("city")

        # 2. Apollo person match
        from app.services.lead_discovery import lead_discovery
        if lead.email or lead.linkedin_url:
            apollo_data = await lead_discovery.get_person_details(
                email=lead.email or "",
                linkedin_url=lead.linkedin_url or "",
            )
            if "error" not in apollo_data and apollo_data:
                enrichment_data["apollo"] = apollo_data
                if not lead.phone and apollo_data.get("phone_numbers"):
                    phones = apollo_data["phone_numbers"]
                    if phones:
                        lead.phone = phones[0].get("sanitized_number", "")
                        enriched_fields.append("phone")
                if not lead.department and apollo_data.get("departments"):
                    lead.department = apollo_data["departments"][0] if apollo_data["departments"] else None
                    enriched_fields.append("department")
                if not lead.seniority and apollo_data.get("seniority"):
                    lead.seniority = apollo_data["seniority"]
                    enriched_fields.append("seniority")

        # 3. Email verification
        if lead.email:
            verification = await lead_discovery.verify_email(lead.email)
            enrichment_data["email_verification"] = verification
            if verification.get("status") == "invalid":
                lead.consent_status = "invalid_email"
                enriched_fields.append("consent_status")

        # 4. AI Lead Scoring
        from app.services.lead_scoring import lead_scoring
        company_name = ""
        industry = "Other"
        employee_count = ""
        if lead.company_id:
            comp_result = await db.execute(select(Company).where(Company.id == lead.company_id))
            company = comp_result.scalar_one_or_none()
            if company:
                company_name = company.name
                industry = company.industry or "Other"
                employee_count = str(company.employee_count or "")

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
        if "score" in score_result:
            lead.lead_score = score_result["score"]
            enriched_fields.append("lead_score")
            enrichment_data["scoring"] = score_result

        # Save enrichment data
        lead.enrichment_data = {**(lead.enrichment_data or {}), **enrichment_data}
        enriched_fields.append("enrichment_data")

        # Log activity
        activity = Activity(
            lead_id=lead.id,
            type="enrichment",
            channel="system",
            description=f"Enriched {len(enriched_fields)} fields: {', '.join(enriched_fields)}",
            extra_data={"enriched_fields": enriched_fields},
        )
        db.add(activity)
        await db.commit()

        return {
            "lead_id": str(lead.id),
            "enriched_fields": enriched_fields,
            "lead_score": lead.lead_score,
            "enrichment_data": enrichment_data,
        }

    async def enrich_company(self, company_id: str, db: AsyncSession) -> dict:
        """
        Enrich a company record:
        1. Proxycurl LinkedIn company enrichment
        2. Hunter.io domain search for contacts
        """
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return {"error": "Company not found"}

        enrichment_data = {}
        enriched_fields = []

        # LinkedIn company enrichment
        if company.linkedin_url:
            linkedin_data = await self.enrich_linkedin_company(company.linkedin_url)
            if "error" not in linkedin_data:
                enrichment_data["linkedin"] = linkedin_data
                if not company.industry and linkedin_data.get("industry"):
                    company.industry = linkedin_data["industry"]
                    enriched_fields.append("industry")
                if not company.employee_count and linkedin_data.get("company_size"):
                    try:
                        size_parts = str(linkedin_data["company_size"]).split("-")
                        company.employee_count = int(size_parts[-1].strip().replace(",", ""))
                    except (ValueError, IndexError):
                        pass

        # Domain search for contacts
        if company.domain:
            from app.services.lead_discovery import lead_discovery
            domain_data = await lead_discovery.domain_search(company.domain, limit=10)
            if "error" not in domain_data:
                enrichment_data["domain_contacts"] = domain_data

        company.enrichment_data = {**(company.enrichment_data or {}), **enrichment_data}
        await db.commit()

        return {
            "company_id": str(company.id),
            "enriched_fields": enriched_fields,
            "enrichment_data": enrichment_data,
        }


enrichment_service = EnrichmentService()
