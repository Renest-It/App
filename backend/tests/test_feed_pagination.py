"""E4.2: GET /listings serves the feed one page at a time with keyset cursors (ADR 0011,
docs/api/listings.md → GET /listings).

Listings are inserted directly with explicit created_at values, so the feed order is known.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Category, Listing, ListingImage, User
from app.pagination import encode_cursor

pytestmark = pytest.mark.requires_db

NEWEST = datetime(2026, 9, 26, 12, 0, 0, 500000, tzinfo=timezone.utc)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def viewer(make_token):
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='viewer@creighton.edu')}"}


@pytest.fixture
def seller_id(db_session):
    seller = User(id=uuid.uuid4(), email="seller@creighton.edu", display_name="Seller")
    db_session.add(seller)
    db_session.commit()
    return seller.id


@pytest.fixture
def category_id(db_session):
    return db_session.query(Category.id).order_by(Category.id).first()[0]


@pytest.fixture
def add(db_session, seller_id, category_id):
    """Insert one listing and return its id as a string."""

    def _add(created_at: datetime, status: str = "active", listing_id: uuid.UUID | None = None) -> str:
        listing = Listing(
            id=listing_id or uuid.uuid4(),
            title="Desk lamp",
            price_cents=1500,
            category_id=category_id,
            seller_id=seller_id,
            status=status,
            created_at=created_at,
        )
        db_session.add(listing)
        db_session.commit()
        return str(listing.id)

    return _add


@pytest.fixture
def seed(add):
    """Insert `count` active listings one minute apart, newest first, and return their ids in
    feed order."""

    def _seed(count: int) -> list[str]:
        return [add(NEWEST - timedelta(minutes=i)) for i in range(count)]

    return _seed


def get_page(client, headers, **params):
    r = client.get("/listings", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def walk(client, headers, **params) -> list[list[str]]:
    """Follow next_cursor from the first page to the end; return each page's ids."""
    pages, cursor = [], None
    while True:
        page = get_page(client, headers, **params, **({"cursor": cursor} if cursor else {}))
        pages.append([item["id"] for item in page["items"]])
        cursor = page["next_cursor"]
        if cursor is None:
            return pages
        assert page["items"], "a non-null next_cursor led to an empty page"


def test_full_walk_returns_every_active_listing_once(client, viewer, seed):
    expected = seed(45)
    pages = walk(client, viewer)
    assert [len(p) for p in pages] == [20, 20, 5]
    assert [i for p in pages for i in p] == expected


def test_exactly_full_last_page_needs_no_extra_request(client, viewer, seed):
    seed(40)
    assert [len(p) for p in walk(client, viewer)] == [20, 20]


def test_last_page_has_a_null_cursor(client, viewer, seed):
    seed(3)
    page = get_page(client, viewer)
    assert len(page["items"]) == 3
    assert page["next_cursor"] is None


def test_empty_feed(client, viewer):
    assert get_page(client, viewer) == {"items": [], "next_cursor": None}


def test_listing_created_mid_walk_causes_no_duplicate_or_skip(client, viewer, seed, add):
    expected = seed(30)
    first = get_page(client, viewer)
    new_id = add(datetime.now(timezone.utc))
    rest = get_page(client, viewer, cursor=first["next_cursor"])

    ids = [i["id"] for i in first["items"]] + [i["id"] for i in rest["items"]]
    assert ids == expected
    assert new_id not in ids
    assert rest["next_cursor"] is None


def test_tied_created_at_across_a_page_boundary(client, viewer, add):
    # 19 newer listings, then two sharing one created_at at positions 20 and 21, so the page
    # boundary (limit 20) falls between them. Ties are ordered by id, descending.
    for i in range(19):
        add(NEWEST - timedelta(minutes=i))
    tie_at = NEWEST - timedelta(minutes=30)
    low = add(tie_at, listing_id=uuid.UUID("00000000-0000-4000-8000-000000000001"))
    high = add(tie_at, listing_id=uuid.UUID("ffffffff-ffff-4fff-bfff-ffffffffffff"))
    add(NEWEST - timedelta(minutes=40))

    pages = walk(client, viewer)
    assert pages[0][-1] == high
    assert pages[1][0] == low
    flat = [i for p in pages for i in p]
    assert flat.count(high) == 1 and flat.count(low) == 1
    assert len(flat) == 22


def test_drafts_and_sold_listings_appear_on_no_page(client, viewer, add):
    active = []
    for i in range(30):
        created = NEWEST - timedelta(minutes=i)
        if i % 3 == 0:
            add(created, status="draft")
        elif i % 3 == 1:
            add(created, status="sold")
        active.append(add(created - timedelta(seconds=1)))

    pages = walk(client, viewer)
    assert [i for p in pages for i in p] == active


def test_default_and_maximum_page_size(client, viewer, seed):
    seed(55)
    assert len(get_page(client, viewer)["items"]) == 20
    assert len(get_page(client, viewer, limit=50)["items"]) == 50


def test_small_page_size(client, viewer, seed):
    expected = seed(5)
    pages = walk(client, viewer, limit=2)
    assert pages == [expected[0:2], expected[2:4], expected[4:5]]


@pytest.mark.parametrize("limit", ["0", "51", "abc", "-1", "2.5", ""])
def test_out_of_range_limit_is_rejected(client, viewer, limit):
    r = client.get("/listings", headers=viewer, params={"limit": limit})
    assert r.status_code == 422
    assert "detail" in r.json()


@pytest.mark.parametrize("cursor", ["not-a-real-cursor", "garbage", ""])
def test_malformed_cursor_is_rejected(client, viewer, seed, cursor):
    seed(3)
    r = client.get("/listings", headers=viewer, params={"cursor": cursor})
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_cursor"
    assert r.json()["message"]


def test_cursor_from_another_filter_is_rejected(client, viewer, seed):
    seed(3)
    cursor = encode_cursor(NEWEST, uuid.uuid4(), {"category": 1})
    r = client.get("/listings", headers=viewer, params={"cursor": cursor})
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_cursor"


def test_items_keep_the_feed_shape(client, viewer, add, db_session, category_id):
    listing_id = add(NEWEST)
    db_session.add(
        ListingImage(
            listing_id=uuid.UUID(listing_id),
            storage_path=f"listings/{listing_id}/cover.jpg",
            position=0,
        )
    )
    db_session.commit()

    [item] = get_page(client, viewer)["items"]
    assert set(item) == {
        "id", "title", "description", "price_cents", "category", "cover_image_url", "created_at",
    }
    assert item["category"]["id"] == category_id
    assert item["cover_image_url"].endswith(f"listings/{listing_id}/cover.jpg")


def test_feed_requires_a_token(client):
    assert client.get("/listings").status_code == 401
