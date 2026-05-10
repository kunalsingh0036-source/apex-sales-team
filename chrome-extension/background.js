// Apex Lead Capture — service worker.
//
// The service worker mediates between content scripts (which know how to
// scrape a target site's DOM) and the popup (which the team member clicks
// to submit captured leads). It also handles API calls so content scripts
// don't need direct fetch access — keeps the security perimeter tight.
//
// Storage layout (chrome.storage.local):
//   apex_token           — bearer token (apex_ext_xxx) issued from dashboard
//   apex_api_url         — backend base URL (defaults to Railway prod)
//   apex_pending_capture — last scrape result kept by the active tab,
//                          waiting for the popup to confirm + submit
//
// Messages this worker handles:
//   { type: "capture_pending", payload: {...} } — content script reports
//     it has scraped the active page; we stash it for the popup to read.
//   { type: "submit_capture" }  — popup asks us to POST the pending payload.
//   { type: "whoami" }          — popup probes whether the saved token works.

const DEFAULT_API_URL = "https://apex-sales-team-production-2c45.up.railway.app/api/v1";

async function getStored(keys) {
  return new Promise((resolve) => {
    chrome.storage.local.get(keys, resolve);
  });
}

async function setStored(obj) {
  return new Promise((resolve) => {
    chrome.storage.local.set(obj, resolve);
  });
}

async function getConfig() {
  const { apex_token, apex_api_url } = await getStored(["apex_token", "apex_api_url"]);
  return {
    token: apex_token || "",
    apiUrl: apex_api_url || DEFAULT_API_URL,
  };
}

async function apiPost(path, body) {
  const { token, apiUrl } = await getConfig();
  if (!token) {
    throw new Error("No token configured. Open Options and paste your apex_ext_… token.");
  }
  const res = await fetch(`${apiUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

async function apiGet(path) {
  const { token, apiUrl } = await getConfig();
  if (!token) {
    throw new Error("No token configured.");
  }
  const res = await fetch(`${apiUrl}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Async handlers must return true and call sendResponse later — the
  // sync return value of `false` is treated as "no response coming".
  (async () => {
    try {
      if (msg.type === "capture_pending") {
        // Stash the scraped payload, keyed by tab id so multiple tabs
        // don't clobber each other's captures.
        const tabId = sender.tab?.id ?? "unknown";
        await setStored({ [`apex_pending_capture_${tabId}`]: msg.payload });
        // Update the action badge so the team member sees "this page
        // has data ready to capture".
        if (msg.payload?.leads?.length) {
          chrome.action.setBadgeText({ text: String(msg.payload.leads.length), tabId });
          chrome.action.setBadgeBackgroundColor({ color: "#7B1620", tabId });
        }
        sendResponse({ ok: true });
        return;
      }

      if (msg.type === "get_pending") {
        const tabId = msg.tabId;
        const out = await getStored([`apex_pending_capture_${tabId}`]);
        sendResponse({ ok: true, payload: out[`apex_pending_capture_${tabId}`] || null });
        return;
      }

      if (msg.type === "submit_capture") {
        const tabId = msg.tabId;
        const stored = await getStored([`apex_pending_capture_${tabId}`]);
        const payload = stored[`apex_pending_capture_${tabId}`];
        if (!payload) {
          sendResponse({ ok: false, error: "No captured leads to submit." });
          return;
        }
        const result = await apiPost("/extension/leads", payload);
        // Clear the stash so accidental re-clicks don't double-submit.
        await chrome.storage.local.remove(`apex_pending_capture_${tabId}`);
        chrome.action.setBadgeText({ text: "", tabId });
        sendResponse({ ok: true, result });
        return;
      }

      if (msg.type === "whoami") {
        const result = await apiGet("/extension/whoami");
        sendResponse({ ok: true, result });
        return;
      }

      sendResponse({ ok: false, error: `Unknown message type: ${msg.type}` });
    } catch (err) {
      sendResponse({ ok: false, error: err?.message || String(err) });
    }
  })();
  return true; // keep the message channel open for async sendResponse
});
