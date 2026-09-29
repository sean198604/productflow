"""Add self-registration and read-only platform administrator access.

Revision ID: 20260928_0008
Revises: 20260925_0007
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0008"
down_revision: str | None = "20260925_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "field_definitions",
    "products",
    "product_field_values",
    "stored_files",
    "product_images",
    "import_templates",
    "import_jobs",
    "import_rows",
    "import_image_candidates",
)


def _replace_policy(table: str, tenant_expression: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write ON {table}")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_select ON {table}
        FOR SELECT
        USING (app.current_platform_admin() OR {tenant_expression})
        """
    )
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_write ON {table}
        FOR ALL
        USING ({tenant_expression})
        WITH CHECK ({tenant_expression})
        """
    )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_users_platform_admin",
        "users",
        ["is_platform_admin"],
        postgresql_where=sa.text("is_platform_admin"),
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_platform_admin()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
            SELECT COALESCE(
                NULLIF(current_setting('app.platform_admin', true), '')::boolean,
                false
            )
        $$
        """
    )

    _replace_policy("tenants", "id = app.current_tenant_id()")
    _replace_policy("users", "tenant_id = app.current_tenant_id()")
    for table in TENANT_TABLES:
        _replace_policy(table, "tenant_id = app.current_tenant_id()")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.register_tenant_owner(
            p_tenant_name text,
            p_tenant_slug text,
            p_username text,
            p_email text,
            p_password_hash text
        )
        RETURNS TABLE (tenant_id uuid, user_id uuid)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            v_tenant_id uuid;
            v_user_id uuid;
        BEGIN
            INSERT INTO public.tenants (name, slug, status)
            VALUES (trim(p_tenant_name), lower(trim(p_tenant_slug)), 'active')
            RETURNING id INTO v_tenant_id;

            INSERT INTO public.users (
                tenant_id,
                username,
                email,
                password_hash,
                role,
                is_platform_admin,
                status
            )
            VALUES (
                v_tenant_id,
                lower(trim(p_username)),
                lower(trim(p_email)),
                p_password_hash,
                'owner',
                false,
                'active'
            )
            RETURNING id INTO v_user_id;

            RETURN QUERY SELECT v_tenant_id, v_user_id;
        END
        $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app.register_tenant_owner(text, text, text, text, text) "
        "FROM PUBLIC"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS app.register_tenant_owner(text, text, text, text, text)"
    )
    for table in ("tenants", "users", *TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write ON {table}")
        tenant_expression = (
            "id = app.current_tenant_id()"
            if table == "tenants"
            else "tenant_id = app.current_tenant_id()"
        )
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({tenant_expression})
            WITH CHECK ({tenant_expression})
            """
        )
    op.execute("DROP FUNCTION IF EXISTS app.current_platform_admin()")
    op.drop_index("ix_users_platform_admin", table_name="users")
    op.drop_column("users", "is_platform_admin")
