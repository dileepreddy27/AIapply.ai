from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import JobPosting


def load_jobs(path: Path) -> list[JobPosting]:
    if not path.exists():
        return []

    jobs: list[JobPosting] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            jobs.append(JobPosting.from_dict(raw))
    return jobs


def save_jobs(path: Path, jobs: list[JobPosting]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        for job in sorted(jobs, key=lambda x: x.discovered_at):
            f.write(json.dumps(job.to_dict(), ensure_ascii=True))
            f.write("\n")


def upsert_jobs(existing: list[JobPosting], incoming: list[JobPosting]) -> list[JobPosting]:
    by_url = {job.url: job for job in existing}
    for item in incoming:
        current = by_url.get(item.url)
        if current is None:
            by_url[item.url] = item
            continue
        current.title = item.title or current.title
        current.company = item.company or current.company
        current.location = item.location or current.location
        current.description = item.description or current.description
        current.source = item.source or current.source
    return list(by_url.values())


def export_pipeline_csv(path: Path, jobs: list[JobPosting]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "status",
        "score",
        "source",
        "company",
        "title",
        "location",
        "url",
        "discovered_at",
        "score_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in sorted(jobs, key=lambda x: (x.score or 0), reverse=True):
            writer.writerow(
                {
                    "status": job.status,
                    "score": "" if job.score is None else f"{job.score:.2f}",
                    "source": job.source,
                    "company": job.company,
                    "title": job.title,
                    "location": job.location,
                    "url": job.url,
                    "discovered_at": job.discovered_at,
                    "score_reason": job.score_reason,
                }
            )
