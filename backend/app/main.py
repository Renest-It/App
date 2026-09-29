from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import register_auth_error_handlers
from app.config import settings
from app.routers import categories, health, listings

app = FastAPI(title="ReNest API")
register_auth_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin] if settings.frontend_origin else [],
    allow_origin_regex=settings.frontend_preview_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(categories.router)
app.include_router(listings.router)
