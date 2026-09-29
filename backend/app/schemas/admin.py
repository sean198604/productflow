from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AdminOverviewResponse(BaseModel):
    counts: dict[str, int]


class AdminTenantItem(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    user_count: int
    product_count: int
    import_job_count: int
    file_count: int
    created_at: datetime


class AdminTenantListResponse(BaseModel):
    items: list[AdminTenantItem]
    total: int
    page: int
    page_size: int


class AdminUserItem(BaseModel):
    id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    username: str
    email: str
    role: str
    is_platform_admin: bool
    status: str
    last_login_at: datetime | None
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class AdminProductItem(BaseModel):
    id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    sku: str
    product_name: str
    category: str | None
    brand: str | None
    status: str
    image_count: int
    created_at: datetime
    updated_at: datetime


class AdminProductListResponse(BaseModel):
    items: list[AdminProductItem]
    total: int
    page: int
    page_size: int


class AdminImportJobItem(BaseModel):
    id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    source_filename: str
    status: str
    total_rows: int
    imported_rows: int
    conflict_rows: int
    created_at: datetime
    completed_at: datetime | None


class AdminImportJobListResponse(BaseModel):
    items: list[AdminImportJobItem]
    total: int
    page: int
    page_size: int


class AdminFileItem(BaseModel):
    id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    original_filename: str
    safe_filename: str
    sha256: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    created_at: datetime


class AdminFileListResponse(BaseModel):
    items: list[AdminFileItem]
    total: int
    page: int
    page_size: int


class AdminDataTableResponse(BaseModel):
    entity: str
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
