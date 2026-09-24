from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import Category
from app.schemas.category import CategoryOut

# Login-only API: every route on this router requires a valid token.
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()