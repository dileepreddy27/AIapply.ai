"""Unified aggregator sources — pull jobs from many platforms in one pass.

These sit alongside the direct ATS scanners (Greenhouse/Lever/Ashby/SmartRecruiters/
Recruitee). Aggregators are query-based and cover the big consumer boards
(LinkedIn / Indeed / Glassdoor / ZipRecruiter) and the wider web via legitimate
middle-layer APIs — no direct LinkedIn/Indeed credential scraping or anti-bot bypass.

Sources (all optional; a source is skipped unless its key/feed is configured):
- JSearch (RapidAPI): one call queries dozens of boards. Needs RAPIDAPI_KEY.
- SerpApi Google Jobs: aggregates most of the web's job pages. Needs SERPAPI_KEY.
- RSS/Atom feeds: niche boards that publish structured feeds. Needs LIVE_RSS_FEEDS.
"""

from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from typing import Any

import requests

from .models import JobPosting
from .scanners import _make_id, _normalize_timestamp

USER_AGENT = "career-autopilot/0.1 (+aggregator)"

# Hosts that indicate a direct ATS application (form-fill friendly).
_ATS_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "workday.com",
    "smartrecruiters.com",
    "recruitee.com",
    "icims.com",
    "jobvite.com",
    "workable.com",
    "bamboohr.com",
)


def classify_apply_type(url: str, is_direct: bool | None = None) -> str:
    """Classify how an application would be submitted, for the auto-applier."""
    host = (url or "").lower()
    if any(h in host for h in _ATS_HOSTS):
        return "external_ats"
    if "linkedin.com" in host:
        return "linkedin_easy_apply"
    if "indeed.com" in host:
        return "indeed"
    if "glassdoor." in host:
        return "glassdoor"
    if is_direct:
        return "direct"
    return "unknown"


def queue_hash(company: str, title: str, location: str) -> str:
    """Deterministic id used to dedupe the same role across platforms."""
    raw = f"{str(company).lower().strip()}_{str(title).lower().strip()}_{str(location).lower().strip()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def classify_application_route(url: str) -> str:
    """Routing taxonomy the applier worker uses to pick an adapter."""
    link = (url or "").lower()
    if not link:
        return "UNKNOWN"
    if "lever.co" in link:
        return "ATS_LEVER_API"
    if "greenhouse.io" in link:
        return "ATS_GREENHOUSE_API"
    if "ashbyhq.com" in link:
        return "ATS_ASHBY"
    if "smartrecruiters.com" in link:
        return "ATS_SMARTRECRUITERS"
    if "recruitee.com" in link:
        return "ATS_RECRUITEE"
    if "workday" in link:
        return "BROWSER_WORKDAY_FLOW"
    if "linkedin.com" in link:
        return "LINKEDIN_EASY_APPLY"
    if "indeed.com" in link:
        return "INDEED"
    return "GENERIC_WEB_FORM"


def fetch_applier_queue(
    query: str, pages: int = 1, date_posted: str = "all", location: str = ""
) -> list[dict[str, Any]]:
    """Query JSearch across LinkedIn/Indeed/Glassdoor/etc. and map to the
    auto-applier queue schema (deduped by company+title+location)."""
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key or not query.strip():
        return []
    host = os.getenv("RAPIDAPI_JSEARCH_HOST", "jsearch.p.rapidapi.com").strip()
    q = f"{query.strip()} in {location.strip()}" if location.strip() else query.strip()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for page in range(1, max(1, min(pages, 5)) + 1):
        try:
            data = _get_json(
                f"https://{host}/search",
                headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": host},
                params={"query": q, "page": str(page), "num_pages": "1", "date_posted": date_posted},
            )
        except Exception:
            # A later page failing (e.g. JSearch 429 rate-limit) must not discard the
            # pages already fetched — stop paginating and return the partial queue.
            break
        for job in (data.get("data", []) if isinstance(data, dict) else []):
            if not isinstance(job, dict):
                continue
            company = str(job.get("employer_name", "") or "Unknown Company")
            title = str(job.get("job_title", "") or "Unknown Title")
            location_str = ", ".join(
                p for p in (str(job.get("job_city", "") or ""), str(job.get("job_state", "") or "")) if p
            ) or ("Remote" if job.get("job_is_remote") else "Unknown Location")
            jid = queue_hash(company, title, location_str)
            if jid in seen:
                continue
            seen.add(jid)
            apply_link = str(job.get("job_apply_link", "") or "")
            out.append(
                {
                    "job_id": jid,
                    "title": title,
                    "company": company,
                    "location": location_str,
                    "platform_source": str(job.get("job_publisher", "") or "Direct Search"),
                    "apply_url": apply_link,
                    "application_type": classify_application_route(apply_link),
                    "description": str(job.get("job_description", "") or ""),
                    "salary_min": job.get("job_min_salary"),
                    "salary_max": job.get("job_max_salary"),
                    "is_remote": bool(job.get("job_is_remote", False)),
                    "posted_at": str(job.get("job_posted_at_datetime_utc", "") or ""),
                }
            )
    return out


def export_applier_queue(
    query: str, out_path: str = "applier_queue.json", pages: int = 1, location: str = ""
) -> int:
    """Write the unified applier queue to JSON. Returns the row count."""
    items = fetch_applier_queue(query, pages=pages, location=location)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    return len(items)


def _job(
    source: str,
    url: str,
    title: str,
    company: str,
    location: str = "",
    description: str = "",
    posted_at: str = "",
    apply_type: str = "unknown",
) -> JobPosting:
    return JobPosting(
        id=_make_id(source, url),
        source=source,
        company=company.strip() or "Unknown Company",
        title=title.strip() or "Unknown Role",
        location=location.strip() or "Unknown Location",
        url=url.strip(),
        description=description.strip(),
        posted_at=_normalize_timestamp(posted_at),
        apply_type=apply_type,
    )


def _get_json(url: str, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> Any:
    resp = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})},
        params=params or {},
    )
    resp.raise_for_status()
    return resp.json()


def scan_jsearch(query: str, location: str = "", pages: int = 1, date_posted: str = "all") -> list[JobPosting]:
    """RapidAPI JSearch — aggregates LinkedIn/Indeed/Glassdoor/ZipRecruiter/etc."""
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key or not query.strip():
        return []
    host = os.getenv("RAPIDAPI_JSEARCH_HOST", "jsearch.p.rapidapi.com").strip()
    q = f"{query.strip()} in {location.strip()}" if location.strip() else query.strip()
    data = _get_json(
        f"https://{host}/search",
        headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": host},
        params={"query": q, "page": "1", "num_pages": str(max(1, min(pages, 5))), "date_posted": date_posted},
    )
    rows = data.get("data", []) if isinstance(data, dict) else []
    out: list[JobPosting] = []
    for j in rows:
        if not isinstance(j, dict):
            continue
        apply_link = str(j.get("job_apply_link", "") or "")
        loc = ", ".join(
            p for p in (str(j.get("job_city", "") or ""), str(j.get("job_state", "") or ""), str(j.get("job_country", "") or "")) if p
        )
        if j.get("job_is_remote"):
            loc = f"{loc} (Remote)".strip(", ").strip()
        publisher = str(j.get("job_publisher", "") or "").strip().lower().replace(" ", "-") or "jsearch"
        out.append(
            _job(
                source=publisher,
                url=apply_link,
                title=str(j.get("job_title", "")),
                company=str(j.get("employer_name", "")),
                location=loc,
                description=str(j.get("job_description", "") or ""),
                posted_at=j.get("job_posted_at_datetime_utc") or "",
                apply_type=classify_apply_type(apply_link, bool(j.get("job_apply_is_direct"))),
            )
        )
    return [j for j in out if j.url]


def scan_serpapi_google_jobs(query: str, location: str = "") -> list[JobPosting]:
    """SerpApi Google Jobs — Google indexes nearly every board and career site."""
    api_key = os.getenv("SERPAPI_KEY", "").strip()
    if not api_key or not query.strip():
        return []
    params: dict[str, Any] = {"engine": "google_jobs", "q": query.strip(), "api_key": api_key}
    if location.strip():
        params["location"] = location.strip()
    data = _get_json("https://serpapi.com/search.json", params=params)
    rows = data.get("jobs_results", []) if isinstance(data, dict) else []
    out: list[JobPosting] = []
    for j in rows:
        if not isinstance(j, dict):
            continue
        options = j.get("apply_options") or []
        url = ""
        if options and isinstance(options[0], dict):
            url = str(options[0].get("link", "") or "")
        url = url or str(j.get("share_link", "") or "")
        posted = ""
        ext = j.get("detected_extensions") or {}
        if isinstance(ext, dict):
            posted = str(ext.get("posted_at", "") or "")
        out.append(
            _job(
                source="google_jobs",
                url=url,
                title=str(j.get("title", "")),
                company=str(j.get("company_name", "")),
                location=str(j.get("location", "") or ""),
                description=str(j.get("description", "") or ""),
                posted_at=posted,
                apply_type=classify_apply_type(url),
            )
        )
    return [j for j in out if j.url]


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def scan_rss(feed_url: str, source_label: str = "rss") -> list[JobPosting]:
    """Parse an RSS 2.0 or Atom feed (stdlib only). Good for niche job boards."""
    if not feed_url.strip():
        return []
    resp = requests.get(feed_url, timeout=25, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    out: list[JobPosting] = []

    # RSS 2.0: channel/item ; Atom: feed/entry
    items = [el for el in root.iter() if _strip_ns(el.tag) in {"item", "entry"}]
    for item in items:
        title = ""
        link = ""
        desc = ""
        posted = ""
        for child in item:
            name = _strip_ns(child.tag)
            if name == "title":
                title = (child.text or "").strip()
            elif name == "link":
                # RSS: text; Atom: href attribute. Atom entries may carry several
                # <link>s (alternate/self/enclosure); the job page is rel="alternate"
                # (or the default when rel is omitted). Don't let a later self/edit
                # link overwrite the alternate — otherwise the applier navigates to
                # an API/self URL instead of the posting.
                href = (child.text or "").strip() or child.attrib.get("href", "").strip()
                if not href:
                    continue
                rel = child.attrib.get("rel", "").strip().lower()
                if rel in ("", "alternate") or not link:
                    link = href
            elif name in {"description", "summary", "content"}:
                desc = (child.text or "").strip()
            elif name in {"pubDate", "published", "updated"} and not posted:
                posted = (child.text or "").strip()
        out.append(
            _job(
                source=source_label,
                url=link,
                title=title,
                company=source_label,
                description=desc,
                posted_at=posted,
                apply_type=classify_apply_type(link),
            )
        )
    return [j for j in out if j.url]
