from career_autopilot import scanners


def test_make_id_is_deterministic():
    a = scanners._make_id("greenhouse", "https://x.com/1")
    b = scanners._make_id("greenhouse", "https://x.com/1")
    c = scanners._make_id("lever", "https://x.com/1")
    assert a == b
    assert a != c


def test_normalize_timestamp_epoch_seconds():
    out = scanners._normalize_timestamp(1_700_000_000)
    assert out.startswith("2023")


def test_normalize_timestamp_epoch_millis():
    out = scanners._normalize_timestamp(1_700_000_000_000)
    assert out.startswith("2023")


def test_normalize_job_defaults():
    job = scanners._normalize_job(source="ashby", url="https://x.com/a", title="", company="")
    assert job.title == "Unknown Role"
    assert job.company == "Unknown Company"
    assert job.location == "Unknown Location"
    assert job.source == "ashby"


def test_smartrecruiters_parse(monkeypatch):
    payload = {
        "content": [
            {
                "id": "abc123",
                "name": "Software Engineer",
                "company": {"name": "Acme"},
                "location": {"city": "New York", "country": "US", "remote": True},
                "releasedDate": "2024-01-01T00:00:00Z",
            }
        ]
    }
    monkeypatch.setattr(scanners, "_get_json", lambda url: payload)
    jobs = scanners.scan_smartrecruiters("acme")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "Software Engineer"
    assert j.source == "smartrecruiters"
    assert "jobs.smartrecruiters.com/acme/abc123" in j.url
    assert "New York" in j.location


def test_recruitee_parse(monkeypatch):
    payload = {
        "offers": [
            {
                "id": 1,
                "title": "Backend Engineer",
                "location": "Berlin",
                "careers_url": "https://acme.recruitee.com/o/backend-engineer",
                "created_at": "2024-01-01",
            }
        ]
    }
    monkeypatch.setattr(scanners, "_get_json", lambda url: payload)
    jobs = scanners.scan_recruitee("acme")
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].source == "recruitee"
    assert jobs[0].url.endswith("/o/backend-engineer")


def test_scan_functions_exist():
    for name in (
        "scan_greenhouse",
        "scan_lever",
        "scan_ashby",
        "scan_smartrecruiters",
        "scan_recruitee",
    ):
        assert hasattr(scanners, name)
