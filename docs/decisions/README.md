# Architecture Decision Records

This directory holds ReNest's Architecture Decision Records (ADRs). An ADR
captures *why* a significant technical or product decision was made, so
nobody has to re-argue it later, and so the reasoning is already written
down when it's needed for the project proposal's Technical Approach
section.

## Format

Each ADR is a single Markdown file named `NNNN-short-title.md`, numbered
sequentially starting from `0001`. Every file has four sections:

- **Context** — the situation and constraints that made this decision
  necessary. What problem are we actually solving, and what was true about
  the project at the time?
- **Decision** — what we chose to do, stated plainly enough that someone
  skimming just this section understands the outcome.
- **Alternatives Considered** — the other options that were seriously
  considered, and why each was rejected (or deferred). This is usually the
  most valuable section months later, since it's the part nobody remembers.
- **Consequences** — what this decision commits us to, what it rules out,
  and what would trigger revisiting it.

A short **Status** line (e.g., `Accepted`) at the top of the file indicates
the ADR's current standing.

## Append-only — supersede, don't edit

ADRs are **append-only**. Once merged, a decision record is not rewritten
or deleted, even if the decision later changes. If a decision needs to
change, write a new ADR that explicitly supersedes the old one (reference
it by number), and update the old ADR's **Status** to point to the new one
(e.g., `Superseded by 0007`). This keeps the historical record of *why* a
choice was made — and *why it later changed* — intact, instead of erasing
the reasoning behind a decision that turned out to be temporary.

## Index

| ADR | Title |
| --- | --- |
| [0001](0001-email-verification-not-sso.md) | Email Verification, Not Creighton SSO |
| [0002](0002-no-payments-in-person-handoff.md) | No Payments; Transactions Are an In-Person Handoff |
| [0003](0003-stack-selection.md) | Stack Selection |
| [0004](0004-monorepo.md) | Monorepo |
| [0005](0005-modular-monolith.md) | Modular Monolith (Not Microservices) |
| [0006](0006-authorization-in-fastapi.md) | Authorization Lives in FastAPI |
