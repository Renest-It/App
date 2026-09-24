from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.dependencies import get_current_user
from app.models import Category, Listing, User
from app.schemas.listing import ListingCreate, ListingCreateResponse, ListingListItem

# Login-only API: every route on this router requires a valid token.
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/listings", status_code=201, response_model=ListingCreateResponse)
def create_listing(
    listing: ListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    category = db.query(Category).filter(Category.id == listing.category_id).first()
    if category is None:
        raise HTTPException(
            status_code=422,
            detail=f"category_id {listing.category_id} does not exist",
        )

    new_listing = Listing(
        title=listing.title,
        description=listing.description,
        price_cents=listing.price_cents,
        category_id=listing.category_id,
        seller_id=current_user.id,
    )
    db.add(new_listing)
    db.commit()
    db.refresh(new_listing)
    return new_listing


@router.get("/listings", response_model=list[ListingListItem])
def list_listings(db: Session = Depends(get_db)):
    listings = (
        db.query(Listing)
        .options(joinedload(Listing.category))
        .filter(Listing.status == "active")
        .order_by(desc(Listing.created_at))
        .all()
    )
    return listings
