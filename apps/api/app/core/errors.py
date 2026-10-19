"""Safe public errors never echo submitted input or local configuration."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DatasetLoadError(RuntimeError):
    """The local dataset is absent or fails the upstream Dataset contract."""


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(item["loc"]), "type": item["type"], "msg": item["msg"]}
                    for item in error.errors()
                ]
            },
        )
