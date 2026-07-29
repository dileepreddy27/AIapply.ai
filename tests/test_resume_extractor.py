from career_autopilot import resume_extractor as rx


SAMPLE_RESUME = """Jane Doe
San Francisco, CA
jane.doe@example.com | +1 (415) 555-0199
https://www.linkedin.com/in/janedoe  https://github.com/janedoe  https://janedoe.dev

Senior Backend Engineer with 8 years building distributed systems and APIs at scale.
Led platform teams and shipped high-throughput services.

Skills: Python, FastAPI, PostgreSQL, Kubernetes, AWS, Python

Experience
Acme Corp — Senior Engineer (2019-2024)
"""


def test_parse_json_object_plain():
    assert rx._parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_json_object_fenced():
    assert rx._parse_json_object('```json\n{"a": "b"}\n```') == {"a": "b"}


def test_parse_json_object_with_prose():
    text = 'Here is the data:\n{"full_name": "X", "skills": ["a"]}\nThanks!'
    assert rx._parse_json_object(text) == {"full_name": "X", "skills": ["a"]}


def test_parse_json_object_invalid():
    assert rx._parse_json_object("not json at all") is None
    assert rx._parse_json_object("") is None


def test_normalize_skills_dedupes_and_splits():
    assert rx._normalize_skills("Python, FastAPI, python") == ["Python", "FastAPI"]
    assert rx._normalize_skills(["React", "React", "TS"]) == ["React", "TS"]
    assert rx._normalize_skills(None) == []


def test_heuristic_pulls_contact_and_links():
    out = rx.extract_heuristic(SAMPLE_RESUME)
    assert out["full_name"] == "Jane Doe"
    assert out["email"] == "jane.doe@example.com"
    assert "linkedin.com/in/janedoe" in out["linkedin_url"]
    assert "github.com/janedoe" in out["github_url"]
    assert out["portfolio_url"].startswith("https://janedoe.dev")
    assert out["experience_level"] == "8 years"
    assert "Python" in out["skills"] and out["skills"].count("Python") == 1
    assert out["phone"]  # some phone captured


def test_extract_profile_fields_prefers_llm(monkeypatch):
    monkeypatch.setattr(
        rx,
        "extract_with_llm",
        lambda text, user_id="": {
            "full_name": "LLM Name",
            "skills": ["Go", "Rust"],
            "experience_level": "Senior",
            "summary": "An engineer.",
            "linkedin_url": "",  # empty -> should fall back to heuristic
        },
    )
    out = rx.extract_profile_fields(SAMPLE_RESUME)
    assert out["full_name"] == "LLM Name"  # LLM wins
    assert out["skills"] == ["Go", "Rust"]
    assert out["experience_level"] == "Senior"
    # LLM left linkedin empty -> heuristic fills it.
    assert "linkedin.com/in/janedoe" in out["linkedin_url"]


def test_extract_profile_fields_falls_back_to_heuristic(monkeypatch):
    monkeypatch.setattr(rx, "extract_with_llm", lambda text, user_id="": None)
    out = rx.extract_profile_fields(SAMPLE_RESUME)
    assert out["full_name"] == "Jane Doe"
    assert out["email"] == "jane.doe@example.com"
    assert out["experience_level"] == "8 years"


def test_extract_with_llm_skips_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert rx.extract_with_llm("some resume text") is None
