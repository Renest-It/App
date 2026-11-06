"""E5.4: GET /listings?min_price=&max_price= filters the feed by price (cents), combines with
the category filter, and binds cursors to the exact filters they were issued under — same
contract as E5.1's category filter (docs/api/listings.md -> GET /listings).

Listings are inserted directly with explicit created_at and price_cents values, so both feed
order and the filtered set are known.
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
        price_cents: int = 1500,
        category: str = "furniture",
        status: str = "active",
        listing_id: uuid.UUID | None = None,
    ) -> str:
        listing = Listing(
            id=listing_id or uuid.uuid4(),
            title="Desk lamp",
            price_cents=price_cents,
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


# --- Filtering, boundaries included ------------------------------------------------------------


def test_range_returns_only_listings_inside_it_boundaries_included(client, viewer, add):
    below = add(NEWEST, 999)
    at_min = add(NEWEST - timedelta(minutes=1), 1000)
    inside = add(NEWEST - timedelta(minutes=2), 1500)
    at_max = add(NEWEST - timedelta(minutes=3), 2000)
    above = add(NEWEST - timedelta(minutes=4), 2001)

    page = get_page(client, viewer, min_price=1000, max_price=2000)
    ids = [item["id"] for item in page["items"]]
    assert ids == [at_min, inside, at_max]
    assert below not in ids and above not in ids


def test_min_price_only_is_an_open_upper_end(client, viewer, add):
    low = add(NEWEST, 500)
    high = add(NEWEST - timedelta(minutes=1), 999_999)
    page = get_page(client, viewer, min_price=1000)
    assert low not in [item["id"] for item in page["items"]]
    assert high in [item["id"] for item in page["items"]]


def test_max_price_only_is_an_open_lower_end(client, viewer, add):
    free = add(NEWEST, 0)
    high = add(NEWEST - timedelta(minutes=1), 5000)
    page = get_page(client, viewer, max_price=1000)
    assert free in [item["id"] for item in page["items"]]
    assert high not in [item["id"] for item in page["items"]]


def test_no_price_filter_returns_every_price(client, viewer, add):
    expected = [add(NEWEST - timedelta(minutes=i), price) for i, price in enumerate([0, 500, 999_999])]
    page = get_page(client, viewer)
    assert [item["id"] for item in page["items"]] == expected


# --- Validation ----------------------------------------------------------------------------------


def test_min_greater_than_max_is_422(client, viewer):
    assert_error(get(client, viewer, min_price=2000, max_price=1000), "invalid_price_range")


def test_min_equal_to_max_is_allowed(client, viewer, add):
    match = add(NEWEST, 1500)
    add(NEWEST - timedelta(minutes=1), 1501)
    page = get_page(client, viewer, min_price=1500, max_price=1500)
    assert [item["id"] for item in page["items"]] == [match]


@pytest.mark.parametrize("params", [{"min_price": -1}, {"max_price": -1}])
def test_negative_price_is_422(client, viewer, params):
    assert get(client, viewer, **params).status_code == 422


@pytest.mark.parametrize("params", [{"min_price": 1_000_001}, {"max_price": 1_000_001}])
def test_over_the_max_bound_is_422(client, viewer, params):
    assert get(client, viewer, **params).status_code == 422


# --- Combines with the category filter ------------------------------------------------------


def test_price_and_category_filters_combine(client, viewer, add):
    match = add(NEWEST, 1500, "furniture")
    add(NEWEST - timedelta(minutes=1), 1500, "kitchen")  # right price, wrong category
    add(NEWEST - timedelta(minutes=2), 5000, "furniture")  # right category, wrong price
    page = get_page(client, viewer, category="furniture", min_price=1000, max_price=2000)
    assert [item["id"] for item in page["items"]] == [match]


def test_price_with_unknown_category_reports_the_category_first(client, viewer):
    assert_error(get(client, viewer, category="nope", min_price=2000, max_price=1000), "unknown_category")


# --- Pagination, same contract as the category filter (E5.1) ------------------------------------


def test_full_price_filtered_walk_returns_each_listing_once(client, viewer, add):
    # 45 in-range listings interleaved with 45 out-of-range ones, so every page boundary of the
    # filtered feed falls between rows the unfiltered feed would also show.
    expected = []
    for i in range(45):
        expected.append(add(NEWEST - timedelta(minutes=i * 2), 1500))
        add(NEWEST - timedelta(minutes=i * 2 + 1), 5000)
    pages = walk(client, viewer, min_price=1000, max_price=2000)
    assert [len(p) for p in pages] == [20, 20, 5]
    assert [i for p in pages for i in p] == expected


def test_hidden_listings_never_appear_in_a_price_filtered_feed(client, viewer, add):
    shown = [add(NEWEST - timedelta(minutes=i), 1500) for i in range(25)]
    hidden = [
        add(NEWEST - timedelta(minutes=30 + i), 1500, status=status)
        for i, status in enumerate(["sold", "draft", "sold", "draft"])
    ]
    shown.append(add(NEWEST - timedelta(minutes=40), 1500))
    flat = [i for p in walk(client, viewer, min_price=1000, max_price=2000) for i in p]
    assert flat == shown
    assert not set(flat) & set(hidden)


# --- Cursors are bound to their exact filters, including price ---------------------------------


@pytest.fixture
def price_cursor(client, viewer, add):
    for i in range(25):
        add(NEWEST - timedelta(minutes=i), 1500)
    return get_page(client, viewer, min_price=1000, max_price=2000)["next_cursor"]


def test_cursor_replayed_under_a_different_range_is_rejected(client, viewer, price_cursor):
    assert_error(
        get(client, viewer, min_price=0, max_price=2000, cursor=price_cursor), "invalid_cursor"
    )


def test_price_filter_removed_mid_walk_is_rejected(client, viewer, price_cursor):
    assert_error(get(client, viewer, cursor=price_cursor), "invalid_cursor")


def test_cursor_works_under_its_own_exact_range(client, viewer, price_cursor):
    assert len(get_page(client, viewer, min_price=1000, max_price=2000, cursor=price_cursor)["items"]) == 5