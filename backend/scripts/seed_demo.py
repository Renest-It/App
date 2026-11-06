"""Seed the demo dataset: realistic listings with photos for the home feed and the E7 demo (E4.4).

Run from backend/, with requirements-dev.txt installed (it needs Pillow):

    # A local database, e.g. the test container. Runs straight away.
    python scripts/seed_demo.py --database-url postgresql://renest_test:renest_test@localhost:5433/renest_test

    # The shared Supabase database. Only with the team's agreement (see backend/README.md).
    python scripts/seed_demo.py --database-url "$SHARED_DATABASE_URL" --shared --yes

    # Take the demo data out again (add --shared --yes for the shared database).
    python scripts/seed_demo.py --database-url ... --remove

The content is in scripts/demo_data/listings.json. The database is never read from .env: it must
be named with --database-url, so the shared one can't be seeded by accident. Storage is always
the project's listing-photos bucket (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env).

The script only touches its own rows: the demo sellers (emails at renest.invalid, no sign-in
account) and their listings. Re-running it replaces them, so it always ends in the same state,
with posting times counted back from the new run.

Photos are content-addressed (listings/{listing_id}/{hash-based uuid}.jpg), so re-running
uploads only new or changed photos. A local run never deletes from storage, since the shared
database may use the same files; a --shared run removes demo photos nothing references any more.
"""

import argparse
import hashlib
import io
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/, for `app`

import httpx  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import storage  # noqa: E402
from app.models import Category, Listing, ListingImage, User  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent / "demo_data"
DATA_FILE = DATA_DIR / "listings.json"

# Never change: every demo id is derived from it, which is how re-runs find their own rows.
DEMO_NAMESPACE = uuid.UUID("6d2f1e0a-4c1b-5e8a-9f3d-2b7c8e1a4d55")

# The same limits as the browser's upload pipeline (frontend/src/listings/processImage.ts).
MAX_DIMENSION = 1600
JPEG_QUALITY_STEPS = [80, 60, 45, 30]
TARGET_MAX_BYTES = 4 * 1024 * 1024


def seller_id(key: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"seller:{key}")


def seller_email(key: str) -> str:
    # .invalid can never be a real address (RFC 2606), so it can't collide with a sign-up.
    return f"demo-seller-{key}@renest.invalid"


def listing_id(slug: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"listing:{slug}")


def photo_path(listing: uuid.UUID, data: bytes) -> str:
    """listings/{listing_id}/{uuid}.jpg, the shape the API accepts, with the uuid derived from the
    photo's bytes: an unchanged photo keeps its path, a changed one gets a new path (so no stale
    CDN copy is ever served)."""
    return f"listings/{listing}/{uuid.uuid5(listing, hashlib.sha256(data).hexdigest())}.jpg"


def load_data(path: Path = DATA_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prepare_photo(raw: bytes) -> bytes:
    """Resize and re-encode like an app upload: upright, longest side at most 1600px, JPEG under
    4 MB. Re-encoding drops all metadata, EXIF included."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
        for quality in JPEG_QUALITY_STEPS:
            out = io.BytesIO()
            image.save(out, "JPEG", quality=quality, optimize=True)
            if out.tell() <= TARGET_MAX_BYTES:
                return out.getvalue()
    raise ValueError("photo is still over 4 MB at the lowest quality")


def read_source(source: str) -> bytes:
    """An http(s) URL, or a file under demo_data/photos/."""
    if urlparse(source).scheme in ("http", "https"):
        response = httpx.get(source, follow_redirects=True, timeout=30)
        response.raise_for_status()
        return response.content
    return (DATA_DIR / "photos" / source).read_bytes()


@dataclass
class Photo:
    path: str
    data: bytes


def prepare_photos(data: dict, read=read_source) -> dict[str, list[Photo]]:
    """Every listing's photos, fetched and prepared, keyed by slug. Runs before any change, so a
    broken source stops the seed with nothing half done."""
    photos: dict[str, list[Photo]] = {}
    for entry in data["listings"]:
        if entry["status"] == "active" and not entry["photos"]:
            sys.exit(f"{entry['slug']}: active listings need at least one photo.")
        prepared = []
        for photo in entry["photos"]:
            try:
                jpeg = prepare_photo(read(photo["source"]))
            except Exception as e:  # any failure names the entry
                sys.exit(f"{entry['slug']}: couldn't prepare {photo['source']}: {e}")
            prepared.append(Photo(photo_path(listing_id(entry["slug"]), jpeg), jpeg))
        photos[entry["slug"]] = prepared
    return photos


def demo_seller_ids(data: dict) -> list[uuid.UUID]:
    return [seller_id(seller["key"]) for seller in data["sellers"]]


def seed_database(db: Session, data: dict, photos: dict[str, list[Photo]], now: datetime) -> None:
    """Replace the demo sellers' listings with the ones in `data`, in one transaction."""
    categories = {slug: id_ for id_, slug in db.query(Category.id, Category.slug)}
    for entry in data["listings"]:
        if entry["category"] not in categories:
            sys.exit(f"{entry['slug']}: unknown category {entry['category']!r}.")

    for seller in data["sellers"]:
        values = {
            "id": seller_id(seller["key"]),
            "email": seller_email(seller["key"]),
            "display_name": seller["display_name"],
        }
        db.execute(
            insert(User)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[User.id], set_={"display_name": values["display_name"]}
            )
        )

    # Images go with their listings (ON DELETE CASCADE).
    db.query(Listing).filter(Listing.seller_id.in_(demo_seller_ids(data))).delete(
        synchronize_session=False
    )

    for entry in data["listings"]:
        listing = listing_id(entry["slug"])
        db.add(
            Listing(
                id=listing,
                seller_id=seller_id(entry["seller"]),
                title=entry["title"],
                description=entry["description"],
                price_cents=entry["price_cents"],
                category_id=categories[entry["category"]],
                status=entry["status"],
                created_at=now - timedelta(hours=entry["age_hours"]),
            )
        )
        for position, photo in enumerate(photos[entry["slug"]]):
            db.add(ListingImage(listing_id=listing, storage_path=photo.path, position=position))
    db.commit()


def upload_photos(photos: dict[str, list[Photo]]) -> int:
    """Upload the photos storage doesn't have yet, and return how many that was. Runs before the
    database step, so no listing ever points at a missing photo."""
    uploaded = 0
    for prepared in photos.values():
        for photo in prepared:
            if not storage.object_exists(photo.path):
                storage.upload_object(photo.path, photo.data, "image/jpeg")
                uploaded += 1
    return uploaded


def delete_unused_photos(data: dict, photos: dict[str, list[Photo]]) -> int:
    """Delete files in the demo listings' folders that no listing uses any more (after a photo
    changed), and return how many. Only for the shared database: see the module docstring."""
    deleted = 0
    for entry in data["listings"]:
        folder = f"listings/{listing_id(entry['slug'])}"
        keep = {photo.path for photo in photos[entry["slug"]]}
        stale = [f"{folder}/{name}" for name in storage.list_folder(folder)]
        stale = [path for path in stale if path not in keep]
        storage.delete_objects(stale)
        deleted += len(stale)
    return deleted


def remove_demo_data(db: Session, data: dict, shared: bool) -> None:
    """Delete the demo sellers, their listings and (with `shared`) their photos."""
    ids = demo_seller_ids(data)
    listing_ids = [row.id for row in db.query(Listing.id).filter(Listing.seller_id.in_(ids))]
    db.query(Listing).filter(Listing.seller_id.in_(ids)).delete(synchronize_session=False)
    db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    if shared:
        for listing in listing_ids:
            storage.remove_folder(f"listings/{listing}")


def is_supabase_host(database_url: str) -> bool:
    host = (urlparse(database_url).hostname or "").lower()
    return host.endswith(".supabase.co") or host.endswith(".supabase.com")


def check_target(args: argparse.Namespace) -> str | None:
    """Why the script must not run with these arguments, or None if it may."""
    if not args.database_url:
        return "Name the database with --database-url (it is never read from .env)."
    if is_supabase_host(args.database_url) and not (args.shared and args.yes):
        return (
            "That's the shared Supabase database. Seeding it needs the team's agreement; "
            "then run again with --shared --yes."
        )
    if args.shared and not is_supabase_host(args.database_url):
        return "--shared is only for the shared Supabase database."
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database-url", default="", help="the database to seed (required)")
    parser.add_argument("--shared", action="store_true", help="the target is the shared database")
    parser.add_argument("--yes", action="store_true", help="confirm changing the shared database")
    parser.add_argument("--remove", action="store_true", help="delete the demo data instead")
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    problem = check_target(args)
    if problem:
        sys.exit(problem)

    data = load_data()
    statuses = [entry["status"] for entry in data["listings"]]
    target = "the SHARED database" if args.shared else "a local database"
    if args.remove:
        print(f"Removing the {len(data['sellers'])} demo sellers and their listings from {target}.")
    else:
        print(
            f"Seeding {target}: {len(data['sellers'])} demo sellers, "
            f"{statuses.count('active')} active, {statuses.count('sold')} sold and "
            f"{statuses.count('draft')} draft listings, "
            f"{sum(len(entry['photos']) for entry in data['listings'])} photos."
        )

    engine = create_engine(args.database_url)
    with Session(engine) as db:
        if args.remove:
            remove_demo_data(db, data, args.shared)
            print("Done.")
            return
        photos = prepare_photos(data)
        uploaded = upload_photos(photos)
        seed_database(db, data, photos, datetime.now(timezone.utc))
    deleted = delete_unused_photos(data, photos) if args.shared else 0
    print(f"Done. Uploaded {uploaded} new photos, removed {deleted} unused ones.")


if __name__ == "__main__":
    main(sys.argv[1:])
