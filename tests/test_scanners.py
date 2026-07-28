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


def test_scan_functions_exist():
    for name in ("scan_greenhouse", "scan_lever", "scan_ashby"):
        assert hasattr(scanners, name)
