from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Customer,
    CustomerSetting,
    CustomerTemplateBinding,
    FieldDefinition,
    GenerationTask,
    GenerationTaskProduct,
    ImportImageCandidate,
    ImportJob,
    ImportRow,
    ImportTemplate,
    OutputTemplate,
    OutputTemplateVersion,
    Product,
    ProductFieldValue,
    ProductImage,
    ProductSet,
    ProductSetItem,
    StoredFile,
    Tenant,
    User,
)
from app.schemas.admin import (
    AdminDataTableResponse,
    AdminFileItem,
    AdminFileListResponse,
    AdminImportJobItem,
    AdminImportJobListResponse,
    AdminOverviewResponse,
    AdminProductItem,
    AdminProductListResponse,
    AdminTenantItem,
    AdminTenantListResponse,
    AdminUserItem,
    AdminUserListResponse,
)

ADMIN_DATA_MODELS = {
    "customers": Customer,
    "customer_settings": CustomerSetting,
    "customer_template_bindings": CustomerTemplateBinding,
    "field_definitions": FieldDefinition,
    "product_sets": ProductSet,
    "product_set_items": ProductSetItem,
    "product_field_values": ProductFieldValue,
    "product_images": ProductImage,
    "import_templates": ImportTemplate,
    "import_rows": ImportRow,
    "import_image_candidates": ImportImageCandidate,
    "output_templates": OutputTemplate,
    "output_template_versions": OutputTemplateVersion,
    "generation_tasks": GenerationTask,
    "generation_task_products": GenerationTaskProduct,
}


async def _total(session: AsyncSession, model) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


class AdminService:
    async def overview(self, session: AsyncSession) -> AdminOverviewResponse:
        models = {
            "tenants": Tenant,
            "users": User,
            "customers": Customer,
            "customer_settings": CustomerSetting,
            "customer_template_bindings": CustomerTemplateBinding,
            "field_definitions": FieldDefinition,
            "products": Product,
            "product_sets": ProductSet,
            "product_set_items": ProductSetItem,
            "product_field_values": ProductFieldValue,
            "stored_files": StoredFile,
            "product_images": ProductImage,
            "import_templates": ImportTemplate,
            "import_jobs": ImportJob,
            "import_rows": ImportRow,
            "import_image_candidates": ImportImageCandidate,
            "output_templates": OutputTemplate,
            "output_template_versions": OutputTemplateVersion,
            "generation_tasks": GenerationTask,
            "generation_task_products": GenerationTaskProduct,
        }
        counts = {name: await _total(session, model) for name, model in models.items()}
        return AdminOverviewResponse(counts=counts)

    async def tenants(
        self, session: AsyncSession, *, page: int, page_size: int
    ) -> AdminTenantListResponse:
        offset = (page - 1) * page_size
        user_count = (
            select(func.count(User.id))
            .where(User.tenant_id == Tenant.id)
            .correlate(Tenant)
            .scalar_subquery()
        )
        product_count = (
            select(func.count(Product.id))
            .where(Product.tenant_id == Tenant.id)
            .correlate(Tenant)
            .scalar_subquery()
        )
        import_count = (
            select(func.count(ImportJob.id))
            .where(ImportJob.tenant_id == Tenant.id)
            .correlate(Tenant)
            .scalar_subquery()
        )
        file_count = (
            select(func.count(StoredFile.id))
            .where(StoredFile.tenant_id == Tenant.id)
            .correlate(Tenant)
            .scalar_subquery()
        )
        rows = (
            await session.execute(
                select(Tenant, user_count, product_count, import_count, file_count)
                .order_by(Tenant.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).all()
        return AdminTenantListResponse(
            items=[
                AdminTenantItem(
                    id=tenant.id,
                    name=tenant.name,
                    slug=tenant.slug,
                    status=tenant.status,
                    user_count=int(users),
                    product_count=int(products),
                    import_job_count=int(imports),
                    file_count=int(files),
                    created_at=tenant.created_at,
                )
                for tenant, users, products, imports, files in rows
            ],
            total=await _total(session, Tenant),
            page=page,
            page_size=page_size,
        )

    async def users(
        self, session: AsyncSession, *, page: int, page_size: int
    ) -> AdminUserListResponse:
        rows = (
            await session.execute(
                select(User, Tenant.name, Tenant.slug)
                .join(Tenant, Tenant.id == User.tenant_id)
                .order_by(User.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return AdminUserListResponse(
            items=[
                AdminUserItem(
                    id=user.id,
                    tenant_id=user.tenant_id,
                    tenant_name=tenant_name,
                    tenant_slug=tenant_slug,
                    username=user.username,
                    email=user.email,
                    role=user.role,
                    is_platform_admin=user.is_platform_admin,
                    status=user.status,
                    last_login_at=user.last_login_at,
                    created_at=user.created_at,
                )
                for user, tenant_name, tenant_slug in rows
            ],
            total=await _total(session, User),
            page=page,
            page_size=page_size,
        )

    async def products(
        self, session: AsyncSession, *, page: int, page_size: int
    ) -> AdminProductListResponse:
        image_count = (
            select(func.count(ProductImage.id))
            .where(ProductImage.product_id == Product.id)
            .correlate(Product)
            .scalar_subquery()
        )
        rows = (
            await session.execute(
                select(Product, Tenant.name, Tenant.slug, image_count)
                .join(Tenant, Tenant.id == Product.tenant_id)
                .order_by(Product.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return AdminProductListResponse(
            items=[
                AdminProductItem(
                    id=product.id,
                    tenant_id=product.tenant_id,
                    tenant_name=tenant_name,
                    tenant_slug=tenant_slug,
                    sku=product.sku,
                    product_name=product.product_name,
                    category=product.category,
                    brand=product.brand,
                    status=product.status,
                    image_count=int(images),
                    created_at=product.created_at,
                    updated_at=product.updated_at,
                )
                for product, tenant_name, tenant_slug, images in rows
            ],
            total=await _total(session, Product),
            page=page,
            page_size=page_size,
        )

    async def import_jobs(
        self, session: AsyncSession, *, page: int, page_size: int
    ) -> AdminImportJobListResponse:
        rows = (
            await session.execute(
                select(ImportJob, Tenant.name, Tenant.slug, StoredFile.original_filename)
                .join(Tenant, Tenant.id == ImportJob.tenant_id)
                .join(StoredFile, StoredFile.id == ImportJob.source_file_id)
                .order_by(ImportJob.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return AdminImportJobListResponse(
            items=[
                AdminImportJobItem(
                    id=job.id,
                    tenant_id=job.tenant_id,
                    tenant_name=tenant_name,
                    tenant_slug=tenant_slug,
                    source_filename=filename,
                    status=job.status,
                    total_rows=job.total_rows,
                    imported_rows=job.imported_rows,
                    conflict_rows=job.conflict_rows,
                    created_at=job.created_at,
                    completed_at=job.completed_at,
                )
                for job, tenant_name, tenant_slug, filename in rows
            ],
            total=await _total(session, ImportJob),
            page=page,
            page_size=page_size,
        )

    async def files(
        self, session: AsyncSession, *, page: int, page_size: int
    ) -> AdminFileListResponse:
        rows = (
            await session.execute(
                select(StoredFile, Tenant.name, Tenant.slug)
                .join(Tenant, Tenant.id == StoredFile.tenant_id)
                .order_by(StoredFile.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return AdminFileListResponse(
            items=[
                AdminFileItem(
                    id=file.id,
                    tenant_id=file.tenant_id,
                    tenant_name=tenant_name,
                    tenant_slug=tenant_slug,
                    original_filename=file.original_filename,
                    safe_filename=file.safe_filename,
                    sha256=file.sha256,
                    mime_type=file.mime_type,
                    size_bytes=file.size_bytes,
                    width=file.width,
                    height=file.height,
                    created_at=file.created_at,
                )
                for file, tenant_name, tenant_slug in rows
            ],
            total=await _total(session, StoredFile),
            page=page,
            page_size=page_size,
        )

    async def data_table(
        self,
        session: AsyncSession,
        *,
        entity: str,
        page: int,
        page_size: int,
    ) -> AdminDataTableResponse | None:
        model = ADMIN_DATA_MODELS.get(entity)
        if model is None:
            return None
        order_column = model.created_at
        rows = (
            await session.execute(
                select(model, Tenant.name, Tenant.slug)
                .join(Tenant, Tenant.id == model.tenant_id)
                .order_by(order_column.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        items: list[dict] = []
        for record, tenant_name, tenant_slug in rows:
            item = {
                column.name: getattr(record, column.name)
                for column in model.__table__.columns
            }
            item["tenant_name"] = tenant_name
            item["tenant_slug"] = tenant_slug
            items.append(item)
        return AdminDataTableResponse(
            entity=entity,
            items=items,
            total=await _total(session, model),
            page=page,
            page_size=page_size,
        )
