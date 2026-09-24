"""The real get_current_user through HTTP: GET /me, POST /listings, and every error path."""

import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.config import settings
from app.main import app
from app.models import Category, Listing, User

pytestmark = pytest.mark.requires_db


@pytest.fixture
def client():
    return TestClient(app)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def user_count(db) -> int:
    return db.query(func.count(User.id)).scalar()


def test_me_returns_the_signed_in_user(client, make_token, db_session):
    sub = str(uuid.uuid4())
    r = client.get("/me", headers=bearer(make_token(sub=sub, email="Jane.Doe@Creighton.edu")))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == sub
    assert body["email"] == "jane.doe@creighton.edu"
    assert body["display_name"] == "Test Student"
    assert set(body) == {"id", "email", "display_name", "created_at"}
    assert user_count(db_session) == 1


def test_second_request_reuses_the_row(client, make_token, db_session):
    token = make_token()
    assert client.get("/me", headers=bearer(token)).status_code == 200
    assert client.get("/me", headers=bearer(token)).status_code == 200
    assert user_count(db_session) == 1


def test_each_user_sees_only_themselves(client, make_token):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    ra = client.get("/me", headers=bearer(make_token(sub=a, email="a@creighton.edu")))
    rb = client.get("/me", headers=bearer(make_token(sub=b, email="b@creighton.edu")))
    assert (ra.json()["id"], ra.json()["email"]) == (a, "a@creighton.edu")
    assert (rb.json()["id"], rb.json()["email"]) == (b, "b@creighton.edu")


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic dXNlcjpwYXNz"}, {"Authorization": "Bearer"}],
    ids=["no-header", "basic-scheme", "empty-bearer"],
)
def test_missing_token_is_401_and_creates_nothing(client, db_session, headers):
    r = client.get("/me", headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json()["code"] == "invalid_token"
    assert user_count(db_session) == 0


def test_expired_token_is_401_and_creates_nothing(client, make_token, db_session):
    token = make_token(iat=int(time.time()) - 7200, exp=int(time.time()) - 3600)
    r = client.get("/me", headers=bearer(token))
    assert r.status_code == 401
    assert user_count(db_session) == 0


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"email": "someone@gmail.com"}, "wrong_domain"),
        ({"user_metadata": {"email_verified": False}}, "email_not_confirmed"),
    ],
)
def test_forbidden_user_is_403_and_creates_nothing(client, make_token, db_session, overrides, code):
    r = client.get("/me", headers=bearer(make_token(**overrides)))
    assert r.status_code == 403
    assert r.json()["code"] == code
    assert user_count(db_session) == 0


def test_email_conflict_is_409(client, make_token, db_session):
    old_id = uuid.uuid4()
    db_session.add(User(id=old_id, email="sam@creighton.edu"))
    db_session.commit()

    r = client.get("/me", headers=bearer(make_token(email="sam@creighton.edu")))
    assert r.status_code == 409
    assert r.json() == {
        "code": "email_conflict",
        "message": "An older account with this email exists. Contact the ReNest team.",
    }
    assert user_count(db_session) == 1


def test_create_listing_uses_the_token_user(client, make_token, db_session):
    sub = str(uuid.uuid4())
    category_id = db_session.query(Category.id).order_by(Category.id).first()[0]
    r = client.post(
        "/listings",
        headers=bearer(make_token(sub=sub)),
        json={"title": "Desk lamp", "price_cents": 1200, "category_id": category_id},
    )
    assert r.status_code == 201, r.text
    listing = db_session.get(Listing, uuid.UUID(r.json()["id"]))
    assert listing.seller_id == uuid.UUID(sub)


def test_create_listing_without_token_is_401(client, db_session):
    r = client.post("/listings", json={"title": "Desk lamp", "price_cents": 1200, "category_id": 1})
    assert r.status_code == 401
    assert db_session.query(func.count(Listing.id)).scalar() == 0


def test_no_dev_bypass_in_development(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    assert client.get("/me").status_code == 401
