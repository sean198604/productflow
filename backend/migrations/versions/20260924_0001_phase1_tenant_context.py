"""Create the Phase 1 tenant-context database primitives.

Revision ID: 20260924_0001
Revises:
Create Date: 2026-09-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260924_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_tenant_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
            SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_user_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
            SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.current_user_id()")
    op.execute("DROP FUNCTION IF EXISTS app.current_tenant_id()")
    op.execute("DROP SCHEMA IF EXISTS app")

