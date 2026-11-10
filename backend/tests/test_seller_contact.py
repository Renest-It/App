"""E6.1: GET /listings/{id}/seller-contact (docs/api/listings.md, ADR 0012)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Category

pytestmark = pytest.mark.requires_db


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
    """Record one photo directly, enough to publish. The images endpoint is E2.3's."""

    def _add(listing_id: str) -> None:
        from app.models import ListingImage

        db_session.add(
            ListingImage(
                listing_id=uuid.UUID(listing_id),
                storage_path=f"listings/{listing_id}/{uuid.uuid4()}.jpg",
                position=0,
            )
        )
        db_session.commit()

    return _add


# --- seller-contact ---------------------------------------------------------------------------


def test_contact_returns_the_sellers_email(client, seller, other, create, add_photos):
    listing = create()
    add_photos(listing["id"])
    client.post(f"/listings/{listing['id']}/publish", headers=seller)
    r = client.get(f"/listings/{listing['id']}/seller-contact", headers=other)
    assert r.status_code == 200, r.text
    assert r.json() == {"email": "seller.jane@creighton.edu", "display_name": "Test Student"}


def test_contact_on_someone_elses_draft_is_404(client, other, create):
    # 404, not 403: a 403 would confirm the draft exists (ADR 0010).
    listing = create()
    r = client.get(f"/listings/{listing['id']}/seller-contact", headers=other)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


@pytest.mark.parametrize("listing_id", [str(uuid.uuid4()), "not-a-uuid"])
def test_contact_on_unknown_or_malformed_id_is_404(client, seller, listing_id):
    r = client.get(f"/listings/{listing_id}/seller-contact", headers=seller)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


def test_contact_works_for_a_sold_listing(client, seller, other, create, add_photos):
    listing = create()
    add_photos(listing["id"])
    client.post(f"/listings/{listing['id']}/publish", headers=seller)
    client.post(f"/listings/{listing['id']}/sold", headers=seller)
    r = client.get(f"/listings/{listing['id']}/seller-contact", headers=other)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "seller.jane@creighton.edu"


def test_seller_can_fetch_their_own_contact_info(client, seller, create):
    # No special-casing: the seller is just another caller who can see this listing.
    listing = create()
    r = client.get(f"/listings/{listing['id']}/seller-contact", headers=seller)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "seller.jane@creighton.edu"


def test_email_never_leaks_into_any_other_listing_response(
    client, seller, other, create, add_photos
):
    """Regression test: SellerOut/Seller must keep omitting email everywhere except this one
    endpoint (docs/api/listings.md, ADR 0012)."""
    listing = create()
    add_photos(listing["id"])
    client.post(f"/listings/{listing['id']}/publish", headers=seller)

    detail = client.get(f"/listings/{listing['id']}", headers=other)
    assert set(detail.json()["seller"]) == {"id", "display_name"}
    assert "seller.jane@creighton.edu" not in detail.text

    feed = client.get("/listings", headers=other)
    assert "seller.jane@creighton.edu" not in feed.text

    mine = client.get("/listings/mine", headers=seller)
    assert "seller.jane@creighton.edu" not in mine.text