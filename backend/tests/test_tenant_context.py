from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.session import SessionFactory
from app.db.tenant_context import set_tenant_context


@pytest.mark.asyncio
async def test_transaction_local_tenant_context() -> None:
    tenant_id = uuid4()
    user_id = uuid4()

    async with SessionFactory() as session, session.begin():
        await set_tenant_context(session, tenant_id=tenant_id, user_id=user_id)
        result = await session.execute(
            text("SELECT app.current_tenant_id(), app.current_user_id()")
        )
        current_tenant, current_user = result.one()

    assert current_tenant == tenant_id
    assert current_user == user_id

