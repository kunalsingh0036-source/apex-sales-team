"""
GeM (Government e-Marketplace) tender scraper.

GeM is the official Indian government procurement portal — every public-
sector body that wants to buy uniforms, merchandise, or anything else
posts a bid here. Active bids = active buying-intent leads. Highest-
intent source we have for the defence/govt/education segments.

Strategy:
- Scrape https://bidplus.gem.gov.in/all-bids (open, no login)
- Each bid card contains the BUYER organization name, items list, and
  bid dates. The buyer is the lead; we synthesize a "Procurement Officer"
  contact placeholder until Hunter.io can find a real person.
- profile.search_params.keywords filters bids by item-text match
  (e.g. ["uniform", "apparel", "merchandise"]). Empty keywords = no filter.
- Apex-specific default keywords are baked in so the scraper is useful
  out-of-the-box without per-profile tuning.

Limitations:
- Only page 1 (10 bids) is scraped per call. Add pagination if a single
  page doesn't fill BATCH_SIZE — easy to extend with ?page=N.
- Department names sometimes lack city/state in the listing. We leave
  city blank and rely on the bid title/items to provide buying context.
- Bids close — we record start_date and end_date in extra_data so the
  outreach engine can prioritize the freshest opportunities.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from app.models.lead import LeadProfile
from app.services.browser import browser_service
from app.services.lead_sources.base import LeadSource, RawLead, register_source

logger = logging.getLogger(__name__)


GEM_BASE = "https://bidplus.gem.gov.in"
GEM_ALL_BIDS = f"{GEM_BASE}/all-bids"

# Apex-relevant keywords — bid item text must contain at least one of these
# (case-insensitive substring match) when no profile keywords are set.
# Tight enough to avoid pulling in irrelevant bids (toner cartridges, etc.),
# loose enough to catch real uniform/apparel/merchandise tenders.
DEFAULT_APEX_KEYWORDS = [
    "uniform",
    "apparel",
    "garment",
    "merchandise",
    "polo",
    "t-shirt",
    "tshirt",
    "shirt",
    "jacket",
    "kit",
    "track suit",
    "sportswear",
    "ppe",
    "fabric",
    "cotton",
    "embroidery",
]


class GEMTenderSource:
    """Scrapes active bids from the Government e-Marketplace tender feed."""

    name = "gem_tenders"
    description = "Government e-Marketplace (GeM) active tender feed — active buying-intent leads"

    def __init__(
        self,
        base_url: str = GEM_BASE,
        list_url: str = GEM_ALL_BIDS,
        page_load_timeout_ms: int = 45_000,
    ) -> None:
        self.base_url = base_url
        self.list_url = list_url
        self.page_load_timeout_ms = page_load_timeout_ms

    async def search(self, profile: LeadProfile, limit: int) -> list[RawLead]:
        params = (profile.search_params or {}) if profile is not None else {}
        keywords = params.get("keywords") or DEFAULT_APEX_KEYWORDS

        try:
            html = await self._fetch_bid_list()
        except Exception as e:
            logger.warning(f"GeM bid-list fetch failed: {e}")
            return []

        try:
            bids = self.parse_bid_list(html)
        except Exception as e:
            logger.error(f"GeM bid-list parse failed: {e}")
            return []

        # Filter to bids whose item text mentions at least one keyword
        if keywords:
            kw_lower = [k.lower() for k in keywords]
            filtered = [
                b for b in bids
                if any(k in (b["extra_data"]["bid_items"] or "").lower() for k in kw_lower)
            ]
        else:
            filtered = bids

        return filtered[:limit]

    async def _fetch_bid_list(self) -> str:
        """Drive Playwright to load the all-bids page and return rendered HTML.

        GeM's listing renders server-side (the JS in the page shows it could
        re-render via AJAX, but page 1 is delivered with cards already populated).
        We use networkidle to ensure any client-side rehydration completes.
        """
        async with browser_service.page() as page:
            await page.goto(
                self.list_url,
                wait_until="networkidle",
                timeout=self.page_load_timeout_ms,
            )

            try:
                await page.wait_for_selector("#bidCard .card", timeout=15_000)
            except Exception:
                logger.info("GeM bid cards selector not found; parser will return [] gracefully")

            return await page.content()

    # ─── Parsing (pure function) ────────────────────────────────

    def parse_bid_list(self, html: str) -> list[RawLead]:
        """Extract bid cards from the GeM all-bids HTML.

        Each card has:
          .block_header > .bid_no > a (BID NO and detail-page link)
          .card-body > .col-md-4 > items + quantity
          .card-body > .col-md-5 > department name & address
          .card-body > .col-md-3 > start_date + end_date
        """
        soup = BeautifulSoup(html, "lxml")
        results: list[RawLead] = []

        # The bid card list is wrapped in #bidCard. Each immediate .card is one bid.
        container = soup.select_one("#bidCard") or soup
        cards = container.select(".card")

        for card in cards:
            lead = self._extract_bid(card)
            if lead:
                results.append(lead)

        return results

    def _extract_bid(self, card: Any) -> RawLead | None:
        """Pull fields from a single bid card."""
        # Bid number — used to dedupe, the link is also the detail URL
        bid_no_link = card.select_one(".bid_no a")
        if not bid_no_link:
            return None
        bid_number = bid_no_link.get_text(strip=True)
        if not bid_number:
            return None
        bid_url = bid_no_link.get("href", "")
        if bid_url and not bid_url.startswith("http"):
            bid_url = f"{GEM_BASE}{bid_url}"

        # Items text (first col-md-4 has Items + Quantity)
        items_text = ""
        items_anchor = card.select_one(".col-md-4 a[data-toggle='popover']")
        if items_anchor:
            # Prefer the popover's data-content (full description) if present
            items_text = items_anchor.get("data-content") or items_anchor.get_text(strip=True)
        else:
            # Fallback: row containing "Items:"
            for row in card.select(".col-md-4 .row"):
                if row.find(string=re.compile(r"Items:", re.IGNORECASE)):
                    # Text after the bold "Items:" label
                    items_text = row.get_text(" ", strip=True).replace("Items:", "").strip()
                    break

        quantity = self._extract_strong_value(card, "Quantity")

        # Department name & address (col-md-5)
        dept_block = card.select_one(".col-md-5")
        dept_name = ""
        if dept_block:
            # All rows after the "Department Name And Address" label
            rows = dept_block.select(".row")
            # Skip rows containing the literal label
            value_rows = [r for r in rows if "Department Name" not in r.get_text()]
            dept_name = " — ".join(r.get_text(" ", strip=True) for r in value_rows if r.get_text(strip=True))

        if not dept_name:
            return None  # bid without a department — drop, can't build a lead

        # Dates (col-md-3)
        start_date = self._first_class_text(card, ".start_date")
        end_date = self._first_class_text(card, ".end_date")

        return {
            "first_name": "Procurement",
            "last_name": "Office",
            "name": "Procurement Office",
            "email": None,
            "phone": None,
            "linkedin_url": None,
            "title": "Head of Procurement",
            "seniority": "head",
            "departments": ["Procurement"],
            "city": "",
            "state": "",
            "country": "India",
            "company": {
                "name": dept_name,
                "domain": "",
                "industry": "Government Administration",
                "employee_count": None,
                "city": "",
                "linkedin_url": None,
            },
            "extra_data": {
                "source": "gem_tender",
                "bid_number": bid_number,
                "bid_url": bid_url,
                "bid_items": items_text,
                "bid_quantity": quantity,
                "bid_start_date": start_date,
                "bid_end_date": end_date,
            },
        }

    @staticmethod
    def _extract_strong_value(card: Any, label: str) -> str:
        """Return the text right after a `<strong>{label}:</strong>` element."""
        for strong in card.find_all("strong"):
            if label.lower() in strong.get_text(strip=True).lower():
                # Remove the strong text from the parent row text and clean up
                row = strong.find_parent(class_="row") or strong.parent
                if row:
                    raw = row.get_text(" ", strip=True)
                    return raw.replace(strong.get_text(strip=True), "").strip(": ").strip()
        return ""

    @staticmethod
    def _first_class_text(card: Any, selector: str) -> str:
        el = card.select_one(selector)
        return el.get_text(strip=True) if el else ""


# Self-register on import
register_source(GEMTenderSource())
