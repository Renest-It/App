import re
import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app import storage
from app.db import get_db
from app.dependencies import get_current_user
from app.errors import ApiError
from app.models import Category, Listing, ListingImage, User
from app.schemas.listing import (
    MAX_PHOTOS,
    ImageUploadUrlOut,
    ImageUploadUrlRequest,
    ListingCreate,
    ListingCreateResponse,
    ListingDetail,
    ListingImageCreate,
    ListingImageOut,
    ListingListItem,
)
from app.storage import public_url

# The photo types the bucket accepts (supabase/storage/listing-photos.sql), and the file
# extension each one is stored under.
IMAGE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

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


def _require_owner(listing: Listing, user: User) -> None:
    if listing.seller_id != user.id:
        raise ApiError(403, "not_owner", "You can't change someone else's listing.")


def _get_own_draft(db: Session, listing_id: str, user: User) -> Listing:
    """The listing, if `user` is its seller and it's still a draft (photos can only be added
    before publishing in E2)."""
    listing = _get_visible_listing(db, listing_id, user)
    _require_owner(listing, user)
    if listing.status != "draft":
        raise ApiError(409, "listing_not_draft", "Photos can only be added before publishing.")
    return listing


def _storage_unavailable() -> ApiError:
    return ApiError(
        503, "storage_unavailable", "Photo storage isn't available right now. Try again shortly."
    )


def _is_own_storage_path(listing: Listing, storage_path: str) -> bool:
    """Whether `storage_path` is exactly the shape the upload-url endpoint hands out for this
    listing: listings/{listing_id}/{uuid}.{ext}. Matching the whole path (rather than only
    checking the prefix) also rules out tricks like `listings/{id}/../{other_id}/x.jpg`."""
    extensions = "|".join(IMAGE_EXTENSIONS.values())
    pattern = rf"listings/{listing.id}/[0-9a-f]{{8}}(-[0-9a-f]{{4}}){{3}}-[0-9a-f]{{12}}\.({extensions})"
    return re.fullmatch(pattern, storage_path) is not None


def _image_out(image: ListingImage) -> ListingImageOut:
    return ListingImageOut(id=image.id, position=image.position, url=public_url(image.storage_path))


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
        images=[_image_out(image) for image in listing.images],
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
    _require_owner(listing, current_user)
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


@router.post("/listings/{listing_id}/images/upload-url", response_model=ImageUploadUrlOut)
def create_image_upload_url(
    listing_id: str,
    body: ImageUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _get_own_draft(db, listing_id, current_user)
    extension = IMAGE_EXTENSIONS.get(body.content_type)
    if extension is None:
        raise ApiError(
            422, "unsupported_content_type", "Photos must be JPEG, PNG, or WebP images."
        )

    # The server picks the path, so a client can only ever upload into its own draft's folder.
    storage_path = f"listings/{listing.id}/{uuid.uuid4()}.{extension}"
    try:
        upload_url = storage.create_signed_upload_url(storage_path)
    except storage.StorageUnavailable:
        raise _storage_unavailable()
    return ImageUploadUrlOut(
        upload_url=upload_url,
        storage_path=storage_path,
        expires_in=storage.UPLOAD_URL_EXPIRES_IN,
    )


@router.post("/listings/{listing_id}/images", status_code=201, response_model=ListingImageOut)
def add_listing_image(
    listing_id: str,
    body: ListingImageCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _get_own_draft(db, listing_id, current_user)
    if not _is_own_storage_path(listing, body.storage_path):
        # Without this, a seller could attach someone else's uploaded photo to their listing.
        raise ApiError(
            422, "invalid_storage_path", "That photo wasn't uploaded for this listing."
        )

    def already_recorded() -> ListingImage | None:
        return next(
            (
                image
                for image in listing.images
                if image.storage_path == body.storage_path and image.position == body.position
            ),
            None,
        )

    existing = already_recorded()
    if existing:
        # An identical retry (e.g. the response was lost on a flaky connection): no duplicate.
        response.status_code = 200
        return _image_out(existing)
    # Covers both "another photo has this position" and "this photo is already recorded at a
    # different position", so one upload can't fill two positions.
    if any(
        image.position == body.position or image.storage_path == body.storage_path
        for image in listing.images
    ):
        raise ApiError(409, "position_taken", "Another photo already has that position.")

    try:
        uploaded = storage.object_exists(body.storage_path)
    except storage.StorageUnavailable:
        raise _storage_unavailable()
    if not uploaded:
        raise ApiError(
            422, "upload_not_found", "That photo hasn't finished uploading. Upload it, then try again."
        )

    image = ListingImage(
        listing_id=listing.id, storage_path=body.storage_path, position=body.position
    )
    db.add(image)
    try:
        db.commit()
    except IntegrityError:
        # Another request recorded a photo at this position after the checks above ran.
        db.rollback()
        db.refresh(listing)
        existing = already_recorded()
        if existing:
            response.status_code = 200
            return _image_out(existing)
        raise ApiError(409, "position_taken", "Another photo already has that position.")
    db.refresh(image)
    return _image_out(image)
