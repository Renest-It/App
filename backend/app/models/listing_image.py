from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class ListingImage(Base):
    """One photo of a listing. The file itself lives in Supabase Storage (ADR 0009)."""

    __tablename__ = "listing_images"
    __table_args__ = (
        CheckConstraint("position BETWEEN 0 AND 5", name="ck_listing_images_position"),
        UniqueConstraint("listing_id", "position", name="uq_listing_images_listing_position"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    listing_id = Column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    # Path inside the listing-photos bucket: listings/{listing_id}/{uuid}.{ext}
    storage_path = Column(String, nullable=False)
    # 0-based; position 0 is the cover photo.
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
