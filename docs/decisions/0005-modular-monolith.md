# 0005 — Modular Monolith (Not Microservices)

## Status

Accepted

## Context

The backend needs an internal structure. ReNest's domain has a handful of
clearly separable concerns — listings, users, categories — and we need to
decide whether those concerns are separate deployable services or separate
modules inside one application.

## Decision

We will build one FastAPI application, internally organized by domain:

```
backend/
  routers/
    listings.py
    users.py
    categories.py
```

Each domain gets its own router module with its own routes, request/response
models, and business logic, but all of it runs as a single process behind a
single deploy pipeline.

## Alternatives Considered

**Microservices** — a separate deployable service per domain (listings
service, users service, categories service), each with its own process,
database access, and deploy pipeline. Explicitly considered and rejected.

Microservices exist to let separate teams own and deploy their piece of the
system independently, and to let each piece scale independently under
uneven load. Neither applies here: a three-person team is building one
product on one timeline, so there is no team boundary for services to
protect, and there is no traffic profile that would need listings to scale
independently from users. Adopting microservices anyway would mean paying
their costs — network calls where a function call would do, distributed
debugging across process boundaries, multiple deploy pipelines to maintain
and keep in sync, and a harder story for local development — with none of
the offsetting benefit.

## Consequences

- All domain modules share one database connection pool and one deploy
  artifact; a change to any router ships in the same release as every other
  router.
- Cross-domain calls (e.g., a listing operation that checks the acting
  user's ownership) are ordinary function calls, not network calls — no
  need for retries, circuit breakers, or service discovery.
- The domain boundaries in `routers/` are still meaningful: they keep
  domain logic from bleeding into each other and are the seam we'd split
  along if this ever needed to become multiple services later. That split
  is not needed now and should not be designed for preemptively.
