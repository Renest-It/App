"""Print EXPLAIN (ANALYZE, BUFFERS) for the feed query, for the E4.2 PR and E4.4's perf pass.

Run from backend/, against the disposable test database (never the shared Supabase one):

    TEST_DATABASE_URL=postgresql://renest_test:renest_test@localhost:5433/renest_test \
        python scripts/explain_feed.py [ROWS]

The database must already be migrated: running the test suite once does that. It WIPES the
users and listings tables, seeds ROWS listings (default 5000, as in
tests/test_feed_query_plan.py), prints the plan for the first page and for a cursor page a
third of the way down, and wipes the tables again.
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

# The same data as tests/test_feed_query_plan.py: one minute apart, 80% active.
SEED = text(
    """
    INSERT INTO listings (id, seller_id, title, price_cents, category_id, status, created_at)
    SELECT gen_random_uuid(), :seller_id, 'Listing ' || g, 1000, :category_id,
           CASE g % 10 WHEN 0 THEN 'draft' WHEN 1 THEN 'sold' ELSE 'active' END,
           TIMESTAMPTZ '2026-09-26 12:00:00+00' - g * INTERVAL '1 minute'
    FROM generate_series(1, :rows) AS g
    """
)


def explain(db, position: FeedPosition | None) -> str:
    statement = feed_query(db, position, 20).statement.compile(
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
        category_id = db.query(Category.id).order_by(Category.id).first()[0]
        db.execute(SEED, {"seller_id": seller.id, "category_id": category_id, "rows": rows})
        db.commit()
        db.execute(text("ANALYZE listings"))
        db.commit()

        middle = db.execute(
            text(
                "SELECT created_at, id FROM listings WHERE status = 'active' "
                "ORDER BY created_at DESC, id DESC OFFSET :n LIMIT 1"
            ),
            {"n": rows // 3},
        ).one()
        server_version = db.execute(text("SHOW server_version")).scalar()

        print(f"-- Postgres {server_version}, {rows} listings (80% active)\n")
        print("-- First page: GET /listings")
        print(explain(db, None))
        print("\n-- Cursor page: GET /listings?cursor=<a third of the way down>")
        print(explain(db, FeedPosition(created_at=middle.created_at, id=middle.id)))
    finally:
        db.rollback()
        db.execute(text("TRUNCATE listings, users CASCADE"))
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
