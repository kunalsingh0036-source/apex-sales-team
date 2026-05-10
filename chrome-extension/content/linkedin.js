// LinkedIn scraper — runs on linkedin.com/sales/* and linkedin.com/in/*
//
// LinkedIn doesn't expose a public API for search results, but the team's
// authenticated Sales Navigator session renders a clean DOM. This script
// captures person profile cards from search results and individual profile
// pages.
//
// Two modes:
//   1. Sales Navigator search results (linkedin.com/sales/search/people)
//      — a list of result cards we parse into RawLeads.
//   2. Individual profile pages (linkedin.com/in/<slug> or
//      linkedin.com/sales/lead/<id>) — captures one lead.
//
// LinkedIn's CSS classes shift constantly. The selectors below target
// stable structural attributes (data-x-search-result, data-anonymize)
// where possible, with class-based fallbacks. If LinkedIn breaks the
// extraction, the popup will report "0 leads" and the team will know.

(function () {
  const path = location.pathname;
  const isSalesSearch = path.startsWith("/sales/search/people");
  const isSalesLead = path.startsWith("/sales/lead/");
  const isProfile = /^\/in\/[^/]+/.test(path);

  if (!(isSalesSearch || isSalesLead || isProfile)) return;

  function clean(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function splitName(fullName) {
    const parts = clean(fullName).split(/\s+/);
    if (parts.length === 0) return { first: "", last: "" };
    if (parts.length === 1) return { first: parts[0], last: "" };
    return { first: parts[0], last: parts.slice(1).join(" ") };
  }

  // ─── Sales Navigator search results ───────────────────────────────

  function parseSalesSearchResults() {
    // Sales Nav results live in <li> rows with data-x-search-result-item.
    // Selectors are fallbacks — LinkedIn renames classes constantly.
    const items = document.querySelectorAll(
      "li[data-x-search-result-item], "
      + "li.artdeco-list__item, "
      + ".search-results__result-item"
    );

    const leads = [];
    items.forEach((item) => {
      // Name
      const nameEl =
        item.querySelector("[data-anonymize='person-name']") ||
        item.querySelector(".result-lockup__name a, .name-link, h3 a, [data-control-name='view_lead_panel_via_search_lead_name']");
      const fullName = clean(nameEl?.textContent);
      if (!fullName || fullName.length < 2) return;

      // Title (job title)
      const titleEl =
        item.querySelector("[data-anonymize='title']") ||
        item.querySelector(".result-lockup__highlight-keyword, .artdeco-entity-lockup__subtitle");
      const title = clean(titleEl?.textContent);

      // Company name
      const companyEl =
        item.querySelector("[data-anonymize='company-name']") ||
        item.querySelector(".result-lockup__position-company a, .artdeco-entity-lockup__caption");
      const company = clean(companyEl?.textContent);

      // Location
      const locEl =
        item.querySelector("[data-anonymize='location']") ||
        item.querySelector(".result-lockup__misc-list li");
      const location = clean(locEl?.textContent);

      // Profile URL — the link wrapping the name
      let profileUrl = "";
      const linkEl = nameEl?.closest("a") || item.querySelector("a[href*='/sales/lead/'], a[href*='/in/']");
      if (linkEl) {
        const href = linkEl.getAttribute("href") || "";
        profileUrl = href.startsWith("http") ? href : `${location.origin}${href}`;
      }

      const { first, last } = splitName(fullName);
      const [city, ...stateParts] = location.split(",").map((p) => p.trim());

      leads.push({
        first_name: first,
        last_name: last,
        full_name: fullName,
        job_title: title || "",
        seniority: inferSeniority(title),
        city: city || "",
        state: stateParts.join(", "),
        country: "India",
        linkedin_url: profileUrl,
        company_name: company,
        company_industry: "",
        extra_data: {
          source: "linkedin_sales_nav",
          captured_from: "search_results",
          location_raw: location,
        },
      });
    });
    return leads;
  }

  // ─── Single profile page (/in/<slug> or /sales/lead/<id>) ─────────

  function parseSingleProfile() {
    // Standard profile pages
    const nameEl =
      document.querySelector("h1.text-heading-xlarge") ||
      document.querySelector("[data-anonymize='person-name']") ||
      document.querySelector("h1");
    const fullName = clean(nameEl?.textContent);
    if (!fullName || fullName.length < 2) return [];

    const titleEl =
      document.querySelector(".text-body-medium.break-words") ||
      document.querySelector("[data-anonymize='title']") ||
      document.querySelector(".pv-text-details__left-panel .text-body-medium");
    const title = clean(titleEl?.textContent);

    const companyEl =
      document.querySelector("[data-anonymize='company-name']") ||
      document.querySelector(".inline-show-more-text--is-collapsed") ||
      document.querySelector("button[aria-label*='current company']");
    const company = clean(companyEl?.textContent);

    const locEl =
      document.querySelector("[data-anonymize='location']") ||
      document.querySelector(".text-body-small.inline.t-black--light.break-words") ||
      document.querySelector(".pv-text-details__left-panel + div span:first-child");
    const location = clean(locEl?.textContent);

    const { first, last } = splitName(fullName);
    const [city, ...stateParts] = location.split(",").map((p) => p.trim());

    return [{
      first_name: first,
      last_name: last,
      full_name: fullName,
      job_title: title,
      seniority: inferSeniority(title),
      city: city || "",
      state: stateParts.join(", "),
      country: "India",
      linkedin_url: location.href,
      company_name: company,
      company_industry: "",
      extra_data: {
        source: "linkedin_profile",
        captured_from: isSalesLead ? "sales_lead_page" : "profile_page",
      },
    }];
  }

  function inferSeniority(title) {
    const t = (title || "").toLowerCase();
    if (/(chief|cxo|cmo|chro|cpo|president|founder|owner)/.test(t)) return "c_suite";
    if (/(\bvp\b|vice president)/.test(t)) return "vp";
    if (/(director|head of)/.test(t)) return "director";
    if (/(manager|lead)/.test(t)) return "manager";
    return "individual_contributor";
  }

  function attempt() {
    let leads = [];
    if (isSalesSearch) {
      leads = parseSalesSearchResults();
    } else if (isProfile || isSalesLead) {
      leads = parseSingleProfile();
    }

    if (!leads.length) return;

    window.apexCommon.report({
      source: "linkedin",
      source_url: location.href,
      label: isSalesSearch
        ? `LinkedIn Sales Nav search — ${leads.length} people`
        : `LinkedIn profile — ${leads[0]?.full_name || "?"}`,
      leads,
    });
  }

  // LinkedIn is heavily JS — wait + watch for content to render.
  attempt();
  let lastLen = 0;
  const observer = new MutationObserver(() => {
    clearTimeout(observer._t);
    observer._t = setTimeout(() => {
      const leads = isSalesSearch ? parseSalesSearchResults() : parseSingleProfile();
      if (leads.length !== lastLen) {
        lastLen = leads.length;
        if (leads.length) attempt();
      }
    }, 1000);
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
