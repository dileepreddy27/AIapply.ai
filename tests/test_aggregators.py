from career_autopilot import aggregators as agg


def test_classify_apply_type():
    assert agg.classify_apply_type("https://boards.greenhouse.io/acme/jobs/1") == "external_ats"
    assert agg.classify_apply_type("https://jobs.lever.co/acme/1") == "external_ats"
    assert agg.classify_apply_type("https://www.linkedin.com/jobs/view/1") == "linkedin_easy_apply"
    assert agg.classify_apply_type("https://www.indeed.com/viewjob?jk=1") == "indeed"
    assert agg.classify_apply_type("https://careers.acme.com/apply", is_direct=True) == "direct"
    assert agg.classify_apply_type("https://unknown.example.com/x") == "unknown"


def test_jsearch_parse(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    payload = {
        "data": [
            {
                "job_id": "1",
                "job_title": "Senior Python Engineer",
                "employer_name": "Acme",
                "job_apply_link": "https://boards.greenhouse.io/acme/jobs/1",
                "job_apply_is_direct": True,
                "job_city": "Austin",
                "job_state": "TX",
                "job_country": "US",
                "job_is_remote": True,
                "job_description": "Build things.",
                "job_posted_at_datetime_utc": "2024-02-01T00:00:00Z",
                "job_publisher": "LinkedIn",
            }
        ]
    }
    monkeypatch.setattr(agg, "_get_json", lambda url, headers=None, params=None: payload)
    jobs = agg.scan_jsearch("python engineer", location="United States")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "Senior Python Engineer"
    assert j.company == "Acme"
    assert j.source == "linkedin"
    assert j.apply_type == "external_ats"  # greenhouse link wins over publisher
    assert "Austin" in j.location and "Remote" in j.location


def test_jsearch_skips_without_key(monkeypatch):
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    assert agg.scan_jsearch("engineer") == []


def test_serpapi_parse(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "test-key")
    payload = {
        "jobs_results": [
            {
                "title": "Data Scientist",
                "company_name": "DataCorp",
                "location": "Remote",
                "description": "ML work.",
                "apply_options": [{"title": "Apply on Lever", "link": "https://jobs.lever.co/datacorp/2"}],
                "detected_extensions": {"posted_at": "3 days ago"},
            }
        ]
    }
    monkeypatch.setattr(agg, "_get_json", lambda url, headers=None, params=None: payload)
    jobs = agg.scan_serpapi_google_jobs("data scientist")
    assert len(jobs) == 1
    assert jobs[0].company == "DataCorp"
    assert jobs[0].source == "google_jobs"
    assert jobs[0].apply_type == "external_ats"


def test_rss_parse(monkeypatch):
    xml = b"""<?xml version='1.0'?>
    <rss version='2.0'><channel>
      <item><title>Backend Engineer</title><link>https://niche.example.com/jobs/9</link>
        <description>Great role</description><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item>
    </channel></rss>"""

    class FakeResp:
        content = xml
        def raise_for_status(self):
            return None

    monkeypatch.setattr(agg.requests, "get", lambda *a, **k: FakeResp())
    jobs = agg.scan_rss("https://niche.example.com/feed.xml", source_label="niche")
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].url == "https://niche.example.com/jobs/9"
    assert jobs[0].source == "niche"


def test_rss_atom_prefers_alternate_over_self(monkeypatch):
    # Atom entries can carry several <link>s; a trailing rel="self" (API URL) must NOT
    # overwrite the rel="alternate" job page.
    xml = b"""<?xml version='1.0'?>
    <feed xmlns='http://www.w3.org/2005/Atom'>
      <entry>
        <title>Platform Engineer</title>
        <link rel='alternate' href='https://board.example.com/jobs/42'/>
        <link rel='self' href='https://board.example.com/api/entries/42'/>
        <summary>Own the platform</summary>
        <updated>2024-03-01T00:00:00Z</updated>
      </entry>
    </feed>"""

    class FakeResp:
        content = xml
        def raise_for_status(self):
            return None

    monkeypatch.setattr(agg.requests, "get", lambda *a, **k: FakeResp())
    jobs = agg.scan_rss("https://board.example.com/atom.xml", source_label="board")
    assert len(jobs) == 1
    assert jobs[0].url == "https://board.example.com/jobs/42"  # alternate, not self


def test_fetch_applier_queue_returns_partial_on_later_page_error(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "k")
    page1 = {
        "data": [
            {
                "employer_name": "Acme",
                "job_title": "Backend Engineer",
                "job_apply_link": "https://jobs.lever.co/acme/1",
                "job_city": "Austin",
                "job_state": "TX",
            }
        ]
    }
    calls = {"n": 0}

    def fake_get_json(url, headers=None, params=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return page1
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr(agg, "_get_json", fake_get_json)
    # pages=3, but page 2 errors -> we keep page 1's jobs instead of crashing.
    q = agg.fetch_applier_queue("backend engineer", pages=3, location="United States")
    assert len(q) == 1
    assert q[0]["company"] == "Acme"
