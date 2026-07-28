from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .models import JobPosting, Profile

MANUAL_ONLY_DOMAINS = ("linkedin.com", "indeed.", "glassdoor.")


FIELD_ALIASES = {
    "name": ["full name", "name"],
    "email": ["email", "email address"],
    "phone": ["phone", "phone number", "mobile"],
    "location": ["location", "city", "current location"],
    "linkedin": ["linkedin", "linkedin url", "linkedin profile"],
    "github": ["github", "github url"],
    "portfolio": ["portfolio", "website", "personal website"],
}


def _try_fill(page: Page, label: str, value: str) -> bool:
    if not value:
        return False

    for alias in FIELD_ALIASES[label]:
        try:
            by_label = page.get_by_label(alias, exact=False)
            if by_label.count() > 0:
                by_label.first.fill(value)
                return True
        except Exception:
            pass

        try:
            by_placeholder = page.get_by_placeholder(alias, exact=False)
            if by_placeholder.count() > 0:
                by_placeholder.first.fill(value)
                return True
        except Exception:
            pass

    return False


def _click_apply(page: Page) -> None:
    selectors = [
        "button:has-text('Apply')",
        "a:has-text('Apply')",
        "button:has-text('Easy Apply')",
        "a:has-text('Easy Apply')",
        "button:has-text('Apply Now')",
        "a:has-text('Apply Now')",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                locator.first.click(timeout=2000)
                return
        except Exception:
            continue


def _attach_files(page: Page, profile: Profile, project_root: Path) -> None:
    assets = profile.assets
    resume_path = assets.get("resume_path", "")
    cover_path = assets.get("cover_letter_path", "")
    file_inputs = page.locator("input[type='file']")

    if file_inputs.count() == 0:
        return

    if resume_path:
        rp = (project_root / resume_path).resolve()
        if rp.exists():
            file_inputs.first.set_input_files(str(rp))

    if cover_path and file_inputs.count() > 1:
        cp = (project_root / cover_path).resolve()
        if cp.exists():
            file_inputs.nth(1).set_input_files(str(cp))


def prepare_application(
    job_url: str,
    applicant: dict[str, str],
    resume_path: str | None = None,
    cover_letter_path: str | None = None,
    answers: list[dict[str, str]] | None = None,
    submit: bool = False,
    headless: bool = True,
    timeout_ms: int = 60000,
    storage_state_path: Path | None = None,
) -> dict[str, Any]:
    """Drive a headless browser to a single job application and fill known fields.

    This is the server-callable entry point (no ``input()`` prompts). It fills the
    standard identity fields, attaches a resume/cover letter when provided, and
    only clicks a submit button when ``submit=True``. Returns a structured result
    so the API can record what happened without trusting the browser blindly.
    """
    result: dict[str, Any] = {
        "job_url": job_url,
        "status": "prepared",
        "submitted": False,
        "filled_fields": [],
        "error": "",
    }
    domain = urlparse(job_url).netloc.lower()
    if any(d in domain for d in MANUAL_ONLY_DOMAINS):
        result["status"] = "manual_only"
        result["error"] = f"{domain} requires manual application."
        return result

    identity = {
        "name": applicant.get("name", ""),
        "email": applicant.get("email", ""),
        "phone": applicant.get("phone", ""),
        "location": applicant.get("location", ""),
        "linkedin": applicant.get("linkedin", ""),
        "github": applicant.get("github", ""),
        "portfolio": applicant.get("portfolio", ""),
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context_kwargs: dict[str, Any] = {}
            if storage_state_path and storage_state_path.exists():
                context_kwargs["storage_state"] = str(storage_state_path)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            try:
                page.goto(job_url, wait_until="domcontentloaded", timeout=timeout_ms)
                _click_apply(page)
                for field, value in identity.items():
                    if value and _try_fill(page, field, value):
                        result["filled_fields"].append(field)
                _attach_files_by_path(page, resume_path, cover_letter_path)
                if answers:
                    _fill_freeform_answers(page, answers)

                if submit:
                    submitted = _click_submit(page)
                    result["submitted"] = submitted
                    result["status"] = "submitted" if submitted else "review_needed"
                else:
                    result["status"] = "prepared_dry_run"
            except PlaywrightTimeoutError:
                result["status"] = "timeout"
                result["error"] = "Page load timed out."
            finally:
                if storage_state_path:
                    storage_state_path.parent.mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=str(storage_state_path))
                page.close()
                context.close()
                browser.close()
    except Exception as exc:  # Playwright not installed, browser missing, etc.
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _attach_files_by_path(
    page: Page, resume_path: str | None, cover_letter_path: str | None
) -> None:
    file_inputs = page.locator("input[type='file']")
    try:
        count = file_inputs.count()
    except Exception:
        return
    if count == 0:
        return
    if resume_path and Path(resume_path).exists():
        try:
            file_inputs.first.set_input_files(resume_path)
        except Exception:
            pass
    if cover_letter_path and Path(cover_letter_path).exists() and count > 1:
        try:
            file_inputs.nth(1).set_input_files(cover_letter_path)
        except Exception:
            pass


def _fill_freeform_answers(page: Page, answers: list[dict[str, str]]) -> None:
    """Best-effort fill of screening questions matched by label substring."""
    for item in answers:
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not question or not answer:
            continue
        key = question.split("?")[0][:40]
        try:
            locator = page.get_by_label(key, exact=False)
            if locator.count() > 0:
                locator.first.fill(answer)
        except Exception:
            continue


def _click_submit(page: Page) -> bool:
    submit_selectors = [
        "button:has-text('Submit Application')",
        "button:has-text('Submit application')",
        "button:has-text('Send Application')",
        "button:has-text('Submit')",
        "button[type='submit']",
    ]
    for selector in submit_selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                locator.first.click(timeout=3000)
                return True
        except Exception:
            continue
    return False


def apply_with_review(
    jobs: list[JobPosting],
    profile: Profile,
    project_root: Path,
    max_jobs: int = 5,
    dry_run: bool = True,
    headless: bool = False,
    storage_state_path: Path | None = None,
) -> tuple[int, int]:
    attempted = 0
    prepared = 0

    # Use project-local Playwright browsers when available.
    local_browsers = project_root / ".playwright"
    if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and local_browsers.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(local_browsers)

    candidates = [j for j in jobs if j.score is None or j.score >= 3.5]
    candidates = sorted(candidates, key=lambda x: (x.score or 0), reverse=True)[:max_jobs]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context_kwargs = {}
        if storage_state_path and storage_state_path.exists():
            context_kwargs["storage_state"] = str(storage_state_path)
        context = browser.new_context(**context_kwargs)

        for job in candidates:
            domain = urlparse(job.url).netloc.lower()
            if "linkedin.com" in domain or "indeed." in domain:
                job.status = "manual_only"
                continue

            attempted += 1
            page = context.new_page()
            try:
                page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
                _click_apply(page)

                _try_fill(page, "name", profile.name)
                _try_fill(page, "email", profile.email)
                _try_fill(page, "phone", profile.phone)
                _try_fill(page, "location", profile.location)
                _try_fill(page, "linkedin", profile.links.get("linkedin", ""))
                _try_fill(page, "github", profile.links.get("github", ""))
                _try_fill(page, "portfolio", profile.links.get("portfolio", ""))
                _attach_files(page, profile, project_root)

                if dry_run:
                    job.status = "prepared_dry_run"
                else:
                    ans = input(
                        f"Ready to submit for '{job.title}' at '{job.company}'?\n"
                        f"Type YES to attempt submit, anything else to skip: "
                    )
                    if ans.strip().upper() == "YES":
                        submit_selectors = [
                            "button:has-text('Submit')",
                            "button:has-text('Submit Application')",
                            "button:has-text('Send Application')",
                        ]
                        submitted = False
                        for selector in submit_selectors:
                            locator = page.locator(selector)
                            if locator.count() > 0:
                                locator.first.click(timeout=3000)
                                submitted = True
                                break
                        job.status = "submitted" if submitted else "review_needed"
                    else:
                        job.status = "review_needed"

                prepared += 1
            except PlaywrightTimeoutError:
                job.status = "timeout"
            except Exception as exc:
                job.status = f"error: {type(exc).__name__}"
            finally:
                page.close()

        if storage_state_path:
            storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(storage_state_path))

        context.close()
        browser.close()

    return attempted, prepared
