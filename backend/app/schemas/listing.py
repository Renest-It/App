from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.category import CategoryOut


class ListingCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    price_cents: int = Field(ge=0)
    category_id: int

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty or whitespace-only")
        return stripped


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    price_cents: int
    category: CategoryOut
    created_at: datetime
