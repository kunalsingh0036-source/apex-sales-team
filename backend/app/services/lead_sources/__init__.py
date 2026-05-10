"""
Lead-source registry — pluggable adapters for every place leads come from.

Apollo was the only source until now; this package replaces that monolith
with a Protocol-based adapter pattern. Every profile carries a `source`
column (see migration 010) that maps into `SOURCES` here.

Why this shape:
- One adapter per source, in its own file. Adding FHRAI/CBSE/GeM scrapers
  later is a copy-paste of the apollo adapter, not a refactor of the
  orchestrator.
- The orchestrator (automation_engine.discover_leads) doesn't know or care
  what an adapter does internally — it hands over (profile, limit) and gets
  a list[RawLead] back. Apollo, scrapers, and passive sources (CSV upload,
  website webhook) all conform to the same Protocol.
- Passive sources (csv_upload, website_form) implement search() as a no-op
  so autopilot's discovery loop doesn't accidentally pull from them. Leads
  enter through dedicated POST endpoints, not through scheduled discovery.

Public API:
- RawLead: the canonical dict shape every adapter must produce
- LeadSource: the Protocol every adapter conforms to
- get_source(name): resolves a source name to its adapter, raising
  UnknownSourceError if not registered
- SOURCES: the live registry; new adapters self-register on import below
"""

from app.services.lead_sources.base import (
    LeadSource,
    RawLead,
    UnknownSourceError,
    get_source,
    register_source,
    list_sources,
    SOURCES,
)

# Adapter modules self-register their instance in SOURCES on import.
# Order doesn't matter — registry is a dict keyed by source name.
from app.services.lead_sources import apollo as _apollo  # noqa: F401
from app.services.lead_sources import passive as _passive  # noqa: F401
from app.services.lead_sources import fhrai_scraper as _fhrai  # noqa: F401
from app.services.lead_sources import schools_scraper as _schools  # noqa: F401

__all__ = [
    "LeadSource",
    "RawLead",
    "UnknownSourceError",
    "get_source",
    "register_source",
    "list_sources",
    "SOURCES",
]
