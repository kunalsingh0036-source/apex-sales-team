"""
Source-adapter Protocol + registry. Pure interface, no I/O.

Adapter modules import this and call register_source() at import time
to add themselves to the registry. The orchestrator imports get_source()
to dispatch by profile.source string.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable

from app.models.lead import LeadProfile


class RawLead(TypedDict, total=False):
    """The shape every adapter must produce.

    Mirrors the columns Lead/Company need at insertion time, with optional
    extras under `extra_data`. Adapter authors should never invent new
    top-level keys — extend `extra_data` instead so the orchestrator's
    ingestion logic stays stable.
    """
    first_name: str
    last_name: str
    name: str               # full display name; used as fallback if first/last empty
    email: str | None
    phone: str | None
    linkedin_url: str | None
    title: str              # job title
    seniority: str | None
    departments: list[str]
    city: str
    state: str
    country: str
    company: dict           # { name, domain, industry, employee_count, ... }
    extra_data: dict        # adapter-specific metadata stashed on the Lead


@runtime_checkable
class LeadSource(Protocol):
    """Protocol every source adapter must satisfy.

    `name` is the registry key — must match what's stored in
    lead_profiles.source. `search` is the only required method; adapters
    that can't do discovery (CSV upload, website webhook) implement it
    as a no-op returning [] and rely on dedicated ingestion endpoints
    for their lead intake.
    """

    name: str

    async def search(
        self,
        profile: LeadProfile,
        limit: int,
    ) -> list[RawLead]:
        """Return up to `limit` raw leads matching the profile's search_params.

        Adapters should:
        - Honor `limit` strictly (orchestrator caps at BATCH_SIZE).
        - Return an empty list rather than raising when the upstream is
          empty / rate-limited / unauthenticated. The orchestrator logs
          empty discoveries; raising would mark the whole batch failed.
        - Catch their own transient errors. Bubble up only programmer bugs.
        """
        ...


class UnknownSourceError(KeyError):
    """Raised when profile.source doesn't map to a registered adapter."""

    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name = name
        self.available = available

    def __str__(self) -> str:
        return f"No source registered for {self.name!r}. Available: {self.available}"


SOURCES: dict[str, LeadSource] = {}


def register_source(source: LeadSource) -> None:
    """Add a source adapter to the global registry. Idempotent — re-registering
    the same name overrides the prior instance, so module re-imports are safe."""
    if not isinstance(source, LeadSource):
        # Will only fail if Protocol contract isn't met (missing `name` attr
        # or missing/non-async `search` method). Better to fail loud at
        # registration time than mysteriously at dispatch time.
        raise TypeError(
            f"Object {source!r} does not conform to LeadSource Protocol "
            f"(needs `name: str` attribute and async `search(profile, limit)` method)"
        )
    SOURCES[source.name] = source


def get_source(name: str) -> LeadSource:
    """Resolve a source name to its adapter. Raises UnknownSourceError if
    the name isn't registered (e.g. a profile referenced a source that was
    deleted, or a typo in the migration)."""
    src = SOURCES.get(name)
    if src is None:
        raise UnknownSourceError(name, sorted(SOURCES.keys()))
    return src


def list_sources() -> list[str]:
    """Sorted list of registered source names — used by the API to power
    the source dropdown in the profile editor."""
    return sorted(SOURCES.keys())
