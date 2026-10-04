# 0009 — Listing Drafts and Photo Storage

## Status

Accepted (E2.1 / SCRUM-32).

## Context

E2 (SCRUM-30) lets a student create a listing with 1–6 photos from their phone or laptop,
publish it, and land on a detail page other students can view. That raises three questions
E0 didn't have to answer:

- **When does a listing exist?** A listing needs its photos before anyone should see it, but
  photos need a listing to attach to. Uploads from a phone can also fail halfway, and a retry
  must not create a second listing.
- **Where do photos live, and who can write them?** All data goes through FastAPI (ADR 0006),
  but routing multi-megabyte image uploads through our Render instance would be slow and
  would use up its memory and bandwidth.
- **Who can read photos?** ReNest is login-only (ADR 0001), but every card in the feed shows
  a photo, so reads have to be fast and cheap.

Phone photos also bring two practical problems: they're large (often 3–8 MB), and they
usually carry GPS coordinates in their EXIF metadata, which would reveal where a student lives.

## Decision

### Listings start as drafts

- `listings.status` allows `draft`, `active`, and `sold`.
- `POST /listings` creates a **draft**. Photos attach to the draft. `POST /listings/{id}/publish`
  makes it `active`, and only succeeds if the draft has at least one photo (`422` otherwise).
- Drafts are visible only to their seller. They never appear in the feed, and every other
  user gets `404` for them, as if they didn't exist.
- On retry, the client reuses the draft's `id`, and recording the same photo at the same
  position twice is a no-op. That makes the whole publish flow safe to retry.
- Photos are stored in a `listing_images` table (`listing_id`, `storage_path`, `position`).
  Deleting a listing deletes its photo rows (`ON DELETE CASCADE`). Two photos in a listing
  can't share a position (unique `(listing_id, position)`), and position `0` is the cover.

### Photos live in a public-read Supabase Storage bucket

- Bucket `listing-photos`, configured by `supabase/storage/listing-photos.sql`:
  - **public read**
  - **jpeg, png, and webp only**
  - **5 MB per file**, enforced by the bucket itself, not by application code, so no client
    can get around it
- Paths are `listings/{listing_id}/{uuid}.{ext}`. The random UUID makes URLs impossible to guess.

### Uploads only through signed URLs that FastAPI issues

- The browser uploads directly to Supabase Storage using a short-lived **signed upload URL**.
- FastAPI issues that URL only after checking that the requester owns the draft, and FastAPI
  picks the path. Clients have no write access to the bucket in any other way (no RLS insert
  policy for `anon` or `authenticated`), so ownership checks stay in FastAPI (ADR 0006).
- FastAPI then records the path in `listing_images` and checks that it belongs to that listing.

### Photos are resized and re-encoded in the browser

- Before uploading, the browser resizes each photo and re-encodes it (E2.5). This keeps
  storage and page weight small, and re-encoding **strips EXIF metadata, including GPS
  location**. It also applies the EXIF orientation first, so portrait photos stay upright.

## Alternatives Considered

**Private bucket with signed read URLs.** This would close the gap described under
Consequences. Rejected for now: every feed card and detail photo would need a signed URL, so
each `GET /listings` would make one signing call per listing (or require us to build a URL
cache). Signed URLs also expire, which breaks browser caching and makes the feed slower.
The images are photos of furniture and textbooks at unguessable URLs, so that cost is too
high for the risk.

**Uploading through FastAPI** (multipart to our API, which then writes to storage). This
would keep all traffic in one place, but every photo would pass through Render twice
(in and out), and the 5 MB limit and file type checks would move into application code.
Rejected because signed uploads keep the same ownership check without the extra traffic.

**Creating the listing and photos in one request** (no draft). Rejected: a single request
carrying 6 photos is exactly what fails on a flaky phone connection, and there's no clean
way to resume it. With drafts, each step can be retried on its own.

**Stripping GPS data on the server.** Rejected: the original file, GPS included, would still
reach our storage before being processed, and we'd need an image-processing step on the
server. Re-encoding in the browser means the GPS data never leaves the phone.

## Consequences

- **Known tradeoff: anyone with a photo's exact URL can view it without logging in.** The
  app is login-only, but the bucket is public-read. The random path makes URLs impossible to
  guess, so the only way to get one is from someone who already had access. If listing photos
  ever become sensitive, revisit this: switch to a private bucket with signed read URLs
  (this ADR's first alternative).
- **Abandoned drafts accumulate** (a user starts publishing, then gives up), along with any
  photos uploaded but never recorded. They're invisible to others and cheap to store. A
  cleanup job can come later if it matters.
- The backend needs Supabase's **service role key** to sign upload URLs (E2.3). It's a
  server-only secret: it goes in Render's environment and never in the frontend.
- The bucket's settings live in a SQL script run in the Supabase dashboard, **not** in an
  Alembic migration. CI runs migrations against plain Postgres, which has no `storage` schema.
- E3 (edit, delete, mark sold) builds on this lifecycle. Until then, photos can only be
  added to drafts.
