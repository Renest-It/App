"""The E4.1 migration: the feed index and a non-null listings.created_at (ADR 0011)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import Listing, User

pytestmark = pytest.mark.requires_db


@pytest.fixture
def listing(db_session):
    seller = User(id=uuid.uuid4(), email="seller@creighton.edu", display_name="Seller")
    db_session.add(seller)
    db_session.flush()
    row = Listing(title="Desk lamp", price_cents=1500, seller_id=seller.id, status="active")
    db_session.add(row)
    db_session.commit()
    return row


def test_feed_index_matches_the_feed_query(db_session):
    indexdef = db_session.execute(
        text("SELECT indexdef FROM pg_indexes WHERE tablename = 'listings' AND indexname = 'ix_listings_feed'")
    ).scalar()
    assert indexdef is not None
    assert "(status, created_at DESC, id DESC) INCLUDE (category_id)" in indexdef


def test_created_at_defaults_on_insert(listing):
    assert listing.created_at is not None


def test_null_created_at_is_rejected(db_session, listing):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("UPDATE listings SET created_at = NULL WHERE id = :id"), {"id": listing.id}
        )
