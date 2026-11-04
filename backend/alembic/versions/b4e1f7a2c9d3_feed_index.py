"""feed index and non-null created_at

Supports the paginated home feed (E4.1 / SCRUM-50, ADR 0011). Keyset pagination orders by
`(created_at, id)`, so every listing needs a `created_at`: any NULLs are backfilled with now()
before the column becomes NOT NULL. The index serves
`WHERE status = 'active' [AND (created_at, id) < (:t, :id)] ORDER BY created_at DESC, id DESC`,
and carries `category_id` so E5's category filter is checked inside the index without
changing the column order the unfiltered feed relies on.

Downgrade drops the index and the NOT NULL constraint; backfilled timestamps are kept.

Revision ID: b4e1f7a2c9d3
Revises: cc8ba30ecbc6
Create Date: 2026-10-26 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e1f7a2c9d3'
down_revision: Union[str, None] = 'cc8ba30ecbc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE listings SET created_at = now() WHERE created_at IS NULL")
    op.alter_column(
        "listings",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text("now()"),
        nullable=False,
    )
    op.create_index(
        "ix_listings_feed",
        "listings",
        ["status", sa.text("created_at DESC"), sa.text("id DESC")],
        postgresql_include=["category_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_listings_feed", table_name="listings")
    op.alter_column(
        "listings",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text("now()"),
        nullable=True,
    )
