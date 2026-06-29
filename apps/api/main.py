from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import router as api_router
from apps.api.schemas import RootResponse
from apps.api.ws import router as ws_router

_origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]


def _configure_server_logging() -> None:
    """Expose CatalogOps logs when uvicorn keeps root logging at WARNING."""
    srv = logging.getLogger("catalogops")
    srv.setLevel(logging.INFO)
    if not srv.handlers:
        h = logging.StreamHandler()
        h.setLevel(logging.INFO)
        h.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        srv.addHandler(h)
    srv.propagate = False


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _configure_server_logging()
    yield


app = FastAPI(title="CatalogOps Agent", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="")
app.include_router(ws_router, prefix="")


@app.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    return RootResponse()
