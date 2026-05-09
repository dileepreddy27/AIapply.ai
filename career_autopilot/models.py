from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobPosting:
    id: str
    source: str
    company: str
    title: str
    location: str
    url: str
    description: str = ""
    discovered_at: str = field(default_factory=utc_now_iso)
    score: float | None = None
    score_reason: str = ""
    status: str = "new"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "JobPosting":
        return cls(
            id=str(raw.get("id", "")),
            source=str(raw.get("source", "")),
            company=str(raw.get("company", "")),
            title=str(raw.get("title", "")),
            location=str(raw.get("location", "")),
            url=str(raw.get("url", "")),
            description=str(raw.get("description", "")),
            discovered_at=str(raw.get("discovered_at", utc_now_iso())),
            score=raw.get("score"),
            score_reason=str(raw.get("score_reason", "")),
            status=str(raw.get("status", "new")),
        )


@dataclass
class Profile:
    name: str
    email: str
    phone: str
    location: str
    target_roles: list[str]
    skills: list[str]
    keywords: list[str]
    narrative: str
    experience_years: int
    links: dict[str, str]
    assets: dict[str, str]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Profile":
        return cls(
            name=str(raw.get("name", "")),
            email=str(raw.get("email", "")),
            phone=str(raw.get("phone", "")),
            location=str(raw.get("location", "")),
            target_roles=[str(x) for x in raw.get("target_roles", [])],
            skills=[str(x) for x in raw.get("skills", [])],
            keywords=[str(x) for x in raw.get("keywords", [])],
            narrative=str(raw.get("narrative", "")),
            experience_years=int(raw.get("experience_years", 0)),
            links={str(k): str(v) for k, v in raw.get("links", {}).items()},
            assets={str(k): str(v) for k, v in raw.get("assets", {}).items()},
        )
