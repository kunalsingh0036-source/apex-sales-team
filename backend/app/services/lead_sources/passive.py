"""
Passive source adapters — sources that don't do scheduled discovery.

CSV upload and website-form leads enter via dedicated POST endpoints
(/leads/bulk-import and /leads/inbound-webhook). They're still represented
in the registry so the profile editor's source dropdown can show them,
and so the orchestrator's dispatch never trips on an unknown source name.

The contract: search() returns [] no matter what. If autopilot ever tries
to discover into a passive profile, nothing happens — which is the right
behavior (these profiles' leads come from outside the discovery loop).
"""

from __future__ import annotations

import logging

from app.models.lead import LeadProfile
from app.services.lead_sources.base import RawLead, register_source

logger = logging.getLogger(__name__)


class PassiveSource:
    """A source whose leads arrive via external POST, not internal discovery."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description

    async def search(self, profile: LeadProfile | None, limit: int) -> list[RawLead]:
        # If the orchestrator dispatched here, it's a config mistake — log
        # so it's visible in autopilot_history, then return [] so the batch
        # continues without crashing. Tolerate profile=None so test harnesses
        # and unconfigured callers don't see AttributeError.
        profile_code = getattr(profile, "code", "<none>")
        logger.info(
            f"Passive source {self.name!r} called via discovery for profile "
            f"{profile_code} — no-op (passive sources receive leads via POST)"
        )
        return []


# Register the two passive sources we already have endpoints for.
register_source(PassiveSource(
    name="csv_upload",
    description="CSV bulk import — POST /api/v1/leads/bulk-import",
))
register_source(PassiveSource(
    name="website_form",
    description="Website contact form — POST /api/v1/leads/inbound-webhook",
))
