# ReNest
![CI](https://github.com/Renest-It/App/actions/workflows/ci.yml/badge.svg?branch=main)
ReNest is a peer-to-peer marketplace built for the Creighton University community, designed to connect students leaving campus with usable dorm and apartment essentials to incoming and returning students who need those same items. The platform centers on a full "Post → Find → Contact → Sold" workflow: verified Creighton users can create and manage listings, browse and filter available items, contact sellers, and mark completed transactions as sold — combining the reach of a large online marketplace with the safety and relevance of a campus-only community.

> **Note:** This README is a work in progress. The stack table, prerequisites, and local setup/run steps for the frontend and backend are still being written and will be filled in before this epic is finished.

## Backend Setup
1. `cd backend`
2. `python -m venv venv && source venv/bin/activate` (Windows: `venv\Scripts\activate`)
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and fill in `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` (see below — the app will not start without these)
5. `alembic upgrade head` to bring your database up to the latest schema (see below — this is a **required step after every `git pull`**, not just on first setup)
6. `uvicorn app.main:app --reload`
7. Visit `http://127.0.0.1:8000/docs` for interactive API docs

### Database Migrations

The database is a single shared Supabase Postgres instance — everyone's schema is kept in sync through Alembic rather than hand-run SQL.

- **Run `alembic upgrade head` after every `git pull`.** Any teammate's new migration won't take effect on your machine (or in your queries against the shared database) until you apply it.
- To create a new migration after changing a model in `app/models/`: `alembic revision --autogenerate -m "description"`, then **hand-review the generated file** before committing — autogenerate misses constraints (like `CHECK` constraints) and can get column type changes wrong.
- `alembic downgrade base` drops all tables. Since the database is shared, never run this against the real Supabase instance unless you've coordinated with the team — test destructive migration changes against a local/disposable Postgres instance first.

### Known Stubs

- **`get_current_user()`** (`app/dependencies.py`) is **not real authentication**. It always returns the seeded `test@creighton.edu` user regardless of any request credentials — it does not check tokens, headers, or sessions. It exists so routes can depend on "the current user" via FastAPI dependency injection before real auth exists. It will be replaced with real Supabase JWT verification in E1 (see the `TODO(E1)` comment in the code, ticket SCRUM-20) with the same function signature, so no route using it will need to change.

### Getting your Supabase credentials

1. Ask a teammate for an invite to the ReNest Supabase org (or request real credentials via the team channel / password manager) — do not create a separate personal project.
2. In the [Supabase dashboard](https://supabase.com/dashboard), open the ReNest project, then go to **Project Settings → Database**.
3. Under **Connection string**, copy the **pooled** connection string (port `6543`, using the `...pooler.supabase.com` host) — not the direct connection (port `5432`). The pooler handles connection recycling correctly on Render's free tier; the direct connection does not.
4. Set that value as `DATABASE_URL` in your local `.env`, substituting your database password into the string.
5. Under **Project Settings → API**, copy the **Project URL** into `SUPABASE_URL` and the **anon public** key into `SUPABASE_ANON_KEY`.
6. Never commit `.env` or paste real credentials into the repo, issues, or PRs — `.env` is git-ignored, and only `.env.example` (with blank placeholder values) should be committed. If a credential is ever committed by accident, rotate it in Supabase immediately; removing the commit afterward is not sufficient, since the value remains in git history.

## Frontend Setup

**Prerequisites:** [Node.js](https://nodejs.org/) `^20.19` or `>=22.12` (this is Vite's requirement) and npm, which ships with Node. Check with `node -v`.

1. `cd frontend`
2. `npm install`
3. `cp .env.example .env` and fill in (the app shows a blank page with an "is not set" error in the console without these):
   - `VITE_API_BASE_URL` — `http://localhost:8000` when running the backend locally
   - `VITE_SUPABASE_URL` — Supabase **Project Settings → API → Project URL**
   - `VITE_SUPABASE_ANON_KEY` — the **anon public** key from the same page. **Never** use the `service_role` key anywhere in `frontend/`: every `VITE_` value is bundled into the public JavaScript.
4. `npm run dev` — starts the dev server at `http://localhost:5173`
5. `npm run build` — type-checks with `tsc` and produces a production build in `frontend/dist/`

Other scripts, all run from `frontend/`:

- `npm run lint` — ESLint
- `npm run format` — format everything with Prettier (`npm run format:check` verifies without writing)
- `npm run preview` — serve the production build locally

The same three `VITE_` variables are set in the Vercel project for **Production** and **Preview**. They're public values, so Vercel's plain (non-sensitive) type is fine.

### Auth in the frontend

Use `useAuth()` from `src/auth/useAuth.ts` for anything auth-related. It returns `session`, `user`, `loading`, `signUp`, `signIn`, and `signOut`. The actions return `{ error }` instead of throwing. Wait for `loading` to be `false` before treating a `null` user as logged out, or the page will flash the logged-out view on reload. `src/lib/supabase.ts` is the only Supabase client; import it rather than calling `createClient` anywhere else.

## Auth & Email Setup (Supabase dashboard)

These settings live in the Supabase dashboard, not in code, so this list is the record of how they're configured. Update it if you change any of them.

**Authentication → Sign In / Providers → Email**
- [x] Email provider enabled
- [x] "Confirm email" on — users can't sign in until they click the verification link

**Authentication → URL Configuration**
- Site URL: `https://renest-frontend.vercel.app`
- Redirect URLs:
  - `http://localhost:5173/**` — local dev
  - `https://renest-frontend.vercel.app/**` — production
  - `https://app-*-saraeavilas-projects.vercel.app/**` — Vercel preview deploys

  A sign-up from a site not on this list is sent to the Site URL instead. Redirect addresses must end in `/` to match the `/**` patterns (the frontend adds it).

**Authentication → SMTP Settings** (custom SMTP via [Brevo](https://www.brevo.com), free plan)
- Host `smtp-relay.brevo.com`, port `587`. The username is Brevo's SMTP login (`…@smtp-brevo.com`), found under Brevo → SMTP & API → **SMTP** tab.
- The password is a Brevo **SMTP key** (starts with `xsmtpsib-`). An API key (`xkeysib-`) fails with `535 Authentication failed`.
- Sender name `ReNest`; sender address is the team Gmail, verified as a single sender in Brevo. Don't use an `@creighton.edu` sender: Creighton's filters reject mail claiming its domain from outside servers.
- Brevo and team-mailbox credentials are in the team password manager, never in the repo.

**Authentication → Email Templates → Confirm signup**
- Subject: `Confirm your ReNest account`
- Body: paste the whole of [`supabase/templates/confirm-signup.html`](supabase/templates/confirm-signup.html). Edit the file in the repo and re-paste it; don't edit only in the dashboard.

**Email limits**

| | Limit | Notes |
|---|---|---|
| Supabase built-in email | 2 / hour | Checked 2026-09-23. Testing only; not used. |
| Supabase auth email rate limit | 30 / hour | Set by us, 2026-09-23 |
| Brevo free plan | 300 / day | Checked 2026-09-23 |

**Delivery test (2026-09-23):** test sign-ups to `@creighton.edu` inboxes of people outside the Supabase project all arrived in the **inbox** (not spam). The email was checked on a phone in iOS Mail and the Gmail app: readable without zooming, with an easy-to-tap button.

**If emails start landing in spam:** buy a domain, verify it in [Resend](https://resend.com) (SPF/DKIM records), and swap the SMTP settings above to Resend's. Only the dashboard settings change; no code changes.

**Known gotcha:** signing up with an email that's already registered returns success with no error. Supabase does this on purpose so nobody can find out which emails have accounts. Sign-up pages should always say "check your email", never "account created".
