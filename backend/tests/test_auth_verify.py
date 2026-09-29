"""verify_token: signature, claims, domain rule, email confirmation, key caching."""

import base64
import hashlib
import hmac
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import auth
from app.auth import (
    AuthClaims,
    AuthUnavailableError,
    ForbiddenUserError,
    InvalidTokenError,
    verify_token,
)
from tests.conftest import jwk_for


def _b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


# --- Valid tokens -----------------------------------------------------------------------


def test_valid_token_returns_claims(make_token):
    token = make_token(sub="user-123")
    assert verify_token(token) == AuthClaims(
        user_id="user-123",
        email="student@creighton.edu",
        email_verified=True,
        display_name="Test Student",
    )


def test_email_is_normalized_and_mixed_case_creighton_accepted(make_token):
    claims = verify_token(make_token(email="  Student@Creighton.EDU "))
    assert claims.email == "student@creighton.edu"


def test_missing_display_name_is_none(make_token):
    claims = verify_token(make_token(user_metadata={"email_verified": True}))
    assert claims.display_name is None


# --- Invalid tokens → InvalidTokenError (401) ---------------------------------------------


@pytest.mark.parametrize("token", [None, "", "not-a-jwt", "a.b.c", "eyJhbGciOiJFUzI1NiJ9.e30."])
def test_missing_or_garbage_token(token):
    with pytest.raises(InvalidTokenError):
        verify_token(token)


def test_expired_token(make_token):
    # Well past the 30-second clock-skew leeway.
    token = make_token(iat=int(time.time()) - 7200, exp=int(time.time()) - 3600)
    with pytest.raises(InvalidTokenError):
        verify_token(token)


def test_wrong_audience(make_token):
    with pytest.raises(InvalidTokenError):
        verify_token(make_token(aud="anon"))


def test_wrong_issuer(make_token):
    with pytest.raises(InvalidTokenError):
        verify_token(make_token(iss="https://some-other-project.supabase.co/auth/v1"))


@pytest.mark.parametrize("claim", ["sub", "email", "exp"])
def test_missing_required_claim(make_token, claim):
    with pytest.raises(InvalidTokenError):
        verify_token(make_token(drop=(claim,)))


def test_tampered_payload(make_token):
    header, _payload, signature = make_token().split(".")
    forged_payload = _b64(
        {
            "sub": "someone-else",
            "aud": "authenticated",
            "iss": "https://test-project.supabase.co/auth/v1",
            "exp": int(time.time()) + 3600,
            "email": "attacker@creighton.edu",
            "user_metadata": {"email_verified": True},
        }
    )
    with pytest.raises(InvalidTokenError):
        verify_token(f"{header}.{forged_payload}.{signature}")


def test_tampered_signature(make_token):
    header, payload, signature = make_token().split(".")
    flipped = signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")
    with pytest.raises(InvalidTokenError):
        verify_token(f"{header}.{payload}.{flipped}")


def test_signed_by_unpublished_key_with_real_kid(make_token, attacker_key):
    # Right kid, wrong key: the signature doesn't match the published public key.
    with pytest.raises(InvalidTokenError):
        verify_token(make_token(key=attacker_key))


def test_hs256_with_public_key_as_secret_is_rejected(make_token, signing_key):
    # Classic algorithm-confusion attack: HMAC-sign with the *public* key (which anyone can
    # download from the JWKS endpoint). PyJWT refuses to create such a token, so forge it by
    # hand the way an attacker would.
    public_pem = signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    _header, payload, _signature = make_token().split(".")
    header = _b64({"alg": "HS256", "typ": "JWT", "kid": "test-key-1"})
    mac = hmac.new(public_pem, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(mac).rstrip(b"=").decode()
    with pytest.raises(InvalidTokenError):
        verify_token(f"{header}.{payload}.{signature}")


def test_alg_none_is_rejected(make_token):
    header, payload, _signature = make_token().split(".")
    none_header = _b64({"alg": "none", "typ": "JWT", "kid": "test-key-1"})
    with pytest.raises(InvalidTokenError):
        verify_token(f"{none_header}.{payload}.")


def test_unknown_kid(make_token, attacker_key):
    with pytest.raises(InvalidTokenError):
        verify_token(make_token(key=attacker_key, kid="not-a-published-key"))


def test_missing_kid(make_token):
    with pytest.raises(InvalidTokenError):
        verify_token(make_token(kid=None))


# --- Allowed domain → ForbiddenUserError("wrong_domain") (403) ----------------------------


@pytest.mark.parametrize(
    "email",
    [
        "someone@notcreighton.edu",  # the careless-endswith trap
        "someone@creighton.edu.evil.com",
        "someone@alumni.creighton.edu",  # subdomains aren't on the allow-list
        "someone@gmail.com",
        "creighton.edu@gmail.com",
    ],
)
def test_wrong_domain(make_token, email):
    with pytest.raises(ForbiddenUserError) as exc:
        verify_token(make_token(email=email))
    assert exc.value.code == "wrong_domain"


# --- Email confirmation → ForbiddenUserError("email_not_confirmed") (403) ----------------


@pytest.mark.parametrize(
    "user_metadata",
    [{"email_verified": False}, {}, {"email_verified": "true"}],
    ids=["false", "missing", "string-not-bool"],
)
def test_unconfirmed_email(make_token, user_metadata):
    with pytest.raises(ForbiddenUserError) as exc:
        verify_token(make_token(user_metadata=user_metadata))
    assert exc.value.code == "email_not_confirmed"


def test_wrong_domain_reported_before_unconfirmed(make_token):
    token = make_token(email="someone@gmail.com", user_metadata={"email_verified": False})
    with pytest.raises(ForbiddenUserError) as exc:
        verify_token(token)
    assert exc.value.code == "wrong_domain"


# --- Key caching, rotation, and outages ---------------------------------------------------


def test_keys_fetched_once_for_many_verifications(make_token, jwks):
    for _ in range(5):
        verify_token(make_token())
    assert jwks.calls == 1


def test_key_rotation_refetches_once(make_token, jwks):
    verify_token(make_token())  # warms the cache with the original key
    assert jwks.calls == 1

    new_key = ec.generate_private_key(ec.SECP256R1())
    jwks.keys.append(jwk_for(new_key, "rotated-key"))
    # Let PyJWT's 30-second anti-spam cooldown for unknown-kid refreshes pass.
    auth._jwks_client()._last_successful_fetch = time.monotonic() - 31

    claims = verify_token(make_token(key=new_key, kid="rotated-key"))
    assert claims.email == "student@creighton.edu"
    assert jwks.calls == 2  # exactly one refetch


def test_unknown_kid_during_cooldown_does_not_refetch(make_token, jwks, attacker_key):
    verify_token(make_token())
    assert jwks.calls == 1
    # A flood of made-up key IDs right after a fetch must not hammer the JWKS endpoint.
    for i in range(3):
        with pytest.raises(InvalidTokenError):
            verify_token(make_token(key=attacker_key, kid=f"made-up-{i}"))
    assert jwks.calls == 1


def test_keys_endpoint_down_with_empty_cache(make_token, jwks):
    jwks.fail = True
    with pytest.raises(AuthUnavailableError):
        verify_token(make_token())


def test_cached_keys_survive_an_outage(make_token, jwks):
    verify_token(make_token())
    jwks.fail = True
    # Still within the cache lifetime, so no fetch is needed and verification works.
    assert verify_token(make_token()).email == "student@creighton.edu"
    assert jwks.calls == 1


def test_no_network_used(make_token, jwks):
    # The autouse no_network fixture fails any real connection; the fake served the keys.
    verify_token(make_token())
    assert jwks.calls == 1
