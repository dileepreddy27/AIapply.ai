# Auto-Applier: queue → Playwright form fill

Two steps: (1) aggregate jobs into a unified JSON queue, (2) a Playwright worker
reads the queue and fills/submits each job, routing to the right form adapter.

```
export-queue ──▶ applier_queue.json ──▶ apply-queue (Playwright) ──▶ Greenhouse / Lever / generic form
 (JSearch)         (unified schema)        (per-job adapter)          (dry-run by default; --submit to send)
```

## 1) Build the queue

```bash
# needs RAPIDAPI_KEY (JSearch) in the environment
python -m career_autopilot.main export-queue \
  --query "Python Backend Developer" --location "United States" --pages 2 \
  --out applier_queue.json
```

Each row (deduped by `md5(company+title+location)`):

```json
{
  "job_id": "0f1e2d...",
  "title": "Backend Engineer",
  "company": "Acme",
  "location": "Austin, TX",
  "platform_source": "LinkedIn",
  "apply_url": "https://jobs.lever.co/acme/1",
  "application_type": "ATS_LEVER_API",
  "description": "Full JD for the LLM to tailor against...",
  "salary_min": 120000,
  "salary_max": 160000,
  "is_remote": false,
  "posted_at": "2024-02-01T00:00:00Z"
}
```

`application_type` drives routing: `ATS_GREENHOUSE_API`, `ATS_LEVER_API`,
`BROWSER_WORKDAY_FLOW`, `LINKEDIN_EASY_APPLY`, `INDEED`, `GENERIC_WEB_FORM`, `UNKNOWN`.

## 2) Apply from the queue

```bash
python -m career_autopilot.main apply-queue --file applier_queue.json \
  --profile config/profile.yml --resume /path/to/resume.pdf         # dry-run: fills only
python -m career_autopilot.main apply-queue --file applier_queue.json \
  --profile config/profile.yml --resume /path/to/resume.pdf --submit # live submit
```

Applicant details come from `--profile config/profile.yml` (or `APPLICANT_NAME`,
`APPLICANT_EMAIL`, `APPLICANT_PHONE`, `APPLICANT_LINKEDIN`, … env vars).

## Adapters (`career_autopilot/applier.py`)

| Route | Adapter | Behavior |
|---|---|---|
| `ATS_GREENHOUSE_API` | `_fill_greenhouse` | Fills `#first_name/#last_name/#email/#phone` + resume upload; submits `Submit Application` when `--submit` |
| `ATS_LEVER_API` | `_fill_lever` | Navigates to `/apply`, fills `name/email/phone/org/LinkedIn` + resume; submits when `--submit` |
| `GENERIC_WEB_FORM` | `_fill_generic` | "Easy Apply" style: clicks Apply, label/placeholder-matched fields + resume; submits when `--submit` |
| `BROWSER_WORKDAY_FLOW` | generic fill | Best-effort fill; **never auto-submits** (multi-step wizard needs an account) |
| `LINKEDIN_/INDEED_/Glassdoor` | — | `manual_only`: not automated (login walls + ToS); no browser launched |

Screening answers (work authorization / sponsorship) are pulled from the profile
and best-effort matched to open-ended fields.

## Safety & ToS

- **Dry-run by default** — the worker fills the form and stops; `--submit` is required to send.
- One browser context is reused across the queue; failures are isolated per job.
- **LinkedIn / Indeed / Glassdoor are deliberately not automated.** Their Easy-Apply
  flows require a logged-in session and their ToS prohibits automated submission; the
  worker marks them `manual_only`. This applies to *your own* applications with *your*
  resume — review results before enabling `--submit`, and expect some ATS forms to need
  a manual pass (custom questions vary by posting).
- Live submission needs Playwright's Chromium installed (`python -m playwright install chromium`).

The pure logic (routing, queue parsing, classification, dedup) is unit-tested; the
browser form-fill is runtime-only and not exercised in CI.
