"""E2.3: upload URLs and recording uploaded photos (docs/api/listings.md).

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


@pytest.fixture
def fake_storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(storage, "create_signed_upload_url", fake.create_signed_upload_url)
    monkeypatch.setattr(storage, "object_exists", fake.object_exists)
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


def image_rows(db_session, listing_id):
    return db_session.query(ListingImage).filter_by(listing_id=uuid.UUID(listing_id)).all()


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


def test_non_seller_upload_url_for_an_active_listing_is_403(
    client, seller, other, draft, upload, register
):
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    publish(client, seller, listing_id)
    r = client.post(
        f"/listings/{listing_id}/images/upload-url", headers=other, json={"content_type": "image/jpeg"}
    )
    assert r.status_code == 403
    assert r.json()["code"] == "not_owner"


def test_non_seller_upload_url_for_a_draft_is_404(client, other, draft, fake_storage):
    # 404, not 403: a 403 would reveal that the draft exists.
    r = client.post(
        f"/listings/{draft()}/images/upload-url", headers=other, json={"content_type": "image/jpeg"}
    )
    assert r.status_code == 404
    assert r.json()["code"] == "listing_not_found"
    assert fake_storage.signed == []


def test_upload_url_for_a_published_listing_is_409(client, seller, draft, upload, register):
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    publish(client, seller, listing_id)
    r = client.post(
        f"/listings/{listing_id}/images/upload-url", headers=seller, json={"content_type": "image/jpeg"}
    )
    assert r.status_code == 409
    assert r.json()["code"] == "listing_not_draft"


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


def test_registering_on_a_published_listing_is_rejected(
    client, seller, draft, upload, register, db_session
):
    listing_id = draft()
    register(listing_id, upload(listing_id), 0)
    late_photo = upload(listing_id)
    publish(client, seller, listing_id)
    r = register(listing_id, late_photo, 1)
    assert r.status_code == 409
    assert r.json()["code"] == "listing_not_draft"
    assert len(image_rows(db_session, listing_id)) == 1


def test_non_seller_registering_on_an_active_listing_is_403(
    client, seller, other, draft, upload, register
):
    listing_id = draft()
    photo = upload(listing_id)
    register(listing_id, photo, 0)
    publish(client, seller, listing_id)
    r = register(listing_id, photo, 1, headers=other)
    assert r.status_code == 403
    assert r.json()["code"] == "not_owner"


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

