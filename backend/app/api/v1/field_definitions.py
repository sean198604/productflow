from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import AuthContext, get_auth_context, require_roles
from app.schemas.catalog import (
    FieldDefinitionCreateRequest,
    FieldDefinitionListResponse,
    FieldDefinitionResponse,
    FieldDefinitionUpdateRequest,
)
from app.schemas.identity import UserRole
from app.services.field_definitions import FieldDefinitionService

router = APIRouter(prefix="/field-definitions", tags=["field-definitions"])
field_admin = require_roles(UserRole.OWNER, UserRole.ADMIN)


def get_service() -> FieldDefinitionService:
    return FieldDefinitionService()


@router.get("", response_model=FieldDefinitionListResponse)
async def list_field_definitions(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[FieldDefinitionService, Depends(get_service)],
    include_archived: Annotated[bool, Query()] = False,
) -> FieldDefinitionListResponse:
    items = await service.list(context.session, include_archived=include_archived)
    return FieldDefinitionListResponse(
        items=[FieldDefinitionResponse.model_validate(item) for item in items]
    )


@router.post("", response_model=FieldDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_field_definition(
    payload: FieldDefinitionCreateRequest,
    context: Annotated[AuthContext, Depends(field_admin)],
    service: Annotated[FieldDefinitionService, Depends(get_service)],
) -> FieldDefinitionResponse:
    item = await service.create(
        context.session, tenant_id=context.tenant.id, payload=payload
    )
    return FieldDefinitionResponse.model_validate(item)


@router.patch("/{field_id}", response_model=FieldDefinitionResponse)
async def update_field_definition(
    field_id: UUID,
    payload: FieldDefinitionUpdateRequest,
    context: Annotated[AuthContext, Depends(field_admin)],
    service: Annotated[FieldDefinitionService, Depends(get_service)],
) -> FieldDefinitionResponse:
    item = await service.update(context.session, field_id=field_id, payload=payload)
    return FieldDefinitionResponse.model_validate(item)
