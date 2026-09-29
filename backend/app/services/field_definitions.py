from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.domain.product_fields import DEFAULT_PRODUCT_FIELDS
from app.models import FieldDefinition
from app.schemas.catalog import FieldDefinitionCreateRequest, FieldDefinitionUpdateRequest


async def seed_default_field_definitions(session: AsyncSession, tenant_id: UUID) -> None:
    existing_codes = set(
        await session.scalars(
            select(FieldDefinition.code).where(FieldDefinition.tenant_id == tenant_id)
        )
    )
    for index, field in enumerate(DEFAULT_PRODUCT_FIELDS, start=1):
        if field.code in existing_codes:
            continue
        options = {"choices": ["USD", "EUR", "GBP", "CNY"]} if field.code == "currency" else {}
        session.add(
            FieldDefinition(
                tenant_id=tenant_id,
                code=field.code,
                label=field.label,
                data_type=field.data_type,
                scope=field.scope,
                is_system=True,
                is_core=field.is_core,
                is_required=field.is_required,
                options=options,
                sort_order=index * 10,
                status="active",
            )
        )
    await session.flush()


class FieldDefinitionService:
    async def list(self, session: AsyncSession, *, include_archived: bool) -> list[FieldDefinition]:
        statement = select(FieldDefinition)
        if not include_archived:
            statement = statement.where(FieldDefinition.status == "active")
        statement = statement.order_by(FieldDefinition.sort_order, FieldDefinition.created_at)
        return list((await session.scalars(statement)).all())

    async def create(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: FieldDefinitionCreateRequest,
    ) -> FieldDefinition:
        existing = await session.scalar(
            select(FieldDefinition.id).where(FieldDefinition.code == payload.code)
        )
        if existing is not None:
            raise ConflictError("当前租户中已存在相同字段代码。")

        field = FieldDefinition(
            tenant_id=tenant_id,
            code=payload.code,
            label=payload.label,
            data_type=payload.data_type.value,
            scope=payload.scope.value,
            is_system=False,
            is_core=False,
            is_required=payload.is_required,
            options=payload.options,
            sort_order=payload.sort_order,
            status="active",
        )
        session.add(field)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("当前租户中已存在相同字段代码。") from exc
        return field

    async def update(
        self,
        session: AsyncSession,
        *,
        field_id: UUID,
        payload: FieldDefinitionUpdateRequest,
    ) -> FieldDefinition:
        field = await session.get(FieldDefinition, field_id)
        if field is None:
            raise NotFoundError("字段定义不存在。")
        values = payload.model_dump(exclude_unset=True)
        if (
            field.is_system
            and values.get("scope") is not None
            and values["scope"].value != field.scope
        ):
            raise BadRequestError("系统字段的客户/内部边界不能修改。")
        for key, value in values.items():
            if key == "scope" and value is not None:
                value = value.value
            setattr(field, key, value)
        await session.flush()
        return field
