import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class OutputTemplateType(StrEnum):
    PPTX = "pptx"
    XLSX = "xlsx"


class OutputTemplateStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class OutputTemplateVersionStatus(StrEnum):
    NEEDS_MAPPING = "needs_mapping"
    READY = "ready"
    INVALID = "invalid"
    ARCHIVED = "archived"


class OutputFormatter(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    INTEGER = "integer"
    CURRENCY = "currency"
    PERCENT = "percent"
    DATE = "date"


class OutputTransform(StrEnum):
    TRIM = "trim"
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    NORMALIZE_DIMENSION = "normalize_dimension"


class ImageFit(StrEnum):
    CONTAIN = "contain"
    COVER = "cover"
    STRETCH = "stretch"


class ImagePosition(StrEnum):
    CENTER = "center"
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"


IMAGE_SOURCES = {
    "image.main",
    "image.white_background",
    "image.lifestyle",
    "image.detail",
    "image.packaging",
    "image.other",
    "customer.logo",
}

CUSTOMER_TEXT_SOURCES = {"customer.name", "customer.code"}
CUSTOMER_SOURCES = IMAGE_SOURCES | CUSTOMER_TEXT_SOURCES


class OutputTextRunBinding(BaseModel):
    run_index: int = Field(ge=0, le=1000)
    source: str = Field(min_length=1, max_length=160)
    visible: bool = True
    product_slot: int = Field(default=1, ge=1, le=1000)
    formatter: OutputFormatter | None = None
    default_value: Any | None = None
    transform: OutputTransform | None = None
    prefix: str = Field(default="", max_length=500)
    suffix: str = Field(default="", max_length=500)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in CUSTOMER_TEXT_SOURCES:
            return normalized
        if not re.fullmatch(r"[a-z][a-z0-9_]*", normalized):
            raise ValueError("source must be a field code or supported customer text source")
        return normalized


class OutputTemplateBinding(BaseModel):
    object_key: str = Field(min_length=1, max_length=500)
    source: str = Field(min_length=1, max_length=160)
    visible: bool = True
    label: str | None = Field(default=None, max_length=160)
    formatter: OutputFormatter | None = None
    default_value: Any | None = None
    fallback: list[str] = Field(default_factory=list, max_length=8)
    transform: OutputTransform | None = None
    fit: ImageFit | None = None
    position: ImagePosition | None = None
    product_slot: int = Field(default=1, ge=1, le=1000)
    image_index: int = Field(default=0, ge=0, le=1000)
    text_runs: list[OutputTextRunBinding] = Field(default_factory=list, max_length=100)
    allow_formula: bool = False

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in CUSTOMER_SOURCES:
            return normalized
        if not re.fullmatch(r"[a-z][a-z0-9_]*", normalized):
            raise ValueError("source must be a field code or supported image source")
        return normalized

    @field_validator("fallback")
    @classmethod
    def validate_fallback(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values if value.strip()]
        invalid = set(normalized) - IMAGE_SOURCES - {"unmatched_placeholder"}
        if invalid:
            raise ValueError(f"unsupported image fallback: {', '.join(sorted(invalid))}")
        return normalized

    @model_validator(mode="after")
    def validate_image_options(self) -> "OutputTemplateBinding":
        is_image = self.source in IMAGE_SOURCES
        if not is_image and (self.fit is not None or self.position is not None or self.fallback):
            raise ValueError("fit, position, and fallback are only available for image bindings")
        if not is_image and self.image_index:
            raise ValueError("image_index is only available for image bindings")
        if is_image and self.text_runs:
            raise ValueError("text_runs are not available for image bindings")
        run_indexes = [item.run_index for item in self.text_runs]
        if len(run_indexes) != len(set(run_indexes)):
            raise ValueError("text_runs cannot bind the same text run twice")
        return self


class OutputTemplateMapping(BaseModel):
    version: Literal["1.0"] = "1.0"
    template_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bindings: list[OutputTemplateBinding] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def reject_duplicate_objects(self) -> "OutputTemplateMapping":
        object_keys = [binding.object_key for binding in self.bindings]
        if len(object_keys) != len(set(object_keys)):
            raise ValueError("一个模板对象只能绑定一次")
        return self


class OutputTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: OutputTemplateStatus | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class OutputTemplateVersionResponse(BaseModel):
    id: UUID
    version_number: int
    template_sha256: str
    original_filename: str
    safe_filename: str
    mime_type: str
    size_bytes: int
    validation_report: dict[str, Any]
    mapping_config: dict[str, Any]
    status: OutputTemplateVersionStatus
    created_at: datetime
    updated_at: datetime


class OutputTemplateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    output_type: OutputTemplateType
    status: OutputTemplateStatus
    current_version_number: int
    current_version: OutputTemplateVersionResponse
    created_at: datetime
    updated_at: datetime


class OutputTemplateListResponse(BaseModel):
    items: list[OutputTemplateResponse]
    total: int


class OutputTemplateDetailResponse(OutputTemplateResponse):
    versions: list[OutputTemplateVersionResponse]
