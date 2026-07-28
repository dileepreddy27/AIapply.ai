from __future__ import annotations

import json
import re
from typing import Any

from .assistant_agent import build_profile_summary, run_personal_assistant

TAILOR_MODES = {"resume", "cover_letter"}

_MODE_INSTRUCTIONS: dict[str, str] = {
    "resume": (
        "Tailor the candidate's resume to the target job. Re-order and rephrase existing "
        "bullet points to surface the most relevant experience, align wording and keywords "
        "with the job description, and strengthen measurable impact. You MUST NOT invent "
        "experience, employers, titles, dates, degrees, or metrics that are not already in "
        "the source resume."
    ),
    "cover_letter": (
        "Write a concise, role-specific cover letter (250-350 words) grounded only in the "
        "candidate's real background and the target job. Open with a strong hook, connect "
        "concrete experience to the role's needs, and close with a clear call to action. "
        "Do not invent experience or credentials."
    ),
}


def _build_messages(
    mode: str,
    base_text: str,
    job_title: str,
    company: str,
    job_description: str,
    profile: dict[str, Any] | None,
) -> list[dict[str, str]]:
    instruction = _MODE_INSTRUCTIONS.get(mode, _MODE_INSTRUCTIONS["resume"])
    system_prompt = (
        "You are AIapply.ai's application tailoring engine.\n"
        f"Task: {instruction}\n"
        "Rules:\n"
        "- Never fabricate facts. Only use information present in the source material or profile.\n"
        "- Prefer the job description's own terminology where the candidate genuinely matches it.\n"
        "Return ONLY a JSON object (no markdown, no prose) with exactly these keys:\n"
        '  "tailored_text": the full tailored document as a single string,\n'
        '  "changes": an array of short strings describing each meaningful change you made,\n'
        '  "keywords": an array of job-description keywords you aligned to.\n\n'
        "Saved candidate profile:\n"
        f"{build_profile_summary(profile)}"
    )
    user_prompt = (
        f"TARGET ROLE: {job_title or 'Unknown role'}\n"
        f"COMPANY: {company or 'Unknown company'}\n\n"
        f"JOB DESCRIPTION:\n{(job_description or '').strip()[:6000] or 'Not provided.'}\n\n"
        f"CANDIDATE SOURCE {'RESUME' if mode == 'resume' else 'BACKGROUND / NOTES'}:\n"
        f"{(base_text or '').strip()[:8000] or 'Use the saved profile above.'}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _parse_tailoring_response(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    # Strip code fences if the model wrapped the JSON.
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    if not candidate.startswith("{"):
        brace = candidate.find("{")
        if brace != -1:
            candidate = candidate[brace:]
    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(candidate)
    except Exception:
        parsed = None
    if not isinstance(parsed, dict):
        # Fall back to returning the raw text so the user still gets output.
        return {"tailored_text": text, "changes": [], "keywords": []}
    changes = parsed.get("changes") or []
    keywords = parsed.get("keywords") or []
    return {
        "tailored_text": str(parsed.get("tailored_text", "") or "").strip() or text,
        "changes": [str(c).strip() for c in changes if str(c).strip()][:20],
        "keywords": [str(k).strip() for k in keywords if str(k).strip()][:30],
    }


def run_tailoring(
    mode: str,
    base_text: str,
    job_title: str,
    company: str,
    job_description: str,
    profile: dict[str, Any] | None,
    user_id: str,
) -> dict[str, Any]:
    normalized_mode = mode if mode in TAILOR_MODES else "resume"
    messages = _build_messages(
        mode=normalized_mode,
        base_text=base_text,
        job_title=job_title,
        company=company,
        job_description=job_description,
        profile=profile,
    )
    raw = run_personal_assistant(messages, user_id=user_id)
    result = _parse_tailoring_response(raw)
    result["mode"] = normalized_mode
    return result
