from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from io import BytesIO, StringIO
import os
from pathlib import Path
import re
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import stripe
from supabase import Client, create_client

from .assistant_agent import (
    assistant_mode_options,
    build_assistant_messages,
    create_thread_title,
    run_personal_assistant,
)
from .models import JobPosting
from .profile_options import company_matches_ranking, get_profile_option_payload
from .plans import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    COMPETITIVE_ADVANTAGES,
    PAID_PLAN_KEYS,
    get_plan_definition,
    normalize_plan,
    resolve_plan_from_price_id,
)
from .rag import MatchResult, recommend_jobs_rag, role_suggestions
from .resume_extractor import extract_profile_fields
from .role_catalog import get_roles_for_sector
from .aggregators import scan_jsearch, scan_rss, scan_serpapi_google_jobs
from .scanners import (
    scan_ashby,
    scan_greenhouse,
    scan_lever,
    scan_recruitee,
    scan_smartrecruiters,
)
from .storage import load_jobs
from .tailoring import TAILOR_MODES, run_tailoring

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None  # type: ignore[assignment]

try:
    from docx import Document
except Exception:
    Document = None  # type: ignore[assignment]


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_FILE = PROJECT_ROOT / "data" / "jobs.jsonl"
DEFAULT_LINKEDIN_IMPORT = PROJECT_ROOT / "data" / "imports" / "linkedin_jobs.csv"
DEFAULT_INDEED_IMPORT = PROJECT_ROOT / "data" / "imports" / "indeed_jobs.csv"
DEFAULT_IMPORTS_DIR = PROJECT_ROOT / "data" / "imports"

DEFAULT_GREENHOUSE_BOARDS = [
    "vercel",
    "stripe",
    "datadog",
    "airbnb",
    "databricks",
    "hubspotjobs",
    "Coinbase",
    "scaleai",
    "fivetran",
    "robinhood",
    "brex",
    "airtable",
    "discord",
    "webflow",
    "dropbox",
    "checkr",
    "asana",
    "cloudflare",
    "yugabyte",
    "samsara",
    "headway",
    "growtherapy",
    "transcarent",
]
DEFAULT_LEVER_SITES: list[str] = []
DEFAULT_ASHBY_ORGS = [
    "ramp",
    "openai",
    "notion",
    "linear",
    "runway",
    "mercury",
    "clipboardhealth",
    "vanta",
]
# Additional ATS sources (public APIs). Empty by default — configure per org via
# LIVE_SMARTRECRUITERS_COMPANIES / LIVE_RECRUITEE_COMPANIES env vars.
DEFAULT_SMARTRECRUITERS_COMPANIES: list[str] = []
DEFAULT_RECRUITEE_COMPANIES: list[str] = []


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _cors_origin_regex() -> str | None:
    # Useful for Vercel preview deployments:
    # https://<project>-<hash>-<team>.vercel.app
    raw = os.getenv("CORS_ORIGIN_REGEX", r"^https://[a-zA-Z0-9-]+\.vercel\.app$")
    value = raw.strip()
    return value if value else None


def _split_env_list(name: str, fallback: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return fallback
    return [x.strip() for x in raw.split(",") if x.strip()]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _premium_testing_enabled() -> bool:
    return _env_flag("ENABLE_PREMIUM_TEST_MODE", True)


def _load_import_jobs(path: Path, source: str) -> list[JobPosting]:
    if not path.exists():
        return []
    out: list[JobPosting] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("url") or "").strip()
            if not url:
                continue
            posted_at = (
                row.get("posted_at")
                or row.get("date_posted")
                or row.get("listed_at")
                or row.get("created_at")
                or row.get("updated_at")
                or ""
            )
            out.append(
                JobPosting(
                    id=f"{source}:{url}",
                    source=source,
                    company=(row.get("company") or "").strip() or "Unknown Company",
                    title=(row.get("title") or "").strip() or "Unknown Role",
                    location=(row.get("location") or "").strip() or "Unknown Location",
                    url=url,
                    description=(row.get("description") or "").strip(),
                    posted_at=str(posted_at).strip(),
                )
            )
    return out


def _load_import_jobs_from_directory(path: Path) -> list[JobPosting]:
    if not path.exists() or not path.is_dir():
        return []
    out: list[JobPosting] = []
    for csv_file in sorted(path.glob("*.csv")):
        source_name = csv_file.stem.replace("_jobs", "").replace("-", "_").strip() or "import"
        out.extend(_load_import_jobs(csv_file, source_name))
    return out


def _text_matches_query(job: JobPosting, query: str) -> bool:
    q = query.lower().strip()
    if not q:
        return True
    text = f"{job.title} {job.company} {job.location} {job.description[:2500]}".lower()
    tokens = [tok for tok in re.split(r"\s+", q) if tok and len(tok) > 1]
    hits = sum(1 for tok in tokens if tok in text)
    return q in text or hits >= max(1, min(2, len(tokens)))


def _dedupe_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    # First collapse exact-URL duplicates.
    by_url: dict[str, JobPosting] = {}
    for job in jobs:
        if not job.url:
            continue
        by_url.setdefault(job.url, job)

    def _role_key(job: JobPosting) -> str:
        return re.sub(r"\s+", " ", f"{job.company}|{job.title}|{job.location}".lower()).strip()

    def _is_direct(job: JobPosting) -> bool:
        # A directly-applyable listing (ATS-hosted or a company's own site).
        return job.apply_type in {"external_ats", "direct"}

    def _rank(job: JobPosting) -> int:
        score = 0
        if job.apply_type not in {"unknown", ""}:
            score += 1
        if job.description:
            score += 1
        return score

    # Keep EVERY distinct-URL direct/ATS listing — two different reqs at the same
    # company can share company+title+location, and each is separately applyable, so
    # they must not be collapsed into one. Record their role keys.
    result: list[JobPosting] = []
    direct_keys: set[str] = set()
    for job in by_url.values():
        if _is_direct(job):
            result.append(job)
            direct_keys.add(_role_key(job))

    # For aggregator listings (LinkedIn/Indeed/Glassdoor/Google Jobs/imports), collapse
    # the SAME role across platforms: drop one entirely when a direct listing already
    # covers that role, and otherwise keep the single most-actionable per role key.
    agg_best: dict[str, JobPosting] = {}
    for job in by_url.values():
        if _is_direct(job):
            continue
        key = _role_key(job)
        if key in direct_keys:
            continue  # a directly-applyable version wins over the aggregator link
        current = agg_best.get(key)
        if current is None or _rank(job) > _rank(current):
            agg_best[key] = job
    result.extend(agg_best.values())
    return result


def _redact_secrets(message: str) -> str:
    """Strip known API keys from diagnostics/error strings before they are returned
    to a client. SerpApi puts its key in the request URL, so a failed request's
    exception text would otherwise expose it via source_diagnostics."""
    out = message
    for env_name in ("SERPAPI_KEY", "RAPIDAPI_KEY", "ANTHROPIC_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "STRIPE_SECRET_KEY"):
        secret = os.getenv(env_name, "").strip()
        if secret and secret in out:
            out = out.replace(secret, "***")
    return out


# Short-TTL cache for the billable aggregator APIs (JSearch/SerpApi/RSS) so repeated
# /api/jobs/matches and /api/rag/match polling does not fire one paid request per call.
_AGG_CACHE: dict[str, tuple[float, list[JobPosting]]] = {}


def _aggregator_cache_ttl() -> float:
    try:
        return float(os.getenv("AGGREGATOR_CACHE_TTL", "900"))
    except ValueError:
        return 900.0


def _cached_aggregator_scan(cache_key: str, runner: Any) -> list[JobPosting]:
    ttl = _aggregator_cache_ttl()
    now = time.monotonic()
    if ttl > 0:
        hit = _AGG_CACHE.get(cache_key)
        if hit is not None and (now - hit[0]) < ttl:
            return hit[1]
    result = runner()  # only cached on success; exceptions propagate uncached
    if ttl > 0:
        _AGG_CACHE[cache_key] = (now, result)
    return result


# Per-user sliding-window rate limit for the discovery endpoints. Job discovery fans
# out to billable aggregator APIs (JSearch/SerpApi), so an authenticated user must not
# be able to hammer it. In-process only (per worker) — front with Redis for multi-node.
_DISCOVERY_HITS: dict[str, list[float]] = {}


def _enforce_discovery_rate_limit(user_id: str) -> None:
    try:
        limit = int(os.getenv("DISCOVERY_RATE_LIMIT", "20"))
    except ValueError:
        limit = 20
    try:
        window = float(os.getenv("DISCOVERY_RATE_WINDOW", "60"))
    except ValueError:
        window = 60.0
    if limit <= 0 or window <= 0 or not user_id:
        return
    now = time.monotonic()
    hits = [t for t in _DISCOVERY_HITS.get(user_id, []) if now - t < window]
    if len(hits) >= limit:
        retry_after = max(1, int(window - (now - hits[0])))
        raise HTTPException(
            status_code=429,
            detail=f"Too many match requests. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)
    _DISCOVERY_HITS[user_id] = hits


def _discover_live_jobs_with_diagnostics(
    query: str,
    limit: int = 600,
    greenhouse_limit: int | None = None,
    lever_limit: int | None = None,
    ashby_limit: int | None = None,
) -> tuple[list[JobPosting], dict[str, Any]]:
    jobs: list[JobPosting] = []
    diagnostics: dict[str, Any] = {
        "imports_loaded": 0,
        "sources_checked": 0,
        "sources_succeeded": 0,
        "source_counts": [],
        "source_errors": [],
    }

    # 1) Local import fallbacks if user uploaded LinkedIn/Indeed lists.
    imported_directory_jobs = _load_import_jobs_from_directory(DEFAULT_IMPORTS_DIR)
    if not imported_directory_jobs:
        imported_linkedin = _load_import_jobs(DEFAULT_LINKEDIN_IMPORT, "linkedin")
        imported_indeed = _load_import_jobs(DEFAULT_INDEED_IMPORT, "indeed")
        imported_directory_jobs = [*imported_linkedin, *imported_indeed]
    jobs.extend(imported_directory_jobs)
    diagnostics["imports_loaded"] = len(imported_directory_jobs)
    if imported_directory_jobs:
        per_source: dict[str, int] = {}
        for job in imported_directory_jobs:
            per_source[job.source] = per_source.get(job.source, 0) + 1
        for source_name, count in sorted(per_source.items()):
            diagnostics["source_counts"].append(
                {"source": source_name, "token": "imports", "jobs": count}
            )

    # 2) Public ATS sources (Greenhouse + Lever).
    greenhouse_tokens = _split_env_list("LIVE_GREENHOUSE_BOARDS", DEFAULT_GREENHOUSE_BOARDS)
    if greenhouse_limit is not None and greenhouse_limit > 0:
        greenhouse_tokens = greenhouse_tokens[:greenhouse_limit]
    for token in greenhouse_tokens:
        diagnostics["sources_checked"] += 1
        try:
            scanned = scan_greenhouse(token)
            jobs.extend(scanned)
            diagnostics["sources_succeeded"] += 1
            diagnostics["source_counts"].append(
                {"source": "greenhouse", "token": token, "jobs": len(scanned)}
            )
        except Exception as exc:
            if len(diagnostics["source_errors"]) < 8:
                diagnostics["source_errors"].append(_redact_secrets(f"greenhouse:{token}:{exc}"))
            continue
    lever_sites = _split_env_list("LIVE_LEVER_SITES", DEFAULT_LEVER_SITES)
    if lever_limit is not None and lever_limit > 0:
        lever_sites = lever_sites[:lever_limit]
    for site in lever_sites:
        diagnostics["sources_checked"] += 1
        try:
            scanned = scan_lever(site)
            jobs.extend(scanned)
            diagnostics["sources_succeeded"] += 1
            diagnostics["source_counts"].append(
                {"source": "lever", "token": site, "jobs": len(scanned)}
            )
        except Exception as exc:
            if len(diagnostics["source_errors"]) < 8:
                diagnostics["source_errors"].append(_redact_secrets(f"lever:{site}:{exc}"))
            continue

    ashby_orgs = _split_env_list("LIVE_ASHBY_BOARDS", DEFAULT_ASHBY_ORGS)
    if ashby_limit is not None and ashby_limit > 0:
        ashby_orgs = ashby_orgs[:ashby_limit]
    for org in ashby_orgs:
        diagnostics["sources_checked"] += 1
        try:
            scanned = scan_ashby(org)
            jobs.extend(scanned)
            diagnostics["sources_succeeded"] += 1
            diagnostics["source_counts"].append(
                {"source": "ashby", "token": org, "jobs": len(scanned)}
            )
        except Exception as exc:
            if len(diagnostics["source_errors"]) < 8:
                diagnostics["source_errors"].append(_redact_secrets(f"ashby:{org}:{exc}"))
            continue

    for source_name, env_name, defaults, scanner in (
        ("smartrecruiters", "LIVE_SMARTRECRUITERS_COMPANIES", DEFAULT_SMARTRECRUITERS_COMPANIES, scan_smartrecruiters),
        ("recruitee", "LIVE_RECRUITEE_COMPANIES", DEFAULT_RECRUITEE_COMPANIES, scan_recruitee),
    ):
        for token in _split_env_list(env_name, defaults):
            diagnostics["sources_checked"] += 1
            try:
                scanned = scanner(token)
                jobs.extend(scanned)
                diagnostics["sources_succeeded"] += 1
                diagnostics["source_counts"].append(
                    {"source": source_name, "token": token, "jobs": len(scanned)}
                )
            except Exception as exc:
                if len(diagnostics["source_errors"]) < 8:
                    diagnostics["source_errors"].append(_redact_secrets(f"{source_name}:{token}:{exc}"))
                continue

    # 3) Aggregator APIs (query-based) — cover LinkedIn/Indeed/Glassdoor/etc. and the
    # wider web via legitimate middle-layer APIs. Each is skipped unless configured.
    job_location = os.getenv("JOB_LOCATION", "").strip()
    aggregator_sources = [
        ("jsearch", lambda: scan_jsearch(query, location=job_location)),
        ("google_jobs", lambda: scan_serpapi_google_jobs(query, location=job_location)),
    ]
    for feed in _split_env_list("LIVE_RSS_FEEDS", []):
        aggregator_sources.append((f"rss:{feed[:40]}", (lambda f=feed: scan_rss(f))))
    for source_name, runner in aggregator_sources:
        diagnostics["sources_checked"] += 1
        try:
            scanned = _cached_aggregator_scan(f"{source_name}|{query}|{job_location}", runner)
        except Exception as exc:
            if len(diagnostics["source_errors"]) < 8:
                diagnostics["source_errors"].append(_redact_secrets(f"{source_name}:{exc}"))
            continue
        diagnostics["sources_succeeded"] += 1
        if not scanned:
            continue
        jobs.extend(scanned)
        diagnostics["source_counts"].append(
            {"source": source_name.split(":")[0], "token": "aggregator", "jobs": len(scanned)}
        )

    jobs = _dedupe_jobs(jobs)
    matched = [j for j in jobs if _text_matches_query(j, query)]
    diagnostics["scanned_jobs"] = len(jobs)
    diagnostics["query_filtered_jobs"] = len(matched)
    selected = matched if matched else jobs
    return selected[:limit], diagnostics


def _discover_live_jobs(
    query: str,
    limit: int = 600,
    greenhouse_limit: int | None = None,
    lever_limit: int | None = None,
    ashby_limit: int | None = None,
) -> list[JobPosting]:
    jobs, _ = _discover_live_jobs_with_diagnostics(
        query,
        limit=limit,
        greenhouse_limit=greenhouse_limit,
        lever_limit=lever_limit,
        ashby_limit=ashby_limit,
    )
    return jobs


def _clean_price_id(raw: str) -> str:
    cleaned = raw or ""
    cleaned = cleaned.replace("\\n", "").replace("\n", "").replace("\r", "").replace("\t", "")
    cleaned = cleaned.replace("\\", "").replace('"', "").replace("'", "").strip()
    # Strip accidental JSON fragments, spaces, etc.
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", cleaned)
    return cleaned


def _location_tokens(text: str) -> set[str]:
    return {token.strip().lower() for token in re.split(r"[,/|]+", text or "") if token.strip()}


def _country_terms(country: str) -> set[str]:
    selected = country.strip().lower()
    if not selected:
        return set()
    aliases = {
        "united states": {"united states", "usa", "us", "u.s.", "u.s.a."},
        "united kingdom": {"united kingdom", "uk", "u.k.", "great britain", "britain"},
        "united arab emirates": {"united arab emirates", "uae", "u.a.e."},
    }
    return aliases.get(selected, {selected})


def _job_matches_location_filters(job: JobPosting, app_profile: dict[str, Any]) -> bool:
    location_text = f"{job.location} {job.description[:800]}".lower()
    work_preferences = {str(x).strip().lower() for x in app_profile.get("work_preferences", []) or []}
    country = str(app_profile.get("country", "")).strip().lower()
    region = str(app_profile.get("region", "")).strip().lower()
    preferred = _location_tokens(str(app_profile.get("preferred_locations", "")))

    if "remote" in work_preferences and "remote" in location_text:
        return True

    location_terms = {token for token in preferred if len(token) > 1}
    if region:
        location_terms.add(region)
    if country:
        location_terms.update(_country_terms(country))

    if not location_terms:
        return True
    return any(term in location_text for term in location_terms)


_NO_SPONSORSHIP_PHRASES = (
    "not be able to sponsor",
    "unable to sponsor",
    "does not sponsor",
    "do not sponsor",
    "not sponsor",
    "no sponsorship",
    "without sponsorship",
    "not provide sponsorship",
    "not offer sponsorship",
    "not offer visa",
    "cannot provide visa",
    "not provide visa",
    "no visa sponsorship",
    "sponsorship is not available",
    "not eligible for sponsorship",
    "authorized to work in the united states without",
    "work authorization without sponsorship",
)


def _job_matches_work_authorization(job: JobPosting, app_profile: dict[str, Any]) -> bool:
    """Drop roles that explicitly won't sponsor when the user needs sponsorship."""
    needs_sponsorship = bool(app_profile.get("needs_sponsorship"))
    if not needs_sponsorship:
        return True
    blob = f"{job.title} {job.description[:2500]}".lower()
    return not any(phrase in blob for phrase in _NO_SPONSORSHIP_PHRASES)


def _job_matches_sector(job: JobPosting, sector: str) -> bool:
    roles = get_roles_for_sector(sector)
    if not roles:
        return True
    blob = f"{job.title} {job.description[:1200]}".lower()
    return any(role.lower() in blob for role in roles)


def _filter_jobs_by_profile_preferences(
    jobs: list[JobPosting],
    app_profile: dict[str, Any],
) -> list[JobPosting]:
    selected_sector = str(app_profile.get("target_sector", "")).strip()
    company_ranking_filter = str(app_profile.get("company_ranking_filter", "any")).strip()

    filtered = [
        job
        for job in jobs
        if _job_matches_location_filters(job, app_profile)
        and _job_matches_sector(job, selected_sector)
        and _job_matches_work_authorization(job, app_profile)
        and company_matches_ranking(job.company, company_ranking_filter)
    ]
    return filtered if filtered else jobs


def build_application_answers(profile: dict[str, Any] | None) -> list[dict[str, str]]:
    """Derive common screening / work-authorization answers from the saved profile.

    Used to pre-fill the standard questions ATS forms ask (work authorization,
    sponsorship, relocation, salary) so the user does not re-answer them per app.
    """
    if not profile:
        return []
    app_profile = profile.get("application_profile") or {}
    status = str(app_profile.get("work_authorization_status", "") or "").strip()
    needs_sponsorship = bool(app_profile.get("needs_sponsorship"))
    willing_to_relocate = bool(app_profile.get("willing_to_relocate"))
    salary = str(app_profile.get("salary_expectation", "") or "").strip()
    country = str(app_profile.get("country", "") or "").strip()

    authorized = bool(status) and not needs_sponsorship
    answers: list[dict[str, str]] = []
    if country:
        answers.append(
            {
                "question": f"Are you legally authorized to work in {country}?",
                "answer": "Yes" if authorized or status else "No",
            }
        )
    answers.append(
        {
            "question": "Will you now or in the future require sponsorship for employment "
            "visa status (e.g., H-1B)?",
            "answer": "Yes" if needs_sponsorship else "No",
        }
    )
    if status:
        answers.append({"question": "Current work authorization / visa status", "answer": status})
    answers.append(
        {
            "question": "Are you willing to relocate?",
            "answer": "Yes" if willing_to_relocate else "No",
        }
    )
    if salary:
        answers.append({"question": "Salary expectation", "answer": salary})
    return answers


def _profile_context_blob(profile: dict[str, Any] | None) -> str:
    if not profile:
        return ""
    fields = [
        str(profile.get("target_role", "")),
        str(profile.get("experience_level", "")),
        " ".join(profile.get("skills", []) or []),
    ]
    application_profile = profile.get("application_profile") or {}
    if isinstance(application_profile, dict):
        fields.extend(
            [
                str(application_profile.get("target_sector", "")),
                str(application_profile.get("country", "")),
                str(application_profile.get("region", "")),
                str(application_profile.get("work_authorization_status", "")),
                str(application_profile.get("preferred_locations", "")),
                str(application_profile.get("company_ranking_filter", "")),
                str(application_profile.get("summary", "")),
            ]
        )
    return "\n".join(x for x in fields if x)


def _sanitize_sub_profiles(raw_items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items or []):
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("id", "") or f"sub_profile_{index + 1}").strip()
        role = str(item.get("target_role", "")).strip()
        name = str(item.get("name", "")).strip() or role or f"Profile {index + 1}"
        sector = str(item.get("target_sector", "")).strip()
        preferred_locations = str(item.get("preferred_locations", "")).strip()
        work_preferences = item.get("work_preferences", []) or []
        if isinstance(work_preferences, str):
            work_preferences = [part.strip() for part in work_preferences.split(",") if part.strip()]
        else:
            work_preferences = [str(part).strip() for part in work_preferences if str(part).strip()]
        companies_to_avoid = str(item.get("companies_to_avoid", "")).strip()
        minimum_match_score = float(item.get("minimum_match_score", 80.0) or 80.0)
        kpi_focus = str(item.get("kpi_focus", "")).strip()
        cleaned.append(
            {
                "id": identifier,
                "name": name,
                "target_role": role,
                "target_sector": sector,
                "preferred_locations": preferred_locations,
                "work_preferences": work_preferences,
                "companies_to_avoid": companies_to_avoid,
                "minimum_match_score": minimum_match_score,
                "kpi_focus": kpi_focus,
            }
        )
    return cleaned[:8]


@lru_cache(maxsize=1)
def _fetch_roles_from_google_form_csv() -> list[str]:
    """
    Expected GOOGLE_FORM_ROLES_CSV_URL to be a public Google Sheet CSV export URL.
    Column names supported: target_role, role, desired_role, job_title.
    """
    url = os.getenv("GOOGLE_FORM_ROLES_CSV_URL", "").strip()
    if not url:
        return []
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        reader = csv.DictReader(StringIO(resp.text))
        roles: set[str] = set()
        for row in reader:
            for key, value in row.items():
                k = (key or "").strip().lower()
                if k not in {"target_role", "role", "desired_role", "job_title"}:
                    continue
                cell = (value or "").strip()
                if not cell:
                    continue
                for part in re.split(r"[|,/;\n]+", cell):
                    role = part.strip()
                    if role:
                        roles.add(role)
        return sorted(roles)
    except Exception:
        return []


def _search_roles(query: str, sector: str = "") -> list[str]:
    extra_roles = _fetch_roles_from_google_form_csv()
    return role_suggestions(query, extra_roles=extra_roles, limit=20, sector=sector)


def _send_application_confirmation_email(to_email: str, role: str, job: JobPosting) -> bool:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("EMAIL_FROM", "").strip()
    if not api_key or not from_email or not to_email:
        return False

    body = {
        "from": from_email,
        "to": [to_email],
        "subject": f"AIapply.ai - Application queued for {job.title}",
        "html": (
            f"<p>A job application draft has been queued for role <strong>{role or 'General'}</strong>.</p>"
            f"<p><strong>{job.title}</strong> at <strong>{job.company}</strong><br/>"
            f"Location: {job.location}<br/>"
            f"URL: <a href='{job.url}'>{job.url}</a></p>"
            "<p>Please review your dashboard and resume details before any final submission.</p>"
        ),
    }
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=20,
        )
        return 200 <= resp.status_code < 300
    except Exception:
        return False


def _send_job_match_digest_email(
    to_email: str, role: str, cards: list[dict[str, Any]]
) -> bool:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("EMAIL_FROM", "").strip()
    if not api_key or not from_email or not to_email or not cards:
        return False
    rows = "".join(
        (
            f"<li><strong>{c.get('title', '')}</strong> at {c.get('company', '')}"
            f" — {c.get('location', '')}"
            f" (match {c.get('ats_score', 0)}%)"
            f" <a href='{c.get('url', '')}'>view</a></li>"
        )
        for c in cards[:10]
    )
    body = {
        "from": from_email,
        "to": [to_email],
        "subject": f"AIapply.ai - {len(cards)} new matches for {role or 'your search'}",
        "html": (
            f"<p>New roles matching <strong>{role or 'your search'}</strong>:</p>"
            f"<ul>{rows}</ul>"
            "<p>Open your dashboard to tailor and apply.</p>"
        ),
    }
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=20,
        )
        return 200 <= resp.status_code < 300
    except Exception:
        return False


app = FastAPI(title="AIapply.ai Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_resume_text(filename: str, payload: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".txt", ".md"}:
        return payload.decode("utf-8", errors="ignore")
    if suffix == ".pdf":
        if PdfReader is None:
            raise ValueError("PDF parser not installed on server.")
        reader = PdfReader(BytesIO(payload))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix == ".docx":
        if Document is None:
            raise ValueError("DOCX parser not installed on server.")
        doc = Document(BytesIO(payload))
        return "\n".join(p.text for p in doc.paragraphs if p.text)
    raise ValueError("Unsupported file. Use PDF, DOCX, TXT, or MD.")


def _parse_iso_datetime(raw: str) -> datetime | None:
    value = str(raw or "").strip()
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _posted_relative_label(raw: str) -> tuple[str, str, int | None]:
    parsed = _parse_iso_datetime(raw)
    if parsed is None:
        return "", "unknown", None
    delta = max(datetime.now(timezone.utc) - parsed, timedelta(0))
    days = delta.days
    if delta < timedelta(days=1):
        hours = max(1, int(delta.total_seconds() // 3600) or 0)
        return ("Today" if hours <= 6 else f"{hours} hours ago"), "past_24_hours", 0
    if days < 7:
        return ("1 day ago" if days == 1 else f"{days} days ago"), "past_week", days
    if days < 30:
        weeks = max(1, round(days / 7))
        return ("1 week ago" if weeks == 1 else f"{weeks} weeks ago"), "past_month", days
    months = max(1, round(days / 30))
    return ("1 month ago" if months == 1 else f"{months} months ago"), "older", days


def _results_to_cards(results: list[MatchResult], min_score: float) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for result in results:
        if result.final_score < min_score:
            continue
        ats_score = int(
            round(
                min(
                    100.0,
                    (
                        62.0 * result.final_score
                        + 22.0 * result.rag_score
                        + 16.0 * min(len(result.overlap_terms) / 8.0, 1.0)
                    )
                    * 100.0,
                )
            )
        )
        posted_raw = result.job.posted_at or result.job.discovered_at
        posted_relative, posted_bucket, posted_days_ago = _posted_relative_label(posted_raw)
        cards.append(
            {
                "title": result.job.title,
                "company": result.job.company,
                "location": result.job.location,
                "url": result.job.url,
                "source": result.job.source,
                "apply_type": result.job.apply_type,
                "rag_score": round(result.rag_score * 5.0, 2),
                "final_score": round(result.final_score * 5.0, 2),
                "ats_score": ats_score,
                "overlap_terms": result.overlap_terms,
                "explanation": result.explanation,
                "posted_at": posted_raw,
                "posted_relative": posted_relative,
                "posted_bucket": posted_bucket,
                "posted_days_ago": posted_days_ago,
            }
        )
    return cards


def _supabase() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase is not configured.")
    return create_client(url, key)


def _stripe_config() -> None:
    secret = os.getenv("STRIPE_SECRET_KEY", "")
    if not secret:
        raise HTTPException(status_code=500, detail="Stripe is not configured.")
    stripe.api_key = secret


def _extract_user_from_auth_response(resp: Any) -> Any:
    if hasattr(resp, "user"):
        return resp.user
    data = getattr(resp, "data", None)
    if data is not None and hasattr(data, "user"):
        return data.user
    if isinstance(resp, dict):
        if "user" in resp:
            return resp.get("user")
        nested = resp.get("data")
        if isinstance(nested, dict):
            return nested.get("user")
    return None


def _token_from_header(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header.")
    return parts[1]


def _to_dict(model_or_dict: Any) -> dict[str, Any]:
    if isinstance(model_or_dict, dict):
        return model_or_dict
    if hasattr(model_or_dict, "model_dump"):
        return model_or_dict.model_dump()
    if hasattr(model_or_dict, "dict"):
        return model_or_dict.dict()
    return {}


def _user_id_from_user(user: Any) -> str:
    as_dict = _to_dict(user)
    uid = as_dict.get("id")
    if uid:
        return str(uid)
    uid = getattr(user, "id", None)
    if uid:
        return str(uid)
    raise HTTPException(status_code=401, detail="User id not found in token.")


def _current_user(authorization: str | None) -> dict[str, Any]:
    token = _token_from_header(authorization)
    sb = _supabase()
    try:
        resp = sb.auth.get_user(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    user = _extract_user_from_auth_response(resp)
    if user is None:
        raise HTTPException(status_code=401, detail="Token verification failed.")
    return _to_dict(user)


class ProfileUpsertRequest(BaseModel):
    full_name: str = ""
    target_role: str = ""
    skills: list[str] = []
    experience_level: str = ""
    target_sector: str = ""
    phone: str = ""
    location: str = ""
    country: str = ""
    region: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    work_authorization_status: str = ""
    needs_sponsorship: bool = False
    veteran_status: str = ""
    race_ethnicity: str = ""
    gender_identity: str = ""
    disability_status: str = ""
    preferred_locations: str = ""
    willing_to_relocate: bool = False
    salary_expectation: str = ""
    auto_apply_enabled: bool = False
    auto_apply_consent: bool = False
    require_approval_before_apply: bool = True
    job_alerts_enabled: bool = False
    work_preferences: list[str] = []
    company_ranking_filter: str = "any"
    companies_to_avoid: str = ""
    max_applications_per_day: int = 10
    minimum_match_score: float = 30.0
    application_summary: str = ""
    bookmarks: list[dict[str, Any]] = []
    permission_requests: list[dict[str, Any]] = []
    auto_apply_queue: list[dict[str, Any]] = []
    sub_profiles: list[dict[str, Any]] = []
    active_sub_profile_id: str = ""
    tailored_documents: list[dict[str, Any]] = []
    resume_storage_path: str = ""
    resume_filename: str = ""


class TailorRequest(BaseModel):
    mode: str = "resume"
    job_title: str = ""
    company: str = ""
    job_description: str = ""
    base_text: str = ""


class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str
    mode: str = "subscription"


class AutoApplyRequest(BaseModel):
    role: str = ""
    custom_role: str = ""
    max_jobs: int = 8
    selected_jobs: list[dict[str, Any]] = []


class AutoApplySubmitRequest(BaseModel):
    application_id: int
    dry_run: bool = True


class AssistantChatRequest(BaseModel):
    mode: str = "job_search_planning"
    message: str
    thread_id: int | None = None


class ApplicationStatusRequest(BaseModel):
    status: str


# Statuses a user is allowed to move an application into from the dashboard.
# Ordering here also defines the pipeline board columns (see frontend PIPELINE_STAGES).
ALLOWED_APPLICATION_STATUSES = {
    "approval_required",
    "queued_auto_apply",
    "viewed",
    "applied",
    "replied",
    "interviewing",
    "rejected",
    "withdrawn",
}


def _count_today_applications(sb: Client, user_id: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        resp = (
            sb.table("applications")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("created_at", today)
            .execute()
        )
        count = getattr(resp, "count", None)
        return int(count or 0)
    except Exception:
        return 0


def _count_month_applications(sb: Client, user_id: str) -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        resp = (
            sb.table("applications")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("created_at", since)
            .execute()
        )
        return int(getattr(resp, "count", 0) or 0)
    except Exception:
        return 0


def _fetch_profile_row(sb: Client, user_id: str) -> dict[str, Any] | None:
    resp = sb.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    rows = getattr(resp, "data", []) or []
    return rows[0] if rows else None


def _latest_paid_payment_exists(sb: Client, user_id: str) -> bool:
    try:
        resp = (
            sb.table("payments")
            .select("id,status")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
    except Exception:
        return False
    rows = getattr(resp, "data", []) or []
    paid_statuses = {"paid", "active", "complete", "succeeded"}
    return any(str(row.get("status", "")).lower() in paid_statuses for row in rows)


def _subscription_row(sb: Client, user_id: str) -> dict[str, Any] | None:
    try:
        resp = (
            sb.table("subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        return None
    rows = getattr(resp, "data", []) or []
    return rows[0] if rows else None


def _assistant_prompt_usage(sb: Client, user_id: str) -> int:
    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        resp = (
            sb.table("assistant_messages")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("role", "user")
            .gte("created_at", start_of_month.isoformat())
            .execute()
        )
    except Exception:
        return 0
    return int(getattr(resp, "count", 0) or 0)


def _resolve_subscription_state(
    sb: Client,
    user_id: str,
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    row = profile or {}
    manual_pro_access = bool(row.get("manual_pro_access"))
    raw_plan_value = str(row.get("plan", "") or "").strip()
    raw_plan = normalize_plan(raw_plan_value or "basic")
    raw_status = str(row.get("plan_status", "inactive") or "inactive").strip().lower()
    stripe_customer_id = str(row.get("stripe_customer_id", "") or "").strip()

    # Tier resolution: pick the specific paid tier from the subscription's price id.
    tier_key = "pro"
    subscription = _subscription_row(sb, user_id)
    if subscription:
        stripe_customer_id = stripe_customer_id or str(subscription.get("stripe_customer_id", "") or "").strip()
        subscription_status = str(subscription.get("status", "") or "").strip().lower()
        tier_key = resolve_plan_from_price_id(subscription.get("stripe_price_id"), default="pro")
        if subscription_status in ACTIVE_SUBSCRIPTION_STATUSES:
            raw_plan = tier_key
            raw_status = subscription_status

    if manual_pro_access:
        raw_plan = "pro"
        raw_status = "manual"
    elif raw_plan in PAID_PLAN_KEYS and raw_status in ACTIVE_SUBSCRIPTION_STATUSES:
        pass
    elif not raw_plan_value and _latest_paid_payment_exists(sb, user_id):
        raw_plan = tier_key
        raw_status = "paid"
    else:
        raw_plan = "basic"
        raw_status = "inactive"

    testing_mode = _premium_testing_enabled()
    if testing_mode:
        raw_plan = "pro"
        raw_status = "testing"

    plan = get_plan_definition(raw_plan)
    assistant_prompts_used = _assistant_prompt_usage(sb, user_id)
    assistant_limit = plan.assistant_monthly_prompts
    assistant_remaining = None if assistant_limit is None else max(0, assistant_limit - assistant_prompts_used)
    monthly_limit = plan.monthly_application_limit
    monthly_used = _count_month_applications(sb, user_id) if monthly_limit else 0
    monthly_remaining = None if not monthly_limit else max(0, monthly_limit - monthly_used)
    return {
        "plan": plan.key,
        "label": plan.label,
        "status": raw_status,
        "testing_mode": testing_mode,
        "price_usd": plan.price_usd,
        "stripe_customer_id": stripe_customer_id,
        "manual_pro_access": manual_pro_access,
        "assistant_prompts_used": assistant_prompts_used,
        "assistant_prompts_limit": assistant_limit,
        "assistant_prompts_remaining": assistant_remaining,
        "applications_used_this_month": monthly_used,
        "applications_monthly_limit": monthly_limit,
        "applications_monthly_remaining": monthly_remaining,
        "features": {
            "can_job_match": plan.can_job_match,
            "can_auto_apply": plan.can_auto_apply,
            "can_run_continuous_auto_apply": plan.can_run_continuous_auto_apply,
            "can_use_assistant": plan.can_use_assistant,
            "max_auto_apply_per_day": plan.max_auto_apply_per_day,
            "monthly_application_limit": monthly_limit,
            "assistant_modes": plan.assistant_modes,
            "highlights": plan.highlights,
        },
    }


def _require_feature(subscription: dict[str, Any], feature: str, detail: str) -> None:
    if not bool(subscription.get("features", {}).get(feature)):
        raise HTTPException(status_code=403, detail=detail)


def _monthly_available_slots(
    sb: Client, user_id: str, plan_monthly_limit: int | None
) -> int | None:
    """Remaining applications this 30-day window, or None if the plan is uncapped."""
    if not plan_monthly_limit or plan_monthly_limit <= 0:
        return None
    used = _count_month_applications(sb, user_id)
    return max(0, plan_monthly_limit - used)


def _run_auto_apply_for_profile(
    sb: Client,
    user_id: str,
    user_email: str,
    profile: dict[str, Any],
    role_query: str,
    max_jobs: int | None = None,
    plan_max_auto_apply_per_day: int | None = None,
    plan_monthly_limit: int | None = None,
) -> dict[str, Any]:
    app_profile = profile.get("application_profile") or {}
    auto_enabled = bool(app_profile.get("auto_apply_enabled"))
    auto_consent = bool(app_profile.get("auto_apply_consent"))
    if not auto_enabled or not auto_consent:
        raise HTTPException(
            status_code=400,
            detail=(
                "Auto Apply requires explicit consent. Enable auto_apply_enabled and "
                "auto_apply_consent in profile settings first."
            ),
        )

    daily_cap = max(1, min(int(app_profile.get("max_applications_per_day", 10) or 10), 50))
    if plan_max_auto_apply_per_day is not None and plan_max_auto_apply_per_day > 0:
        daily_cap = min(daily_cap, plan_max_auto_apply_per_day)
    if max_jobs is not None:
        daily_cap = min(daily_cap, max(1, min(max_jobs, 50)))

    existing_today = _count_today_applications(sb, user_id)
    available_slots = max(0, daily_cap - existing_today)
    monthly_slots = _monthly_available_slots(sb, user_id, plan_monthly_limit)
    if monthly_slots is not None:
        available_slots = min(available_slots, monthly_slots)
    if available_slots == 0:
        reached = "Monthly" if monthly_slots == 0 else "Daily"
        return {
            "role": role_query,
            "matched_jobs": 0,
            "queued_applications": 0,
            "email_confirmations_sent": 0,
            "message": f"{reached} auto-apply limit already reached for this user.",
        }

    avoid_text = str(app_profile.get("companies_to_avoid", "") or "")
    avoid_companies = {x.strip().lower() for x in avoid_text.split(",") if x.strip()}
    require_approval = bool(app_profile.get("require_approval_before_apply", True))
    minimum_match_score = float(app_profile.get("minimum_match_score", 30.0) or 30.0)

    jobs = _discover_live_jobs(
        role_query, limit=160, greenhouse_limit=10, lever_limit=10, ashby_limit=8
    )
    matched = [j for j in jobs if _text_matches_query(j, role_query)]
    matched = _filter_jobs_by_profile_preferences(matched, app_profile)
    if avoid_companies:
        matched = [j for j in matched if j.company.lower() not in avoid_companies]
    profile_context = _profile_context_blob(profile)
    _, _, rag_matches = recommend_jobs_rag(
        jobs=matched,
        resume_text=profile_context or role_query,
        selected_role="custom",
        custom_role=role_query,
        top_k=max(available_slots * 4, 20),
        sector=str(app_profile.get("target_sector", "")).strip(),
    )
    min_threshold = max(0.0, min(100.0, minimum_match_score)) / 100.0
    ranked_jobs = [
        item.job for item in rag_matches if item.final_score >= min_threshold
    ]
    matched = ranked_jobs[:available_slots]

    queued = 0
    emails_sent = 0
    for job in matched:
        try:
            sb.table("applications").insert(
                {
                    "user_id": user_id,
                    "job_url": job.url,
                    "company": job.company,
                    "title": job.title,
                    "location": job.location,
                    "status": "approval_required" if require_approval else "queued_auto_apply",
                    "notes": (
                        "Queued by AIapply.ai continuous auto-apply flow."
                        if not require_approval
                        else "Awaiting user approval before submission."
                    ),
                }
            ).execute()
            queued += 1
            if _send_application_confirmation_email(
                to_email=user_email,
                role=role_query,
                job=job,
            ):
                emails_sent += 1
        except Exception:
            continue

    return {
        "role": role_query,
        "matched_jobs": len(matched),
        "queued_applications": queued,
        "email_confirmations_sent": emails_sent,
        "message": (
            "Auto Apply run completed."
            if not require_approval
            else "Auto Apply run completed in approval-required mode."
        ),
    }


def _queue_selected_jobs_for_profile(
    sb: Client,
    user_id: str,
    user_email: str,
    profile: dict[str, Any],
    role_query: str,
    selected_jobs: list[dict[str, Any]],
    max_jobs: int | None = None,
    plan_max_auto_apply_per_day: int | None = None,
    plan_monthly_limit: int | None = None,
) -> dict[str, Any]:
    app_profile = profile.get("application_profile") or {}
    auto_enabled = bool(app_profile.get("auto_apply_enabled"))
    auto_consent = bool(app_profile.get("auto_apply_consent"))
    if not auto_enabled or not auto_consent:
        raise HTTPException(
            status_code=400,
            detail=(
                "Auto Apply requires explicit consent. Enable auto_apply_enabled and "
                "auto_apply_consent in profile settings first."
            ),
        )

    daily_cap = max(1, min(int(app_profile.get("max_applications_per_day", 10) or 10), 50))
    if plan_max_auto_apply_per_day is not None and plan_max_auto_apply_per_day > 0:
        daily_cap = min(daily_cap, plan_max_auto_apply_per_day)
    if max_jobs is not None:
        daily_cap = min(daily_cap, max(1, min(max_jobs, 50)))

    existing_today = _count_today_applications(sb, user_id)
    available_slots = max(0, daily_cap - existing_today)
    monthly_slots = _monthly_available_slots(sb, user_id, plan_monthly_limit)
    if monthly_slots is not None:
        available_slots = min(available_slots, monthly_slots)
    if available_slots == 0:
        reached = "Monthly" if monthly_slots == 0 else "Daily"
        return {
            "role": role_query,
            "matched_jobs": len(selected_jobs),
            "queued_applications": 0,
            "email_confirmations_sent": 0,
            "message": f"{reached} auto-apply limit already reached for this user.",
        }

    avoid_text = str(app_profile.get("companies_to_avoid", "") or "")
    avoid_companies = {x.strip().lower() for x in avoid_text.split(",") if x.strip()}
    require_approval = bool(app_profile.get("require_approval_before_apply", True))
    minimum_match_score = float(app_profile.get("minimum_match_score", 30.0) or 30.0)

    candidates = []
    for raw in selected_jobs:
        if not isinstance(raw, dict):
            continue
        company = str(raw.get("company", "") or "").strip()
        title = str(raw.get("title", "") or "").strip()
        location = str(raw.get("location", "") or "").strip()
        source_url = str(raw.get("url", "") or "").strip()
        application_url = str(raw.get("application_url", "") or "").strip()
        permission_required = bool(raw.get("permission_required"))
        final_score = raw.get("final_score")
        if company.lower() in avoid_companies:
            continue
        if final_score is not None:
            try:
                normalized_score = float(final_score) * 20.0
                if normalized_score < minimum_match_score:
                    continue
            except Exception:
                pass
        if not source_url and not application_url:
            continue
        candidates.append({
            "company": company or "Unknown Company",
            "title": title or "Unknown Role",
            "location": location or "Unknown Location",
            "source_url": source_url,
            "application_url": application_url,
            "permission_required": permission_required,
            "posted_relative": str(raw.get("posted_relative", "") or "").strip(),
            "source": str(raw.get("source", "") or "").strip(),
        })

    candidates = candidates[:available_slots]
    queued = 0
    emails_sent = 0
    permission_count = 0

    for job in candidates:
        try:
            effective_url = job["application_url"] or job["source_url"]
            notes_parts = []
            if job["permission_required"]:
                permission_count += 1
                notes_parts.append("Permission-required application URL provided by user.")
            if job["application_url"] and job["source_url"] and job["application_url"] != job["source_url"]:
                notes_parts.append(f"Original source URL: {job['source_url']}")
            if job["posted_relative"]:
                notes_parts.append(f"Posted: {job['posted_relative']}")
            if job["source"]:
                notes_parts.append(f"Source: {job['source']}")
            notes_parts.append(
                "Awaiting user approval before submission."
                if require_approval
                else "Queued by AIapply.ai auto-apply workflow."
            )
            sb.table("applications").insert(
                {
                    "user_id": user_id,
                    "job_url": effective_url,
                    "company": job["company"],
                    "title": job["title"],
                    "location": job["location"],
                    "status": "approval_required" if require_approval else "queued_auto_apply",
                    "notes": " ".join(notes_parts),
                }
            ).execute()
            queued += 1
            email_job = JobPosting(
                id=f"manual:{effective_url}",
                source=str(job.get("source") or "manual"),
                company=job["company"],
                title=job["title"],
                location=job["location"],
                url=effective_url,
                description="",
            )
            if _send_application_confirmation_email(
                to_email=user_email,
                role=role_query,
                job=email_job,
            ):
                emails_sent += 1
        except Exception:
            continue

    mode_text = "approval-required mode" if require_approval else "auto-queue mode"
    permission_text = f" {permission_count} permission-required jobs included." if permission_count else ""
    return {
        "role": role_query,
        "matched_jobs": len(candidates),
        "queued_applications": queued,
        "email_confirmations_sent": emails_sent,
        "message": f"Auto Apply completed in {mode_text}.{permission_text}",
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "AIapply.ai Backend",
        "status": "running",
        "health": "/healthz",
        "docs": "/docs",
    }


@app.get("/api/auth/me")
def auth_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    return {"user": _current_user(authorization)}


@app.get("/api/roles/search")
def search_roles(q: str = "", sector: str = "") -> dict[str, Any]:
    return {"roles": _search_roles(q, sector=sector)}


@app.get("/api/profile/options")
def get_profile_options() -> dict[str, Any]:
    payload = get_profile_option_payload()
    payload["assistant_modes"] = assistant_mode_options()
    return payload


@app.post("/api/profile/upsert")
def upsert_profile(
    body: ProfileUpsertRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    existing_profile = _fetch_profile_row(sb, user_id)
    subscription = _resolve_subscription_state(sb, user_id, existing_profile)
    auto_apply_enabled = body.auto_apply_enabled if subscription["features"]["can_auto_apply"] else False
    sub_profiles = _sanitize_sub_profiles(body.sub_profiles)
    payload = {
        "id": user_id,
        "email": user.get("email", ""),
        "full_name": body.full_name,
        "target_role": body.target_role,
        "skills": body.skills,
        "experience_level": body.experience_level,
        "application_profile": {
            "target_sector": body.target_sector,
            "phone": body.phone,
            "location": body.location,
            "country": body.country,
            "region": body.region,
            "linkedin_url": body.linkedin_url,
            "portfolio_url": body.portfolio_url,
            "work_authorization_status": body.work_authorization_status,
            "needs_sponsorship": body.needs_sponsorship,
            "veteran_status": body.veteran_status,
            "race_ethnicity": body.race_ethnicity,
            "gender_identity": body.gender_identity,
            "disability_status": body.disability_status,
            "preferred_locations": body.preferred_locations,
            "willing_to_relocate": body.willing_to_relocate,
            "salary_expectation": body.salary_expectation,
            "auto_apply_enabled": auto_apply_enabled,
            "auto_apply_consent": body.auto_apply_consent,
            "require_approval_before_apply": body.require_approval_before_apply,
            "job_alerts_enabled": body.job_alerts_enabled,
            "work_preferences": body.work_preferences,
            "company_ranking_filter": body.company_ranking_filter,
            "companies_to_avoid": body.companies_to_avoid,
            "max_applications_per_day": body.max_applications_per_day,
            "minimum_match_score": body.minimum_match_score,
            "summary": body.application_summary,
            "bookmarks": body.bookmarks,
            "permission_requests": body.permission_requests,
            "auto_apply_queue": body.auto_apply_queue,
            "sub_profiles": sub_profiles,
            "active_sub_profile_id": body.active_sub_profile_id,
            "tailored_documents": body.tailored_documents[:50],
            "resume_storage_path": body.resume_storage_path,
            "resume_filename": body.resume_filename,
        },
    }
    try:
        sb.table("profiles").upsert(payload).execute()
    except Exception as exc:
        # Backward compatibility: if schema wasn't migrated yet, retry without new jsonb column.
        if "application_profile" in str(exc).lower():
            legacy_payload = dict(payload)
            legacy_payload.pop("application_profile", None)
            try:
                sb.table("profiles").upsert(legacy_payload).execute()
            except Exception as legacy_exc:
                raise HTTPException(status_code=500, detail=f"Failed to upsert profile: {legacy_exc}")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to upsert profile: {exc}")
    return {"ok": True, "profile": payload, "subscription": subscription}


@app.get("/api/profile/me")
def get_profile(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    try:
        resp = sb.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {exc}")
    rows = getattr(resp, "data", []) or []
    profile = rows[0] if rows else None
    return {"profile": profile, "subscription": _resolve_subscription_state(sb, user_id, profile)}


@app.get("/api/profile/application-answers")
def get_application_answers(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    profile = _fetch_profile_row(sb, user_id)
    return {"answers": build_application_answers(profile)}


@app.get("/api/subscription/me")
def get_subscription(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    profile = _fetch_profile_row(sb, user_id)
    return {
        "subscription": _resolve_subscription_state(sb, user_id, profile),
        "competitive_advantages": COMPETITIVE_ADVANTAGES,
    }


@app.get("/api/applications/me")
def get_applications(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    try:
        resp = (
            sb.table("applications")
            .select("*", count="exact")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch applications: {exc}")
    rows = getattr(resp, "data", []) or []
    return {"applications": rows, "count": int(getattr(resp, "count", 0) or 0)}


@app.post("/api/applications/{application_id}/status")
def update_application_status(
    application_id: int,
    body: ApplicationStatusRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    new_status = body.status.strip().lower()
    if new_status not in ALLOWED_APPLICATION_STATUSES:
        raise HTTPException(status_code=400, detail="Unsupported application status.")
    sb = _supabase()
    try:
        resp = (
            sb.table("applications")
            .update({"status": new_status})
            .eq("id", application_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update application: {exc}")
    rows = getattr(resp, "data", []) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Application not found.")
    return {"ok": True, "application": rows[0]}


def _latest_assistant_thread(sb: Client, user_id: str) -> dict[str, Any] | None:
    try:
        resp = (
            sb.table("assistant_threads")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(resp, "data", []) or []
        return rows[0] if rows else None
    except Exception:
        return None


def _assistant_messages_for_thread(sb: Client, user_id: str, thread_id: int) -> list[dict[str, Any]]:
    try:
        resp = (
            sb.table("assistant_messages")
            .select("*")
            .eq("user_id", user_id)
            .eq("thread_id", thread_id)
            .order("created_at")
            .limit(30)
            .execute()
        )
        return getattr(resp, "data", []) or []
    except Exception:
        return []


@app.get("/api/assistant/me")
def get_assistant_state(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    profile = _fetch_profile_row(sb, user_id)
    subscription = _resolve_subscription_state(sb, user_id, profile)
    latest_thread = _latest_assistant_thread(sb, user_id)
    messages: list[dict[str, Any]] = []
    if latest_thread:
        messages = _assistant_messages_for_thread(sb, user_id, int(latest_thread["id"]))
    return {
        "subscription": subscription,
        "modes": assistant_mode_options(),
        "active_thread": latest_thread,
        "messages": messages,
    }


@app.post("/api/assistant/chat")
def assistant_chat(
    body: AssistantChatRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    profile = _fetch_profile_row(sb, user_id)
    subscription = _resolve_subscription_state(sb, user_id, profile)
    _require_feature(
        subscription,
        "can_use_assistant",
        "Your plan does not include the Personal Assistant Agent.",
    )

    limit = subscription.get("assistant_prompts_limit")
    remaining = subscription.get("assistant_prompts_remaining")
    if limit is not None and isinstance(remaining, int) and remaining <= 0:
        raise HTTPException(
            status_code=403,
            detail="You have used all Personal Assistant prompts for this month. Upgrade to Pro for unlimited access.",
        )

    user_message = body.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Assistant message cannot be empty.")

    mode = body.mode.strip() or "job_search_planning"
    valid_modes = {item["value"] for item in assistant_mode_options()}
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail="Unsupported assistant mode.")

    thread_id = body.thread_id
    thread: dict[str, Any] | None = None
    if thread_id is not None:
        thread_resp = (
            sb.table("assistant_threads")
            .select("*")
            .eq("id", thread_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        thread_rows = getattr(thread_resp, "data", []) or []
        thread = thread_rows[0] if thread_rows else None
        if thread is None:
            raise HTTPException(status_code=404, detail="Assistant thread not found.")
    else:
        try:
            insert_resp = (
                sb.table("assistant_threads")
                .insert(
                    {
                        "user_id": user_id,
                        "mode": mode,
                        "title": create_thread_title(mode, user_message),
                    }
                )
                .execute()
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Assistant storage is not ready. Run the latest Supabase schema migration first. ({exc})",
            )
        inserted_rows = getattr(insert_resp, "data", []) or []
        thread = inserted_rows[0] if inserted_rows else None
        if thread is None:
            raise HTTPException(status_code=500, detail="Failed to create assistant thread.")
        thread_id = int(thread["id"])

    history_rows = _assistant_messages_for_thread(sb, user_id, int(thread_id))
    history = [
        {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
        for item in history_rows
    ]

    try:
        sb.table("assistant_messages").insert(
            {
                "thread_id": thread_id,
                "user_id": user_id,
                "role": "user",
                "content": user_message,
                "metadata": {"mode": mode},
            }
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Assistant message storage is not ready. Run the latest Supabase schema migration first. ({exc})",
        )

    try:
        assistant_text = run_personal_assistant(
            build_assistant_messages(
                mode=mode,
                profile=profile,
                history=history,
                latest_user_message=user_message,
                plan_label=str(subscription.get("label", "Basic")),
            ),
            user_id=user_id,
        )
    except requests.HTTPError as exc:
        detail = getattr(exc.response, "text", str(exc))
        raise HTTPException(status_code=502, detail=f"Assistant provider request failed: {detail}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        sb.table("assistant_messages").insert(
            {
                "thread_id": thread_id,
                "user_id": user_id,
                "role": "assistant",
                "content": assistant_text,
                "metadata": {"mode": mode},
            }
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Assistant response storage is not ready. Run the latest Supabase schema migration first. ({exc})",
        )
    try:
        sb.table("assistant_threads").update({"updated_at": datetime.now(timezone.utc).isoformat()}).eq(
            "id", thread_id
        ).eq("user_id", user_id).execute()
    except Exception:
        pass

    refreshed_subscription = _resolve_subscription_state(sb, user_id, profile)
    messages = _assistant_messages_for_thread(sb, user_id, int(thread_id))
    return {
        "thread_id": thread_id,
        "subscription": refreshed_subscription,
        "messages": messages,
        "assistant_message": assistant_text,
    }


def _match_jobs_for_profile(
    profile: dict[str, Any] | None,
    role_query: str,
    top_k: int = 30,
    discovery_limit: int = 400,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    app_profile = (profile or {}).get("application_profile") or {}
    live_jobs, diagnostics = _discover_live_jobs_with_diagnostics(role_query, limit=discovery_limit)
    jobs = _filter_jobs_by_profile_preferences(live_jobs, app_profile)
    profile_context = _profile_context_blob(profile)
    _, _, matches = recommend_jobs_rag(
        jobs=jobs,
        resume_text=profile_context or role_query,
        selected_role="custom",
        custom_role=role_query,
        top_k=max(1, min(top_k, 80)),
        sector=str(app_profile.get("target_sector", "")).strip(),
    )
    cards = _results_to_cards(matches, min_score=0.0)
    return cards, diagnostics


@app.get("/api/jobs/matches")
def get_job_matches(
    q: str = "",
    limit: int = 30,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Live monitoring feed: current matching roles for the saved profile.

    Unlike /api/rag/match this needs no resume upload — it blends the saved
    profile context and re-runs discovery so the dashboard can poll for new
    matches across Greenhouse, Lever, and Ashby.
    """
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    _enforce_discovery_rate_limit(user_id)
    sb = _supabase()
    profile = _fetch_profile_row(sb, user_id)
    role_query = q.strip() or str((profile or {}).get("target_role", "") or "").strip()
    if not role_query:
        raise HTTPException(
            status_code=400,
            detail="Set a target role in your profile (or pass q) before monitoring matches.",
        )
    cards, diagnostics = _match_jobs_for_profile(profile, role_query, top_k=limit)
    return {
        "role": role_query,
        "count": len(cards),
        "results": cards,
        "source_diagnostics": diagnostics,
    }


@app.post("/api/tailor")
def tailor_documents(
    body: TailorRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    profile = _fetch_profile_row(sb, user_id)
    subscription = _resolve_subscription_state(sb, user_id, profile)
    _require_feature(
        subscription,
        "can_use_assistant",
        "Resume tailoring requires the Personal Assistant, which your plan does not include.",
    )
    limit = subscription.get("assistant_prompts_limit")
    remaining = subscription.get("assistant_prompts_remaining")
    if limit is not None and isinstance(remaining, int) and remaining <= 0:
        raise HTTPException(
            status_code=403,
            detail="You have used all assistant credits this month. Upgrade to Pro for unlimited tailoring.",
        )

    mode = body.mode.strip().lower()
    if mode not in TAILOR_MODES:
        raise HTTPException(status_code=400, detail="Unsupported tailoring mode.")
    if not body.base_text.strip() and not profile:
        raise HTTPException(
            status_code=400,
            detail="Provide source resume text or save a profile before tailoring.",
        )

    try:
        result = run_tailoring(
            mode=mode,
            base_text=body.base_text,
            job_title=body.job_title,
            company=body.company,
            job_description=body.job_description,
            profile=profile,
            user_id=user_id,
        )
    except requests.HTTPError as exc:
        detail = getattr(exc.response, "text", str(exc))
        raise HTTPException(status_code=502, detail=f"Tailoring provider request failed: {detail}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Best-effort usage accounting so tailoring counts toward Basic limits.
    try:
        thread_resp = (
            sb.table("assistant_threads")
            .insert(
                {
                    "user_id": user_id,
                    "mode": "resume_improvement" if mode == "resume" else "cover_letter_generation",
                    "title": f"Tailored {mode.replace('_', ' ')}: {body.company or body.job_title or 'role'}"[:60],
                }
            )
            .execute()
        )
        thread_rows = getattr(thread_resp, "data", []) or []
        if thread_rows:
            sb.table("assistant_messages").insert(
                {
                    "thread_id": thread_rows[0]["id"],
                    "user_id": user_id,
                    "role": "user",
                    "content": f"[tailor:{mode}] {body.job_title} @ {body.company}",
                    "metadata": {"kind": "tailor", "mode": mode},
                }
            ).execute()
    except Exception:
        pass

    refreshed = _resolve_subscription_state(sb, user_id, profile)
    return {
        "mode": result.get("mode", mode),
        "tailored_text": result.get("tailored_text", ""),
        "changes": result.get("changes", []),
        "keywords": result.get("keywords", []),
        "subscription": refreshed,
    }


RESUME_BUCKET = os.getenv("SUPABASE_RESUME_BUCKET", "resumes")


@app.post("/api/resume/upload")
async def upload_resume(
    resume_file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Store the user's resume in Supabase Storage so the auto-submit engine can
    upload it to ATS forms. Requires a Storage bucket named by SUPABASE_RESUME_BUCKET
    (default 'resumes'). Returns the stored path to save on the profile.
    """
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    payload = await resume_file.read()
    filename = Path(resume_file.filename or "resume.pdf").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=400, detail="Use PDF, DOCX, TXT, or MD.")
    # Validate it parses so we don't store an unreadable file.
    try:
        text = _extract_resume_text(filename, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if len(text.strip()) < 40:
        raise HTTPException(status_code=400, detail="Resume text is too short.")

    storage_path = f"{user_id}/{filename}"
    sb = _supabase()
    content_type = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".md": "text/markdown",
    }[suffix]
    try:
        sb.storage.from_(RESUME_BUCKET).upload(
            storage_path,
            payload,
            {"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Resume upload failed. Ensure a Storage bucket '{RESUME_BUCKET}' exists. ({exc})"
            ),
        )

    # Parse the resume into structured fields so it becomes the source of truth for
    # candidate data (name, skills, links, summary, ...). LLM-first with a heuristic
    # fallback; missing fields stay empty and never overwrite existing data with blanks.
    extracted = extract_profile_fields(text, user_id)
    applied: dict[str, Any] = {}
    try:
        profile = _fetch_profile_row(sb, user_id) or {}
        app_profile = dict(profile.get("application_profile") or {})
        app_profile["resume_storage_path"] = storage_path
        app_profile["resume_filename"] = filename
        # Merge resume-derived jsonb fields, overwriting only when the resume had a value.
        for key in ("phone", "location", "linkedin_url", "portfolio_url", "github_url", "summary"):
            value = extracted.get(key)
            if value:
                app_profile[key] = value
                applied[key] = value

        payload: dict[str, Any] = {
            "id": user_id,
            "email": user.get("email", ""),
            "application_profile": app_profile,
        }
        # Top-level columns — overwrite only when the resume provided a value. We never
        # touch target_role (user-controlled) or the work-auth/screening answers.
        if extracted.get("full_name"):
            payload["full_name"] = extracted["full_name"]
            applied["full_name"] = extracted["full_name"]
        if extracted.get("experience_level"):
            payload["experience_level"] = extracted["experience_level"]
            applied["experience_level"] = extracted["experience_level"]
        if extracted.get("skills"):
            payload["skills"] = extracted["skills"]
            applied["skills"] = extracted["skills"]

        try:
            sb.table("profiles").upsert(payload).execute()
        except Exception as exc:
            # Backward compat: retry without the jsonb column if the schema predates it.
            if "application_profile" in str(exc).lower():
                legacy = dict(payload)
                legacy.pop("application_profile", None)
                sb.table("profiles").upsert(legacy).execute()
            else:
                raise
    except Exception:
        pass
    return {
        "ok": True,
        "resume_storage_path": storage_path,
        "resume_filename": filename,
        "extracted": applied,
    }


def _download_resume_to_temp(sb: Client, storage_path: str) -> str | None:
    if not storage_path:
        return None
    try:
        data = sb.storage.from_(RESUME_BUCKET).download(storage_path)
    except Exception:
        return None
    if not data:
        return None
    suffix = Path(storage_path).suffix or ".pdf"
    import tempfile

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(data)
        tmp.flush()
    finally:
        tmp.close()
    return tmp.name


@app.post("/api/rag/match")
async def rag_match(
    resume_file: UploadFile = File(...),
    role: str = Form("software_engineer"),
    custom_role: str = Form(""),
    top_k: int = Form(12),
    min_score: float = Form(1.8),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = _current_user(authorization)
    _enforce_discovery_rate_limit(_user_id_from_user(user))
    payload = await resume_file.read()
    try:
        resume_text = _extract_resume_text(resume_file.filename or "", payload).strip()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if len(resume_text) < 40:
        raise HTTPException(status_code=400, detail="Resume text is too short.")

    query_role = (custom_role.strip() if role == "custom" else role.strip()) or role

    jobs: list[JobPosting] = load_jobs(DEFAULT_JOBS_FILE)
    live_jobs, discovery_diagnostics = _discover_live_jobs_with_diagnostics(query_role, limit=800)
    if live_jobs:
        jobs = _dedupe_jobs([*jobs, *live_jobs])
    if not jobs:
        raise HTTPException(
            status_code=400,
            detail=(
                "No jobs found from configured imports or live ATS sources. Add imports in data/imports CSVs "
                "or configure LIVE_GREENHOUSE_BOARDS/LIVE_LEVER_SITES env vars."
            ),
        )

    # Blend profile context with resume context for better relevance.
    sb = _supabase()
    profile_blob = ""
    selected_sector = ""
    try:
        uid = _user_id_from_user(user)
        profile_resp = sb.table("profiles").select("*").eq("id", uid).limit(1).execute()
        rows = getattr(profile_resp, "data", []) or []
        current_profile = rows[0] if rows else None
        profile_blob = _profile_context_blob(current_profile)
        if current_profile:
            selected_sector = str(
                (current_profile.get("application_profile") or {}).get("target_sector", "")
            ).strip()
            jobs = _filter_jobs_by_profile_preferences(
                jobs,
                current_profile.get("application_profile") or {},
            )
    except Exception:
        profile_blob = ""

    combined_resume_context = resume_text if not profile_blob else f"{resume_text}\n\n{profile_blob}"

    selected_role_label, resume_keywords, matched = recommend_jobs_rag(
        jobs=jobs,
        resume_text=combined_resume_context,
        selected_role=role,
        custom_role=custom_role,
        top_k=max(1, min(top_k, 80)),
        sector=selected_sector,
    )
    strict_threshold = min_score / 5.0
    results = _results_to_cards(matched, min_score=strict_threshold)
    used_fallback = False
    message = f"Found {len(results)} matching jobs from {len(jobs)} scanned openings."
    if not results and matched:
        used_fallback = True
        results = _results_to_cards(matched, min_score=0.0)
        message = (
            f"No jobs cleared the strict threshold for '{selected_role_label}'. "
            f"Showing the best available matches from {len(jobs)} scanned openings instead."
        )
    elif not matched:
        message = (
            f"Scanned {len(jobs)} openings but did not find a close fit for '{selected_role_label}' yet. "
            "Try broader keywords such as backend, python, react, data, nurse, or remote."
        )
    return {
        "role": selected_role_label,
        "resume_keywords": resume_keywords,
        "count": len(results),
        "results": results,
        "scanned_jobs": len(jobs),
        "live_jobs": len(live_jobs),
        "used_fallback": used_fallback,
        "message": message,
        "source_diagnostics": discovery_diagnostics,
    }


@app.post("/api/payments/checkout")
def create_checkout(
    body: CheckoutRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    profile = _fetch_profile_row(sb, user_id)
    subscription = _resolve_subscription_state(sb, user_id, profile)
    if subscription["plan"] == "pro" and subscription["status"] in ACTIVE_SUBSCRIPTION_STATUSES:
        raise HTTPException(status_code=400, detail="This account already has active Pro access.")
    _stripe_config()
    cleaned_price_id = _clean_price_id(body.price_id)
    if not cleaned_price_id.startswith("price_"):
        raise HTTPException(status_code=400, detail="Invalid Stripe price id format.")
    try:
        session = stripe.checkout.Session.create(
            mode=body.mode,
            line_items=[{"price": cleaned_price_id, "quantity": 1}],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            client_reference_id=str(user_id),
            customer_email=str(user.get("email", "")),
            allow_promotion_codes=True,
            metadata={"plan": "pro", "price_id": cleaned_price_id},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stripe checkout failed: {exc}")
    return {"checkout_url": session.url, "session_id": session.id}


@app.post("/api/auto-apply/run")
def auto_apply_run(
    body: AutoApplyRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()

    profile = _fetch_profile_row(sb, user_id)
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not found. Save profile first.")
    subscription = _resolve_subscription_state(sb, user_id, profile)
    _require_feature(
        subscription,
        "can_auto_apply",
        "Auto Apply is available on the Pro plan. Upgrade to unlock hands-free applications.",
    )
    role_query = (body.custom_role.strip() if body.role == "custom" else body.role.strip()) or profile.get(
        "target_role", ""
    )
    max_jobs = max(1, min(body.max_jobs, 20))
    monthly_limit = subscription["features"].get("monthly_application_limit")
    if body.selected_jobs:
        return _queue_selected_jobs_for_profile(
            sb=sb,
            user_id=user_id,
            user_email=str(user.get("email", "")),
            profile=profile,
            role_query=role_query,
            selected_jobs=body.selected_jobs,
            max_jobs=max_jobs,
            plan_max_auto_apply_per_day=int(subscription["features"]["max_auto_apply_per_day"]),
            plan_monthly_limit=monthly_limit,
        )
    return _run_auto_apply_for_profile(
        sb=sb,
        user_id=user_id,
        user_email=str(user.get("email", "")),
        profile=profile,
        role_query=role_query,
        max_jobs=max_jobs,
        plan_max_auto_apply_per_day=int(subscription["features"]["max_auto_apply_per_day"]),
        plan_monthly_limit=monthly_limit,
    )


@app.post("/api/auto-apply/submit")
def auto_apply_submit(
    body: AutoApplySubmitRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    """Drive a headless browser to actually fill (and optionally submit) a queued
    application. Experimental: requires Playwright browsers on the host and a
    server-stored resume for document upload. Defaults to dry_run (fill only).
    """
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    profile = _fetch_profile_row(sb, user_id)
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not found. Save profile first.")
    subscription = _resolve_subscription_state(sb, user_id, profile)
    _require_feature(
        subscription,
        "can_auto_apply",
        "Auto Apply submission is available on the Pro plan.",
    )
    app_profile = profile.get("application_profile") or {}
    if not bool(app_profile.get("auto_apply_enabled")) or not bool(app_profile.get("auto_apply_consent")):
        raise HTTPException(
            status_code=400,
            detail="Enable Auto Apply and consent before submitting applications.",
        )

    try:
        resp = (
            sb.table("applications")
            .select("*")
            .eq("id", body.application_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load application: {exc}")
    rows = getattr(resp, "data", []) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Application not found.")
    application = rows[0]
    job_url = str(application.get("job_url", "") or "")
    if not job_url:
        raise HTTPException(status_code=400, detail="Application has no job URL to submit to.")

    applicant = {
        "name": str(profile.get("full_name", "") or ""),
        "email": str(profile.get("email", "") or user.get("email", "")),
        "phone": str(app_profile.get("phone", "") or ""),
        "location": str(app_profile.get("location", "") or ""),
        "linkedin": str(app_profile.get("linkedin_url", "") or ""),
        "portfolio": str(app_profile.get("portfolio_url", "") or ""),
    }
    resume_path = _download_resume_to_temp(sb, str(app_profile.get("resume_storage_path", "") or ""))
    if not resume_path:
        resume_path = os.getenv("AUTO_APPLY_RESUME_PATH", "").strip() or None
    require_approval = bool(app_profile.get("require_approval_before_apply", True))
    # Never auto-submit when the user still wants to approve each application.
    do_submit = bool(not body.dry_run and not require_approval)

    try:
        from .apply_bot import prepare_application
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Submission engine unavailable (Playwright not installed): {exc}",
        )

    result = prepare_application(
        job_url=job_url,
        applicant=applicant,
        resume_path=resume_path,
        answers=build_application_answers(profile),
        submit=do_submit,
        headless=True,
    )

    if result.get("submitted"):
        try:
            sb.table("applications").update({"status": "applied"}).eq(
                "id", body.application_id
            ).eq("user_id", user_id).execute()
        except Exception:
            pass

    return {
        "application_id": body.application_id,
        "dry_run": not do_submit,
        "resume_uploaded": bool(resume_path),
        "result": result,
    }


@app.post("/api/auto-apply/tick")
def auto_apply_tick(x_auto_apply_secret: str | None = Header(default=None)) -> dict[str, Any]:
    expected_secret = os.getenv("AUTO_APPLY_CRON_SECRET", "").strip()
    if not expected_secret or x_auto_apply_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid auto apply scheduler secret.")

    sb = _supabase()
    try:
        resp = sb.table("profiles").select("*").execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profiles: {exc}")

    profiles = getattr(resp, "data", []) or []
    processed = 0
    queued = 0
    emails_sent = 0
    alerts_sent = 0

    for profile in profiles:
        app_profile = profile.get("application_profile") or {}
        user_id = str(profile.get("id", "")).strip()
        user_email = str(profile.get("email", "")).strip()
        role_query = str(profile.get("target_role", "")).strip()
        if not user_id or not role_query:
            continue

        # Job-match alerts (available regardless of auto-apply) — email a digest
        # of fresh matches to users who opted in.
        if bool(app_profile.get("job_alerts_enabled")) and user_email:
            try:
                cards, _ = _match_jobs_for_profile(profile, role_query, top_k=10)
                fresh = [c for c in cards if c.get("posted_bucket") in {"past_24_hours", "past_week"}]
                if _send_job_match_digest_email(user_email, role_query, fresh or cards):
                    alerts_sent += 1
            except Exception:
                pass

        # Continuous auto-apply (Pro + explicit consent only).
        if not bool(app_profile.get("auto_apply_enabled")) or not bool(app_profile.get("auto_apply_consent")):
            continue
        try:
            subscription = _resolve_subscription_state(sb, user_id, profile)
            if not bool(subscription.get("features", {}).get("can_run_continuous_auto_apply")):
                continue
            result = _run_auto_apply_for_profile(
                sb=sb,
                user_id=user_id,
                user_email=user_email,
                profile=profile,
                role_query=role_query,
                plan_max_auto_apply_per_day=int(subscription["features"]["max_auto_apply_per_day"]),
                plan_monthly_limit=subscription["features"].get("monthly_application_limit"),
            )
            processed += 1
            queued += int(result.get("queued_applications", 0))
            emails_sent += int(result.get("email_confirmations_sent", 0))
        except Exception:
            continue

    return {
        "processed_profiles": processed,
        "queued_applications": queued,
        "email_confirmations_sent": emails_sent,
        "alert_digests_sent": alerts_sent,
    }


@app.post("/api/payments/webhook")
async def stripe_webhook(request: Request) -> dict[str, Any]:
    _stripe_config()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Missing STRIPE_WEBHOOK_SECRET.")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {exc}")

    if event["type"] == "checkout.session.completed":
        checkout = event["data"]["object"]
        user_id = checkout.get("client_reference_id")
        sb = _supabase()
        if user_id:
            try:
                sb.table("payments").insert(
                    {
                        "user_id": user_id,
                        "stripe_session_id": checkout.get("id"),
                        "status": checkout.get("payment_status", "unknown"),
                        "amount_total": checkout.get("amount_total"),
                        "currency": checkout.get("currency"),
                        "price_id": ((checkout.get("metadata") or {}).get("price_id", "")),
                        "mode": checkout.get("mode", ""),
                    }
                ).execute()
            except Exception:
                pass
            checkout_price_id = (checkout.get("metadata") or {}).get("price_id", "")
            try:
                sb.table("profiles").upsert(
                    {
                        "id": user_id,
                        "email": checkout.get("customer_details", {}).get("email", ""),
                        "plan": resolve_plan_from_price_id(checkout_price_id),
                        "plan_status": "active",
                        "stripe_customer_id": checkout.get("customer", ""),
                    }
                ).execute()
            except Exception:
                pass
            subscription_id = checkout.get("subscription")
            if subscription_id:
                try:
                    sb.table("subscriptions").upsert(
                        {
                            "user_id": user_id,
                            "stripe_customer_id": checkout.get("customer", ""),
                            "stripe_subscription_id": subscription_id,
                            "stripe_price_id": ((checkout.get("metadata") or {}).get("price_id", "")),
                            "status": "active",
                        },
                        on_conflict="stripe_subscription_id",
                    ).execute()
                except Exception:
                    pass

    elif event["type"] in {"customer.subscription.updated", "customer.subscription.deleted"}:
        # Keep entitlements in sync when a subscription is renewed, paused, or
        # cancelled. Without this, cancelled users would keep Pro access forever.
        subscription = event["data"]["object"]
        _apply_subscription_event(sb=_supabase(), subscription=subscription)

    return {"received": True}


def _apply_subscription_event(sb: Client, subscription: dict[str, Any]) -> None:
    stripe_subscription_id = str(subscription.get("id", "") or "")
    stripe_customer_id = str(subscription.get("customer", "") or "")
    status = str(subscription.get("status", "") or "").strip().lower()
    if not stripe_subscription_id:
        return

    # Resolve the owning user from the subscription or, failing that, the customer.
    user_id = ""
    try:
        resp = (
            sb.table("subscriptions")
            .select("user_id")
            .eq("stripe_subscription_id", stripe_subscription_id)
            .limit(1)
            .execute()
        )
        rows = getattr(resp, "data", []) or []
        if rows:
            user_id = str(rows[0].get("user_id", "") or "")
    except Exception:
        user_id = ""
    if not user_id and stripe_customer_id:
        try:
            resp = (
                sb.table("subscriptions")
                .select("user_id")
                .eq("stripe_customer_id", stripe_customer_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = getattr(resp, "data", []) or []
            if rows:
                user_id = str(rows[0].get("user_id", "") or "")
        except Exception:
            user_id = ""

    price_id = ""
    try:
        items = ((subscription.get("items") or {}).get("data") or [])
        if items:
            price_id = str(((items[0].get("price") or {}).get("id", "")) or "")
    except Exception:
        price_id = ""

    payload: dict[str, Any] = {
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_customer_id": stripe_customer_id,
        "status": status or "canceled",
        "cancel_at_period_end": bool(subscription.get("cancel_at_period_end")),
    }
    if user_id:
        payload["user_id"] = user_id
    if price_id:
        payload["stripe_price_id"] = price_id
    try:
        sb.table("subscriptions").upsert(
            payload, on_conflict="stripe_subscription_id"
        ).execute()
    except Exception:
        pass

    # Downgrade the profile when the subscription is no longer active.
    if user_id:
        active = status in ACTIVE_SUBSCRIPTION_STATUSES
        tier = resolve_plan_from_price_id(price_id) if active else "basic"
        try:
            sb.table("profiles").update(
                {
                    "plan": tier,
                    "plan_status": status if active else "canceled",
                }
            ).eq("id", user_id).execute()
        except Exception:
            pass
