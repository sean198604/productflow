from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
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


class OutputTemplate(Base):
    __tablename__ = "output_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_output_templates_tenant_id_id"),
        CheckConstraint("output_type IN ('pptx', 'xlsx')", name="valid_output_type"),
        CheckConstraint("status IN ('active', 'archived')", name="valid_status"),
        CheckConstraint("current_version_number >= 1", name="version_number_positive"),
        Index(
            "uq_output_templates_tenant_name_ci",
            "tenant_id",
            text("lower(name)"),
            unique=True,
        ),
        Index("ix_output_templates_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    output_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OutputTemplateVersion(Base):
    __tablename__ = "output_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "id", name="uq_output_template_versions_tenant_id_id"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "output_template_id"],
            ["output_templates.tenant_id", "output_templates.id"],
            name="fk_output_template_versions_tenant_template",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "stored_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_output_template_versions_tenant_file",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_output_template_versions_tenant_created_by",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "tenant_id",
            "output_template_id",
            "version_number",
            name="uq_output_template_versions_template_number",
        ),
        UniqueConstraint(
            "tenant_id",
            "output_template_id",
            "template_sha256",
            name="uq_output_template_versions_template_sha256",
        ),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("length(template_sha256) = 64", name="sha256_length"),
        CheckConstraint(
            "status IN ('needs_mapping', 'ready', 'invalid', 'archived')",
            name="valid_status",
        ),
        Index(
            "ix_output_template_versions_tenant_template",
            "tenant_id",
            "output_template_id",
        ),
        Index("ix_output_template_versions_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    output_template_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    stored_file_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    template_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_report: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    mapping_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_mapping")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
