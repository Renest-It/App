"""get_or_create_user: first-request provisioning, repeat requests, races, email conflicts."""

import logging
import threading
import uuid

import pytest
from sqlalchemy import func, text

from app.auth import AuthClaims
from app.db import SessionLocal
from app.models import Listing, User
from app.users import EmailConflictError, get_or_create_user

pytestmark = pytest.mark.requires_db


def claims(user_id=None, email="jane.doe@creighton.edu", display_name="Jane"):
    return AuthClaims(
        user_id=str(user_id or uuid.uuid4()),
        email=email,
        email_verified=True,
        display_name=display_name,
    )


def user_count(db) -> int:
    return db.query(func.count(User.id)).scalar()


def test_first_request_creates_row(db_session):
    c = claims()
    user = get_or_create_user(db_session, c)
    assert user.id == uuid.UUID(c.user_id)  # the Supabase id, not a generated one
    assert user.email == "jane.doe@creighton.edu"
    assert user.display_name == "Jane"
    assert user.created_at is not None
    assert user_count(db_session) == 1


def test_display_name_falls_back_to_email_local_part(db_session):
    user = get_or_create_user(db_session, claims(email="jdoe@creighton.edu", display_name=None))
    assert user.display_name == "jdoe"


def test_repeat_request_reuses_row(db_session):
    c = claims()
    first = get_or_create_user(db_session, c)
    second = get_or_create_user(db_session, c)
    assert second.id == first.id
    assert user_count(db_session) == 1


def test_existing_row_is_not_modified(db_session):
    c = claims(display_name="Original")
    get_or_create_user(db_session, c)
    # Later token with a different display name: the row keeps its original value.
    changed = AuthClaims(c.user_id, c.email, True, "Renamed In Supabase")
    user = get_or_create_user(db_session, changed)
    assert user.display_name == "Original"


def test_simultaneous_first_requests_create_one_row():
    c = claims()
    barrier = threading.Barrier(2)
    results, errors = [], []

    def first_request():
        session = SessionLocal()
        # Force the real race: both threads must finish the "does the row exist?" lookup (and
        # see nothing) before either inserts. Without this, one thread usually finishes before
        # the other starts, and the race never happens.
        real_get, lookups = session.get, []

        def get_then_wait(*args, **kwargs):
            result = real_get(*args, **kwargs)
            lookups.append(result)
            if len(lookups) == 1:
                barrier.wait(timeout=5)
            return result

        session.get = get_then_wait
        try:
            results.append(get_or_create_user(session, c).id)
        except Exception as e:  # noqa: BLE001 - collected and asserted below
            errors.append(e)
        finally:
            session.close()

    threads = [threading.Thread(target=first_request) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == []
    assert results == [uuid.UUID(c.user_id)] * 2
    with SessionLocal() as session:
        assert user_count(session) == 1


def test_email_conflict_is_an_error_and_changes_nothing(db_session, caplog):
    old_id, new_id = uuid.uuid4(), uuid.uuid4()
    db_session.add(User(id=old_id, email="sam@creighton.edu", display_name="Sam"))
    db_session.flush()
    db_session.add(Listing(title="Sam's old desk", price_cents=1500, seller_id=old_id))
    db_session.commit()

    with caplog.at_level(logging.WARNING, logger="app.users"):
        with pytest.raises(EmailConflictError):
            get_or_create_user(db_session, claims(user_id=new_id, email="sam@creighton.edu"))

    # The old row and its listing are untouched, and no row exists for the new id.
    old = db_session.get(User, old_id)
    assert old is not None and old.email == "sam@creighton.edu" and old.display_name == "Sam"
    assert db_session.get(User, new_id) is None
    assert db_session.query(Listing).filter(Listing.seller_id == old_id).count() == 1
    # Logged for admins, with both ids.
    assert str(new_id) in caplog.text and str(old_id) in caplog.text


def test_other_integrity_errors_are_not_mistaken_for_conflicts(db_session, monkeypatch):
    # e.g. a NOT NULL violation must surface as a real error, not a 409.
    db_session.execute(text("ALTER TABLE users ADD CONSTRAINT tmp_no_x CHECK (email <> 'x@creighton.edu')"))
    db_session.commit()
    try:
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            get_or_create_user(db_session, claims(email="x@creighton.edu"))
    finally:
        db_session.rollback()
        db_session.execute(text("ALTER TABLE users DROP CONSTRAINT tmp_no_x"))
        db_session.commit()
