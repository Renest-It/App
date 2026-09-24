# 0007 — Authentication and Identity

## Status

Accepted (token verification: E1.4 / SCRUM-27; user provisioning: E1.5 / SCRUM-28).

## Context

ReNest is limited to the Creighton community (ADR 0001). Users sign up and log in through
Supabase Auth directly from the browser, which returns a signed access token (a JWT). All data
goes through FastAPI (ADR 0006), so FastAPI needs to decide, for every request, whether the
token can be trusted and whether its user is allowed in.

The sign-up form (E1.3) already checks for an `@creighton.edu` address, but that check exists
for user experience only. Anyone can call Supabase's API directly and get a valid token for a
Gmail address, so the frontend can't be the gate.

We checked the live Supabase project before building this (2026-09-24):

- Its JWKS endpoint (`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`) publishes one **ES256**
  (P-256) public key.
- Real access tokens are signed with that key (`alg: ES256`, matching `kid`). They carry
  `aud: "authenticated"`, `iss: "<SUPABASE_URL>/auth/v1"`, a 1-hour `exp`, a top-level `email`,
  and `user_metadata.email_verified`.

## Decision

### Where the rules are enforced

**FastAPI enforces who is allowed in**, in `backend/app/auth.py` → `verify_token(token)`. Client
checks are conveniences only.

### How tokens are verified

- **Signature:** ES256 only, checked against the project's published JWKS and chosen by the
  token's `kid`. HS256, `none`, and every other algorithm are rejected. That blocks
  algorithm-confusion attacks (e.g. HMAC-signing with the downloadable public key). There's no
  shared JWT secret, so there's nothing secret to store on Render.
- **Keys are cached** in memory for 10 minutes. A token with an unknown `kid` triggers one
  refetch (at most every 30 seconds), which handles Supabase key rotation without a restart and
  without letting made-up key IDs hammer the endpoint.
- **Claims:** `exp` (with 30 seconds of clock-skew leeway), `aud = authenticated`,
  `iss = <SUPABASE_URL>/auth/v1` (so a token from any other Supabase project is rejected), and
  `sub`, `email`, and `exp` must be present.

### The domain rule

The email is trimmed and lowercased, and the part after the last `@` must **exactly equal** a
domain in `ALLOWED_EMAIL_DOMAINS`, currently only `creighton.edu`. This is an exact domain
comparison, not a suffix check, so:

- `someone@notcreighton.edu`, `someone@creighton.edu.evil.com`, and
  `someone@alumni.creighton.edu` are all refused.
- **Alumni and employee addresses directly on `@creighton.edu` are allowed**, consistent with
  ADR 0001's accepted MVP limitation. If Creighton issues a separate alumni domain, allowing it is
  a one-entry change to `ALLOWED_EMAIL_DOMAINS`, and it should be recorded here.

### Email confirmation, and the dependency on a Supabase setting

`verify_token` refuses tokens whose `user_metadata.email_verified` isn't `true`. **But
`user_metadata` can be edited by the signed-in user** (through Supabase's `updateUser`), so this
claim is defense in depth, not proof.

**The real guarantee is the Supabase project setting "Confirm email" (Authentication → Sign In /
Providers → Email), which is on.** With it on, Supabase issues no session, and so no token, to
a user who hasn't confirmed their address (E1.2, the `auth-email-verification` spec).
**Turning that setting off would silently weaken identity checks, and must not be done without
revisiting this ADR.**

### Error meanings

`verify_token` raises named errors. `register_auth_error_handlers(app)` (called in
`app/main.py`) turns them into JSON responses whose body is exactly `{"code", "message"}`:

| Status | `code` | Meaning | Frontend should |
|---|---|---|---|
| 401 (+ `WWW-Authenticate: Bearer`) | `invalid_token` | The token can't be trusted: missing, malformed, badly signed, expired, or wrong audience/issuer | Send the user to log in |
| 403 | `wrong_domain` | Valid token, but not an allowed Creighton address | Explain ReNest is Creighton-only |
| 403 | `email_not_confirmed` | Valid token, but the email isn't confirmed | Ask them to confirm their email |
| 503 (+ `Retry-After`) | `auth_unavailable` | Supabase's keys couldn't be fetched, so the token can't be checked right now | Retry. **Don't** log the user out. |

When a token is both on the wrong domain and unconfirmed, the response is `wrong_domain`.
Response bodies never include the token or library error text.

### User provisioning (E1.5 / SCRUM-28)

**The backend creates a user's row on their first authenticated request**, inside the real
`get_current_user()` dependency (`app/dependencies.py` → `app/users.py`), not with a database
trigger.

- **Order:** `verify_token` runs first. The domain rule, the confirmed-email check, and
  signature/expiry are all enforced **before any row is read or created**, so a rejected token
  never produces a `users` row.
- **IDs:** `users.id` is the Supabase user ID (the token's `sub`). The database no longer
  generates ids; the E1.5 migration dropped the `gen_random_uuid()` default and removed the fake E0
  user `test@creighton.edu` along with its listings.
- **Lookup, then insert:** an existing user costs one primary-key lookup. A first request runs
  `INSERT … ON CONFLICT (id) DO NOTHING` and then re-reads the row. The explicit `(id)` target
  means two simultaneous first requests from the same user both succeed with exactly one row, and
  **only** that case is ignored.
- **Stored values:** the email is lowercased. `display_name` comes from the sign-up form's metadata
  (`user_metadata.display_name`), falling back to the part of the email before the `@`.
- **Captured once:** later requests reuse the row unchanged, so a changed Supabase display name
  isn't copied over. That's until profile editing exists.
- **No stub or dev fallback:** the E0 stub is deleted. There is no setting, flag, or environment in
  which `get_current_user` returns a user without a verified token.

**Email conflicts are an explicit error, never fixed automatically.** If a first-time user's email
already belongs to a row with a *different* id (typically an admin deleted their Supabase account
and they signed up again, getting a new Supabase id), the insert hits the `users_email_key` unique
constraint. The backend then:

- returns **409** `{"code": "email_conflict", "message": "An older account with this email exists. Contact the ReNest team."}`
- logs a warning with both user ids (never the token)
- creates, re-points, and deletes nothing

Account deletion in the dashboard is usually a deliberate removal, for example of someone who broke
the rules. Automatically re-pointing would hand their old listings back the moment they
re-register, and it means changing a primary key that listings reference. Automatically deleting
would destroy data on sign-up.

**Manual fix (admin, in the Supabase SQL editor), for a legitimate case.** Use the ids from the
log. Either:

- **Remove the old account** (and its listings):
  ```sql
  BEGIN;
  DELETE FROM listings WHERE seller_id = '<old_id>';
  DELETE FROM users WHERE id = '<old_id>';
  COMMIT;
  ```
- **Or keep their history** by moving it to the new id: create the new row, move the listings,
  then delete the old row, all in one transaction:
  ```sql
  BEGIN;
  -- Free the email on the old row, copy the row to the new id, move listings, remove the old row.
  UPDATE users SET email = '<old_id>@moved.invalid' WHERE id = '<old_id>';
  INSERT INTO users (id, email, display_name, created_at)
    SELECT '<new_id>', '<email>', display_name, created_at FROM users WHERE id = '<old_id>';
  UPDATE listings SET seller_id = '<new_id>' WHERE seller_id = '<old_id>';
  DELETE FROM users WHERE id = '<old_id>';
  COMMIT;
  ```
  Afterward the person's next request finds their row under the new id.

**Why first-request provisioning, not a trigger on `auth.users`:** it keeps all identity logic in
FastAPI next to the domain rule, doesn't couple the schema to Supabase's internal `auth` schema,
and is covered by the backend test suite (real Postgres, including the concurrency race). The
cost is one primary-key lookup per authenticated request, which is negligible.

## Alternatives Considered

**Trusting the frontend's domain check.** Rejected: it can be bypassed by calling Supabase's API
directly.

**Verifying with the legacy shared JWT secret (HS256).** Rejected: the project signs with
asymmetric ES256 keys. Supporting both would widen the attack surface (algorithm confusion) and
require storing a secret for no benefit.

**Asking Supabase to validate every token** (calling its `/auth/v1/user` endpoint per request).
Rejected: it adds a network round trip and a hard runtime dependency on Supabase to every API
call. Local verification against cached public keys is standard and much faster.

**`endswith("creighton.edu")` / suffix matching.** Rejected: it accepts `notcreighton.edu`
(and, without the `@`, lookalike domains). An exact comparison against an allow-list is both
safer and easier to extend.

**Enforcing the domain inside Supabase instead** (a "before user created" auth hook). Not
chosen for now: FastAPI must check tokens anyway, so this is the single place to keep the rule.
A hook could be added later as an extra layer that stops non-Creighton accounts from being
created at all.

## Consequences

- Every protected API route will depend on `verify_token` (through E1.5's `get_current_user()`).
  The domain rule lives in one constant.
- The backend needs outbound HTTPS access to `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`, but
  only about every 10 minutes. A short Supabase outage with warm caches has no effect; with cold
  caches, requests get 503, not a logout.
- The "Confirm email" Supabase setting becomes part of the security model (see above).
- Tests sign their own tokens with a locally generated key and a fake JWKS, so they run offline.
- **Revisit if** Supabase changes signing algorithms, Creighton adopts SSO (ADR 0001), or the
  allowed domains change.
