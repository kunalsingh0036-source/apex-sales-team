"""
Lead discovery service.
Integrates with Apollo.io for people/company search and Hunter.io for email verification.
"""

import httpx
from app.config import get_settings


class LeadDiscoveryService:
    """Discover leads from external data sources."""

    APOLLO_BASE = "https://api.apollo.io/v1"
    HUNTER_BASE = "https://api.hunter.io/v2"

    # ─── Apollo.io ──────────────────────────────────────────────

    async def search_people(
        self,
        job_titles: list[str] | None = None,
        industries: list[str] | None = None,
        locations: list[str] | None = None,
        company_sizes: list[str] | None = None,
        keywords: list[str] | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """
        Search Apollo.io for people matching criteria.

        Args:
            job_titles: e.g. ["Head of Procurement", "VP Operations", "CEO"]
            industries: e.g. ["technology", "hospitality", "banking"]
            locations: e.g. ["India", "Mumbai", "Delhi NCR"]
            company_sizes: e.g. ["51-200", "201-500", "501-1000"]
            keywords: Free-text search keywords
            page: Page number
            per_page: Results per page (max 100)
        """
        settings = get_settings()
        if not settings.apollo_api_key:
            return {"error": "Apollo API key not configured", "people": [], "total": 0}

        payload: dict = {
            "page": page,
            "per_page": min(per_page, 100),
        }
        if job_titles:
            payload["person_titles"] = job_titles
        if industries:
            payload["organization_industry_tag_ids"] = industries
        if locations:
            payload["person_locations"] = locations
        if company_sizes:
            payload["organization_num_employees_ranges"] = company_sizes
        if keywords:
            payload["q_keywords"] = " ".join(keywords)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.APOLLO_BASE}/mixed_people/search",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                    "X-Api-Key": settings.apollo_api_key,
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                people = data.get("people", [])
                return {
                    "people": [
                        {
                            "first_name": p.get("first_name", ""),
                            "last_name": p.get("last_name", ""),
                            "name": p.get("name", ""),
                            "title": p.get("title", ""),
                            "email": p.get("email"),
                            "phone": p.get("phone_numbers", [{}])[0].get("sanitized_number") if p.get("phone_numbers") else None,
                            "linkedin_url": p.get("linkedin_url"),
                            "city": p.get("city", ""),
                            "state": p.get("state", ""),
                            "country": p.get("country", ""),
                            "seniority": p.get("seniority", ""),
                            "departments": p.get("departments", []),
                            "company": {
                                "name": p.get("organization", {}).get("name", ""),
                                "domain": p.get("organization", {}).get("primary_domain", ""),
                                "industry": p.get("organization", {}).get("industry", ""),
                                "employee_count": p.get("organization", {}).get("estimated_num_employees"),
                                "city": p.get("organization", {}).get("city", ""),
                                "linkedin_url": p.get("organization", {}).get("linkedin_url", ""),
                            },
                        }
                        for p in people
                    ],
                    "total": data.get("pagination", {}).get("total_entries", 0),
                    "page": page,
                    "per_page": per_page,
                }
            else:
                return {"error": resp.text, "people": [], "total": 0}

    async def search_companies(
        self,
        industries: list[str] | None = None,
        locations: list[str] | None = None,
        sizes: list[str] | None = None,
        keywords: list[str] | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """Search Apollo.io for companies matching criteria."""
        settings = get_settings()
        if not settings.apollo_api_key:
            return {"error": "Apollo API key not configured", "organizations": [], "total": 0}

        payload: dict = {"page": page, "per_page": min(per_page, 100)}
        if industries:
            payload["organization_industry_tag_ids"] = industries
        if locations:
            payload["organization_locations"] = locations
        if sizes:
            payload["organization_num_employees_ranges"] = sizes
        if keywords:
            payload["q_organization_keyword_tags"] = keywords

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.APOLLO_BASE}/mixed_companies/search",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": settings.apollo_api_key,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                orgs = data.get("organizations", [])
                return {
                    "organizations": [
                        {
                            "name": o.get("name", ""),
                            "domain": o.get("primary_domain", ""),
                            "industry": o.get("industry", ""),
                            "employee_count": o.get("estimated_num_employees"),
                            "city": o.get("city", ""),
                            "state": o.get("state", ""),
                            "country": o.get("country", ""),
                            "linkedin_url": o.get("linkedin_url", ""),
                            "logo_url": o.get("logo_url", ""),
                            "annual_revenue": o.get("annual_revenue"),
                        }
                        for o in orgs
                    ],
                    "total": data.get("pagination", {}).get("total_entries", 0),
                    "page": page,
                    "per_page": per_page,
                }
            return {"error": resp.text, "organizations": [], "total": 0}

    async def get_person_details(self, email: str = "", linkedin_url: str = "") -> dict:
        """Get enriched person details from Apollo."""
        settings = get_settings()
        if not settings.apollo_api_key:
            return {"error": "Apollo API key not configured"}

        payload: dict = {}
        if email:
            payload["email"] = email
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.APOLLO_BASE}/people/match",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": settings.apollo_api_key,
                },
            )
            if resp.status_code == 200:
                return resp.json().get("person", {})
            return {"error": resp.text}

    # ─── Hunter.io ──────────────────────────────────────────────

    async def verify_email(self, email: str) -> dict:
        """
        Verify an email address using Hunter.io.

        Returns:
            status: "valid", "invalid", "accept_all", "webmail", "disposable", "unknown"
            score: 0-100 confidence score
        """
        settings = get_settings()
        if not settings.hunter_api_key:
            return {"error": "Hunter API key not configured", "status": "unknown", "score": 0}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.HUNTER_BASE}/email-verifier",
                params={"email": email, "api_key": settings.hunter_api_key},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "status": data.get("status", "unknown"),
                    "score": data.get("score", 0),
                    "result": data.get("result", "unknown"),
                    "smtp_check": data.get("smtp_check", False),
                    "mx_records": data.get("mx_records", False),
                }
            return {"error": resp.text, "status": "unknown", "score": 0}

    async def find_email(self, domain: str, first_name: str, last_name: str) -> dict:
        """Find a professional email address using Hunter.io email finder."""
        settings = get_settings()
        if not settings.hunter_api_key:
            return {"error": "Hunter API key not configured"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.HUNTER_BASE}/email-finder",
                params={
                    "domain": domain,
                    "first_name": first_name,
                    "last_name": last_name,
                    "api_key": settings.hunter_api_key,
                },
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "email": data.get("email"),
                    "score": data.get("score", 0),
                    "position": data.get("position"),
                    "sources": len(data.get("sources", [])),
                }
            return {"error": resp.text}

    async def domain_search(self, domain: str, limit: int = 10) -> dict:
        """Find all email addresses for a domain using Hunter.io."""
        settings = get_settings()
        if not settings.hunter_api_key:
            return {"error": "Hunter API key not configured"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.HUNTER_BASE}/domain-search",
                params={
                    "domain": domain,
                    "limit": limit,
                    "api_key": settings.hunter_api_key,
                },
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "domain": data.get("domain"),
                    "organization": data.get("organization"),
                    "emails": [
                        {
                            "email": e.get("value"),
                            "type": e.get("type"),
                            "confidence": e.get("confidence"),
                            "first_name": e.get("first_name"),
                            "last_name": e.get("last_name"),
                            "position": e.get("position"),
                            "department": e.get("department"),
                        }
                        for e in data.get("emails", [])
                    ],
                }
            return {"error": resp.text}


lead_discovery = LeadDiscoveryService()
