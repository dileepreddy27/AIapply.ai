from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ASSISTANT_MODES = [
    "job_search_planning",
    "resume_improvement",
    "cover_letter_generation",
    "screening_answers",
    "interview_preparation",
    "follow_up_emails",
    "application_tracking",
]


@dataclass(frozen=True)
class PlanDefinition:
    key: str
    label: str
    can_job_match: bool
    can_auto_apply: bool
    can_run_continuous_auto_apply: bool
    can_use_assistant: bool
    assistant_monthly_prompts: int | None
    assistant_modes: list[str]
    max_auto_apply_per_day: int
    highlights: list[str]


PLAN_DEFINITIONS: dict[str, PlanDefinition] = {
    "basic": PlanDefinition(
        key="basic",
        label="Basic",
        can_job_match=True,
        can_auto_apply=False,
        can_run_continuous_auto_apply=False,
        can_use_assistant=True,
        assistant_monthly_prompts=20,
        assistant_modes=ASSISTANT_MODES,
        max_auto_apply_per_day=0,
        highlights=[
            "Resume-based job matching",
            "Target role, location, and company filters",
            "AI assistant with limited monthly prompts",
            "Application tracker and saved profile",
        ],
    ),
    "pro": PlanDefinition(
        key="pro",
        label="Pro",
        can_job_match=True,
        can_auto_apply=True,
        can_run_continuous_auto_apply=True,
        can_use_assistant=True,
        assistant_monthly_prompts=None,
        assistant_modes=ASSISTANT_MODES,
        max_auto_apply_per_day=25,
        highlights=[
            "Everything in Basic",
            "Auto Apply on supported sources",
            "Continuous auto-apply scheduler eligibility",
            "Unlimited AI assistant prompts",
            "Priority AI workflow features for cover letters, interviews, and follow-ups",
        ],
    ),
}


COMPETITIVE_ADVANTAGES = [
    {
        "title": "Explainable match engine",
        "description": "Every match includes overlap terms and a relevance explanation instead of opaque scoring.",
    },
    {
        "title": "Consent-first automation",
        "description": "Auto Apply uses explicit consent, configurable approval rules, daily caps, and company avoidance filters.",
    },
    {
        "title": "Structured preference targeting",
        "description": "Sector, country, state/province, salary, and Fortune ranking filters give tighter control than generic job-title-only workflows.",
    },
    {
        "title": "Personal assistant agent",
        "description": "One assistant handles planning, resume edits, cover letters, screening answers, interview prep, follow-ups, and tracking help.",
    },
    {
        "title": "Transparent pipeline tracking",
        "description": "Users can see queued applications, status history, and source links instead of blind background automation.",
    },
]


ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing", "manual", "paid"}


def normalize_plan(plan_name: str | None) -> str:
    plan = (plan_name or "basic").strip().lower()
    return plan if plan in PLAN_DEFINITIONS else "basic"


def get_plan_definition(plan_name: str | None) -> PlanDefinition:
    return PLAN_DEFINITIONS[normalize_plan(plan_name)]


def plan_to_dict(plan_name: str | None) -> dict[str, Any]:
    return asdict(get_plan_definition(plan_name))

