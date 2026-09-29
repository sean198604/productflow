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


class ImportTemplate(Base):
    __tablename__ = "import_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_import_templates_tenant_id_id"),
        CheckConstraint("source_type IN ('xlsx')", name="valid_source_type"),
        CheckConstraint("status IN ('active', 'archived')", name="valid_status"),
        Index(
            "uq_import_templates_tenant_name_ci",
            "tenant_id",
            text("lower(name)"),
            unique=True,
        ),
        Index("ix_import_templates_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="xlsx")
    mapping_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_import_jobs_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "import_template_id"],
            ["import_templates.tenant_id", "import_templates.id"],
            name="fk_import_jobs_tenant_template",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_import_jobs_tenant_source_file",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_import_jobs_tenant_created_by",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "status IN ('analyzing', 'analyzed', 'preview_ready', 'importing', "
            "'completed', 'failed')",
            name="valid_status",
        ),
        CheckConstraint(
            "duplicate_strategy IS NULL OR duplicate_strategy IN "
            "('overwrite', 'update_non_empty', 'skip')",
            name="valid_duplicate_strategy",
        ),
        CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND imported_rows >= 0 "
            "AND skipped_rows >= 0 AND conflict_rows >= 0",
            name="nonnegative_counts",
        ),
        Index("ix_import_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_import_jobs_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    import_template_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_file_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="analyzing")
    analysis: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    mapping_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    duplicate_strategy: Mapped[str | None] = mapped_column(String(32))
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ImportRow(Base):
    __tablename__ = "import_rows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "import_job_id"],
            ["import_jobs.tenant_id", "import_jobs.id"],
            name="fk_import_rows_tenant_job",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_import_rows_tenant_product",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "tenant_id",
            "import_job_id",
            "source_sheet",
            "source_row",
            name="uq_import_rows_job_source",
        ),
        CheckConstraint(
            "status IN ('valid', 'invalid', 'conflict', 'imported', 'skipped', 'failed')",
            name="valid_status",
        ),
        CheckConstraint(
            "action IN ('create', 'update', 'skip', 'conflict')",
            name="valid_action",
        ),
        CheckConstraint("source_row > 0", name="source_row_positive"),
        Index("ix_import_rows_tenant_job", "tenant_id", "import_job_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    import_job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_sheet: Mapped[str] = mapped_column(String(200), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    mapped_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ImportImageCandidate(Base):
    __tablename__ = "import_image_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "import_job_id"],
            ["import_jobs.tenant_id", "import_jobs.id"],
            name="fk_import_image_candidates_tenant_job",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "stored_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_import_image_candidates_tenant_file",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "matched_product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_import_image_candidates_tenant_product",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("source_row > 0", name="source_row_positive"),
        CheckConstraint("source_column > 0", name="source_column_positive"),
        CheckConstraint(
            "image_type IN ('main', 'white_background', 'lifestyle', 'detail', "
            "'packaging', 'certificate', 'other')",
            name="valid_image_type",
        ),
        CheckConstraint(
            "match_method IN ('manual', 'filename_sku', 'anchor', 'nearby_sku', "
            "'context', 'ai_vision', 'unmatched')",
            name="valid_match_method",
        ),
        CheckConstraint(
            "match_confidence >= 0 AND match_confidence <= 1",
            name="match_confidence_range",
        ),
        CheckConstraint(
            "status IN ('matched', 'unmatched', 'imported', 'skipped')",
            name="valid_status",
        ),
        Index("ix_import_image_candidates_tenant_job", "tenant_id", "import_job_id"),
        Index("ix_import_image_candidates_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    import_job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    stored_file_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    matched_product_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    matched_sku: Mapped[str | None] = mapped_column(String(160))
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(200), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_column: Mapped[int] = mapped_column(Integer, nullable=False)
    image_type: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    match_method: Mapped[str] = mapped_column(String(32), nullable=False)
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    match_source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
