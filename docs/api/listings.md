# Listings API Contract (E2)

This is the agreed shape of every listings endpoint for E2 (SCRUM-30). The frontend builds
against it using the MSW mocks in `frontend/src/mocks/`, and the backend implements it in E2.2
(listing lifecycle) and E2.3 (image uploads). If an endpoint needs to change, change this file
in the same PR, so the mocks, the frontend, and the backend never drift apart.

General rules come from [API Conventions](../api-conventions.md). Where that document and the
code already on `main` disagree, this contract follows `main` so nothing already merged breaks
(see [Differences from API Conventions](#differences-from-api-conventions)). The storage and
lifecycle decisions are recorded in [ADR 0009](../decisions/0009-listing-drafts-and-photo-storage.md).

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
- [The publish flow, end to end](#the-publish-flow-end-to-end)
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

**Owner-only actions.** The image and publish endpoints only work for the listing's seller.
For someone else's **active or sold** listing, they return `403 not_owner`.

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

> **Transition note:** On `main` today, this endpoint creates an `active` listing, and
> `NewListingPage` depends on that. It switches to creating drafts in **E2.2**, together with
> the publish endpoint, so listings never become impossible to publish in between.

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
| `403` | `not_owner` | Someone else's active or sold listing |
| `404` | `listing_not_found` | No such listing, or someone else's draft |
| `409` | `listing_not_draft` | The listing is already published (photos can only be added to drafts in E2) |
| `422` | `unsupported_content_type` | `content_type` isn't jpeg, png, or webp |

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
| `403` | `not_owner` | Someone else's active or sold listing |
| `404` | `listing_not_found` | No such listing, or someone else's draft |
| `409` | `listing_not_draft` | The listing is already published |
| `409` | `position_taken` | A *different* photo already has this position |
| `422` | *(FastAPI `detail`)* | `position` outside 0–5, or a missing field |
| `422` | `invalid_storage_path` | `storage_path` isn't under `listings/{id}/` for this listing |

## `POST /listings/{id}/publish`

Makes a draft **active**, so it appears in `GET /listings`. There's no request body.

**Response: `200 OK`**: the published listing, in the same shape as
[`GET /listings/{id}`](#get-listingsid), with `"status": "active"`.

| Status | `code` | When |
|---|---|---|
| `200` | — | Published |
| `403` | `not_owner` | Someone else's active or sold listing |
| `404` | `listing_not_found` | No such listing, or someone else's draft |
| `409` | `already_published` | The listing's status is already `active` or `sold` |
| `422` | `no_images` | The draft has no photos |

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

## Differences from API Conventions

[API Conventions](../api-conventions.md) describes two things that the code on `main`
doesn't do yet. This contract follows `main`, so E2 doesn't break merged E1 work:

| API Conventions says | `main` does, and this contract follows | Why not change it in E2.1 |
|---|---|---|
| Errors are wrapped: `{"error": {"code", "message", "details"}}` | Flat `{"code", "message"}` (auth and user errors) | `frontend/src/api/client.ts` reads `body.code` at the top level to detect auth failures (E1.6) |
| Collections use `{"items": [...], "page": {...}}` | `GET /listings` returns a bare array | `ListPage` and `getListings()` expect an array |

Whether to align the code with the conventions (or the reverse) is a team decision for a
separate ticket.
