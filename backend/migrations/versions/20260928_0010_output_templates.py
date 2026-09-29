"""Create versioned PPTX and XLSX output templates.

Revision ID: 20260928_0010
Revises: 20260928_0009
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260928_0010"
down_revision: str | None = "20260928_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "output_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("output_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("current_version_number", sa.Integer(), server_default="1", nullable=False),
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
            "output_type IN ('pptx', 'xlsx')",
            name="ck_output_templates_valid_output_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_output_templates_valid_status",
        ),
        sa.CheckConstraint(
            "current_version_number >= 1",
            name="ck_output_templates_version_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_output_templates_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_output_templates"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_output_templates_tenant_id_id"),
    )
    op.create_index(
        "uq_output_templates_tenant_name_ci",
        "output_templates",
        ["tenant_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_output_templates_tenant_status",
        "output_templates",
        ["tenant_id", "status"],
    )

    op.create_table(
        "output_template_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stored_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("template_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "validation_report",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "mapping_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=24), server_default="needs_mapping", nullable=False
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
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_output_template_versions_version_number_positive",
        ),
        sa.CheckConstraint(
            "length(template_sha256) = 64",
            name="ck_output_template_versions_sha256_length",
        ),
        sa.CheckConstraint(
            "status IN ('needs_mapping', 'ready', 'invalid', 'archived')",
            name="ck_output_template_versions_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "output_template_id"],
            ["output_templates.tenant_id", "output_templates.id"],
            name="fk_output_template_versions_tenant_template",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "stored_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_output_template_versions_tenant_file",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_output_template_versions_tenant_created_by",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_output_template_versions"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_output_template_versions_tenant_id_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "output_template_id",
            "version_number",
            name="uq_output_template_versions_template_number",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "output_template_id",
            "template_sha256",
            name="uq_output_template_versions_template_sha256",
        ),
    )
    op.create_index(
        "ix_output_template_versions_tenant_template",
        "output_template_versions",
        ["tenant_id", "output_template_id"],
    )
    op.create_index(
        "ix_output_template_versions_tenant_status",
        "output_template_versions",
        ["tenant_id", "status"],
    )

    for table in ("output_templates", "output_template_versions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_select ON {table}
            FOR SELECT
            USING (
                app.current_platform_admin()
                OR tenant_id = app.current_tenant_id()
            )
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
    for table in ("output_template_versions", "output_templates"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write ON {table}")
    op.drop_index(
        "ix_output_template_versions_tenant_status",
        table_name="output_template_versions",
    )
    op.drop_index(
        "ix_output_template_versions_tenant_template",
        table_name="output_template_versions",
    )
    op.drop_table("output_template_versions")
    op.drop_index("ix_output_templates_tenant_status", table_name="output_templates")
    op.drop_index("uq_output_templates_tenant_name_ci", table_name="output_templates")
    op.drop_table("output_templates")
