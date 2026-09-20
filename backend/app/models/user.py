from sqlalchemy import Column, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
