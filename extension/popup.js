// AIapply.ai popup: reads job context from the active tab and calls the backend API.
const out = document.getElementById("out");
const detected = document.getElementById("detected");
let job = null;

async function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["backendUrl", "token"], (v) => resolve(v || {}));
  });
}

async function activeTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ? tab.id : null;
}

async function detectJob() {
  const tabId = await activeTabId();
  if (!tabId) return null;
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, { type: "AIAPPLY_DETECT_JOB" }, (resp) => {
      if (chrome.runtime.lastError) resolve(null);
      else resolve(resp || null);
    });
  });
}

function render(html) {
  out.innerHTML = html;
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

async function api(path, options) {
  const { backendUrl, token } = await getSettings();
  if (!backendUrl || !token) {
    render("Set your Backend URL and access token in Settings first.");
    throw new Error("not configured");
  }
  const res = await fetch(`${backendUrl.replace(/\/$/, "")}${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options && options.headers) }
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

document.getElementById("match").addEventListener("click", async () => {
  render("Finding matches…");
  try {
    const q = job && job.title ? job.title : "";
    const data = await api(`/api/jobs/matches?limit=15${q ? `&q=${encodeURIComponent(q)}` : ""}`);
    const cards = (data.results || [])
      .slice(0, 12)
      .map(
        (c) =>
          `<div class="card"><strong>${escapeHtml(c.title)}</strong> — ${escapeHtml(c.company)}<br/>` +
          `<span class="muted">${escapeHtml(c.location)} · match ${c.ats_score}%</span><br/>` +
          `<a href="${escapeHtml(c.url)}" target="_blank">Open</a></div>`
      )
      .join("");
    render(cards || "No matches found. Set a target role in your profile.");
  } catch (e) {
    render(escapeHtml(e.message));
  }
});

async function tailor(mode) {
  render(`Tailoring your ${mode === "resume" ? "resume" : "cover letter"}…`);
  try {
    const data = await api(`/api/tailor`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode,
        job_title: job ? job.title : "",
        company: job ? job.company : "",
        job_description: job ? job.description : "",
        base_text: ""
      })
    });
    const changes = (data.changes || []).map((c) => `<li>${escapeHtml(c)}</li>`).join("");
    render(
      `<div class="card"><strong>Aligned keywords:</strong> ${escapeHtml((data.keywords || []).join(", "))}</div>` +
        (changes ? `<ul>${changes}</ul>` : "") +
        `<textarea rows="10" readonly>${escapeHtml(data.tailored_text)}</textarea>`
    );
  } catch (e) {
    render(escapeHtml(e.message));
  }
}

document.getElementById("tailorResume").addEventListener("click", () => tailor("resume"));
document.getElementById("tailorCover").addEventListener("click", () => tailor("cover_letter"));

document.getElementById("save").addEventListener("click", () => {
  const backendUrl = document.getElementById("backendUrl").value.trim();
  const token = document.getElementById("token").value.trim();
  chrome.storage.local.set({ backendUrl, token }, () => render("Settings saved."));
});

(async function init() {
  const s = await getSettings();
  document.getElementById("backendUrl").value = s.backendUrl || "";
  document.getElementById("token").value = s.token || "";
  job = await detectJob();
  if (job && job.title) {
    detected.textContent = `Detected: ${job.title} @ ${job.company}`;
  } else {
    detected.textContent = "No job detected on this page — Find Matches still uses your profile.";
  }
})();
