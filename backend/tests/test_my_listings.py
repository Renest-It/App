"""E3.3: GET /listings/mine (docs/api/listings.md)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Category, ListingImage

pytestmark = pytest.mark.requires_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def category_id(db_session):
    return db_session.query(Category.id).order_by(Category.id).first()[0]


@pytest.fixture
def seller(make_token):
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='seller@creighton.edu')}"}


@pytest.fixture
def other(make_token):
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='other@creighton.edu')}"}


@pytest.fixture
def create(client, seller, category_id, db_session):
    """Create a listing for `headers` and bring it to `status`. Non-drafts get one photo,
    recorded directly (the images endpoints need storage)."""

    def _create(status: str, title: str = "Desk lamp", headers=None) -> str:
        headers = headers or seller
        r = client.post(
            "/listings",
            headers=headers,
            json={"title": title, "price_cents": 1500, "category_id": category_id},
        )
        assert r.status_code == 201, r.text
        listing_id = r.json()["id"]
        if status == "draft":
            return listing_id
        db_session.add(
            ListingImage(
                listing_id=uuid.UUID(listing_id),
                storage_path=f"listings/{listing_id}/{uuid.uuid4()}.jpg",
                position=0,
            )
        )
        db_session.commit()
        assert client.post(f"/listings/{listing_id}/publish", headers=headers).status_code == 200
        if status == "sold":
            assert client.post(f"/listings/{listing_id}/sold", headers=headers).status_code == 200
        return listing_id

    return _create


def mine(client, headers, status=None):
    params = {"status": status} if status else None
    r = client.get("/listings/mine", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_returns_only_your_listings_including_drafts(client, seller, other, create):
    draft = create("draft")
    active = create("active")
    sold = create("sold")
    create("active", headers=other)
    create("draft", headers=other)

    listings = mine(client, seller)
    assert {item["id"] for item in listings} == {draft, active, sold}
    assert {item["status"] for item in listings} == {"draft", "active", "sold"}


def test_newest_first(client, seller, create):
    first = create("active", title="First listing")
    second = create("draft", title="Second listing")
    third = create("sold", title="Third listing")
    assert [item["id"] for item in mine(client, seller)] == [third, second, first]


@pytest.mark.parametrize("status", ["active", "draft", "sold"])
def test_status_filter(client, seller, create, status):
    ids = {s: create(s) for s in ("active", "draft", "sold")}
    listings = mine(client, seller, status)
    assert [item["id"] for item in listings] == [ids[status]]
    assert listings[0]["status"] == status


def test_sold_excludes_active_and_draft(client, seller, create):
    create("active")
    create("draft")
    sold = create("sold")
    assert [item["id"] for item in mine(client, seller, "sold")] == [sold]


def test_empty_is_an_empty_array(client, seller, other, create):
    assert mine(client, seller) == []
    create("active")
    assert mine(client, seller, "sold") == []
    assert mine(client, other) == []


def test_items_have_the_feed_shape_plus_status(client, seller, create):
    listing_id = create("active")
    feed_item = next(i for i in client.get("/listings", headers=seller).json() if i["id"] == listing_id)
    [item] = mine(client, seller)
    assert item == {**feed_item, "status": "active"}
    assert item["cover_image_url"].endswith(".jpg")


def test_draft_without_photos_has_no_cover(client, seller, create):
    create("draft")
    [item] = mine(client, seller)
    assert item["cover_image_url"] is None


def test_unknown_status_is_422(client, seller):
    r = client.get("/listings/mine", headers=seller, params={"status": "deleted"})
    assert r.status_code == 422
    assert "detail" in r.json()


def test_requires_login(client):
    assert client.get("/listings/mine").status_code == 401


def test_mine_is_not_treated_as_a_listing_id(client, seller, create):
    # If /listings/{id} were declared first, this would be a 404 listing_not_found.
    create("draft")
    r = client.get("/listings/mine", headers=seller)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
