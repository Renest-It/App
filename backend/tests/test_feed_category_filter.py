"""E5.1: GET /listings?category=<slug> filters the feed by category, with cursors bound to the
filter they were issued under (spec: feed-category-filter, docs/api/listings.md → GET /listings).

Listings are inserted directly with explicit created_at values, so the feed order is known.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Category, Listing, User

pytestmark = pytest.mark.requires_db

NEWEST = datetime(2026, 9, 26, 12, 0, 0, 500000, tzinfo=timezone.utc)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def viewer(make_token):
    return {
        "Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='viewer@creighton.edu')}"
    }


@pytest.fixture
def seller_id(db_session):
    seller = User(id=uuid.uuid4(), email="seller@creighton.edu", display_name="Seller")
    db_session.add(seller)
    db_session.commit()
    return seller.id


@pytest.fixture
def category_ids(db_session) -> dict[str, int]:
    return {slug: id_ for id_, slug in db_session.query(Category.id, Category.slug)}


@pytest.fixture
def add(db_session, seller_id, category_ids):
    """Insert one listing and return its id as a string."""

    def _add(
        created_at: datetime,
        category: str = "furniture",
        status: str = "active",
        listing_id: uuid.UUID | None = None,
    ) -> str:
        listing = Listing(
            id=listing_id or uuid.uuid4(),
            title="Desk lamp",
            price_cents=1500,
            category_id=category_ids[category],
            seller_id=seller_id,
            status=status,
            created_at=created_at,
        )
        db_session.add(listing)
        db_session.commit()
        return str(listing.id)

    return _add


def get(client, headers, **params):
    return client.get("/listings", headers=headers, params=params)


def get_page(client, headers, **params):
    r = get(client, headers, **params)
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


def assert_error(response, code: str):
    assert response.status_code == 422, response.text
    assert response.json()["code"] == code


# --- Filtering --------------------------------------------------------------------------------


def test_only_the_requested_category_newest_first(client, viewer, add):
    furniture = [add(NEWEST - timedelta(minutes=i * 2), "furniture") for i in range(3)]
    for i in range(3):
        add(NEWEST - timedelta(minutes=i * 2 + 1), "kitchen")
    page = get_page(client, viewer, category="furniture")
    assert [item["id"] for item in page["items"]] == furniture
    assert {item["category"]["slug"] for item in page["items"]} == {"furniture"}
    assert page["next_cursor"] is None


def test_no_filter_returns_every_category(client, viewer, add):
    expected = [
        add(NEWEST - timedelta(minutes=i), slug)
        for i, slug in enumerate(["furniture", "kitchen", "decor"])
    ]
    page = get_page(client, viewer)
    assert [item["id"] for item in page["items"]] == expected


@pytest.mark.parametrize("slug", ["furnture", "", "Furniture"])
def test_unknown_category_is_422(client, viewer, slug):
    assert_error(get(client, viewer, category=slug), "unknown_category")


def test_unknown_category_is_reported_before_a_bad_cursor(client, viewer):
    assert_error(get(client, viewer, category="nope", cursor="garbage"), "unknown_category")


def test_category_with_only_hidden_listings_is_an_empty_page(client, viewer, add):
    add(NEWEST, "decor", status="sold")
    add(NEWEST - timedelta(minutes=1), "decor", status="draft")
    add(NEWEST - timedelta(minutes=2), "kitchen")
    assert get_page(client, viewer, category="decor") == {"items": [], "next_cursor": None}


# --- Pagination ---------------------------------------------------------------------------------


def test_full_filtered_walk_returns_each_listing_once(client, viewer, add):
    # 45 furniture listings interleaved with 45 kitchen ones, so every page boundary of the
    # filtered feed falls between rows the unfiltered feed would also show.
    expected = []
    for i in range(45):
        expected.append(add(NEWEST - timedelta(minutes=i * 2), "furniture"))
        add(NEWEST - timedelta(minutes=i * 2 + 1), "kitchen")
    pages = walk(client, viewer, category="furniture")
    assert [len(p) for p in pages] == [20, 20, 5]
    assert [i for p in pages for i in p] == expected


def test_tied_created_at_across_a_filtered_page_boundary(client, viewer, add):
    for i in range(19):
        add(NEWEST - timedelta(minutes=i), "furniture")
    tie_at = NEWEST - timedelta(minutes=30)
    low = add(tie_at, "furniture", listing_id=uuid.UUID("00000000-0000-4000-8000-000000000001"))
    high = add(tie_at, "furniture", listing_id=uuid.UUID("ffffffff-ffff-4fff-bfff-ffffffffffff"))
    add(tie_at, "kitchen")  # same moment, other category: must not affect the boundary
    add(NEWEST - timedelta(minutes=40), "furniture")

    pages = walk(client, viewer, category="furniture")
    assert pages[0][-1] == high  # ties are ordered by id, descending
    assert pages[1][0] == low
    flat = [i for p in pages for i in p]
    assert len(flat) == len(set(flat)) == 22


def test_hidden_listings_never_appear_on_later_filtered_pages(client, viewer, add):
    shown = [add(NEWEST - timedelta(minutes=i), "furniture") for i in range(25)]
    hidden = [
        add(NEWEST - timedelta(minutes=30 + i), "furniture", status=status)
        for i, status in enumerate(["sold", "draft", "sold", "draft"])
    ]
    shown.append(add(NEWEST - timedelta(minutes=40), "furniture"))
    flat = [i for p in walk(client, viewer, category="furniture") for i in p]
    assert flat == shown
    assert not set(flat) & set(hidden)


# --- Cursors are bound to their filter ------------------------------------------------------


@pytest.fixture
def cursors(client, viewer, add):
    """A next_cursor from the furniture feed and one from the unfiltered feed."""
    for i in range(25):
        add(NEWEST - timedelta(minutes=i * 2), "furniture")
        add(NEWEST - timedelta(minutes=i * 2 + 1), "kitchen")
    return {
        "furniture": get_page(client, viewer, category="furniture")["next_cursor"],
        "unfiltered": get_page(client, viewer)["next_cursor"],
    }


def test_cursor_replayed_under_another_category_is_rejected(client, viewer, cursors):
    assert_error(
        get(client, viewer, category="kitchen", cursor=cursors["furniture"]), "invalid_cursor"
    )


def test_filter_removed_mid_walk_is_rejected(client, viewer, cursors):
    assert_error(get(client, viewer, cursor=cursors["furniture"]), "invalid_cursor")


def test_filter_added_mid_walk_is_rejected(client, viewer, cursors):
    assert_error(
        get(client, viewer, category="furniture", cursor=cursors["unfiltered"]), "invalid_cursor"
    )


def test_cursors_work_under_their_own_filter(client, viewer, cursors):
    assert (
        len(get_page(client, viewer, category="furniture", cursor=cursors["furniture"])["items"])
        == 5
    )
    assert len(get_page(client, viewer, cursor=cursors["unfiltered"])["items"]) == 20
