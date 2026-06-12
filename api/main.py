"""Phantom web API — serves the Telegram Mini App and the admin panel.

Run with:  uvicorn api.main:app --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bot_package.database import engine
from bot_package.models import Base

from .config import ApiConfig
from .routers import (
    admin_auth,
    admin_payments,
    admin_stats,
    admin_users,
    referrals,
    shop,
    user_auth,
    wallet,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ApiConfig.validate()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Phantom API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ApiConfig.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(user_auth.router, prefix=API_PREFIX)
app.include_router(shop.router, prefix=API_PREFIX)
app.include_router(wallet.router, prefix=API_PREFIX)
app.include_router(referrals.router, prefix=API_PREFIX)
app.include_router(admin_auth.router, prefix=API_PREFIX)
app.include_router(admin_stats.router, prefix=API_PREFIX)
app.include_router(admin_users.router, prefix=API_PREFIX)
app.include_router(admin_payments.router, prefix=API_PREFIX)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
