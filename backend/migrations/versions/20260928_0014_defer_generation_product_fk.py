"""Defer generation product history FK for tenant lifecycle transactions.

Revision ID: 20260928_0014
Revises: 20260928_0013
Create Date: 2026-09-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260928_0014"
down_revision: str | None = "20260928_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE generation_task_products
        DROP CONSTRAINT fk_generation_task_products_tenant_product,
        ADD CONSTRAINT fk_generation_task_products_tenant_product
        FOREIGN KEY (tenant_id, product_id)
        REFERENCES products (tenant_id, id)
        DEFERRABLE INITIALLY DEFERRED
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE generation_task_products
        DROP CONSTRAINT fk_generation_task_products_tenant_product,
        ADD CONSTRAINT fk_generation_task_products_tenant_product
        FOREIGN KEY (tenant_id, product_id)
        REFERENCES products (tenant_id, id)
        """
    )
