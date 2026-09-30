from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, AuthorizationError
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.db.session import SessionFactory
from app.db.tenant_context import set_tenant_context
from app.models import Tenant, User
from app.schemas.identity import UserRole
from app.services.auth import AuthService
from app.services.health import HealthService

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthContext:
    session: AsyncSession
    user: User
    tenant: Tenant


def get_health_service() -> HealthService:
    return HealthService()


def get_auth_service() -> AuthService:
    return AuthService()


async def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AsyncIterator[AuthContext]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("请先登录。")
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise AuthenticationError("登录状态无效或已经过期，请重新登录。") from exc

    async with SessionFactory() as session, session.begin():
        await set_tenant_context(
            session,
            tenant_id=claims.tenant_id,
            user_id=claims.user_id,
        )
        user = await session.scalar(select(User).where(User.id == claims.user_id))
        tenant = await session.scalar(select(Tenant).where(Tenant.id == claims.tenant_id))
        if (
            user is None
            or tenant is None
            or user.status != "active"
            or tenant.status != "active"
            or user.token_version != claims.token_version
        ):
            raise AuthenticationError("登录状态无效或账号已停用。")
        yield AuthContext(session=session, user=user, tenant=tenant)


async def get_platform_admin_context(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
) -> AuthContext:
    if not context.user.is_platform_admin:
        raise AuthorizationError("仅平台管理员可以访问系统后台。")
    await set_tenant_context(
        context.session,
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        platform_admin=True,
    )
    return context


def require_roles(*allowed_roles: UserRole) -> Callable[..., AuthContext]:
    async def dependency(
        context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    ) -> AuthContext:
        if UserRole(context.user.role) not in allowed_roles:
            raise AuthorizationError()
        return context

    return dependency
