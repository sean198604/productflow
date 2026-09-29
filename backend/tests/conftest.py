from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app
from app.models import Tenant, User
from app.services.field_definitions import seed_default_field_definitions


@dataclass(frozen=True, slots=True)
class IdentityFixture:
    tenant_id: UUID
    tenant_slug: str
    owner_id: UUID
    owner_username: str
    owner_email: str
    member_id: UUID
    member_email: str
    password: str
    other_tenant_id: UUID
    other_user_id: UUID


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def identity_fixture() -> AsyncIterator[IdentityFixture]:
    settings = get_settings()
    if settings.database_admin_url is None:
        pytest.skip("DATABASE_ADMIN_URL is required for identity integration tests")

    engine = create_async_engine(settings.database_admin_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex[:10]
    password = "ValidPassword123!"
    tenant = Tenant(name=f"Test Tenant {suffix}", slug=f"tenant-{suffix}", status="active")
    other_tenant = Tenant(
        name=f"Other Tenant {suffix}",
        slug=f"other-{suffix}",
        status="active",
    )
    try:
        async with factory() as session, session.begin():
            session.add_all([tenant, other_tenant])
            await session.flush()
            await seed_default_field_definitions(session, tenant.id)
            await seed_default_field_definitions(session, other_tenant.id)
            owner = User(
                tenant_id=tenant.id,
                username=f"owner-{suffix}",
                email=f"owner-{suffix}@example.test",
                password_hash=hash_password(password),
                role="owner",
                is_platform_admin=True,
                status="active",
            )
            member = User(
                tenant_id=tenant.id,
                username=f"member-{suffix}",
                email=f"member-{suffix}@example.test",
                password_hash=hash_password(password),
                role="member",
                status="active",
            )
            other_user = User(
                tenant_id=other_tenant.id,
                username=f"other-{suffix}",
                email=f"other-{suffix}@example.test",
                password_hash=hash_password(password),
                role="owner",
                status="active",
            )
            session.add_all([owner, member, other_user])
            await session.flush()
            fixture = IdentityFixture(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                owner_id=owner.id,
                owner_username=owner.username,
                owner_email=owner.email,
                member_id=member.id,
                member_email=member.email,
                password=password,
                other_tenant_id=other_tenant.id,
                other_user_id=other_user.id,
            )
        yield fixture
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                delete(Tenant).where(Tenant.id.in_([tenant.id, other_tenant.id]))
            )
        await engine.dispose()
