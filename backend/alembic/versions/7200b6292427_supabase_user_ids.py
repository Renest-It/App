"""supabase user ids

Users are now created on their first authenticated request, with `users.id` set to their
Supabase user ID (E1.5 / SCRUM-28), so the database no longer generates ids.

Also removes the fake E0 user `test@creighton.edu` (seeded in fdbb7049f797 for the old
get_current_user() stub) and ALL of its listings. On the shared database that is every listing
created before E1.5 — all test data, deleted intentionally.

Downgrade restores the id default but does NOT restore the deleted user or listings.

Revision ID: 7200b6292427
Revises: fdbb7049f797
Create Date: 2026-09-24 16:41:45.952022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7200b6292427'
down_revision: Union[str, None] = 'fdbb7049f797'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEST_USER_EMAIL = "test@creighton.edu"


def upgrade() -> None:
    # Listings first: listings.seller_id references users.id with no ON DELETE rule.
    op.execute(
        sa.text(
            "DELETE FROM listings WHERE seller_id IN "
            "(SELECT id FROM users WHERE email = :email)"
        ).bindparams(email=TEST_USER_EMAIL)
    )
    op.execute(sa.text("DELETE FROM users WHERE email = :email").bindparams(email=TEST_USER_EMAIL))
    op.alter_column("users", "id", server_default=None)


def downgrade() -> None:
    op.alter_column("users", "id", server_default=sa.text("gen_random_uuid()"))
