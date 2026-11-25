"""Aktau Guide API — точка входа: uvicorn app.main:app --reload"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 — регистрирует таблицы в Base.metadata
from .config import Settings, get_settings
from .db import Base, make_engine, make_session_factory
from .routers import admin, auth, businesses, cabinet, catalog, me, planner
from .seed.seed import seed_database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.check_production_safety()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        if settings.seed_on_startup:
            with app.state.session_factory() as db:
                seed_database(db, settings.today())
        yield
        engine.dispose()

    app = FastAPI(
        title="Aktau Guide API",
        version="0.1.0",
        description="Бэкенд цифрового гида по Актау: места, события, Hidden Aktau, планировщик, бизнес, тарифы, админ-панель.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = make_session_factory(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["system"])
    def health():
        return {"status": "ok"}

    for r in (auth.router, catalog.router, businesses.router, me.router, planner.router, cabinet.router, admin.router):
        app.include_router(r, prefix="/api")
    return app


app = create_app()
