"""Keyset cursors for the home feed (GET /listings, ADR 0011).

A cursor is base64url, without padding, of compact JSON: {"v":1,"t":"<created_at>","id":"<uuid>","f":{}}.
`f` is the filter the cursor was issued under; it stays {} until E5 adds a category filter.
Clients treat cursors as opaque, so the format can change by bumping `v`.
"""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.errors import ApiError

CURSOR_VERSION = 1

# A real cursor is about 120 characters. Anything far longer isn't worth decoding.
MAX_CURSOR_LENGTH = 512


@dataclass(frozen=True)
class FeedPosition:
    """The last listing of a page: the next page starts strictly after it in feed order."""

    created_at: datetime
    id: uuid.UUID


def _invalid_cursor() -> ApiError:
    return ApiError(422, "invalid_cursor", "This page link is no longer valid. Reload the feed.")


def encode_cursor(created_at: datetime, listing_id: uuid.UUID, filters: dict | None = None) -> str:
    payload = {
        "v": CURSOR_VERSION,
        # Microseconds always, even when zero: Postgres stores them, and a rounded boundary
        # would skip or repeat a row.
        "t": created_at.astimezone(timezone.utc).isoformat(timespec="microseconds"),
        "id": str(listing_id),
        "f": filters or {},
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(raw: str, filters: dict | None = None) -> FeedPosition:
    """Read a cursor issued under `filters`. Anything unusable raises 422 invalid_cursor."""
    if not raw or len(raw) > MAX_CURSOR_LENGTH:
        raise _invalid_cursor()
    try:
        padded = raw + "=" * (-len(raw) % 4)
        data = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
        if not isinstance(data, dict):
            raise ValueError("not an object")
        # `type(...) is int` because True == 1 in Python.
        if type(data["v"]) is not int or data["v"] != CURSOR_VERSION:
            raise ValueError("unknown version")
        if not isinstance(data["t"], str) or not isinstance(data["id"], str):
            raise ValueError("wrong field types")
        created_at = datetime.fromisoformat(data["t"])
        # A naive time would be compared in the session's timezone: a silent off-by-hours bug.
        if created_at.tzinfo is None:
            raise ValueError("timestamp has no timezone")
        listing_id = uuid.UUID(data["id"])
        if not isinstance(data["f"], dict) or data["f"] != (filters or {}):
            raise ValueError("issued under a different filter")
    except (ValueError, TypeError, KeyError, binascii.Error) as e:
        raise _invalid_cursor() from e
    return FeedPosition(created_at=created_at, id=listing_id)
