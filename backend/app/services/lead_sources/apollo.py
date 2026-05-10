"""
Apollo.io adapter — wraps the existing search_people() in lead_discovery.py.

We keep the actual HTTP/JSON wrangling in lead_discovery.LeadDiscoveryService
(it's also used by the manual /discovery API route) and just translate
between the LeadSource Protocol's RawLead shape and Apollo's wire format.

Empty-array contract: returns [] on rate-limit, missing-key, or upstream
error. Errors are logged (lead_discovery already does this) but not raised
— the orchestrator treats an empty discovery as "tried, found nothing,
will rotate to a different profile next time."
"""

from __future__ import annotations

import logging

from app.models.lead import LeadProfile
from app.services.lead_discovery import lead_discovery
from app.services.lead_sources.base import LeadSource, RawLead, register_source

logger = logging.getLogger(__name__)


class ApolloSource:
    """Pulls people from Apollo.io's mixed_people/api_search endpoint."""

    name = "apollo"

    async def search(self, profile: LeadProfile, limit: int) -> list[RawLead]:
        params = profile.search_params or {}

        # Apollo accepts up to 100 per page. We over-fetch by 3x because
        # autopilot dedupes against existing leads — without over-fetch a
        # batch in a saturated segment lands at 4-5 leads instead of 20.
        per_page = min(max(limit * 3, limit), 100)

        result = await lead_discovery.search_people(
            job_titles=params.get("job_titles"),
            industries=params.get("industries"),
            locations=params.get("locations"),
            company_sizes=params.get("company_sizes"),
            keywords=params.get("keywords"),
            per_page=per_page,
        )

        if "error" in result and result["error"]:
            logger.warning(
                f"Apollo returned error for profile {profile.code}: {result['error']}"
            )
            return []

        people = result.get("people", []) or []
        # Apollo's response is already shaped close to RawLead. We pass it
        # through as-is — automation_engine.discover_leads consumes the
        # legacy shape (first_name, last_name, email, title, company:{...}).
        # When we add stricter typing we'll normalize here.
        return people  # type: ignore[return-value]


# Register on import so app.services.lead_sources.__init__ pulls us in.
register_source(ApolloSource())
