"""Create Excel import templates, jobs, rows, and image candidates.

Revision ID: 20260925_0004
Revises: 20260925_0003
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0004"
down_revision: str | None = "20260925_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=20), server_default="xlsx", nullable=False),
        sa.Column("mapping_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            "source_type IN ('xlsx')", name="ck_import_templates_valid_source_type"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name="ck_import_templates_valid_status"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_import_templates_tenant", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_templates"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_import_templates_tenant_id_id"),
    )
    op.create_index(
        "uq_import_templates_tenant_name_ci",
        "import_templates",
        ["tenant_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_import_templates_tenant_status", "import_templates", ["tenant_id", "status"]
    )

    op.create_table(
        "import_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="analyzing", nullable=False),
        sa.Column(
            "analysis",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("mapping_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("duplicate_strategy", sa.String(length=32), nullable=True),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conflict_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('analyzing', 'analyzed', 'preview_ready', 'importing', "
            "'completed', 'failed')",
            name="ck_import_jobs_valid_status",
        ),
        sa.CheckConstraint(
            "duplicate_strategy IS NULL OR duplicate_strategy IN "
            "('overwrite', 'update_non_empty', 'skip')",
            name="ck_import_jobs_valid_duplicate_strategy",
        ),
        sa.CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND imported_rows >= 0 "
            "AND skipped_rows >= 0 AND conflict_rows >= 0",
            name="ck_import_jobs_nonnegative_counts",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "import_template_id"],
            ["import_templates.tenant_id", "import_templates.id"],
            name="fk_import_jobs_tenant_template",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_import_jobs_tenant_source_file",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_import_jobs_tenant_created_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_jobs"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_import_jobs_tenant_id_id"),
    )
    op.create_index("ix_import_jobs_tenant_status", "import_jobs", ["tenant_id", "status"])
    op.create_index(
        "ix_import_jobs_tenant_created", "import_jobs", ["tenant_id", "created_at"]
    )

    op.create_table(
        "import_rows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_sheet", sa.String(length=200), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("source_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mapped_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column(
            "errors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
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
        sa.CheckConstraint("source_row > 0", name="ck_import_rows_source_row_positive"),
        sa.CheckConstraint(
            "status IN ('valid', 'invalid', 'conflict', 'imported', 'skipped', 'failed')",
            name="ck_import_rows_valid_status",
        ),
        sa.CheckConstraint(
            "action IN ('create', 'update', 'skip', 'conflict')",
            name="ck_import_rows_valid_action",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "import_job_id"],
            ["import_jobs.tenant_id", "import_jobs.id"],
            name="fk_import_rows_tenant_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_import_rows_tenant_product",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_rows"),
        sa.UniqueConstraint(
            "tenant_id",
            "import_job_id",
            "source_sheet",
            "source_row",
            name="uq_import_rows_job_source",
        ),
    )
    op.create_index("ix_import_rows_tenant_job", "import_rows", ["tenant_id", "import_job_id"])

    op.create_table(
        "import_image_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stored_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matched_product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_sku", sa.String(length=160), nullable=True),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("safe_filename", sa.String(length=500), nullable=False),
        sa.Column("source_sheet", sa.String(length=200), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("source_column", sa.Integer(), nullable=False),
        sa.Column("image_type", sa.String(length=32), server_default="other", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("match_method", sa.String(length=32), nullable=False),
        sa.Column("match_confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("match_source", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
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
            "source_row > 0", name="ck_import_image_candidates_source_row_positive"
        ),
        sa.CheckConstraint(
            "source_column > 0", name="ck_import_image_candidates_source_column_positive"
        ),
        sa.CheckConstraint(
            "image_type IN ('main', 'white_background', 'lifestyle', 'detail', "
            "'packaging', 'certificate', 'other')",
            name="ck_import_image_candidates_valid_image_type",
        ),
        sa.CheckConstraint(
            "match_method IN ('manual', 'filename_sku', 'anchor', 'nearby_sku', "
            "'context', 'ai_vision', 'unmatched')",
            name="ck_import_image_candidates_valid_match_method",
        ),
        sa.CheckConstraint(
            "match_confidence >= 0 AND match_confidence <= 1",
            name="ck_import_image_candidates_match_confidence_range",
        ),
        sa.CheckConstraint(
            "status IN ('matched', 'unmatched', 'imported', 'skipped')",
            name="ck_import_image_candidates_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "import_job_id"],
            ["import_jobs.tenant_id", "import_jobs.id"],
            name="fk_import_image_candidates_tenant_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "stored_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_import_image_candidates_tenant_file",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "matched_product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_import_image_candidates_tenant_product",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_image_candidates"),
    )
    op.create_index(
        "ix_import_image_candidates_tenant_job",
        "import_image_candidates",
        ["tenant_id", "import_job_id"],
    )
    op.create_index(
        "ix_import_image_candidates_tenant_status",
        "import_image_candidates",
        ["tenant_id", "status"],
    )

    for table in (
        "import_templates",
        "import_jobs",
        "import_rows",
        "import_image_candidates",
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


def downgrade() -> None:
    for table in (
        "import_image_candidates",
        "import_rows",
        "import_jobs",
        "import_templates",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    op.drop_index(
        "ix_import_image_candidates_tenant_status", table_name="import_image_candidates"
    )
    op.drop_index(
        "ix_import_image_candidates_tenant_job", table_name="import_image_candidates"
    )
    op.drop_table("import_image_candidates")
    op.drop_index("ix_import_rows_tenant_job", table_name="import_rows")
    op.drop_table("import_rows")
    op.drop_index("ix_import_jobs_tenant_created", table_name="import_jobs")
    op.drop_index("ix_import_jobs_tenant_status", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_index("ix_import_templates_tenant_status", table_name="import_templates")
    op.drop_index("uq_import_templates_tenant_name_ci", table_name="import_templates")
    op.drop_table("import_templates")
