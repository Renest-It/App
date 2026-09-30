"""The E2.1 migration: listing_images constraints and the new draft status (ADR 0009)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import Listing, ListingImage, User

pytestmark = pytest.mark.requires_db


@pytest.fixture
def listing(db_session):
    seller = User(id=uuid.uuid4(), email="seller@creighton.edu", display_name="Seller")
    db_session.add(seller)
    db_session.flush()
    row = Listing(title="Desk lamp", price_cents=1500, seller_id=seller.id, status="draft")
    db_session.add(row)
    db_session.commit()
    return row


def add_image(db_session, listing_id, position):
    db_session.add(
        ListingImage(
            listing_id=listing_id,
            storage_path=f"listings/{listing_id}/{uuid.uuid4()}.jpg",
            position=position,
        )
    )
    db_session.commit()


def image_count(db_session, listing_id) -> int:
    return db_session.execute(
        text("SELECT count(*) FROM listing_images WHERE listing_id = :id"), {"id": listing_id}
    ).scalar()


def test_draft_status_is_allowed(listing):
    assert listing.status == "draft"


def test_unknown_status_is_rejected(db_session, listing):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("UPDATE listings SET status = 'bogus' WHERE id = :id"), {"id": listing.id}
        )
    db_session.rollback()


def test_new_listings_still_default_to_active(db_session, listing):
    # E2.2 switches POST /listings to drafts; until then the column default is unchanged.
    row = Listing(title="Chair", price_cents=0, seller_id=listing.seller_id)
    db_session.add(row)
    db_session.commit()
    assert row.status == "active"


def test_images_are_ordered_by_position(db_session, listing):
    add_image(db_session, listing.id, 2)
    add_image(db_session, listing.id, 0)
    add_image(db_session, listing.id, 1)
    db_session.refresh(listing)
    assert [image.position for image in listing.images] == [0, 1, 2]


def test_two_photos_cannot_share_a_position(db_session, listing):
    add_image(db_session, listing.id, 0)
    with pytest.raises(IntegrityError):
        add_image(db_session, listing.id, 0)
    db_session.rollback()


@pytest.mark.parametrize("position", [-1, 6])
def test_position_must_be_0_to_5(db_session, listing, position):
    with pytest.raises(IntegrityError):
        add_image(db_session, listing.id, position)
    db_session.rollback()


def test_deleting_a_listing_deletes_its_images(db_session, listing):
    add_image(db_session, listing.id, 0)
    add_image(db_session, listing.id, 1)
    # Raw SQL, so the database's ON DELETE CASCADE does the work, not the ORM.
    db_session.execute(text("DELETE FROM listings WHERE id = :id"), {"id": listing.id})
    db_session.commit()
    assert image_count(db_session, listing.id) == 0
