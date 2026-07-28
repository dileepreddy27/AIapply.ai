from __future__ import annotations

import os
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
    monthly_application_limit: int | None
    price_usd: int
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
        monthly_application_limit=0,
        price_usd=0,
        highlights=[
            "Resume-based job matching",
            "Target role, location, and company filters",
            "AI assistant with limited monthly prompts",
            "Application tracker and saved profile",
        ],
    ),
    "starter": PlanDefinition(
        key="starter",
        label="Starter",
        can_job_match=True,
        can_auto_apply=True,
        can_run_continuous_auto_apply=True,
        can_use_assistant=True,
        assistant_monthly_prompts=None,
        assistant_modes=ASSISTANT_MODES,
        max_auto_apply_per_day=20,
        monthly_application_limit=600,
        price_usd=19,
        highlights=[
            "Everything in Basic",
            "Auto Apply on supported sources",
            "Up to 600 applications / 30 days",
            "Unlimited AI assistant prompts",
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
        max_auto_apply_per_day=50,
        monthly_application_limit=1500,
        price_usd=39,
        highlights=[
            "Everything in Starter",
            "Up to 1,500 applications / 30 days",
            "Continuous auto-apply scheduler eligibility",
            "Priority tailoring for resumes, cover letters, and screening answers",
        ],
    ),
    "power": PlanDefinition(
        key="power",
        label="Power",
        can_job_match=True,
        can_auto_apply=True,
        can_run_continuous_auto_apply=True,
        can_use_assistant=True,
        assistant_monthly_prompts=None,
        assistant_modes=ASSISTANT_MODES,
        max_auto_apply_per_day=150,
        monthly_application_limit=4500,
        price_usd=99,
        highlights=[
            "Everything in Pro",
            "Up to 4,500 applications / 30 days",
            "Highest daily auto-apply throughput",
            "Best for high-volume and career-transition searches",
        ],
    ),
}

# Plan tiers that unlock paid features. Anything in this set is treated like
# the legacy "pro" entitlement for gating purposes.
PAID_PLAN_KEYS = {"starter", "pro", "power"}


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
    # Legacy rows may store "pro" for any paid tier; keep that mapping valid.
    return plan if plan in PLAN_DEFINITIONS else "basic"


def resolve_plan_from_price_id(price_id: str | None, default: str = "pro") -> str:
    """Map a Stripe price id to a plan tier via env vars.

    Set STRIPE_PRICE_STARTER / STRIPE_PRICE_PRO / STRIPE_PRICE_POWER to the
    corresponding Stripe price_... ids. Unmapped price ids fall back to `default`.
    """
    pid = (price_id or "").strip()
    if not pid:
        return default
    mapping = {
        os.getenv("STRIPE_PRICE_STARTER", "").strip(): "starter",
        os.getenv("STRIPE_PRICE_PRO", "").strip(): "pro",
        os.getenv("STRIPE_PRICE_POWER", "").strip(): "power",
    }
    mapping.pop("", None)
    return mapping.get(pid, default)


def get_plan_definition(plan_name: str | None) -> PlanDefinition:
    return PLAN_DEFINITIONS[normalize_plan(plan_name)]


def plan_to_dict(plan_name: str | None) -> dict[str, Any]:
    return asdict(get_plan_definition(plan_name))

