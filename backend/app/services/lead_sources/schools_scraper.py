"""
Indian schools scraper — uses schools.org.in's state-by-state CBSE directory.

CBSE's official portal (cbseaff.nic.in / saras.cbse.gov.in) is unreliable
(503s, NAME_NOT_RESOLVED) and CISCE moved their school locator behind a
form. schools.org.in aggregates the same data from public sources and
serves it on plain HTML pages with no anti-bot challenges. It's the right
primary source for the P-schools-india profile.

Strategy:
- profile.search_params.locations selects which state pages to scrape.
- "India" is treated as "all states"; we pick a rotating subset to fan out.
- Each state page lists schools as `<a class="list-group-item">` anchors
  with name, city/area, and a link to a detail page.
- For batch-of-20 use we don't follow detail links (would be 20x slower);
  Hunter.io domain enrichment fills in contact info downstream.

Limitations:
- schools.org.in only publishes a "top" subset per state, not every school.
  For exhaustive coverage we'd need UDISE+ government data — separate work.
- Names come uppercased and are normalized to Title Case for friendlier
  outreach copy (same as FHRAI).
- Phone/email aren't on the list page; deferred to enrichment downstream.
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from app.models.lead import LeadProfile
from app.services.browser import browser_service
from app.services.lead_sources.base import LeadSource, RawLead, register_source

logger = logging.getLogger(__name__)


SCHOOLS_BASE = "https://schools.org.in"

# State slugs schools.org.in uses on URLs of the form
# https://schools.org.in/cbse/schools-in-<slug>
# Most populous + business-dense states first so default rotation hits them.
DEFAULT_STATE_SLUGS = [
    "delhi",
    "maharashtra",
    "karnataka",
    "tamil-nadu",
    "uttar-pradesh",
    "gujarat",
    "west-bengal",
    "telangana",
    "haryana",
    "rajasthan",
    "kerala",
    "punjab",
]


def _state_slug(name: str) -> str:
    """Normalize a state name (e.g. "Tamil Nadu") into the slug format
    schools.org.in uses on URLs (lowercase, dash-separated)."""
    return name.lower().strip().replace(" ", "-")


class SchoolsScraper:
    """Scrapes Indian CBSE-affiliated schools from schools.org.in."""

    name = "schools_scraper"
    description = "Indian CBSE schools directory via schools.org.in"

    def __init__(
        self,
        base_url: str = SCHOOLS_BASE,
        page_load_timeout_ms: int = 30_000,
    ) -> None:
        self.base_url = base_url
        self.page_load_timeout_ms = page_load_timeout_ms

    async def search(self, profile: LeadProfile, limit: int) -> list[RawLead]:
        params = (profile.search_params or {}) if profile is not None else {}
        locations = params.get("locations") or []

        # Decide which state slugs to scrape. If the profile names specific
        # Indian states we use those; otherwise rotate through defaults.
        explicit = [
            _state_slug(loc) for loc in locations
            if loc.lower() not in ("india", "")
        ]
        slugs = explicit or DEFAULT_STATE_SLUGS

        results: list[RawLead] = []
        for slug in slugs:
            if len(results) >= limit:
                break
            try:
                html = await self._fetch_state_page(slug)
            except Exception as e:
                logger.info(f"Schools state '{slug}' fetch failed: {e}")
                continue
            try:
                state_results = self.parse_state_page(html, state_slug=slug)
            except Exception as e:
                logger.error(f"Schools state '{slug}' parse failed: {e}")
                continue

            # Diagnostic: when a state returns 0, log enough to tell whether
            # the page was bot-blocked (small HTML, "Cloudflare" / "captcha"
            # markers) vs a real parser miss vs an empty state directory.
            if not state_results:
                lower = html[:5000].lower()
                hints = []
                if "cloudflare" in lower: hints.append("cloudflare")
                if "captcha" in lower: hints.append("captcha")
                if "denied" in lower: hints.append("access-denied")
                if "<title>just a moment" in lower: hints.append("cf-challenge")
                hint_str = f" hints={hints}" if hints else ""
                logger.info(
                    f"Schools state '{slug}' parsed 0 schools "
                    f"(html_bytes={len(html)}{hint_str})"
                )

            results.extend(state_results)

        return results[:limit]

    async def _fetch_state_page(self, state_slug: str) -> str:
        """Fetch one state's CBSE schools list page via Playwright.

        Playwright (vs plain httpx) lets us reuse the existing BrowserService
        infrastructure and tolerate any future JS-rendering schools.org.in
        adds. The site is plain HTML today; this is forward-proofing.
        """
        url = f"{self.base_url}/cbse/schools-in-{state_slug}"
        async with browser_service.page() as page:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.page_load_timeout_ms,
            )
            return await page.content()

    # ─── Parsing (pure function) ────────────────────────────────

    def parse_state_page(self, html: str, state_slug: str = "") -> list[RawLead]:
        """Extract `<a class="list-group-item">` school entries.

        Pure function — unit tested against tests/fixtures/schools_sample.html.
        """
        soup = BeautifulSoup(html, "lxml")
        results: list[RawLead] = []

        for anchor in soup.select("a.list-group-item"):
            lead = self._extract_school(anchor, state_slug)
            if lead:
                results.append(lead)

        return results

    def _extract_school(self, anchor: Any, state_slug: str) -> RawLead | None:
        """Pull fields from a single school anchor entry."""
        # Strip the leading "➲" decoration and trailing whitespace.
        full_text = anchor.get_text(" ", strip=True).lstrip("➲").strip()
        if not full_text or len(full_text) < 3:
            return None

        # The <small> element holds the city/area; the rest is the school name.
        small = anchor.find("small")
        city = small.get_text(strip=True) if small else ""
        # Remove the <small>'s text from the full text to isolate the name.
        if small:
            small.extract()
        name = anchor.get_text(" ", strip=True).lstrip("➲").strip()
        if not name or len(name) < 3:
            return None

        # Title-case names that come ALL CAPS, preserve mixed-case ones.
        name_display = self._normalize_name(name)

        # The href captures the school's detail-page slug — useful for
        # later enrichment (we can revisit and pull principal name + phone).
        href = anchor.get("href", "") or ""
        detail_url = ""
        if href:
            detail_url = (
                href if href.startswith("http")
                else f"{SCHOOLS_BASE}/{href.lstrip('./')}"
            )

        # State derived from URL slug — schools.org.in doesn't put state
        # text on the listing page itself, only on the URL.
        state = state_slug.replace("-", " ").title() if state_slug else ""

        return {
            "first_name": "Principal",
            "last_name": "Office",
            "name": "Principal Office",
            "email": None,
            "phone": None,
            "linkedin_url": None,
            "title": "Principal",
            "seniority": "head",
            "departments": ["Administration"],
            "city": city,
            "state": state,
            "country": "India",
            "company": {
                "name": name_display,
                "domain": "",  # most schools don't have a usable web domain in the listing
                "industry": "Primary/Secondary Education",
                "employee_count": None,
                "city": city,
                "linkedin_url": None,
            },
            "extra_data": {
                "source": "schools_org_in",
                "schools_org_in_url": detail_url,
                "state_slug": state_slug,
            },
        }

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Convert ALL CAPS school names to Title Case for friendlier emails."""
        if not name:
            return name
        letters = [c for c in name if c.isalpha()]
        if not letters:
            return name
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.8:
            return name.title()
        return name


# Self-register on import
register_source(SchoolsScraper())
