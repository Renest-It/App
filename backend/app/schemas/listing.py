from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.category import CategoryOut

# The validation rules from docs/api/listings.md. The frontend form enforces the same ones.
TITLE_MIN = 3
TITLE_MAX = 80
DESCRIPTION_MAX = 2000
PRICE_MAX_CENTS = 1_000_000  # $10,000
MAX_PHOTOS = 6


# Trimmed first, then length-checked.
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=TITLE_MIN, max_length=TITLE_MAX)
]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=DESCRIPTION_MAX)]


class ListingCreate(BaseModel):
    title: Title
    description: Description | None = None
    price_cents: int = Field(ge=0, le=PRICE_MAX_CENTS)
    category_id: int

    @field_validator("description")
    @classmethod
    def empty_description_is_none(cls, value: str | None) -> str | None:
        return value or None


class ListingUpdate(BaseModel):
    """PATCH /listings/{id}: any subset of the fields, with the same rules as ListingCreate.
    Read it with `model_dump(exclude_unset=True)` so fields the client left out stay as they
    are. Only `description` may be sent as null (which clears it)."""

    title: Title | None = None
    description: Description | None = None
    price_cents: int | None = Field(default=None, ge=0, le=PRICE_MAX_CENTS)
    category_id: int | None = None

    @field_validator("description")
    @classmethod
    def empty_description_is_none(cls, value: str | None) -> str | None:
        return value or None

    # Validators don't run on defaults, so this only fires when the client sends null.
    @field_validator("title", "price_cents", "category_id")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("can't be null")
        return value


class ListingCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    price_cents: int
    category_id: int | None
    status: str
    created_at: datetime


class ListingListItem(BaseModel):
    id: UUID
    title: str
    description: str | None
    price_cents: int
    category: CategoryOut
    cover_image_url: str | None  # the position-0 photo; None if there isn't one
    created_at: datetime


class MyListingItem(ListingListItem):
    """GET /listings/mine: the feed's shape plus status, since it includes drafts and sold."""

    status: str


class ListingImageOut(BaseModel):
    id: UUID
    position: int
    url: str


class SellerOut(BaseModel):
    """The seller as shown on a listing. Never add email here (docs/api/listings.md)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str | None


class ListingDetail(BaseModel):
    id: UUID
    title: str
    description: str | None
    price_cents: int
    status: str
    category: CategoryOut
    seller: SellerOut
    images: list[ListingImageOut]  # sorted by position
    created_at: datetime


class ImageUploadUrlRequest(BaseModel):
    # Checked in the route, not here, so an unsupported type gets the contract's own
    # `unsupported_content_type` code instead of FastAPI's generic 422.
    content_type: str


class ImageUploadUrlOut(BaseModel):
    upload_url: str
    storage_path: str
    expires_in: int  # seconds


class ListingImageCreate(BaseModel):
    storage_path: str
    # 0–5 plus the unique (listing_id, position) constraint is what caps a listing at 6 photos.
    position: int = Field(ge=0, le=MAX_PHOTOS - 1)
