from fastapi import FastAPI
from app.routers import categories, health, listings

app = FastAPI(title="ReNest API")

app.include_router(health.router)
app.include_router(categories.router)
app.include_router(listings.router)
