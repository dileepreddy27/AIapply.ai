from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from urllib.parse import urlparse

import requests

from .models import JobPosting


USER_AGENT = "career-autopilot/0.1"


def _make_id(source: str, url: str) -> str:
    raw = f"{source}:{url}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


def _normalize_job(
    source: str,
    url: str,
    title: str = "",
    company: str = "",
    location: str = "",
    description: str = "",
) -> JobPosting:
    title = title.strip() or "Unknown Role"
    company = company.strip() or "Unknown Company"
    location = location.strip() or "Unknown Location"
    return JobPosting(
        id=_make_id(source, url),
        source=source,
        company=company,
        title=title,
        location=location,
        url=url.strip(),
        description=description.strip(),
    )


def _get_json(url: str) -> dict | list:
    resp = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def scan_greenhouse(board_token: str) -> list[JobPosting]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    data = _get_json(url)
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    out: list[JobPosting] = []
    for j in jobs:
        out.append(
            _normalize_job(
                source="greenhouse",
                url=str(j.get("absolute_url", "")),
                title=str(j.get("title", "")),
                company=board_token,
                location=str((j.get("location") or {}).get("name", "")),
                description=str(j.get("content", "")),
            )
        )
    return [j for j in out if j.url]


def scan_lever(site: str) -> list[JobPosting]:
    url = f"https://api.lever.co/v0/postings/{site}?mode=json"
    data = _get_json(url)
    rows = data if isinstance(data, list) else []
    out: list[JobPosting] = []
    for j in rows:
        categories = j.get("categories") or {}
        out.append(
            _normalize_job(
                source="lever",
                url=str(j.get("hostedUrl", "")),
                title=str(j.get("text", "")),
                company=site,
                location=str(categories.get("location", "")),
                description=str(j.get("descriptionPlain", "")),
            )
        )
    return [j for j in out if j.url]


def scan_manual_urls(path: Path) -> list[JobPosting]:
    if not path.exists():
        return []
    out: list[JobPosting] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        domain = urlparse(line).netloc
        out.append(
            _normalize_job(
                source="manual",
                url=line,
                title=f"Job from {domain}",
                company=domain,
            )
        )
    return out


def scan_import_csv(path: Path, source_name: str) -> list[JobPosting]:
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
                _normalize_job(
                    source=source_name,
                    url=url,
                    title=row.get("title", "") or "",
                    company=row.get("company", "") or "",
                    location=row.get("location", "") or "",
                    description=row.get("description", "") or "",
                )
            )
    return out


def scan_all_sources(raw_cfg: dict, project_root: Path) -> list[JobPosting]:
    jobs: list[JobPosting] = []

    for token in raw_cfg.get("greenhouse", {}).get("boards", []):
        try:
            jobs.extend(scan_greenhouse(str(token)))
        except Exception as exc:
            print(f"[warn] greenhouse {token}: {exc}")

    for site in raw_cfg.get("lever", {}).get("sites", []):
        try:
            jobs.extend(scan_lever(str(site)))
        except Exception as exc:
            print(f"[warn] lever {site}: {exc}")

    manual_cfg = raw_cfg.get("manual", {})
    manual_file = manual_cfg.get("job_urls_file")
    if manual_file:
        jobs.extend(scan_manual_urls((project_root / manual_file).resolve()))

    linkedin_cfg = raw_cfg.get("linkedin", {})
    linkedin_csv = linkedin_cfg.get("imports_csv")
    if linkedin_csv:
        jobs.extend(scan_import_csv((project_root / linkedin_csv).resolve(), "linkedin"))

    indeed_cfg = raw_cfg.get("indeed", {})
    indeed_csv = indeed_cfg.get("imports_csv")
    if indeed_csv:
        jobs.extend(scan_import_csv((project_root / indeed_csv).resolve(), "indeed"))

    return jobs
