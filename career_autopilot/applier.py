"""Playwright auto-applier worker.

Reads a unified job queue (applier_queue.json — see aggregators.export_applier_queue)
and applies to each job, routing to a form adapter based on where the job lives:

    ATS_GREENHOUSE_API  -> Greenhouse hosted form (first/last/email/phone + resume)
    ATS_LEVER_API       -> Lever hosted form (/apply)
    GENERIC_WEB_FORM    -> generic "Easy Apply"/label-matched form fill
    BROWSER_WORKDAY_FLOW-> best-effort generic fill, never auto-submit (multi-step + account)
    LINKEDIN_/INDEED_   -> manual_only (login walls / ToS — not automated)

Safety: dry-run by default (fills the form, does NOT submit). Pass submit=True to
actually submit, and only for adapters where that is supported. This applies to the
user's own applications, on their behalf, with a resume they provide.

    python -m career_autopilot.main apply-queue --file applier_queue.json          # dry-run
    python -m career_autopilot.main apply-queue --file applier_queue.json --submit  # live
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .apply_bot import (
    MANUAL_ONLY_DOMAINS,
    _attach_files_by_path,
    _click_apply,
    _click_submit,
    _fill_freeform_answers,
    _try_fill,
)


def route_adapter(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "myworkdayjobs" in host or "workday" in host:
        return "workday"
    if any(d in host for d in MANUAL_ONLY_DOMAINS):
        return "manual"
    return "generic"


def _safe_fill(page: Any, selector: str, value: str) -> bool:
    if not value:
        return False
    try:
        loc = page.locator(selector)
        if loc.count() > 0:
            loc.first.fill(value)
            return True
    except Exception:
        pass
    return False


def _safe_set_files(page: Any, selector: str, path: str | None) -> bool:
    if not path or not Path(path).exists():
        return False
    try:
        loc = page.locator(selector)
        if loc.count() > 0:
            loc.first.set_input_files(path)
            return True
    except Exception:
        pass
    return False


def _split_name(applicant: dict[str, str]) -> tuple[str, str]:
    full = (applicant.get("name") or "").strip()
    if not full:
        return "", ""
    parts = full.split()
    return parts[0], " ".join(parts[1:]) if len(parts) > 1 else ""


def _fill_greenhouse(page: Any, applicant: dict[str, str], resume_path: str | None, answers: Any) -> list[str]:
    first, last = _split_name(applicant)
    filled: list[str] = []
    for selector, value in (
        ("#first_name", first),
        ("#last_name", last),
        ("#email", applicant.get("email", "")),
        ("#phone", applicant.get("phone", "")),
    ):
        if _safe_fill(page, selector, value):
            filled.append(selector)
    if _safe_set_files(page, "input[type='file']", resume_path):
        filled.append("resume")
    if answers:
        _fill_freeform_answers(page, answers)
    return filled


def _fill_lever(page: Any, applicant: dict[str, str], resume_path: str | None, answers: Any) -> list[str]:
    filled: list[str] = []
    for selector, value in (
        ("input[name='name']", applicant.get("name", "")),
        ("input[name='email']", applicant.get("email", "")),
        ("input[name='phone']", applicant.get("phone", "")),
        ("input[name='org']", applicant.get("company", "")),
        ("input[name='urls[LinkedIn]']", applicant.get("linkedin", "")),
    ):
        if _safe_fill(page, selector, value):
            filled.append(selector)
    if _safe_set_files(page, "input[name='resume'], input[type='file']", resume_path):
        filled.append("resume")
    if answers:
        _fill_freeform_answers(page, answers)
    return filled


def _fill_generic(page: Any, applicant: dict[str, str], resume_path: str | None, answers: Any) -> list[str]:
    _click_apply(page)  # reveal an "Easy Apply"/modal form if present
    filled: list[str] = []
    for field in ("name", "email", "phone", "location", "linkedin", "github", "portfolio"):
        if _try_fill(page, field, applicant.get(field, "")):
            filled.append(field)
    _attach_files_by_path(page, resume_path, None)
    if answers:
        _fill_freeform_answers(page, answers)
    return filled


def apply_one(
    context: Any,
    job: dict[str, Any],
    applicant: dict[str, str],
    resume_path: str | None = None,
    answers: Any = None,
    submit: bool = False,
    timeout_ms: int = 60000,
) -> dict[str, Any]:
    url = str(job.get("apply_url") or job.get("url") or "")
    result: dict[str, Any] = {
        "job_id": job.get("job_id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "adapter": route_adapter(url),
        "url": url,
        "status": "prepared",
        "submitted": False,
        "filled_fields": [],
        "error": "",
    }
    if not url:
        result["status"] = "error"
        result["error"] = "no apply_url"
        return result

    adapter = result["adapter"]
    if adapter == "manual":
        result["status"] = "manual_only"
        result["error"] = "Login-walled / ToS-restricted (LinkedIn/Indeed/Glassdoor)."
        return result

    page = context.new_page()
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        if adapter == "lever" and not url.rstrip("/").endswith("/apply"):
            url = url.rstrip("/") + "/apply"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            result["status"] = "timeout"
            result["error"] = "page load timed out"
            return result

        if adapter == "greenhouse":
            result["filled_fields"] = _fill_greenhouse(page, applicant, resume_path, answers)
        elif adapter == "lever":
            result["filled_fields"] = _fill_lever(page, applicant, resume_path, answers)
        else:
            result["filled_fields"] = _fill_generic(page, applicant, resume_path, answers)

        # Workday is a multi-step wizard that usually needs an account — never
        # auto-submit it; leave it prepared for manual review.
        if submit and adapter != "workday":
            result["submitted"] = _click_submit(page)
            result["status"] = "submitted" if result["submitted"] else "review_needed"
        else:
            result["status"] = "prepared_dry_run" if not submit else "review_needed"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        page.close()
    return result


def apply_from_queue(
    queue_path: str,
    applicant: dict[str, str],
    resume_path: str | None = None,
    answers: Any = None,
    submit: bool = False,
    headless: bool = True,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Read the JSON queue and apply to each job with one shared browser."""
    items = json.loads(Path(queue_path).read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError("Queue file must be a JSON array of job objects.")
    items = items[: max(1, limit)]

    from playwright.sync_api import sync_playwright

    results: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        try:
            for job in items:
                if not isinstance(job, dict):
                    continue
                results.append(
                    apply_one(context, job, applicant, resume_path, answers, submit=submit)
                )
        finally:
            context.close()
            browser.close()
    return results
