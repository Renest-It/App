"""Shared test setup.

Token tests sign their own tokens with a locally generated P-256 key and serve its public half
through a fake JWKS endpoint, so they never call Supabase (and fail loudly if anything tries
to open a network connection from Python).

Database tests (marked `requires_db`) run against a disposable Postgres given by
TEST_DATABASE_URL, and are skipped when it isn't set. They must never run against the shared
Supabase database, so a Supabase host aborts the whole test run before anything connects.
"""

import os
from urllib.parse import urlparse

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()

if TEST_DATABASE_URL:
    _host = (urlparse(TEST_DATABASE_URL).hostname or "").lower()
    if "supabase.co" in _host or "supabase.com" in _host:
        raise pytest.UsageError(
            f"TEST_DATABASE_URL points at a Supabase host ({_host}). Tests truncate tables and "
            "must never run against the shared database. Use a disposable local Postgres instead."
        )

# Settings are read when `app` is first imported, so set these before any app import.
# Environment variables win over backend/.env, so a developer's real .env can't leak in.
# DATABASE_URL is only ever the disposable test database (or a dummy that is never connected to).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or "postgresql://test:test@localhost:5432/test"
os.environ["SUPABASE_URL"] = "https://test-project.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"

import json  # noqa: E402
import socket  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from jwt.algorithms import ECAlgorithm  # noqa: E402

from app import auth  # noqa: E402

TEST_KID = "test-key-1"
ISSUER = "https://test-project.supabase.co/auth/v1"


def jwk_for(private_key: ec.EllipticCurvePrivateKey, kid: str) -> dict:
    """The public JWK for a private key, as Supabase's JWKS endpoint would publish it."""
    jwk = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})
    return jwk


@pytest.fixture(scope="session")
def signing_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(scope="session")
def attacker_key() -> ec.EllipticCurvePrivateKey:
    """A valid P-256 key that the project does NOT publish."""
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any attempt to open a real connection fails the test."""

    def refuse(*_args, **_kwargs):
        raise RuntimeError("Tests must not make network calls")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@dataclass
class FakeJWKS:
    keys: list[dict]
    calls: int = 0
    fail: bool = False
    history: list[int] = field(default_factory=list)


@pytest.fixture(autouse=True)
def jwks(monkeypatch, signing_key) -> FakeJWKS:
    """Replace the JWKS fetch with an in-memory key set and count fetches.

    Mirrors the real PyJWKClient.fetch_data: returns the key set and starts the unknown-kid
    refresh cooldown. PyJWT's own caching and kid lookup run unmodified.
    """
    fake = FakeJWKS(keys=[jwk_for(signing_key, TEST_KID)])

    def fake_fetch_data(self):
        fake.calls += 1
        if fake.fail:
            raise jwt.PyJWKClientConnectionError("simulated outage")
        self._last_successful_fetch = time.monotonic()
        return {"keys": list(fake.keys)}

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", fake_fetch_data)
    auth._jwks_client.cache_clear()  # fresh client (and empty key cache) for every test
    yield fake
    auth._jwks_client.cache_clear()


@pytest.fixture
def make_token(signing_key):
    """Build a token that is valid by default; override any claim, header, or the key."""

    def _make(
        *,
        key=None,
        kid=TEST_KID,
        algorithm="ES256",
        drop=(),
        user_metadata=None,
        **claim_overrides,
    ) -> str:
        now = int(time.time())
        claims = {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "iss": ISSUER,
            "iat": now,
            "exp": now + 3600,
            "email": "student@creighton.edu",
            "role": "authenticated",
            "user_metadata": {"email_verified": True, "display_name": "Test Student"}
            if user_metadata is None
            else user_metadata,
        }
        claims.update(claim_overrides)
        for name in drop:
            claims.pop(name, None)
        headers = {"kid": kid} if kid is not None else {}
        return jwt.encode(claims, key or signing_key, algorithm=algorithm, headers=headers)

    return _make


# --- Database tests -----------------------------------------------------------------------

_SKIP_DB_REASON = (
    "Database test skipped: set TEST_DATABASE_URL to a disposable Postgres, e.g. "
    "`docker run -d --name renest-test-db -e POSTGRES_USER=renest_test "
    "-e POSTGRES_PASSWORD=renest_test -e POSTGRES_DB=renest_test -p 5433:5432 postgres:16` and "
    "TEST_DATABASE_URL=postgresql://renest_test:renest_test@localhost:5433/renest_test"
)


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip_db = pytest.mark.skip(reason=_SKIP_DB_REASON)
    for item in items:
        if "requires_db" in item.keywords:
            item.add_marker(skip_db)


@pytest.fixture(scope="session")
def migrated_db():
    """Rebuild the test database with the real migrations: downgrade to nothing, then upgrade.

    This also exercises every migration (including the E1.5 one) on a fresh database.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic")
    )
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_db(request):
    """For database tests: start from a migrated schema and wipe users/listings afterward."""
    if request.node.get_closest_marker("requires_db") is None:
        yield
        return
    request.getfixturevalue("migrated_db")
    yield
    from sqlalchemy import text

    from app.db import engine

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE listings, users CASCADE"))


@pytest.fixture
def db_session():
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
