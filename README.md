# AIapply.ai

Full-stack job platform with:

- frontend on **Vercel** (Next.js),
- backend on **Render** (FastAPI),
- auth/data on **Supabase**,
- payments via **Stripe Checkout**,
- role-based resume matching with a **RAG-style retrieval layer**.

## Architecture

```text
frontend (Next.js / Vercel)
  - Sign In / Create Account
  - Dashboard (profile, resume upload, role select, match results, checkout)
  - Supabase client auth
  - Calls backend API with JWT bearer token

backend (FastAPI / Render)
  - /api/auth/me
  - /api/roles/search
  - /api/profile/upsert
  - /api/profile/me
  - /api/rag/match
  - /api/auto-apply/run
  - /api/auto-apply/tick
  - /api/payments/checkout
  - /api/payments/webhook
  - Verifies Supabase JWT
```

## Repo Layout

```text
career-autopilot/
  career_autopilot/
    api.py
    rag.py
    main.py
    ...
  frontend/
    app/
      page.tsx
      dashboard/page.tsx
    lib/supabase.ts
    package.json
    .env.example
    vercel.json
  supabase/
    schema.sql
  render.yaml
  requirements.txt
```

## 1) Backend Setup (Local)

```powershell
cd "C:\Users\dilee\OneDrive\Desktop\Personal-Projects\career-autopilot"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Set values in `.env`:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `CORS_ORIGINS` (include your Vercel URL)
- `CORS_ORIGIN_REGEX` (optional wildcard for preview domains)
- `GOOGLE_FORM_ROLES_CSV_URL` (optional, Google Sheet CSV export for dynamic role suggestions)
- `LIVE_GREENHOUSE_BOARDS`, `LIVE_LEVER_SITES` (optional, live job discovery sources)
- `RESEND_API_KEY`, `EMAIL_FROM` (optional, application confirmation emails)
- `AUTO_APPLY_CRON_SECRET` (for scheduled continuous auto-apply runs)

Run backend API:

```powershell
python -m career_autopilot.main api --reload --host 127.0.0.1 --port 8000
```

Health check:

- `http://127.0.0.1:8000/healthz`

## 2) Supabase Setup

Run SQL in Supabase SQL editor:

- [supabase/schema.sql](C:/Users/dilee/OneDrive/Desktop/Personal-Projects/career-autopilot/supabase/schema.sql)

Then in Supabase Auth:

- Enable Email/Password provider.
- Configure redirect URLs for local + Vercel domains.

## 3) Frontend Setup (Local)

```powershell
cd "C:\Users\dilee\OneDrive\Desktop\Personal-Projects\career-autopilot\frontend"
Copy-Item .env.example .env.local
```

Set values in `frontend/.env.local`:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_BACKEND_URL` (local: `http://127.0.0.1:8000`)
- `NEXT_PUBLIC_STRIPE_PRICE_ID`
- `NEXT_PUBLIC_SITE_URL`

Install and run:

```powershell
npm install
npm run dev
```

Open:

- `http://127.0.0.1:3000`

## 4) Deploy Backend to Render

1. Push repo to GitHub.
2. In Render, create a new **Web Service** from this repo.
3. Use root `render.yaml` (or set manually):
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn career_autopilot.api:app --host 0.0.0.0 --port $PORT`
4. Add env vars from `.env`.
5. Deploy and copy backend URL, for example:
   - `https://aiapply-backend.onrender.com`

## 5) Deploy Frontend to Vercel

1. Import repo in Vercel.
2. Set **Root Directory** to `frontend`.
3. Add env vars from `frontend/.env.local`, with:
   - `NEXT_PUBLIC_BACKEND_URL` = your Render backend URL
4. Deploy.

## 6) Stripe Setup

1. Create product + recurring/one-time price in Stripe.
2. Put the `price_...` id in `NEXT_PUBLIC_STRIPE_PRICE_ID`.
3. Add webhook endpoint in Stripe:
   - `https://<your-render-domain>/api/payments/webhook`
4. Subscribe to `checkout.session.completed`.
5. Copy webhook secret to `STRIPE_WEBHOOK_SECRET`.

## Current UX Included

- Main auth page with:
  - **Create Account**
  - **Sign In**
- Dashboard with:
  - profile storage in Supabase,
  - extended application profile fields (authorization, sponsorship, optional sensitive fields),
  - dynamic role suggestions from Google Form/Sheet CSV (if configured),
  - resume upload,
  - role-based matching with live discovery fallback,
  - Auto Apply queue with explicit consent and daily limits,
  - Stripe checkout button.

## Continuous Auto Apply

For always-on job discovery, schedule a secure POST to:

- `/api/auto-apply/tick`

with header:

- `X-Auto-Apply-Secret: <AUTO_APPLY_CRON_SECRET>`

Render cron jobs can call this endpoint on a recurring schedule, such as every 30 or 60 minutes. This is the right place to automate continuous discovery for opted-in users.

## Why You Saw `127.0.0.1 refused to connect`

That error happens when no process is listening on port `8000`.  
Run backend first:

```powershell
python -m career_autopilot.main api --reload --port 8000
```
