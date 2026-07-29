# Job Aggregation Layer

How AIapply.ai pulls jobs from many platforms into one normalized feed for the
matcher and the auto-applier.

```
[ Job platforms ]                [ Unified aggregator layer ]        [ Pipeline ]        [ Auto-applier ]
Greenhouse / Lever / Ashby  ──▶  direct ATS scanners (scanners.py) ─┐
SmartRecruiters / Recruitee ──▶  direct ATS scanners               ├─▶ dedupe + normalize ─▶ RAG match ─▶ queue / submit
LinkedIn / Indeed / Glassdoor ▶  JSearch (RapidAPI)  ──────────────┤   (JobPosting schema)
the wider web / most ATSes  ──▶  SerpApi Google Jobs ──────────────┤
niche boards                ──▶  RSS/Atom feeds ───────────────────┘
```

## Sources

All sources normalize to the `JobPosting` schema and run inside per-source
try/except in `career_autopilot/api.py::_discover_live_jobs_with_diagnostics`, so
one failing source never breaks discovery. Every source is **optional** — it is
skipped unless its key/board/feed is configured.

| Layer | Source | Config | Covers |
|---|---|---|---|
| Direct ATS | Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee | `LIVE_*_BOARDS/COMPANIES` | Company career pages on those ATSes |
| Aggregator API | **JSearch** (`aggregators.scan_jsearch`) | `RAPIDAPI_KEY` | LinkedIn, Indeed, Glassdoor, ZipRecruiter, … in one call |
| Aggregator API | **SerpApi Google Jobs** (`scan_serpapi_google_jobs`) | `SERPAPI_KEY` | Nearly the whole web (Google indexes most boards/ATSes) |
| Feeds | **RSS/Atom** (`scan_rss`, stdlib parser) | `LIVE_RSS_FEEDS` | Niche boards that publish feeds |

## The two engineering gates (from the aggregator design)

1. **Cross-platform dedup** — `_dedupe_jobs` collapses exact-URL duplicates, then
   hashes `company + title + location` to merge the *same* role posted on multiple
   platforms, keeping the most actionable listing (a direct/ATS apply with a
   description beats a bare LinkedIn/aggregator link).
2. **Apply-type classification** — `aggregators.classify_apply_type` tags each job
   (`external_ats`, `linkedin_easy_apply`, `indeed`, `glassdoor`, `direct`,
   `unknown`) and stores it on `JobPosting.apply_type` (surfaced in match cards).
   The auto-submit engine can branch on this: `external_ats` → drive the ATS form;
   `linkedin_easy_apply` → not automated (see ToS note).

## Why not scrape LinkedIn/Indeed directly?

Deliberately not implemented. LinkedIn/Indeed heavily protect their data; direct
scraping needs login walls, CAPTCHA solving, and rotating residential proxies, and
risks IP/account bans and ToS violations. The **aggregator APIs above are the
sanctioned "shortest path"** to that same data. The headless auto-submit engine
also hard-excludes `linkedin.com` / `indeed.com` / `glassdoor.` in
`apply_bot.MANUAL_ONLY_DOMAINS`.

## "Pull all jobs from all platforms" — realistically

No single system returns literally everything. The practical union here is:
direct ATS (Greenhouse/Lever/Ashby/SmartRecruiters/Recruitee) **+** JSearch
(the big consumer boards) **+** Google Jobs (the long tail) **+** RSS (niche).
Configure `RAPIDAPI_KEY` + `SERPAPI_KEY` to switch on the broad consumer coverage;
add ATS boards/RSS feeds for depth.
