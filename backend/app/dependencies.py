import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import verify_token
from app.db import get_db
from app.errors import ApiError
from app.models import Listing, User
from app.users import get_or_create_user

# Registers a "bearer" security scheme in the OpenAPI schema, which is what adds the Authorize
# button to /docs. auto_error=False: a missing header reaches verify_token(None), so it gets the
# same 401 invalid_token response as every other auth failure (not FastAPI's own 403).
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Supabase access token. Get one with `python scripts/get_token.py`.",
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """The signed-in user, from the request's bearer token.

    Verifies the token (401/403/503 on failure, see app/auth.py), then returns the user's row,
    creating it on their first request (409 on an email conflict, see app/users.py).
    """
    claims = verify_token(credentials.credentials if credentials else None)
    return get_or_create_user(db, claims)


def listing_not_found() -> ApiError:
    return ApiError(404, "listing_not_found", "Listing not found.")


def load_listing(db: Session, listing_id: str) -> Listing | None:
    """The listing with this ID, with its category, seller, and images loaded, or None if the
    ID is malformed or unknown."""
    try:
        parsed_id = uuid.UUID(listing_id)
    except ValueError:
        return None
    return (
        db.query(Listing)
        .options(
            joinedload(Listing.category),
            joinedload(Listing.seller),
            selectinload(Listing.images),
        )
        .filter(Listing.id == parsed_id)
        .first()
    )


def get_owned_listing(
    listing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Listing:
    """The listing at `{listing_id}`, if the current user is its seller. Every seller-only
    route gets its listing through this, so the ownership check can't be left out of one.

    Someone else's listing (draft, active, or sold) is a 404, exactly like a listing that
    doesn't exist: a 403 would confirm the ID is real (ADR 0010). Status rules (draft only, not
    sold, ...) differ per action, so each route checks those itself.
    """
    listing = load_listing(db, listing_id)
    if listing is None or listing.seller_id != current_user.id:
        raise listing_not_found()
    return listing
