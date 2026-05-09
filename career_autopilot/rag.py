from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

from .models import JobPosting


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
    "your",
    "you",
    "will",
    "our",
    "we",
    "this",
    "these",
    "those",
    "their",
    "they",
    "them",
    "into",
    "about",
    "using",
    "use",
    "experience",
    "years",
    "year",
    "work",
    "working",
    "role",
    "team",
    "job",
    "position",
}

ROLE_PRESETS: dict[str, list[str]] = {
    "software_engineer": [
        "software engineer",
        "backend",
        "frontend",
        "full stack",
        "python",
        "java",
        "javascript",
        "react",
        "api",
        "microservices",
        "distributed systems",
    ],
    "data_scientist": [
        "data scientist",
        "machine learning",
        "statistics",
        "python",
        "sql",
        "pandas",
        "modeling",
        "analytics",
        "experimentation",
    ],
    "ml_engineer": [
        "ml engineer",
        "machine learning",
        "pytorch",
        "tensorflow",
        "model serving",
        "feature store",
        "mlops",
        "pipeline",
        "inference",
    ],
    "nurse": [
        "nurse",
        "registered nurse",
        "rn",
        "clinical",
        "patient care",
        "charting",
        "hospital",
        "icu",
        "medication",
        "triage",
    ],
    "product_manager": [
        "product manager",
        "roadmap",
        "stakeholder",
        "kpi",
        "user research",
        "delivery",
        "agile",
    ],
    "cybersecurity": [
        "security",
        "soc",
        "siem",
        "incident response",
        "iam",
        "cloud security",
        "threat",
        "vulnerability",
    ],
}


@dataclass
class MatchResult:
    job: JobPosting
    rag_score: float
    final_score: float
    overlap_terms: list[str]
    explanation: str


def tokenize(text: str) -> list[str]:
    return [tok.lower() for tok in TOKEN_RE.findall(text or "")]


def normalize_role_key(role_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", role_name.lower()).strip("_")


def extract_keywords(text: str, limit: int = 20) -> list[str]:
    counts = Counter(tok for tok in tokenize(text) if tok not in STOPWORDS and len(tok) > 2)
    return [t for t, _ in counts.most_common(limit)]


def role_terms(selected_role: str, custom_role: str = "") -> tuple[str, list[str]]:
    if selected_role == "custom":
        role_text = custom_role.strip()
    else:
        role_text = selected_role.replace("_", " ").strip()

    if not role_text:
        return "any", []

    preset = ROLE_PRESETS.get(normalize_role_key(role_text))
    if preset:
        return role_text, extract_keywords(" ".join(preset), limit=30)
    return role_text, extract_keywords(role_text, limit=30)


def _to_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    if not tokens:
        return {}
    tf = Counter(tokens)
    denom = float(len(tokens))
    return {term: (count / denom) * idf.get(term, 1.0) for term, count in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, v in a.items():
        dot += v * b.get(k, 0.0)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _build_idf(docs_tokens: list[list[str]]) -> dict[str, float]:
    n_docs = len(docs_tokens)
    df: Counter[str] = Counter()
    for toks in docs_tokens:
        for term in set(toks):
            df[term] += 1
    return {term: math.log((n_docs + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}


def filter_jobs_for_role(jobs: list[JobPosting], role_keywords: list[str], role_text: str) -> list[JobPosting]:
    if not role_keywords or role_text == "any":
        return jobs

    role_kw = set(extract_keywords(" ".join(role_keywords), limit=40))
    filtered: list[JobPosting] = []
    for job in jobs:
        blob = f"{job.title} {job.description[:2000]}".lower()
        tokens = set(tokenize(blob))
        overlap = tokens & role_kw
        if overlap:
            filtered.append(job)
            continue
        if role_text.lower() in blob:
            filtered.append(job)

    return filtered if filtered else jobs


def recommend_jobs_rag(
    jobs: list[JobPosting],
    resume_text: str,
    selected_role: str,
    custom_role: str = "",
    top_k: int = 15,
) -> tuple[str, list[str], list[MatchResult]]:
    role_text, role_kw = role_terms(selected_role, custom_role)
    resume_kw = extract_keywords(resume_text, limit=30)
    filtered_jobs = filter_jobs_for_role(jobs, role_kw, role_text)

    query_terms = role_kw + resume_kw
    if not query_terms:
        query_terms = extract_keywords(resume_text, limit=20)

    documents = [
        f"{job.title}\n{job.company}\n{job.location}\n{job.description[:4000]}"
        for job in filtered_jobs
    ]
    docs_tokens = [tokenize(doc) for doc in documents]
    idf = _build_idf(docs_tokens) if docs_tokens else {}

    query_vector = _to_vector(tokenize(" ".join(query_terms)), idf)

    scored: list[MatchResult] = []
    for job, doc_tokens in zip(filtered_jobs, docs_tokens):
        doc_vec = _to_vector(doc_tokens, idf)
        rag_score = _cosine(query_vector, doc_vec)
        baseline = (job.score or 0.0) / 5.0
        final_score = 0.8 * rag_score + 0.2 * baseline

        overlap = list((set(doc_tokens) & set(query_terms)))
        overlap = sorted(overlap)[:8]
        explanation = (
            f"Matched on {len(overlap)} shared terms; "
            f"rag={rag_score:.3f}, prior_score={job.score if job.score is not None else 0:.2f}"
        )

        scored.append(
            MatchResult(
                job=job,
                rag_score=rag_score,
                final_score=final_score,
                overlap_terms=overlap,
                explanation=explanation,
            )
        )

    ranked = sorted(scored, key=lambda m: m.final_score, reverse=True)[:top_k]
    return role_text, resume_kw[:12], ranked
