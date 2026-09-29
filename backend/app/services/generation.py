import hashlib
import logging
import os
import re
import shutil
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError, NotFoundError
from app.models import (
    Customer,
    CustomerSetting,
    CustomerTemplateBinding,
    FieldDefinition,
    GenerationTask,
    GenerationTaskProduct,
    OutputTemplate,
    OutputTemplateVersion,
    Product,
    ProductFieldValue,
    ProductImage,
    ProductSet,
    ProductSetItem,
    StoredFile,
)
from app.schemas.generation import (
    GenerationTaskCreateRequest,
    GenerationTaskDetailResponse,
    GenerationTaskResponse,
)
from app.schemas.templates import CUSTOMER_SOURCES
from app.services.renderers import PptxRenderer, RenderRequest, XlsxRenderer

settings = get_settings()
logger = logging.getLogger(__name__)

CORE_VALUE_COLUMNS = {
    "sku": "sku",
    "product_name": "product_name",
    "description": "description",
    "category": "category",
    "brand": "brand",
}


class GenerationService:
    def __init__(self) -> None:
        self.renderers = {"pptx": PptxRenderer(), "xlsx": XlsxRenderer()}

    @staticmethod
    def _storage_path(storage_key: str) -> Path:
        root = settings.storage_root.resolve()
        destination = (root / storage_key).resolve()
        if root not in destination.parents:
            raise BadRequestError("文件存储路径无效。")
        return destination

    async def _selected_products(
        self,
        session: AsyncSession,
        payload: GenerationTaskCreateRequest,
    ) -> tuple[list[Product], ProductSet | None]:
        product_set = None
        if payload.product_set_id is not None:
            product_set = await session.get(ProductSet, payload.product_set_id)
            if product_set is None or product_set.status != "active":
                raise BadRequestError("产品组合不存在或已归档。")
            rows = (
                await session.execute(
                    select(ProductSetItem, Product)
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
            products = [product for _, product in rows]
        else:
            products_by_id = {
                product.id: product
                for product in await session.scalars(
                    select(Product).where(Product.id.in_(payload.product_ids))
                )
            }
            products = [
                products_by_id[item]
                for item in payload.product_ids
                if item in products_by_id
            ]
            if len(products) != len(payload.product_ids):
                raise BadRequestError("选择中包含不存在的产品。")
        if not products:
            raise BadRequestError("产品组合中没有可生成的产品。")
        inactive = [product.sku for product in products if product.status != "active"]
        if inactive:
            raise BadRequestError("以下产品不是有效状态：" + ", ".join(inactive))
        return products, product_set

    async def _validate_mapping_fields(
        self, session: AsyncSession, mapping: dict
    ) -> dict[str, FieldDefinition]:
        sources = {
            source
            for binding in mapping.get("bindings", [])
            if binding.get("visible", True)
            for source in [
                binding["source"],
                *(item["source"] for item in binding.get("text_runs") or []),
            ]
            if source not in CUSTOMER_SOURCES
        }
        fields = list(
            await session.scalars(
                select(FieldDefinition).where(FieldDefinition.code.in_(sources))
            )
        ) if sources else []
        by_code = {field.code: field for field in fields}
        unknown = sources - set(by_code)
        if unknown:
            raise BadRequestError(
                "模板引用的字段不存在：" + ", ".join(sorted(unknown))
            )
        forbidden = [
            code
            for code, field in by_code.items()
            if field.scope == "internal" or field.status != "active"
        ]
        if forbidden:
            raise BadRequestError(
                "客户输出禁止使用内部或已停用字段：" + ", ".join(sorted(forbidden))
            )
        return by_code

    async def _product_snapshots(
        self,
        session: AsyncSession,
        products: list[Product],
        allowed_fields: dict[str, FieldDefinition],
    ) -> list[dict]:
        ids = [product.id for product in products]
        value_rows = (
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
                .where(
                    ProductFieldValue.product_id.in_(ids),
                    FieldDefinition.scope == "customer",
                    FieldDefinition.status == "active",
                )
            )
        ).all()
        values_by_product: dict[UUID, dict] = {product.id: {} for product in products}
        for product_id, code, value in value_rows:
            values_by_product[product_id][code] = value
        image_rows = (
            await session.execute(
                select(ProductImage, StoredFile)
                .join(
                    StoredFile,
                    and_(
                        StoredFile.tenant_id == ProductImage.tenant_id,
                        StoredFile.id == ProductImage.stored_file_id,
                    ),
                )
                .where(ProductImage.product_id.in_(ids))
                .order_by(
                    ProductImage.product_id,
                    ProductImage.is_primary.desc(),
                    ProductImage.sort_order,
                )
            )
        ).all()
        images_by_product: dict[UUID, list[dict]] = {product.id: [] for product in products}
        for image, stored_file in image_rows:
            images_by_product[image.product_id].append(
                {
                    "id": str(image.id),
                    "image_type": image.image_type,
                    "is_primary": image.is_primary,
                    "sort_order": image.sort_order,
                    "stored_file_id": str(stored_file.id),
                    "storage_key": stored_file.storage_key,
                    "sha256": stored_file.sha256,
                    "mime_type": stored_file.mime_type,
                    "width": stored_file.width,
                    "height": stored_file.height,
                    "original_filename": stored_file.original_filename,
                }
            )
        snapshots: list[dict] = []
        for product in products:
            fields: dict = {}
            for code, column in CORE_VALUE_COLUMNS.items():
                definition = allowed_fields.get(code)
                if definition is not None and definition.scope == "customer":
                    fields[code] = getattr(product, column)
            for code, value in values_by_product[product.id].items():
                if code in allowed_fields:
                    fields[code] = value
            snapshots.append(
                {
                    "product_id": str(product.id),
                    "sku": product.sku,
                    "product_name": product.product_name,
                    "fields": fields,
                    "images": images_by_product[product.id],
                    "captured_at": datetime.now(UTC).isoformat(),
                }
            )
        return snapshots

    async def _customer_snapshot(
        self, session: AsyncSession, customer: Customer
    ) -> dict:
        setting = await session.scalar(
            select(CustomerSetting).where(CustomerSetting.customer_id == customer.id)
        )
        logo = None
        if customer.logo_file_id is not None:
            stored_file = await session.get(StoredFile, customer.logo_file_id)
            if stored_file is not None:
                logo = {
                    "stored_file_id": str(stored_file.id),
                    "storage_key": stored_file.storage_key,
                    "sha256": stored_file.sha256,
                    "mime_type": stored_file.mime_type,
                    "width": stored_file.width,
                    "height": stored_file.height,
                }
        return {
            "customer_id": str(customer.id),
            "name": customer.name,
            "code": customer.code,
            "status": customer.status,
            "locale": setting.locale if setting else "en-US",
            "currency": setting.currency if setting else "USD",
            "timezone": setting.timezone if setting else "Asia/Shanghai",
            "settings": setting.settings if setting else {},
            "logo": logo,
            "captured_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _product_set_snapshot(product_set: ProductSet | None, products: list[Product]):
        if product_set is None:
            return None
        return {
            "product_set_id": str(product_set.id),
            "name": product_set.name,
            "description": product_set.description,
            "customer_id": str(product_set.customer_id) if product_set.customer_id else None,
            "product_ids": [str(product.id) for product in products],
            "items": [
                {"product_id": str(product.id), "sort_order": index}
                for index, product in enumerate(products)
            ],
            "captured_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _validate_customer_output_fields(
        customer_snapshot: dict, allowed_fields: dict[str, FieldDefinition]
    ) -> None:
        configured = customer_snapshot.get("settings", {}).get("allowed_output_fields")
        if configured is None:
            return
        if not isinstance(configured, list) or not all(
            isinstance(item, str) for item in configured
        ):
            raise BadRequestError("客户允许输出字段配置无效。")
        configured_fields = {item.strip().lower() for item in configured}
        forbidden = set(allowed_fields) - configured_fields
        if forbidden:
            raise BadRequestError(
                "模板包含客户未授权输出的字段：" + ", ".join(sorted(forbidden))
            )

    async def create_task(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        payload: GenerationTaskCreateRequest,
    ) -> GenerationTaskDetailResponse:
        customer = await session.get(Customer, payload.customer_id)
        if customer is None or customer.status != "active":
            raise BadRequestError("客户不存在或不是有效状态。")
        version = await session.get(OutputTemplateVersion, payload.output_template_version_id)
        if version is None:
            raise BadRequestError("输出模板版本不存在。")
        template = await session.get(OutputTemplate, version.output_template_id)
        if template is None or template.status != "active":
            raise BadRequestError("输出模板不存在或已归档。")
        if version.status != "ready":
            raise BadRequestError("输出模板尚未完成字段映射验证。")
        template_binding = await session.scalar(
            select(CustomerTemplateBinding).where(
                CustomerTemplateBinding.customer_id == customer.id,
                CustomerTemplateBinding.output_template_id == template.id,
            )
        )
        if template_binding is None:
            raise BadRequestError("当前输出模板尚未绑定到该客户。")
        mapping = version.mapping_config
        if mapping.get("template_sha256") != version.template_sha256:
            raise BadRequestError("模板文件发生变化，请重新验证字段映射。")
        allowed_fields = await self._validate_mapping_fields(session, mapping)
        products, product_set = await self._selected_products(session, payload)
        if (
            product_set is not None
            and product_set.customer_id is not None
            and product_set.customer_id != customer.id
        ):
            raise BadRequestError("该产品组合已绑定其他客户，不能用于当前生成任务。")
        product_bindings = [
            binding
            for binding in mapping.get("bindings", [])
            if binding.get("visible", True)
            and binding["source"]
            not in {"customer.name", "customer.code", "customer.logo"}
        ]
        product_slots = [
            int(slot)
            for binding in product_bindings
            for slot in [
                binding.get("product_slot") or 1,
                *(item.get("product_slot") or 1 for item in binding.get("text_runs") or []),
            ]
        ]
        capacity = max(product_slots, default=0)
        if capacity == 0:
            raise BadRequestError("模板没有配置产品字段或图片槽位。")
        if len(products) > capacity:
            raise BadRequestError(
                f"模板映射仅配置了 {capacity} 个产品槽位，当前选择了 {len(products)} 个产品。"
            )

        product_snapshot = await self._product_snapshots(session, products, allowed_fields)
        customer_snapshot = await self._customer_snapshot(session, customer)
        self._validate_customer_output_fields(customer_snapshot, allowed_fields)
        product_set_snapshot = self._product_set_snapshot(product_set, products)
        stored_template = await session.get(StoredFile, version.stored_file_id)
        if stored_template is None:
            raise BadRequestError("输出模板文件记录不存在。")
        template_snapshot = {
            "output_template_id": str(template.id),
            "template_name": template.name,
            "output_template_version_id": str(version.id),
            "version_number": version.version_number,
            "template_sha256": version.template_sha256,
            "mapping": mapping,
            "stored_file_id": str(stored_template.id),
            "storage_key": stored_template.storage_key,
            "original_filename": stored_template.original_filename,
            "output_type": template.output_type,
            "captured_at": datetime.now(UTC).isoformat(),
        }
        task = GenerationTask(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            customer_id=customer.id,
            product_set_id=product_set.id if product_set else None,
            output_template_version_id=version.id,
            name=payload.name,
            status="queued",
            output_type=template.output_type,
            product_snapshot=product_snapshot,
            customer_snapshot=customer_snapshot,
            product_set_snapshot=product_set_snapshot,
            template_snapshot=template_snapshot,
            output_parameters=payload.output_parameters,
        )
        session.add(task)
        await session.flush()
        for index, (product, snapshot) in enumerate(zip(products, product_snapshot, strict=True)):
            session.add(
                GenerationTaskProduct(
                    tenant_id=tenant_id,
                    generation_task_id=task.id,
                    product_id=product.id,
                    sort_order=index,
                    product_snapshot=snapshot,
                )
            )
        await session.flush()
        await self._render_task(session, task, stored_template)
        return await self.get_task(session, task.id)

    async def _render_task(
        self,
        session: AsyncSession,
        task: GenerationTask,
        template_file: StoredFile,
    ) -> None:
        task.status = "processing"
        task.started_at = datetime.now(UTC)
        await session.flush()
        temp_dir = self._storage_path(f"{task.tenant_id}/tmp/{task.id}")
        temp_path = temp_dir / f"{uuid4().hex}.{task.output_type}"
        try:
            template_path = self._storage_path(template_file.storage_key)
            if not template_path.is_file():
                raise BadRequestError("输出模板文件不存在。")
            current_sha = hashlib.sha256(template_path.read_bytes()).hexdigest()
            expected_sha = task.template_snapshot["template_sha256"]
            if current_sha != expected_sha:
                raise BadRequestError("模板文件已经发生变化，请重新验证模板后再生成。")
            render_products = deepcopy(task.product_snapshot)
            for product in render_products:
                for image in product.get("images", []):
                    image["_path"] = str(self._storage_path(image["storage_key"]))
            render_customer = deepcopy(task.customer_snapshot)
            if render_customer.get("logo"):
                render_customer["logo"]["_path"] = str(
                    self._storage_path(render_customer["logo"]["storage_key"])
                )
            renderer = self.renderers[task.output_type]
            renderer.render(
                RenderRequest(
                    template_path=template_path,
                    destination=temp_path,
                    mapping=task.template_snapshot["mapping"],
                    products=render_products,
                    customer=render_customer,
                    parameters=task.output_parameters,
                )
            )
            if not temp_path.is_file() or temp_path.stat().st_size == 0:
                raise BadRequestError("Renderer 未产生有效输出文件。")
            digest = hashlib.sha256(temp_path.read_bytes()).hexdigest()
            safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", task.name).strip("-._") or "output"
            filename = f"{safe_stem[:120]}.{task.output_type}"
            existing = await session.scalar(select(StoredFile).where(StoredFile.sha256 == digest))
            if existing is None:
                now = datetime.now(UTC)
                storage_key = (
                    f"{task.tenant_id}/exports/{now:%Y/%m}/{task.id}/{filename}"
                )
                destination = self._storage_path(storage_key)
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temp_path, destination)
                output_file = StoredFile(
                    tenant_id=task.tenant_id,
                    storage_key=storage_key,
                    original_filename=filename,
                    safe_filename=filename,
                    sha256=digest,
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                        if task.output_type == "pptx"
                        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    ),
                    size_bytes=destination.stat().st_size,
                )
                session.add(output_file)
                await session.flush()
            else:
                output_file = existing
                temp_path.unlink(missing_ok=True)
            task.output_file_id = output_file.id
            task.status = "completed"
            task.completed_at = datetime.now(UTC)
            task.error_message = None
        except Exception as exc:
            logger.exception("Generation task failed", extra={"generation_task_id": str(task.id)})
            task.status = "failed"
            task.completed_at = datetime.now(UTC)
            task.output_file_id = None
            task.error_message = (
                exc.message
                if isinstance(exc, BadRequestError)
                else "文件生成失败，请检查模板映射和产品资料。"
            )
            temp_path.unlink(missing_ok=True)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        await session.flush()

    async def list_tasks(self, session: AsyncSession) -> list[GenerationTaskResponse]:
        tasks = list(
            await session.scalars(
                select(GenerationTask).order_by(GenerationTask.created_at.desc()).limit(200)
            )
        )
        return [await self._task_response(session, task) for task in tasks]

    async def get_task(
        self, session: AsyncSession, task_id: UUID
    ) -> GenerationTaskDetailResponse:
        task = await session.get(GenerationTask, task_id)
        if task is None:
            raise NotFoundError("生成任务不存在。")
        summary = await self._task_response(session, task)
        return GenerationTaskDetailResponse(
            **summary.model_dump(),
            product_snapshot=task.product_snapshot,
            customer_snapshot=task.customer_snapshot,
            product_set_snapshot=task.product_set_snapshot,
            template_snapshot=task.template_snapshot,
            output_parameters=task.output_parameters,
        )

    async def _task_response(
        self, session: AsyncSession, task: GenerationTask
    ) -> GenerationTaskResponse:
        output_file = (
            await session.get(StoredFile, task.output_file_id) if task.output_file_id else None
        )
        customer_snapshot = task.customer_snapshot or {}
        product_set_snapshot = task.product_set_snapshot or {}
        template_snapshot = task.template_snapshot or {}
        return GenerationTaskResponse(
            id=task.id,
            tenant_id=task.tenant_id,
            name=task.name,
            status=task.status,
            output_type=task.output_type,
            customer_id=task.customer_id,
            customer_name=customer_snapshot.get("name", ""),
            product_set_id=task.product_set_id,
            product_set_name=product_set_snapshot.get("name"),
            output_template_version_id=task.output_template_version_id,
            template_name=template_snapshot.get("template_name", ""),
            template_version_number=int(template_snapshot.get("version_number", 0)),
            product_count=len(task.product_snapshot or []),
            output_filename=output_file.original_filename if output_file else None,
            download_url=(
                f"/api/v1/generation-tasks/{task.id}/download"
                if task.status == "completed" and output_file
                else None
            ),
            error_message=task.error_message,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )

    async def output_path(
        self, session: AsyncSession, task_id: UUID
    ) -> tuple[Path, StoredFile]:
        task = await session.get(GenerationTask, task_id)
        if task is None:
            raise NotFoundError("生成任务不存在。")
        if task.status != "completed" or task.output_file_id is None:
            raise BadRequestError("该任务尚无可下载的完整输出文件。")
        stored_file = await session.get(StoredFile, task.output_file_id)
        if stored_file is None:
            raise NotFoundError("生成文件记录不存在。")
        path = self._storage_path(stored_file.storage_key)
        if not path.is_file():
            raise NotFoundError("生成文件不存在。")
        return path, stored_file
