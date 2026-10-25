"""HAQ API entry point. Run with:  python -m uvicorn app.main:app --port 8000"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import routes_auth, routes_common, routes_employer, routes_worker
from .ai import build_provider
from .config import load_settings
from .db import Database, run_migrations
from .deps import AppContext
from .errors import install_error_handlers
from .mailer import Mailer

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app(settings=None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_migrations(settings.db_path)
    db = Database(settings.db_path)
    ctx = AppContext(settings=settings, db=db, mailer=Mailer(settings, db), ai=build_provider(settings))

    app = FastAPI(title="HAQ API", version="1.0.0",
                  docs_url="/api/docs" if settings.app_env != "production" else None,
                  openapi_url="/api/openapi.json" if settings.app_env != "production" else None)
    app.state.ctx = ctx
    install_error_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "PUT"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    for r in (routes_auth.router, routes_worker.router, routes_employer.router, routes_common.router):
        app.include_router(r)

    # Serve the built React app (single-process deployment) if it exists.
    if (FRONTEND_DIST / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                from .errors import ApiError
                raise ApiError(404, "not_found", "Not found.")
            candidate = (FRONTEND_DIST / full_path).resolve()
            if full_path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    logging.getLogger("haq").info("HAQ started (env=%s, ai=%s)", settings.app_env, ctx.ai.name)
    return app


app = create_app()
