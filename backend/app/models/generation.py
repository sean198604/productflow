from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
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


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_customers_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "logo_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_customers_tenant_logo_file",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "default_ppt_template_id"],
            ["output_templates.tenant_id", "output_templates.id"],
            name="fk_customers_tenant_default_ppt_template",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "default_xlsx_template_id"],
            ["output_templates.tenant_id", "output_templates.id"],
            name="fk_customers_tenant_default_xlsx_template",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'archived')", name="valid_status"
        ),
        Index("uq_customers_tenant_code_ci", "tenant_id", text("lower(code)"), unique=True),
        Index("ix_customers_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    logo_file_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    default_ppt_template_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    default_xlsx_template_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CustomerSetting(Base):
    __tablename__ = "customer_settings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_customer_settings_tenant_customer",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "customer_id", name="uq_customer_settings_customer"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    locale: Mapped[str] = mapped_column(String(20), nullable=False, default="en-US")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="Asia/Shanghai")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CustomerTemplateBinding(Base):
    __tablename__ = "customer_template_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_customer_template_bindings_tenant_customer",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "output_template_id"],
            ["output_templates.tenant_id", "output_templates.id"],
            name="fk_customer_template_bindings_tenant_template",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "customer_id",
            "output_template_id",
            name="uq_customer_template_bindings_customer_template",
        ),
        CheckConstraint("output_type IN ('pptx', 'xlsx')", name="valid_output_type"),
        Index(
            "uq_customer_template_bindings_default",
            "tenant_id",
            "customer_id",
            "output_type",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    output_template_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    output_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductSet(Base):
    __tablename__ = "product_sets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_product_sets_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_product_sets_tenant_customer",
        ),
        CheckConstraint("status IN ('active', 'archived')", name="valid_status"),
        Index(
            "uq_product_sets_tenant_name_ci",
            "tenant_id",
            text("lower(name)"),
            unique=True,
        ),
        Index("ix_product_sets_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductSetItem(Base):
    __tablename__ = "product_set_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "product_set_id"],
            ["product_sets.tenant_id", "product_sets.id"],
            name="fk_product_set_items_tenant_product_set",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_product_set_items_tenant_product",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id", "product_set_id", "product_id", name="uq_product_set_items_product"
        ),
        UniqueConstraint(
            "tenant_id",
            "product_set_id",
            "sort_order",
            name="uq_product_set_items_sort_order",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_product_set_items_tenant_set", "tenant_id", "product_set_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GenerationTask(Base):
    __tablename__ = "generation_tasks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_generation_tasks_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_generation_tasks_tenant_created_by",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_generation_tasks_tenant_customer",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_set_id"],
            ["product_sets.tenant_id", "product_sets.id"],
            name="fk_generation_tasks_tenant_product_set",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "output_template_version_id"],
            ["output_template_versions.tenant_id", "output_template_versions.id"],
            name="fk_generation_tasks_tenant_template_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "output_file_id"],
            ["stored_files.tenant_id", "stored_files.id"],
            name="fk_generation_tasks_tenant_output_file",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')", name="valid_status"
        ),
        CheckConstraint("output_type IN ('pptx', 'xlsx')", name="valid_output_type"),
        Index("ix_generation_tasks_tenant_status", "tenant_id", "status"),
        Index("ix_generation_tasks_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    output_template_version_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    output_file_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    output_type: Mapped[str] = mapped_column(String(20), nullable=False)
    product_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    customer_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    product_set_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    template_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GenerationTaskProduct(Base):
    __tablename__ = "generation_task_products"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "generation_task_id"],
            ["generation_tasks.tenant_id", "generation_tasks.id"],
            name="fk_generation_task_products_tenant_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_generation_task_products_tenant_product",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "tenant_id",
            "generation_task_id",
            "sort_order",
            name="uq_generation_task_products_sort_order",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index(
            "ix_generation_task_products_tenant_task", "tenant_id", "generation_task_id"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    generation_task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    product_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
