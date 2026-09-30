import uuid

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.dependencies import get_current_user
from app.errors import ApiError
from app.models import Category, Listing, User
from app.schemas.listing import (
    MAX_PHOTOS,
    ListingCreate,
    ListingCreateResponse,
    ListingDetail,
    ListingImageOut,
    ListingListItem,
)
from app.storage import public_url

# Login-only API: every route on this router requires a valid token.
router = APIRouter(dependencies=[Depends(get_current_user)])


def _not_found() -> ApiError:
    return ApiError(404, "listing_not_found", "Listing not found.")


def _get_visible_listing(db: Session, listing_id: str, user: User) -> Listing:
    """The listing, if `user` may see it. Anyone else's draft is a 404, exactly like a listing
    that doesn't exist, so outsiders can't tell whether a draft exists."""
    try:
        parsed_id = uuid.UUID(listing_id)
    except ValueError:
        raise _not_found()

    listing = (
        db.query(Listing)
        .options(
            joinedload(Listing.category),
            joinedload(Listing.seller),
            selectinload(Listing.images),
        )
        .filter(Listing.id == parsed_id)
        .first()
    )
    if listing is None or (listing.status == "draft" and listing.seller_id != user.id):
        raise _not_found()
    return listing


def _cover_image_url(listing: Listing) -> str | None:
    cover = next((image for image in listing.images if image.position == 0), None)
    return public_url(cover.storage_path) if cover else None


def _to_detail(listing: Listing) -> ListingDetail:
    return ListingDetail(
        id=listing.id,
        title=listing.title,
        description=listing.description,
        price_cents=listing.price_cents,
        status=listing.status,
        category=listing.category,
        seller=listing.seller,
        # listing.images is already ordered by position (see the relationship).
        images=[
            ListingImageOut(id=image.id, position=image.position, url=public_url(image.storage_path))
            for image in listing.images
        ],
        created_at=listing.created_at,
    )


def _publish_problem(listing: Listing) -> str | None:
    """Re-check the E2.1 validation rules on a draft; returns a message if one fails."""
    if len(listing.images) > MAX_PHOTOS:
        return f"A listing can have at most {MAX_PHOTOS} photos."
    try:
        ListingCreate(
            title=listing.title,
            description=listing.description,
            price_cents=listing.price_cents,
            category_id=listing.category_id,
        )
    except ValidationError as e:
        field = e.errors()[0]["loc"][0]
        return f"This listing's {field} isn't valid. Edit it and try again."
    return None


@router.post("/listings", status_code=201, response_model=ListingCreateResponse)
def create_listing(
    listing: ListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    category = db.query(Category).filter(Category.id == listing.category_id).first()
    if category is None:
        raise ApiError(422, "unknown_category", "That category doesn't exist.")

    new_listing = Listing(
        title=listing.title,
        description=listing.description,
        price_cents=listing.price_cents,
        category_id=listing.category_id,
        seller_id=current_user.id,
        # Set here rather than by the column default, which is still 'active' (E2.1 migration).
        status="draft",
    )
    db.add(new_listing)
    db.commit()
    db.refresh(new_listing)
    return new_listing


@router.get("/listings", response_model=list[ListingListItem])
def list_listings(db: Session = Depends(get_db)):
    listings = (
        db.query(Listing)
        .options(joinedload(Listing.category), selectinload(Listing.images))
        .filter(Listing.status == "active")
        .order_by(desc(Listing.created_at))
        .all()
    )
    return [
        ListingListItem(
            id=listing.id,
            title=listing.title,
            description=listing.description,
            price_cents=listing.price_cents,
            category=listing.category,
            cover_image_url=_cover_image_url(listing),
            created_at=listing.created_at,
        )
        for listing in listings
    ]


@router.get("/listings/{listing_id}", response_model=ListingDetail)
def get_listing(
    listing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _to_detail(_get_visible_listing(db, listing_id, current_user))


@router.post("/listings/{listing_id}/publish", response_model=ListingDetail)
def publish_listing(
    listing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _get_visible_listing(db, listing_id, current_user)
    if listing.seller_id != current_user.id:
        raise ApiError(403, "not_owner", "You can't change someone else's listing.")
    if listing.status != "draft":
        raise ApiError(409, "already_published", "This listing is already published.")
    if not listing.images:
        raise ApiError(422, "no_images", "Add at least one photo before publishing.")
    problem = _publish_problem(listing)
    if problem:
        raise ApiError(422, "invalid_listing", problem)

    listing.status = "active"
    listing.updated_at = func.now()
    db.commit()
    db.refresh(listing)
    return _to_detail(listing)
