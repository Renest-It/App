"""E2.3: upload URLs and recording uploaded photos, and E3.3: adding photos to published
listings and deleting photos (docs/api/listings.md).

Supabase Storage is replaced by FakeStorage: tests never make network calls (conftest.py).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.models import Category, ListingImage

pytestmark = pytest.mark.requires_db

STORAGE = "https://test-project.supabase.co/storage/v1"


class FakeStorage:
    def __init__(self):
        self.uploaded: set[str] = set()
        self.signed: list[str] = []
        self.deleted: list[str] = []
        self.down = False

    def create_signed_upload_url(self, storage_path: str) -> str:
        if self.down:
            raise storage.StorageUnavailable("simulated outage")
        self.signed.append(storage_path)
        return f"{STORAGE}/object/upload/sign/listing-photos/{storage_path}?token=fake"

    def object_exists(self, storage_path: str) -> bool:
        if self.down:
            raise storage.StorageUnavailable("simulated outage")
        return storage_path in self.uploaded

    def delete_objects(self, storage_paths: list[str]) -> None:
        if self.down:
            raise storage.StorageUnavailable("simulated outage")
        self.deleted.extend(storage_paths)
        self.uploaded.difference_update(storage_paths)


@pytest.fixture
def fake_storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(storage, "create_signed_upload_url", fake.create_signed_upload_url)
    monkeypatch.setattr(storage, "object_exists", fake.object_exists)
    monkeypatch.setattr(storage, "delete_objects", fake.delete_objects)
    return fake


@pytest.fixture
def client(fake_storage):
    return TestClient(app)


@pytest.fixture
def category_id(db_session):
    return db_session.query(Category.id).order_by(Category.id).first()[0]


@pytest.fixture
def seller(make_token):
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='seller@creighton.edu')}"}


@pytest.fixture
def other(make_token):
    return {"Authorization": f"Bearer {make_token(sub=str(uuid.uuid4()), email='other@creighton.edu')}"}


@pytest.fixture
def draft(client, seller, category_id):
    def _draft(headers=None) -> str:
        body = {"title": "Desk lamp", "price_cents": 1500, "category_id": category_id}
        r = client.post("/listings", headers=headers or seller, json=body)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    return _draft


@pytest.fixture
def upload(client, seller, fake_storage):
    """Get an upload URL for a listing and "upload" the file. Returns its storage_path."""

    def _upload(listing_id: str, content_type: str = "image/jpeg") -> str:
        r = client.post(
            f"/listings/{listing_id}/images/upload-url",
            headers=seller,
            json={"content_type": content_type},
        )
        assert r.status_code == 200, r.text
        storage_path = r.json()["storage_path"]
        fake_storage.uploaded.add(storage_path)
        return storage_path

    return _upload


@pytest.fixture
def register(client, seller):
    def _register(listing_id: str, storage_path: str, position: int, headers=None):
        return client.post(
            f"/listings/{listing_id}/images",
            headers=headers or seller,
            json={"storage_path": storage_path, "position": position},
        )

    return _register


def publish(client, seller, listing_id):
    r = client.post(f"/listings/{listing_id}/publish", headers=seller)
    assert r.status_code == 200, r.text


def mark_sold(client, seller, listing_id):
    r = client.post(f"/listings/{listing_id}/sold", headers=seller)
    assert r.status_code == 200, r.text


def image_rows(db_session, listing_id):
    db_session.expire_all()
    return (
        db_session.query(ListingImage)
        .filter_by(listing_id=uuid.UUID(listing_id))
        .order_by(ListingImage.position)
        .all()
    )


# --- full flow ------------------------------------------------------------------------------


def test_full_flow_upload_url_then_register(client, seller, draft, upload, register):
    listing_id = draft()
    storage_path = upload(listing_id)

    r = register(listing_id, storage_path, 0)
    assert r.status_code == 201, r.text
    assert r.json()["position"] == 0
    assert r.json()["url"] == f"{STORAGE}/object/public/listing-photos/{storage_path}"

    images = client.get(f"/listings/{listing_id}", headers=seller).json()["images"]
    assert [image["id"] for image in images] == [r.json()["id"]]
    publish(client, seller, listing_id)


# --- upload URL -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content_type, extension",
    [("image/jpeg", "jpg"), ("image/png", "png"), ("image/webp", "webp")],
)
def test_upload_url_picks_a_random_path_in_the_listings_folder(
    client, seller, draft, fake_storage, content_type, extension
):
    listing_id = draft()
    r = client.post(
        f"/listings/{listing_id}/images/upload-url",
        headers=seller,
        json={"content_type": content_type},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    folder, name = body["storage_path"].rsplit("/", 1)
    stem, ext = name.split(".")
    assert folder == f"listings/{listing_id}"
    assert ext == extension
    uuid.UUID(stem)  # raises if the file name isn't a uuid
    assert body["upload_url"].startswith(f"{STORAGE}/object/upload/sign/listing-photos/")
    assert body["expires_in"] == 7200
    assert fake_storage.signed == [body["storage_path"]]


def test_upload_url_paths_are_never_reused(draft, upload):
    listing_id = draft()
    assert upload(listing_id) != upload(listing_id)


@pytest.mark.parametrize("content_type", ["image/gif", "image/heic", "text/html", ""])
def test_upload_url_rejects_other_file_types(client, seller, draft, fake_storage, content_type):
    r = client.post(
        f"/listings/{draft()}/images/upload-url", headers=seller, json={"content_type": content_type}
    )
    assert r.status_code == 422
    assert r.json()["code"] == "unsupported_content_type"
    assert fake_storage.signed == []


def test_non_seller_upload_url_for_an_active_listing_is_404(
    client, seller, other, draft, upload, register
):
    # 404, not 403: a 403 would confirm the listing exists (get_owned_listing, ADR 0010).
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    publish(client, seller, listing_id)
    r = client.post(
        f"/listings/{listing_id}/images/upload-url", headers=other, json={"content_type": "image/jpeg"}
    )
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


def test_non_seller_upload_url_for_a_draft_is_404(client, other, draft, fake_storage):
    # 404, not 403: a 403 would reveal that the draft exists.
    r = client.post(
        f"/listings/{draft()}/images/upload-url", headers=other, json={"content_type": "image/jpeg"}
    )
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"
    assert fake_storage.signed == []


def test_upload_url_for_a_published_listing_is_allowed(client, seller, draft, upload, register):
    # E3.3: "draft only" became "seller and not sold".
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    publish(client, seller, listing_id)
    r = client.post(
        f"/listings/{listing_id}/images/upload-url", headers=seller, json={"content_type": "image/jpeg"}
    )
    assert r.status_code == 200
    assert r.json()["storage_path"].startswith(f"listings/{listing_id}/")


def test_upload_url_for_a_sold_listing_is_409(client, seller, draft, upload, register, fake_storage):
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    publish(client, seller, listing_id)
    mark_sold(client, seller, listing_id)
    signed_before = list(fake_storage.signed)
    r = client.post(
        f"/listings/{listing_id}/images/upload-url", headers=seller, json={"content_type": "image/jpeg"}
    )
    assert r.status_code == 409
    assert r.json()["code"] == "listing_sold"
    assert fake_storage.signed == signed_before


def test_upload_url_when_storage_is_down_is_503(client, seller, draft, fake_storage):
    fake_storage.down = True
    r = client.post(
        f"/listings/{draft()}/images/upload-url", headers=seller, json={"content_type": "image/jpeg"}
    )
    assert r.status_code == 503
    assert r.json()["code"] == "storage_unavailable"


# --- register -------------------------------------------------------------------------------


def test_path_in_another_listings_folder_is_rejected(draft, upload, register, db_session):
    mine, theirs = draft(), draft()
    their_photo = upload(theirs)
    r = register(mine, their_photo, 0)
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_storage_path"
    assert image_rows(db_session, mine) == []


@pytest.mark.parametrize(
    "make_path",
    [
        lambda mine, theirs: f"listings/{mine}/../{theirs}/{uuid.uuid4()}.jpg",
        lambda mine, theirs: f"listings/{mine}/{uuid.uuid4()}.gif",
        lambda mine, theirs: f"listings/{mine}/photo.jpg",
        lambda mine, theirs: f"listings/{mine}/sub/{uuid.uuid4()}.jpg",
        lambda mine, theirs: f"/listings/{mine}/{uuid.uuid4()}.jpg",
        lambda mine, theirs: f"{mine}/{uuid.uuid4()}.jpg",
    ],
)
def test_malformed_paths_are_rejected(draft, register, fake_storage, make_path):
    mine, theirs = draft(), draft()
    path = make_path(mine, theirs)
    fake_storage.uploaded.add(path)  # even if something exists there, the path is refused
    r = register(mine, path, 0)
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_storage_path"


def test_path_where_no_file_exists_is_rejected(client, seller, draft, register, db_session):
    listing_id = draft()
    r = client.post(
        f"/listings/{listing_id}/images/upload-url", headers=seller, json={"content_type": "image/jpeg"}
    )
    never_uploaded = r.json()["storage_path"]
    r = register(listing_id, never_uploaded, 0)
    assert r.status_code == 422
    assert r.json()["code"] == "upload_not_found"
    assert image_rows(db_session, listing_id) == []


def test_seventh_photo_is_rejected(draft, upload, register, db_session):
    listing_id = draft()
    for position in range(6):
        assert register(listing_id, upload(listing_id), position).status_code == 201

    seventh = upload(listing_id)
    r = register(listing_id, seventh, 6)
    assert r.status_code == 422  # positions run 0–5
    for position in range(6):  # and every one of those is taken
        r = register(listing_id, seventh, position)
        assert r.status_code == 409
        assert r.json()["code"] == "position_taken"
    assert len(image_rows(db_session, listing_id)) == 6


def test_registering_on_a_published_listing_is_allowed(
    client, seller, draft, upload, register, db_session
):
    # E3.3: "draft only" became "seller and not sold".
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    publish(client, seller, listing_id)
    r = register(listing_id, upload(listing_id), 1)
    assert r.status_code == 201
    assert [i.position for i in image_rows(db_session, listing_id)] == [0, 1]


def test_registering_on_a_sold_listing_is_409(client, seller, draft, upload, register, db_session):
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    late_photo = upload(listing_id)
    publish(client, seller, listing_id)
    mark_sold(client, seller, listing_id)
    r = register(listing_id, late_photo, 1)
    assert r.status_code == 409
    assert r.json()["code"] == "listing_sold"
    assert len(image_rows(db_session, listing_id)) == 1


def test_registering_still_checks_the_upload_exists_on_a_published_listing(
    client, seller, draft, upload, register, db_session
):
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    publish(client, seller, listing_id)
    r = client.post(
        f"/listings/{listing_id}/images/upload-url", headers=seller, json={"content_type": "image/jpeg"}
    )
    never_uploaded = r.json()["storage_path"]
    r = register(listing_id, never_uploaded, 1)
    assert r.status_code == 422
    assert r.json()["code"] == "upload_not_found"


def test_seventh_photo_on_an_active_listing_is_rejected(
    client, seller, draft, upload, register, db_session
):
    listing_id = draft()
    for position in range(6):
        assert register(listing_id, upload(listing_id), position).status_code == 201
    publish(client, seller, listing_id)

    seventh = upload(listing_id)
    assert register(listing_id, seventh, 6).status_code == 422  # positions run 0–5
    for position in range(6):  # and every one of those is taken
        assert register(listing_id, seventh, position).status_code == 409
    assert len(image_rows(db_session, listing_id)) == 6


def test_non_seller_registering_on_an_active_listing_is_404(
    client, seller, other, draft, upload, register
):
    # 404, not 403: a 403 would confirm the listing exists (get_owned_listing, ADR 0010).
    listing_id = draft()
    photo = upload(listing_id)
    register(listing_id, photo, 0)
    publish(client, seller, listing_id)
    r = register(listing_id, photo, 1, headers=other)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


def test_non_seller_registering_on_a_draft_is_404(draft, upload, register, other):
    listing_id = draft()
    r = register(listing_id, upload(listing_id), 0, headers=other)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


def test_identical_retry_returns_the_existing_photo(draft, upload, register, db_session):
    listing_id = draft()
    photo = upload(listing_id)
    first = register(listing_id, photo, 0)
    retry = register(listing_id, photo, 0)
    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json() == first.json()
    assert len(image_rows(db_session, listing_id)) == 1


def test_a_different_photo_at_a_taken_position_is_409(draft, upload, register):
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    r = register(listing_id, upload(listing_id), 0)
    assert r.status_code == 409
    assert r.json()["code"] == "position_taken"


def test_one_photo_cant_fill_two_positions(draft, upload, register, db_session):
    listing_id = draft()
    photo = upload(listing_id)
    register(listing_id, photo, 0)
    r = register(listing_id, photo, 1)
    assert r.status_code == 409
    assert r.json()["code"] == "position_taken"
    assert len(image_rows(db_session, listing_id)) == 1


def test_register_when_storage_is_down_is_503(draft, upload, register, fake_storage, db_session):
    listing_id = draft()
    photo = upload(listing_id)
    fake_storage.down = True
    r = register(listing_id, photo, 0)
    assert r.status_code == 503
    assert r.json()["code"] == "storage_unavailable"
    assert image_rows(db_session, listing_id) == []


def test_unknown_listing_is_404(client, seller, register):
    missing = str(uuid.uuid4())
    r = register(missing, f"listings/{missing}/{uuid.uuid4()}.jpg", 0)
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


# --- delete a photo (E3.3) ----------------------------------------------------------------


@pytest.fixture
def with_photos(client, seller, draft, upload, register):
    """A listing with `count` photos at positions 0.., brought to `status`. Returns
    (listing_id, [image ids in position order])."""

    def _with_photos(count: int, status: str = "active"):
        listing_id = draft()
        ids = []
        for position in range(count):
            r = register(listing_id, upload(listing_id), position)
            assert r.status_code == 201, r.text
            ids.append(r.json()["id"])
        if status in ("active", "sold"):
            publish(client, seller, listing_id)
        if status == "sold":
            mark_sold(client, seller, listing_id)
        return listing_id, ids

    return _with_photos


def delete_photo(client, headers, listing_id, image_id):
    return client.delete(f"/listings/{listing_id}/images/{image_id}", headers=headers)


@pytest.mark.parametrize("status", ["draft", "active"])
def test_delete_photo_removes_the_row_and_the_file(
    client, seller, with_photos, db_session, fake_storage, status
):
    listing_id, ids = with_photos(2, status)
    path = next(i.storage_path for i in image_rows(db_session, listing_id) if str(i.id) == ids[1])
    r = delete_photo(client, seller, listing_id, ids[1])
    assert r.status_code == 204
    assert r.content == b""
    assert [str(i.id) for i in image_rows(db_session, listing_id)] == [ids[0]]
    assert fake_storage.deleted == [path]


def test_positions_stay_contiguous_after_deleting_a_middle_photo(
    client, seller, with_photos, db_session
):
    listing_id, ids = with_photos(4)
    assert delete_photo(client, seller, listing_id, ids[1]).status_code == 204
    rows = image_rows(db_session, listing_id)
    assert [i.position for i in rows] == [0, 1, 2]
    assert [str(i.id) for i in rows] == [ids[0], ids[2], ids[3]]


def test_deleting_the_cover_makes_the_next_photo_the_cover(client, seller, with_photos):
    listing_id, ids = with_photos(3)
    assert delete_photo(client, seller, listing_id, ids[0]).status_code == 204
    images = client.get(f"/listings/{listing_id}", headers=seller).json()["images"]
    assert [(i["id"], i["position"]) for i in images] == [(ids[1], 0), (ids[2], 1)]
    feed = client.get("/listings", headers=seller).json()
    cover = next(item["cover_image_url"] for item in feed if item["id"] == listing_id)
    assert cover == images[0]["url"]


def test_deleting_the_last_photo_on_an_active_listing_is_422(
    client, seller, with_photos, db_session, fake_storage
):
    listing_id, ids = with_photos(1)
    r = delete_photo(client, seller, listing_id, ids[0])
    assert r.status_code == 422
    assert r.json()["code"] == "last_photo_required"
    assert len(image_rows(db_session, listing_id)) == 1
    assert fake_storage.deleted == []


def test_deleting_the_last_photo_on_a_draft_is_allowed(client, seller, with_photos, db_session):
    listing_id, ids = with_photos(1, "draft")
    assert delete_photo(client, seller, listing_id, ids[0]).status_code == 204
    assert image_rows(db_session, listing_id) == []


def test_deleting_a_photo_from_a_sold_listing_is_409(
    client, seller, with_photos, db_session, fake_storage
):
    listing_id, ids = with_photos(2, "sold")
    r = delete_photo(client, seller, listing_id, ids[0])
    assert r.status_code == 409
    assert r.json()["code"] == "listing_sold"
    assert len(image_rows(db_session, listing_id)) == 2
    assert fake_storage.deleted == []


@pytest.mark.parametrize("status", ["draft", "active", "sold"])
def test_non_seller_deleting_a_photo_is_404(
    client, other, with_photos, db_session, fake_storage, status
):
    listing_id, ids = with_photos(2, status)
    r = delete_photo(client, other, listing_id, ids[0])
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"
    assert len(image_rows(db_session, listing_id)) == 2
    assert fake_storage.deleted == []


@pytest.mark.parametrize("image_id", [str(uuid.uuid4()), "not-a-uuid"])
def test_unknown_or_malformed_image_id_is_404(client, seller, with_photos, image_id):
    listing_id, _ = with_photos(2)
    r = delete_photo(client, seller, listing_id, image_id)
    assert r.status_code == 404
    assert r.json()["code"] == "image_not_found"


def test_a_photo_from_another_listing_is_404(client, seller, with_photos, db_session):
    mine, _ = with_photos(2)
    theirs, their_ids = with_photos(2)
    r = delete_photo(client, seller, mine, their_ids[0])
    assert r.status_code == 404
    assert r.json()["code"] == "image_not_found"
    assert len(image_rows(db_session, theirs)) == 2


def test_deleting_a_photo_on_an_unknown_listing_is_404(client, seller):
    r = delete_photo(client, seller, uuid.uuid4(), uuid.uuid4())
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"


def test_delete_photo_still_succeeds_when_storage_fails(
    client, seller, with_photos, db_session, fake_storage, caplog
):
    listing_id, ids = with_photos(2)
    fake_storage.down = True
    with caplog.at_level("WARNING", logger="app.routers.listings"):
        r = delete_photo(client, seller, listing_id, ids[1])
    assert r.status_code == 204
    assert [str(i.id) for i in image_rows(db_session, listing_id)] == [ids[0]]
    assert f"listings/{listing_id}/" in caplog.text


def test_a_photo_can_be_added_back_after_one_is_deleted(
    client, seller, with_photos, upload, register, db_session
):
    # The edit page adds at the next free position, which is the number of photos now.
    listing_id, ids = with_photos(6)
    assert delete_photo(client, seller, listing_id, ids[2]).status_code == 204
    assert register(listing_id, upload(listing_id), 5).status_code == 201
    assert [i.position for i in image_rows(db_session, listing_id)] == [0, 1, 2, 3, 4, 5]
