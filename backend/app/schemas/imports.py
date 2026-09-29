import re
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue, field_validator, model_validator


class ImportTemplateStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ImportJobStatus(StrEnum):
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    PREVIEW_READY = "preview_ready"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


class DuplicateStrategy(StrEnum):
    OVERWRITE = "overwrite"
    UPDATE_NON_EMPTY = "update_non_empty"
    SKIP = "skip"


class ImportTransform(StrEnum):
    TEXT = "text"
    TRIM = "trim"
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    NORMALIZE_DIMENSION = "normalize_dimension"


class ImportFieldMapping(BaseModel):
    source: str = Field(min_length=1, max_length=300)
    target: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    transform: ImportTransform | None = None
    default_value: JsonValue = None
    required: bool = False
    validation: dict[str, JsonValue] = Field(default_factory=dict)
    formatter: str | None = Field(default=None, max_length=80)

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return value.strip()


class ImportMappingConfig(BaseModel):
    version: str = Field(default="1.0", pattern=r"^1\.\d+$")
    sheet_names: list[str] | None = None
    header_row: int = Field(default=1, ge=1, le=10_000)
    data_start_row: int = Field(default=2, ge=1, le=10_001)
    fields: list[ImportFieldMapping] = Field(min_length=1, max_length=500)

    @field_validator("sheet_names")
    @classmethod
    def normalize_sheet_names(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        if len(set(normalized)) != len(normalized):
            raise ValueError("sheet_names 不能重复。")
        return normalized or None

    @model_validator(mode="after")
    def validate_mapping(self) -> "ImportMappingConfig":
        if self.data_start_row <= self.header_row:
            raise ValueError("data_start_row 必须位于 header_row 之后。")
        targets = [field.target for field in self.fields]
        if len(targets) != len(set(targets)):
            raise ValueError("同一个 target 只能映射一次。")
        required_targets = {"sku", "product_name"}
        if not required_targets.issubset(targets):
            missing = ", ".join(sorted(required_targets - set(targets)))
            raise ValueError(f"缺少核心字段映射：{missing}")
        return self


class ImportTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    source_type: str = Field(default="xlsx", pattern="^xlsx$")
    mapping_config: ImportMappingConfig

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class ImportTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    mapping_config: ImportMappingConfig | None = None
    status: ImportTemplateStatus | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ImportTemplateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    source_type: str
    mapping_config: ImportMappingConfig
    status: ImportTemplateStatus
    created_at: datetime
    updated_at: datetime


class ImportTemplateListResponse(BaseModel):
    items: list[ImportTemplateResponse]
    total: int


class WorkbookImageAnalysis(BaseModel):
    source_filename: str
    source_sheet: str
    source_row: int
    source_column: int
    width: int
    height: int
    mime_type: str
    sha256: str


class WorkbookSheetAnalysis(BaseModel):
    name: str
    max_row: int
    max_column: int
    merged_cells: list[str]
    headers: list[dict[str, Any]]
    sample_rows: list[dict[str, Any]]
    images: list[WorkbookImageAnalysis]
    suggested_mapping: list[dict[str, Any]]


class WorkbookAnalysis(BaseModel):
    workbook_filename: str
    workbook_sha256: str
    sheets: list[WorkbookSheetAnalysis]
    markitdown: dict[str, Any]


class ImportRowResponse(BaseModel):
    id: UUID
    source_sheet: str
    source_row: int
    source_data: dict[str, Any]
    mapped_data: dict[str, Any]
    status: str
    action: str
    errors: list[Any]
    product_id: UUID | None


class ImportImageCandidateResponse(BaseModel):
    id: UUID
    stored_file_id: UUID
    matched_product_id: UUID | None
    matched_sku: str | None
    original_filename: str
    safe_filename: str
    sha256: str
    mime_type: str
    width: int | None
    height: int | None
    source_sheet: str
    source_row: int
    source_column: int
    image_type: str
    is_primary: bool
    match_method: str
    match_confidence: float
    match_source: str
    status: str
    content_url: str


class ImportJobResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    import_template_id: UUID | None
    source_file_id: UUID
    source_filename: str
    source_sha256: str
    status: ImportJobStatus
    analysis: WorkbookAnalysis
    mapping_snapshot: ImportMappingConfig | None
    duplicate_strategy: DuplicateStrategy | None
    total_rows: int
    valid_rows: int
    imported_rows: int
    skipped_rows: int
    conflict_rows: int
    error_message: str | None
    rows: list[ImportRowResponse] = Field(default_factory=list)
    images: list[ImportImageCandidateResponse] = Field(default_factory=list)
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ImportJobListResponse(BaseModel):
    items: list[ImportJobResponse]
    total: int


class ImportPreviewRequest(BaseModel):
    import_template_id: UUID | None = None
    mapping_config: ImportMappingConfig | None = None

    @model_validator(mode="after")
    def exactly_one_mapping_source(self) -> "ImportPreviewRequest":
        if (self.import_template_id is None) == (self.mapping_config is None):
            raise ValueError("必须且只能提供 import_template_id 或 mapping_config。")
        return self


class ImportConfirmRequest(BaseModel):
    duplicate_strategy: DuplicateStrategy


class ImportImageMatchRequest(BaseModel):
    matched_product_id: UUID | None = None
    matched_sku: str | None = Field(default=None, min_length=1, max_length=160)
    image_type: str = Field(
        default="other",
        pattern=r"^(main|white_background|lifestyle|detail|packaging|certificate|other)$",
    )
    is_primary: bool = False

    @field_validator("matched_sku")
    @classmethod
    def normalize_matched_sku(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_match_target(self) -> "ImportImageMatchRequest":
        if self.matched_product_id is not None and self.matched_sku is not None:
            raise ValueError("matched_product_id 与 matched_sku 不能同时提供。")
        return self


def is_column_reference(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z]{1,3}", value.strip()) is not None
