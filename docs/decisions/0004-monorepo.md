# 0004 — Monorepo

## Status

Accepted

## Context

ReNest consists of a frontend and a backend that share a data contract: every
endpoint the backend exposes has a corresponding client consumer in the
frontend. With a three-person team building both sides concurrently, we need
to decide whether the frontend and backend live in one repository or two.

The two realistic options were:

- **Polyrepo** — separate `renest-frontend` and `renest-backend` repositories,
  versioned and released independently.
- **Monorepo** — a single repository containing `/frontend` and `/backend`.

## Decision

We will use a single repository containing `/frontend` and `/backend`.

A single PR can change an endpoint and its client consumer together, so the
contract between them cannot silently drift or break — the same review that
approves a backend change also shows the frontend change it requires. CI runs
against one coherent snapshot of both sides at every commit.

## Alternatives Considered

**Polyrepo.** Rejected. Two repositories require coordinating merges across
them on every schema change: the backend PR merges, then the frontend PR has
to catch up, and there is a window where the two are out of sync with no
single commit that shows the full picture. This coordination cost is paid on
every change while the schema is still moving, which is most of E0–E4. For a
three-person team, the isolation benefits of separate repos (independent
release cadences, separate access control, separate CI pipelines) have no
payoff — nobody on this team needs to release the frontend without the
backend, or vice versa.

## Consequences

- One CI pipeline needs to handle both frontend and backend jobs, scoped by
  changed paths so a backend-only change doesn't force a frontend build and
  vice versa.
- Folder structure (`/frontend`, `/backend`, `/docs`) is fixed by this
  decision and drives T0.1.
- If the frontend and backend ever need independent deploy lifecycles or
  separate teams with different access needs, this decision should be
  revisited — that is not the case at this scale.
