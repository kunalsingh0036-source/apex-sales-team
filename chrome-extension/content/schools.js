// schools.org.in scraper — runs on https://schools.org.in/cbse/schools-in-<state>
//
// schools.org.in puts itself behind Cloudflare's bot protection, which
// blocks our server-side Playwright but lets a real browser through. The
// team member visits a state page in their normal Chrome, this content
// script extracts the school list, the user submits via the popup.
//
// Reuses the same anchor-based parsing strategy the backend SchoolsScraper
// uses (see app/services/lead_sources/schools_scraper.py) so leads land
// in the same shape regardless of source.

(function () {
  // Only run on actual school-listing pages; skip the homepage / unrelated
  // schools.org.in pages so we don't spam empty captures.
  if (!/\/(cbse|schools)\b/.test(location.pathname)) return;

  function extractStateSlugFromPath() {
    // URL shapes we expect:
    //   /cbse/schools-in-delhi
    //   /cbse/top-schools-in-south-delhi
    //   /residential-schools-in-tamil-nadu.html
    const m = location.pathname.match(/schools-in-([a-z][a-z0-9-]+?)(?:\.html)?$/i);
    if (m) return m[1].toLowerCase();
    return "";
  }

  function parseSchools() {
    const anchors = document.querySelectorAll("a.list-group-item, a.list-group-item-action");
    const stateSlug = extractStateSlugFromPath();
    const stateName = stateSlug
      ? stateSlug.split("-").map((p) => p[0].toUpperCase() + p.slice(1)).join(" ")
      : "";

    const leads = [];
    anchors.forEach((a) => {
      // The <small> child holds the city; remove it first then take the
      // remaining anchor text as the school name.
      const small = a.querySelector("small");
      const city = small ? small.textContent.trim() : "";

      // Clone so we can strip the small without mutating the live page.
      const clone = a.cloneNode(true);
      clone.querySelectorAll("small").forEach((el) => el.remove());
      // Strip the leading "➲" or other decoration.
      const rawName = clone.textContent.replace(/^[➲•\s]+/, "").trim();
      if (!rawName || rawName.length < 3) return;

      const href = a.getAttribute("href") || "";
      const detailUrl = href.startsWith("http")
        ? href
        : `${location.origin}/${href.replace(/^\.?\//, "")}`;

      leads.push({
        first_name: "Principal",
        last_name: "Office",
        full_name: "Principal Office",
        job_title: "Principal",
        department: "Administration",
        seniority: "head",
        city,
        state: stateName,
        country: "India",
        company_name: window.apexCommon.normalizeName(rawName),
        company_industry: "Primary/Secondary Education",
        extra_data: {
          source: "schools_org_in",
          schools_org_in_url: detailUrl,
          state_slug: stateSlug,
        },
      });
    });
    return leads;
  }

  function attempt() {
    const leads = parseSchools();
    if (!leads.length) return;
    const stateSlug = extractStateSlugFromPath();
    window.apexCommon.report({
      source: "schools_org_in",
      source_url: location.href,
      label: `schools.org.in — ${stateSlug || "page"} (${leads.length} schools)`,
      leads,
    });
  }

  // Run once after DOM is idle, then watch for navigation/pagination changes.
  attempt();
  let lastLen = 0;
  const observer = new MutationObserver(() => {
    clearTimeout(observer._t);
    observer._t = setTimeout(() => {
      const leads = parseSchools();
      if (leads.length && leads.length !== lastLen) {
        lastLen = leads.length;
        attempt();
      }
    }, 500);
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
