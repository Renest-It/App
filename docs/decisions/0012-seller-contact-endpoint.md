# 0012 — Seller Contact Endpoint

## Status

Accepted (E6.1 / SCRUM-60).

## Context

There's no in-app messaging (ADR 0002): a buyer who wants a listing has to reach the seller
off-platform, which means getting their email. Up to now the seller's email has never been
returned by any listings endpoint on purpose — `SellerOut`/`Seller` only ever carry `id` and
`display_name` (`docs/api/listings.md`) — so E6.1 has to add exactly one way to get it,
without quietly loosening that rule anywhere else.

Two things have to be settled before the endpoint can be built:

- **Where the email lives in the response shape.** Putting it on the listing detail response
  would mean every `GET /listings/{id}` call leaks it, including the drafts/feed scan a
  logged-in but uninterested user might do just by browsing.
- **What stops someone from harvesting emails.** Any logged-in student can already walk the
  whole feed page by page (E4). If the same is true of a per-listing contact lookup, a script
  could collect every active seller's email in a few hundred requests. Something has to make
  that visible, even if nothing blocks it outright this semester.

## Decision

### A separate endpoint: `GET /listings/{id}/seller-contact`

The email is returned only from its own endpoint, never alongside the listing itself. A buyer
has to take the deliberate step of asking to contact the seller; a feed scan or a listing-detail
fetch never sees it. Visibility reuses the existing owner-or-anyone-if-active rule
(`_get_visible_listing`, same as `GET /listings/{id}`): someone else's draft, or an unknown or
malformed ID, is `404 listing_not_found` — this endpoint can't be used to probe for listings
that `GET /listings/{id}` wouldn't already show.

### Logged, not rate-limited

Every successful call is logged at `INFO` with the caller's user ID and the listing ID. This
doesn't stop a scripted harvest in the moment, but it makes the pattern — one account calling
this endpoint far more than a person manually contacting sellers would — visible after the
fact.

Rate limiting the endpoint was deliberately left out **this semester**. The app runs on
Render's free tier, which spins the backend down on idle and loses any in-memory limiter state
on every spin-up/spin-down cycle. Shipping a rate limiter here would look like a real
protection in a demo or a code review, while actually resetting every time the dyno sleeps —
protecting little in practice and hiding that fact. The honest trade for this semester is: log
every reveal, write down the gap plainly (this ADR), and treat a real limiter — backed by
something that survives a restart, such as the Postgres database already in use, or a paid tier
with a persistent cache — as explicit future work, not a silent gap.

## Alternatives Considered

- **Add `email` to the existing listing-detail response (`SellerOut`/`ListingDetail`).**
  Rejected. It would reverse the standing "never add email here" rule on the one schema every
  other endpoint already trusts to omit it, and it would hand out the email to anyone who
  simply views the listing, not just someone who asks to contact the seller.
- **Rate-limit the endpoint now (in-memory, per-IP or per-user).** Rejected for this semester.
  On Render's free tier the backend process (and any in-memory counters) is recycled on every
  idle spin-down, so the limiter would reset constantly and give a false sense of protection.
  Revisit once there's persistent storage for limiter state, or a paid tier that doesn't
  spin down.
- **No logging either, since it isn't rate-limited anyway.** Rejected. Logging is cheap and is
  the only signal available this semester for noticing a harvesting pattern after the fact;
  dropping it would leave no evidence trail at all.
- **Require some extra step (e.g. a "reason" field, or limiting to active listings only) before
  revealing the email.** Rejected as unnecessary complexity: visibility already matches
  `GET /listings/{id}` exactly, so this endpoint reveals nothing about which listings exist that
  a buyer couldn't already learn by opening the listing page itself.

## Consequences

- The seller's email is now reachable through exactly one endpoint, documented in
  `docs/api/listings.md`, and `SellerOut`/`Seller` keep their "no email" contract everywhere
  else — `test_seller_contact.py`'s regression test asserts this directly for `GET /listings`,
  `GET /listings/{id}`, and `GET /listings/mine`.
- A motivated user can still script a full-feed email harvest this semester; nothing in this
  decision prevents that, only makes it detectable after the fact via the `INFO` logs.
- **Open for future work: real rate limiting.** Once the backend runs somewhere that doesn't
  reset in-memory state on every idle cycle (a paid Render tier, or a limiter backed by
  Postgres/Redis), add per-user rate limiting to this endpoint and record that decision here as
  an addendum, or in a new ADR if the approach changes this one.