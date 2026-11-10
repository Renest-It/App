"""Walk a deployed feed and check it against the demo seed (E4.4). Read-only: safe on production.

Run from backend/:

    TOKEN=$(python scripts/get_token.py) python scripts/check_feed.py --api https://<backend host>

The token is read from the TOKEN environment variable (or --token), so it stays out of the shell
history.

Requests GET /listings page by page until next_cursor is null, then reports the pages, the
total, any listing served twice, and any seeded sold or draft listing that showed up. Demo ids
are derived from scripts/demo_data/listings.json the same way seed_demo.py derives them, so no
database access is needed. Exits 1 if anything is wrong.

--all-categories (E5.3) repeats the walk once per seeded category (?category=<slug>), checking
the same things inside each filtered view, plus that every active demo listing in that category
shows up exactly once and that a hand-edited, unknown slug returns a clear 422 rather than a
silently empty feed.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/, for seed_demo

import httpx  # noqa: E402

from seed_demo import listing_id, load_data  # noqa: E402

MAX_PAGES = 100  # a cursor bug could loop forever; no real feed is this long


def walk(api: str, token: str, category: str | None = None) -> list[list[str]]:
    """Every page of the feed, as lists of ids. `category`, when given, is sent as the filter on
    every request, the same way the frontend does (E5.1/E5.2)."""
    pages, cursor = [], None
    params = {"category": category} if category else {}
    with httpx.Client(
        base_url=api.rstrip("/"), headers={"Authorization": f"Bearer {token}"}, timeout=30
    ) as client:
        while len(pages) < MAX_PAGES:
            request_params = {**params, **({"cursor": cursor} if cursor else {})}
            response = client.get("/listings", params=request_params)
            response.raise_for_status()
            body = response.json()
            pages.append([item["id"] for item in body["items"]])
            cursor = body["next_cursor"]
            if cursor is None:
                return pages
    sys.exit(f"Stopped after {MAX_PAGES} pages: next_cursor never became null.")


def check_unknown_category(api: str, token: str) -> bool:
    """A hand-edited slug that doesn't exist should fail clearly (422 unknown_category), never
    come back as an empty page (E5.3 URL-behaviour criterion). Returns whether it passed."""
    with httpx.Client(
        base_url=api.rstrip("/"), headers={"Authorization": f"Bearer {token}"}, timeout=30
    ) as client:
        response = client.get("/listings", params={"category": "not-a-real-category-xyz"})
    ok = response.status_code == 422 and response.json().get("code") == "unknown_category"
    status = "ok" if ok else "FAILED"
    print(f"Unknown category slug -> {response.status_code} ({status})")
    if not ok:
        print(f"  body: {response.text[:200]}")
    return ok


def check_feed(
    pages: list[list[str]],
    data: dict,
    category: str | None,
    label: str,
) -> bool:
    """Report one feed's pages (unfiltered, or a single category) against the demo seed.
    Returns whether everything was clean."""
    seen = [listing for page in pages for listing in page]
    duplicates = sorted({listing for listing in seen if seen.count(listing) > 1})

    listings = data["listings"]
    if category is not None:
        listings = [e for e in listings if e["category"] == category]
    hidden = {str(listing_id(e["slug"])): e for e in listings if e["status"] != "active"}
    demo_active = {str(listing_id(e["slug"])) for e in listings if e["status"] == "active"}
    shown_hidden = [hidden[listing] for listing in seen if listing in hidden]
    missing_demo = demo_active - set(seen)

    print(f"--- {label} ---")
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
        for slug_id in sorted(missing_demo):
            print(f"  {slug_id}")

    return not (duplicates or shown_hidden or missing_demo)


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", required=True, help="the backend's base URL")
    parser.add_argument("--token", default=os.environ.get("TOKEN", ""), help="default: $TOKEN")
    parser.add_argument(
        "--category",
        help="also walk this one category's filtered feed (slug, e.g. furniture)",
    )
    parser.add_argument(
        "--all-categories",
        action="store_true",
        help="walk every seeded category's filtered feed, plus the unknown-category check (E5.3)",
    )
    args = parser.parse_args(argv)
    if not args.token:
        sys.exit("Set TOKEN to an access token (scripts/get_token.py), or pass --token.")
    if args.category and args.all_categories:
        sys.exit("Use either --category or --all-categories, not both.")

    data = load_data()
    ok = True

    ok &= check_feed(walk(args.api, args.token), data, None, "unfiltered feed")

    if args.category:
        ok &= check_feed(
            walk(args.api, args.token, args.category), data, args.category, f"category={args.category}"
        )
    elif args.all_categories:
        categories = sorted({e["category"] for e in data["listings"]})
        print(f"\nSeeded categories: {', '.join(categories)}\n")
        for category in categories:
            ok &= check_feed(
                walk(args.api, args.token, category), data, category, f"category={category}"
            )
        print("--- unknown category slug ---")
        ok &= check_unknown_category(args.api, args.token)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1:])