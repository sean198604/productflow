from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import AuthContext, get_auth_context, require_roles
from app.schemas.generation import (
    CustomerCreateRequest,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdateRequest,
)
from app.schemas.identity import UserRole
from app.services.customer_catalog import CustomerCatalogService

router = APIRouter(prefix="/customers", tags=["customers"])
customer_admin = require_roles(UserRole.OWNER, UserRole.ADMIN)


def get_service() -> CustomerCatalogService:
    return CustomerCatalogService()


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[CustomerCatalogService, Depends(get_service)],
) -> CustomerListResponse:
    items = await service.list_customers(context.session)
    return CustomerListResponse(items=items, total=len(items))


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreateRequest,
    context: Annotated[AuthContext, Depends(customer_admin)],
    service: Annotated[CustomerCatalogService, Depends(get_service)],
) -> CustomerResponse:
    return await service.create_customer(
        context.session, tenant_id=context.tenant.id, payload=payload
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[CustomerCatalogService, Depends(get_service)],
) -> CustomerResponse:
    return await service.get_customer(context.session, customer_id)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdateRequest,
    context: Annotated[AuthContext, Depends(customer_admin)],
    service: Annotated[CustomerCatalogService, Depends(get_service)],
) -> CustomerResponse:
    return await service.update_customer(
        context.session, customer_id=customer_id, payload=payload
    )


@router.post("/{customer_id}/logo", response_model=CustomerResponse)
async def upload_customer_logo(
    customer_id: UUID,
    context: Annotated[AuthContext, Depends(customer_admin)],
    service: Annotated[CustomerCatalogService, Depends(get_service)],
    logo: Annotated[UploadFile, File()],
) -> CustomerResponse:
    return await service.upload_logo(
        context.session,
        customer_id=customer_id,
        tenant_id=context.tenant.id,
        upload=logo,
    )


@router.get("/{customer_id}/logo", response_class=FileResponse)
async def get_customer_logo(
    customer_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[CustomerCatalogService, Depends(get_service)],
) -> FileResponse:
    path, stored_file = await service.logo_path(context.session, customer_id)
    return FileResponse(
        path,
        media_type=stored_file.mime_type,
        filename=stored_file.safe_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=300"},
    )
