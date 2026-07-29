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


def test_dedupe_keeps_distinct_ats_reqs():
    # Two genuinely-different reqs at one company can share company+title+location but
    # have distinct URLs — each is separately applyable and must NOT be collapsed.
    a = JobPosting(
        id="a", source="greenhouse", company="Stripe", title="Software Engineer",
        location="San Francisco, CA", url="https://boards.greenhouse.io/stripe/1",
        description="JD one", apply_type="external_ats",
    )
    b = JobPosting(
        id="b", source="greenhouse", company="Stripe", title="Software Engineer",
        location="San Francisco, CA", url="https://boards.greenhouse.io/stripe/2",
        description="JD two", apply_type="external_ats",
    )
    out = api._dedupe_jobs([a, b])
    assert len(out) == 2
    assert {j.url for j in out} == {a.url, b.url}


def test_dedupe_ats_survives_regardless_of_order():
    # Even when the aggregator listing is encountered first, the ATS listing must win
    # (the fix must not depend on _rank ordering between direct and aggregator).
    linkedin = JobPosting(
        id="l", source="linkedin", company="Ramp", title="Engineer", location="(Remote)",
        url="https://linkedin.com/jobs/9", description="desc", apply_type="linkedin_easy_apply",
    )
    ats = JobPosting(
        id="g", source="ashby", company="Ramp", title="Engineer", location="(Remote)",
        url="https://jobs.ashbyhq.com/ramp/9", description="", apply_type="external_ats",
    )
    out = api._dedupe_jobs([linkedin, ats])
    assert len(out) == 1
    assert out[0].apply_type == "external_ats"


def test_redact_secrets_strips_api_key(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "sk-super-secret-123")
    msg = "google_jobs:401 Client Error for url: https://serpapi.com/search.json?api_key=sk-super-secret-123"
    redacted = api._redact_secrets(msg)
    assert "sk-super-secret-123" not in redacted
    assert "***" in redacted


def test_aggregator_cache_serves_within_ttl(monkeypatch):
    monkeypatch.setenv("AGGREGATOR_CACHE_TTL", "900")
    api._AGG_CACHE.clear()
    calls = {"n": 0}

    def runner():
        calls["n"] += 1
        return ["job"]

    key = "jsearch|engineer|United States"
    assert api._cached_aggregator_scan(key, runner) == ["job"]
    assert api._cached_aggregator_scan(key, runner) == ["job"]
    assert calls["n"] == 1  # second call served from cache, no second billable request
    api._AGG_CACHE.clear()


def test_aggregator_cache_does_not_store_on_error(monkeypatch):
    monkeypatch.setenv("AGGREGATOR_CACHE_TTL", "900")
    api._AGG_CACHE.clear()

    def boom():
        raise RuntimeError("429")

    import pytest

    with pytest.raises(RuntimeError):
        api._cached_aggregator_scan("k", boom)
    assert "k" not in api._AGG_CACHE


def test_allowed_statuses_include_pipeline_stages():
    for s in ("viewed", "applied", "replied", "interviewing", "withdrawn"):
        assert s in api.ALLOWED_APPLICATION_STATUSES
