"""Consistent JSON error responses: {"error": {"code": ..., "message": ...}}."""
from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def _body(code: str, message: str, details: dict | None = None) -> dict:
    err = {"code": code, "message": message}
    if details:
        err["details"] = details
    return {"error": err}


def install_error_handlers(app) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = []
        for e in exc.errors():
            loc = ".".join(str(p) for p in e.get("loc", []) if p != "body")
            fields.append({"field": loc, "message": e.get("msg", "Invalid value")})
        return JSONResponse(status_code=422, content=_body("validation_error", "Some fields need correcting.", {"fields": fields}))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        # Never echo internals (could contain personal data) back to the client.
        import logging
        logging.getLogger("haq").exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content=_body("server_error", "Something went wrong on our side. Please try again."))
