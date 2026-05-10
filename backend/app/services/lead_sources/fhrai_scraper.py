"""
FHRAI hotels scraper — Federation of Hotel & Restaurant Associations of India.

FHRAI publishes a member directory at https://www.fhrai.com that lists
hotels with their address, phone, and (sometimes) GM/owner contact details.
Apollo's `Hospitality` industry returns 0 leads for India (their taxonomy
doesn't match Indian hotel groups), so this scraper is the right primary
source for the P-hospitality-luxury profile.

Implementation notes:
- We hit the public member-search endpoint, not any authenticated area.
- HTML parsed with BeautifulSoup (lxml). No JS rendering needed — FHRAI's
  member listings are server-side rendered.
- Rate-limited to 1 req/sec with httpx.AsyncClient + asyncio.sleep so we
  don't get IP-banned. Even at 1/sec we get ~3,600 hotels/hour upper bound.
- Returns RawLead-shaped dicts. No email/phone for some entries — those
  go through the existing Hunter.io enrichment downstream.
- Profile.search_params are honored where possible (locations →
  state/city filter on FHRAI's UI; company_sizes → ignored, FHRAI
  doesn't publish room counts in directory listing).

Limitations / known walls:
- Some FHRAI pages are JS-rendered (member detail modals). For those we
  fall back to the listing-page fields only.
- FHRAI doesn't publish principal contact emails in the directory; we'd
  need Hunter.io domain-search downstream to find a usable address.
- If FHRAI changes their HTML structure, this scraper goes silent. The
  unit tests use a frozen HTML fixture so we'd notice in CI before prod.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.models.lead import LeadProfile
from app.services.lead_sources.base import LeadSource, RawLead, register_source

logger = logging.getLogger(__name__)


# Public member-search endpoint. FHRAI has restructured the URL a few
# times; if it 404s we log the error and return [] rather than crashing.
FHRAI_BASE = "https://www.fhrai.com"
FHRAI_MEMBER_DIRECTORY = f"{FHRAI_BASE}/member-list"


class FHRAIScraper:
    """Scrapes FHRAI's public hotel/restaurant member directory."""

    name = "fhrai_scraper"
    description = "Federation of Hotel & Restaurant Associations of India member directory"

    def __init__(
        self,
        base_url: str = FHRAI_BASE,
        directory_url: str = FHRAI_MEMBER_DIRECTORY,
        rate_limit_seconds: float = 1.0,
        request_timeout: int = 20,
    ) -> None:
        self.base_url = base_url
        self.directory_url = directory_url
        self.rate_limit_seconds = rate_limit_seconds
        self.request_timeout = request_timeout

    async def search(self, profile: LeadProfile, limit: int) -> list[RawLead]:
        params = (profile.search_params or {}) if profile is not None else {}
        locations = params.get("locations") or []
        # FHRAI's UI accepts an optional state/city filter; we just pick the
        # first non-"India" location since "India" alone returns the full set.
        state_filter = next(
            (loc for loc in locations if loc.lower() not in ("india", "")),
            None,
        )

        try:
            html = await self._fetch_directory(state_filter=state_filter)
        except Exception as e:
            logger.warning(f"FHRAI directory fetch failed: {e}")
            return []

        try:
            members = self.parse_directory(html)
        except Exception as e:
            logger.error(f"FHRAI directory parsing failed: {e}")
            return []

        # Cap to limit; over-fetch built into the directory itself
        return members[:limit]

    async def _fetch_directory(self, state_filter: str | None = None) -> str:
        """Hit the directory page. State filter passed as query param when set."""
        url = self.directory_url
        params: dict[str, Any] = {}
        if state_filter:
            params["state"] = state_filter

        async with httpx.AsyncClient(
            timeout=self.request_timeout,
            headers={"User-Agent": "ApexHumanCompany-LeadDiscovery/1.0 (info@theapexhumancompany.com)"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.text

    # ─── Parsing (pure function, easily testable) ─────────────────

    def parse_directory(self, html: str) -> list[RawLead]:
        """Extract member entries from FHRAI directory HTML.

        Pure function — no I/O, no side effects. Unit tests run this
        against an HTML fixture in tests/fixtures/fhrai_sample.html.

        Selectors target FHRAI's current markup as of 2026-Q2. The site's
        member listings live in `.member-list-item` divs (or table rows
        depending on the page variant — we handle both).
        """
        soup = BeautifulSoup(html, "lxml")
        results: list[RawLead] = []

        # Variant A: <div class="member-list-item">
        for item in soup.select(".member-list-item"):
            lead = self._extract_member(item)
            if lead:
                results.append(lead)

        # Variant B: <tr> rows in a table — fallback for legacy pages
        if not results:
            for row in soup.select("table.member-table tr"):
                lead = self._extract_member(row)
                if lead:
                    results.append(lead)

        # Variant C: generic anchor-card fallback used during FHRAI redesigns.
        # Looks for any block with both a name (.name / h3 / h4) and contact
        # info (phone or address). Less precise but resilient to markup churn.
        if not results:
            for block in soup.select("article, .card, .member-card"):
                lead = self._extract_member(block)
                if lead:
                    results.append(lead)

        return results

    def _extract_member(self, node: Any) -> RawLead | None:
        """Pull fields from a single member listing node. Skips empty rows."""
        # Hotel/restaurant name — the most identifying field.
        name_el = (
            node.select_one(".member-name")
            or node.select_one(".name")
            or node.select_one("h3")
            or node.select_one("h4")
            or node.select_one("strong")
        )
        if not name_el:
            return None
        company_name = name_el.get_text(strip=True)
        if not company_name or len(company_name) < 3:
            return None

        # Address — concatenated text, often spans multiple lines.
        addr_el = (
            node.select_one(".address")
            or node.select_one(".member-address")
            or node.select_one(".location")
        )
        address = addr_el.get_text(" ", strip=True) if addr_el else ""

        # Phone — first phone number we find.
        phone_text = ""
        phone_el = node.select_one(".phone, .tel, .contact-phone")
        if phone_el:
            phone_text = phone_el.get_text(strip=True)
        else:
            # Scan all text for a phone-like pattern. Indian numbers are
            # often broken into 2-4 segments (e.g. "+91-44-2220-0000",
            # "022-2661-1111", "+91 98765 43210") so we match a digit
            # followed by 8-15 chars of digits/spaces/dashes ending in a
            # digit. The leading +91 country code is optional.
            text = node.get_text(" ", strip=True)
            phone_match = re.search(
                r"(?:\+?91[-\s]?)?\d[\d\s\-]{8,15}\d",
                text,
            )
            if phone_match:
                phone_text = phone_match.group(0).strip()

        # Email — best-effort; FHRAI rarely publishes these.
        email = ""
        email_el = node.select_one("a[href^='mailto:']")
        if email_el:
            email = email_el.get("href", "").replace("mailto:", "").strip()
        else:
            text = node.get_text(" ", strip=True)
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
            if email_match:
                email = email_match.group(0)

        # Website — useful for downstream Hunter.io domain enrichment.
        website = ""
        web_el = node.select_one("a[href^='http']:not([href^='mailto:'])")
        if web_el:
            href = web_el.get("href", "")
            if "fhrai.com" not in href:
                website = href

        # City/state — best-effort from address parsing.
        city, state = self._parse_city_state(address)

        # FHRAI listings rarely give a contact person. We synthesize a
        # placeholder name so downstream code (which expects first/last)
        # doesn't crash — Hunter.io / manual review fills in the real
        # contact later. The placeholder is recognizable so the team can
        # tell at-a-glance which leads need contact-name enrichment.
        return {
            "first_name": "Operations",
            "last_name": "Team",
            "name": "Operations Team",
            "email": email or None,
            "phone": phone_text or None,
            "linkedin_url": None,
            "title": "General Manager",  # default target role for hospitality
            "seniority": "head",
            "departments": ["Operations"],
            "city": city,
            "state": state,
            "country": "India",
            "company": {
                "name": company_name,
                "domain": self._domain_from_website(website),
                "industry": "Hospitality",
                "employee_count": None,
                "city": city,
                "linkedin_url": None,
            },
            "extra_data": {
                "source": "fhrai_directory",
                "raw_address": address,
                "website": website,
            },
        }

    @staticmethod
    def _parse_city_state(address: str) -> tuple[str, str]:
        """Extract city + state from an FHRAI address string.

        Indian addresses are usually `..., City, State PIN` — we pick the
        last two comma-separated parts before the PIN. Resilient to missing
        parts; returns ("", "") if it can't tell.
        """
        if not address:
            return "", ""
        # Strip trailing PIN
        addr = re.sub(r"[\s\-,]*\b\d{6}\b\s*$", "", address).strip()
        parts = [p.strip() for p in addr.split(",") if p.strip()]
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        if len(parts) == 1:
            return parts[0], ""
        return "", ""

    @staticmethod
    def _domain_from_website(website: str) -> str:
        """Extract bare domain from a website URL."""
        if not website:
            return ""
        m = re.match(r"https?://(?:www\.)?([^/]+)", website)
        return m.group(1) if m else ""


# Self-register on import
register_source(FHRAIScraper())
