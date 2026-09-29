"""Create products, field definitions, stored files, and product images.

Revision ID: 20260925_0003
Revises: 20260925_0002
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0003"
down_revision: str | None = "20260925_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "field_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("data_type", sa.String(length=24), nullable=False),
        sa.Column("scope", sa.String(length=20), server_default="customer", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_core", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "options", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("code = lower(code)", name="ck_field_definitions_code_lowercase"),
        sa.CheckConstraint(
            "data_type IN ('text', 'number', 'money', 'date', 'boolean', 'select', "
            "'multi_select', 'image')",
            name="ck_field_definitions_valid_data_type",
        ),
        sa.CheckConstraint(
            "scope IN ('customer', 'internal')",
            name="ck_field_definitions_valid_scope",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_field_definitions_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_field_definitions_tenant", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_field_definitions"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_field_definitions_tenant_id_id"
        ),
        sa.UniqueConstraint(
            "tenant_id", "code", name="uq_field_definitions_tenant_code"
        ),
    )
    op.create_index(
        "ix_field_definitions_tenant_status",
        "field_definitions",
        ["tenant_id", "status"],
    )

    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(length=160), nullable=False),
        sa.Column("product_name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=160), nullable=True),
        sa.Column("brand", sa.String(length=160), nullable=True),
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
            "status IN ('draft', 'active', 'archived')", name="ck_products_valid_status"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_products_tenant", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_products_tenant_id_id"),
    )
    op.create_index(
        "uq_products_tenant_sku_ci",
        "products",
        ["tenant_id", sa.text("lower(sku)")],
        unique=True,
    )
    op.create_index("ix_products_tenant_status", "products", ["tenant_id", "status"])
    op.create_index("ix_products_tenant_category", "products", ["tenant_id", "category"])

    op.create_table(
        "product_field_values",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["tenant_id", "field_definition_id"],
            ["field_definitions.tenant_id", "field_definitions.id"],
            name="fk_product_field_values_tenant_field_definition",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_product_field_values_tenant_product",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_field_values"),
        sa.UniqueConstraint(
            "tenant_id",
            "product_id",
            "field_definition_id",
            name="uq_product_field_values_product_field",
        ),
    )
    op.create_index(
        "ix_product_field_values_tenant_product",
        "product_field_values",
        ["tenant_id", "product_id"],
    )

    op.create_table(
        "stored_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("safe_filename", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=160), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_stored_files_size_nonnegative"),
        sa.CheckConstraint(
            "width IS NULL OR width > 0", name="ck_stored_files_width_positive"
        ),
        sa.CheckConstraint(
            "height IS NULL OR height > 0", name="ck_stored_files_height_positive"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_stored_files_tenant", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stored_files"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_stored_files_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id", "storage_key", name="uq_stored_files_tenant_storage_key"
        ),
        sa.UniqueConstraint("tenant_id", "sha256", name="uq_stored_files_tenant_sha256"),
    )

    op.create_table(
        "product_images",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stored_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_type", sa.String(length=32), server_default="other", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("source_sheet", sa.String(length=200), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_column", sa.Integer(), nullable=True),
        sa.Column("match_method", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column(
            "match_confidence", sa.Numeric(precision=4, scale=3), server_default="1", nullable=False
        ),
        sa.Column("match_source", sa.Text(), server_default="manual_upload", nullable=False),
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
            "image_type IN ('main', 'white_background', 'lifestyle', 'detail', "
            "'packaging', 'certificate', 'other')",
            name="ck_product_images_valid_image_type",
        ),
        sa.CheckConstraint(
            "match_confidence >= 0 AND match_confidence <= 1",
            name="ck_product_images_match_confidence_range",
        ),
        sa.CheckConstraint(
            "match_method IN ('manual', 'filename_sku', 'anchor', 'nearby_sku', "
            "'context', 'ai_vision', 'unmatched')",
            name="ck_product_images_valid_match_method",
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name="ck_product_images_sort_order_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_product_images_tenant_product",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "stored_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_product_images_tenant_stored_file",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_images"),
        sa.UniqueConstraint(
            "tenant_id",
            "product_id",
            "stored_file_id",
            "image_type",
            name="uq_product_images_product_file_type",
        ),
    )
    op.create_index(
        "ix_product_images_tenant_product",
        "product_images",
        ["tenant_id", "product_id"],
    )
    op.create_index(
        "uq_product_images_primary",
        "product_images",
        ["tenant_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    for table in (
        "field_definitions",
        "products",
        "product_field_values",
        "stored_files",
        "product_images",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
            """
        )

    op.execute(
        """
        INSERT INTO field_definitions
            (tenant_id, code, label, data_type, scope, is_system, is_core,
             is_required, options, sort_order, status)
        SELECT t.id, v.code, v.label, v.data_type, v.scope, true, v.is_core,
               v.is_required, v.options::jsonb, v.sort_order, 'active'
        FROM tenants AS t
        CROSS JOIN (
            VALUES
                ('sku', 'SKU', 'text', 'customer', true, true, '{}', 10),
                ('product_name', 'Product Name', 'text', 'customer', true, true, '{}', 20),
                ('description', 'Description', 'text', 'customer', true, false, '{}', 30),
                ('category', 'Category', 'text', 'customer', true, false, '{}', 40),
                ('brand', 'Brand', 'text', 'customer', true, false, '{}', 50),
                ('model', 'Model', 'text', 'customer', false, false, '{}', 60),
                ('material', 'Material', 'text', 'customer', false, false, '{}', 70),
                ('color', 'Color', 'text', 'customer', false, false, '{}', 80),
                ('size', 'Size', 'text', 'customer', false, false, '{}', 90),
                ('weight', 'Weight', 'number', 'customer', false, false, '{}', 100),
                ('voltage', 'Voltage', 'text', 'customer', false, false, '{}', 110),
                ('wattage', 'Wattage', 'number', 'customer', false, false, '{}', 120),
                ('lumens', 'Lumens', 'number', 'customer', false, false, '{}', 130),
                ('battery', 'Battery', 'text', 'customer', false, false, '{}', 140),
                ('moq', 'MOQ', 'number', 'customer', false, false, '{}', 150),
                ('price', 'Price', 'money', 'customer', false, false, '{}', 160),
                ('selling_price', 'Selling Price', 'money', 'customer', false, false, '{}', 170),
                ('currency', 'Currency', 'select', 'customer', false, false,
                 '{"choices":["USD","EUR","GBP","CNY"]}', 180),
                ('packing', 'Packing', 'text', 'customer', false, false, '{}', 190),
                ('carton_qty', 'Carton Qty', 'number', 'customer', false, false, '{}', 200),
                ('carton_size', 'Carton Size', 'text', 'customer', false, false, '{}', 210),
                ('carton_weight', 'Carton Weight', 'number', 'customer', false, false, '{}', 220),
                ('certification', 'Certification', 'multi_select', 'customer',
                 false, false, '{}', 230),
                ('country_of_origin', 'Country of Origin', 'text', 'customer',
                 false, false, '{}', 240),
                ('hs_code', 'HS Code', 'text', 'customer', false, false, '{}', 250),
                ('remark', 'Remark', 'text', 'customer', false, false, '{}', 260),
                ('supplier_cost', 'Supplier Cost', 'money', 'internal', false, false, '{}', 270),
                ('purchase_price', 'Purchase Price', 'money', 'internal', false, false, '{}', 280),
                ('margin', 'Margin', 'number', 'internal', false, false, '{}', 290),
                ('supplier', 'Supplier', 'text', 'internal', false, false, '{}', 300)
        ) AS v(code, label, data_type, scope, is_core, is_required, options, sort_order)
        ON CONFLICT (tenant_id, code) DO NOTHING
        """
    )


def downgrade() -> None:
    for table in (
        "product_images",
        "stored_files",
        "product_field_values",
        "products",
        "field_definitions",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    op.drop_index("uq_product_images_primary", table_name="product_images")
    op.drop_index("ix_product_images_tenant_product", table_name="product_images")
    op.drop_table("product_images")
    op.drop_table("stored_files")
    op.drop_index("ix_product_field_values_tenant_product", table_name="product_field_values")
    op.drop_table("product_field_values")
    op.drop_index("ix_products_tenant_category", table_name="products")
    op.drop_index("ix_products_tenant_status", table_name="products")
    op.drop_index("uq_products_tenant_sku_ci", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_field_definitions_tenant_status", table_name="field_definitions")
    op.drop_table("field_definitions")
