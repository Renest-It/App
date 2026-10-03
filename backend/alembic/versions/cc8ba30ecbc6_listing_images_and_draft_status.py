"""listing images and draft status

Adds the `listing_images` table and allows `draft` as a listing status (E2.1 / SCRUM-32,
ADR 0009). The `status` default stays `active` for now: E2.2 switches POST /listings to
create drafts together with the publish endpoint.

Downgrade deletes any draft listings (and, through the cascade, their images) before
restoring the old status check, which doesn't allow them.

Revision ID: cc8ba30ecbc6
Revises: 7200b6292427
Create Date: 2026-09-30 14:20:11.482913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc8ba30ecbc6'
down_revision: Union[str, None] = '7200b6292427'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_listings_status", "listings", type_="check")
    op.create_check_constraint(
        "ck_listings_status", "listings", "status IN ('draft', 'active', 'sold')"
    )

    op.create_table('listing_images',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('listing_id', sa.UUID(), nullable=False),
    sa.Column('storage_path', sa.String(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.CheckConstraint('position BETWEEN 0 AND 5', name='ck_listing_images_position'),
    sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('listing_id', 'position', name='uq_listing_images_listing_position'),
    )


def downgrade() -> None:
    op.drop_table('listing_images')

    op.execute("DELETE FROM listings WHERE status = 'draft'")
    op.drop_constraint("ck_listings_status", "listings", type_="check")
    op.create_check_constraint("ck_listings_status", "listings", "status IN ('active', 'sold')")
