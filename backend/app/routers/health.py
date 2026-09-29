from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user

router = APIRouter()

# The only public route: a liveness check for hosting platforms. No database, no data.
@router.get("/health")
def health_check():
    return {"status": "ok"}

# Reveals database reachability, so it requires a token (use scripts/get_token.py).
@router.get("/health/db", dependencies=[Depends(get_current_user)])
def health_check_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
