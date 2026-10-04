# Supabase

Settings for the Supabase project that live outside the backend's Alembic migrations.

| Path | What it is |
|---|---|
| `templates/` | Auth email templates (E1.2) |
| `storage/listing-photos.sql` | The `listing-photos` Storage bucket for listing photos (E2.1, [ADR 0009](../docs/decisions/0009-listing-drafts-and-photo-storage.md)) |

## Setting up the listing photos bucket

1. In the Supabase dashboard, open **SQL Editor** → **New query**.
2. Paste the contents of `storage/listing-photos.sql` and click **Run**.
3. Check it in **Storage** → `listing-photos` → **Edit bucket**:
   - **Public bucket**: on
   - **Restrict file size**: 5 MB
   - **Allowed MIME types**: `image/jpeg`, `image/png`, `image/webp`

The script is safe to run again. If the bucket's settings ever need to change, change the
script and run it again, so the repo stays the source of truth.
