from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .models import JobPosting, Profile


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
