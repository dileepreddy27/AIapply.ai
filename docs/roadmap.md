# AIapply.ai Roadmap & Architecture Notes

This document tracks the Tsenta-style feature build-out: what shipped, and the
architecture plan for the two big items that are deliberately **not** finished
in a single pass (production auto-submit hardening, and mobile/extension surfaces).

## Shipped (2026-07)

Feature parity work modeled on tsenta.com:

- **More ATS coverage** — Ashby added alongside Greenhouse + Lever
  (`scanners.scan_ashby`, `LIVE_ASHBY_BOARDS`). Discovery diagnostics report per-source counts.
- **Job-match alerts** — opt-in (`job_alerts_enabled`) email digest of fresh matches,
  sent from the `/api/auto-apply/tick` cron via Resend.
- **Live match feed** — `GET /api/jobs/matches` returns current matches for the saved
  profile with no resume re-upload (blends profile context + re-runs discovery).
- **Work-authorization matching** — sponsorship-aware filtering
  (`_job_matches_work_authorization`) + derived screening answers
  (`build_application_answers`, `GET /api/profile/application-answers`).
- **Resume & cover-letter tailoring** — `POST /api/tailor` (module `tailoring.py`):
  keyword-aligns to the role, rewrites factually, returns a change list + keywords;
  the dashboard shows a preview and saves versions per company (`tailored_documents`).
- **Pipeline tracker** — stages `queued → viewed → applied → replied → interviewing`,
  a board view, and `POST /api/applications/{id}/status`.
- **Auto-submit engine (experimental)** — `apply_bot.prepare_application` (server-callable,
  headless, no prompts) + `POST /api/auto-apply/submit` (consent-gated, dry-run default).

## Shipped (2026-07, wave 2 — advanced)

- **Volume pricing tiers** — Starter / Pro / Power ($19/$39/$99) with 600 / 1,500 / 4,500
  monthly application caps (`plans.py`), resolved from Stripe price ids
  (`STRIPE_PRICE_STARTER|PRO|POWER`); monthly caps enforced in auto-apply.
- **Server-side resume storage** — `POST /api/resume/upload` → Supabase Storage bucket
  (`SUPABASE_RESUME_BUCKET`, default `resumes`); the submit engine downloads and uploads it.
- **Background auto-submit worker** — `career_autopilot/worker.py`, run via
  `python -m career_autopilot.main worker [--submit] [--once]`; polls `queued_auto_apply`
  rows and drives the engine (consent-checked, dry-run by default).
- **MCP server** — `career_autopilot/mcp_server.py` exposes `search_roles`, `match_jobs`,
  `tailor` over stdio (`python -m career_autopilot.main mcp`); supports mcp 1.x and 2.x.
- **Chrome extension** — `extension/` (MV3): detects the job on the current tab and calls
  the API to find matches / tailor documents.
- **Tests + CI** — `tests/` pytest suite (27 tests) + `.github/workflows/ci.yml`
  (backend tests + frontend typecheck/build).

## Big item 1 — Production auto-submit hardening

Wave-2 progress: server-side resume storage and a background worker now exist. Remaining:

The current engine drives a headless Chromium against a single job URL and fills the
standard identity fields. To make it production-grade:

1. ~~Server-side resume storage.~~ **Done** — `POST /api/resume/upload` → Supabase Storage
   (`SUPABASE_RESUME_BUCKET`); the submit engine downloads it per user before filling forms.
2. ~~Background worker.~~ **Done (v1)** — `career_autopilot/worker.py` polls `queued_auto_apply`
   and drives the engine. Still worth adding: a real queue (RQ/Celery) so `/api/auto-apply/submit`
   only enqueues, plus retry/backoff and concurrency control.
3. **Per-ATS adapters.** Generic label/placeholder matching handles simple forms; add
   dedicated flows for Greenhouse, Lever, Ashby, and Workday (each has predictable DOM /
   multi-step wizards, custom questions, EEO pages). Keep a shared `prepare_application`
   core and layer adapters on top.
4. **Screening-question answering.** Feed `build_application_answers` + the assistant into
   open-ended questions; keep the current best-effort label matcher as a fallback.
5. **Consent, audit, and ToS.** Keep the double gate (`auto_apply_enabled` + consent),
   store a per-submission receipt (screenshot + field log), and respect each site's ToS —
   several major boards prohibit automated submission, which is why LinkedIn/Indeed/
   Glassdoor are hard-excluded in `MANUAL_ONLY_DOMAINS`.
6. **Infra.** `render.yaml` now runs `playwright install --with-deps chromium`; a worker
   service needs the same. Budget memory — headless Chromium needs ~512MB+.

**Verified so far:** the refactor imports and is dry-run safe. Live browser submission
has **not** been exercised end-to-end (no target sites, stored resumes, or browser in CI).

## Big item 2 — Mobile / iMessage / Chrome extension

Tsenta ships web + iOS/Android + iMessage + a Chrome extension + MCP/CLI. AIapply.ai
already has web + a CLI (`career_autopilot.main`). The backend API is the shared core;
each surface is a thin client over it. Recommended sequence, cheapest first:

1. **Chrome extension (highest leverage).** A content script that detects a job page,
   calls `/api/jobs/matches` / `/api/tailor`, and offers one-click "save + tailor". Reuses
   Supabase auth via the existing JWT. Small, high-value, no app-store friction.
2. **PWA / mobile web.** The Next.js app is already responsive; add a manifest + service
   worker for installable mobile before committing to native.
3. **Native apps (React Native / Expo).** Only if push notifications and app-store
   presence are worth the maintenance. Share types with the backend via an OpenAPI client
   generated from FastAPI's `/openapi.json`.
4. **iMessage / SMS.** A Twilio (or iMessage-for-business) webhook that maps a phone
   number to a user and proxies to `/api/assistant/chat` and `/api/jobs/matches`.
5. **MCP server.** Expose `search roles`, `match jobs`, `tailor`, `apply` as MCP tools so
   external agents can drive AIapply.ai — mirrors Tsenta's "MCP server and CLI".

All five depend only on the existing REST API; no core rework required.

## Other backlog (from the initial review)

- Turn off `ENABLE_PREMIUM_TEST_MODE` for production (currently everyone is Pro).
- Volume-based pricing tiers (Tsenta uses application-count tiers).
- Tests + CI (none today).
- Recruiter-email routing into the pipeline (needs inbound email infra).
