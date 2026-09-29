"""Defer import reference constraints for complete tenant cascades.

Revision ID: 20260925_0007
Revises: 20260925_0006
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260925_0007"
down_revision: str | None = "20260925_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINTS = (
    (
        "fk_import_jobs_tenant_template",
        "import_jobs",
        "import_templates",
        ["tenant_id", "import_template_id"],
        ["tenant_id", "id"],
    ),
    (
        "fk_import_jobs_tenant_source_file",
        "import_jobs",
        "stored_files",
        ["tenant_id", "source_file_id"],
        ["tenant_id", "id"],
    ),
    (
        "fk_import_jobs_tenant_created_by",
        "import_jobs",
        "users",
        ["tenant_id", "created_by_user_id"],
        ["tenant_id", "id"],
    ),
    (
        "fk_import_image_candidates_tenant_file",
        "import_image_candidates",
        "stored_files",
        ["tenant_id", "stored_file_id"],
        ["tenant_id", "id"],
    ),
)


def upgrade() -> None:
    for name, source, target, local_columns, remote_columns in CONSTRAINTS:
        op.drop_constraint(name, source, type_="foreignkey")
        op.create_foreign_key(
            name,
            source,
            target,
            local_columns,
            remote_columns,
            deferrable=True,
            initially="DEFERRED",
        )


def downgrade() -> None:
    for name, source, target, local_columns, remote_columns in reversed(CONSTRAINTS):
        op.drop_constraint(name, source, type_="foreignkey")
        op.create_foreign_key(
            name,
            source,
            target,
            local_columns,
            remote_columns,
            ondelete="RESTRICT",
        )
