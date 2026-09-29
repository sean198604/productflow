from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import AuthContext, get_auth_service, require_roles
from app.schemas.identity import UserCreateRequest, UserListResponse, UserRole, UserSummary
from app.services.auth import AuthService

router = APIRouter(prefix="/users", tags=["users"])
tenant_admin = require_roles(UserRole.OWNER, UserRole.ADMIN)


@router.get("", response_model=UserListResponse)
async def list_users(
    context: Annotated[AuthContext, Depends(tenant_admin)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserListResponse:
    users = await service.list_users(context.session)
    return UserListResponse(items=[UserSummary.model_validate(user) for user in users])


@router.post("", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    context: Annotated[AuthContext, Depends(tenant_admin)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserSummary:
    user = await service.create_user(context.session, actor=context.user, payload=payload)
    return UserSummary.model_validate(user)
