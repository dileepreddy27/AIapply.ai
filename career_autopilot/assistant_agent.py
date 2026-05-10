from __future__ import annotations

import os
import re
from typing import Any

import requests


ASSISTANT_MODE_DETAILS: dict[str, dict[str, str]] = {
    "job_search_planning": {
        "label": "Job Search Planning",
        "prompt": (
            "Help the user build a practical job search plan. Prioritize role targeting, weekly goals, "
            "networking suggestions, application sequencing, and risk reduction."
        ),
    },
    "resume_improvement": {
        "label": "Resume Improvement",
        "prompt": (
            "Act like a resume strategist. Improve clarity, keyword alignment, measurable outcomes, "
            "and ATS compatibility without inventing experience."
        ),
    },
    "cover_letter_generation": {
        "label": "Cover Letter Generation",
        "prompt": (
            "Draft a concise, role-specific cover letter using only the user's stated background and goals. "
            "Keep it credible and tailored."
        ),
    },
    "screening_answers": {
        "label": "Screening Answers",
        "prompt": (
            "Generate clear, recruiter-friendly answers to screening questions. Prefer short direct answers, "
            "and note where the user should customize details."
        ),
    },
    "interview_preparation": {
        "label": "Interview Preparation",
        "prompt": (
            "Prepare interview talking points, likely questions, STAR stories, and concise answer frameworks."
        ),
    },
    "follow_up_emails": {
        "label": "Follow-up Emails",
        "prompt": (
            "Write polished follow-up emails for recruiters, hiring managers, interview thank-yous, and status checks."
        ),
    },
    "application_tracking": {
        "label": "Application Tracking",
        "prompt": (
            "Help the user prioritize applications, interpret pipeline status, and decide where to follow up or pause."
        ),
    },
}


def assistant_mode_options() -> list[dict[str, str]]:
    return [
        {"value": key, "label": details["label"]}
        for key, details in ASSISTANT_MODE_DETAILS.items()
    ]


def create_thread_title(mode: str, user_message: str) -> str:
    label = ASSISTANT_MODE_DETAILS.get(mode, {}).get("label", "Career Assistant")
    first_line = re.sub(r"\s+", " ", (user_message or "").strip())
    if not first_line:
        return label
    return f"{label}: {first_line[:50]}".rstrip()


def build_profile_summary(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "No saved user profile was found."
    app = profile.get("application_profile") or {}
    parts = [
        f"Full name: {profile.get('full_name', '')}",
        f"Target role: {profile.get('target_role', '')}",
        f"Experience level: {profile.get('experience_level', '')}",
        f"Skills: {', '.join(profile.get('skills', []) or [])}",
        f"Sector: {app.get('target_sector', '')}",
        f"Country: {app.get('country', '')}",
        f"Region: {app.get('region', '')}",
        f"Preferred locations: {app.get('preferred_locations', '')}",
        f"Work preferences: {', '.join(app.get('work_preferences', []) or [])}",
        f"Salary expectation: {app.get('salary_expectation', '')}",
        f"Summary: {app.get('summary', '')}",
    ]
    return "\n".join(part for part in parts if part and not part.endswith(": "))


def build_assistant_messages(
    mode: str,
    profile: dict[str, Any] | None,
    history: list[dict[str, str]],
    latest_user_message: str,
    plan_label: str,
) -> list[dict[str, str]]:
    mode_details = ASSISTANT_MODE_DETAILS.get(mode, ASSISTANT_MODE_DETAILS["job_search_planning"])
    system_prompt = (
        "You are AIapply.ai's Personal Assistant Agent powered by DeepSeek.\n"
        f"Current subscription tier: {plan_label}.\n"
        f"Assistant mode: {mode_details['label']}.\n"
        "Follow these rules:\n"
        "- Be concrete, strategic, and helpful.\n"
        "- Never invent experience, education, or certifications.\n"
        "- Flag assumptions clearly.\n"
        "- Prefer concise sections, bullets, or templates when useful.\n"
        "- If the user asks for resume, cover letter, or screening content, ground it in the saved profile.\n"
        "- If profile information is missing, tell the user exactly what detail would strengthen the output.\n"
        f"- Task instructions: {mode_details['prompt']}\n\n"
        "Saved user profile:\n"
        f"{build_profile_summary(profile)}"
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for item in history[-10:]:
        role = item.get("role", "")
        content = item.get("content", "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": latest_user_message.strip()})
    return messages


def run_deepseek_assistant(
    messages: list[dict[str, str]],
    user_id: str,
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DeepSeek is not configured. Set DEEPSEEK_API_KEY on the backend.")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash"
    safe_user_id = re.sub(r"[^a-zA-Z0-9\-_]", "-", user_id)[:128] or "anonymous-user"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "stream": False,
        "user_id": safe_user_id,
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek returned no completion choices.")
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content") or ""
                if text:
                    text_parts.append(str(text))
        content = "\n".join(text_parts)
    if not str(content).strip():
        raise RuntimeError("DeepSeek returned an empty assistant response.")
    return str(content).strip()

