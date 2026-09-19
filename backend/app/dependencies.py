from sqlalchemy.orm import Session

from fastapi import Depends

from app.db import get_db
from app.models import User


# TODO(E1 - SCRUM-20): Replace this stub with real Supabase JWT verification.
# The real implementation will look like:
#
#   def get_current_user(
#       token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
#   ) -> User:
#       payload = verify_supabase_jwt(token)  # validates against Supabase JWKS
#       return db.query(User).filter(User.id == payload["sub"]).one()
#
# The signature (Depends(...) -> User) stays the same, so no calling route
# needs to change when this swap happens.
def get_current_user(db: Session = Depends(get_db)) -> User:
    return db.query(User).filter(User.email == "test@creighton.edu").one()
