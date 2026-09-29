import re
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class FieldDataType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    MONEY = "money"
    DATE = "date"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    IMAGE = "image"


class FieldScope(StrEnum):
    CUSTOMER = "customer"
    INTERNAL = "internal"


class ImageType(StrEnum):
    MAIN = "main"
    WHITE_BACKGROUND = "white_background"
    LIFESTYLE = "lifestyle"
    DETAIL = "detail"
    PACKAGING = "packaging"
    CERTIFICATE = "certificate"
    OTHER = "other"


class FieldDefinitionCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    data_type: FieldDataType
    scope: FieldScope = FieldScope.CUSTOMER
    is_required: bool = False
    options: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = Field(default=0, ge=0, le=100_000)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", normalized):
            raise ValueError("field code must start with a letter and use a-z, 0-9, or _")
        return normalized

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_options(self) -> "FieldDefinitionCreateRequest":
        if self.data_type in {FieldDataType.SELECT, FieldDataType.MULTI_SELECT}:
            choices = self.options.get("choices", [])
            if choices and (
                not isinstance(choices, list)
                or not all(isinstance(choice, str) and choice.strip() for choice in choices)
            ):
                raise ValueError("options.choices must be a list of non-empty strings")
        return self


class FieldDefinitionUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=160)
    scope: FieldScope | None = None
    is_required: bool | None = None
    options: dict[str, Any] | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    status: str | None = Field(default=None, pattern=r"^(active|archived)$")


class FieldDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    label: str
    data_type: FieldDataType
    scope: FieldScope
    is_system: bool
    is_core: bool
    is_required: bool
    options: dict[str, Any]
    sort_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class FieldDefinitionListResponse(BaseModel):
    items: list[FieldDefinitionResponse]


JsonValue = str | int | float | bool | date | list[str] | None


class ProductCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=160)
    product_name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    category: str | None = Field(default=None, max_length=160)
    brand: str | None = Field(default=None, max_length=160)
    status: ProductStatus = ProductStatus.ACTIVE
    custom_fields: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("sku", "product_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "category", "brand")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ProductUpdateRequest(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=160)
    product_name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    category: str | None = Field(default=None, max_length=160)
    brand: str | None = Field(default=None, max_length=160)
    status: ProductStatus | None = None
    custom_fields: dict[str, JsonValue] | None = None

    @field_validator("sku", "product_name")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ProductResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    sku: str
    product_name: str
    description: str | None
    category: str | None
    brand: str | None
    status: ProductStatus
    custom_fields: dict[str, Any]
    image_count: int = 0
    primary_image_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


class ProductStatsResponse(BaseModel):
    total: int
    active: int
    draft: int
    archived: int
    with_images: int
    field_count: int


class ProductImageUpdateRequest(BaseModel):
    image_type: ImageType | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_primary: bool | None = None


class ProductImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_sku: str
    product_name: str
    image_type: ImageType
    sort_order: int
    is_primary: bool
    original_filename: str
    safe_filename: str
    sha256: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    source_sheet: str | None
    source_row: int | None
    source_column: int | None
    match_method: str
    match_confidence: float
    match_source: str
    content_url: str
    created_at: datetime


class ProductImageListResponse(BaseModel):
    items: list[ProductImageResponse]
    total: int
