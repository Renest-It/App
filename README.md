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
3. `npm run dev` — starts the dev server at `http://localhost:5173`
4. `npm run build` — type-checks with `tsc` and produces a production build in `frontend/dist/`

Other scripts, all run from `frontend/`:

- `npm run lint` — ESLint
- `npm run format` — format everything with Prettier (`npm run format:check` verifies without writing)
- `npm run preview` — serve the production build locally

The frontend does not call the backend yet, so it runs without any `.env` file or a running API.
