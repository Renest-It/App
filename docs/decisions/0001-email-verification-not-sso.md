# 0001 — Email Verification, Not Creighton SSO

## Status

Accepted

## Context

ReNest is scoped to the Creighton University community, so the platform
needs some way to confirm that a user is actually a member of that
community before letting them post or contact sellers. Creighton, like most
universities, has an institutional single sign-on (SSO) system tied to its
identity provider. We need to decide whether the MVP integrates with that
SSO system or verifies membership some other way.

The two realistic options were:

- **Creighton SSO integration** — users authenticate through Creighton's
  identity provider, and ReNest trusts that provider's assertion of identity
  and university affiliation.
- **Email verification** — users sign up with a `@creighton.edu` address and
  confirm ownership of it via a verification link/code, with no integration
  into Creighton's identity systems.

## Decision

For the MVP, ReNest will verify community membership by confirming ownership
of a `@creighton.edu` email address, not by integrating with Creighton SSO.

This must be stated carefully: choosing email verification means **no IT
involvement is required during development**, because the app never touches
Creighton's institutional identity systems — it only sends a verification
email to an address the user provides and checks that address's domain.
This is what makes the approach viable for a semester project with no
formal channel to campus IT.

That said, **formal university adoption of ReNest beyond the MVP would
likely require IT, security, and legal review** — covering data handling
practices, use of university branding, account lifecycle management (what
happens to a listing when a student graduates or leaves), and whether
alumni or employee `@creighton.edu` addresses should qualify as community
members alongside current students. Email verification defers that review;
it does not avoid it.

## Alternatives Considered

**Creighton SSO integration.** Rejected for the MVP. SSO would require
registering ReNest as a recognized application with Creighton's identity
provider, which means engaging university IT, going through whatever
approval process exists for third-party applications touching institutional
identity, and likely signing some form of data-sharing agreement — none of
which is achievable or appropriate for a semester project built and
evaluated independently of the university. SSO also creates a hard external
dependency: if that approval process stalls, the MVP has no path to ship at
all.

## Consequences

- Anyone who can receive mail at a `@creighton.edu` address can create an
  account, including addresses that are not current-student accounts (for
  example, alumni or employee addresses, if Creighton provisions those on
  the same domain). This is an accepted MVP limitation, not an oversight.
- Because there is no integration with institutional identity systems, a
  user's account lifecycle in ReNest (created, active, deleted) is entirely
  independent of their status at the university — the platform has no way
  to know when someone graduates or leaves.
- If ReNest is ever pursued as a university-adopted tool, this decision is
  the first one to revisit, and it should be treated as requiring a real
  review cycle with IT, security, and legal — not a code change.
