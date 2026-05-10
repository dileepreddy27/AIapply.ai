from __future__ import annotations

import os
import re
from typing import Any

import requests


def _clean_env_value(value: str) -> str:
    return value.replace('\n', '').replace('\r', '').replace('\t', '').replace('"', '').replace("'", '').strip()


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
        "You are AIapply.ai's Personal Assistant Agent.\n"
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


def _extract_anthropic_text(data: dict[str, Any]) -> str:
    text_parts: list[str] = []
    for item in data.get("content") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            text_value = str(item.get("text", "") or "").strip()
            if text_value:
                text_parts.append(text_value)
    return "\n".join(text_parts).strip()


def _anthropic_error_message(detail_payload: Any, fallback: str) -> str:
    if isinstance(detail_payload, dict):
        error_obj = detail_payload.get("error")
        if isinstance(error_obj, dict):
            message = str(error_obj.get("message", "") or "").strip()
            if message:
                return message
        message = str(detail_payload.get("message", "") or "").strip()
        if message:
            return message
    return fallback.strip()


def run_anthropic_assistant(
    messages: list[dict[str, str]],
    user_id: str,
) -> str:
    api_key = _clean_env_value(os.getenv("ANTHROPIC_API_KEY", ""))
    if not api_key:
        raise RuntimeError("Anthropic is not configured. Set ANTHROPIC_API_KEY on the backend.")

    model = _clean_env_value(os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")) or "claude-sonnet-4-20250514"
    safe_user_id = re.sub(r"[^a-zA-Z0-9\-_]", "-", user_id)[:128] or "anonymous-user"

    system_prompt = "\n\n".join(
        item.get("content", "").strip()
        for item in messages
        if item.get("role") == "system" and item.get("content", "").strip()
    ).strip()
    conversation = [
        {"role": item.get("role", "user"), "content": item.get("content", "").strip()}
        for item in messages
        if item.get("role") in {"user", "assistant"} and item.get("content", "").strip()
    ]
    if not conversation:
        raise RuntimeError("Anthropic request could not be built because no assistant input was provided.")

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 1200,
        "messages": conversation,
        "metadata": {"user_id": safe_user_id},
    }
    if system_prompt:
        payload["system"] = system_prompt

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    detail_payload = None
    try:
        detail_payload = response.json()
    except Exception:
        detail_payload = None

    detail_text = _anthropic_error_message(detail_payload, response.text)
    lowered = detail_text.lower()

    if response.status_code == 401:
        raise RuntimeError("Anthropic API key is invalid. Update ANTHROPIC_API_KEY in Render and redeploy.")
    if response.status_code == 403:
        raise RuntimeError(
            "Anthropic returned a permission error for this key or model. Check workspace access and ANTHROPIC_MODEL in Render."
        )
    if response.status_code == 429:
        raise RuntimeError(
            "Anthropic rate limit or billing limit was reached. Check Anthropic billing and usage, then try again."
        )
    if response.status_code == 529:
        raise RuntimeError("Anthropic is temporarily overloaded. Wait a moment and try the assistant again.")
    if not response.ok:
        if "credit balance" in lowered or "insufficient" in lowered or "billing" in lowered:
            raise RuntimeError(
                "Anthropic billing is not available for this key right now. Add credit or update the Anthropic account, then retry."
            )
        raise RuntimeError(f"Anthropic request failed: {detail_text}")

    data = detail_payload if isinstance(detail_payload, dict) else response.json()
    content = _extract_anthropic_text(data)
    if not content:
        raise RuntimeError("Anthropic returned an empty assistant response.")
    return content


def run_personal_assistant(
    messages: list[dict[str, str]],
    user_id: str,
) -> str:
    return run_anthropic_assistant(messages, user_id)
