// Apex Lead Capture — popup.
//
// On open:
//   1. Get the active tab id
//   2. Probe the token via /extension/whoami so we can show "Authenticated as <label>"
//   3. Fetch any pending capture stashed by the content script for this tab
//   4. Render either the "Submit N leads" button or the empty state
//
// On Submit click:
//   POST the captured leads via the background worker.

const $ = (id) => document.getElementById(id);

function setStatus(msg, kind = "info") {
  const el = $("status-area");
  el.textContent = msg;
  el.className = `status status-${kind}`;
}

async function getActiveTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.id;
}

async function send(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (resp) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(resp);
      }
    });
  });
}

async function init() {
  $("open-options").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });

  // 1. Validate token
  let me = null;
  try {
    const resp = await send({ type: "whoami" });
    if (resp.ok) {
      me = resp.result;
      setStatus(`Authenticated as ${me.label}`, "ok");
    } else {
      const errText = resp.error || "unknown auth failure";
      if (errText.includes("No token configured")) {
        setStatus("No token configured. Open Settings to paste your apex_ext_… token.", "error");
      } else {
        setStatus(`Token rejected: ${errText}`, "error");
      }
      $("empty-area").classList.remove("hidden");
      return;
    }
  } catch (err) {
    setStatus(`Auth probe failed: ${err.message}`, "error");
    $("empty-area").classList.remove("hidden");
    return;
  }

  // 2. Look for pending capture from this tab's content script
  const tabId = await getActiveTabId();
  if (!tabId) {
    $("empty-area").classList.remove("hidden");
    return;
  }

  const resp = await send({ type: "get_pending", tabId });
  const payload = resp?.payload;

  if (!payload || !payload.leads?.length) {
    $("empty-area").classList.remove("hidden");
    return;
  }

  // 3. Render capture summary
  $("capture-area").classList.remove("hidden");
  $("lead-count").textContent = payload.leads.length;
  $("source-name").textContent = payload.source || "page";
  $("source-url").textContent = payload.source_url || "";

  // 4. Wire submit
  $("submit-btn").addEventListener("click", async () => {
    $("submit-btn").disabled = true;
    $("submit-btn").textContent = "Submitting…";
    try {
      const r = await send({ type: "submit_capture", tabId });
      if (!r.ok) throw new Error(r.error);
      const created = r.result.created;
      const skipped = r.result.skipped;
      const batch = r.result.batch?.batch_code;
      const resultEl = $("submit-result");
      resultEl.classList.remove("hidden");
      resultEl.classList.add("success");
      resultEl.textContent = `Created ${created} leads as ${batch}${skipped ? ` (${skipped} duplicates skipped)` : ""}.`;
      $("submit-btn").textContent = "Done";
    } catch (err) {
      const resultEl = $("submit-result");
      resultEl.classList.remove("hidden");
      resultEl.classList.add("error");
      resultEl.textContent = `Submit failed: ${err.message}`;
      $("submit-btn").disabled = false;
      $("submit-btn").textContent = "Retry submit";
    }
  });
}

init();
