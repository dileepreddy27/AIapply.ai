from __future__ import annotations

import argparse
from pathlib import Path

from .apply_bot import apply_with_review
from .config import load_profile, read_yaml
from .scanners import scan_all_sources
from .scoring import score_jobs
from .storage import export_pipeline_csv, load_jobs, save_jobs, upsert_jobs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_FILE = PROJECT_ROOT / "data" / "jobs.jsonl"
DEFAULT_PIPELINE_FILE = PROJECT_ROOT / "data" / "pipeline.csv"
DEFAULT_PROFILE_FILE = PROJECT_ROOT / "config" / "profile.yml"
DEFAULT_SOURCES_FILE = PROJECT_ROOT / "config" / "sources.yml"
DEFAULT_STORAGE_STATE = PROJECT_ROOT / "data" / "browser_state.json"


def cmd_scan(args: argparse.Namespace) -> None:
    cfg = read_yaml(Path(args.sources))
    incoming = scan_all_sources(cfg, PROJECT_ROOT)
    existing = load_jobs(Path(args.jobs))
    merged = upsert_jobs(existing, incoming)
    save_jobs(Path(args.jobs), merged)
    print(f"scan complete: +{len(incoming)} discovered, total={len(merged)}")


def cmd_score(args: argparse.Namespace) -> None:
    profile = load_profile(Path(args.profile))
    jobs = load_jobs(Path(args.jobs))
    updated = score_jobs(jobs, profile, only_unscored=not args.rescore)
    save_jobs(Path(args.jobs), jobs)
    print(f"scored jobs: {updated}")


def cmd_top(args: argparse.Namespace) -> None:
    jobs = load_jobs(Path(args.jobs))
    scored = [j for j in jobs if j.score is not None]
    ranked = sorted(scored, key=lambda x: x.score or 0, reverse=True)[: args.limit]
    for i, job in enumerate(ranked, start=1):
        print(
            f"{i:02d}. [{job.score:.2f}] {job.title} | {job.company} | "
            f"{job.location} | {job.source}"
        )
        print(f"    {job.url}")


def cmd_apply(args: argparse.Namespace) -> None:
    profile = load_profile(Path(args.profile))
    jobs = load_jobs(Path(args.jobs))
    attempted, prepared = apply_with_review(
        jobs=jobs,
        profile=profile,
        project_root=PROJECT_ROOT,
        max_jobs=args.max_jobs,
        dry_run=args.dry_run,
        headless=args.headless,
        storage_state_path=Path(args.storage_state),
    )
    save_jobs(Path(args.jobs), jobs)
    print(f"apply run complete: attempted={attempted}, prepared={prepared}")


def cmd_pipeline(args: argparse.Namespace) -> None:
    jobs = load_jobs(Path(args.jobs))
    export_pipeline_csv(Path(args.out), jobs)
    print(f"pipeline exported: {args.out}")


def cmd_web(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except Exception as exc:
        raise RuntimeError(
            "uvicorn is required for web mode. Install dependencies from requirements.txt."
        ) from exc

    uvicorn.run(
        "career_autopilot.webapp:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def cmd_api(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except Exception as exc:
        raise RuntimeError(
            "uvicorn is required for api mode. Install dependencies from requirements.txt."
        ) from exc

    uvicorn.run(
        "career_autopilot.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Career Autopilot CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan configured sources for jobs")
    p_scan.add_argument("--sources", default=str(DEFAULT_SOURCES_FILE))
    p_scan.add_argument("--jobs", default=str(DEFAULT_JOBS_FILE))
    p_scan.set_defaults(func=cmd_scan)

    p_score = sub.add_parser("score", help="Score jobs against profile")
    p_score.add_argument("--profile", default=str(DEFAULT_PROFILE_FILE))
    p_score.add_argument("--jobs", default=str(DEFAULT_JOBS_FILE))
    p_score.add_argument("--rescore", action="store_true", help="Re-score all jobs")
    p_score.set_defaults(func=cmd_score)

    p_top = sub.add_parser("top", help="Show top scored jobs")
    p_top.add_argument("--jobs", default=str(DEFAULT_JOBS_FILE))
    p_top.add_argument("--limit", type=int, default=20)
    p_top.set_defaults(func=cmd_top)

    p_apply = sub.add_parser("apply", help="Open jobs and auto-fill forms")
    p_apply.add_argument("--profile", default=str(DEFAULT_PROFILE_FILE))
    p_apply.add_argument("--jobs", default=str(DEFAULT_JOBS_FILE))
    p_apply.add_argument("--max-jobs", type=int, default=5)
    p_apply.add_argument("--dry-run", dest="dry_run", action="store_true")
    p_apply.add_argument("--submit", dest="dry_run", action="store_false")
    p_apply.set_defaults(dry_run=True)
    p_apply.add_argument("--headless", action="store_true")
    p_apply.add_argument("--storage-state", default=str(DEFAULT_STORAGE_STATE))
    p_apply.set_defaults(func=cmd_apply)

    p_pipeline = sub.add_parser("pipeline", help="Export jobs as CSV")
    p_pipeline.add_argument("--jobs", default=str(DEFAULT_JOBS_FILE))
    p_pipeline.add_argument("--out", default=str(DEFAULT_PIPELINE_FILE))
    p_pipeline.set_defaults(func=cmd_pipeline)

    p_web = sub.add_parser("web", help="Run the AIapply.ai web application")
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=8000)
    p_web.add_argument("--reload", action="store_true")
    p_web.set_defaults(func=cmd_web)

    p_api = sub.add_parser("api", help="Run the Render-style backend API")
    p_api.add_argument("--host", default="127.0.0.1")
    p_api.add_argument("--port", type=int, default=8000)
    p_api.add_argument("--reload", action="store_true")
    p_api.set_defaults(func=cmd_api)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
