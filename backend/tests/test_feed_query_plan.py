"""E4.2 / E5.1: the planner actually uses ix_listings_feed for the feed query, unfiltered and
filtered by category (ADR 0011).

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


COMMON, RARE = "furniture", "decor"


@pytest.fixture
def seeded(db_session) -> dict[str, int]:
    """ROWS listings one minute apart: 80% active, the rest drafts and sold. Categories are
    skewed like scripts/explain_feed.py: COMMON ~40% of rows, RARE ~2%. Returns their ids."""
    seller = User(id=uuid.uuid4(), email="seller@creighton.edu", display_name="Seller")
    db_session.add(seller)
    db_session.commit()
    ids = {slug: id_ for id_, slug in db_session.query(Category.id, Category.slug)}
    others = [id_ for slug, id_ in sorted(ids.items()) if slug not in (COMMON, RARE)]
    db_session.execute(
        text(
            """
            INSERT INTO listings (id, seller_id, title, price_cents, category_id, status, created_at)
            SELECT gen_random_uuid(), :seller_id, 'Listing ' || g, 1000,
                   CASE WHEN (g / 10) % 50 < 20 THEN :common
                        WHEN (g / 10) % 50 = 20 THEN :rare
                        ELSE (CAST(:others AS int[]))[1 + (g / 10) % 5] END,
                   CASE g % 10 WHEN 0 THEN 'draft' WHEN 1 THEN 'sold' ELSE 'active' END,
                   TIMESTAMPTZ '2026-09-26 12:00:00+00' - g * INTERVAL '1 minute'
            FROM generate_series(1, :rows) AS g
            """
        ),
        {
            "seller_id": seller.id,
            "rows": ROWS,
            "common": ids[COMMON],
            "rare": ids[RARE],
            "others": others,
        },
    )
    db_session.commit()
    db_session.execute(text("ANALYZE listings"))
    db_session.commit()
    return {COMMON: ids[COMMON], RARE: ids[RARE]}


def a_third_down(db_session, category_id: int | None = None) -> FeedPosition:
    filtered = "AND category_id = :category_id" if category_id is not None else ""
    count = db_session.execute(
        text(f"SELECT count(*) FROM listings WHERE status = 'active' {filtered}"),
        {"category_id": category_id},
    ).scalar()
    row = db_session.execute(
        text(
            f"SELECT created_at, id FROM listings WHERE status = 'active' {filtered} "
            "ORDER BY created_at DESC, id DESC OFFSET :n LIMIT 1"
        ),
        {"category_id": category_id, "n": count // 3},
    ).one()
    return FeedPosition(created_at=row.created_at, id=row.id)


def plan(db_session, position: FeedPosition | None, category_id: int | None = None) -> str:
    statement = feed_query(db_session, position, 20, category_id).statement.compile(
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


def assert_cursor_is_an_index_condition(query_plan: str):
    # The row comparison is an index condition (where the scan starts), not a filter applied
    # to every row the scan reads.
    [index_cond] = [line for line in query_plan.splitlines() if "ROW(created_at, id) <" in line]
    assert "Index Cond" in index_cond, query_plan


def test_cursor_page_uses_the_feed_index(db_session, seeded):
    query_plan = plan(db_session, a_third_down(db_session))
    assert_uses_feed_index(query_plan)
    assert_cursor_is_an_index_condition(query_plan)


# E5.1 kept ix_listings_feed alone for the category filter: the category is a Filter on the
# index scan, which stays cheap down to a ~2% category (ADR 0011, E5.1 addendum). If a second
# index is ever added, these tests say which one the filtered feed should use.
@pytest.mark.parametrize("slug", [COMMON, RARE])
def test_filtered_first_page_uses_the_feed_index(db_session, seeded, slug):
    assert_uses_feed_index(plan(db_session, None, seeded[slug]))


@pytest.mark.parametrize("slug", [COMMON, RARE])
def test_filtered_cursor_page_uses_the_feed_index(db_session, seeded, slug):
    query_plan = plan(db_session, a_third_down(db_session, seeded[slug]), seeded[slug])
    assert_uses_feed_index(query_plan)
    assert_cursor_is_an_index_condition(query_plan)
