-- Listing photos bucket (E2.1 / SCRUM-32, ADR 0009).
--
-- Run once in the Supabase dashboard: SQL Editor → paste → Run. Safe to re-run: it updates
-- the bucket's settings if it already exists.
--
-- This is NOT an Alembic migration: CI runs migrations against plain Postgres, which has no
-- `storage` schema.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'listing-photos',
  'listing-photos',
  true,                                           -- public read (see ADR 0009's tradeoff)
  5242880,                                        -- 5 MB per file, enforced by the bucket
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- No insert/update/delete policies on storage.objects for this bucket, on purpose: clients
-- can only upload through signed upload URLs that FastAPI issues after checking ownership.
