from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import AuthContext, get_auth_context
from app.schemas.catalog import (
    ImageType,
    ProductCreateRequest,
    ProductImageListResponse,
    ProductImageResponse,
    ProductImageUpdateRequest,
    ProductListResponse,
    ProductResponse,
    ProductStatsResponse,
    ProductUpdateRequest,
)
from app.services.product_catalog import ProductCatalogService

router = APIRouter(tags=["products"])


def get_service() -> ProductCatalogService:
    return ProductCatalogService()


@router.get("/products/stats", response_model=ProductStatsResponse)
async def product_stats(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
) -> ProductStatsResponse:
    return await service.stats(context.session)


@router.get("/products", response_model=ProductListResponse)
async def list_products(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
    search: Annotated[str | None, Query(max_length=200)] = None,
    status_filter: Annotated[
        str | None, Query(alias="status", pattern=r"^(draft|active|archived)$")
    ] = None,
    category: Annotated[str | None, Query(max_length=160)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductListResponse:
    return await service.list_products(
        context.session,
        search=search,
        status=status_filter,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
) -> ProductResponse:
    return await service.create_product(
        context.session, tenant_id=context.tenant.id, payload=payload
    )


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
) -> ProductResponse:
    return await service.get_product(context.session, product_id)


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    payload: ProductUpdateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
) -> ProductResponse:
    return await service.update_product(
        context.session, product_id=product_id, payload=payload
    )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
) -> None:
    await service.delete_product(context.session, product_id=product_id)


@router.get("/products/{product_id}/images", response_model=ProductImageListResponse)
async def list_product_images(
    product_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
) -> ProductImageListResponse:
    items, total = await service.list_images(context.session, product_id=product_id)
    return ProductImageListResponse(items=items, total=total)


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_image(
    product_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
    image: Annotated[UploadFile, File()],
    image_type: Annotated[ImageType, Form()] = ImageType.OTHER,
    is_primary: Annotated[bool, Form()] = False,
) -> ProductImageResponse:
    return await service.upload_image(
        context.session,
        tenant_id=context.tenant.id,
        product_id=product_id,
        upload=image,
        image_type=image_type,
        is_primary=is_primary,
    )


@router.get("/product-images", response_model=ProductImageListResponse)
async def list_image_library(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
    image_type: Annotated[
        str | None,
        Query(
            pattern=r"^(main|white_background|lifestyle|detail|packaging|certificate|other)$"
        ),
    ] = None,
) -> ProductImageListResponse:
    items, total = await service.list_images(context.session, image_type=image_type)
    return ProductImageListResponse(items=items, total=total)


@router.patch("/product-images/{image_id}", response_model=ProductImageResponse)
async def update_product_image(
    image_id: UUID,
    payload: ProductImageUpdateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
) -> ProductImageResponse:
    return await service.update_image(
        context.session,
        image_id=image_id,
        image_type=payload.image_type,
        sort_order=payload.sort_order,
        is_primary=payload.is_primary,
    )


@router.get("/product-images/{image_id}/content", response_class=FileResponse)
async def get_product_image_content(
    image_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ProductCatalogService, Depends(get_service)],
) -> FileResponse:
    path, stored_file = await service.get_image_file(context.session, image_id)
    return FileResponse(
        path,
        media_type=stored_file.mime_type,
        filename=stored_file.safe_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=300"},
    )
