"""Print EXPLAIN (ANALYZE, BUFFERS) for the feed query, for the E4.2 PR and E4.4's perf pass.

Run from backend/, against the disposable test database (never the shared Supabase one):

    TEST_DATABASE_URL=postgresql://renest_test:renest_test@localhost:5433/renest_test \
        python scripts/explain_feed.py [ROWS]

The database must already be migrated: running the test suite once does that. It WIPES the
users and listings tables, seeds ROWS listings (default 5000, as in
tests/test_feed_query_plan.py), prints the plan for the first page and for a cursor page a
third of the way down, and wipes the tables again. It does that for the unfiltered feed and
for two category filters (E5.1): a common category (~40% of rows) and a rare one (~2%).
"""

import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
if not TEST_DATABASE_URL:
    sys.exit("Set TEST_DATABASE_URL to a disposable local Postgres (see the docstring).")
_host = (urlparse(TEST_DATABASE_URL).hostname or "").lower()
if "supabase.co" in _host or "supabase.com" in _host:
    sys.exit(f"TEST_DATABASE_URL points at a Supabase host ({_host}). This script wipes tables.")

# Settings are read when `app` is first imported, so point it at the test database first.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/, for `app`

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Category, User  # noqa: E402
from app.pagination import FeedPosition  # noqa: E402
from app.routers.listings import feed_query  # noqa: E402

# The same data as tests/test_feed_query_plan.py: one minute apart, 80% active. Categories are
# skewed: `common` gets 40% of rows, `rare` 2%, `others` share the rest. Status follows g % 10
# and category (g / 10) % 50, so each category gets the same 80% active.
SEED = text(
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
)
COMMON, RARE = "furniture", "decor"


def seed_params(db, seller_id: uuid.UUID, rows: int) -> dict:
    ids = {slug: id_ for id_, slug in db.query(Category.id, Category.slug)}
    others = [id_ for slug, id_ in sorted(ids.items()) if slug not in (COMMON, RARE)]
    return {
        "seller_id": seller_id,
        "rows": rows,
        "common": ids[COMMON],
        "rare": ids[RARE],
        "others": others,
    }


def a_third_down(db, category_id: int | None) -> FeedPosition:
    """The feed position a third of the way down the (filtered) feed."""
    filtered = "AND category_id = :category_id" if category_id is not None else ""
    count = db.execute(
        text(f"SELECT count(*) FROM listings WHERE status = 'active' {filtered}"),
        {"category_id": category_id},
    ).scalar()
    row = db.execute(
        text(
            f"SELECT created_at, id FROM listings WHERE status = 'active' {filtered} "
            "ORDER BY created_at DESC, id DESC OFFSET :n LIMIT 1"
        ),
        {"category_id": category_id, "n": count // 3},
    ).one()
    return FeedPosition(created_at=row.created_at, id=row.id)


def explain(db, position: FeedPosition | None, category_id: int | None = None) -> str:
    statement = feed_query(db, position, 20, category_id).statement.compile(
        dialect=db.bind.dialect, compile_kwargs={"literal_binds": True}
    )
    return "\n".join(db.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {statement}")).scalars())


def main() -> None:
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    db = SessionLocal()
    try:
        db.execute(text("TRUNCATE listings, users CASCADE"))
        seller = User(id=uuid.uuid4(), email="seller@creighton.edu", display_name="Seller")
        db.add(seller)
        db.flush()
        params = seed_params(db, seller.id, rows)
        db.execute(SEED, params)
        db.commit()
        db.execute(text("ANALYZE listings"))
        db.commit()
        server_version = db.execute(text("SHOW server_version")).scalar()

        print(
            f"-- Postgres {server_version}, {rows} listings (80% active); "
            f"{COMMON} ~40% of rows, {RARE} ~2%\n"
        )
        for label, slug, category_id in [
            ("Unfiltered", None, None),
            (f"Common category ({COMMON})", COMMON, params["common"]),
            (f"Rare category ({RARE})", RARE, params["rare"]),
        ]:
            query = f"?category={slug}" if slug else ""
            print(f"-- {label}, first page: GET /listings{query}")
            print(explain(db, None, category_id))
            joiner = "&" if query else "?"
            print(
                f"\n-- {label}, cursor page: GET /listings{query}{joiner}cursor=<a third of the way down>"
            )
            print(explain(db, a_third_down(db, category_id), category_id))
            print()
    finally:
        db.rollback()
        db.execute(text("TRUNCATE listings, users CASCADE"))
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
