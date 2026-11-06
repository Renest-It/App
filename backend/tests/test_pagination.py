"""E4.2: feed cursors encode and decode, and every unusable cursor is 422 invalid_cursor (ADR 0011).

No database: these run without TEST_DATABASE_URL.
"""

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.errors import ApiError
from app.pagination import FeedPosition, decode_cursor, encode_cursor

LISTING_ID = uuid.UUID("3f2b8c1e-9a4d-4e7b-8c2a-1d5e6f7a8b9c")
CREATED_AT = datetime(2026, 9, 26, 12, 0, 0, 123456, tzinfo=timezone.utc)
VALID = {"v": 1, "t": CREATED_AT.isoformat(), "id": str(LISTING_ID), "f": {}}


def cursor_of(payload) -> str:
    raw = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def assert_invalid(raw: str, filters: dict | None = None):
    with pytest.raises(ApiError) as caught:
        decode_cursor(raw, filters)
    assert caught.value.status == 422
    assert caught.value.code == "invalid_cursor"


def test_round_trip_keeps_microseconds():
    cursor = encode_cursor(CREATED_AT, LISTING_ID)
    assert decode_cursor(cursor) == FeedPosition(created_at=CREATED_AT, id=LISTING_ID)


def test_microseconds_are_written_even_when_zero():
    cursor = encode_cursor(CREATED_AT.replace(microsecond=0), LISTING_ID)
    data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    assert data["t"] == "2026-09-26T12:00:00.000000+00:00"


def test_encodes_in_utc():
    central = CREATED_AT.astimezone(timezone(timedelta(hours=-5)))
    cursor = encode_cursor(central, LISTING_ID)
    data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    assert data["t"].endswith("+00:00")
    assert decode_cursor(cursor).created_at == CREATED_AT


def test_cursor_is_url_safe_without_padding():
    cursor = encode_cursor(CREATED_AT, LISTING_ID)
    assert "=" not in cursor and "+" not in cursor and "/" not in cursor


def test_accepts_a_z_suffix():
    position = decode_cursor(cursor_of({**VALID, "t": "2026-09-26T12:00:00.123456Z"}))
    assert position.created_at == CREATED_AT


def test_empty_cursor():
    assert_invalid("")


def test_too_long():
    assert_invalid("A" * 513)


def test_bad_base64():
    assert_invalid("not a cursor!")


def test_bad_json():
    assert_invalid(cursor_of(b"{not json"))


@pytest.mark.parametrize("payload", [[1, 2], "text", 1, None])
def test_json_that_isnt_an_object(payload):
    assert_invalid(cursor_of(payload))


@pytest.mark.parametrize("version", [2, 0, "1", True, None])
def test_unknown_version(version):
    assert_invalid(cursor_of({**VALID, "v": version}))


@pytest.mark.parametrize("field", ["v", "t", "id", "f"])
def test_missing_field(field):
    assert_invalid(cursor_of({k: v for k, v in VALID.items() if k != field}))


@pytest.mark.parametrize("t", [12345, "yesterday", "2026-13-01T00:00:00+00:00"])
def test_bad_timestamp(t):
    assert_invalid(cursor_of({**VALID, "t": t}))


def test_naive_timestamp():
    assert_invalid(cursor_of({**VALID, "t": "2026-09-26T12:00:00.123456"}))


@pytest.mark.parametrize("listing_id", [42, "not-a-uuid", ""])
def test_bad_id(listing_id):
    assert_invalid(cursor_of({**VALID, "id": listing_id}))


@pytest.mark.parametrize("f", [[], "none", None])
def test_filter_that_isnt_an_object(f):
    assert_invalid(cursor_of({**VALID, "f": f}))


def test_cursor_from_another_filter():
    assert_invalid(cursor_of({**VALID, "f": {"category": 3}}))


def test_unfiltered_cursor_under_a_filter():
    assert_invalid(encode_cursor(CREATED_AT, LISTING_ID), {"category": 3})


def test_filtered_cursor_round_trip():
    cursor = encode_cursor(CREATED_AT, LISTING_ID, {"category": 3})
    assert decode_cursor(cursor, {"category": 3}).id == LISTING_ID
