"""User provisioning: turning a verified token into a `users` row (E1.5 / SCRUM-28).

Rows are created by the backend on a user's first authenticated request, not by a database
trigger. See ADR 0007 ("User provisioning").
"""

import logging
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg2 import errors as pg_errors
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import AuthClaims
from app.models import User

logger = logging.getLogger(__name__)

# Postgres's default name for the unique constraint on users.email (migration e603ec682a24).
_EMAIL_UNIQUE_CONSTRAINT = "users_email_key"


class EmailConflictError(Exception):
    """A new Supabase user's email already belongs to a different users row. → 409

    Happens when an admin deleted someone's Supabase account and they signed up again (new
    Supabase id, same email). The old row and its listings are never re-pointed or deleted
    automatically; an admin fixes legitimate cases by hand (ADR 0007).
    """

    code = "email_conflict"


def _is_email_conflict(error: IntegrityError) -> bool:
    orig = error.orig
    return (
        isinstance(orig, pg_errors.UniqueViolation)
        and getattr(orig.diag, "constraint_name", None) == _EMAIL_UNIQUE_CONSTRAINT
    )


def get_or_create_user(db: Session, claims: AuthClaims) -> User:
    """Return the user's row, creating it on their first request."""
    user_id = UUID(claims.user_id)

    # Common path: the user already exists, so this is a single primary-key lookup.
    user = db.get(User, user_id)
    if user is not None:
        return user

    insert_stmt = (
        pg_insert(User)
        .values(
            id=user_id,
            email=claims.email,  # already lowercased by verify_token
            display_name=claims.display_name or claims.email.split("@")[0],
        )
        # Explicit (id) target: only "the same user's simultaneous first requests" is ignored.
        # An email already used by a *different* id still raises, and becomes a 409 below.
        .on_conflict_do_nothing(index_elements=[User.id])
    )
    try:
        db.execute(insert_stmt)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if not _is_email_conflict(e):
            raise
        existing_id = db.query(User.id).filter(User.email == claims.email).scalar()
        logger.warning(
            "Email conflict: Supabase user %s signed in, but their email already belongs to "
            "user %s. Not provisioning; an admin must resolve it (see ADR 0007).",
            user_id,
            existing_id,
        )
        raise EmailConflictError() from None

    user = db.get(User, user_id)
    if user is None:  # Defensive: shouldn't happen after the insert above.
        raise EmailConflictError()
    return user


def register_user_error_handlers(app: FastAPI) -> None:
    """Turn EmailConflictError into a 409 in the same {code, message} shape as auth errors."""

    @app.exception_handler(EmailConflictError)
    async def _email_conflict(_request: Request, exc: EmailConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "code": exc.code,
                "message": "An older account with this email exists. Contact the ReNest team.",
            },
        )
