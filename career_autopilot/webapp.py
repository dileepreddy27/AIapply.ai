from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None  # type: ignore[assignment]

try:
    from docx import Document
except Exception:
    Document = None  # type: ignore[assignment]

from .rag import MatchResult, recommend_jobs_rag
from .storage import load_jobs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_FILE = PROJECT_ROOT / "data" / "jobs.jsonl"

ROLE_OPTIONS = [
    ("software_engineer", "Software Engineer"),
    ("data_scientist", "Data Scientist"),
    ("ml_engineer", "ML Engineer"),
    ("nurse", "Nurse"),
    ("product_manager", "Product Manager"),
    ("cybersecurity", "Cybersecurity"),
    ("custom", "Custom Role"),
]

app = FastAPI(title="AIapply.ai")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")


def _extract_resume_text(filename: str, payload: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".txt", ".md"}:
        return payload.decode("utf-8", errors="ignore")

    if suffix == ".pdf":
        if PdfReader is None:
            raise ValueError("PDF parser not installed. Run: pip install pypdf")
        reader = PdfReader(BytesIO(payload))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    if suffix == ".docx":
        if Document is None:
            raise ValueError("DOCX parser not installed. Run: pip install python-docx")
        doc = Document(BytesIO(payload))
        return "\n".join(p.text for p in doc.paragraphs if p.text)

    raise ValueError("Unsupported file type. Use PDF, DOCX, TXT, or MD.")


def _results_to_cards(results: list[MatchResult], min_score: float) -> list[dict]:
    cards: list[dict] = []
    for result in results:
        if result.final_score < min_score:
            continue
        cards.append(
            {
                "title": result.job.title,
                "company": result.job.company,
                "location": result.job.location,
                "url": result.job.url,
                "source": result.job.source,
                "rag_score": round(result.rag_score * 5.0, 2),
                "final_score": round(result.final_score * 5.0, 2),
                "overlap_terms": result.overlap_terms,
                "explanation": result.explanation,
            }
        )
    return cards


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={
            "roles": ROLE_OPTIONS,
            "results": [],
            "selected_role": "software_engineer",
            "custom_role": "",
            "top_k": 12,
            "min_score": 1.8,
            "resume_keywords": [],
            "message": "Upload resume + choose role to get personalized RAG matches.",
        },
    )


@app.post("/match", response_class=HTMLResponse)
async def match_jobs(
    request: Request,
    resume_file: UploadFile = File(...),
    role: str = Form("software_engineer"),
    custom_role: str = Form(""),
    top_k: int = Form(12),
    min_score: float = Form(1.8),
) -> HTMLResponse:
    message = ""
    results: list[dict] = []
    resume_keywords: list[str] = []
    selected_role_label = role

    try:
        payload = await resume_file.read()
        resume_text = _extract_resume_text(resume_file.filename or "", payload).strip()
        if len(resume_text) < 40:
            raise ValueError("Resume text is too short. Please upload a fuller resume.")

        jobs = load_jobs(DEFAULT_JOBS_FILE)
        if not jobs:
            raise ValueError(
                "No jobs found in data/jobs.jsonl. Run scan/import first, then retry."
            )

        selected_role_label, resume_keywords, matched = recommend_jobs_rag(
            jobs=jobs,
            resume_text=resume_text,
            selected_role=role,
            custom_role=custom_role,
            top_k=max(1, min(top_k, 50)),
        )
        results = _results_to_cards(matched, min_score=min_score / 5.0)
        message = f"Found {len(results)} matching jobs for '{selected_role_label}'."
    except Exception as exc:
        message = f"Could not match jobs: {exc}"

    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={
            "roles": ROLE_OPTIONS,
            "results": results,
            "selected_role": role,
            "custom_role": custom_role,
            "top_k": top_k,
            "min_score": min_score,
            "resume_keywords": resume_keywords,
            "message": message,
        },
    )
