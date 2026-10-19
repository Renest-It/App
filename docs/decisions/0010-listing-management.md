# 0010 — Listing Management: Edit, Delete, and Sold

## Status

Accepted (E3.1 / SCRUM-42).

## Context

E3 (SCRUM-40) lets a seller manage what they've posted: edit it, delete it, mark it sold, and
find their own drafts and listings again. E2 (ADR 0009) only covered getting a listing
published, so E3 has to answer questions E2 didn't:

- **What does "delete" mean** when a listing has photos in Supabase Storage as well as rows in
  Postgres, and the two can't be changed in one transaction?
- **Is "sold" final?** In-person handoffs (ADR 0002) fall through: a buyer doesn't show up, or
  a seller marks the wrong listing.
- **Should editing a listing move it to the top of the feed?**
- **What can change once a listing is sold?**
- **How do we stop an owner-only endpoint from forgetting its ownership check?** E2 wrote that
  check inline in three routes (publish, upload-url, register-image), and E3 adds five more.

## Decision

### One ownership check, and it returns 404

- Every owner-only route loads its listing through a single FastAPI dependency,
  `get_owned_listing()` (`backend/app/dependencies.py`). It returns `404 listing_not_found` if
  the listing doesn't exist, the ID is malformed, or the current user isn't the seller.
- **404, never 403**, whatever the listing's status. A `403` would confirm that the ID is real,
  which lets someone probe for valid listing IDs. This extends E2's rule for drafts (ADR 0009)
  to every owner-only action, and deliberately differs from API Conventions, which uses `403`
  for "not yours".
- The dependency checks ownership only. Status rules (draft only, not sold, ...) differ per
  action, so each route checks those itself.

### Delete is a hard delete, with best-effort storage cleanup

- `DELETE /listings/{id}` deletes the row. Its `listing_images` rows go with it
  (`ON DELETE CASCADE`). There's no soft delete and no undo.
- After the database commit, the backend tries to remove the listing's storage folder
  (`listings/{listing_id}/`). If that fails, the failure is **logged, not returned**: the
  response is still `204`.
- Deleting one photo (`DELETE /listings/{id}/images/{image_id}`) works the same way: the row
  goes first, then the file is removed on a best-effort basis.

### Sold is reversible

- `POST /listings/{id}/sold` moves an active listing to `sold`; `POST /listings/{id}/unsold`
  moves it back to `active`. A sold listing leaves the feed but is still viewable by ID.

### Edits don't bump the feed

- `PATCH /listings/{id}` sets `updated_at` and leaves `created_at` alone. The feed sorts by
  `created_at`, so an edited listing keeps its place.

### Sold listings are frozen

- A sold listing can't be edited (`PATCH` returns `409 listing_sold`), and its photos can't be
  added or removed. It can still be marked unsold, or deleted.

## Alternatives Considered

**403 for someone else's active listing** (what E2 did). It's the textbook status code, and
the listing is public anyway. Rejected: it still answers "does this ID exist, and is it a
draft?" differently depending on status, and one uniform 404 is simpler to reason about and
to test. The cost is a less specific error for a request the real UI never makes.

**Ownership checks written in each route.** Rejected: with eight owner-only routes, the check
is easy to leave out of one, and nothing would catch it. A dependency makes the check part of
how a route gets its listing at all.

**Soft delete** (a `deleted_at` column, hidden from every query). It would allow undo and keep
a record for moderation. Rejected for now: every query that reads listings would need to
filter it out, and forgetting once would leak "deleted" listings back into the feed. Nobody
has asked for undo. Revisit if moderation (reports, bans) needs a record of removed listings.

**Delete storage first, then the database**, or fail the request if storage fails. Rejected:
storage and Postgres can't share a transaction, so one of them can always fail after the
other succeeds. If storage goes first and the database fails, the listing survives with
broken photos. If the request fails whenever storage does, a Supabase outage blocks every
delete. Leftover files with a clean database is the only failure mode that users never see.

**Sold is final.** Simpler, and closer to a real sale. Rejected: handoffs fall through, and
the only way back would be re-creating the listing and re-uploading every photo.

**Edits bump the listing to the top.** Rejected: a seller could resurface a stale listing
indefinitely by changing one character, which pushes everyone else's listings down. Bumping
is out of scope for E3. If it's ever wanted, it should be a deliberate, rate-limited action,
not a side effect of editing.

**Allow editing sold listings.** Rejected: a sold listing records what was actually sold. If
it could change afterwards, a buyer looking back at it could see a different price or
description from the one they agreed to. Marking it unsold first makes the change explicit.

## Consequences

- **Orphaned files can accumulate** in `listing-photos` when storage cleanup fails. They're
  invisible (nothing links to them) and cheap. The same cleanup job ADR 0009 mentions for
  abandoned drafts could sweep them, if it's ever needed.
- **Deletes can't be undone**, and there's no record of a deleted listing. A moderation feature
  that needs one would supersede the hard-delete part of this ADR.
- **Every new owner-only route must use `get_owned_listing()`.** A route that loads a listing
  itself and changes it is a bug, and code review should treat it as one.
- The frontend can't tell "not yours" from "doesn't exist", and doesn't need to: the real UI
  only shows management actions on your own listings.
- `GET /listings/mine` is the only way a seller finds their drafts. E2's publish flow can leave
  a draft behind if it fails partway, and this is how the seller gets back to it.
