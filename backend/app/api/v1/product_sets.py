from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import AuthContext, get_auth_context
from app.schemas.generation import (
    ProductSetCreateRequest,
    ProductSetListResponse,
    ProductSetResponse,
    ProductSetUpdateRequest,
)
from app.services.customer_catalog import ProductSetService

router = APIRouter(prefix="/product-sets", tags=["product-sets"])


def get_service() -> ProductSetService:
    return ProductSetService()


@router.get("", response_model=ProductSetListResponse)
async def list_product_sets(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductSetService, Depends(get_service)],
) -> ProductSetListResponse:
    items = await service.list_product_sets(context.session)
    return ProductSetListResponse(items=items, total=len(items))


@router.post("", response_model=ProductSetResponse, status_code=status.HTTP_201_CREATED)
async def create_product_set(
    payload: ProductSetCreateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductSetService, Depends(get_service)],
) -> ProductSetResponse:
    return await service.create_product_set(
        context.session, tenant_id=context.tenant.id, payload=payload
    )


@router.get("/{product_set_id}", response_model=ProductSetResponse)
async def get_product_set(
    product_set_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductSetService, Depends(get_service)],
) -> ProductSetResponse:
    return await service.get_product_set(context.session, product_set_id)


@router.patch("/{product_set_id}", response_model=ProductSetResponse)
async def update_product_set(
    product_set_id: UUID,
    payload: ProductSetUpdateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductSetService, Depends(get_service)],
) -> ProductSetResponse:
    return await service.update_product_set(
        context.session, product_set_id=product_set_id, payload=payload
    )
