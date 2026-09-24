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

### Running backend tests

From `backend/`, run `pytest`. The tests run offline: they sign their own tokens with a locally generated key, so they never call Supabase, and they don't need a database. CI runs them on every PR to `main`.

Unrecognized keys in `backend/.env` are ignored, so you can keep local-only test credentials there (e.g. `TEST_EMAIL` / `TEST_PASSWORD` for a dashboard-created, auto-confirmed test account). Never commit them.

### Authentication

`app/auth.py` → `verify_token(token)` checks a Supabase access token (ES256 against the project's public keys, expiry, audience, issuer, the exact `@creighton.edu` domain, and a confirmed email) and returns the user's `AuthClaims`. Failures become JSON errors with a `code` the frontend can switch on: 401 `invalid_token`, 403 `wrong_domain` or `email_not_confirmed`, 503 `auth_unavailable`. See [ADR 0007](docs/decisions/0007-authentication-and-identity.md). No route uses it yet; E1.5 wires it into `get_current_user()`.

### Database Migrations

The database is a single shared Supabase Postgres instance — everyone's schema is kept in sync through Alembic rather than hand-run SQL.

- **Run `alembic upgrade head` after every `git pull`.** Any teammate's new migration won't take effect on your machine (or in your queries against the shared database) until you apply it.
- To create a new migration after changing a model in `app/models/`: `alembic revision --autogenerate -m "description"`, then **hand-review the generated file** before committing — autogenerate misses constraints (like `CHECK` constraints) and can get column type changes wrong.
- `alembic downgrade base` drops all tables. Since the database is shared, never run this against the real Supabase instance unless you've coordinated with the team — test destructive migration changes against a local/disposable Postgres instance first.

### Known Stubs

- **`get_current_user()`** (`app/dependencies.py`) is **not real authentication**. It always returns the seeded `test@creighton.edu` user regardless of any request credentials — it does not check tokens, headers, or sessions. It exists so routes can depend on "the current user" via FastAPI dependency injection before real auth exists. Token verification itself now exists (`app/auth.py`, see Authentication above). E1.5 (SCRUM-28) replaces this stub with the real dependency, which calls `verify_token`, with the same function signature, so no route using it will need to change (see the `TODO(E1.5)` comment in the code).

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

Use `useAuth()` from `src/auth/useAuth.ts` for anything auth-related. It returns:

- `session`, `user`, `loading`: wait for `loading` to be `false` before treating a `null` user as logged out, or the page will flash the logged-out view on reload.
- `signUp(email, password, displayName)`: the display name is stored in the Supabase user's metadata as `user.user_metadata.display_name`, which is where the backend reads it when it creates the user's row (SCRUM-28).
- `signIn(email, password)`, `signOut()`
- `resend(email)`: re-sends the verification email.

The actions return `{ error }` instead of throwing. Turn an error into user-facing text with `authErrorMessage(error)` from `src/auth/errorMessages.ts`. Never show Supabase's `error.message` to users.

Other pieces:

- `src/lib/supabase.ts` is the only Supabase client; import it rather than calling `createClient` anywhere else.
- `useLogout()` (`src/auth/useLogout.ts`) signs out and goes to `/login`. The Account tab's log-out button should use it.
- `<GuestOnly>` (`src/auth/GuestOnly.tsx`) wraps pages only signed-out visitors should see. Signed-in users are sent to Home.
- `PASSWORD_MIN_LENGTH` in `src/auth/validation.ts` must match Supabase → Authentication → Sign In / Providers → Email → "Minimum password length" (currently **6**). Change both together.
- On page load, a saved session is checked with Supabase. If the account was deleted, the session is cleared, so you aren't stuck "logged in" as a user that no longer exists.

| Route | Page |
|---|---|
| `/signup` | Sign up (display name, Creighton email, password). Signed-in users are redirected. |
| `/login` | Log in. Signed-in users are redirected. |
| `/check-email` | "Check your email", with a 60-second resend cooldown that survives a reload |
| `/auth/confirm` | Where verification links land: "You're verified!" or "Link expired" (with resend) |

The `@creighton.edu` check on the sign-up form is for user experience only. The backend enforces the domain (SCRUM-27, ADR 0006).

### App shell

`AppShell` (`src/components/AppShell.tsx`) is the navigation around every in-app page: a left rail on desktop (1024px and up) and a bottom tab bar on phones. It's the element of the `/` route in `src/router.tsx`.

- **To add a new in-app page, add it as a child of that route.** Don't wrap pages in the shell yourself.
- E1.6's route protection wraps that one route, rather than each page.
- The shell adds page padding, plus space for the mobile tab bar, so pages don't need their own outer padding. The auth pages sit outside the shell and use `AuthLayout` instead.
- Nav items are defined once in `NAV_ITEMS`, which feeds both the rail and the tab bar.

| Route | Page |
|---|---|
| `/` | Home: the listings list |
| `/sell` | Sell: the create-listing form (the old `/new` redirects here) |
| `/account` | Account: a placeholder with the Log Out button (moves to Settings later) |
| Messages | Not a route: opens Creighton webmail (`https://outlook.office.com/mail`) in a new tab. There's no in-app messaging. |

### Styling

Tailwind CSS v4 (see [ADR 0008](docs/decisions/0008-styling.md)). Design values from Figma live in the `@theme` block in `src/index.css`, with colors named by job (`bg-surface`, `text-text-muted`, `bg-accent`, `border-danger`, …). Build pages from the shared components in `src/components/` (`Button`, `TextField`, `Alert`, `AuthLayout`, `TextLink`), and don't use raw hex colors or `[#…]` arbitrary colors in components or pages. If Figma introduces a new value, add it to the theme.

`Button` has three variants:
- `primary`: the main action
- `secondary`: outlined
- `danger`: destructive actions such as Log Out

Nav labels use Geist Mono (`font-mono`).

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
