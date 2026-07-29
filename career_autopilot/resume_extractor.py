"""Extract structured profile fields from a resume's plain text.

Primary path uses the Anthropic Messages API (same client/config as the assistant)
to parse the resume into a JSON object. If Anthropic is not configured or the call
fails, a lightweight regex/heuristic fallback still pulls out contact details, links,
a skills list, an experience level, and a short summary — so uploads always populate
something without a hard dependency on the LLM.

Nothing here invents data: empty fields stay empty.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .assistant_agent import _clean_env_value, run_anthropic_assistant

# Fields we return and (except email) persist onto the profile.
EXTRACT_FIELDS = (
    "full_name",
    "email",
    "phone",
    "location",
    "linkedin_url",
    "portfolio_url",
    "github_url",
    "skills",
    "experience_level",
    "summary",
)

_MAX_RESUME_CHARS = 16000
_MAX_SKILLS = 30

_SYSTEM_PROMPT = (
    "You extract structured data from a candidate's resume. "
    "Return ONLY a single valid JSON object — no prose, no markdown code fences. "
    "Use exactly these keys: "
    "full_name (string), email (string), phone (string), "
    "location (string like 'City, State' or 'City, Country'), "
    "linkedin_url (string), portfolio_url (string), github_url (string), "
    "skills (array of short strings, deduped, most relevant first), "
    "experience_level (one of 'Entry-level','Mid-level','Senior','Lead','Executive', "
    "or a phrase like '5 years'), "
    "summary (a 2-3 sentence professional summary). "
    'Use "" for missing string fields and [] for missing skills. '
    "Never invent information that is not in the resume."
)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _parse_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort parse of a JSON object from an LLM response that may be wrapped
    in markdown fences or surrounded by prose."""
    if not text:
        return None
    cleaned = text.strip()
    # Strip ```json ... ``` / ``` ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    # Fall back to the first balanced-looking {...} span.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _normalize_skills(value: Any) -> list[str]:
    items: list[str] = []
    if isinstance(value, str):
        items = re.split(r"[,\n;|•·]+", value)
    elif isinstance(value, list):
        items = [str(v) for v in value]
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        skill = re.sub(r"\s+", " ", str(raw)).strip(" .-–—")
        if not skill or len(skill) > 60:
            continue
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(skill)
        if len(out) >= _MAX_SKILLS:
            break
    return out


def extract_with_llm(resume_text: str, user_id: str = "") -> dict[str, Any] | None:
    """Ask Anthropic to parse the resume. Returns None when not configured or on error."""
    if not _clean_env_value(os.getenv("ANTHROPIC_API_KEY", "")):
        return None
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": resume_text[:_MAX_RESUME_CHARS]},
    ]
    try:
        raw = run_anthropic_assistant(messages, user_id or "resume-extract")
    except Exception:
        return None
    return _parse_json_object(raw)


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{7,}\d)(?!\d)")
_LINKEDIN_RE = re.compile(r"(https?://)?(www\.)?linkedin\.com/[^\s,)|]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"(https?://)?(www\.)?github\.com/[^\s,)|]+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s,)|]+", re.IGNORECASE)
_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:years|yrs)\b", re.IGNORECASE)


def _first_url(text: str, pattern: re.Pattern[str]) -> str:
    m = pattern.search(text)
    if not m:
        return ""
    url = m.group(0)
    if not url.lower().startswith("http"):
        url = "https://" + url
    return url.rstrip(".,);")


def _guess_name(text: str) -> str:
    for line in text.splitlines()[:8]:
        candidate = line.strip()
        if not candidate or "@" in candidate or any(ch.isdigit() for ch in candidate):
            continue
        if "http" in candidate.lower():
            continue
        tokens = candidate.split()
        if 1 < len(tokens) <= 4 and len(candidate) <= 50:
            # Mostly alphabetic words (allow hyphens/apostrophes/periods).
            if all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", tok) for tok in tokens):
                return candidate
    return ""


def _guess_summary(text: str) -> str:
    for block in re.split(r"\n\s*\n", text):
        para = re.sub(r"\s+", " ", block).strip()
        # Skip obvious contact/header lines.
        if len(para) < 60 or "@" in para[:40] or para.lower().startswith(("http", "www")):
            continue
        return para[:400].strip()
    return ""


def extract_heuristic(resume_text: str) -> dict[str, Any]:
    text = resume_text or ""
    linkedin = _first_url(text, _LINKEDIN_RE)
    github = _first_url(text, _GITHUB_RE)
    portfolio = ""
    for url in _URL_RE.findall(text):
        low = url.lower()
        if "linkedin.com" in low or "github.com" in low:
            continue
        portfolio = url.rstrip(".,);")
        break
    email_m = _EMAIL_RE.search(text)
    phone_m = _PHONE_RE.search(text)
    years_m = _YEARS_RE.search(text)
    skills = ""
    skills_match = re.search(r"(?im)^\s*(?:technical\s+)?skills?\s*[:\-]?\s*(.+(?:\n.+){0,3})", text)
    if skills_match:
        skills = skills_match.group(1)
    return {
        "full_name": _guess_name(text),
        "email": email_m.group(0) if email_m else "",
        "phone": phone_m.group(0).strip() if phone_m else "",
        "location": "",
        "linkedin_url": linkedin,
        "portfolio_url": portfolio,
        "github_url": github,
        "skills": _normalize_skills(skills),
        "experience_level": f"{years_m.group(1)} years" if years_m else "",
        "summary": _guess_summary(text),
    }


def extract_profile_fields(resume_text: str, user_id: str = "") -> dict[str, Any]:
    """Return normalized profile fields extracted from a resume. LLM values are
    preferred; heuristic values fill any gaps the LLM left empty."""
    llm = extract_with_llm(resume_text, user_id) or {}
    heuristic = extract_heuristic(resume_text)
    out: dict[str, Any] = {}
    for field in EXTRACT_FIELDS:
        value = llm.get(field)
        if _is_empty(value):
            value = heuristic.get(field)
        if field == "skills":
            out[field] = _normalize_skills(value)
        else:
            out[field] = re.sub(r"\s+", " ", str(value)).strip() if not _is_empty(value) else ""
    return out
