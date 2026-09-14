# API Conventions

These conventions apply to every endpoint in the FastAPI backend. They exist
so the frontend can write one client layer instead of special-casing each
endpoint, and so a developer reading any route already knows its shape
before opening the file. See [0006 — Authorization Lives in
FastAPI](decisions/0006-authorization-in-fastapi.md) for where permission
checks live, and [0005 — Modular Monolith](decisions/0005-modular-monolith.md)
for how routes are organized.

## Resource naming

Resources are plural nouns, following standard REST collection/member
shape:

| Action | Route |
|---|---|
| List | `GET /listings` |
| Create | `POST /listings` |
| Read one | `GET /listings/{id}` |
| Update | `PATCH /listings/{id}` |
| Delete | `DELETE /listings/{id}` |

Same pattern for every resource: `/categories`, `/categories/{id}`, `/users`,
`/users/{id}`, and so on. Nested resources follow the same rule, e.g.
`/listings/{id}/images`.

## Status codes

| Code | Meaning | Used for |
|---|---|---|
| `200` | OK | Successful `GET`, `PATCH` |
| `201` | Created | Successful `POST` that creates a resource |
| `204` | No Content | Successful `DELETE` |
| `403` | Forbidden | Request is authenticated but the actor doesn't own/can't act on this resource ("not yours") |
| `404` | Not Found | Resource doesn't exist (also used instead of `403` when a resource's existence itself shouldn't be revealed to a non-owner) |
| `422` | Unprocessable Entity | Request body fails validation |

`401` is reserved for missing/invalid authentication, distinct from `403`
(authenticated, but not permitted).

## Error envelope

Every endpoint that returns an error uses the same envelope shape, so the
frontend has one error handler for the whole API:

```json
{
  "error": {
    "code": "not_owner",
    "message": "You do not have permission to modify this listing.",
    "details": null
  }
}
```

- `code` — a short, stable, machine-readable string (`snake_case`) the
  frontend can switch on. Not the HTTP status text.
- `message` — a human-readable message, safe to show directly to a user.
- `details` — optional structured data for the error case, e.g. per-field
  validation errors on a `422`. `null` when there's nothing more to add.

## Pagination

Decided now, even though E0 ships no paginated endpoint, because retrofitting
a bare array into a paginated envelope later breaks every existing caller.
Any endpoint that returns a collection uses this shape from day one:

```json
{
  "items": [ ... ],
  "page": {
    "limit": 20,
    "offset": 0,
    "total": 137
  }
}
```

- `items` — the array of resources for this page.
- `page.limit` — page size requested (query param `?limit=`, default TBD per
  endpoint).
- `page.offset` — offset requested (query param `?offset=`).
- `page.total` — total count of matching items across all pages.

An endpoint that has no need for pagination in E0 still returns this
envelope, with all items in a single page (`limit`/`offset` covering the
full result, `total` equal to `items.length`) — not a bare array. The
frontend can always assume this shape for any collection response.

## Case convention

`snake_case` end to end: request bodies, response bodies, and query
parameters from the API are all `snake_case`, and the TypeScript interfaces
in the frontend mirror that exactly (`created_at`, not `createdAt`). No
`camelCase`/`snake_case` translation layer exists at the API boundary — see
[0004 — Monorepo](decisions/0004-monorepo.md) for why frontend and backend
are close enough that this mapping layer would be pure overhead for no
functional gain.
