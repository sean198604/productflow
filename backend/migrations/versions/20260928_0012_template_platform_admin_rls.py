"""Allow platform administrators to read output template records.

Revision ID: 20260928_0012
Revises: 20260928_0011
Create Date: 2026-09-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260928_0012"
down_revision: str | None = "20260928_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("output_templates", "output_template_versions")


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
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
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_write ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
            """
        )
