"""Defer output template audit references for complete tenant cascades.

Revision ID: 20260928_0011
Revises: 20260928_0010
Create Date: 2026-09-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260928_0011"
down_revision: str | None = "20260928_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINTS = (
    (
        "fk_output_template_versions_tenant_file",
        "stored_files",
        ["tenant_id", "stored_file_id"],
    ),
    (
        "fk_output_template_versions_tenant_created_by",
        "users",
        ["tenant_id", "created_by_user_id"],
    ),
)


def upgrade() -> None:
    for name, target, local_columns in CONSTRAINTS:
        op.drop_constraint(name, "output_template_versions", type_="foreignkey")
        op.create_foreign_key(
            name,
            "output_template_versions",
            target,
            local_columns,
            ["tenant_id", "id"],
            deferrable=True,
            initially="DEFERRED",
        )


def downgrade() -> None:
    for name, target, local_columns in reversed(CONSTRAINTS):
        op.drop_constraint(name, "output_template_versions", type_="foreignkey")
        op.create_foreign_key(
            name,
            "output_template_versions",
            target,
            local_columns,
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )
