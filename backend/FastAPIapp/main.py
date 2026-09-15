from fastapi import FastAPI
from app.routers import health

app = FastAPI(title="ReNest API")

app.include_router(health.router)
