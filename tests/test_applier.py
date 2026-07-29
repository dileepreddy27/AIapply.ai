from career_autopilot import aggregators as agg
from career_autopilot import applier


def test_classify_application_route():
    assert agg.classify_application_route("https://jobs.lever.co/acme/1") == "ATS_LEVER_API"
    assert agg.classify_application_route("https://boards.greenhouse.io/acme/jobs/1") == "ATS_GREENHOUSE_API"
    assert agg.classify_application_route("https://acme.wd1.myworkdayjobs.com/x") == "BROWSER_WORKDAY_FLOW"
    assert agg.classify_application_route("https://www.linkedin.com/jobs/view/1") == "LINKEDIN_EASY_APPLY"
    assert agg.classify_application_route("https://careers.acme.com/apply") == "GENERIC_WEB_FORM"
    assert agg.classify_application_route("") == "UNKNOWN"


def test_queue_hash_is_stable_and_normalized():
    a = agg.queue_hash("Acme ", "Engineer", " NYC")
    b = agg.queue_hash("acme", "engineer", "nyc")
    assert a == b  # case + whitespace normalized -> same hash


def test_fetch_applier_queue(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "k")
    payload = {
        "data": [
            {
                "employer_name": "Acme",
                "job_title": "Backend Engineer",
                "job_apply_link": "https://jobs.lever.co/acme/1",
                "job_city": "Austin",
                "job_state": "TX",
                "job_is_remote": False,
                "job_description": "desc",
                "job_min_salary": 120000,
                "job_max_salary": 160000,
                "job_publisher": "LinkedIn",
                "job_posted_at_datetime_utc": "2024-02-01T00:00:00Z",
            },
            # duplicate of the same role -> collapsed by hash
            {
                "employer_name": "Acme",
                "job_title": "Backend Engineer",
                "job_apply_link": "https://www.indeed.com/viewjob?jk=2",
                "job_city": "Austin",
                "job_state": "TX",
            },
        ]
    }
    monkeypatch.setattr(agg, "_get_json", lambda url, headers=None, params=None: payload)
    q = agg.fetch_applier_queue("backend engineer", location="United States")
    assert len(q) == 1  # deduped
    item = q[0]
    assert item["application_type"] == "ATS_LEVER_API"
    assert item["salary_min"] == 120000 and item["salary_max"] == 160000
    assert item["platform_source"] == "LinkedIn"
    assert set(["job_id", "title", "company", "location", "apply_url", "description", "is_remote"]).issubset(item)


def test_route_adapter():
    assert applier.route_adapter("https://boards.greenhouse.io/acme/jobs/1") == "greenhouse"
    assert applier.route_adapter("https://jobs.lever.co/acme/1") == "lever"
    assert applier.route_adapter("https://acme.wd1.myworkdayjobs.com/x") == "workday"
    assert applier.route_adapter("https://www.linkedin.com/jobs/view/1") == "manual"
    assert applier.route_adapter("https://www.indeed.com/viewjob?jk=1") == "manual"
    assert applier.route_adapter("https://careers.acme.com/apply") == "generic"


def test_route_adapter_scheme_malformed_fails_safe():
    # A scheme-malformed URL (empty urlparse().netloc) must NOT fall open to the
    # submitting "generic" adapter — LinkedIn/Indeed stay manual, Workday stays workday.
    assert applier.route_adapter("http:www.linkedin.com/jobs/view/1") == "manual"
    assert applier.route_adapter("https:www.indeed.com/viewjob?jk=1") == "manual"
    assert applier.route_adapter("https:acme.wd1.myworkdayjobs.com/x") == "workday"
    assert applier.route_adapter("https:boards.greenhouse.io/acme/jobs/1") == "greenhouse"


def test_lever_apply_url_preserves_query():
    # /apply must be appended to the PATH, not the raw string, so tracking params survive.
    assert (
        applier._lever_apply_url("https://jobs.lever.co/acme/abc-123?lever-source=LinkedIn")
        == "https://jobs.lever.co/acme/abc-123/apply?lever-source=LinkedIn"
    )
    # Already-/apply URLs are left untouched (idempotent), trailing slash tolerated.
    assert applier._lever_apply_url("https://jobs.lever.co/acme/abc-123/apply") == "https://jobs.lever.co/acme/abc-123/apply"
    assert applier._lever_apply_url("https://jobs.lever.co/acme/abc-123/") == "https://jobs.lever.co/acme/abc-123/apply"


def test_split_name():
    assert applier._split_name({"name": "Alex Morgan"}) == ("Alex", "Morgan")
    assert applier._split_name({"name": "Cher"}) == ("Cher", "")
    assert applier._split_name({"name": ""}) == ("", "")


def test_apply_one_manual_only_short_circuits():
    # LinkedIn/Indeed are manual_only and must not launch a browser.
    res = applier.apply_one(
        context=None,  # never used for manual_only
        job={"apply_url": "https://www.linkedin.com/jobs/view/1", "title": "X", "company": "Y"},
        applicant={"name": "Alex Morgan", "email": "a@b.com"},
    )
    assert res["status"] == "manual_only"
    assert res["submitted"] is False
