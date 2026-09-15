# 0003 — Stack Selection

## Status

Accepted

## Context

ReNest is a semester-long, three-person project with hard checkpoint dates
(demos, a proposal, a final submission) and no dedicated infrastructure or
ops support. The stack needs to be productive for a small team working
quickly, low-risk to operate without prior ops experience, and unlikely to
introduce friction at a live checkpoint demo.

## Decision

ReNest is built on:

- **Frontend:** React + TypeScript, built with Vite
- **Backend:** FastAPI (Python)
- **Database:** Supabase Postgres
- **Auth:** Supabase Auth
- **File/image storage:** Supabase Storage
- **Migrations:** Alembic
- **Frontend hosting:** Vercel
- **Backend hosting:** Render
- **CI:** GitHub Actions

Supabase is used for Postgres, Auth, and Storage as one managed vendor
rather than three separate ones, which minimizes the number of accounts,
credentials, and dashboards a three-person team has to stand up and keep in
sync. See ADR 0006, Authorization Lives in FastAPI, for how authorization is
layered on top of Supabase's auth and database.

## Alternatives Considered

**React Native + Expo**, instead of a web frontend. Rejected: no MVP feature
(browsing listings, posting a listing, contacting a seller) requires native
device capabilities, and native builds add signing and packaging steps that
are a real source of demo-day risk — a broken build or an expired signing
certificate can block a checkpoint demo in a way a web app cannot. A
responsive web app reaches the same phones through a browser with none of
that risk.

**Cloudinary**, for image storage. Rejected: Supabase Storage already
covers the file storage need (listing photos), so adding Cloudinary would
mean a second vendor, a second set of credentials, and a second thing that
can go down — for no capability ReNest actually needs at MVP scope.

**AWS** (S3, RDS, etc.), as the hosting/infra layer. Rejected: AWS's IAM
model and billing structure are built for infrastructure that outlives a
semester and is operated by people who manage AWS regularly. For a
three-person team on a fixed timeline, that complexity is pure overhead —
Vercel and Render both deploy directly from GitHub with effectively no
infrastructure configuration.

**Docker**, for local development and/or deployment. Deferred, not
rejected. Docker solves environment-mismatch problems that have not
occurred yet; introducing it preemptively adds a layer the team has to
learn and maintain without a concrete problem to justify it. Revisit if an
actual environment mismatch appears, or during E7 if containerization
becomes relevant to deployment at that stage.

## Consequences

- The team depends on Supabase, Vercel, Render, and GitHub Actions all
  staying available and within their free/hobby tiers for the semester;
  none of these are self-hosted, so there is no fallback if a vendor has an
  outage during a checkpoint.
- Because Supabase Auth is used but Supabase's client-side database access
  is not, the traffic-flow and authorization decisions in
  ADR 0006 (Authorization Lives in FastAPI) apply directly on top of this stack.
- Alembic migrations mean schema changes are code-reviewed and versioned
  alongside the FastAPI app, rather than made ad hoc through the Supabase
  dashboard.
- Revisiting Docker (deferred above) is the most likely stack change during
  the project's lifetime; it should be reconsidered explicitly at E7 rather
  than added incrementally without a decision record.
