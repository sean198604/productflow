"""Add product category/brand dictionaries and transparent image derivatives.

Revision ID: 20260930_0015
Revises: 20260928_0014
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260930_0015"
down_revision: str | None = "20260928_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_dictionary_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
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
        sa.CheckConstraint(
            "kind IN ('category', 'brand')",
            name="ck_product_dictionary_entries_valid_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_product_dictionary_entries_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_product_dictionary_entries_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_dictionary_entries"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_product_dictionary_entries_tenant_id_id",
        ),
    )
    op.create_index(
        "uq_product_dictionary_entries_tenant_kind_name_ci",
        "product_dictionary_entries",
        ["tenant_id", "kind", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_product_dictionary_entries_tenant_kind_status",
        "product_dictionary_entries",
        ["tenant_id", "kind", "status"],
    )
    op.execute("ALTER TABLE product_dictionary_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE product_dictionary_entries FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY product_dictionary_entries_tenant_select
        ON product_dictionary_entries FOR SELECT
        USING (app.current_platform_admin() OR tenant_id = app.current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE POLICY product_dictionary_entries_tenant_write
        ON product_dictionary_entries FOR ALL
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
        """
    )

    op.execute(
        """
        INSERT INTO product_dictionary_entries (tenant_id, kind, name)
        SELECT DISTINCT tenant_id, 'category', btrim(category)
        FROM products
        WHERE category IS NOT NULL AND btrim(category) <> ''
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO product_dictionary_entries (tenant_id, kind, name)
        SELECT DISTINCT tenant_id, 'brand', btrim(brand)
        FROM products
        WHERE brand IS NOT NULL AND btrim(brand) <> ''
        ON CONFLICT DO NOTHING
        """
    )

    op.add_column(
        "product_images",
        sa.Column("processed_file_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column(
            "background_removed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_product_images_tenant_processed_file",
        "product_images",
        "stored_files",
        ["tenant_id", "processed_file_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_product_images_tenant_processed_file",
        "product_images",
        type_="foreignkey",
    )
    op.drop_column("product_images", "background_removed")
    op.drop_column("product_images", "processed_file_id")
    op.execute(
        "DROP POLICY IF EXISTS product_dictionary_entries_tenant_write "
        "ON product_dictionary_entries"
    )
    op.execute(
        "DROP POLICY IF EXISTS product_dictionary_entries_tenant_select "
        "ON product_dictionary_entries"
    )
    op.drop_index(
        "ix_product_dictionary_entries_tenant_kind_status",
        table_name="product_dictionary_entries",
    )
    op.drop_index(
        "uq_product_dictionary_entries_tenant_kind_name_ci",
        table_name="product_dictionary_entries",
    )
    op.drop_table("product_dictionary_entries")
