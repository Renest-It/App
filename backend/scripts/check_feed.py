"""Walk a deployed feed and check it against the demo seed (E4.4). Read-only: safe on production.

Run from backend/:

    TOKEN=$(python scripts/get_token.py) python scripts/check_feed.py --api https://<backend host>

The token is read from the TOKEN environment variable (or --token), so it stays out of the shell
history.

Requests GET /listings page by page until next_cursor is null, then reports the pages, the
total, any listing served twice, and any seeded sold or draft listing that showed up. Demo ids
are derived from scripts/demo_data/listings.json the same way seed_demo.py derives them, so no
database access is needed. Exits 1 if anything is wrong.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/, for seed_demo

import httpx  # noqa: E402

from seed_demo import listing_id, load_data  # noqa: E402

MAX_PAGES = 100  # a cursor bug could loop forever; no real feed is this long


def walk(api: str, token: str) -> list[list[str]]:
    """Every page of the feed, as lists of ids."""
    pages, cursor = [], None
    with httpx.Client(
        base_url=api.rstrip("/"), headers={"Authorization": f"Bearer {token}"}, timeout=30
    ) as client:
        while len(pages) < MAX_PAGES:
            response = client.get("/listings", params={"cursor": cursor} if cursor else {})
            response.raise_for_status()
            body = response.json()
            pages.append([item["id"] for item in body["items"]])
            cursor = body["next_cursor"]
            if cursor is None:
                return pages
    sys.exit(f"Stopped after {MAX_PAGES} pages: next_cursor never became null.")


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", required=True, help="the backend's base URL")
    parser.add_argument("--token", default=os.environ.get("TOKEN", ""), help="default: $TOKEN")
    args = parser.parse_args(argv)
    if not args.token:
        sys.exit("Set TOKEN to an access token (scripts/get_token.py), or pass --token.")

    pages = walk(args.api, args.token)
    seen = [listing for page in pages for listing in page]
    duplicates = sorted({listing for listing in seen if seen.count(listing) > 1})

    data = load_data()
    hidden = {str(listing_id(e["slug"])): e for e in data["listings"] if e["status"] != "active"}
    demo_active = {str(listing_id(e["slug"])) for e in data["listings"] if e["status"] == "active"}
    shown_hidden = [hidden[listing] for listing in seen if listing in hidden]
    missing_demo = demo_active - set(seen)

    print(f"Pages: {len(pages)} ({', '.join(str(len(page)) for page in pages)} listings)")
    print(f"Total: {len(seen)} listings, {len(demo_active & set(seen))} of them demo listings")
    print(f"Duplicates: {len(duplicates)}")
    for listing in duplicates:
        print(f"  {listing}")
    print(f"Sold or draft demo listings shown: {len(shown_hidden)}")
    for entry in shown_hidden:
        print(f"  {entry['slug']} ({entry['status']})")
    if missing_demo:
        print(f"Active demo listings missing: {len(missing_demo)} (was the seed run?)")

    sys.exit(1 if duplicates or shown_hidden or missing_demo else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
