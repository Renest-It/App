"""Shared test setup for token verification.

Tests sign their own tokens with a locally generated P-256 key and serve its public half
through a fake JWKS endpoint, so they never call Supabase (and fail loudly if anything tries
to open a network connection).
"""

import os

# Settings are read when `app` is first imported, so set dummy values before any app import.
# Environment variables win over backend/.env, so a developer's real .env can't leak in.
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["SUPABASE_URL"] = "https://test-project.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"

import json  # noqa: E402
import socket  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
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
