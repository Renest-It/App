import logging
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import ValidationError
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app import storage
from app.db import get_db
from app.dependencies import (
    get_current_user,
    get_owned_listing,
    listing_not_found,
    load_listing,
)
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
    ListingUpdate,
    MyListingItem,
)
from app.storage import public_url

# The photo types the bucket accepts (supabase/storage/listing-photos.sql), and the file
# extension each one is stored under.
IMAGE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

logger = logging.getLogger(__name__)

# Login-only API: every route on this router requires a valid token.
router = APIRouter(dependencies=[Depends(get_current_user)])


def _get_visible_listing(db: Session, listing_id: str, user: User) -> Listing:
    """The listing, if `user` may see it. Anyone else's draft is a 404, exactly like a listing
    that doesn't exist, so outsiders can't tell whether a draft exists."""
    listing = load_listing(db, listing_id)
    if listing is None or (listing.status == "draft" and listing.seller_id != user.id):
        raise listing_not_found()
    return listing


def _listing_sold() -> ApiError:
    return ApiError(409, "listing_sold", "Sold listings can't be changed. Mark it unsold first.")


def _require_not_sold(listing: Listing) -> None:
    """Sold listings are frozen: no edits and no photo changes (ADR 0010)."""
    if listing.status == "sold":
        raise _listing_sold()


def _unknown_category() -> ApiError:
    return ApiError(422, "unknown_category", "That category doesn't exist.")


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


def _list_item_fields(listing: Listing) -> dict:
    return dict(
        id=listing.id,
        title=listing.title,
        description=listing.description,
        price_cents=listing.price_cents,
        category=listing.category,
        cover_image_url=_cover_image_url(listing),
        created_at=listing.created_at,
    )


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
        raise _unknown_category()

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
    return [ListingListItem(**_list_item_fields(listing)) for listing in listings]


# Declared before /listings/{listing_id}, or "mine" would be matched as a listing ID.
@router.get("/listings/mine", response_model=list[MyListingItem])
def list_my_listings(
    status: Literal["active", "draft", "sold"] | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The only endpoint that lists drafts: how a seller gets back to a draft whose publish
    failed partway."""
    query = (
        db.query(Listing)
        .options(joinedload(Listing.category), selectinload(Listing.images))
        .filter(Listing.seller_id == current_user.id)
    )
    if status is not None:
        query = query.filter(Listing.status == status)
    listings = query.order_by(desc(Listing.created_at)).all()
    return [
        MyListingItem(**_list_item_fields(listing), status=listing.status) for listing in listings
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
    listing: Listing = Depends(get_owned_listing),
    db: Session = Depends(get_db),
):
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
    body: ImageUploadUrlRequest,
    listing: Listing = Depends(get_owned_listing),
):
    _require_not_sold(listing)
    extension = IMAGE_EXTENSIONS.get(body.content_type)
    if extension is None:
        raise ApiError(
            422, "unsupported_content_type", "Photos must be JPEG, PNG, or WebP images."
        )

    # The server picks the path, so a client can only ever upload into its own listing's folder.
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
    body: ListingImageCreate,
    response: Response,
    listing: Listing = Depends(get_owned_listing),
    db: Session = Depends(get_db),
):
    _require_not_sold(listing)
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


@router.patch("/listings/{listing_id}", response_model=ListingDetail)
def update_listing(
    changes: ListingUpdate,
    listing: Listing = Depends(get_owned_listing),
    db: Session = Depends(get_db),
):
    _require_not_sold(listing)
    fields = changes.model_dump(exclude_unset=True)
    if "category_id" in fields and db.get(Category, fields["category_id"]) is None:
        raise _unknown_category()

    if fields:
        for name, value in fields.items():
            setattr(listing, name, value)
        # created_at is left alone: the feed sorts by it, and edits don't bump a listing (ADR 0010).
        listing.updated_at = func.now()
        db.commit()
        db.refresh(listing)
    return _to_detail(listing)


@router.delete("/listings/{listing_id}", status_code=204)
def delete_listing(
    listing: Listing = Depends(get_owned_listing),
    db: Session = Depends(get_db),
):
    folder = f"listings/{listing.id}"
    # The database goes first, and its listing_images rows cascade. Storage can't share the
    # transaction, so if it fails afterwards, leftover files are the acceptable outcome; a
    # half-deleted listing isn't (ADR 0010).
    db.delete(listing)
    db.commit()
    try:
        storage.remove_folder(folder)
    except storage.StorageUnavailable as e:
        logger.warning("Deleted listing, but couldn't remove %s from storage: %s", folder, e)
    return Response(status_code=204)


@router.post("/listings/{listing_id}/sold", response_model=ListingDetail)
def mark_sold(
    listing: Listing = Depends(get_owned_listing),
    db: Session = Depends(get_db),
):
    if listing.status != "active":
        raise ApiError(409, "listing_not_active", "Only an active listing can be marked sold.")
    return _set_status(db, listing, "sold")


@router.post("/listings/{listing_id}/unsold", response_model=ListingDetail)
def mark_unsold(
    listing: Listing = Depends(get_owned_listing),
    db: Session = Depends(get_db),
):
    if listing.status != "sold":
        raise ApiError(409, "listing_not_sold", "This listing isn't marked sold.")
    return _set_status(db, listing, "active")


def _set_status(db: Session, listing: Listing, status: str) -> ListingDetail:
    listing.status = status
    listing.updated_at = func.now()
    db.commit()
    db.refresh(listing)
    return _to_detail(listing)


@router.delete("/listings/{listing_id}/images/{image_id}", status_code=204)
def delete_listing_image(
    image_id: str,
    listing: Listing = Depends(get_owned_listing),
    db: Session = Depends(get_db),
):
    # Lock the listing so two deletes at once can't both pass the last-photo check, or collide
    # while renumbering. Then re-read it and its photos, which may have changed before the lock.
    # (A plain query: Postgres can't lock through the outer joins the original load used.)
    db.query(Listing).filter(Listing.id == listing.id).with_for_update().populate_existing().one()
    images = (
        db.query(ListingImage)
        .filter(ListingImage.listing_id == listing.id)
        .order_by(ListingImage.position)
        .populate_existing()
        .all()
    )
    try:
        parsed_id = uuid.UUID(image_id)
    except ValueError:
        parsed_id = None
    image = next((i for i in images if i.id == parsed_id), None)
    if image is None:
        raise ApiError(404, "image_not_found", "Photo not found.")
    _require_not_sold(listing)
    # A published listing with no photos would show a broken card in the feed. Drafts may go
    # down to 0, since publishing already requires at least 1.
    if listing.status == "active" and len(images) == 1:
        raise ApiError(
            422,
            "last_photo_required",
            "A published listing needs at least one photo. Add another first.",
        )

    storage_path = image.storage_path
    db.delete(image)
    db.flush()
    # Close the gap so positions stay 0, 1, 2... Deleting the cover makes the next photo the
    # cover. (listing_id, position) is unique and checked on every update, so move each photo
    # down one at a time, lowest first: its new position is always already free.
    for later in (i for i in images if i.position > image.position):
        later.position -= 1
        db.flush()
    listing.updated_at = func.now()
    db.commit()

    # Same as deleting a listing: the database is the source of truth, and a file left behind
    # in storage is the acceptable failure (ADR 0010).
    try:
        storage.delete_objects([storage_path])
    except storage.StorageUnavailable as e:
        logger.warning("Deleted photo, but couldn't remove %s from storage: %s", storage_path, e)
    return Response(status_code=204)
