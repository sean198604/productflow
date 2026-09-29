"""Add direct tenant lifecycle foreign key to import jobs.

Revision ID: 20260925_0005
Revises: 20260925_0004
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260925_0005"
down_revision: str | None = "20260925_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_import_jobs_tenant",
        "import_jobs",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_import_jobs_tenant", "import_jobs", type_="foreignkey")
