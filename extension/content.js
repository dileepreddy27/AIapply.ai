// Extracts a best-effort {title, company, description, url} from the current page
// so the popup can pre-fill match/tailor requests. Read-only; no network calls.
function textOf(selector) {
  const el = document.querySelector(selector);
  return el ? el.textContent.trim() : "";
}

function detectJob() {
  const url = location.href;
  const host = location.hostname.replace(/^www\./, "");

  // Common ATS heuristics first, then generic fallbacks.
  const title =
    textOf("h1[data-testid='job-title']") ||
    textOf(".posting-headline h2") || // Lever
    textOf(".app-title") || // Greenhouse
    textOf("h1") ||
    document.title;

  const company =
    textOf("[data-testid='company-name']") ||
    textOf(".company-name") ||
    (document.querySelector("meta[property='og:site_name']") || {}).content ||
    host.split(".")[0];

  const descEl =
    document.querySelector("#content .body") || // Greenhouse
    document.querySelector(".posting-page .section-wrapper") || // Lever
    document.querySelector("[data-testid='jobDescriptionText']") ||
    document.querySelector("main") ||
    document.body;
  const description = (descEl ? descEl.innerText : "").trim().slice(0, 6000);

  return {
    title: (title || "").trim().slice(0, 200),
    company: (company || "").trim().slice(0, 120),
    description,
    url
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "AIAPPLY_DETECT_JOB") {
    sendResponse(detectJob());
  }
  return true;
});
