"""E2.2: draft → publish → view, and the feed's cover photo (docs/api/listings.md)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Category, Listing, ListingImage

pytestmark = pytest.mark.requires_db

STORAGE_PUBLIC = "https://test-project.supabase.co/storage/v1/object/public/listing-photos/"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def category_id(db_session):
    return db_session.query(Category.id).order_by(Category.id).first()[0]


@pytest.fixture
def seller(make_token):
    """Headers for the seller. Their email is checked for below, so keep it distinctive."""
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='seller.jane@creighton.edu')}"}


@pytest.fixture
def other(make_token):
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='other@creighton.edu')}"}


@pytest.fixture
def create(client, seller, category_id):
    def _create(headers=None, **overrides) -> dict:
        body = {"title": "Desk lamp", "price_cents": 1500, "category_id": category_id}
        body.update(overrides)
        r = client.post("/listings", headers=headers or seller, json=body)
        assert r.status_code == 201, r.text
        return r.json()

    return _create


@pytest.fixture
def add_photos(db_session):
    """Record photos directly. The images endpoint is E2.3's."""

    def _add(listing_id: str, positions) -> list[str]:
        paths = []
        for position in positions:
            path = f"listings/{listing_id}/{uuid.uuid4()}.jpg"
            db_session.add(
                ListingImage(listing_id=uuid.UUID(listing_id), storage_path=path, position=position)
            )
            paths.append(path)
        db_session.commit()
        return paths

    return _add


# --- create ---------------------------------------------------------------------------------


def test_create_makes_a_draft(create):
    assert create()["status"] == "draft"


def test_create_trims_and_normalizes(create):
    body = create(title="  Desk lamp  ", description="   ")
    assert body["title"] == "Desk lamp"
    assert body["description"] is None


@pytest.mark.parametrize(
    "field, value, ok",
    [
        ("title", "ab", False),
        ("title", "abc", True),
        ("title", "x" * 80, True),
        ("title", "x" * 81, False),
        ("title", "   ab   ", False),
        ("description", "x" * 2000, True),
        ("description", "x" * 2001, False),
        ("price_cents", -1, False),
        ("price_cents", 0, True),
        ("price_cents", 1_000_000, True),
        ("price_cents", 1_000_001, False),
    ],
)
def test_create_validation_rules(client, seller, category_id, field, value, ok):
    body = {"title": "Desk lamp", "price_cents": 1500, "category_id": category_id, field: value}
    r = client.post("/listings", headers=seller, json=body)
    assert r.status_code == (201 if ok else 422), r.text


def test_create_requires_a_category(client, seller):
    r = client.post("/listings", headers=seller, json={"title": "Desk lamp", "price_cents": 1})
    assert r.status_code == 422


def test_create_with_unknown_category(client, seller):
    r = client.post(
        "/listings", headers=seller, json={"title": "Desk lamp", "price_cents": 1, "category_id": 999999}
    )
    assert r.status_code == 422
    assert r.json() == {"code": "unknown_category", "message": "That category doesn't exist."}


# --- publish --------------------------------------------------------------------------------


def test_draft_is_published(client, seller, create, add_photos):
    listing = create()
    add_photos(listing["id"], [0])
    r = client.post(f"/listings/{listing['id']}/publish", headers=seller)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    assert client.get(f"/listings/{listing['id']}", headers=seller).json()["status"] == "active"


def test_publish_without_photos_is_422(client, seller, create):
    listing = create()
    r = client.post(f"/listings/{listing['id']}/publish", headers=seller)
    assert r.status_code == 422
    assert r.json()["code"] == "no_images"


def test_publish_twice_is_409(client, seller, create, add_photos):
    listing = create()
    add_photos(listing["id"], [0])
    assert client.post(f"/listings/{listing['id']}/publish", headers=seller).status_code == 200
    r = client.post(f"/listings/{listing['id']}/publish", headers=seller)
    assert r.status_code == 409
    assert r.json()["code"] == "already_published"


def test_non_seller_publishing_an_active_listing_is_403(client, seller, other, create, add_photos):
    listing = create()
    add_photos(listing["id"], [0])
    client.post(f"/listings/{listing['id']}/publish", headers=seller)
    r = client.post(f"/listings/{listing['id']}/publish", headers=other)
    assert r.status_code == 403
    assert r.json()["code"] == "not_owner"


def test_non_seller_publishing_a_draft_is_404(client, other, create, add_photos, db_session):
    # 404, not 403: a 403 would reveal that the draft exists.
    listing = create()
    add_photos(listing["id"], [0])
    r = client.post(f"/listings/{listing['id']}/publish", headers=other)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"
    assert db_session.get(Listing, uuid.UUID(listing["id"])).status == "draft"


def test_publish_rechecks_validation(client, seller, create, add_photos, db_session):
    # A draft can become invalid after creation, e.g. when its category is deleted.
    listing = create()
    add_photos(listing["id"], [0])
    row = db_session.get(Listing, uuid.UUID(listing["id"]))
    row.category_id = None
    db_session.commit()
    r = client.post(f"/listings/{listing['id']}/publish", headers=seller)
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_listing"


# --- view -----------------------------------------------------------------------------------


def test_draft_is_visible_to_its_seller_only(client, seller, other, create):
    listing = create()
    assert client.get(f"/listings/{listing['id']}", headers=seller).status_code == 200
    r = client.get(f"/listings/{listing['id']}", headers=other)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


def test_active_listing_is_visible_to_anyone_logged_in(client, seller, other, create, add_photos):
    listing = create()
    add_photos(listing["id"], [0])
    client.post(f"/listings/{listing['id']}/publish", headers=seller)
    assert client.get(f"/listings/{listing['id']}", headers=other).status_code == 200


@pytest.mark.parametrize("listing_id", [str(uuid.uuid4()), "not-a-uuid"])
def test_unknown_or_malformed_id_is_404(client, seller, listing_id):
    r = client.get(f"/listings/{listing_id}", headers=seller)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


def test_detail_images_are_ordered_with_public_urls(client, seller, create, add_photos):
    listing = create()
    paths = add_photos(listing["id"], [2, 0, 1])
    images = client.get(f"/listings/{listing['id']}", headers=seller).json()["images"]
    assert [image["position"] for image in images] == [0, 1, 2]
    by_position = dict(zip([2, 0, 1], paths))
    assert [image["url"] for image in images] == [STORAGE_PUBLIC + by_position[p] for p in (0, 1, 2)]


def test_detail_never_includes_the_seller_email(client, seller, other, create, add_photos):
    listing = create()
    add_photos(listing["id"], [0])
    client.post(f"/listings/{listing['id']}/publish", headers=seller)
    r = client.get(f"/listings/{listing['id']}", headers=other)
    assert set(r.json()["seller"]) == {"id", "display_name"}
    assert "seller.jane@creighton.edu" not in r.text
    assert "email" not in r.text


# --- feed -----------------------------------------------------------------------------------


def test_draft_never_appears_in_the_feed(client, seller, create):
    listing = create()
    ids = [item["id"] for item in client.get("/listings", headers=seller).json()]
    assert listing["id"] not in ids


def test_feed_cover_is_the_position_0_photo(client, seller, create, add_photos):
    listing = create()
    paths = add_photos(listing["id"], [1, 0, 2])
    client.post(f"/listings/{listing['id']}/publish", headers=seller)
    [item] = client.get("/listings", headers=seller).json()
    assert item["cover_image_url"] == STORAGE_PUBLIC + paths[1]


def test_feed_cover_is_null_without_a_position_0_photo(client, seller, db_session, create):
    # Listings from before E2 have no photos; they're still active.
    listing = create()
    db_session.get(Listing, uuid.UUID(listing["id"])).status = "active"
    db_session.commit()
    [item] = client.get("/listings", headers=seller).json()
    assert item["cover_image_url"] is None
