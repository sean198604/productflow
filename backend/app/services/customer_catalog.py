import hashlib
import os
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    Customer,
    CustomerSetting,
    CustomerTemplateBinding,
    OutputTemplate,
    Product,
    ProductImage,
    ProductSet,
    ProductSetItem,
    StoredFile,
)
from app.schemas.generation import (
    CustomerCreateRequest,
    CustomerResponse,
    CustomerSettingsPayload,
    CustomerTemplateBindingResponse,
    CustomerUpdateRequest,
    ProductSetCreateRequest,
    ProductSetItemResponse,
    ProductSetResponse,
    ProductSetUpdateRequest,
)

settings = get_settings()


def _safe_filename(original: str, digest: str, extension: str) -> str:
    stem = Path(original).stem
    normalized = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized).strip("-._") or "logo"
    return f"{digest[:12]}-{clean[:120]}{extension}"


class CustomerCatalogService:
    async def _validate_template(
        self,
        session: AsyncSession,
        template_id: UUID | None,
        expected_type: str,
    ) -> OutputTemplate | None:
        if template_id is None:
            return None
        template = await session.get(OutputTemplate, template_id)
        if template is None or template.status != "active":
            raise BadRequestError("默认输出模板不存在或已归档。")
        if template.output_type != expected_type:
            raise BadRequestError(f"默认模板必须是 {expected_type.upper()} 类型。")
        return template

    async def _sync_default_binding(
        self,
        session: AsyncSession,
        *,
        customer: Customer,
        output_type: str,
        template_id: UUID | None,
    ) -> None:
        await session.execute(
            update(CustomerTemplateBinding)
            .where(
                CustomerTemplateBinding.customer_id == customer.id,
                CustomerTemplateBinding.output_type == output_type,
            )
            .values(is_default=False)
        )
        if template_id is None:
            return
        binding = await session.scalar(
            select(CustomerTemplateBinding).where(
                CustomerTemplateBinding.customer_id == customer.id,
                CustomerTemplateBinding.output_template_id == template_id,
            )
        )
        if binding is None:
            binding = CustomerTemplateBinding(
                tenant_id=customer.tenant_id,
                customer_id=customer.id,
                output_template_id=template_id,
                output_type=output_type,
                is_default=True,
            )
            session.add(binding)
        else:
            binding.output_type = output_type
            binding.is_default = True

    async def create_customer(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: CustomerCreateRequest,
    ) -> CustomerResponse:
        await self._validate_template(session, payload.default_ppt_template_id, "pptx")
        await self._validate_template(session, payload.default_xlsx_template_id, "xlsx")
        duplicate = await session.scalar(
            select(Customer.id).where(func.lower(Customer.code) == payload.code.lower())
        )
        if duplicate is not None:
            raise ConflictError("当前租户中已存在相同客户代码。")
        customer = Customer(
            tenant_id=tenant_id,
            name=payload.name,
            code=payload.code,
            status=payload.status.value,
            default_ppt_template_id=payload.default_ppt_template_id,
            default_xlsx_template_id=payload.default_xlsx_template_id,
        )
        session.add(customer)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("当前租户中已存在相同客户代码。") from exc
        session.add(
            CustomerSetting(
                tenant_id=tenant_id,
                customer_id=customer.id,
                locale=payload.settings.locale,
                currency=payload.settings.currency,
                timezone=payload.settings.timezone,
                settings=payload.settings.settings,
            )
        )
        await self._sync_default_binding(
            session,
            customer=customer,
            output_type="pptx",
            template_id=payload.default_ppt_template_id,
        )
        await self._sync_default_binding(
            session,
            customer=customer,
            output_type="xlsx",
            template_id=payload.default_xlsx_template_id,
        )
        await session.flush()
        return await self.get_customer(session, customer.id)

    async def update_customer(
        self,
        session: AsyncSession,
        *,
        customer_id: UUID,
        payload: CustomerUpdateRequest,
    ) -> CustomerResponse:
        customer = await session.get(Customer, customer_id)
        if customer is None:
            raise NotFoundError("客户不存在。")
        values = payload.model_dump(exclude_unset=True, exclude={"settings"})
        if "code" in values:
            duplicate = await session.scalar(
                select(Customer.id).where(
                    func.lower(Customer.code) == values["code"].lower(),
                    Customer.id != customer.id,
                )
            )
            if duplicate is not None:
                raise ConflictError("当前租户中已存在相同客户代码。")
        if "default_ppt_template_id" in values:
            await self._validate_template(session, values["default_ppt_template_id"], "pptx")
        if "default_xlsx_template_id" in values:
            await self._validate_template(
                session, values["default_xlsx_template_id"], "xlsx"
            )
        for key, value in values.items():
            if key == "status" and value is not None:
                value = value.value
            setattr(customer, key, value)
        if payload.settings is not None:
            setting = await session.scalar(
                select(CustomerSetting).where(CustomerSetting.customer_id == customer.id)
            )
            if setting is None:
                setting = CustomerSetting(tenant_id=customer.tenant_id, customer_id=customer.id)
                session.add(setting)
            setting.locale = payload.settings.locale
            setting.currency = payload.settings.currency
            setting.timezone = payload.settings.timezone
            setting.settings = payload.settings.settings
        if "default_ppt_template_id" in values:
            await self._sync_default_binding(
                session,
                customer=customer,
                output_type="pptx",
                template_id=customer.default_ppt_template_id,
            )
        if "default_xlsx_template_id" in values:
            await self._sync_default_binding(
                session,
                customer=customer,
                output_type="xlsx",
                template_id=customer.default_xlsx_template_id,
            )
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("客户资料与现有记录冲突。") from exc
        return await self.get_customer(session, customer.id)

    async def list_customers(self, session: AsyncSession) -> list[CustomerResponse]:
        customers = list(
            await session.scalars(select(Customer).order_by(Customer.status, Customer.name))
        )
        return [await self._customer_response(session, customer) for customer in customers]

    async def get_customer(
        self, session: AsyncSession, customer_id: UUID
    ) -> CustomerResponse:
        customer = await session.get(Customer, customer_id)
        if customer is None:
            raise NotFoundError("客户不存在。")
        return await self._customer_response(session, customer)

    async def _customer_response(
        self, session: AsyncSession, customer: Customer
    ) -> CustomerResponse:
        setting = await session.scalar(
            select(CustomerSetting).where(CustomerSetting.customer_id == customer.id)
        )
        bindings = list(
            await session.scalars(
                select(CustomerTemplateBinding)
                .where(CustomerTemplateBinding.customer_id == customer.id)
                .order_by(
                    CustomerTemplateBinding.output_type,
                    CustomerTemplateBinding.is_default.desc(),
                )
            )
        )
        settings_payload = CustomerSettingsPayload(
            locale=setting.locale if setting else "en-US",
            currency=setting.currency if setting else "USD",
            timezone=setting.timezone if setting else "Asia/Shanghai",
            settings=setting.settings if setting else {},
        )
        return CustomerResponse(
            id=customer.id,
            tenant_id=customer.tenant_id,
            name=customer.name,
            code=customer.code,
            logo_url=f"/api/v1/customers/{customer.id}/logo" if customer.logo_file_id else None,
            status=customer.status,
            default_ppt_template_id=customer.default_ppt_template_id,
            default_xlsx_template_id=customer.default_xlsx_template_id,
            settings=settings_payload,
            template_bindings=[
                CustomerTemplateBindingResponse(
                    id=item.id,
                    output_template_id=item.output_template_id,
                    output_type=item.output_type,
                    is_default=item.is_default,
                    settings=item.settings,
                )
                for item in bindings
            ],
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )

    async def upload_logo(
        self,
        session: AsyncSession,
        *,
        customer_id: UUID,
        tenant_id: UUID,
        upload: UploadFile,
    ) -> CustomerResponse:
        customer = await session.get(Customer, customer_id)
        if customer is None:
            raise NotFoundError("客户不存在。")
        limit = settings.max_upload_size_mb * 1024 * 1024
        payload = await upload.read(limit + 1)
        if not payload or len(payload) > limit:
            raise BadRequestError("客户 Logo 为空或超过上传大小限制。")
        try:
            with Image.open(BytesIO(payload)) as image:
                image.verify()
            with Image.open(BytesIO(payload)) as image:
                width, height = image.size
                image_format = image.format
        except (UnidentifiedImageError, OSError) as exc:
            raise BadRequestError("上传文件不是可识别的图片。") from exc
        mime_type = Image.MIME.get(image_format or "")
        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(mime_type)
        if extension is None:
            raise BadRequestError("客户 Logo 仅支持 JPG、PNG 和 WebP。")
        digest = hashlib.sha256(payload).hexdigest()
        stored_file = await session.scalar(select(StoredFile).where(StoredFile.sha256 == digest))
        if stored_file is None:
            original = upload.filename or f"logo{extension}"
            storage_key = f"{tenant_id}/customer-logos/{digest[:2]}/{digest}{extension}"
            stored_file = StoredFile(
                tenant_id=tenant_id,
                storage_key=storage_key,
                original_filename=original[:500],
                safe_filename=_safe_filename(original, digest, extension),
                sha256=digest,
                mime_type=mime_type,
                size_bytes=len(payload),
                width=width,
                height=height,
            )
            session.add(stored_file)
            await session.flush()
            destination = (settings.storage_root / storage_key).resolve()
            if settings.storage_root.resolve() not in destination.parents:
                raise BadRequestError("客户 Logo 存储路径无效。")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
                temporary.write_bytes(payload)
                os.replace(temporary, destination)
        customer.logo_file_id = stored_file.id
        await session.flush()
        return await self.get_customer(session, customer.id)

    async def logo_path(
        self, session: AsyncSession, customer_id: UUID
    ) -> tuple[Path, StoredFile]:
        row = (
            await session.execute(
                select(Customer, StoredFile)
                .join(
                    StoredFile,
                    and_(
                        StoredFile.tenant_id == Customer.tenant_id,
                        StoredFile.id == Customer.logo_file_id,
                    ),
                )
                .where(Customer.id == customer_id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("客户 Logo 不存在。")
        _, stored_file = row
        path = (settings.storage_root / stored_file.storage_key).resolve()
        if settings.storage_root.resolve() not in path.parents or not path.is_file():
            raise NotFoundError("客户 Logo 文件不存在。")
        return path, stored_file


class ProductSetService:
    async def _validate_customer(
        self, session: AsyncSession, customer_id: UUID | None
    ) -> None:
        if customer_id is not None and await session.get(Customer, customer_id) is None:
            raise BadRequestError("关联客户不存在。")

    async def _replace_items(
        self,
        session: AsyncSession,
        *,
        product_set: ProductSet,
        product_ids: list[UUID],
    ) -> None:
        products = list(
            await session.scalars(select(Product).where(Product.id.in_(product_ids)))
        ) if product_ids else []
        if len(products) != len(product_ids):
            raise BadRequestError("产品组合中包含不存在的产品。")
        await session.execute(
            delete(ProductSetItem).where(ProductSetItem.product_set_id == product_set.id)
        )
        for index, product_id in enumerate(product_ids):
            session.add(
                ProductSetItem(
                    tenant_id=product_set.tenant_id,
                    product_set_id=product_set.id,
                    product_id=product_id,
                    sort_order=index,
                )
            )

    async def create_product_set(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: ProductSetCreateRequest,
    ) -> ProductSetResponse:
        await self._validate_customer(session, payload.customer_id)
        duplicate = await session.scalar(
            select(ProductSet.id).where(func.lower(ProductSet.name) == payload.name.lower())
        )
        if duplicate is not None:
            raise ConflictError("当前租户中已存在同名产品组合。")
        product_set = ProductSet(
            tenant_id=tenant_id,
            customer_id=payload.customer_id,
            name=payload.name,
            description=payload.description,
            status=payload.status.value,
        )
        session.add(product_set)
        await session.flush()
        await self._replace_items(
            session, product_set=product_set, product_ids=payload.product_ids
        )
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("产品组合名称或排序发生冲突。") from exc
        return await self.get_product_set(session, product_set.id)

    async def update_product_set(
        self,
        session: AsyncSession,
        *,
        product_set_id: UUID,
        payload: ProductSetUpdateRequest,
    ) -> ProductSetResponse:
        product_set = await session.get(ProductSet, product_set_id)
        if product_set is None:
            raise NotFoundError("产品组合不存在。")
        values = payload.model_dump(exclude_unset=True, exclude={"product_ids"})
        if "customer_id" in values:
            await self._validate_customer(session, values["customer_id"])
        if "name" in values:
            duplicate = await session.scalar(
                select(ProductSet.id).where(
                    func.lower(ProductSet.name) == values["name"].lower(),
                    ProductSet.id != product_set.id,
                )
            )
            if duplicate is not None:
                raise ConflictError("当前租户中已存在同名产品组合。")
        for key, value in values.items():
            if key == "status" and value is not None:
                value = value.value
            setattr(product_set, key, value)
        if payload.product_ids is not None:
            await self._replace_items(
                session, product_set=product_set, product_ids=payload.product_ids
            )
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("产品组合资料发生冲突。") from exc
        return await self.get_product_set(session, product_set.id)

    async def list_product_sets(self, session: AsyncSession) -> list[ProductSetResponse]:
        product_sets = list(
            await session.scalars(select(ProductSet).order_by(ProductSet.status, ProductSet.name))
        )
        return [await self._product_set_response(session, item) for item in product_sets]

    async def get_product_set(
        self, session: AsyncSession, product_set_id: UUID
    ) -> ProductSetResponse:
        product_set = await session.get(ProductSet, product_set_id)
        if product_set is None:
            raise NotFoundError("产品组合不存在。")
        return await self._product_set_response(session, product_set)

    async def _product_set_response(
        self, session: AsyncSession, product_set: ProductSet
    ) -> ProductSetResponse:
        primary_image = (
            select(ProductImage.id)
            .where(
                ProductImage.product_id == Product.id,
                ProductImage.is_primary.is_(True),
            )
            .correlate(Product)
            .scalar_subquery()
        )
        rows = (
            await session.execute(
                select(ProductSetItem, Product, primary_image)
                .join(
                    Product,
                    and_(
                        Product.tenant_id == ProductSetItem.tenant_id,
                        Product.id == ProductSetItem.product_id,
                    ),
                )
                .where(ProductSetItem.product_set_id == product_set.id)
                .order_by(ProductSetItem.sort_order)
            )
        ).all()
        return ProductSetResponse(
            id=product_set.id,
            tenant_id=product_set.tenant_id,
            customer_id=product_set.customer_id,
            name=product_set.name,
            description=product_set.description,
            status=product_set.status,
            items=[
                ProductSetItemResponse(
                    product_id=product.id,
                    sku=product.sku,
                    product_name=product.product_name,
                    sort_order=item.sort_order,
                    primary_image_url=(
                        f"/api/v1/product-images/{image_id}/content" if image_id else None
                    ),
                )
                for item, product, image_id in rows
            ],
            created_at=product_set.created_at,
            updated_at=product_set.updated_at,
        )
