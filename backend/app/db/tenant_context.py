from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID | None = None,
    platform_admin: bool = False,
) -> None:
    """Set transaction-local identifiers consumed by PostgreSQL RLS policies."""
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id) if user_id else ""},
    )
    await session.execute(
        text("SELECT set_config('app.platform_admin', :platform_admin, true)"),
        {"platform_admin": "true" if platform_admin else "false"},
    )

