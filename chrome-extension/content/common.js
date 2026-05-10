// Apex Lead Capture — content-script helpers.
//
// Loaded before each site-specific scraper. Provides:
// - `apexCommon.normalizeName(s)`: ALL CAPS → Title Case
// - `apexCommon.report(payload)`: send the scraped batch to the background
//   service worker, which stashes it for the popup to submit.
//
// Each site-specific script (fhrai.js, schools.js, gem.js, linkedin.js)
// runs at document_idle, builds an array of leads in the shared shape,
// and calls apexCommon.report({ source, source_url, label, leads }).

window.apexCommon = (() => {
  function normalizeName(name) {
    if (!name) return name;
    const letters = [...name].filter((c) => /[A-Za-z]/.test(c));
    if (letters.length === 0) return name;
    const upperRatio = letters.filter((c) => c === c.toUpperCase()).length / letters.length;
    if (upperRatio > 0.8) {
      // Title-case each word
      return name
        .toLowerCase()
        .replace(/(^|\s|-|\.)([a-z])/g, (_, sep, ch) => sep + ch.toUpperCase());
    }
    return name;
  }

  function textOf(el) {
    return (el && el.textContent ? el.textContent : "").trim();
  }

  function report(payload) {
    chrome.runtime.sendMessage({ type: "capture_pending", payload }, (resp) => {
      if (chrome.runtime.lastError) {
        console.warn("[Apex] sendMessage failed:", chrome.runtime.lastError.message);
        return;
      }
      if (resp?.ok) {
        console.log(`[Apex] captured ${payload?.leads?.length || 0} leads from ${payload.source}`);
      } else {
        console.warn("[Apex] capture rejected:", resp?.error);
      }
    });
  }

  return { normalizeName, textOf, report };
})();
