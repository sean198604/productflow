import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, AuthorizationError, ConflictError
from app.core.security import (
    create_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.db.tenant_context import set_tenant_context
from app.models import Tenant, User
from app.schemas.identity import LoginRequest, RegisterRequest, UserCreateRequest, UserRole
from app.services.field_definitions import seed_default_field_definitions

_dummy_password_hash = hash_password(secrets.token_urlsafe(32))


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    access_token: str
    expires_in: int
    user: User
    tenant: Tenant


class AuthService:
    async def register(
        self,
        session: AsyncSession,
        payload: RegisterRequest,
    ) -> AuthenticatedSession:
        tenant_slug = f"tenant-{secrets.token_hex(8)}"
        try:
            async with session.begin_nested():
                registration = (
                    await session.execute(
                        text(
                            "SELECT tenant_id, user_id FROM app.register_tenant_owner("
                            ":tenant_name, :tenant_slug, :username, :email, :password_hash)"
                        ),
                        {
                            "tenant_name": payload.tenant_name,
                            "tenant_slug": tenant_slug,
                            "username": payload.username,
                            "email": payload.email,
                            "password_hash": hash_password(payload.password),
                        },
                    )
                ).mappings().one()
        except IntegrityError as exc:
            raise ConflictError("用户名或邮箱已被使用，请更换后重试。") from exc

        tenant_id = UUID(str(registration["tenant_id"]))
        user_id = UUID(str(registration["user_id"]))
        await set_tenant_context(session, tenant_id=tenant_id, user_id=user_id)
        await seed_default_field_definitions(session, tenant_id)
        user = await session.get(User, user_id)
        tenant = await session.get(Tenant, tenant_id)
        if user is None or tenant is None:
            raise AuthenticationError("注册结果无法建立登录状态。")
        access_token, expires_in = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
            token_version=user.token_version,
        )
        return AuthenticatedSession(
            access_token=access_token,
            expires_in=expires_in,
            user=user,
            tenant=tenant,
        )

    async def authenticate(
        self,
        session: AsyncSession,
        credentials: LoginRequest,
    ) -> AuthenticatedSession:
        login_row = (
            await session.execute(
                text(
                    "SELECT tenant_id, tenant_name, tenant_slug, user_id "
                    "FROM app.lookup_active_login(:identifier)"
                ),
                {"identifier": credentials.identifier},
            )
        ).mappings().one_or_none()

        if login_row is None:
            verify_password(credentials.password, _dummy_password_hash)
            raise AuthenticationError()

        tenant_id = UUID(str(login_row["tenant_id"]))
        user_id = UUID(str(login_row["user_id"]))
        await set_tenant_context(session, tenant_id=tenant_id)
        user = await session.scalar(select(User).where(User.id == user_id))

        password_hash = user.password_hash if user is not None else _dummy_password_hash
        password_valid = verify_password(credentials.password, password_hash)
        if user is None or not password_valid or user.status != "active":
            raise AuthenticationError()

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(credentials.password)
        user.last_login_at = datetime.now(UTC)
        await set_tenant_context(session, tenant_id=tenant_id, user_id=user.id)

        tenant = Tenant(
            id=tenant_id,
            name=str(login_row["tenant_name"]),
            slug=str(login_row["tenant_slug"]),
            status="active",
        )
        access_token, expires_in = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
            token_version=user.token_version,
        )
        return AuthenticatedSession(
            access_token=access_token,
            expires_in=expires_in,
            user=user,
            tenant=tenant,
        )

    async def list_users(self, session: AsyncSession) -> list[User]:
        return list((await session.scalars(select(User).order_by(User.created_at))).all())

    async def create_user(
        self,
        session: AsyncSession,
        *,
        actor: User,
        payload: UserCreateRequest,
    ) -> User:
        if actor.role == UserRole.ADMIN and payload.role != UserRole.MEMBER:
            raise AuthorizationError("管理员只能创建普通成员账号。")

        existing = await session.scalar(
            select(User.id).where(
                or_(User.username == payload.username, User.email == payload.email)
            )
        )
        if existing is not None:
            raise ConflictError("该用户名或邮箱已被使用。")

        user = User(
            tenant_id=actor.tenant_id,
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role.value,
            status="active",
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("该用户名或邮箱已被使用。") from exc
        return user
