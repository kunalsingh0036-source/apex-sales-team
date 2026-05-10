# Apex Lead Capture (Chrome extension)

Captures leads from FHRAI, schools.org.in, GeM tenders, and LinkedIn into
the Apex outreach agent. Runs entirely on the team member's browser, so
the team member's local Indian IP is what reaches the target sites —
bypassing the Cloudflare and IP-geo blocks that prevent server-side
scraping from Railway/AWS.

## Why a browser extension and not a server-side scraper

- **schools.org.in serves a Cloudflare bot challenge to non-residential IPs.**
  Real Chrome on a real laptop solves the challenge transparently. Headless
  Chromium on a datacenter IP gets stuck on the challenge page.
- **GeM (bidplus.gem.gov.in) outright refuses connections from non-India
  IPs** with `ERR_CONNECTION_REFUSED`. Even with proxies this is fragile.
- LinkedIn's Sales Nav is gated by user session — only a logged-in human
  browser sees the data. There's no API for scrape volumes that matter.

The extension sidesteps all three: it IS a real browser, on a real network,
already logged in.

## Install (developer / sideload mode)

1. `chrome://extensions/` → enable "Developer mode" (top right).
2. Click "Load unpacked" → choose this `chrome-extension/` directory.
3. Open the extension's options page, paste an `apex_ext_…` token issued
   from the Apex dashboard.
4. Visit a supported page — FHRAI hotel search, schools.org.in/cbse/...,
   GeM all-bids, or LinkedIn Sales Nav. The extension's icon shows a
   badge with the lead count once it detects something.

## Install (Chrome Web Store)

Will be wired up after Chrome Web Store review (~1-2 days). For now use
sideload mode above.

## File layout

```
manifest.json         Manifest v3 spec
background.js         Service worker — handles auth + API calls
content/common.js     Helpers shared across all content scripts
content/fhrai.js      Scraper for fhrai.com hotel directory
content/schools.js    Scraper for schools.org.in CBSE pages (Day 2)
content/gem.js        Scraper for bidplus.gem.gov.in (Day 2)
content/linkedin.js   Scraper for linkedin.com Sales Nav (Day 3)
popup/                The toolbar popup the user clicks to submit
options/              Token + backend URL config page
```

## Auth model

The user pastes an `apex_ext_…` token in the options page. Background
service worker attaches it as `Authorization: Bearer <token>` on every
API call. Backend looks up the SHA-256 hash in `extension_tokens` table.

Tokens are revocable from the dashboard — no extension reinstall needed.

## API contract

All calls go to `${apex_api_url}/extension/...`:

- `GET /extension/whoami` → `{ id, label, created_at }`
- `POST /extension/leads` body `{ source, source_url, label, leads: [...] }`
  → `{ created, skipped, batch: { batch_code, ... } }`
