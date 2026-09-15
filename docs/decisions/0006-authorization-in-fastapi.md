# 0006 — Authorization Lives in FastAPI

## Status

Accepted

## Context

Supabase provides both authentication (via its Auth service) and a Postgres
database with Row Level Security (RLS), and it permits the browser to talk to
the database directly through its client SDK. We need to decide where
traffic flows and where authorization checks — "only the seller can mark
this listing sold" — actually live.

Left unstated, this is the kind of decision that erodes silently: someone
reaches for the Supabase client for a "quick read" during E4, and from that
point on authorization logic exists in two places that can disagree.

## Decision

**Traffic split:**

- **Auth** — browser → Supabase Auth directly, via the client SDK, returning
  a JWT.
- **Data** — browser → FastAPI → Postgres. **The browser never queries the
  database directly**, even for reads, even though Supabase's architecture
  permits it.

**Authorization location:** FastAPI connects to Postgres using Supabase's
service-role key, which bypasses Row Level Security entirely. This means
**RLS provides no protection on this path** — it is not a safety net, and no
code should be written as though it were. Every ownership and permission
check (e.g., "only the seller can mark this listing sold") is application
code inside FastAPI, evaluated before the query runs.

**Anon key scope:** the Supabase anon key (the one a browser client would
use) must not be granted broad table access. Since the browser never queries
the database directly, the anon key's role is minimal by construction; it
should not be widened to enable a shortcut later.

## Alternatives Considered

**Browser → Supabase directly for data, with RLS as the enforcement layer.**
Rejected. This would mean writing and maintaining every authorization rule
twice — once as an RLS policy in SQL, once implicitly assumed by the FastAPI
business logic that also touches the same tables — with no single source of
truth for "who can do what." It also splits where a developer looks to
understand a permission: sometimes it's a route handler, sometimes it's a
SQL policy. Centralizing in FastAPI means one place to read, review, and
test.

## Consequences

- Every new endpoint that mutates or reads user-scoped data must include an
  explicit ownership/permission check in FastAPI — there is no database
  fallback if one is forgotten. This should be caught in code review.
- Because RLS is bypassed on the service-role path, RLS policies (if any
  exist on the tables) are not a substitute for testing authorization logic
  in the backend.
- The anon key stays minimally scoped, which also means nothing changes
  here if the anon key ever leaks to the client — it grants no meaningful
  data access on its own.
- All auth state (JWT) originates from Supabase Auth; FastAPI is responsible
  for validating that JWT on incoming requests, not for issuing or managing
  sessions itself.
