"""Replace tenant-code login with globally unique account identifiers.

Revision ID: 20260928_0009
Revises: 20260928_0008
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0009"
down_revision: str | None = "20260928_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_users_username_ci_global",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )
    op.create_index(
        "uq_users_email_ci_global",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.lookup_active_login(p_identifier text)
        RETURNS TABLE (
            tenant_id uuid,
            tenant_name text,
            tenant_slug text,
            user_id uuid
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT
                tenants.id,
                tenants.name::text,
                tenants.slug::text,
                users.id
            FROM public.users
            JOIN public.tenants ON tenants.id = users.tenant_id
            WHERE (
                users.username = lower(trim(p_identifier))
                OR users.email = lower(trim(p_identifier))
            )
              AND users.status = 'active'
              AND tenants.status = 'active'
            LIMIT 1
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app.lookup_active_login(text) FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.lookup_active_login(text)")
    op.drop_index("uq_users_email_ci_global", table_name="users")
    op.drop_index("uq_users_username_ci_global", table_name="users")
