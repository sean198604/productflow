from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FieldDefinition(Base):
    __tablename__ = "field_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_field_definitions_tenant_id_id"),
        UniqueConstraint("tenant_id", "code", name="uq_field_definitions_tenant_code"),
        CheckConstraint(
            "data_type IN ('text', 'number', 'money', 'date', 'boolean', 'select', "
            "'multi_select', 'image')",
            name="valid_data_type",
        ),
        CheckConstraint("scope IN ('customer', 'internal')", name="valid_scope"),
        CheckConstraint("status IN ('active', 'archived')", name="valid_status"),
        CheckConstraint("code = lower(code)", name="code_lowercase"),
        Index("ix_field_definitions_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    data_type: Mapped[str] = mapped_column(String(24), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="customer")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_products_tenant_id_id"),
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="valid_status"),
        Index("uq_products_tenant_sku_ci", "tenant_id", text("lower(sku)"), unique=True),
        Index("ix_products_tenant_status", "tenant_id", "status"),
        Index("ix_products_tenant_category", "tenant_id", "category"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(160), nullable=False)
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(160))
    brand: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductFieldValue(Base):
    __tablename__ = "product_field_values"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_product_field_values_tenant_product",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "field_definition_id"],
            ["field_definitions.tenant_id", "field_definitions.id"],
            name="fk_product_field_values_tenant_field_definition",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "product_id",
            "field_definition_id",
            name="uq_product_field_values_product_field",
        ),
        Index("ix_product_field_values_tenant_product", "tenant_id", "product_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    field_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StoredFile(Base):
    __tablename__ = "stored_files"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_stored_files_tenant_id_id"),
        UniqueConstraint("tenant_id", "storage_key", name="uq_stored_files_tenant_storage_key"),
        UniqueConstraint("tenant_id", "sha256", name="uq_stored_files_tenant_sha256"),
        CheckConstraint("size_bytes >= 0", name="size_nonnegative"),
        CheckConstraint("width IS NULL OR width > 0", name="width_positive"),
        CheckConstraint("height IS NULL OR height > 0", name="height_positive"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_product_images_tenant_product",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "stored_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_product_images_tenant_stored_file",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "product_id",
            "stored_file_id",
            "image_type",
            name="uq_product_images_product_file_type",
        ),
        CheckConstraint(
            "image_type IN ('main', 'white_background', 'lifestyle', 'detail', "
            "'packaging', 'certificate', 'other')",
            name="valid_image_type",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        CheckConstraint(
            "match_method IN ('manual', 'filename_sku', 'anchor', 'nearby_sku', "
            "'context', 'ai_vision', 'unmatched')",
            name="valid_match_method",
        ),
        CheckConstraint(
            "match_confidence >= 0 AND match_confidence <= 1",
            name="match_confidence_range",
        ),
        Index("ix_product_images_tenant_product", "tenant_id", "product_id"),
        Index(
            "uq_product_images_primary",
            "tenant_id",
            "product_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    stored_file_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    image_type: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_sheet: Mapped[str | None] = mapped_column(String(200))
    source_row: Mapped[int | None] = mapped_column(Integer)
    source_column: Mapped[int | None] = mapped_column(Integer)
    match_method: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    match_confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, default=Decimal("1.000")
    )
    match_source: Mapped[str] = mapped_column(Text, nullable=False, default="manual_upload")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
