"""Create customers, product sets, immutable generation snapshots, and tasks.

Revision ID: 20260928_0013
Revises: 20260928_0012
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260928_0013"
down_revision: str | None = "20260928_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "customers",
    "customer_settings",
    "customer_template_bindings",
    "product_sets",
    "product_set_items",
    "generation_tasks",
    "generation_task_products",
)


def _id_column() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    op.create_table(
        "customers",
        _id_column(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("logo_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("default_ppt_template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("default_xlsx_template_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'archived')",
            name="ck_customers_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_customers_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "logo_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_customers_tenant_logo_file",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "default_ppt_template_id"],
            ["output_templates.tenant_id", "output_templates.id"],
            name="fk_customers_tenant_default_ppt_template",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "default_xlsx_template_id"],
            ["output_templates.tenant_id", "output_templates.id"],
            name="fk_customers_tenant_default_xlsx_template",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_customers_tenant_id_id"),
    )
    op.create_index(
        "uq_customers_tenant_code_ci",
        "customers",
        ["tenant_id", sa.text("lower(code)")],
        unique=True,
    )
    op.create_index("ix_customers_tenant_status", "customers", ["tenant_id", "status"])

    op.create_table(
        "customer_settings",
        _id_column(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locale", sa.String(length=20), server_default="en-US", nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="USD", nullable=False),
        sa.Column(
            "timezone", sa.String(length=80), server_default="Asia/Shanghai", nullable=False
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_customer_settings_tenant_customer",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_settings"),
        sa.UniqueConstraint(
            "tenant_id", "customer_id", name="uq_customer_settings_customer"
        ),
    )

    op.create_table(
        "customer_template_bindings",
        _id_column(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_type", sa.String(length=20), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "output_type IN ('pptx', 'xlsx')",
            name="ck_customer_template_bindings_valid_output_type",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_customer_template_bindings_tenant_customer",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "output_template_id"],
            ["output_templates.tenant_id", "output_templates.id"],
            name="fk_customer_template_bindings_tenant_template",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_template_bindings"),
        sa.UniqueConstraint(
            "tenant_id",
            "customer_id",
            "output_template_id",
            name="uq_customer_template_bindings_customer_template",
        ),
    )
    op.create_index(
        "uq_customer_template_bindings_default",
        "customer_template_bindings",
        ["tenant_id", "customer_id", "output_type"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )

    op.create_table(
        "product_sets",
        _id_column(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name="ck_product_sets_valid_status"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_product_sets_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_product_sets_tenant_customer",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_sets"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_product_sets_tenant_id_id"),
    )
    op.create_index(
        "uq_product_sets_tenant_name_ci",
        "product_sets",
        ["tenant_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index("ix_product_sets_tenant_status", "product_sets", ["tenant_id", "status"])

    op.create_table(
        "product_set_items",
        _id_column(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name="ck_product_set_items_sort_order_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_set_id"],
            ["product_sets.tenant_id", "product_sets.id"],
            name="fk_product_set_items_tenant_product_set",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_product_set_items_tenant_product",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_set_items"),
        sa.UniqueConstraint(
            "tenant_id",
            "product_set_id",
            "product_id",
            name="uq_product_set_items_product",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "product_set_id",
            "sort_order",
            name="uq_product_set_items_sort_order",
        ),
    )
    op.create_index(
        "ix_product_set_items_tenant_set",
        "product_set_items",
        ["tenant_id", "product_set_id"],
    )

    op.create_table(
        "generation_tasks",
        _id_column(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_set_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("output_template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("output_type", sa.String(length=20), nullable=False),
        sa.Column(
            "product_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "customer_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "product_set_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "template_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "output_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_generation_tasks_valid_status",
        ),
        sa.CheckConstraint(
            "output_type IN ('pptx', 'xlsx')",
            name="ck_generation_tasks_valid_output_type",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_generation_tasks_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_generation_tasks_tenant_created_by",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_generation_tasks_tenant_customer",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_set_id"],
            ["product_sets.tenant_id", "product_sets.id"],
            name="fk_generation_tasks_tenant_product_set",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "output_template_version_id"],
            ["output_template_versions.tenant_id", "output_template_versions.id"],
            name="fk_generation_tasks_tenant_template_version",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "output_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_generation_tasks_tenant_output_file",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_generation_tasks"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_generation_tasks_tenant_id_id"),
    )
    op.create_index(
        "ix_generation_tasks_tenant_status", "generation_tasks", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_generation_tasks_tenant_created", "generation_tasks", ["tenant_id", "created_at"]
    )

    op.create_table(
        "generation_task_products",
        _id_column(),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("product_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name="ck_generation_task_products_sort_order_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "generation_task_id"],
            ["generation_tasks.tenant_id", "generation_tasks.id"],
            name="fk_generation_task_products_tenant_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_generation_task_products_tenant_product",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_generation_task_products"),
        sa.UniqueConstraint(
            "tenant_id",
            "generation_task_id",
            "sort_order",
            name="uq_generation_task_products_sort_order",
        ),
    )
    op.create_index(
        "ix_generation_task_products_tenant_task",
        "generation_task_products",
        ["tenant_id", "generation_task_id"],
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_select ON {table}
            FOR SELECT
            USING (app.current_platform_admin() OR tenant_id = app.current_tenant_id())
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_write ON {table}
            FOR ALL
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
            """
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write ON {table}")
        op.drop_table(table)
