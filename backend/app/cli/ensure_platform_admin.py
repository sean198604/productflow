import asyncio
import json

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Tenant, User
from app.services.field_definitions import seed_default_field_definitions


async def ensure_platform_admin() -> None:
    settings = get_settings()
    if not settings.initial_admin_enabled:
        print(json.dumps({"status": "disabled"}))
        return

    database_url = settings.database_admin_url or settings.database_url
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tenant_slug = settings.initial_admin_tenant_slug.strip().lower()
    username = settings.initial_admin_username.strip().lower()
    email = settings.initial_admin_email.strip().lower()
    created = False
    try:
        async with factory() as session, session.begin():
            is_superuser = await session.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            )
            if not is_superuser:
                raise RuntimeError(
                    "Platform administrator bootstrap requires the admin database role"
                )

            tenant = await session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
            if tenant is None:
                tenant = Tenant(
                    name=settings.initial_admin_tenant_name.strip(),
                    slug=tenant_slug,
                    status="active",
                )
                session.add(tenant)
                await session.flush()
            elif tenant.status != "active":
                tenant.status = "active"

            await seed_default_field_definitions(session, tenant.id)
            user = await session.scalar(
                select(User).where(
                    User.tenant_id == tenant.id,
                    User.username == username,
                )
            )
            if user is None:
                user = User(
                    tenant_id=tenant.id,
                    username=username,
                    email=email,
                    password_hash=hash_password(settings.initial_admin_password),
                    role="owner",
                    is_platform_admin=True,
                    status="active",
                )
                session.add(user)
                await session.flush()
                created = True
            else:
                user.is_platform_admin = True
                user.role = "owner"
                user.status = "active"

            result = {
                "status": "created" if created else "exists",
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
                "user_id": str(user.id),
                "username": user.username,
            }
        print(json.dumps(result, ensure_ascii=False))
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(ensure_platform_admin())


if __name__ == "__main__":
    main()
