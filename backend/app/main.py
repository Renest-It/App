from fastapi import FastAPI
from app.routers import categories, health

app = FastAPI(title="ReNest API")

app.include_router(health.router)
app.include_router(categories.router)