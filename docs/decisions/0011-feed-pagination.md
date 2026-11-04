# 0011 — Feed Pagination: Keyset Cursors

## Status

Accepted (E4.1 / SCRUM-50).

## Context

Until E4, `GET /listings` returned every active listing in one response, as a bare array.
E4 (SCRUM-48) loads the home feed incrementally (infinite scroll with a "Load more" button)
and has to settle several things before the backend (E4.2) and frontend (E4.3) are built in
parallel:

- **How pages are linked.** New listings arrive at the top of the feed all the time, so the
  approach must not repeat or skip listings when someone posts mid-scroll.
- **The response shape.** [API Conventions](../api-conventions.md) defines
  `{ items, page: { limit, offset, total } }` for collections, but it was written before any
  endpoint was paginated.
- **What happens with a bad page size or a bad page token.** Both are user-controlled input.
- **The index.** Without one, every page is a scan and sort of all active listings.
- **E5's category filter.** E5 adds filtering. If the cursor and index only know about time,
  E5 would have to rewrite the query, the cursor format, the index, and the frontend's
  page handling.

## Decision

### Keyset pagination on `(created_at, id)`

- The feed is ordered by `created_at DESC, id DESC`. `id` breaks ties between listings created
  at the same moment.
- A page is "the first `limit` active listings strictly older than the cursor's position":
  `WHERE status = 'active' AND (created_at, id) < (:t, :id) ORDER BY created_at DESC, id DESC`.
- The server fetches `limit + 1` rows. If the extra row exists, `next_cursor` is built from
  the **last returned** item; otherwise it's `null`. So `null` means end of feed, and a
  non-null cursor never leads to an empty page.

### The response is `{ items, next_cursor }`

This replaces the bare array and differs from the conventions' envelope. Keyset pagination has
no offset, and a `total` would need a `count(*)` on every request for a number the feed never
shows. `items` keeps the conventions' name. The difference is recorded in
`docs/api/listings.md`'s "Differences from API Conventions" table.

### The cursor is an opaque, versioned token

- It's base64url (no padding) of compact JSON: `{"v":1,"t":"<created_at>","id":"<uuid>","f":{}}`.
  - `v` is the format version, so the format can change without old cursors being misread.
  - `t` keeps **microseconds**, because Postgres stores them and a truncated boundary skips or
    repeats rows.
  - `f` is the filter the cursor was issued under, so it can carry a category filter. It's
    `{}` until E5, which adds `{"category": <id>}`.
- Clients treat cursors as opaque: they send them back unchanged and never build or parse one.
- Anything the server can't use returns `422 invalid_cursor`, never a `500`. That covers bad
  base64 or JSON, an unknown `v`, missing or wrong fields, a bad timestamp or uuid, or an `f`
  that doesn't match the request's filter. The client's recovery is to drop the cursor and
  reload from the first page.
- A cursor only works with its own filter. Changing the filter means starting again from the
  first page.

### `limit` defaults to 20, accepts 1–50, and is rejected outside that

20 fills about 10 rows on a two-column phone grid. A bad `limit` gets FastAPI's default `422`
instead of being clamped: the frontend never sends one, so a 422 can only mean a bug, and
clamping would hide it.

### `listings.created_at` is `NOT NULL`

Keyset ordering needs every row to have a position. A `NULL` `created_at` sorts first under
`DESC` and can't take part in the row comparison, so that listing would never be served, or
always be. The E4.1 migration backfills any `NULL`s with `now()` and adds the constraint.

### One index: `(status, created_at DESC, id DESC) INCLUDE (category_id)`

- The leading `status` equality, followed by the feed's sort order, lets Postgres start at the
  cursor position and read `limit + 1` entries with no sort step.
- `category_id` is an `INCLUDE` column, not a key column. E5's `AND category_id = :id` is
  then checked from the index entries, without visiting the table for rows that don't match,
  and the column order the unfiltered feed depends on stays intact.
- With the demo dataset (about 60 listings), the planner may still choose a sequential scan,
  which is correct at that size. E4.2 checks the plan against seeded data.

### Rollout without breaking the home page

The mocks switch to the new shape in E4.1, the backend in E4.2, and the home page in E4.3.
Until E4.3, `getListings()` in the frontend accepts both the bare array and the envelope, so
the three can merge in any order.

## Alternatives Considered

- **Offset pagination (`LIMIT/OFFSET`).** Rejected. When someone posts while you scroll, every
  later page shifts by one, so page 2 repeats the last item of page 1. Deep offsets also get
  slower, because the database still reads and discards every skipped row.
- **Cursor on `created_at` alone.** Rejected. Two listings with the same timestamp straddling
  a page boundary would be skipped or repeated. Tie-breaking on `id` is what makes the walk
  exact.
- **Signing the cursor (HMAC).** Rejected. A tampered cursor can only point at a different
  spot in data the caller can already page through, so signing protects nothing and adds a
  secret to manage. Strict validation is what keeps bad input from causing `500`s.
- **The conventions' `{ items, page: { limit, offset, total } }` envelope.** Rejected for this
  endpoint. There's no offset, and `total` costs a count per request.
- **Clamping an out-of-range `limit`.** Rejected because it hides client bugs.
- **Index `(status, category_id, created_at DESC, id DESC)`.** Rejected for E4. With
  `category_id` second, the unfiltered feed can't use the index for ordering, so Postgres would
  read and sort every active listing.
- **A partial index `(created_at DESC, id DESC) INCLUDE (category_id) WHERE status = 'active'`.**
  It's smaller, but the planner only uses it when it can prove `status = 'active'` from the
  query, which is fragile with bound parameters. Rejected.

## Consequences

- No page numbers, no "jump to page N", and no total count. An infinite feed needs none of
  them; if a future screen does, it needs its own endpoint.
- **E5** adds its filter by putting `category` in the cursor's `f` and adding one
  `AND category_id = :id` clause. If measurements show a narrow category is slow (the index
  walk has to skip many non-matching entries), E5 adds a second index,
  `(status, category_id, created_at DESC, id DESC)`.
- The mock API (`frontend/src/mocks/handlers.ts`) implements the same cursor format so E4.3
  can test invalid-cursor recovery. If the backend's format changes, the mock should follow,
  though clients can't tell the difference.
- `GET /listings/mine` stays a bare array. A seller's own listings are few. If that changes,
  it should adopt this same scheme.
- **Open for E4.4: thumbnails.** Cover images are the full 1600px uploads from E2.5, shown in
  small cards. E4.4 measures time to first paint and image bytes for the first two pages on a
  real phone, with realistic seed data. If the numbers are bad, the options are:
  - generating thumbnails at upload time, which changes E2.3's pipeline and adds a column;
  - Supabase image transformations, if the plan includes them;
  - accepting it as a documented limitation.

  The measurement and decision get added here as an addendum, or in a new ADR if the decision
  changes this one.
