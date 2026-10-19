"""E3.2: edit, delete, and mark sold/unsold (docs/api/listings.md → E3 endpoints)."""

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.models import Category, Listing, ListingImage

pytestmark = pytest.mark.requires_db

# Each action as (method, path suffix, JSON body), for the tests every one of them must pass.
ACTIONS = [
    ("PATCH", "", {"price_cents": 100}),
    ("DELETE", "", None),
    ("POST", "/sold", None),
    ("POST", "/unsold", None),
]


@pytest.fixture
def removed_folders(monkeypatch):
    """Stands in for Supabase Storage: records each folder delete_listing removes."""
    removed = []
    monkeypatch.setattr(storage, "remove_folder", removed.append)
    return removed


@pytest.fixture
def client(removed_folders):
    return TestClient(app)


@pytest.fixture
def category_ids(db_session):
    return [row[0] for row in db_session.query(Category.id).order_by(Category.id).limit(2)]


@pytest.fixture
def seller(make_token):
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='seller@creighton.edu')}"}


@pytest.fixture
def other(make_token):
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='other@creighton.edu')}"}


@pytest.fixture
def create(client, seller, category_ids, db_session):
    """Create a listing through the API and bring it to `status`, with one photo unless it's
    a draft."""

    def _create(status: str = "active", **overrides) -> dict:
        body = {"title": "Desk lamp", "price_cents": 1500, "category_id": category_ids[0]}
        body.update(overrides)
        r = client.post("/listings", headers=seller, json=body)
        assert r.status_code == 201, r.text
        listing = r.json()
        if status == "draft":
            return listing
        # Recorded directly: the images endpoints are E2.3's, and need storage.
        db_session.add(
            ListingImage(
                listing_id=uuid.UUID(listing["id"]),
                storage_path=f"listings/{listing['id']}/{uuid.uuid4()}.jpg",
                position=0,
            )
        )
        db_session.commit()
        assert client.post(f"/listings/{listing['id']}/publish", headers=seller).status_code == 200
        if status == "sold":
            assert client.post(f"/listings/{listing['id']}/sold", headers=seller).status_code == 200
        return listing

    return _create


def send(client, headers, method, listing_id, suffix="", body=None):
    return client.request(method, f"/listings/{listing_id}{suffix}", headers=headers, json=body)


def row(db_session, listing_id: str) -> Listing | None:
    db_session.expire_all()
    return db_session.get(Listing, uuid.UUID(listing_id))


def feed_ids(client, headers) -> list[str]:
    return [listing["id"] for listing in client.get("/listings", headers=headers).json()]


# --- every action: owner-only -----------------------------------------------------------------


@pytest.mark.parametrize("status", ["draft", "active", "sold"])
@pytest.mark.parametrize("method, suffix, body", ACTIONS)
def test_non_owner_gets_404_and_nothing_changes(
    client, other, create, db_session, status, method, suffix, body
):
    listing = create(status)
    before = row(db_session, listing["id"])
    before_state = (before.status, before.price_cents, before.updated_at)

    r = send(client, other, method, listing["id"], suffix, body)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"
    after = row(db_session, listing["id"])
    assert after is not None
    assert (after.status, after.price_cents, after.updated_at) == before_state


@pytest.mark.parametrize("listing_id", [str(uuid.uuid4()), "not-a-uuid"])
@pytest.mark.parametrize("method, suffix, body", ACTIONS)
def test_unknown_or_malformed_id_is_404(client, seller, listing_id, method, suffix, body):
    r = send(client, seller, method, listing_id, suffix, body)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


# --- PATCH ------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["draft", "active"])
def test_edit_changes_only_the_fields_sent(client, seller, create, category_ids, status):
    listing = create(status, description="Bulb included.")
    r = send(
        client, seller, "PATCH", listing["id"],
        body={"title": "  Floor lamp  ", "price_cents": 900, "category_id": category_ids[1]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Floor lamp"
    assert body["price_cents"] == 900
    assert body["category"]["id"] == category_ids[1]
    assert body["description"] == "Bulb included."  # not sent, so unchanged
    assert body["status"] == status


def test_edit_keeps_created_at_and_sets_updated_at(client, seller, create, db_session):
    listing = create()
    before = row(db_session, listing["id"])
    created_at, updated_at = before.created_at, before.updated_at

    assert send(client, seller, "PATCH", listing["id"], body={"price_cents": 900}).status_code == 200
    after = row(db_session, listing["id"])
    assert after.created_at == created_at
    assert after.updated_at is not None and after.updated_at != updated_at


def test_edit_does_not_bump_the_feed(client, seller, create):
    older = create(title="Older listing")
    newer = create(title="Newer listing")
    send(client, seller, "PATCH", older["id"], body={"title": "Older listing, edited"})
    ids = feed_ids(client, seller)
    assert ids.index(newer["id"]) < ids.index(older["id"])


@pytest.mark.parametrize("description", [None, "   "])
def test_edit_can_clear_the_description(client, seller, create, description):
    listing = create(description="Bulb included.")
    r = send(client, seller, "PATCH", listing["id"], body={"description": description})
    assert r.status_code == 200
    assert r.json()["description"] is None


def test_empty_edit_changes_nothing(client, seller, create, db_session):
    listing = create()
    updated_at = row(db_session, listing["id"]).updated_at
    r = send(client, seller, "PATCH", listing["id"], body={})
    assert r.status_code == 200
    assert r.json()["title"] == "Desk lamp"
    assert row(db_session, listing["id"]).updated_at == updated_at


@pytest.mark.parametrize(
    "body",
    [
        {"title": "ab"},
        {"title": "x" * 81},
        {"title": None},
        {"description": "x" * 2001},
        {"price_cents": -1},
        {"price_cents": 1_000_001},
        {"price_cents": None},
        {"category_id": None},
    ],
)
def test_edit_reruns_validation_rules(client, seller, create, db_session, body):
    listing = create()
    r = send(client, seller, "PATCH", listing["id"], body=body)
    assert r.status_code == 422
    assert "detail" in r.json()
    assert row(db_session, listing["id"]).title == "Desk lamp"


def test_edit_with_unknown_category(client, seller, create, db_session):
    listing = create()
    r = send(client, seller, "PATCH", listing["id"], body={"category_id": 999_999})
    assert r.status_code == 422
    assert r.json()["code"] == "unknown_category"


def test_editing_a_sold_listing_is_409(client, seller, create, db_session):
    listing = create("sold")
    r = send(client, seller, "PATCH", listing["id"], body={"price_cents": 1})
    assert r.status_code == 409
    assert r.json()["code"] == "listing_sold"
    assert row(db_session, listing["id"]).price_cents == 1500


# --- DELETE -----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["draft", "active", "sold"])
def test_delete_removes_the_listing_and_its_folder(
    client, seller, create, db_session, removed_folders, status
):
    listing = create(status)
    r = send(client, seller, "DELETE", listing["id"])
    assert r.status_code == 204
    assert r.content == b""
    assert row(db_session, listing["id"]) is None
    assert removed_folders == [f"listings/{listing['id']}"]
    assert client.get(f"/listings/{listing['id']}", headers=seller).status_code == 404


def test_delete_removes_the_listings_image_rows(client, seller, create, db_session):
    listing = create()
    listing_id = uuid.UUID(listing["id"])
    assert db_session.query(ListingImage).filter_by(listing_id=listing_id).count() == 1
    send(client, seller, "DELETE", listing["id"])
    db_session.expire_all()
    assert db_session.query(ListingImage).filter_by(listing_id=listing_id).count() == 0


def test_delete_still_succeeds_when_storage_fails(
    client, seller, create, db_session, monkeypatch, caplog
):
    def fail(folder):
        raise storage.StorageUnavailable("simulated outage")

    monkeypatch.setattr(storage, "remove_folder", fail)
    listing = create()
    with caplog.at_level(logging.WARNING, logger="app.routers.listings"):
        r = send(client, seller, "DELETE", listing["id"])
    assert r.status_code == 204
    assert row(db_session, listing["id"]) is None
    assert f"listings/{listing['id']}" in caplog.text


def test_deleting_twice_is_404(client, seller, create):
    listing = create()
    assert send(client, seller, "DELETE", listing["id"]).status_code == 204
    assert send(client, seller, "DELETE", listing["id"]).status_code == 404


# --- sold / unsold ----------------------------------------------------------------------------


def test_sold_leaves_the_feed_and_unsold_brings_it_back(client, seller, other, create):
    listing = create()
    assert listing["id"] in feed_ids(client, other)

    r = send(client, seller, "POST", listing["id"], "/sold")
    assert r.status_code == 200
    assert r.json()["status"] == "sold"
    assert listing["id"] not in feed_ids(client, other)
    # Still viewable by ID once sold.
    assert client.get(f"/listings/{listing['id']}", headers=other).json()["status"] == "sold"

    r = send(client, seller, "POST", listing["id"], "/unsold")
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert listing["id"] in feed_ids(client, other)


def test_unsold_keeps_its_place_in_the_feed(client, seller, create, db_session):
    older = create(title="Older listing")
    newer = create(title="Newer listing")
    created_at = row(db_session, older["id"]).created_at
    send(client, seller, "POST", older["id"], "/sold")
    send(client, seller, "POST", older["id"], "/unsold")
    assert row(db_session, older["id"]).created_at == created_at
    ids = feed_ids(client, seller)
    assert ids.index(newer["id"]) < ids.index(older["id"])


@pytest.mark.parametrize("status", ["draft", "sold"])
def test_sold_is_only_for_active_listings(client, seller, create, db_session, status):
    listing = create(status)
    r = send(client, seller, "POST", listing["id"], "/sold")
    assert r.status_code == 409
    assert r.json()["code"] == "listing_not_active"
    assert row(db_session, listing["id"]).status == status


@pytest.mark.parametrize("status", ["draft", "active"])
def test_unsold_is_only_for_sold_listings(client, seller, create, db_session, status):
    listing = create(status)
    r = send(client, seller, "POST", listing["id"], "/unsold")
    assert r.status_code == 409
    assert r.json()["code"] == "listing_not_sold"
    assert row(db_session, listing["id"]).status == status
