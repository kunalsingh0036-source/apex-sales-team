"""
FHRAI hotels scraper — Federation of Hotel & Restaurant Associations of India.

FHRAI's member directory lives behind ASP.NET WebForms (search results
require POST with __VIEWSTATE/__EVENTVALIDATION). Plain HTTP gets nothing
useful. This scraper drives a real Chromium via the BrowserService — we
load the search page, fill the search form, click submit, wait for the
results table, then hand the rendered HTML to the existing parser.

Apollo's `Hospitality` industry returns 0 leads for India (their taxonomy
doesn't match Indian hotel groups), so FHRAI is the right primary source
for the P-hospitality-luxury profile.

Architecture:
- _fetch_directory: Playwright-driven (handles JS, cookies, viewstate)
- parse_directory: pure BeautifulSoup function over rendered HTML.
  Lives separately so unit tests run against a frozen fixture without
  needing a browser.

Limitations / known walls:
- Search results are paginated; we currently scrape page 1 only. Add
  pagination loop if a single page doesn't fill BATCH_SIZE.
- FHRAI rarely publishes principal-contact emails in the directory; we'd
  need Hunter.io domain-search downstream to find a usable address.
- If FHRAI changes selectors, the parser goes silent. Unit-test fixture
  in tests/fixtures/fhrai_sample.html catches selector drift in CI.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from app.models.lead import LeadProfile
from app.services.browser import browser_service
from app.services.lead_sources.base import LeadSource, RawLead, register_source

logger = logging.getLogger(__name__)


# Public member-search URLs. The actual search lives at /Search_member.aspx
# (probed live in 2026-05). FHRAI's old `/member-list` slug returns 404.
FHRAI_BASE = "https://www.fhrai.com"
# stType=Hotel narrows to hotels; "Restaurant" / "Associate" are other slices.
FHRAI_HOTEL_SEARCH = f"{FHRAI_BASE}/Search_member.aspx?stType=Hotel"


class FHRAIScraper:
    """Scrapes FHRAI's public hotel/restaurant member directory via Playwright."""

    name = "fhrai_scraper"
    description = "Federation of Hotel & Restaurant Associations of India member directory"

    def __init__(
        self,
        base_url: str = FHRAI_BASE,
        directory_url: str = FHRAI_HOTEL_SEARCH,
        page_load_timeout_ms: int = 30_000,
        results_wait_timeout_ms: int = 15_000,
    ) -> None:
        self.base_url = base_url
        self.directory_url = directory_url
        self.page_load_timeout_ms = page_load_timeout_ms
        self.results_wait_timeout_ms = results_wait_timeout_ms

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

        return members[:limit]

    async def _fetch_directory(self, state_filter: str | None = None) -> str:
        """Drive Playwright to load FHRAI's hotel search page and return the HTML.

        FHRAI's behavior is finicky: on initial GET it serves an empty
        results tbody, expecting a Search button click via ASP.NET PostBack
        to populate. We click it after navigation and wait for the AJAX
        rehydration to complete.

        The state_filter param is accepted for API symmetry; we don't apply
        it currently because FHRAI's filter UI uses chained PostBacks that
        get brittle quickly. We can sort/dedupe by city downstream.
        """
        async with browser_service.page() as page:
            # networkidle makes Playwright wait for ASP.NET's rehydration
            # before handing control back. Slightly slower than domcontentloaded
            # but reliable for WebForms sites that defer rendering.
            await page.goto(
                self.directory_url,
                wait_until="networkidle",
                timeout=self.page_load_timeout_ms,
            )

            # Click the Search button to trigger PostBack → real data load.
            # FHRAI's actual submit button (probed live 2026-05) is:
            #   <input id="ctl00_ContentPlaceHolder1_BtnSearch"
            #          name="ctl00$ContentPlaceHolder1$BtnSearch"
            #          type="submit" value="Submit" class="vac_btn performa_btn">
            # Selector matches the id pattern (most stable across redesigns).
            try:
                search_btn = page.locator(
                    "input[id$='BtnSearch'][type='submit'], "
                    "input[name$='BtnSearch'][type='submit']"
                ).first
                # Wait for the PostBack network roundtrip to settle.
                async with page.expect_response(
                    lambda r: "Search_member" in r.url and r.status == 200,
                    timeout=self.results_wait_timeout_ms,
                ):
                    await search_btn.click(timeout=5000)
            except Exception as e:
                logger.info(
                    f"FHRAI search submit didn't complete cleanly ({e}). "
                    f"Falling through to whatever tbody contains."
                )

            # Now wait for actual data rows in tbody.
            try:
                await page.wait_for_selector(
                    "table.search_member_tb tbody tr td",
                    timeout=self.results_wait_timeout_ms,
                )
            except Exception:
                logger.info(
                    "FHRAI results tbody did not populate within timeout; "
                    "parser will return [] gracefully"
                )

            return await page.content()

    # ─── Parsing (pure function, easily testable) ─────────────────

    def parse_directory(self, html: str) -> list[RawLead]:
        """Extract member entries from FHRAI directory HTML.

        Pure function — no I/O, no side effects. Unit tests run this
        against an HTML fixture in tests/fixtures/fhrai_sample.html.

        FHRAI's actual rendered structure (verified live 2026-05) is a
        single results table:
          <table class="search_member_tb">
            <thead> <th>Establishment Name</th> <th>City</th>
                    <th>Category</th> <th>Website</th> </thead>
            <tbody>
              <tr>
                <td><a onclick="ViewInvoicedetails('GUID')">HOTEL NAME</a></td>
                <td>City</td>
                <td>Category (e.g. "5 Star", "Unclassified")</td>
                <td><a href="https://hotel.example.com">website</a> (often blank)</td>
              </tr>
              ...
            </tbody>
          </table>

        Phone/email are not in the listing rows — they live in a per-member
        modal opened by ViewInvoicedetails(). For batch-of-20 use we keep
        each scrape lightweight and skip those modals; downstream Hunter.io
        domain enrichment fills in contacts when needed.
        """
        soup = BeautifulSoup(html, "lxml")
        results: list[RawLead] = []

        # Primary path: real FHRAI structure
        table = soup.select_one("table.search_member_tb")
        if table:
            for row in table.select("tbody tr"):
                lead = self._extract_member_row(row)
                if lead:
                    results.append(lead)

        return results

    def _extract_member_row(self, row: Any) -> RawLead | None:
        """Pull fields from a single FHRAI table row. Skips empty rows.

        FHRAI's tbody contains alternating empty <tr></tr> separators between
        real data rows; we filter those out by requiring at least 2 td cells.
        """
        cells = row.find_all("td")
        if len(cells) < 2:
            return None  # empty separator row

        # Establishment name lives in the first <td>, usually wrapped in an
        # <a onclick="ViewInvoicedetails(...)"> for the modal trigger.
        name_cell = cells[0]
        name_link = name_cell.find("a")
        company_name = (
            (name_link.get_text(strip=True) if name_link else "")
            or name_cell.get_text(strip=True)
        )
        if not company_name or len(company_name) < 2:
            return None

        # FHRAI uppercases all hotel names. Title-case for display so emails
        # don't shout at recipients ("Dear team at THE TAJ LAKE PALACE...").
        company_name_display = self._normalize_name(company_name)

        # City is the second cell; Category third; Website fourth (when present).
        city = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        category = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        website = ""
        if len(cells) > 3:
            web_link = cells[3].find("a", href=True)
            if web_link:
                href = web_link.get("href", "").strip()
                if href and href.startswith("http") and "fhrai.com" not in href:
                    website = href

        return {
            "first_name": "Operations",
            "last_name": "Team",
            "name": "Operations Team",
            "email": None,  # not in listing — Hunter.io fills downstream
            "phone": None,  # ditto
            "linkedin_url": None,
            "title": "General Manager",  # default target role for hospitality
            "seniority": "head",
            "departments": ["Operations"],
            "city": city,
            "state": "",  # FHRAI listing doesn't expose state directly
            "country": "India",
            "company": {
                "name": company_name_display,
                "domain": self._domain_from_website(website),
                "industry": "Hospitality",
                "employee_count": None,
                "city": city,
                "linkedin_url": None,
            },
            "extra_data": {
                "source": "fhrai_directory",
                "fhrai_category": category,  # "5 Star", "Unclassified", etc.
                "website": website,
            },
        }

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Convert ALL CAPS hotel names to Title Case for friendlier emails."""
        if not name:
            return name
        # If majority of letters are uppercase, title-case it. Preserve
        # already-mixed-case names as-is.
        letters = [c for c in name if c.isalpha()]
        if not letters:
            return name
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.8:
            return name.title()
        return name

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
