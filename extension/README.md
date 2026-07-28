# AIapply.ai Chrome Extension

A Manifest V3 extension that detects a job posting on the current tab and calls the
AIapply.ai backend to find matches and tailor your resume / cover letter.

## Load it (unpacked)

1. Open `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → select this `extension/` folder.
3. Click the AIapply.ai toolbar icon → **Settings**:
   - **Backend URL** — your Render backend (e.g. `https://aiapply-backend.onrender.com`).
   - **Access token** — a Supabase JWT from the web app. On the dashboard, open DevTools
     console and run:
     ```js
     copy((await supabase.auth.getSession()).data.session.access_token)
     ```
   - **Save settings**.

## Use it

- Open any job posting (Greenhouse, Lever, Ashby, company career pages…).
- Click the extension:
  - **Find Matches** → calls `GET /api/jobs/matches` (uses the detected role or your profile).
  - **Tailor Resume / Cover Letter** → calls `POST /api/tailor` with the detected
    title/company/description.

## Notes

- The popup runs as an extension page with `host_permissions: <all_urls>`, so browser CORS
  is not enforced for its requests — no backend CORS change is needed.
- The token is stored in `chrome.storage.local`. Tokens expire; re-copy when calls 401.
- `content.js` is read-only (extracts page text); it never submits anything.
- Roadmap: replace the paste-a-token flow with a proper Supabase OAuth sign-in popup.
