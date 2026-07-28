"""MCP server exposing AIapply.ai job tools to external agents.

Run over stdio:

    python -m career_autopilot.main mcp

Tools:
- search_roles(query, sector) -> role suggestions
- match_jobs(role, resume_text, top_k) -> ranked matches from live ATS discovery
- tailor(mode, job_title, company, job_description, base_text) -> tailored document

search_roles / match_jobs need no credentials (public ATS discovery). tailor needs
ANTHROPIC_API_KEY. This mirrors Tsenta's "MCP server and CLI" agent surface.
"""

from __future__ import annotations

from typing import Any

# The server class was renamed FastMCP -> MCPServer in the mcp 2.x SDK; support both.
_ServerClass: Any = None
_IMPORT_ERROR: Exception | None = None
try:
    from mcp.server.mcpserver import MCPServer as _ServerClass  # mcp >= 2.0
except Exception:
    try:
        from mcp.server.fastmcp import FastMCP as _ServerClass  # mcp 1.x
    except Exception as exc:  # pragma: no cover - optional dependency
        _IMPORT_ERROR = exc


def _build_server() -> Any:
    if _ServerClass is None:
        raise RuntimeError(
            "The 'mcp' package is required for the MCP server. Install it with "
            f"`pip install mcp`. ({_IMPORT_ERROR})"
        )

    from .rag import role_suggestions
    from .tailoring import run_tailoring
    from .api import _discover_live_jobs_with_diagnostics, _match_jobs_for_profile  # noqa: WPS437

    server = _ServerClass("aiapply")

    @server.tool()
    def search_roles(query: str, sector: str = "") -> list[str]:
        """Suggest normalized job-role titles for a free-text query."""
        return role_suggestions(query, limit=20, sector=sector)

    @server.tool()
    def match_jobs(role: str, resume_text: str = "", top_k: int = 20) -> dict[str, Any]:
        """Discover live roles (Greenhouse/Lever/Ashby) and rank them for a role/resume."""
        profile = {"target_role": role, "skills": [], "application_profile": {}}
        if resume_text.strip():
            profile["application_profile"] = {"summary": resume_text.strip()[:4000]}
        cards, diagnostics = _match_jobs_for_profile(profile, role, top_k=top_k)
        return {"role": role, "count": len(cards), "results": cards, "diagnostics": diagnostics}

    @server.tool()
    def tailor(
        mode: str,
        job_title: str,
        company: str = "",
        job_description: str = "",
        base_text: str = "",
    ) -> dict[str, Any]:
        """Tailor a resume or cover_letter to a role. Requires ANTHROPIC_API_KEY."""
        return run_tailoring(
            mode=mode,
            base_text=base_text,
            job_title=job_title,
            company=company,
            job_description=job_description,
            profile=None,
            user_id="mcp",
        )

    return server


def main() -> None:
    _build_server().run()


if __name__ == "__main__":
    main()
