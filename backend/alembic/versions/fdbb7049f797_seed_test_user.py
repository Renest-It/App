"""seed test user

Revision ID: fdbb7049f797
Revises: 3d3ecb5e40b8
Create Date: 2026-09-19 11:00:54.853299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fdbb7049f797'
down_revision: Union[str, None] = '3d3ecb5e40b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEST_USER_EMAIL = "test@creighton.edu"

users_table = sa.table(
    "users",
    sa.column("email", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(users_table, [{"email": TEST_USER_EMAIL}])


def downgrade() -> None:
    op.execute(users_table.delete().where(users_table.c.email == TEST_USER_EMAIL))
