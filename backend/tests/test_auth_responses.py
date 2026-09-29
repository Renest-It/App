"""register_auth_error_handlers: auth errors become 401/403/503 JSON responses."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import (
    AuthUnavailableError,
    ForbiddenUserError,
    InvalidTokenError,
    register_auth_error_handlers,
    verify_token,
)


@pytest.fixture
def client():
    app = FastAPI()
    register_auth_error_handlers(app)

    @app.get("/invalid")
    def invalid():
        raise InvalidTokenError()

    @app.get("/wrong-domain")
    def wrong_domain():
        raise ForbiddenUserError("wrong_domain")

    @app.get("/unconfirmed")
    def unconfirmed():
        raise ForbiddenUserError("email_not_confirmed")

    @app.get("/unavailable")
    def unavailable():
        raise AuthUnavailableError()

    @app.get("/verify")
    def verify(token: str = ""):
        return {"email": verify_token(token).email}

    return TestClient(app)


def test_invalid_token_is_401_with_bearer_challenge(client):
    r = client.get("/invalid")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json()["code"] == "invalid_token"


@pytest.mark.parametrize(
    "path, code",
    [("/wrong-domain", "wrong_domain"), ("/unconfirmed", "email_not_confirmed")],
)
def test_forbidden_is_403_with_reason_code(client, path, code):
    r = client.get(path)
    assert r.status_code == 403
    assert "www-authenticate" not in r.headers
    assert r.json()["code"] == code


def test_unavailable_is_503_with_retry_after(client):
    r = client.get("/unavailable")
    assert r.status_code == 503
    assert r.headers["retry-after"] == "5"
    assert r.json()["code"] == "auth_unavailable"


@pytest.mark.parametrize("path", ["/invalid", "/wrong-domain", "/unconfirmed", "/unavailable"])
def test_body_has_only_code_and_message(client, path):
    body = client.get(path).json()
    assert set(body) == {"code", "message"}
    assert body["message"]


def test_real_verification_failure_leaks_nothing(client, make_token):
    token = make_token(aud="anon")
    r = client.get("/verify", params={"token": token})
    assert r.status_code == 401
    assert token not in r.text
    assert "audience" not in r.text.lower()  # no PyJWT error text


def test_real_verification_success(client, make_token):
    r = client.get("/verify", params={"token": make_token()})
    assert r.status_code == 200
    assert r.json() == {"email": "student@creighton.edu"}
