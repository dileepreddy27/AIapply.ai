"""Background auto-submit worker.

Polls the applications table for approved, queued applications and drives the
headless browser engine to fill (and, when consent allows, submit) them. Run it
as a separate Render background worker, not on the web dyno:

    python -m career_autopilot.main worker --interval 120           # dry-run loop
    python -m career_autopilot.main worker --submit --once          # one live pass

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY, Playwright chromium installed,
and (for document upload) resumes stored via /api/resume/upload.
"""

from __future__ import annotations

import os
import time
from typing import Any

from supabase import Client, create_client

from .apply_bot import prepare_application


def _client() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    return create_client(url, key)


def _fetch_queued(sb: Client, limit: int) -> list[dict[str, Any]]:
    try:
        resp = (
            sb.table("applications")
            .select("*")
            .eq("status", "queued_auto_apply")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return getattr(resp, "data", []) or []
    except Exception:
        return []


def _profile_for(sb: Client, user_id: str) -> dict[str, Any] | None:
    try:
        resp = sb.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        rows = getattr(resp, "data", []) or []
        return rows[0] if rows else None
    except Exception:
        return None


def _applicant_from_profile(profile: dict[str, Any]) -> dict[str, str]:
    app_profile = profile.get("application_profile") or {}
    return {
        "name": str(profile.get("full_name", "") or ""),
        "email": str(profile.get("email", "") or ""),
        "phone": str(app_profile.get("phone", "") or ""),
        "location": str(app_profile.get("location", "") or ""),
        "linkedin": str(app_profile.get("linkedin_url", "") or ""),
        "portfolio": str(app_profile.get("portfolio_url", "") or ""),
    }


def process_once(dry_run: bool = True, batch: int = 10) -> dict[str, Any]:
    # Import here to avoid importing the FastAPI app at module load.
    from .api import build_application_answers, _download_resume_to_temp

    sb = _client()
    queued = _fetch_queued(sb, batch)
    processed = 0
    submitted = 0
    errors = 0
    for application in queued:
        user_id = str(application.get("user_id", "") or "")
        job_url = str(application.get("job_url", "") or "")
        if not user_id or not job_url:
            continue
        profile = _profile_for(sb, user_id)
        if not profile:
            continue
        app_profile = profile.get("application_profile") or {}
        # Respect consent: never live-submit unless the user consented and did
        # not require per-application approval.
        consented = bool(app_profile.get("auto_apply_enabled")) and bool(
            app_profile.get("auto_apply_consent")
        )
        require_approval = bool(app_profile.get("require_approval_before_apply", True))
        do_submit = bool(not dry_run and consented and not require_approval)

        resume_path = _download_resume_to_temp(
            sb, str(app_profile.get("resume_storage_path", "") or "")
        )
        result = prepare_application(
            job_url=job_url,
            applicant=_applicant_from_profile(profile),
            resume_path=resume_path,
            answers=build_application_answers(profile),
            submit=do_submit,
            headless=True,
        )
        processed += 1
        if result.get("submitted"):
            submitted += 1
            try:
                sb.table("applications").update({"status": "applied"}).eq(
                    "id", application.get("id")
                ).execute()
            except Exception:
                pass
        elif result.get("status") in {"error", "timeout"}:
            errors += 1
    return {"processed": processed, "submitted": submitted, "errors": errors}


def run_worker(
    interval: int = 120,
    dry_run: bool = True,
    batch: int = 10,
    once: bool = False,
) -> None:
    mode = "DRY-RUN" if dry_run else "LIVE-SUBMIT"
    print(f"[worker] starting ({mode}); interval={interval}s batch={batch}")
    while True:
        try:
            stats = process_once(dry_run=dry_run, batch=batch)
            print(f"[worker] {stats}")
        except Exception as exc:  # keep the loop alive on transient failures
            print(f"[worker] error: {type(exc).__name__}: {exc}")
        if once:
            break
        time.sleep(max(10, interval))
