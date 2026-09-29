import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.tenant_context import set_tenant_context
from app.models import Customer, ImportTemplate, OutputTemplate, Product, Tenant, User
from tests.conftest import IdentityFixture


async def test_runtime_role_sees_no_tenant_rows_without_context(
    identity_fixture: IdentityFixture,
) -> None:
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            tenants = list((await session.scalars(select(Tenant))).all())
    finally:
        await engine.dispose()

    assert tenants == []


async def test_rls_limits_users_to_current_tenant(
    identity_fixture: IdentityFixture,
) -> None:
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.tenant_id)
            users = list((await session.scalars(select(User))).all())
            other_user = await session.scalar(
                select(User).where(User.id == identity_fixture.other_user_id)
            )
    finally:
        await engine.dispose()

    assert {user.id for user in users} == {
        identity_fixture.owner_id,
        identity_fixture.member_id,
    }
    assert other_user is None


async def test_rls_limits_products_to_current_tenant(
    identity_fixture: IdentityFixture,
) -> None:
    settings = get_settings()
    runtime_engine = create_async_engine(settings.database_url)
    runtime_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    assert settings.database_admin_url is not None
    admin_engine = create_async_engine(settings.database_admin_url)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    try:
        async with admin_factory() as session, session.begin():
            session.add_all(
                [
                    Product(
                        tenant_id=identity_fixture.tenant_id,
                        sku="RLS-PRODUCT-A",
                        product_name="Tenant A Product",
                    ),
                    Product(
                        tenant_id=identity_fixture.other_tenant_id,
                        sku="RLS-PRODUCT-B",
                        product_name="Tenant B Product",
                    ),
                ]
            )

        async with runtime_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.tenant_id)
            products = list((await session.scalars(select(Product))).all())
            assert [product.product_name for product in products] == ["Tenant A Product"]

        async with runtime_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.other_tenant_id)
            products = list((await session.scalars(select(Product))).all())
            assert [product.product_name for product in products] == ["Tenant B Product"]
    finally:
        await runtime_engine.dispose()
        await admin_engine.dispose()


async def test_rls_limits_import_templates_to_current_tenant(
    identity_fixture: IdentityFixture,
) -> None:
    settings = get_settings()
    runtime_engine = create_async_engine(settings.database_url)
    runtime_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    assert settings.database_admin_url is not None
    admin_engine = create_async_engine(settings.database_admin_url)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    mapping = {
        "version": "1.0",
        "header_row": 1,
        "data_start_row": 2,
        "fields": [
            {"source": "A", "target": "sku", "required": True},
            {"source": "B", "target": "product_name", "required": True},
        ],
    }
    try:
        async with admin_factory() as session, session.begin():
            session.add_all(
                [
                    ImportTemplate(
                        tenant_id=identity_fixture.tenant_id,
                        name="Tenant A Import",
                        mapping_config=mapping,
                    ),
                    ImportTemplate(
                        tenant_id=identity_fixture.other_tenant_id,
                        name="Tenant B Import",
                        mapping_config=mapping,
                    ),
                ]
            )

        async with runtime_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.tenant_id)
            templates = list((await session.scalars(select(ImportTemplate))).all())
            assert [template.name for template in templates] == ["Tenant A Import"]

        async with runtime_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.other_tenant_id)
            templates = list((await session.scalars(select(ImportTemplate))).all())
            assert [template.name for template in templates] == ["Tenant B Import"]
    finally:
        await runtime_engine.dispose()
        await admin_engine.dispose()


async def test_rls_limits_output_templates_to_current_tenant(
    identity_fixture: IdentityFixture,
) -> None:
    settings = get_settings()
    runtime_engine = create_async_engine(settings.database_url)
    runtime_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    assert settings.database_admin_url is not None
    admin_engine = create_async_engine(settings.database_admin_url)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    try:
        async with admin_factory() as session, session.begin():
            session.add_all(
                [
                    OutputTemplate(
                        tenant_id=identity_fixture.tenant_id,
                        name="Tenant A Output",
                        output_type="pptx",
                    ),
                    OutputTemplate(
                        tenant_id=identity_fixture.other_tenant_id,
                        name="Tenant B Output",
                        output_type="xlsx",
                    ),
                ]
            )

        async with runtime_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.tenant_id)
            templates = list((await session.scalars(select(OutputTemplate))).all())
            assert [template.name for template in templates] == ["Tenant A Output"]

        async with runtime_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.other_tenant_id)
            templates = list((await session.scalars(select(OutputTemplate))).all())
            assert [template.name for template in templates] == ["Tenant B Output"]
    finally:
        await runtime_engine.dispose()
        await admin_engine.dispose()


async def test_rls_limits_customers_to_current_tenant(
    identity_fixture: IdentityFixture,
) -> None:
    settings = get_settings()
    runtime_engine = create_async_engine(settings.database_url)
    runtime_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    assert settings.database_admin_url is not None
    admin_engine = create_async_engine(settings.database_admin_url)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    try:
        async with admin_factory() as session, session.begin():
            session.add_all(
                [
                    Customer(
                        tenant_id=identity_fixture.tenant_id,
                        name="Tenant A Customer",
                        code="RLS-CUSTOMER-A",
                    ),
                    Customer(
                        tenant_id=identity_fixture.other_tenant_id,
                        name="Tenant B Customer",
                        code="RLS-CUSTOMER-B",
                    ),
                ]
            )

        async with runtime_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.tenant_id)
            customers = list((await session.scalars(select(Customer))).all())
            assert [customer.name for customer in customers] == ["Tenant A Customer"]

        async with runtime_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id=identity_fixture.other_tenant_id)
            customers = list((await session.scalars(select(Customer))).all())
            assert [customer.name for customer in customers] == ["Tenant B Customer"]
    finally:
        await runtime_engine.dispose()
        await admin_engine.dispose()


async def test_platform_admin_rls_reads_all_tenants_but_cannot_write_across_tenants(
    identity_fixture: IdentityFixture,
) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    assert settings.database_admin_url is not None
    admin_engine = create_async_engine(settings.database_admin_url)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    try:
        async with admin_factory() as session, session.begin():
            session.add_all(
                [
                    OutputTemplate(
                        tenant_id=identity_fixture.tenant_id,
                        name="Platform Visible Output A",
                        output_type="pptx",
                    ),
                    OutputTemplate(
                        tenant_id=identity_fixture.other_tenant_id,
                        name="Platform Visible Output B",
                        output_type="xlsx",
                    ),
                ]
            )

        async with factory() as session, session.begin():
            await set_tenant_context(
                session,
                tenant_id=identity_fixture.tenant_id,
                user_id=identity_fixture.owner_id,
                platform_admin=True,
            )
            tenants = list((await session.scalars(select(Tenant))).all())
            assert {identity_fixture.tenant_id, identity_fixture.other_tenant_id}.issubset(
                {tenant.id for tenant in tenants}
            )
            templates = list((await session.scalars(select(OutputTemplate))).all())
            assert {"Platform Visible Output A", "Platform Visible Output B"}.issubset(
                {template.name for template in templates}
            )

            session.add(
                Product(
                    tenant_id=identity_fixture.other_tenant_id,
                    sku="FORBIDDEN-CROSS-TENANT-WRITE",
                    product_name="Must not be inserted",
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()
    finally:
        await engine.dispose()
        await admin_engine.dispose()
