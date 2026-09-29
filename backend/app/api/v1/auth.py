from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import AuthContext, get_auth_context, get_auth_service
from app.db.session import get_session
from app.schemas.identity import (
    LoginRequest,
    RegisterRequest,
    SessionResponse,
    TenantSummary,
    TokenResponse,
    UserSummary,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


def _token_response(authenticated) -> TokenResponse:
    return TokenResponse(
        access_token=authenticated.access_token,
        expires_in=authenticated.expires_in,
        user=UserSummary.model_validate(authenticated.user),
        tenant=TenantSummary(
            id=authenticated.tenant.id,
            name=authenticated.tenant.name,
            slug=authenticated.tenant.slug,
        ),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    async with session.begin():
        authenticated = await service.register(session, payload)
    return _token_response(authenticated)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    async with session.begin():
        authenticated = await service.authenticate(session, payload)
    return _token_response(authenticated)


@router.get("/me", response_model=SessionResponse)
async def me(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
) -> SessionResponse:
    return SessionResponse(
        user=UserSummary.model_validate(context.user),
        tenant=TenantSummary(
            id=context.tenant.id,
            name=context.tenant.name,
            slug=context.tenant.slug,
        ),
    )
