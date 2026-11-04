"""E4.4: the demo seed script (scripts/seed_demo.py, spec: demo-seed-data).

Storage is stubbed: photos are "uploaded" to a dict. The seeded feed is walked through the real
GET /listings, so these also re-check the feed rules (no duplicates, no sold or draft listings)
on data spread over three pages.
"""

import importlib.util
import io
import re
import uuid
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import storage
from app.main import app
from app.models import Category, Listing, ListingImage, User
from app.routers.listings import _is_own_storage_path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "seed_demo.py"
_spec = importlib.util.spec_from_file_location("seed_demo", _SCRIPT)
seed_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_demo)

DATA = seed_demo.load_data()
PAGE_SIZE = 20  # the feed's default limit
NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)


def by_status(status: str) -> list[dict]:
    return [entry for entry in DATA["listings"] if entry["status"] == status]


def image_bytes(color: tuple[int, int, int], size=(64, 48), fmt="PNG", exif=None) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, fmt, **({"exif": exif} if exif else {}))
    return out.getvalue()


def with_fake_photos(data: dict) -> dict:
    """The real content, with every listing given one photo source that fake_read() can serve,
    so the database tests don't depend on the network."""
    listings = [
        {**entry, "photos": [{"source": entry["slug"], "credit": "x"}]}
        for entry in data["listings"]
    ]
    return {**data, "listings": listings}


def fake_read(source: str) -> bytes:
    # A different colour per source, so every photo gets its own content-addressed path.
    digest = uuid.uuid5(uuid.NAMESPACE_URL, source).bytes
    return image_bytes((digest[0], digest[1], digest[2]))


@pytest.fixture
def bucket(monkeypatch) -> dict[str, bytes]:
    """A fake listing-photos bucket: path -> bytes."""
    files: dict[str, bytes] = {}
    monkeypatch.setattr(storage, "object_exists", lambda path: path in files)
    monkeypatch.setattr(
        storage, "upload_object", lambda path, data, _type: files.__setitem__(path, data)
    )
    monkeypatch.setattr(
        storage,
        "list_folder",
        lambda folder: [p.removeprefix(f"{folder}/") for p in files if p.startswith(f"{folder}/")],
    )

    def delete(paths):
        for path in paths:
            files.pop(path, None)

    monkeypatch.setattr(storage, "delete_objects", delete)
    monkeypatch.setattr(
        storage,
        "remove_folder",
        lambda folder: delete([p for p in files if p.startswith(f"{folder}/")]),
    )
    return files


@pytest.fixture
def run_seed(db_session, bucket):
    """Seed like main() does, with fake photos: upload, then the database."""

    def _run(now: datetime = NOW, data: dict | None = None):
        data = data or with_fake_photos(DATA)
        photos = seed_demo.prepare_photos(data, read=fake_read)
        seed_demo.upload_photos(photos)
        seed_demo.seed_database(db_session, data, photos, now)
        return photos

    return _run


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def viewer(make_token):
    return {
        "Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='viewer@creighton.edu')}"
    }


def walk(client, headers) -> list[list[str]]:
    """Every page of the feed, as lists of ids."""
    pages, cursor = [], None
    while True:
        r = client.get("/listings", headers=headers, params={"cursor": cursor} if cursor else {})
        assert r.status_code == 200
        body = r.json()
        pages.append([item["id"] for item in body["items"]])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages


def ids(entries: list[dict]) -> set[str]:
    return {str(seed_demo.listing_id(entry["slug"])) for entry in entries}


# --- The content (no database) ----------------------------------------------------------------


def test_dataset_contents():
    active = by_status("active")
    assert len(active) >= 40
    assert len(by_status("sold")) >= 3
    assert len(by_status("draft")) >= 3
    assert sum(entry["price_cents"] == 0 for entry in active) >= 1
    slugs = [entry["slug"] for entry in DATA["listings"]]
    assert len(slugs) == len(set(slugs))
    sellers = {seller["key"] for seller in DATA["sellers"]}
    assert {entry["seller"] for entry in DATA["listings"]} <= sellers


def test_every_starter_category_has_active_listings():
    starter = {"furniture", "electronics", "textbooks", "clothing", "kitchen", "decor", "other"}
    assert {entry["category"] for entry in by_status("active")} == starter


def test_no_placeholder_text():
    for entry in DATA["listings"]:
        text = f"{entry['title']} {entry['description']}"
        assert not re.search(r"test|lorem|ipsum", text, re.IGNORECASE), entry["slug"]


def test_every_active_listing_has_credited_photos():
    for entry in DATA["listings"]:
        if entry["status"] == "active":
            assert 1 <= len(entry["photos"]) <= 3, entry["slug"]
        for photo in entry["photos"]:
            assert photo["source"] and photo["credit"], entry["slug"]


def test_sold_and_drafts_fall_on_every_later_page():
    """Sorted by age like the feed, each page after the first spans an age range; at least one
    sold and one draft listing must fall in each, so hiding them is checked on later pages."""
    ages = sorted(entry["age_hours"] for entry in by_status("active"))
    starts = ages[::PAGE_SIZE] + [float("inf")]
    for page in range(1, len(starts) - 1):
        low, high = starts[page], starts[page + 1]
        for status in ("sold", "draft"):
            assert any(low <= entry["age_hours"] < high for entry in by_status(status)), (
                page + 1,
                status,
            )


def test_an_equal_timestamp_pair_straddles_the_first_page_boundary():
    ages = sorted(entry["age_hours"] for entry in by_status("active"))
    assert ages[PAGE_SIZE - 1] == ages[PAGE_SIZE]


# --- Photos and guards (no database) -----------------------------------------------------------


def test_prepare_photo_matches_the_upload_pipeline():
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotated 90°, so the result must come out upright (portrait)
    exif[0x010F] = "Camera maker"
    raw = image_bytes((200, 100, 50), size=(3200, 2400), fmt="JPEG", exif=exif.tobytes())
    jpeg = seed_demo.prepare_photo(raw)
    with Image.open(io.BytesIO(jpeg)) as image:
        assert image.format == "JPEG"
        assert image.size == (1200, 1600)
        assert not image.getexif()
    assert len(jpeg) < 4 * 1024 * 1024


def test_photo_paths_are_accepted_by_the_api_and_content_addressed():
    listing = Listing(id=seed_demo.listing_id("kallax-shelf"))
    path = seed_demo.photo_path(listing.id, b"one")
    assert _is_own_storage_path(listing, path)
    assert seed_demo.photo_path(listing.id, b"one") == path
    assert seed_demo.photo_path(listing.id, b"two") != path


def test_a_broken_photo_stops_before_any_change():
    def broken(_source):
        raise OSError("404")

    with pytest.raises(SystemExit, match="kallax-shelf"):
        seed_demo.prepare_photos(with_fake_photos(DATA), read=broken)


def target(**overrides) -> Namespace:
    return Namespace(
        **{"database_url": "", "shared": False, "yes": False, "remove": False, **overrides}
    )


SHARED_URL = "postgresql://postgres.x:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
LOCAL_URL = "postgresql://renest_test:renest_test@localhost:5433/renest_test"


@pytest.mark.parametrize(
    "args",
    [
        target(),
        target(database_url=SHARED_URL),
        target(database_url=SHARED_URL, shared=True),
        target(database_url=SHARED_URL, yes=True),
        target(database_url=LOCAL_URL, shared=True, yes=True),
    ],
)
def test_guards_refuse(args):
    assert seed_demo.check_target(args) is not None


@pytest.mark.parametrize(
    "args", [target(database_url=LOCAL_URL), target(database_url=SHARED_URL, shared=True, yes=True)]
)
def test_guards_allow(args):
    assert seed_demo.check_target(args) is None


def test_main_without_a_target_changes_nothing(monkeypatch):
    monkeypatch.setattr(seed_demo, "create_engine", lambda *_: pytest.fail("connected"))
    with pytest.raises(SystemExit):
        seed_demo.main([])
    with pytest.raises(SystemExit):
        seed_demo.main(["--database-url", SHARED_URL])


# --- Seeding a database ------------------------------------------------------------------------


@pytest.mark.requires_db
def test_feed_walk_returns_every_active_listing_once_and_nothing_hidden(run_seed, client, viewer):
    run_seed()
    pages = walk(client, viewer)
    seen = [listing for page in pages for listing in page]
    assert len(seen) == len(set(seen))
    assert set(seen) == ids(by_status("active"))
    assert not set(seen) & ids(by_status("sold") + by_status("draft"))
    assert len(pages) == 3


@pytest.mark.requires_db
def test_equal_timestamps_split_across_the_first_page_boundary(run_seed, client, viewer):
    run_seed()
    pages = walk(client, viewer)
    ages = {str(seed_demo.listing_id(e["slug"])): e["age_hours"] for e in by_status("active")}
    assert ages[pages[0][-1]] == ages[pages[1][0]]


@pytest.mark.requires_db
def test_every_seeded_active_listing_has_a_cover_photo(run_seed, client, viewer):
    run_seed()
    r = client.get("/listings", headers=viewer, params={"limit": 50})
    assert all(item["cover_image_url"] for item in r.json()["items"])


@pytest.mark.requires_db
def test_posting_times_are_relative_to_the_run(run_seed, db_session):
    run_seed(now=NOW)
    times = [row.created_at for row in db_session.query(Listing.created_at)]
    assert NOW - max(times) < timedelta(days=1)
    assert timedelta(days=25) <= NOW - min(times) <= timedelta(days=28)


@pytest.mark.requires_db
def test_running_twice_converges(run_seed, db_session, bucket, client, viewer):
    run_seed(now=NOW)
    counts = (
        db_session.query(Listing).count(),
        db_session.query(ListingImage).count(),
        len(bucket),
    )
    run_seed(now=NOW + timedelta(days=3))
    db_session.expire_all()
    assert (
        db_session.query(Listing).count(),
        db_session.query(ListingImage).count(),
        len(bucket),
    ) == counts
    newest = max(row.created_at for row in db_session.query(Listing.created_at))
    assert newest > NOW + timedelta(days=2)  # times refreshed for the new run
    seen = [listing for page in walk(client, viewer) for listing in page]
    assert len(seen) == len(set(seen)) == len(by_status("active"))


@pytest.mark.requires_db
def test_real_users_and_listings_are_untouched(run_seed, db_session):
    real = User(id=uuid.uuid4(), email="real@creighton.edu", display_name="Real Student")
    db_session.add(real)
    category = db_session.query(Category.id).first()[0]
    listings = [
        Listing(
            id=uuid.uuid4(),
            seller_id=real.id,
            title=title,
            price_cents=500,
            category_id=category,
            status=status,
        )
        for title, status in [("My lamp", "active"), ("My draft", "draft")]
    ]
    db_session.add_all(listings)
    db_session.flush()
    db_session.add(
        ListingImage(
            listing_id=listings[0].id, storage_path=f"listings/{listings[0].id}/a.jpg", position=0
        )
    )
    db_session.commit()

    run_seed()
    run_seed()
    seed_demo.remove_demo_data(db_session, with_fake_photos(DATA), shared=True)
    db_session.expire_all()

    assert db_session.get(User, real.id).display_name == "Real Student"
    assert {(row.title, row.status) for row in db_session.query(Listing)} == {
        ("My lamp", "active"),
        ("My draft", "draft"),
    }
    assert db_session.query(ListingImage).count() == 1


@pytest.mark.requires_db
def test_demo_sellers_use_reserved_emails_and_a_new_sign_up_works(
    run_seed, db_session, client, make_token
):
    run_seed()
    emails = [row.email for row in db_session.query(User.email)]
    assert emails and all(email.endswith("@renest.invalid") for email in emails)

    token = make_token(sub=str(uuid.uuid4()), email="newstudent@creighton.edu")
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.requires_db
def test_shared_cleanup_deletes_only_unused_demo_photos(run_seed, bucket):
    data = with_fake_photos(DATA)
    run_seed(data=data)
    stray = f"listings/{seed_demo.listing_id('kallax-shelf')}/{uuid.uuid4()}.jpg"
    other = f"listings/{uuid.uuid4()}/{uuid.uuid4()}.jpg"  # someone else's listing
    bucket[stray] = bucket[other] = b"old"
    photos = run_seed(data=data)
    assert seed_demo.delete_unused_photos(data, photos) == 1
    assert stray not in bucket and other in bucket


@pytest.mark.requires_db
def test_remove_deletes_all_demo_rows_and_photos(run_seed, db_session, bucket):
    run_seed()
    seed_demo.remove_demo_data(db_session, with_fake_photos(DATA), shared=True)
    assert db_session.query(Listing).count() == 0
    assert db_session.query(User).count() == 0
    assert bucket == {}


# --- scripts/check_feed.py ---------------------------------------------------------------------

_CHECK = Path(__file__).resolve().parent.parent / "scripts" / "check_feed.py"
_check_spec = importlib.util.spec_from_file_location("check_feed", _CHECK)
check_feed = importlib.util.module_from_spec(_check_spec)
_check_spec.loader.exec_module(check_feed)


@pytest.fixture
def check(monkeypatch, viewer, capsys):
    """Run check_feed.main() against the app in-process; returns (exit code, output)."""
    monkeypatch.setattr(
        check_feed.httpx, "Client", lambda **kw: TestClient(app, headers=kw["headers"])
    )
    token = viewer["Authorization"].removeprefix("Bearer ")

    def _run():
        with pytest.raises(SystemExit) as exit_:
            check_feed.main(["--api", "http://testserver", "--token", token])
        return exit_.value.code, capsys.readouterr().out

    return _run


@pytest.mark.requires_db
def test_check_feed_passes_on_a_seeded_feed(run_seed, check):
    run_seed()
    code, out = check()
    assert code == 0
    assert "Duplicates: 0" in out
    assert "Sold or draft demo listings shown: 0" in out


@pytest.mark.requires_db
def test_check_feed_flags_a_hidden_listing_that_shows_up(run_seed, check, db_session):
    run_seed()
    db_session.get(Listing, seed_demo.listing_id("rice-cooker")).status = "active"  # a sold one
    db_session.commit()
    code, out = check()
    assert code == 1
    assert "rice-cooker (sold)" in out
