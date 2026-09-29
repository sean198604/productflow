from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class CustomerSettingsPayload(BaseModel):
    locale: str = Field(default="en-US", min_length=2, max_length=20)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class CustomerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    status: CustomerStatus = CustomerStatus.ACTIVE
    default_ppt_template_id: UUID | None = None
    default_xlsx_template_id: UUID | None = None
    settings: CustomerSettingsPayload = Field(default_factory=CustomerSettingsPayload)

    @field_validator("name", "code")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    status: CustomerStatus | None = None
    default_ppt_template_id: UUID | None = None
    default_xlsx_template_id: UUID | None = None
    settings: CustomerSettingsPayload | None = None

    @field_validator("name", "code")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CustomerTemplateBindingResponse(BaseModel):
    id: UUID
    output_template_id: UUID
    output_type: str
    is_default: bool
    settings: dict[str, Any]


class CustomerResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    code: str
    logo_url: str | None
    status: CustomerStatus
    default_ppt_template_id: UUID | None
    default_xlsx_template_id: UUID | None
    settings: CustomerSettingsPayload
    template_bindings: list[CustomerTemplateBindingResponse]
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int


class ProductSetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProductSetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    customer_id: UUID | None = None
    product_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    status: ProductSetStatus = ProductSetStatus.ACTIVE

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def reject_duplicate_products(self) -> "ProductSetCreateRequest":
        if len(self.product_ids) != len(set(self.product_ids)):
            raise ValueError("产品组合中不能重复选择同一个产品")
        return self


class ProductSetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    customer_id: UUID | None = None
    product_ids: list[UUID] | None = Field(default=None, max_length=1000)
    status: ProductSetStatus | None = None

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def reject_duplicate_products(self) -> "ProductSetUpdateRequest":
        if self.product_ids is not None and len(self.product_ids) != len(set(self.product_ids)):
            raise ValueError("产品组合中不能重复选择同一个产品")
        return self


class ProductSetItemResponse(BaseModel):
    product_id: UUID
    sku: str
    product_name: str
    sort_order: int
    primary_image_url: str | None


class ProductSetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    customer_id: UUID | None
    name: str
    description: str | None
    status: ProductSetStatus
    items: list[ProductSetItemResponse]
    created_at: datetime
    updated_at: datetime


class ProductSetListResponse(BaseModel):
    items: list[ProductSetResponse]
    total: int


class GenerationTaskStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationTaskCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    customer_id: UUID
    output_template_version_id: UUID
    product_set_id: UUID | None = None
    product_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    output_parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_task_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_selection(self) -> "GenerationTaskCreateRequest":
        if self.product_set_id is None and not self.product_ids:
            raise ValueError("请选择产品组合或至少一个产品")
        if self.product_set_id is not None and self.product_ids:
            raise ValueError("产品组合和临时产品选择不能同时提交")
        if len(self.product_ids) != len(set(self.product_ids)):
            raise ValueError("生成任务中不能重复选择同一个产品")
        return self


class GenerationTaskResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    status: GenerationTaskStatus
    output_type: str
    customer_id: UUID
    customer_name: str
    product_set_id: UUID | None
    product_set_name: str | None
    output_template_version_id: UUID
    template_name: str
    template_version_number: int
    product_count: int
    output_filename: str | None
    download_url: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class GenerationTaskDetailResponse(GenerationTaskResponse):
    product_snapshot: list[dict[str, Any]]
    customer_snapshot: dict[str, Any]
    product_set_snapshot: dict[str, Any] | None
    template_snapshot: dict[str, Any]
    output_parameters: dict[str, Any]


class GenerationTaskListResponse(BaseModel):
    items: list[GenerationTaskResponse]
    total: int
