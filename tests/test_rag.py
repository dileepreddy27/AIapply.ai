from career_autopilot import rag
from career_autopilot.models import JobPosting


def _job(title, description=""):
    return JobPosting(
        id=title, source="test", company="Acme", title=title, location="Remote",
        url=f"https://example.com/{title.replace(' ', '-')}", description=description,
    )


def test_tokenize_and_keywords():
    kws = rag.extract_keywords("Python backend engineer with FastAPI and Postgres experience")
    assert "python" in kws
    assert "experience" not in kws  # stopword-ish / filtered


def test_role_suggestions_returns_list():
    out = rag.role_suggestions("python developer")
    assert isinstance(out, list) and len(out) > 0


def test_recommend_ranks_relevant_job_first():
    jobs = [
        _job("Senior Python Backend Engineer", "Build APIs in Python and FastAPI."),
        _job("Registered Nurse", "Provide patient care in the ICU."),
    ]
    _, _, matches = rag.recommend_jobs_rag(
        jobs=jobs,
        resume_text="Experienced Python backend engineer, FastAPI, REST APIs.",
        selected_role="custom",
        custom_role="Python Backend Engineer",
        top_k=2,
    )
    assert matches
    assert "Python" in matches[0].job.title


def test_cosine_bounds():
    a = {"x": 1.0, "y": 2.0}
    assert rag._cosine(a, a) == 1.0 or abs(rag._cosine(a, a) - 1.0) < 1e-9
    assert rag._cosine(a, {}) == 0.0
