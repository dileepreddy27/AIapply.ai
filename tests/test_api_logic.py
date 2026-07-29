"""Pure-logic tests for api.py helpers (no network / no Supabase calls)."""
from career_autopilot import api
from career_autopilot.models import JobPosting


def _job(title="Engineer", description="", location="Remote", company="Acme"):
    return JobPosting(
        id="1", source="test", company=company, title=title,
        location=location, url="https://example.com/j", description=description,
    )


def test_clean_price_id_strips_junk():
    assert api._clean_price_id('  "price_123ABC"\n ') == "price_123ABC"
    assert api._clean_price_id("price_\t9\\n9") == "price_99"


def test_text_matches_query():
    job = _job(title="Python Backend Engineer", description="FastAPI, REST")
    assert api._text_matches_query(job, "python") is True
    assert api._text_matches_query(job, "") is True
    assert api._text_matches_query(job, "welding underwater") is False


def test_work_authorization_filter():
    needs = {"needs_sponsorship": True}
    no_sponsor = _job(description="We are unable to sponsor visas for this position.")
    ok = _job(description="Competitive salary and benefits.")
    assert api._job_matches_work_authorization(no_sponsor, needs) is False
    assert api._job_matches_work_authorization(ok, needs) is True
    # No filtering when the user does not need sponsorship.
    assert api._job_matches_work_authorization(no_sponsor, {"needs_sponsorship": False}) is True


def test_build_application_answers():
    profile = {
        "email": "x@y.com",
        "application_profile": {
            "work_authorization_status": "H-1B",
            "needs_sponsorship": True,
            "willing_to_relocate": True,
            "country": "United States",
            "salary_expectation": "150k",
        },
    }
    answers = api.build_application_answers(profile)
    joined = {a["question"]: a["answer"] for a in answers}
    assert any("sponsorship" in q.lower() for q in joined)
    assert any(a["answer"] == "H-1B" for a in answers)
    assert api.build_application_answers(None) == []


def test_posted_relative_label_buckets():
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    _, bucket_recent, _ = api._posted_relative_label((now - timedelta(hours=2)).isoformat())
    _, bucket_old, _ = api._posted_relative_label((now - timedelta(days=90)).isoformat())
    _, bucket_unknown, _ = api._posted_relative_label("")
    assert bucket_recent == "past_24_hours"
    assert bucket_old == "older"
    assert bucket_unknown == "unknown"


def test_dedupe_jobs():
    a = _job(title="A")
    b = _job(title="B")
    b.url = a.url  # same url -> deduped
    out = api._dedupe_jobs([a, b])
    assert len(out) == 1


def test_dedupe_cross_platform_keeps_actionable():
    # Same role on LinkedIn (aggregator) and on Greenhouse (external ATS) -> one wins.
    linkedin = JobPosting(
        id="l", source="linkedin", company="Acme", title="Engineer", location="NYC",
        url="https://linkedin.com/jobs/1", description="", apply_type="linkedin_easy_apply",
    )
    ats = JobPosting(
        id="g", source="greenhouse", company="Acme", title="Engineer", location="NYC",
        url="https://boards.greenhouse.io/acme/1", description="Full JD", apply_type="external_ats",
    )
    out = api._dedupe_jobs([linkedin, ats])
    assert len(out) == 1
    assert out[0].apply_type == "external_ats"  # the more-actionable listing wins


def test_allowed_statuses_include_pipeline_stages():
    for s in ("viewed", "applied", "replied", "interviewing", "withdrawn"):
        assert s in api.ALLOWED_APPLICATION_STATUSES
