"""Defer import history product references for tenant cascades.

Revision ID: 20260925_0006
Revises: 20260925_0005
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260925_0006"
down_revision: str | None = "20260925_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_import_rows_tenant_product", "import_rows", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_import_rows_tenant_product",
        "import_rows",
        "products",
        ["tenant_id", "product_id"],
        ["tenant_id", "id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.drop_constraint(
        "fk_import_image_candidates_tenant_product",
        "import_image_candidates",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_import_image_candidates_tenant_product",
        "import_image_candidates",
        "products",
        ["tenant_id", "matched_product_id"],
        ["tenant_id", "id"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_import_image_candidates_tenant_product",
        "import_image_candidates",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_import_image_candidates_tenant_product",
        "import_image_candidates",
        "products",
        ["tenant_id", "matched_product_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "fk_import_rows_tenant_product", "import_rows", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_import_rows_tenant_product",
        "import_rows",
        "products",
        ["tenant_id", "product_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
