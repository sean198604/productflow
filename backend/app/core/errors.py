import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    def __init__(self, *, error_type: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.status_code = status_code


class AuthenticationError(ApplicationError):
    def __init__(self, message: str = "用户名、邮箱或密码不正确。") -> None:
        super().__init__(
            error_type="authentication_error",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(ApplicationError):
    def __init__(self, message: str = "当前账号没有执行此操作的权限。") -> None:
        super().__init__(
            error_type="authorization_error",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_type="conflict_error",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class BadRequestError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_type="bad_request",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class NotFoundError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_type="not_found",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error(request: Request, exc: ApplicationError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content={
                "type": exc.error_type,
                "message": exc.message,
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "type": "validation_error",
                "message": "The request could not be validated.",
                "details": exc.errors(),
                "request_id": _request_id(request),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error", extra={"request_id": _request_id(request)})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "internal_error",
                "message": "An unexpected error occurred.",
                "request_id": _request_id(request),
            },
        )
