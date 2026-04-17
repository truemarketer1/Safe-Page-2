"""FastAPI entrypoint. `uvicorn app.main:app`."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import close_pool, init_pool
from .read_api import router as read_router
from .webhooks import router as webhook_router


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_pool()
        yield
        close_pool()

    app = FastAPI(title="CRM core", version="0.1.0", lifespan=lifespan)
    app.include_router(webhook_router)
    app.include_router(read_router)
    return app


app = create_app()
