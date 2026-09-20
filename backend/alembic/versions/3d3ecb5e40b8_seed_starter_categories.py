"""seed starter categories

Revision ID: 3d3ecb5e40b8
Revises: e603ec682a24
Create Date: 2026-09-19 10:32:32.304066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d3ecb5e40b8'
down_revision: Union[str, None] = 'e603ec682a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STARTER_CATEGORIES = [
    {"name": "Furniture", "slug": "furniture"},
    {"name": "Electronics", "slug": "electronics"},
    {"name": "Textbooks", "slug": "textbooks"},
    {"name": "Clothing", "slug": "clothing"},
    {"name": "Kitchen", "slug": "kitchen"},
    {"name": "Decor", "slug": "decor"},
    {"name": "Other", "slug": "other"},
]

categories_table = sa.table(
    "categories",
    sa.column("name", sa.String),
    sa.column("slug", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(categories_table, STARTER_CATEGORIES)


def downgrade() -> None:
    slugs = [c["slug"] for c in STARTER_CATEGORIES]
    op.execute(
        categories_table.delete().where(categories_table.c.slug.in_(slugs))
    )
