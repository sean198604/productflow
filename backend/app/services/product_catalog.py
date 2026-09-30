import hashlib
import os
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.domain.product_fields import CORE_FIELD_CODES
from app.models import (
    FieldDefinition,
    GenerationTaskProduct,
    ImportImageCandidate,
    ImportRow,
    Product,
    ProductDictionaryEntry,
    ProductFieldValue,
    ProductImage,
    StoredFile,
)
from app.schemas.catalog import (
    FieldDataType,
    ImageType,
    ProductCreateRequest,
    ProductDictionaryCreateRequest,
    ProductDictionaryResponse,
    ProductImageResponse,
    ProductListResponse,
    ProductResponse,
    ProductStatsResponse,
    ProductUpdateRequest,
)
from app.services.image_processing import ProductImageProcessor

settings = get_settings()


def _safe_filename(original: str, sha256: str, extension: str) -> str:
    stem = Path(original).stem
    normalized = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized).strip("-._") or "image"
    return f"{sha256[:12]}-{clean[:120]}{extension}"


def _normalize_field_value(field: FieldDefinition, value: object) -> object:
    if value is None:
        if field.is_required:
            raise BadRequestError(f"字段 {field.label} 为必填字段。")
        return None

    data_type = FieldDataType(field.data_type)
    if data_type in {FieldDataType.TEXT, FieldDataType.IMAGE}:
        if not isinstance(value, str):
            raise BadRequestError(f"字段 {field.label} 必须是文本。")
        return value.strip()
    if data_type == FieldDataType.NUMBER:
        if isinstance(value, bool):
            raise BadRequestError(f"字段 {field.label} 必须是数字。")
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise BadRequestError(f"字段 {field.label} 必须是数字。") from exc
        return int(number) if number == number.to_integral_value() else float(number)
    if data_type == FieldDataType.MONEY:
        if isinstance(value, bool):
            raise BadRequestError(f"字段 {field.label} 必须是金额。")
        try:
            return format(Decimal(str(value)), "f")
        except (InvalidOperation, ValueError) as exc:
            raise BadRequestError(f"字段 {field.label} 必须是金额。") from exc
    if data_type == FieldDataType.DATE:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value).isoformat()
            except ValueError as exc:
                raise BadRequestError(f"字段 {field.label} 必须是 ISO 日期。") from exc
        raise BadRequestError(f"字段 {field.label} 必须是 ISO 日期。")
    if data_type == FieldDataType.BOOLEAN:
        if not isinstance(value, bool):
            raise BadRequestError(f"字段 {field.label} 必须是布尔值。")
        return value

    choices = field.options.get("choices", [])
    if data_type == FieldDataType.SELECT:
        if not isinstance(value, str):
            raise BadRequestError(f"字段 {field.label} 必须是一个选项。")
        if choices and value not in choices:
            raise BadRequestError(f"字段 {field.label} 的选项无效。")
        return value
    if data_type == FieldDataType.MULTI_SELECT:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise BadRequestError(f"字段 {field.label} 必须是文本选项列表。")
        if choices and any(item not in choices for item in value):
            raise BadRequestError(f"字段 {field.label} 包含无效选项。")
        return value
    raise BadRequestError(f"字段 {field.label} 的类型不受支持。")


class ProductCatalogService:
    def __init__(self) -> None:
        self.image_processor = ProductImageProcessor()

    async def _get_product(self, session: AsyncSession, product_id: UUID) -> Product:
        product = await session.get(Product, product_id)
        if product is None:
            raise NotFoundError("产品不存在。")
        return product

    async def _field_map(
        self, session: AsyncSession, codes: set[str]
    ) -> dict[str, FieldDefinition]:
        if not codes:
            return {}
        fields = list(
            await session.scalars(
                select(FieldDefinition).where(
                    FieldDefinition.code.in_(codes), FieldDefinition.status == "active"
                )
            )
        )
        by_code = {field.code: field for field in fields}
        unknown = codes - by_code.keys()
        if unknown:
            raise BadRequestError(f"未知或已停用字段：{', '.join(sorted(unknown))}")
        core = codes & CORE_FIELD_CODES
        if core:
            raise BadRequestError(f"核心字段不能写入 custom_fields：{', '.join(sorted(core))}")
        return by_code

    async def _apply_custom_fields(
        self,
        session: AsyncSession,
        *,
        product: Product,
        values: dict[str, object],
        require_all: bool = False,
    ) -> None:
        fields = await self._field_map(session, set(values))
        if require_all:
            required = list(
                await session.scalars(
                    select(FieldDefinition).where(
                        FieldDefinition.status == "active",
                        FieldDefinition.is_required.is_(True),
                        FieldDefinition.is_core.is_(False),
                    )
                )
            )
            missing = [field.label for field in required if values.get(field.code) is None]
            if missing:
                raise BadRequestError(f"缺少必填字段：{', '.join(missing)}")

        existing = {
            item.field_definition_id: item
            for item in await session.scalars(
                select(ProductFieldValue).where(ProductFieldValue.product_id == product.id)
            )
        }
        for code, raw_value in values.items():
            field = fields[code]
            normalized = _normalize_field_value(field, raw_value)
            current = existing.get(field.id)
            if normalized is None:
                if current is not None:
                    await session.delete(current)
                continue
            if current is None:
                session.add(
                    ProductFieldValue(
                        tenant_id=product.tenant_id,
                        product_id=product.id,
                        field_definition_id=field.id,
                        value=normalized,
                    )
                )
            else:
                current.value = normalized

    async def _ensure_dictionary_entries(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        category: str | None,
        brand: str | None,
    ) -> None:
        for kind, name in (("category", category), ("brand", brand)):
            if not name:
                continue
            await session.execute(
                pg_insert(ProductDictionaryEntry)
                .values(tenant_id=tenant_id, kind=kind, name=name, status="active")
                .on_conflict_do_nothing()
            )

    async def list_dictionary_entries(
        self,
        session: AsyncSession,
        *,
        kind: str | None,
    ) -> list[ProductDictionaryResponse]:
        filters = [ProductDictionaryEntry.status == "active"]
        if kind:
            filters.append(ProductDictionaryEntry.kind == kind)
        entries = list(
            await session.scalars(
                select(ProductDictionaryEntry)
                .where(*filters)
                .order_by(ProductDictionaryEntry.kind, func.lower(ProductDictionaryEntry.name))
            )
        )
        return [ProductDictionaryResponse.model_validate(entry) for entry in entries]

    async def create_dictionary_entry(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: ProductDictionaryCreateRequest,
    ) -> ProductDictionaryResponse:
        await session.execute(
            pg_insert(ProductDictionaryEntry)
            .values(
                tenant_id=tenant_id,
                kind=payload.kind.value,
                name=payload.name,
                status="active",
            )
            .on_conflict_do_nothing()
        )
        entry = await session.scalar(
            select(ProductDictionaryEntry).where(
                ProductDictionaryEntry.kind == payload.kind.value,
                func.lower(ProductDictionaryEntry.name) == payload.name.lower(),
            )
        )
        if entry is None:
            raise ConflictError("分类或品牌字典项创建失败。")
        if entry.status != "active":
            entry.status = "active"
            entry.name = payload.name
            await session.flush()
        return ProductDictionaryResponse.model_validate(entry)

    async def create_product(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: ProductCreateRequest,
    ) -> ProductResponse:
        duplicate = await session.scalar(
            select(Product.id).where(func.lower(Product.sku) == payload.sku.lower())
        )
        if duplicate is not None:
            raise ConflictError("当前租户中已存在相同 SKU。")
        product = Product(
            tenant_id=tenant_id,
            sku=payload.sku,
            product_name=payload.product_name,
            description=payload.description,
            category=payload.category,
            brand=payload.brand,
            status=payload.status.value,
        )
        session.add(product)
        try:
            await session.flush()
            await self._ensure_dictionary_entries(
                session,
                tenant_id=tenant_id,
                category=product.category,
                brand=product.brand,
            )
            await self._apply_custom_fields(
                session,
                product=product,
                values=payload.custom_fields,
                require_all=True,
            )
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("当前租户中已存在相同 SKU。") from exc
        return await self.get_product(session, product.id)

    async def update_product(
        self,
        session: AsyncSession,
        *,
        product_id: UUID,
        payload: ProductUpdateRequest,
    ) -> ProductResponse:
        product = await self._get_product(session, product_id)
        values = payload.model_dump(exclude_unset=True, exclude={"custom_fields"})
        if "sku" in values:
            if values["sku"] is None:
                raise BadRequestError("SKU 不能为空。")
            duplicate = await session.scalar(
                select(Product.id).where(
                    func.lower(Product.sku) == values["sku"].lower(), Product.id != product.id
                )
            )
            if duplicate is not None:
                raise ConflictError("当前租户中已存在相同 SKU。")
        if "product_name" in values and values["product_name"] is None:
            raise BadRequestError("产品名称不能为空。")
        for key, value in values.items():
            if key == "status" and value is not None:
                value = value.value
            setattr(product, key, value)
        if payload.custom_fields is not None:
            await self._apply_custom_fields(
                session, product=product, values=payload.custom_fields
            )
        await self._ensure_dictionary_entries(
            session,
            tenant_id=product.tenant_id,
            category=product.category,
            brand=product.brand,
        )
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("当前租户中已存在相同 SKU。") from exc
        await session.refresh(product)
        return await self.get_product(session, product.id)

    async def _hydrate_products(
        self, session: AsyncSession, products: list[Product]
    ) -> list[ProductResponse]:
        if not products:
            return []
        ids = [product.id for product in products]
        field_rows = (
            await session.execute(
                select(
                    ProductFieldValue.product_id,
                    FieldDefinition.code,
                    ProductFieldValue.value,
                )
                .join(
                    FieldDefinition,
                    and_(
                        FieldDefinition.tenant_id == ProductFieldValue.tenant_id,
                        FieldDefinition.id == ProductFieldValue.field_definition_id,
                    ),
                )
                .where(ProductFieldValue.product_id.in_(ids))
            )
        ).all()
        fields_by_product: dict[UUID, dict[str, object]] = defaultdict(dict)
        for product_id, code, value in field_rows:
            fields_by_product[product_id][code] = value

        image_rows = list(
            await session.scalars(
                select(ProductImage)
                .where(ProductImage.product_id.in_(ids))
                .order_by(
                    ProductImage.is_primary.desc(),
                    ProductImage.sort_order,
                    ProductImage.created_at,
                )
            )
        )
        images_by_product: dict[UUID, list[ProductImage]] = defaultdict(list)
        for image in image_rows:
            images_by_product[image.product_id].append(image)

        return [
            ProductResponse(
                id=product.id,
                tenant_id=product.tenant_id,
                sku=product.sku,
                product_name=product.product_name,
                description=product.description,
                category=product.category,
                brand=product.brand,
                status=product.status,
                custom_fields=fields_by_product[product.id],
                image_count=len(images_by_product[product.id]),
                primary_image_url=(
                    f"/api/v1/product-images/{images_by_product[product.id][0].id}/content"
                    if images_by_product[product.id]
                    else None
                ),
                created_at=product.created_at,
                updated_at=product.updated_at,
            )
            for product in products
        ]

    async def get_product(self, session: AsyncSession, product_id: UUID) -> ProductResponse:
        product = await self._get_product(session, product_id)
        return (await self._hydrate_products(session, [product]))[0]

    async def delete_product(self, session: AsyncSession, *, product_id: UUID) -> None:
        product = await self._get_product(session, product_id)
        generation_count = int(
            await session.scalar(
                select(func.count())
                .select_from(GenerationTaskProduct)
                .where(GenerationTaskProduct.product_id == product.id)
            )
            or 0
        )
        if generation_count:
            raise ConflictError(
                f"该产品已被 {generation_count} 个历史生成任务使用，不能永久删除。"
                "可以将产品状态改为“已归档”。"
            )

        # 导入记录保留自己的行/图片快照，只解除对当前产品实体的引用。
        await session.execute(
            update(ImportRow)
            .where(ImportRow.product_id == product.id)
            .values(product_id=None)
        )
        await session.execute(
            update(ImportImageCandidate)
            .where(ImportImageCandidate.matched_product_id == product.id)
            .values(matched_product_id=None)
        )
        await session.delete(product)
        await session.flush()

    async def list_products(
        self,
        session: AsyncSession,
        *,
        search: str | None,
        status: str | None,
        category: str | None,
        brand: str | None,
        page: int,
        page_size: int,
    ) -> ProductListResponse:
        filters = []
        if search:
            term = f"%{search.strip()}%"
            filters.append(or_(Product.sku.ilike(term), Product.product_name.ilike(term)))
        if status:
            filters.append(Product.status == status)
        if category:
            filters.append(Product.category == category)
        if brand:
            filters.append(Product.brand == brand)

        total = int(
            await session.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
        )
        import_order = (
            select(
                ImportRow.tenant_id.label("tenant_id"),
                ImportRow.product_id.label("product_id"),
                ImportRow.updated_at.label("imported_at"),
                ImportRow.source_sheet.label("source_sheet"),
                ImportRow.source_row.label("source_row"),
                func.row_number()
                .over(
                    partition_by=(ImportRow.tenant_id, ImportRow.product_id),
                    order_by=(
                        ImportRow.updated_at.desc(),
                        ImportRow.source_sheet.desc(),
                        ImportRow.source_row.desc(),
                    ),
                )
                .label("position"),
            )
            .where(ImportRow.status == "imported", ImportRow.product_id.is_not(None))
            .subquery()
        )
        products = list(
            await session.scalars(
                select(Product)
                .outerjoin(
                    import_order,
                    and_(
                        import_order.c.tenant_id == Product.tenant_id,
                        import_order.c.product_id == Product.id,
                        import_order.c.position == 1,
                    ),
                )
                .where(*filters)
                .order_by(
                    func.coalesce(import_order.c.imported_at, Product.created_at).desc(),
                    import_order.c.source_sheet.desc().nulls_last(),
                    import_order.c.source_row.desc().nulls_last(),
                    Product.created_at.desc(),
                    Product.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return ProductListResponse(
            items=await self._hydrate_products(session, products),
            total=total,
            page=page,
            page_size=page_size,
        )

    async def stats(self, session: AsyncSession) -> ProductStatsResponse:
        status_rows = (
            await session.execute(select(Product.status, func.count()).group_by(Product.status))
        ).all()
        counts = {status: count for status, count in status_rows}
        with_images = int(
            await session.scalar(
                select(func.count(func.distinct(ProductImage.product_id))).select_from(ProductImage)
            )
            or 0
        )
        field_count = int(
            await session.scalar(
                select(func.count())
                .select_from(FieldDefinition)
                .where(FieldDefinition.status == "active")
            )
            or 0
        )
        return ProductStatsResponse(
            total=sum(counts.values()),
            active=counts.get("active", 0),
            draft=counts.get("draft", 0),
            archived=counts.get("archived", 0),
            with_images=with_images,
            field_count=field_count,
        )

    async def list_images(
        self,
        session: AsyncSession,
        *,
        product_id: UUID | None = None,
        image_type: str | None = None,
    ) -> tuple[list[ProductImageResponse], int]:
        filters = []
        if product_id:
            filters.append(ProductImage.product_id == product_id)
        if image_type:
            filters.append(ProductImage.image_type == image_type)
        original_file = aliased(StoredFile, name="original_file")
        processed_file = aliased(StoredFile, name="processed_file")
        statement = (
            select(ProductImage, original_file, Product, processed_file)
            .join(
                original_file,
                and_(
                    original_file.tenant_id == ProductImage.tenant_id,
                    original_file.id == ProductImage.stored_file_id,
                ),
            )
            .outerjoin(
                processed_file,
                and_(
                    processed_file.tenant_id == ProductImage.tenant_id,
                    processed_file.id == ProductImage.processed_file_id,
                ),
            )
            .join(
                Product,
                and_(
                    Product.tenant_id == ProductImage.tenant_id,
                    Product.id == ProductImage.product_id,
                ),
            )
            .where(*filters)
            .order_by(ProductImage.created_at.desc())
        )
        rows = (await session.execute(statement)).all()
        return [self._image_response(*row) for row in rows], len(rows)

    async def upload_image(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        product_id: UUID,
        upload: UploadFile,
        image_type: ImageType,
        is_primary: bool,
    ) -> ProductImageResponse:
        product = await self._get_product(session, product_id)
        limit = settings.max_upload_size_mb * 1024 * 1024
        payload = await upload.read(limit + 1)
        if not payload:
            raise BadRequestError("图片文件为空。")
        if len(payload) > limit:
            raise BadRequestError(f"图片不能超过 {settings.max_upload_size_mb} MB。")
        try:
            with Image.open(BytesIO(payload)) as image:
                image.verify()
            with Image.open(BytesIO(payload)) as image:
                width, height = image.size
                image_format = image.format
        except (UnidentifiedImageError, OSError) as exc:
            raise BadRequestError("上传文件不是可识别的图片。") from exc
        mime_type = Image.MIME.get(image_format or "")
        if not mime_type or not mime_type.startswith("image/"):
            raise BadRequestError("上传图片格式不受支持。")
        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
        }.get(mime_type)
        if extension is None:
            raise BadRequestError("仅支持 JPG、PNG、WebP、GIF 和 BMP 图片。")

        digest = hashlib.sha256(payload).hexdigest()
        original_filename = upload.filename or f"image{extension}"
        stored_file = await session.scalar(select(StoredFile).where(StoredFile.sha256 == digest))
        if stored_file is None:
            safe_filename = _safe_filename(original_filename, digest, extension)
            storage_key = f"{tenant_id}/images/{digest[:2]}/{digest}{extension}"
            stored_file = StoredFile(
                tenant_id=tenant_id,
                storage_key=storage_key,
                original_filename=original_filename[:500],
                safe_filename=safe_filename,
                sha256=digest,
                mime_type=mime_type,
                size_bytes=len(payload),
                width=width,
                height=height,
            )
            session.add(stored_file)
            await session.flush()
            destination = (settings.storage_root / storage_key).resolve()
            storage_root = settings.storage_root.resolve()
            if storage_root not in destination.parents:
                raise BadRequestError("图片存储路径无效。")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
                temporary.write_bytes(payload)
                os.replace(temporary, destination)

        duplicate = await session.scalar(
            select(ProductImage.id).where(
                ProductImage.product_id == product.id,
                ProductImage.stored_file_id == stored_file.id,
                ProductImage.image_type == image_type.value,
            )
        )
        if duplicate is not None:
            raise ConflictError("该产品已经关联同一图片和图片类型。")

        processed_file, background_removed = (
            await self.image_processor.ensure_transparent_variant(
                session,
                tenant_id=tenant_id,
                original=stored_file,
            )
        )

        image_count = int(
            await session.scalar(
                select(func.count())
                .select_from(ProductImage)
                .where(ProductImage.product_id == product.id)
            )
            or 0
        )
        make_primary = is_primary or image_count == 0
        if make_primary:
            await session.execute(
                update(ProductImage)
                .where(ProductImage.product_id == product.id)
                .values(is_primary=False)
            )
        product_image = ProductImage(
            tenant_id=tenant_id,
            product_id=product.id,
            stored_file_id=stored_file.id,
            processed_file_id=processed_file.id,
            background_removed=background_removed,
            image_type=image_type.value,
            sort_order=image_count,
            is_primary=make_primary,
            match_method="manual",
            match_confidence=Decimal("1.000"),
            match_source="manual_upload",
        )
        session.add(product_image)
        await session.flush()
        return self._image_response(product_image, stored_file, product, processed_file)

    async def update_image(
        self,
        session: AsyncSession,
        *,
        image_id: UUID,
        image_type: ImageType | None,
        sort_order: int | None,
        is_primary: bool | None,
    ) -> ProductImageResponse:
        original_file = aliased(StoredFile, name="original_file")
        processed_file = aliased(StoredFile, name="processed_file")
        row = (
            await session.execute(
                select(ProductImage, original_file, Product, processed_file)
                .join(
                    original_file,
                    and_(
                        original_file.tenant_id == ProductImage.tenant_id,
                        original_file.id == ProductImage.stored_file_id,
                    ),
                )
                .outerjoin(
                    processed_file,
                    and_(
                        processed_file.tenant_id == ProductImage.tenant_id,
                        processed_file.id == ProductImage.processed_file_id,
                    ),
                )
                .join(
                    Product,
                    and_(
                        Product.tenant_id == ProductImage.tenant_id,
                        Product.id == ProductImage.product_id,
                    ),
                )
                .where(ProductImage.id == image_id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("产品图片不存在。")
        product_image, stored_file, product, processed = row
        if is_primary is True:
            await session.execute(
                update(ProductImage)
                .where(ProductImage.product_id == product_image.product_id)
                .values(is_primary=False)
            )
            product_image.is_primary = True
        elif is_primary is False and product_image.is_primary:
            raise BadRequestError("请先将另一张图片设为主图。")
        if image_type is not None:
            product_image.image_type = image_type.value
        if sort_order is not None:
            product_image.sort_order = sort_order
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("图片类型调整后产生了重复关联。") from exc
        return self._image_response(product_image, stored_file, product, processed)

    async def delete_image(self, session: AsyncSession, *, image_id: UUID) -> None:
        product_image = await session.get(ProductImage, image_id)
        if product_image is None:
            raise NotFoundError("产品图片不存在。")

        product_id = product_image.product_id
        await session.delete(product_image)
        await session.flush()

        remaining = list(
            await session.scalars(
                select(ProductImage)
                .where(ProductImage.product_id == product_id)
                .order_by(ProductImage.sort_order, ProductImage.created_at, ProductImage.id)
            )
        )
        if remaining and not any(image.is_primary for image in remaining):
            remaining[0].is_primary = True
        for index, image in enumerate(remaining):
            image.sort_order = index
        await session.flush()

    async def get_image_file(
        self, session: AsyncSession, image_id: UUID, *, processed: bool = False
    ) -> tuple[Path, StoredFile]:
        original_file = aliased(StoredFile, name="original_file")
        processed_file = aliased(StoredFile, name="processed_file")
        row = (
            await session.execute(
                select(ProductImage, original_file, processed_file)
                .join(
                    original_file,
                    and_(
                        original_file.tenant_id == ProductImage.tenant_id,
                        original_file.id == ProductImage.stored_file_id,
                    ),
                )
                .outerjoin(
                    processed_file,
                    and_(
                        processed_file.tenant_id == ProductImage.tenant_id,
                        processed_file.id == ProductImage.processed_file_id,
                    ),
                )
                .where(ProductImage.id == image_id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("产品图片不存在。")
        _, original, transparent = row
        stored_file = transparent if processed and transparent is not None else original
        path = (settings.storage_root / stored_file.storage_key).resolve()
        if settings.storage_root.resolve() not in path.parents or not path.is_file():
            raise NotFoundError("图片文件不存在。")
        return path, stored_file

    @staticmethod
    def _image_response(
        product_image: ProductImage,
        stored_file: StoredFile,
        product: Product,
        processed_file: StoredFile | None,
    ) -> ProductImageResponse:
        return ProductImageResponse(
            id=product_image.id,
            product_id=product.id,
            product_sku=product.sku,
            product_name=product.product_name,
            image_type=product_image.image_type,
            sort_order=product_image.sort_order,
            is_primary=product_image.is_primary,
            original_filename=stored_file.original_filename,
            safe_filename=stored_file.safe_filename,
            sha256=stored_file.sha256,
            mime_type=stored_file.mime_type,
            size_bytes=stored_file.size_bytes,
            width=stored_file.width,
            height=stored_file.height,
            source_sheet=product_image.source_sheet,
            source_row=product_image.source_row,
            source_column=product_image.source_column,
            match_method=product_image.match_method,
            match_confidence=float(product_image.match_confidence),
            match_source=product_image.match_source,
            content_url=f"/api/v1/product-images/{product_image.id}/content",
            processed_content_url=(
                f"/api/v1/product-images/{product_image.id}/processed-content"
                if processed_file is not None
                else None
            ),
            processed_sha256=processed_file.sha256 if processed_file is not None else None,
            processed_mime_type=(
                processed_file.mime_type if processed_file is not None else None
            ),
            background_removed=product_image.background_removed,
            created_at=product_image.created_at,
        )
