"""E4.2: the planner actually uses ix_listings_feed for the feed query (ADR 0011).

An index that exists but isn't used is invisible, so this checks the plan of the exact query
the endpoint runs. It needs enough rows for an index scan to beat a sequential scan: with a
handful, Postgres correctly reads the whole table.
"""

import uuid

import pytest
from sqlalchemy import text

from app.models import Category, User
from app.pagination import FeedPosition
from app.routers.listings import feed_query

pytestmark = pytest.mark.requires_db

ROWS = 5000


@pytest.fixture
def seeded(db_session):
    """ROWS listings one minute apart: 80% active, the rest drafts and sold."""
    seller = User(id=uuid.uuid4(), email="seller@creighton.edu", display_name="Seller")
    db_session.add(seller)
    db_session.commit()
    category_id = db_session.query(Category.id).order_by(Category.id).first()[0]
    db_session.execute(
        text(
            """
            INSERT INTO listings (id, seller_id, title, price_cents, category_id, status, created_at)
            SELECT gen_random_uuid(), :seller_id, 'Listing ' || g, 1000, :category_id,
                   CASE g % 10 WHEN 0 THEN 'draft' WHEN 1 THEN 'sold' ELSE 'active' END,
                   TIMESTAMPTZ '2026-09-26 12:00:00+00' - g * INTERVAL '1 minute'
            FROM generate_series(1, :rows) AS g
            """
        ),
        {"seller_id": seller.id, "category_id": category_id, "rows": ROWS},
    )
    db_session.commit()
    db_session.execute(text("ANALYZE listings"))
    db_session.commit()


def plan(db_session, position: FeedPosition | None) -> str:
    statement = feed_query(db_session, position, 20).statement.compile(
        dialect=db_session.bind.dialect, compile_kwargs={"literal_binds": True}
    )
    rows = db_session.execute(text(f"EXPLAIN {statement}")).scalars()
    return "\n".join(rows)


def assert_uses_feed_index(query_plan: str):
    assert "ix_listings_feed" in query_plan, query_plan
    assert "Seq Scan on listings" not in query_plan, query_plan
    assert "Sort" not in query_plan, query_plan


def test_first_page_uses_the_feed_index(db_session, seeded):
    assert_uses_feed_index(plan(db_session, None))


def test_cursor_page_uses_the_feed_index(db_session, seeded):
    middle = db_session.execute(
        text(
            "SELECT created_at, id FROM listings WHERE status = 'active' "
            "ORDER BY created_at DESC, id DESC OFFSET :n LIMIT 1"
        ),
        {"n": ROWS // 3},
    ).one()
    query_plan = plan(db_session, FeedPosition(created_at=middle.created_at, id=middle.id))
    assert_uses_feed_index(query_plan)
    # The row comparison is an index condition (where the scan starts), not a filter applied
    # to every row the scan reads.
    [index_cond] = [line for line in query_plan.splitlines() if "ROW(created_at, id) <" in line]
    assert "Index Cond" in index_cond, query_plan
