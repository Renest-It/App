from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.db import get_db
from app.models import User
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
