"""Create tenant identity, users, and RLS policies.

Revision ID: 20260925_0002
Revises: 20260924_0001
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0002"
down_revision: str | None = "20260924_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("logo", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("slug = lower(slug)", name="ck_tenants_slug_lowercase"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'archived')",
            name="ck_tenants_valid_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="member", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("username = lower(username)", name="ck_users_username_lowercase"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_users_valid_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_users_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_users_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_users_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenants_tenant_isolation ON tenants
        USING (id = app.current_tenant_id())
        WITH CHECK (id = app.current_tenant_id())
        """
    )
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY users_tenant_isolation ON users
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.lookup_active_tenant(p_slug text)
        RETURNS TABLE (id uuid, name text, slug text)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT tenants.id, tenants.name::text, tenants.slug::text
            FROM public.tenants
            WHERE tenants.slug = lower(trim(p_slug))
              AND tenants.status = 'active'
            LIMIT 1
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app.lookup_active_tenant(text) FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.lookup_active_tenant(text)")
    op.execute("DROP POLICY IF EXISTS users_tenant_isolation ON users")
    op.execute("DROP POLICY IF EXISTS tenants_tenant_isolation ON tenants")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
