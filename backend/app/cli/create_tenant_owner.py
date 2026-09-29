import argparse
import asyncio
import json
from getpass import getpass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Tenant, User
from app.services.field_definitions import seed_default_field_definitions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a ProductFlow tenant and owner")
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password")
    return parser.parse_args()


async def create_tenant_owner(args: argparse.Namespace) -> None:
    settings = get_settings()
    database_url = settings.database_admin_url or settings.database_url
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    password = args.password or getpass("Owner password: ")
    if len(password) < 12:
        raise ValueError("Owner password must contain at least 12 characters")

    slug = args.tenant_slug.strip().lower()
    username = args.username.strip().lower()
    email = args.email.strip().lower()
    try:
        async with factory() as session, session.begin():
            is_superuser = await session.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            )
            if not is_superuser:
                raise RuntimeError("Tenant provisioning requires the migration/admin database role")

            tenant = await session.scalar(select(Tenant).where(Tenant.slug == slug))
            if tenant is None:
                tenant = Tenant(name=args.tenant_name.strip(), slug=slug, status="active")
                session.add(tenant)
                await session.flush()
            await seed_default_field_definitions(session, tenant.id)

            user = await session.scalar(
                select(User).where(
                    User.tenant_id == tenant.id,
                    User.username == username,
                )
            )
            if user is not None:
                raise ValueError("The owner username already exists in this tenant")

            user = User(
                tenant_id=tenant.id,
                username=username,
                email=email,
                password_hash=hash_password(password),
                role="owner",
                status="active",
            )
            session.add(user)
            await session.flush()
            result = {
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
            }
        print(json.dumps(result, ensure_ascii=False))
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(create_tenant_owner(parse_args()))


if __name__ == "__main__":
    main()
