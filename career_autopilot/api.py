from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
import os
from pathlib import Path
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import stripe
from supabase import Client, create_client

from .models import JobPosting
from .rag import MatchResult, recommend_jobs_rag
from .scanners import scan_greenhouse, scan_lever
from .storage import load_jobs

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

DEFAULT_ROLES = [
    "Software Engineer",
    "Data Scientist",
    "ML Engineer",
    "Nurse",
    "Product Manager",
    "Cybersecurity Analyst",
    "DevOps Engineer",
    "QA Engineer",
]
DEFAULT_GREENHOUSE_BOARDS = [
    "openai",
    "anthropic",
    "mistral",
    "vercel",
    "retool",
]
DEFAULT_LEVER_SITES = [
    "lever",
    "n8n",
]


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
            out.append(
                JobPosting(
                    id=f"{source}:{url}",
                    source=source,
                    company=(row.get("company") or "").strip() or "Unknown Company",
                    title=(row.get("title") or "").strip() or "Unknown Role",
                    location=(row.get("location") or "").strip() or "Unknown Location",
                    url=url,
                    description=(row.get("description") or "").strip(),
                )
            )
    return out


def _text_matches_query(job: JobPosting, query: str) -> bool:
    q = query.lower().strip()
    if not q:
        return True
    text = f"{job.title} {job.company} {job.location} {job.description[:2500]}".lower()
    tokens = [tok for tok in re.split(r"\s+", q) if tok]
    return any(tok in text for tok in tokens) or q in text


def _dedupe_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    by_url: dict[str, JobPosting] = {}
    for job in jobs:
        if not job.url:
            continue
        if job.url not in by_url:
            by_url[job.url] = job
    return list(by_url.values())


def _discover_live_jobs(query: str, limit: int = 250) -> list[JobPosting]:
    jobs: list[JobPosting] = []

    # 1) Local import fallbacks if user uploaded LinkedIn/Indeed lists.
    jobs.extend(_load_import_jobs(DEFAULT_LINKEDIN_IMPORT, "linkedin"))
    jobs.extend(_load_import_jobs(DEFAULT_INDEED_IMPORT, "indeed"))

    # 2) Public ATS sources (Greenhouse + Lever).
    for token in _split_env_list("LIVE_GREENHOUSE_BOARDS", DEFAULT_GREENHOUSE_BOARDS):
        try:
            jobs.extend(scan_greenhouse(token))
        except Exception:
            continue
    for site in _split_env_list("LIVE_LEVER_SITES", DEFAULT_LEVER_SITES):
        try:
            jobs.extend(scan_lever(site))
        except Exception:
            continue

    jobs = _dedupe_jobs(jobs)
    matched = [j for j in jobs if _text_matches_query(j, query)]
    if not matched:
        matched = jobs
    return matched[:limit]


def _clean_price_id(raw: str) -> str:
    cleaned = raw or ""
    cleaned = cleaned.replace("\\n", "").replace("\n", "").replace("\r", "").replace("\t", "")
    cleaned = cleaned.replace("\\", "").replace('"', "").replace("'", "").strip()
    # Strip accidental JSON fragments, spaces, etc.
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", cleaned)
    return cleaned


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
                str(application_profile.get("work_authorization_status", "")),
                str(application_profile.get("preferred_locations", "")),
                str(application_profile.get("summary", "")),
            ]
        )
    return "\n".join(x for x in fields if x)


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
                for part in re.split(r"[|,/;]+", cell):
                    role = part.strip()
                    if role:
                        roles.add(role)
        return sorted(roles)
    except Exception:
        return []


def _search_roles(query: str) -> list[str]:
    pool = _fetch_roles_from_google_form_csv()
    if not pool:
        pool = DEFAULT_ROLES
    q = (query or "").strip().lower()
    if not q:
        return pool[:20]
    out = [r for r in pool if q in r.lower()]
    return out[:20]


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


def _results_to_cards(results: list[MatchResult], min_score: float) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for result in results:
        if result.final_score < min_score:
            continue
        cards.append(
            {
                "title": result.job.title,
                "company": result.job.company,
                "location": result.job.location,
                "url": result.job.url,
                "source": result.job.source,
                "rag_score": round(result.rag_score * 5.0, 2),
                "final_score": round(result.final_score * 5.0, 2),
                "overlap_terms": result.overlap_terms,
                "explanation": result.explanation,
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
    phone: str = ""
    location: str = ""
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
    work_preferences: list[str] = []
    companies_to_avoid: str = ""
    max_applications_per_day: int = 10
    minimum_match_score: float = 80.0
    application_summary: str = ""


class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str
    mode: str = "subscription"


class AutoApplyRequest(BaseModel):
    role: str = ""
    custom_role: str = ""
    max_jobs: int = 8


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


def _run_auto_apply_for_profile(
    sb: Client,
    user_id: str,
    user_email: str,
    profile: dict[str, Any],
    role_query: str,
    max_jobs: int | None = None,
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
    if max_jobs is not None:
        daily_cap = min(daily_cap, max(1, min(max_jobs, 50)))

    existing_today = _count_today_applications(sb, user_id)
    available_slots = max(0, daily_cap - existing_today)
    if available_slots == 0:
        return {
            "role": role_query,
            "matched_jobs": 0,
            "queued_applications": 0,
            "email_confirmations_sent": 0,
            "message": "Daily auto-apply limit already reached for this user.",
        }

    avoid_text = str(app_profile.get("companies_to_avoid", "") or "")
    avoid_companies = {x.strip().lower() for x in avoid_text.split(",") if x.strip()}
    require_approval = bool(app_profile.get("require_approval_before_apply", True))
    minimum_match_score = float(app_profile.get("minimum_match_score", 80.0) or 80.0)

    jobs = _discover_live_jobs(role_query, limit=160)
    matched = [j for j in jobs if _text_matches_query(j, role_query)]
    if avoid_companies:
        matched = [j for j in matched if j.company.lower() not in avoid_companies]
    profile_context = _profile_context_blob(profile)
    _, _, rag_matches = recommend_jobs_rag(
        jobs=matched,
        resume_text=profile_context or role_query,
        selected_role="custom",
        custom_role=role_query,
        top_k=max(available_slots * 4, 20),
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
def search_roles(q: str = "") -> dict[str, Any]:
    return {"roles": _search_roles(q)}


@app.post("/api/profile/upsert")
def upsert_profile(
    body: ProfileUpsertRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    user = _current_user(authorization)
    user_id = _user_id_from_user(user)
    sb = _supabase()
    payload = {
        "id": user_id,
        "email": user.get("email", ""),
        "full_name": body.full_name,
        "target_role": body.target_role,
        "skills": body.skills,
        "experience_level": body.experience_level,
        "application_profile": {
            "phone": body.phone,
            "location": body.location,
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
            "auto_apply_enabled": body.auto_apply_enabled,
            "auto_apply_consent": body.auto_apply_consent,
            "require_approval_before_apply": body.require_approval_before_apply,
            "work_preferences": body.work_preferences,
            "companies_to_avoid": body.companies_to_avoid,
            "max_applications_per_day": body.max_applications_per_day,
            "minimum_match_score": body.minimum_match_score,
            "summary": body.application_summary,
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
    return {"ok": True, "profile": payload}


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
    return {"profile": rows[0] if rows else None}


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
    payload = await resume_file.read()
    try:
        resume_text = _extract_resume_text(resume_file.filename or "", payload).strip()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if len(resume_text) < 40:
        raise HTTPException(status_code=400, detail="Resume text is too short.")

    query_role = (custom_role.strip() if role == "custom" else role.strip()) or role

    jobs: list[JobPosting] = load_jobs(DEFAULT_JOBS_FILE)
    if not jobs:
        jobs = _discover_live_jobs(query_role)
    if not jobs:
        raise HTTPException(
            status_code=400,
            detail=(
                "No jobs found. Add imports in data/imports CSVs or configure LIVE_GREENHOUSE_BOARDS/"
                "LIVE_LEVER_SITES env vars."
            ),
        )

    # Blend profile context with resume context for better relevance.
    sb = _supabase()
    profile_blob = ""
    try:
        uid = _user_id_from_user(user)
        profile_resp = sb.table("profiles").select("*").eq("id", uid).limit(1).execute()
        rows = getattr(profile_resp, "data", []) or []
        profile_blob = _profile_context_blob(rows[0] if rows else None)
    except Exception:
        profile_blob = ""

    combined_resume_context = resume_text if not profile_blob else f"{resume_text}\n\n{profile_blob}"

    selected_role_label, resume_keywords, matched = recommend_jobs_rag(
        jobs=jobs,
        resume_text=combined_resume_context,
        selected_role=role,
        custom_role=custom_role,
        top_k=max(1, min(top_k, 50)),
    )
    results = _results_to_cards(matched, min_score=min_score / 5.0)
    return {
        "role": selected_role_label,
        "resume_keywords": resume_keywords,
        "count": len(results),
        "results": results,
    }


@app.post("/api/payments/checkout")
def create_checkout(
    body: CheckoutRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    user = _current_user(authorization)
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
            client_reference_id=str(user.get("id", "")),
            customer_email=str(user.get("email", "")),
            allow_promotion_codes=True,
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

    profile_resp = sb.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    rows = getattr(profile_resp, "data", []) or []
    if not rows:
        raise HTTPException(status_code=400, detail="Profile not found. Save profile first.")
    profile = rows[0]
    role_query = (body.custom_role.strip() if body.role == "custom" else body.role.strip()) or profile.get(
        "target_role", ""
    )
    max_jobs = max(1, min(body.max_jobs, 20))
    return _run_auto_apply_for_profile(
        sb=sb,
        user_id=user_id,
        user_email=str(user.get("email", "")),
        profile=profile,
        role_query=role_query,
        max_jobs=max_jobs,
    )


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

    for profile in profiles:
        app_profile = profile.get("application_profile") or {}
        if not bool(app_profile.get("auto_apply_enabled")) or not bool(app_profile.get("auto_apply_consent")):
            continue
        user_id = str(profile.get("id", "")).strip()
        user_email = str(profile.get("email", "")).strip()
        role_query = str(profile.get("target_role", "")).strip()
        if not user_id or not role_query:
            continue

        try:
            result = _run_auto_apply_for_profile(
                sb=sb,
                user_id=user_id,
                user_email=user_email,
                profile=profile,
                role_query=role_query,
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
                    }
                ).execute()
            except Exception:
                pass

    return {"received": True}
