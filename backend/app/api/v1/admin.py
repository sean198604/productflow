from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import AuthContext, get_platform_admin_context
from app.schemas.admin import (
    AdminDataTableResponse,
    AdminFileListResponse,
    AdminImportJobListResponse,
    AdminOverviewResponse,
    AdminProductListResponse,
    AdminTenantListResponse,
    AdminUserListResponse,
)
from app.services.admin import AdminService

router = APIRouter(prefix="/admin", tags=["platform administration"])


def get_admin_service() -> AdminService:
    return AdminService()


@router.get("/overview", response_model=AdminOverviewResponse)
async def overview(
    context: Annotated[AuthContext, Depends(get_platform_admin_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
) -> AdminOverviewResponse:
    return await service.overview(context.session)


@router.get("/tenants", response_model=AdminTenantListResponse)
async def tenants(
    context: Annotated[AuthContext, Depends(get_platform_admin_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminTenantListResponse:
    return await service.tenants(context.session, page=page, page_size=page_size)


@router.get("/users", response_model=AdminUserListResponse)
async def users(
    context: Annotated[AuthContext, Depends(get_platform_admin_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminUserListResponse:
    return await service.users(context.session, page=page, page_size=page_size)


@router.get("/products", response_model=AdminProductListResponse)
async def products(
    context: Annotated[AuthContext, Depends(get_platform_admin_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminProductListResponse:
    return await service.products(context.session, page=page, page_size=page_size)


@router.get("/import-jobs", response_model=AdminImportJobListResponse)
async def import_jobs(
    context: Annotated[AuthContext, Depends(get_platform_admin_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminImportJobListResponse:
    return await service.import_jobs(context.session, page=page, page_size=page_size)


@router.get("/files", response_model=AdminFileListResponse)
async def files(
    context: Annotated[AuthContext, Depends(get_platform_admin_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminFileListResponse:
    return await service.files(context.session, page=page, page_size=page_size)


@router.get("/data/{entity}", response_model=AdminDataTableResponse)
async def data_table(
    entity: str,
    context: Annotated[AuthContext, Depends(get_platform_admin_context)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminDataTableResponse:
    result = await service.data_table(
        context.session,
        entity=entity,
        page=page,
        page_size=page_size,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown admin data entity")
    return result
