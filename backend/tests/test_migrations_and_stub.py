"""The E1.5 migration's effects, and proof the E0 stub is gone."""

import pathlib

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"


def test_no_stub_user_in_app_code():
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in APP_DIR.rglob("*.py")
        if "test@creighton.edu" in path.read_text()
    ]
    assert offenders == []


@pytest.mark.requires_db
def test_users_id_is_not_generated(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(text("INSERT INTO users (email) VALUES ('noid@creighton.edu')"))
    db_session.rollback()


@pytest.mark.requires_db
def test_fake_e0_user_is_gone_after_migrations(db_session):
    # The seed migration creates it and the E1.5 migration removes it (migrated_db runs both).
    count = db_session.execute(
        text("SELECT count(*) FROM users WHERE email = 'test@creighton.edu'")
    ).scalar()
    assert count == 0
