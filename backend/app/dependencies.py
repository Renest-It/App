from sqlalchemy.orm import Session

from fastapi import Depends

from app.db import get_db
from app.models import User


# TODO(E1.5 - SCRUM-28): Replace this stub with real authentication.
# Token verification already exists: app.auth.verify_token (SCRUM-27). The real version will
# look roughly like:
#
#   def get_current_user(
#       credentials = Depends(HTTPBearer(auto_error=False)), db: Session = Depends(get_db)
#   ) -> User:
#       claims = verify_token(credentials.credentials if credentials else None)
#       ...find or create the users row for claims.user_id...
#
# verify_token raises InvalidTokenError / ForbiddenUserError / AuthUnavailableError, which the
# handlers registered in main.py turn into 401 / 403 / 503 responses.
#
# The signature (Depends(...) -> User) stays the same, so no calling route
# needs to change when this swap happens.
def get_current_user(db: Session = Depends(get_db)) -> User:
    return db.query(User).filter(User.email == "test@creighton.edu").one()
