"""Supabase access-token verification.

This is where the backend decides whether a request's token can be trusted and whether its
user is allowed into ReNest. Client-side checks (like the sign-up form's @creighton.edu check)
can be bypassed; this can't. See ADR 0007.

E1.5 (SCRUM-28) calls `verify_token` from the real `get_current_user()` dependency.
"""

import logging
from dataclasses import dataclass
from functools import cache

import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

# The Supabase project signs access tokens with an asymmetric ES256 key and publishes the
# public half at the JWKS URL (checked against the live project for SCRUM-27). Only ES256 is
# accepted: pinning the algorithm blocks HS256/"none" and algorithm-confusion attacks.
ALGORITHMS = ["ES256"]
AUDIENCE = "authenticated"

_SUPABASE_URL = settings.supabase_url.rstrip("/")
ISSUER = f"{_SUPABASE_URL}/auth/v1"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"

# Compared against the *whole* domain after the last "@", never with endswith, so
# notcreighton.edu, creighton.edu.evil.com, and alumni.creighton.edu are all refused.
# Alumni/employee addresses directly on @creighton.edu are allowed (ADR 0001). If Creighton
# issues a separate alumni domain, add it here and note it in ADR 0007.
ALLOWED_EMAIL_DOMAINS = frozenset({"creighton.edu"})

# Allow for small clock differences between this server and Supabase.
_CLOCK_SKEW_LEEWAY_SECONDS = 30
# How long the fetched key set is cached. Unknown key IDs trigger an earlier refresh
# (at most once every 30 seconds, PyJWT's default cooldown).
_JWKS_CACHE_SECONDS = 600


@dataclass(frozen=True)
class AuthClaims:
    """The verified identity from a token."""

    user_id: str  # Supabase user ID (the token's `sub`)
    email: str  # lowercased
    email_verified: bool
    display_name: str | None  # from the sign-up form, if the user set one


class InvalidTokenError(Exception):
    """The token can't be trusted (missing, malformed, badly signed, expired, ...). → 401"""

    code = "invalid_token"


class ForbiddenUserError(Exception):
    """The token is valid, but this user isn't allowed in. → 403"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code  # "wrong_domain" or "email_not_confirmed"


class AuthUnavailableError(Exception):
    """The signing keys couldn't be fetched, so the token can't be checked right now. → 503

    Deliberately not a 401: a Supabase outage shouldn't tell clients to log everyone out.
    """

    code = "auth_unavailable"


@cache
def _jwks_client() -> jwt.PyJWKClient:
    # Created on first use (not at import), so importing the app never touches the network.
    return jwt.PyJWKClient(JWKS_URL, cache_jwk_set=True, lifespan=_JWKS_CACHE_SECONDS)


def verify_token(token: str | None) -> AuthClaims:
    """Verify a Supabase access token and return the user's identity.

    Raises InvalidTokenError, ForbiddenUserError, or AuthUnavailableError.
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError()

    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
    except (jwt.PyJWKClientConnectionError, jwt.PyJWKSetError) as e:
        # Couldn't reach the keys endpoint, or it returned no usable keys.
        logger.warning("Could not load Supabase signing keys: %s", e)
        raise AuthUnavailableError() from None
    except jwt.PyJWTError as e:
        # Malformed token, or its key ID isn't one of the project's keys.
        logger.debug("Token rejected before decoding: %s", e)
        raise InvalidTokenError() from None

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=ISSUER,
            leeway=_CLOCK_SKEW_LEEWAY_SECONDS,
            options={"require": ["exp", "sub", "email"]},
        )
    except jwt.PyJWTError as e:
        # Bad signature, expired, wrong audience/issuer, wrong algorithm, missing claim, ...
        logger.debug("Token rejected: %s", e)
        raise InvalidTokenError() from None

    email = str(claims["email"]).strip().lower()
    if email.rpartition("@")[2] not in ALLOWED_EMAIL_DOMAINS:
        raise ForbiddenUserError("wrong_domain")

    # Defense in depth: user_metadata is editable by the signed-in user, so the real guarantee
    # is the Supabase project requiring email confirmation before it issues any token (ADR 0007).
    user_metadata = claims.get("user_metadata") or {}
    if user_metadata.get("email_verified") is not True:
        raise ForbiddenUserError("email_not_confirmed")

    display_name = user_metadata.get("display_name")
    return AuthClaims(
        user_id=str(claims["sub"]),
        email=email,
        email_verified=True,
        display_name=display_name if isinstance(display_name, str) and display_name else None,
    )


_MESSAGES = {
    "invalid_token": "Your session is invalid or has expired. Please log in again.",
    "wrong_domain": "ReNest is only available to @creighton.edu accounts.",
    "email_not_confirmed": "Please confirm your email address before continuing.",
    "auth_unavailable": "Sign-in is temporarily unavailable. Please try again.",
}


def _error_body(code: str) -> dict[str, str]:
    # Only a stable code (for the frontend to switch on) and a friendly message. Never the
    # token or library error text.
    return {"code": code, "message": _MESSAGES[code]}


def register_auth_error_handlers(app: FastAPI) -> None:
    """Turn the auth errors above into 401/403/503 JSON responses."""

    @app.exception_handler(InvalidTokenError)
    async def _invalid_token(_request: Request, exc: InvalidTokenError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_body(exc.code),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ForbiddenUserError)
    async def _forbidden(_request: Request, exc: ForbiddenUserError) -> JSONResponse:
        return JSONResponse(status_code=403, content=_error_body(exc.code))

    @app.exception_handler(AuthUnavailableError)
    async def _unavailable(_request: Request, exc: AuthUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_body(exc.code),
            headers={"Retry-After": "5"},
        )
