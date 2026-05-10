// Settings page for the Apex Lead Capture extension.

const $ = (id) => document.getElementById(id);

const DEFAULT_API_URL = "https://apex-sales-team-production-2c45.up.railway.app/api/v1";

async function load() {
  chrome.storage.local.get(["apex_token", "apex_api_url"], (data) => {
    if (data.apex_token) {
      $("token-input").value = data.apex_token;
    }
    $("api-url-input").value = data.apex_api_url || DEFAULT_API_URL;
  });
}

function showResult(elId, text, kind) {
  const el = $(elId);
  el.textContent = text;
  el.classList.remove("hidden", "success", "error");
  el.classList.add(kind);
}

$("save-btn").addEventListener("click", () => {
  const token = $("token-input").value.trim();
  const apiUrl = $("api-url-input").value.trim() || DEFAULT_API_URL;

  if (token && !token.startsWith("apex_ext_")) {
    showResult("save-result", "Token must start with apex_ext_", "error");
    return;
  }

  chrome.storage.local.set({ apex_token: token, apex_api_url: apiUrl }, () => {
    showResult("save-result", "Saved.", "success");
  });
});

$("show-btn").addEventListener("click", () => {
  const inp = $("token-input");
  inp.type = inp.type === "password" ? "text" : "password";
  $("show-btn").textContent = inp.type === "password" ? "Show" : "Hide";
});

$("probe-btn").addEventListener("click", async () => {
  const probeBtn = $("probe-btn");
  probeBtn.disabled = true;
  probeBtn.textContent = "Probing…";
  showResult("probe-result", "Calling /extension/whoami…", "success");

  try {
    const resp = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "whoami" }, (r) => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve(r);
      });
    });

    if (resp.ok) {
      showResult("probe-result", `Connected as "${resp.result.label}". Token works.`, "success");
    } else {
      showResult("probe-result", `Failed: ${resp.error}`, "error");
    }
  } catch (err) {
    showResult("probe-result", `Failed: ${err.message}`, "error");
  } finally {
    probeBtn.disabled = false;
    probeBtn.textContent = "Probe /whoami";
  }
});

load();
