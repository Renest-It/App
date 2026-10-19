# Listings API Contract (E2–E3)

This is the agreed shape of every listings endpoint for E2 (SCRUM-30) and E3 (SCRUM-40). The
frontend builds against it using the MSW mocks in `frontend/src/mocks/`, and the backend
implements it in E2.2 (listing lifecycle), E2.3 (image uploads), E3.2 (edit, delete, sold), and
E3.3 (My Listings and photo editing). If an endpoint needs to change, change this file
in the same PR, so the mocks, the frontend, and the backend never drift apart.

General rules come from [API Conventions](../api-conventions.md). Where that document and the
code already on `main` disagree, this contract follows `main` so nothing already merged breaks
(see [Differences from API Conventions](#differences-from-api-conventions)). The storage and
lifecycle decisions are recorded in [ADR 0009](../decisions/0009-listing-drafts-and-photo-storage.md),
and E3's listing management decisions in [ADR 0010](../decisions/0010-listing-management.md).

## Contents

- [Common rules](#common-rules)
- [Validation rules](#validation-rules)
- [Shared shapes](#shared-shapes)
- Endpoints:
  [`POST /listings`](#post-listings) ·
  [`POST /listings/{id}/images/upload-url`](#post-listingsidimagesupload-url) ·
  [`POST /listings/{id}/images`](#post-listingsidimages) ·
  [`POST /listings/{id}/publish`](#post-listingsidpublish) ·
  [`GET /listings/{id}`](#get-listingsid) ·
  [`GET /listings`](#get-listings)
- E3 endpoints:
  [`PATCH /listings/{id}`](#patch-listingsid) ·
  [`DELETE /listings/{id}`](#delete-listingsid) ·
  [`POST /listings/{id}/sold`](#post-listingsidsold) ·
  [`POST /listings/{id}/unsold`](#post-listingsidunsold) ·
  [`GET /listings/mine`](#get-listingsmine) ·
  [`DELETE /listings/{id}/images/{image_id}`](#delete-listingsidimagesimage_id)
- [The publish flow, end to end](#the-publish-flow-end-to-end)
- [Editing photos on a published listing](#editing-photos-on-a-published-listing)
- [Differences from API Conventions](#differences-from-api-conventions)

## Common rules

**Authentication.** Every endpoint requires `Authorization: Bearer <Supabase access token>`.
Failures are handled by the shared auth code (ADR 0007) and aren't repeated per endpoint below:

| Status | `code` | When |
|---|---|---|
| `401` | `invalid_token` | Missing, malformed, or expired token |
| `403` | `wrong_domain`, `email_not_confirmed` | Valid token, but the user isn't allowed in |
| `409` | `email_conflict` | Account conflict during first-request provisioning |
| `503` | `auth_unavailable` | Supabase signing keys couldn't be fetched |

**Error body.** Errors this contract defines use the same flat shape the auth errors already use:

```json
{ "code": "listing_not_found", "message": "Listing not found." }
```

`code` is stable and `snake_case`, so the frontend switches on it. `message` is safe to show
to a user.

Request bodies that fail Pydantic validation (wrong types, a title that's too long, and so
on) return FastAPI's default `422` body, `{"detail": [ ... ]}`, with one entry per invalid
field. The frontend validates with the same rules first, so users should rarely see these.

**Hiding other people's drafts.** A draft exists only for its seller. When anyone else sends
a request about a draft (read it, get an upload URL, add an image, publish it), the response
is `404 listing_not_found`, exactly as if the listing didn't exist. The same applies to a
malformed or unknown `{id}`. The API never reveals that someone else's draft exists
(API Conventions: 404 instead of 403).

**Owner-only actions return 404, never 403.** Every endpoint that changes a listing (publish,
the image endpoints, and all of E3's: edit, delete, sold, unsold, delete photo) only works for
the listing's seller. For anyone else, they return `404 listing_not_found`, whatever the
listing's status, exactly as if it didn't exist. A `403` would confirm that the ID is real,
which lets someone probe for valid IDs. The backend enforces this in one place, the
`get_owned_listing()` dependency, so a new endpoint can't forget the check (ADR 0010).

**Case.** `snake_case` everywhere. Timestamps are ISO 8601 strings with a timezone.

## Validation rules

The frontend form and the backend enforce the same rules.

| Field | Rule |
|---|---|
| `title` | Required. Trimmed, then **3–80 characters**. |
| `description` | Optional. Trimmed, then **up to 2,000 characters**. Empty after trimming is stored as `null`. |
| `price_cents` | Required integer, **0 to 1,000,000** ($0–$10,000). `0` is allowed and displays as **"Free"**. |
| `category_id` | **Required**, and must be an existing category (`GET /categories`). |
| Photos | **1–6 photos to publish.** Each is jpeg, png, or webp, **5 MB at most** (enforced by the storage bucket). |

## Shared shapes

```ts
type ListingStatus = "draft" | "active" | "sold";

// One photo, as returned to clients.
interface ListingImage {
  id: string;            // uuid
  position: number;      // 0–5; position 0 is the cover photo
  url: string;           // public URL of the stored file
}

// The seller as shown on a listing. NEVER includes email (see GET /listings/{id}).
interface Seller {
  id: string;            // uuid
  display_name: string | null;
}
```

**Image URLs.** Photos live in the `listing-photos` Supabase Storage bucket, at
`listings/{listing_id}/{uuid}.{ext}`, where `{ext}` is `jpg`, `png`, or `webp`. That path is the
`storage_path`. The public URL is:

```
{SUPABASE_URL}/storage/v1/object/public/listing-photos/{storage_path}
```

The API always returns the full `url`. Clients never build it themselves.

---

## `POST /listings`

Creates a **draft** listing owned by the current user. Drafts never appear in `GET /listings`.

**Request**

```json
{
  "title": "IKEA desk lamp",
  "description": "Works great, bulb included.",
  "price_cents": 1500,
  "category_id": 3
}
```

**Response: `201 Created`**

```json
{
  "id": "6f1c…",
  "title": "IKEA desk lamp",
  "description": "Works great, bulb included.",
  "price_cents": 1500,
  "category_id": 3,
  "status": "draft",
  "created_at": "2026-10-01T14:03:00Z"
}
```

| Status | `code` | When |
|---|---|---|
| `201` | — | Draft created |
| `422` | *(FastAPI `detail`)* | Body fails the [validation rules](#validation-rules) |
| `422` | `unknown_category` | `category_id` doesn't exist |

## `POST /listings/{id}/images/upload-url`

Returns a short-lived signed URL the browser uses to upload **one** photo straight to Supabase
Storage. The server picks the path, so clients can't write anywhere else. The seller calls it
once per photo.

**Request**

```json
{ "content_type": "image/jpeg" }
```

`content_type` must be `image/jpeg`, `image/png`, or `image/webp`. It determines the file
extension (`jpg`, `png`, `webp`).

**Response: `200 OK`**

```json
{
  "upload_url": "https://<project>.supabase.co/storage/v1/object/upload/sign/listing-photos/listings/6f1c…/0b9e….jpg?token=…",
  "storage_path": "listings/6f1c…/0b9e….jpg",
  "expires_in": 7200
}
```

- To upload, send an HTTP `PUT` to `upload_url` with the file bytes as the body and the same
  `Content-Type` header. The bucket rejects files over 5 MB and other file types.
- Keep `storage_path`: the next call needs it.
- `expires_in` is in seconds. If it runs out, ask for a new URL.

| Status | `code` | When |
|---|---|---|
| `200` | — | URL issued |
| `404` | `listing_not_found` | No such listing, or someone else's listing |
| `409` | `listing_not_draft` | The listing is already published (photos can only be added to drafts in E2). **Changes in E3.3**, see below. |
| `422` | `unsupported_content_type` | `content_type` isn't jpeg, png, or webp |
| `503` | `storage_unavailable` | Supabase Storage couldn't be reached, or the backend's storage key isn't configured. Retry shortly. |

**Changing in E3.3: "draft only" becomes "seller and not sold".** So sellers can add photos to
a listing they've already published, this endpoint will accept any listing that isn't sold.
For a sold listing it returns `409 listing_sold` (`listing_not_draft` goes away). Every other
check stays exactly as it is: only the seller can call it, and the server picks the path inside
this listing's own folder.

## `POST /listings/{id}/images`

Records a photo that was uploaded to `storage_path`, at a position in the listing.

**Request**

```json
{ "storage_path": "listings/6f1c…/0b9e….jpg", "position": 0 }
```

**Response: `201 Created`** (or `200 OK` for an identical retry; see below)

```json
{ "id": "a2d4…", "position": 0, "url": "https://…/listing-photos/listings/6f1c…/0b9e….jpg" }
```

- `position` is 0-based and runs from `0` to `5`. Position `0` is the cover photo. Two photos
  in a listing never share a position (the database enforces this).
- **Retries are safe.** If the same `storage_path` is already recorded at the same `position`,
  the response is `200` with the existing image and nothing new is created. This is what lets
  a publish that fails partway (for example, after going offline) be retried without creating
  duplicates.

| Status | `code` | When |
|---|---|---|
| `201` | — | Image recorded |
| `200` | — | Identical retry, returning the existing image |
| `404` | `listing_not_found` | No such listing, or someone else's listing |
| `409` | `listing_not_draft` | The listing is already published. **Changes in E3.3**, see below. |
| `409` | `position_taken` | A *different* photo already has this position, or this photo is already recorded at a different position |
| `422` | *(FastAPI `detail`)* | `position` outside 0–5, or a missing field |
| `422` | `invalid_storage_path` | `storage_path` isn't exactly `listings/{id}/{uuid}.{ext}` for this listing |
| `422` | `upload_not_found` | Nothing has been uploaded at `storage_path` yet |
| `503` | `storage_unavailable` | Supabase Storage couldn't be reached to check the upload, or the backend's storage key isn't configured. Retry shortly. |

**Changing in E3.3: "draft only" becomes "seller and not sold".** So sellers can add photos to
a listing they've already published, this endpoint will accept any listing that isn't sold.
For a sold listing it returns `409 listing_sold` (`listing_not_draft` goes away). Every other
check stays exactly as it is: the path must be inside this listing's own folder, the file must
exist in storage before the row is written, and positions 0–5 still cap a listing at 6 photos.

## `POST /listings/{id}/publish`

Makes a draft **active**, so it appears in `GET /listings`. There's no request body.

**Response: `200 OK`**: the published listing, in the same shape as
[`GET /listings/{id}`](#get-listingsid), with `"status": "active"`.

| Status | `code` | When |
|---|---|---|
| `200` | — | Published |
| `404` | `listing_not_found` | No such listing, or someone else's listing |
| `409` | `already_published` | The listing's status is already `active` or `sold` |
| `422` | `no_images` | The draft has no photos |
| `422` | `invalid_listing` | The draft no longer passes the [validation rules](#validation-rules) (e.g. its category was deleted). `message` says what to fix. |

Publishing re-checks every validation rule before switching the status.

## `GET /listings/{id}`

One listing, with its photos in order and its seller.

- `active` and `sold` listings: any logged-in user can view them.
- `draft` listings: only the seller can view them. Everyone else gets `404`.

**Response: `200 OK`**

```json
{
  "id": "6f1c…",
  "title": "IKEA desk lamp",
  "description": "Works great, bulb included.",
  "price_cents": 1500,
  "status": "active",
  "category": { "id": 3, "name": "Electronics", "slug": "electronics" },
  "seller": { "id": "9a7e…", "display_name": "Jane" },
  "images": [
    { "id": "a2d4…", "position": 0, "url": "https://…/0b9e….jpg" },
    { "id": "c81f…", "position": 1, "url": "https://…/51aa….webp" }
  ],
  "created_at": "2026-10-01T14:03:00Z"
}
```

- `images` is sorted by `position`, ascending.
- `category` is the full object, the same shape as in `GET /listings`.
- **`seller` contains `id` and `display_name` only. The seller's email is never returned**,
  here or on any listings endpoint. It's revealed only through E6's contact button, when
  someone deliberately asks to contact the seller.

| Status | `code` | When |
|---|---|---|
| `200` | — | Found |
| `404` | `listing_not_found` | No such listing, or someone else's draft |

## `GET /listings`

Every **active** listing, newest first. Drafts and sold listings aren't included.

**Response: `200 OK`**: a JSON array (see [Differences](#differences-from-api-conventions)):

```json
[
  {
    "id": "6f1c…",
    "title": "IKEA desk lamp",
    "description": "Works great, bulb included.",
    "price_cents": 1500,
    "category": { "id": 3, "name": "Electronics", "slug": "electronics" },
    "cover_image_url": "https://…/0b9e….jpg",
    "created_at": "2026-10-01T14:03:00Z"
  }
]
```

- **New in E2:** `cover_image_url` is the URL of the photo at position `0`. The home cards in
  E2.7 and E4's feed need it.
- `cover_image_url` is `null` when a listing has no photo at position `0` (for example,
  listings created before E2). The UI shows a placeholder.

| Status | `code` | When |
|---|---|---|
| `200` | — | Always, including when the list is empty |

---

## E3 endpoints

These let a seller manage their own listings. All of them are owner-only, so someone else's
listing (or an unknown or malformed ID) is `404 listing_not_found`
([Common rules](#common-rules)). Sold listings are frozen: they can be marked unsold or
deleted, but not edited, and their photos can't change (ADR 0010).

## `PATCH /listings/{id}`

Edits a draft or active listing. Send **only the fields you want to change**: any subset of
`title`, `description`, `price_cents`, and `category_id`. Fields you leave out stay as they are.

**Request**

```json
{ "price_cents": 1200, "description": "Bulb not included anymore." }
```

- Each field follows the same [validation rules](#validation-rules) as `POST /listings`.
- `description: null` (or a description that's empty after trimming) clears it. `title`,
  `price_cents`, and `category_id` can't be `null`.
- An empty body `{}` changes nothing and returns the listing as it is.
- Editing sets `updated_at` but **leaves `created_at` alone**, so an edited listing keeps its
  place in the feed. Edits don't bump a listing to the top (ADR 0010).

**Response: `200 OK`**: the updated listing, in the same shape as
[`GET /listings/{id}`](#get-listingsid).

| Status | `code` | When |
|---|---|---|
| `200` | — | Updated |
| `404` | `listing_not_found` | No such listing, or someone else's listing |
| `409` | `listing_sold` | The listing is sold. Mark it unsold to edit it. |
| `422` | *(FastAPI `detail`)* | A field fails the [validation rules](#validation-rules), or is `null` when it can't be |
| `422` | `unknown_category` | `category_id` doesn't exist |

## `DELETE /listings/{id}`

Permanently deletes a listing, whatever its status, along with its photos. There's no
request body and no undo.

**Response: `204 No Content`**

- The listing's `listing_images` rows are deleted with it (`ON DELETE CASCADE`).
- The backend then tries to remove the listing's storage folder (`listings/{listing_id}/`).
  **That cleanup is best-effort:** if Supabase Storage fails, the error is logged and the
  response is still `204`. Leftover files with a clean database are acceptable; a
  half-deleted listing isn't (ADR 0010).

| Status | `code` | When |
|---|---|---|
| `204` | — | Deleted |
| `404` | `listing_not_found` | No such listing, someone else's listing, or already deleted |

## `POST /listings/{id}/sold`

Marks an **active** listing as sold. It leaves the feed (`GET /listings` only returns active
listings) but is still visible at `GET /listings/{id}` with `"status": "sold"`. There's no
request body.

**Response: `200 OK`**: the listing, in the same shape as [`GET /listings/{id}`](#get-listingsid),
with `"status": "sold"`.

| Status | `code` | When |
|---|---|---|
| `200` | — | Marked sold |
| `404` | `listing_not_found` | No such listing, or someone else's listing |
| `409` | `listing_not_active` | The listing is a draft (publish it first) or already sold |

## `POST /listings/{id}/unsold`

Undoes [`/sold`](#post-listingsidsold): a sold listing becomes **active** again and reappears in
the feed, in its original place (`created_at` doesn't change). There's no request body.

**Response: `200 OK`**: the listing, in the same shape as [`GET /listings/{id}`](#get-listingsid),
with `"status": "active"`.

| Status | `code` | When |
|---|---|---|
| `200` | — | Marked active again |
| `404` | `listing_not_found` | No such listing, or someone else's listing |
| `409` | `listing_not_sold` | The listing isn't sold |

## `GET /listings/mine`

The current user's own listings, newest first (by `created_at`). **This is the only endpoint
that lists drafts**, which makes it how a seller gets back to a draft whose publish failed
partway.

**Query parameters**

| Parameter | Values | Default |
|---|---|---|
| `status` | `active`, `draft`, or `sold` | Omitted: all three |

**Response: `200 OK`**: a JSON array, in the same shape as [`GET /listings`](#get-listings)
plus each listing's `status`:

```json
[
  {
    "id": "6f1c…",
    "title": "IKEA desk lamp",
    "description": "Works great, bulb included.",
    "price_cents": 1500,
    "status": "draft",
    "category": { "id": 3, "name": "Electronics", "slug": "electronics" },
    "cover_image_url": null,
    "created_at": "2026-10-01T14:03:00Z"
  }
]
```

- An empty array, not an error, when you have no listings (or none with that `status`).
- `cover_image_url` is `null` for a listing with no photo at position `0`, which is common
  for drafts.
- **Backend note:** this route must be declared before `GET /listings/{id}`, or `mine` is read
  as a listing ID and returns `404`.

| Status | `code` | When |
|---|---|---|
| `200` | — | Always, including when the list is empty |
| `422` | *(FastAPI `detail`)* | `status` isn't `active`, `draft`, or `sold` |

## `DELETE /listings/{id}/images/{image_id}`

Removes one photo from a draft or active listing. There's no request body.

**Response: `204 No Content`**

- **An active listing always keeps at least 1 photo.** Deleting its last one returns `422`,
  because a published listing with no photos would show a broken card in the feed. A draft
  can go down to 0 photos (publishing already requires at least 1).
- **Positions close up.** The photos after the deleted one move down one position, so they
  stay `0, 1, 2…` with no gaps. Deleting the cover (position `0`) makes the next photo the
  cover. Fetch [`GET /listings/{id}`](#get-listingsid) afterwards for the new order.
- The file is removed from storage on a best-effort basis, like
  [`DELETE /listings/{id}`](#delete-listingsid): a storage failure is logged, and the response
  is still `204`.

| Status | `code` | When |
|---|---|---|
| `204` | — | Deleted |
| `404` | `listing_not_found` | No such listing, or someone else's listing |
| `404` | `image_not_found` | No photo with that `image_id` on this listing (including a malformed ID) |
| `409` | `listing_sold` | The listing is sold, so its photos can't change |
| `422` | `last_photo_required` | It's the only photo on an active listing. Add another first. |

---

## The publish flow, end to end

What the create-listing page (E2.4/E2.5) does after the user clicks **Publish**:

1. `POST /listings` → keep the draft `id`. **On retry, reuse this `id`.** Don't create a
   second draft.
2. For each photo, in order (`position` = 0, 1, 2, …):
   1. `POST /listings/{id}/images/upload-url` with its `content_type`
   2. `PUT` the resized file to `upload_url`
   3. `POST /listings/{id}/images` with `storage_path` and `position`

   Skip any photo that's already recorded. If a step fails, retry that photo from step 1
   (a new upload URL is fine).
3. `POST /listings/{id}/publish` → go to the detail page (`/listings/{id}`).

## Editing photos on a published listing

What the edit page (E3.4) does, once E3.3 relaxes the image endpoints:

- **Add a photo:** the same three steps as the publish flow above (upload URL, `PUT`, record),
  using the next free position, which is the number of photos the listing has now.
- **Remove a photo:** [`DELETE /listings/{id}/images/{image_id}`](#delete-listingsidimagesimage_id),
  then re-fetch the listing, since the positions after it have moved down.
- **Change the details:** [`PATCH /listings/{id}`](#patch-listingsid) with only the changed fields.

None of this works on a sold listing (`409 listing_sold`). Mark it unsold first.

## Differences from API Conventions

[API Conventions](../api-conventions.md) describes two things that the code on `main`
doesn't do yet, plus one rule this contract deliberately does differently. Otherwise it
follows `main`, so E2 and E3 don't break merged work:

| API Conventions says | `main` does, and this contract follows | Why |
|---|---|---|
| Errors are wrapped: `{"error": {"code", "message", "details"}}` | Flat `{"code", "message"}` (auth and user errors) | `frontend/src/api/client.ts` reads `body.code` at the top level to detect auth failures (E1.6) |
| Collections use `{"items": [...], "page": {...}}` | `GET /listings` returns a bare array | `ListPage` and `getListings()` expect an array |
| `403` when the actor doesn't own the resource | `404 listing_not_found` for every owner-only action on someone else's listing (E3.1) | A 403 confirms the listing ID exists. Deliberate, not a gap to close (ADR 0010). |

`GET /listings/mine` returns a bare array too, to match `GET /listings`.

Whether to align the code with the conventions (or the reverse) is a team decision for a
separate ticket.
