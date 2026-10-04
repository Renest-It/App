"""Errors that API routes raise, returned in the same flat {code, message} shape as the auth
errors (docs/api/listings.md → Common rules)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Raise from a route to return `status` with a stable `code` and a user-safe `message`."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


def register_api_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status, content={"code": exc.code, "message": exc.message}
        )
