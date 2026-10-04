"""Supabase Storage for listing photos (ADR 0009)."""

from app.config import settings

LISTING_PHOTOS_BUCKET = "listing-photos"


def public_url(storage_path: str) -> str:
    """The public URL of a file in the listing photos bucket (the bucket is public-read)."""
    base = settings.supabase_url.rstrip("/")
    return f"{base}/storage/v1/object/public/{LISTING_PHOTOS_BUCKET}/{storage_path}"
