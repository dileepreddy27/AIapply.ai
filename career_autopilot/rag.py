from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

from .models import JobPosting
from .role_catalog import get_role_record, get_role_records


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


def _record_blob(record: dict[str, object]) -> str:
    fields: list[str] = [
        str(record.get("label", "")),
        str(record.get("category", "")),
    ]
    fields.extend(str(x) for x in record.get("aliases", []) or [])
    fields.extend(str(x) for x in record.get("keywords", []) or [])
    return " ".join(x for x in fields if x).strip()


def role_suggestions(query: str, extra_roles: list[str] | None = None, limit: int = 20) -> list[str]:
    records = get_role_records(extra_roles=extra_roles)
    if not query.strip():
        return [str(record["label"]) for record in records[:limit]]

    q_lower = query.strip().lower()
    q_tokens = set(extract_keywords(query, limit=12)) or set(tokenize(query))
    scored: list[tuple[float, str]] = []

    for record in records:
        label = str(record.get("label", "")).strip()
        label_lower = label.lower()
        category_lower = str(record.get("category", "")).lower()
        blob = _record_blob(record).lower()
        blob_tokens = set(extract_keywords(blob, limit=30)) or set(tokenize(blob))
        overlap = len(q_tokens & blob_tokens)

        score = 0.0
        if label_lower == q_lower:
            score += 300.0
        if label_lower.startswith(q_lower):
            score += 120.0
        if q_lower in label_lower:
            score += 80.0
        if q_lower in category_lower:
            score += 25.0
        if q_tokens:
            score += overlap * 28.0
            score += sum(1 for tok in q_tokens if tok in blob) * 8.0

        if score > 0:
            scored.append((score, label))

    ranked = [label for _, label in sorted(scored, key=lambda item: (-item[0], item[1]))]
    if ranked:
        return ranked[:limit]
    return [query.title()]


def role_terms(
    selected_role: str,
    custom_role: str = "",
    extra_roles: list[str] | None = None,
) -> tuple[str, list[str]]:
    if selected_role == "custom":
        role_text = custom_role.strip()
    else:
        role_text = selected_role.replace("_", " ").strip()

    if not role_text:
        return "any", []

    record = get_role_record(role_text, extra_roles=extra_roles)
    if record:
        blob = _record_blob(record)
        return role_text, extract_keywords(blob, limit=40)

    expansions = [role_text]
    for label in role_suggestions(role_text, extra_roles=extra_roles, limit=5):
        expansions.append(label)
        matched_record = get_role_record(label, extra_roles=extra_roles)
        if matched_record:
            expansions.append(_record_blob(matched_record))
    return role_text, extract_keywords(" ".join(expansions), limit=40)


def _role_relevance(job: JobPosting, role_keywords: list[str], role_text: str) -> float:
    if not role_keywords and role_text == "any":
        return 0.0

    blob = f"{job.title}\n{job.company}\n{job.location}\n{job.description[:2500]}".lower()
    title_blob = job.title.lower()
    role_kw = set(role_keywords)
    overlap = set(tokenize(blob)) & role_kw

    score = 0.0
    role_phrase = role_text.lower().strip()
    if role_phrase:
        if role_phrase in title_blob:
            score += 0.55
        elif role_phrase in blob:
            score += 0.25
    if role_kw:
        overlap_ratio = len(overlap) / max(1, min(len(role_kw), 8))
        score += min(0.45, overlap_ratio * 0.45)
    return min(score, 1.0)


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
    for key, value in a.items():
        dot += value * b.get(key, 0.0)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _build_idf(docs_tokens: list[list[str]]) -> dict[str, float]:
    n_docs = len(docs_tokens)
    df: Counter[str] = Counter()
    for tokens in docs_tokens:
        for term in set(tokens):
            df[term] += 1
    return {term: math.log((n_docs + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}


def filter_jobs_for_role(jobs: list[JobPosting], role_keywords: list[str], role_text: str) -> list[JobPosting]:
    if not role_keywords or role_text == "any":
        return jobs

    filtered = [job for job in jobs if _role_relevance(job, role_keywords, role_text) >= 0.18]
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
        role_score = _role_relevance(job, role_kw, role_text)
        baseline = (job.score or 0.0) / 5.0
        keyword_overlap = len(set(doc_tokens) & set(query_terms)) / max(1, min(len(set(query_terms)), 12))
        final_score = (
            0.55 * rag_score
            + 0.25 * role_score
            + 0.15 * min(keyword_overlap, 1.0)
            + 0.05 * baseline
        )

        overlap = sorted(set(doc_tokens) & set(query_terms))[:8]
        explanation = (
            f"Matched on {len(overlap)} shared terms; "
            f"rag={rag_score:.3f}, role_fit={role_score:.3f}, prior_score={job.score if job.score is not None else 0:.2f}"
        )

        scored.append(
            MatchResult(
                job=job,
                rag_score=rag_score,
                final_score=final_score,
                overlap_terms=list(overlap),
                explanation=explanation,
            )
        )

    ranked = sorted(scored, key=lambda match: match.final_score, reverse=True)[:top_k]
    return role_text, resume_kw[:12], ranked
