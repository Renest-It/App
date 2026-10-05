"""Supabase Storage for listing photos (ADR 0009)."""

import httpx

from app.config import settings

LISTING_PHOTOS_BUCKET = "listing-photos"

# Supabase's signed upload URLs always last 2 hours; the expiry isn't configurable.
UPLOAD_URL_EXPIRES_IN = 7200

_TIMEOUT = httpx.Timeout(10.0)


class StorageUnavailable(Exception):
    """Supabase Storage didn't answer, or answered with something unexpected."""


def _storage_url(path: str) -> str:
    return f"{settings.supabase_url.rstrip('/')}/storage/v1{path}"


def _service_headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {"Authorization": f"Bearer {key}", "apikey": key}


def public_url(storage_path: str) -> str:
    """The public URL of a file in the listing photos bucket (the bucket is public-read)."""
    return _storage_url(f"/object/public/{LISTING_PHOTOS_BUCKET}/{storage_path}")


def create_signed_upload_url(storage_path: str) -> str:
    """A signed URL the browser can PUT one file to, at exactly `storage_path`."""
    try:
        response = httpx.post(
            _storage_url(f"/object/upload/sign/{LISTING_PHOTOS_BUCKET}/{storage_path}"),
            headers=_service_headers(),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        # Supabase returns the URL relative to /storage/v1, e.g. "/object/upload/sign/...?token=..."
        return _storage_url(response.json()["url"])
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise StorageUnavailable("Could not create a signed upload URL") from e


def object_exists(storage_path: str) -> bool:
    """Whether a file has been uploaded at `storage_path`.

    Goes through the authenticated endpoint rather than the public one so a cached "not found"
    from the CDN can't hide a file that was just uploaded.
    """
    try:
        response = httpx.head(
            _storage_url(f"/object/authenticated/{LISTING_PHOTOS_BUCKET}/{storage_path}"),
            headers=_service_headers(),
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        raise StorageUnavailable("Could not reach storage") from e
    if response.status_code == 200:
        return True
    # Supabase Storage answers a missing object with 400 on some versions and 404 on others.
    if response.status_code in (400, 404):
        return False
    raise StorageUnavailable(f"Unexpected storage response: {response.status_code}")
