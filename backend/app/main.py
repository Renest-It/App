from fastapi import FastAPI
from app.routers import health, listings

app = FastAPI(title="ReNest API")

app.include_router(health.router)
app.include_router(listings.router)
