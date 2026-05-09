from __future__ import annotations

import re

from .models import JobPosting, Profile


TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.-]{2,}")


def tokenize(text: str) -> set[str]:
    return {tok.lower() for tok in TOKEN_RE.findall(text)}


def score_job(job: JobPosting, profile: Profile) -> tuple[float, str]:
    profile_blob = " ".join(
        profile.target_roles
        + profile.skills
        + profile.keywords
        + [profile.narrative, profile.location]
    )
    job_blob = " ".join([job.title, job.company, job.location, job.description])

    profile_terms = tokenize(profile_blob)
    job_terms = tokenize(job_blob)

    if not profile_terms:
        return 0.0, "Profile terms are empty."

    overlap = len(profile_terms & job_terms)
    lexical = overlap / max(1, len(profile_terms))

    location_bonus = 0.0
    if profile.location and profile.location.lower() in job.location.lower():
        location_bonus = 0.2
    elif "remote" in job.location.lower():
        location_bonus = 0.15

    experience_bonus = min(profile.experience_years / 20.0, 0.2)

    score_0_to_1 = min(1.0, lexical + location_bonus + experience_bonus)
    score_0_to_5 = round(score_0_to_1 * 5.0, 2)

    reason = (
        f"keyword_overlap={overlap}; lexical={lexical:.2f}; "
        f"location_bonus={location_bonus:.2f}; experience_bonus={experience_bonus:.2f}"
    )
    return score_0_to_5, reason


def score_jobs(jobs: list[JobPosting], profile: Profile, only_unscored: bool = True) -> int:
    updated = 0
    for job in jobs:
        if only_unscored and job.score is not None:
            continue
        job.score, job.score_reason = score_job(job, profile)
        if job.status == "new":
            job.status = "scored"
        updated += 1
    return updated
