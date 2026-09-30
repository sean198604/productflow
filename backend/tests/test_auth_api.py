from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import FieldDefinition, Tenant, User
from tests.conftest import IdentityFixture


def login(client: TestClient, fixture: IdentityFixture, identifier: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": identifier,
            "password": fixture.password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_login_and_current_session(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    token = login(client, identity_fixture, identity_fixture.owner_email)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["id"] == str(identity_fixture.owner_id)
    assert payload["user"]["role"] == "owner"
    assert payload["user"]["is_platform_admin"] is True
    assert payload["tenant"]["id"] == str(identity_fixture.tenant_id)


def test_login_failure_is_generic(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": identity_fixture.owner_email,
            "password": "incorrect",
        },
    )

    assert response.status_code == 401
    assert response.json()["message"] == "用户名、邮箱或密码不正确。"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_owner_can_manage_users_but_member_cannot(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    owner_token = login(client, identity_fixture, identity_fixture.owner_email)
    member_token = login(client, identity_fixture, identity_fixture.member_email)

    owner_response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert owner_response.status_code == 200
    assert {item["id"] for item in owner_response.json()["items"]} == {
        str(identity_fixture.owner_id),
        str(identity_fixture.member_id),
    }
    assert member_response.status_code == 403


async def test_registration_creates_isolated_tenant_owner_and_default_fields(
    client: TestClient,
) -> None:
    suffix = uuid4().hex[:10]
    registered_tenant_id: UUID | None = None
    settings = get_settings()
    assert settings.database_admin_url is not None
    engine = create_async_engine(settings.database_admin_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": "Registered Trading",
                "username": f"new-owner-{suffix}",
                "email": f"owner-{suffix}@example.test",
                "password": "RegisteredPassword123!",
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        registered_tenant_id = UUID(payload["tenant"]["id"])
        assert payload["tenant"]["slug"].startswith("tenant-")
        assert payload["user"]["role"] == "owner"
        assert payload["user"]["is_platform_admin"] is False

        duplicate = client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": "Duplicate Trading",
                "username": f"new-owner-{suffix}",
                "email": f"owner-{suffix}@example.test",
                "password": "RegisteredPassword123!",
            },
        )
        assert duplicate.status_code == 409

        token = payload["access_token"]
        current = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert current.status_code == 200

        async with factory() as session, session.begin():
            tenant = await session.get(Tenant, registered_tenant_id)
            assert tenant is not None
            owner = await session.scalar(select(User).where(User.tenant_id == tenant.id))
            assert owner is not None
            field_count = len(
                list(
                    await session.scalars(
                        select(FieldDefinition).where(FieldDefinition.tenant_id == tenant.id)
                    )
                )
            )
            assert field_count > 0
    finally:
        if registered_tenant_id is not None:
            async with factory() as session, session.begin():
                await session.execute(
                    delete(Tenant).where(Tenant.id == registered_tenant_id)
                )
        await engine.dispose()


def test_platform_admin_can_read_cross_tenant_overview(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    owner_token = login(client, identity_fixture, identity_fixture.owner_email)
    member_token = login(client, identity_fixture, identity_fixture.member_email)

    overview = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    tenants = client.get(
        "/api/v1/admin/tenants",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    denied = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert overview.status_code == 200, overview.text
    assert overview.json()["counts"]["tenants"] >= 2
    assert tenants.status_code == 200, tenants.text
    tenant_ids = {item["id"] for item in tenants.json()["items"]}
    assert str(identity_fixture.tenant_id) in tenant_ids
    assert str(identity_fixture.other_tenant_id) in tenant_ids
    assert denied.status_code == 403

    for entity in (
        "customers",
        "customer_settings",
        "customer_template_bindings",
        "field_definitions",
        "product_field_values",
        "product_dictionary_entries",
        "product_images",
        "import_templates",
        "import_rows",
        "import_image_candidates",
        "output_templates",
        "output_template_versions",
        "product_sets",
        "product_set_items",
        "generation_tasks",
        "generation_task_products",
    ):
        table_response = client.get(
            f"/api/v1/admin/data/{entity}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert table_response.status_code == 200, table_response.text
        assert table_response.json()["entity"] == entity


def test_platform_admin_can_reset_password_and_revoke_existing_sessions(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    owner_token = login(client, identity_fixture, identity_fixture.owner_email)
    member_token = login(client, identity_fixture, identity_fixture.member_email)
    new_password = "ResetPassword456!"

    denied = client.post(
        f"/api/v1/admin/users/{identity_fixture.owner_id}/reset-password",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"new_password": new_password},
    )
    assert denied.status_code == 403

    reset = client.post(
        f"/api/v1/admin/users/{identity_fixture.member_id}/reset-password",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"new_password": new_password},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json() == {
        "user_id": str(identity_fixture.member_id),
        "username": identity_fixture.member_email.split("@")[0],
        "sessions_revoked": True,
    }

    revoked = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert revoked.status_code == 401

    old_password = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": identity_fixture.member_email,
            "password": identity_fixture.password,
        },
    )
    assert old_password.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": identity_fixture.member_email,
            "password": new_password,
        },
    )
    assert new_login.status_code == 200, new_login.text
