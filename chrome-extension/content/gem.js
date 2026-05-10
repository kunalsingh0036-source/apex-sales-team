// GeM tender scraper — runs on https://bidplus.gem.gov.in/all-bids
//
// GeM is geo-firewalled: server-side scrapers from non-India IPs get
// ERR_CONNECTION_REFUSED. The team member's office Chrome goes through
// fine; this script reads the rendered bid cards, the user submits.
//
// Mirrors the parse logic of the backend GEMTenderSource so leads land
// in the same shape (the team gets to compare apples-to-apples between
// FHRAI/extension batches and any future server-side batches).

(function () {
  // Apex-relevant default keyword filter — same list the backend uses.
  const APEX_KEYWORDS = [
    "uniform", "apparel", "garment", "merchandise", "polo", "t-shirt",
    "tshirt", "shirt", "jacket", "kit", "track suit", "sportswear",
    "ppe", "fabric", "cotton", "embroidery",
  ];

  function getStrongValueFromCard(card, label) {
    const strongs = card.querySelectorAll("strong");
    for (const s of strongs) {
      if (s.textContent.toLowerCase().includes(label.toLowerCase())) {
        const row = s.closest(".row") || s.parentElement;
        if (row) {
          return row.textContent.replace(s.textContent, "").replace(":", "").trim();
        }
      }
    }
    return "";
  }

  function parseBidCards() {
    const container = document.querySelector("#bidCard") || document;
    const cards = container.querySelectorAll(".card");
    const leads = [];

    cards.forEach((card) => {
      // Bid number link
      const bidNoLink = card.querySelector(".bid_no a");
      if (!bidNoLink) return;
      const bidNumber = bidNoLink.textContent.trim();
      if (!bidNumber) return;

      let bidUrl = bidNoLink.getAttribute("href") || "";
      if (bidUrl && !bidUrl.startsWith("http")) {
        bidUrl = `${location.origin}${bidUrl}`;
      }

      // Items text — prefer popover data-content (full description)
      let itemsText = "";
      const popoverAnchor = card.querySelector(".col-md-4 a[data-toggle='popover']");
      if (popoverAnchor) {
        itemsText = popoverAnchor.getAttribute("data-content") || popoverAnchor.textContent.trim();
      } else {
        const rows = card.querySelectorAll(".col-md-4 .row");
        for (const r of rows) {
          if (/Items:/i.test(r.textContent)) {
            itemsText = r.textContent.replace(/Items:/i, "").trim();
            break;
          }
        }
      }

      // Quantity
      const quantity = getStrongValueFromCard(card, "Quantity");

      // Department name
      const deptBlock = card.querySelector(".col-md-5");
      let deptName = "";
      if (deptBlock) {
        const valueRows = [...deptBlock.querySelectorAll(".row")].filter(
          (r) => !r.textContent.includes("Department Name")
        );
        deptName = valueRows
          .map((r) => r.textContent.replace(/\s+/g, " ").trim())
          .filter(Boolean)
          .join(" — ");
      }
      if (!deptName) return;

      // Dates
      const startDate = card.querySelector(".start_date")?.textContent?.trim() || "";
      const endDate = card.querySelector(".end_date")?.textContent?.trim() || "";

      // Apex-relevance filter — only include bids whose items mention something
      // we'd actually pitch on. Without this, GeM dumps 10 unrelated bids per page.
      const lowerItems = itemsText.toLowerCase();
      const matches = APEX_KEYWORDS.some((k) => lowerItems.includes(k));
      if (!matches) return;

      leads.push({
        first_name: "Procurement",
        last_name: "Office",
        full_name: "Procurement Office",
        job_title: "Head of Procurement",
        department: "Procurement",
        seniority: "head",
        city: "",
        state: "",
        country: "India",
        company_name: deptName,
        company_industry: "Government Administration",
        extra_data: {
          source: "gem_tender",
          bid_number: bidNumber,
          bid_url: bidUrl,
          bid_items: itemsText,
          bid_quantity: quantity,
          bid_start_date: startDate,
          bid_end_date: endDate,
        },
      });
    });

    return leads;
  }

  function attempt() {
    const leads = parseBidCards();
    if (!leads.length) return;
    window.apexCommon.report({
      source: "gem_tenders",
      source_url: location.href,
      label: `GeM bids — ${leads.length} Apex-relevant`,
      leads,
    });
  }

  attempt();
  let lastLen = 0;
  const observer = new MutationObserver(() => {
    clearTimeout(observer._t);
    observer._t = setTimeout(() => {
      const leads = parseBidCards();
      if (leads.length && leads.length !== lastLen) {
        lastLen = leads.length;
        attempt();
      }
    }, 500);
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
