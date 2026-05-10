// FHRAI scraper — runs on https://www.fhrai.com/Search_member.aspx?stType=Hotel
//
// Scrapes the rendered table.search_member_tb and reports the rows to the
// background service worker. The team member then clicks the extension icon
// → popup → "Submit N leads" → background POSTs to the agent.
//
// We don't auto-submit — keeping the human-in-the-loop confirmation prevents
// accidental uploads from random pages and lets the team member spot bad
// rows before they hit the agent's inbox.

(function () {
  if (!location.pathname.includes("Search_member") && !location.pathname.includes("member-list")) {
    return; // not the search page; nothing to do
  }

  function parseRows(table) {
    const rows = table.querySelectorAll("tbody tr");
    const leads = [];
    rows.forEach((row) => {
      const cells = row.querySelectorAll("td");
      if (cells.length < 2) return; // empty separator row

      // Hotel name is the first cell, usually wrapped in an <a>.
      const nameCell = cells[0];
      const nameLink = nameCell.querySelector("a");
      const rawName = (nameLink?.textContent || nameCell.textContent || "").trim();
      if (!rawName || rawName.length < 2) return;

      const city = cells[1]?.textContent?.trim() || "";
      const category = cells[2]?.textContent?.trim() || "";
      let website = "";
      if (cells[3]) {
        const link = cells[3].querySelector("a[href^='http']");
        if (link) {
          const href = link.getAttribute("href") || "";
          if (!href.includes("fhrai.com")) website = href;
        }
      }

      leads.push({
        first_name: "Operations",
        last_name: "Team",
        full_name: "Operations Team",
        job_title: "General Manager",
        department: "Operations",
        seniority: "head",
        city,
        state: "",
        country: "India",
        company_name: window.apexCommon.normalizeName(rawName),
        company_industry: "Hospitality",
        extra_data: {
          source: "fhrai_directory",
          fhrai_category: category,
          website,
        },
      });
    });
    return leads;
  }

  function tryScrape() {
    const table = document.querySelector("table.search_member_tb");
    if (!table) return null;
    const leads = parseRows(table);
    if (!leads.length) return null;
    return {
      source: "fhrai",
      source_url: location.href,
      label: `FHRAI hotels — ${leads.length} rows`,
      leads,
    };
  }

  // Try once now. If the table hasn't rendered yet (FHRAI uses ASP.NET
  // PostBack — search results may load after the user clicks Submit on
  // their own), watch the DOM and re-run when rows appear.
  let lastReportedCount = 0;

  function attempt() {
    const payload = tryScrape();
    if (payload && payload.leads.length !== lastReportedCount) {
      lastReportedCount = payload.leads.length;
      window.apexCommon.report(payload);
    }
  }

  attempt();

  // Re-scrape when the table mutates (paging, filtering, or initial fill).
  const observer = new MutationObserver(() => {
    // Debounce so we don't flood the background script during heavy mutations.
    clearTimeout(observer._t);
    observer._t = setTimeout(attempt, 500);
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
