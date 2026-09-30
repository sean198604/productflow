import asyncio
import hashlib
import mimetypes
import os
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.domain.product_fields import CORE_FIELD_CODES
from app.models import (
    FieldDefinition,
    ImportImageCandidate,
    ImportJob,
    ImportRow,
    ImportTemplate,
    Product,
    ProductImage,
    StoredFile,
)
from app.schemas.catalog import ProductCreateRequest, ProductStatus, ProductUpdateRequest
from app.schemas.imports import (
    DuplicateStrategy,
    ImportConfirmRequest,
    ImportImageCandidateResponse,
    ImportImageMatchRequest,
    ImportJobResponse,
    ImportMappingConfig,
    ImportPreviewRequest,
    ImportRowResponse,
    ImportTemplateCreateRequest,
    ImportTemplateResponse,
    ImportTemplateUpdateRequest,
)
from app.services.document_parser import ExcelImporter, ExtractedImage
from app.services.product_catalog import ProductCatalogService

settings = get_settings()
AUTO_MATCH_THRESHOLD = Decimal("0.850")


def _safe_filename(original: str, digest: str, extension: str) -> str:
    stem = Path(original).stem
    normalized = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized).strip("-._") or "file"
    return f"{digest[:12]}-{clean[:120]}{extension}"


def _normalize_sku(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


class ImportTemplateService:
    async def list(self, session: AsyncSession) -> list[ImportTemplate]:
        return list(
            await session.scalars(
                select(ImportTemplate).order_by(
                    ImportTemplate.status, ImportTemplate.updated_at.desc()
                )
            )
        )

    async def create(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: ImportTemplateCreateRequest,
    ) -> ImportTemplate:
        duplicate = await session.scalar(
            select(ImportTemplate.id).where(
                func.lower(ImportTemplate.name) == payload.name.lower()
            )
        )
        if duplicate is not None:
            raise ConflictError("当前租户中已存在同名导入模板。")
        await self._validate_targets(session, payload.mapping_config)
        template = ImportTemplate(
            tenant_id=tenant_id,
            name=payload.name,
            description=payload.description,
            source_type=payload.source_type,
            mapping_config=payload.mapping_config.model_dump(mode="json"),
        )
        session.add(template)
        await session.flush()
        return template

    async def update(
        self,
        session: AsyncSession,
        *,
        template_id: UUID,
        payload: ImportTemplateUpdateRequest,
    ) -> ImportTemplate:
        template = await session.get(ImportTemplate, template_id)
        if template is None:
            raise NotFoundError("导入模板不存在。")
        values = payload.model_dump(exclude_unset=True)
        if "name" in values:
            duplicate = await session.scalar(
                select(ImportTemplate.id).where(
                    func.lower(ImportTemplate.name) == values["name"].lower(),
                    ImportTemplate.id != template.id,
                )
            )
            if duplicate is not None:
                raise ConflictError("当前租户中已存在同名导入模板。")
        if payload.mapping_config is not None:
            await self._validate_targets(session, payload.mapping_config)
            values["mapping_config"] = payload.mapping_config.model_dump(mode="json")
        if payload.status is not None:
            values["status"] = payload.status.value
        for key, value in values.items():
            setattr(template, key, value)
        await session.flush()
        await session.refresh(template)
        return template

    async def delete(self, session: AsyncSession, *, template_id: UUID) -> None:
        template = await session.get(ImportTemplate, template_id)
        if template is None:
            raise NotFoundError("导入模板不存在。")
        # 导入任务已保存 mapping_snapshot，删除复用模板不会破坏历史导入记录。
        await session.execute(
            update(ImportJob)
            .where(ImportJob.import_template_id == template.id)
            .values(import_template_id=None)
        )
        await session.delete(template)
        await session.flush()

    @staticmethod
    async def _validate_targets(
        session: AsyncSession, mapping: ImportMappingConfig
    ) -> None:
        targets = {field.target for field in mapping.fields}
        known = set(
            await session.scalars(
                select(FieldDefinition.code).where(
                    FieldDefinition.code.in_(targets), FieldDefinition.status == "active"
                )
            )
        )
        unknown = targets - known
        if unknown:
            raise BadRequestError(
                f"映射引用了未知或已停用字段：{', '.join(sorted(unknown))}"
            )


class ImportJobService:
    def __init__(self) -> None:
        self.importer = ExcelImporter()
        self.products = ProductCatalogService()
        self.templates = ImportTemplateService()

    @staticmethod
    def _storage_path(storage_key: str) -> Path:
        root = settings.storage_root.resolve()
        destination = (root / storage_key).resolve()
        if root not in destination.parents:
            raise BadRequestError("文件存储路径无效。")
        return destination

    @staticmethod
    def _extension(original_filename: str, mime_type: str) -> str:
        extension = Path(original_filename).suffix.lower()
        if extension and re.fullmatch(r"\.[a-z0-9]{1,10}", extension):
            return extension
        return mimetypes.guess_extension(mime_type) or ".bin"

    async def _store_bytes(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: bytes,
        original_filename: str,
        mime_type: str,
        category: str,
        width: int | None = None,
        height: int | None = None,
    ) -> StoredFile:
        digest = hashlib.sha256(payload).hexdigest()
        existing = await session.scalar(select(StoredFile).where(StoredFile.sha256 == digest))
        if existing is not None:
            if width is not None and height is not None:
                existing.width = width
                existing.height = height
            existing_path = self._storage_path(existing.storage_key)
            if not existing_path.exists():
                existing_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = existing_path.with_name(
                    f".{existing_path.name}.{uuid4().hex}.tmp"
                )
                temporary.write_bytes(payload)
                os.replace(temporary, existing_path)
            return existing
        extension = self._extension(original_filename, mime_type)
        storage_key = f"{tenant_id}/{category}/{digest[:2]}/{digest}{extension}"
        destination = self._storage_path(storage_key)
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, destination)
        stored_file = StoredFile(
            tenant_id=tenant_id,
            storage_key=storage_key,
            original_filename=original_filename[:500],
            safe_filename=_safe_filename(original_filename, digest, extension),
            sha256=digest,
            mime_type=mime_type,
            size_bytes=len(payload),
            width=width,
            height=height,
        )
        session.add(stored_file)
        await session.flush()
        return stored_file

    async def analyze_upload(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        upload: UploadFile,
    ) -> ImportJobResponse:
        filename = upload.filename or "workbook.xlsx"
        if Path(filename).suffix.lower() != ".xlsx":
            raise BadRequestError("第一版 Excel Importer 仅支持普通 XLSX 文件。")
        limit = settings.max_upload_size_mb * 1024 * 1024
        payload = await upload.read(limit + 1)
        if not payload:
            raise BadRequestError("上传文件为空。")
        if len(payload) > limit:
            raise BadRequestError(f"Excel 文件不能超过 {settings.max_upload_size_mb} MB。")
        digest = hashlib.sha256(payload).hexdigest()
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = ".xlsx"
        storage_key = f"{tenant_id}/imports/source/{digest[:2]}/{digest}{extension}"
        path = self._storage_path(storage_key)
        created_physical_file = not path.exists()
        if created_physical_file:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, path)
        try:
            analysis, extracted_images = await asyncio.to_thread(
                self.importer.analyze,
                path,
                original_filename=filename,
                sha256=digest,
            )
        except Exception:
            if created_physical_file and path.is_file():
                path.unlink()
            raise

        source_file = await session.scalar(
            select(StoredFile).where(StoredFile.sha256 == digest)
        )
        if source_file is None:
            source_file = StoredFile(
                tenant_id=tenant_id,
                storage_key=storage_key,
                original_filename=filename[:500],
                safe_filename=_safe_filename(filename, digest, extension),
                sha256=digest,
                mime_type=mime_type,
                size_bytes=len(payload),
            )
            session.add(source_file)
            await session.flush()

        job = ImportJob(
            tenant_id=tenant_id,
            source_file_id=source_file.id,
            created_by_user_id=user_id,
            status="analyzed",
            analysis=analysis,
        )
        session.add(job)
        await session.flush()
        for image in extracted_images:
            stored_image = await self._store_extracted_image(
                session, tenant_id=tenant_id, image=image
            )
            session.add(
                ImportImageCandidate(
                    tenant_id=tenant_id,
                    import_job_id=job.id,
                    stored_file_id=stored_image.id,
                    original_filename=image.original_filename[:500],
                    safe_filename=stored_image.safe_filename,
                    source_sheet=image.source_sheet,
                    source_row=image.source_row,
                    source_column=image.source_column,
                    image_type="other",
                    match_method="unmatched",
                    match_confidence=Decimal("0.000"),
                    match_source="analysis_pending_mapping",
                    status="unmatched",
                )
            )
        await session.flush()
        return await self.get_job(session, job.id)

    async def _store_extracted_image(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        image: ExtractedImage,
    ) -> StoredFile:
        return await self._store_bytes(
            session,
            tenant_id=tenant_id,
            payload=image.payload,
            original_filename=image.original_filename,
            mime_type=image.mime_type,
            category="imports/images",
            width=image.width,
            height=image.height,
        )

    async def _get_job(self, session: AsyncSession, job_id: UUID) -> ImportJob:
        job = await session.get(ImportJob, job_id)
        if job is None:
            raise NotFoundError("导入任务不存在。")
        return job

    async def _source_path(self, session: AsyncSession, job: ImportJob) -> tuple[Path, StoredFile]:
        source_file = await session.get(StoredFile, job.source_file_id)
        if source_file is None:
            raise NotFoundError("导入源文件不存在。")
        path = self._storage_path(source_file.storage_key)
        if not path.is_file():
            raise NotFoundError("导入源文件不存在。")
        return path, source_file

    async def preview(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        request: ImportPreviewRequest,
    ) -> ImportJobResponse:
        job = await self._get_job(session, job_id)
        if job.status not in {"analyzed", "preview_ready", "failed"}:
            raise BadRequestError("当前导入任务状态不能重新生成预览。")
        if request.import_template_id is not None:
            template = await session.get(ImportTemplate, request.import_template_id)
            if template is None or template.status != "active":
                raise NotFoundError("导入模板不存在或已停用。")
            mapping = ImportMappingConfig.model_validate(template.mapping_config)
            job.import_template_id = template.id
        else:
            assert request.mapping_config is not None
            mapping = request.mapping_config
            job.import_template_id = None
        await self.templates._validate_targets(session, mapping)
        path, _ = await self._source_path(session, job)
        preview_rows = await asyncio.to_thread(self.importer.preview, path, mapping)

        await session.execute(delete(ImportRow).where(ImportRow.import_job_id == job.id))
        skus = [
            str(row["mapped_data"].get("sku", "")).strip()
            for row in preview_rows
            if not row["errors"] and row["mapped_data"].get("sku")
        ]
        sku_counts = Counter(sku.lower() for sku in skus)
        duplicate_skus = {sku for sku, count in sku_counts.items() if count > 1}
        existing_products = list(
            await session.scalars(
                select(Product).where(func.lower(Product.sku).in_({sku.lower() for sku in skus}))
            )
        )
        existing_by_sku = {product.sku.lower(): product for product in existing_products}
        valid_rows = 0
        conflict_rows = 0
        for item in preview_rows:
            errors = list(item["errors"])
            sku = str(item["mapped_data"].get("sku", "")).strip()
            product = existing_by_sku.get(sku.lower()) if sku else None
            if sku.lower() in duplicate_skus:
                errors.append("sku: 文件内存在重复 SKU")
            if errors:
                status = "invalid"
                action = "conflict"
                conflict_rows += 1
            elif product is not None:
                status = "conflict"
                action = "conflict"
                valid_rows += 1
                conflict_rows += 1
            else:
                status = "valid"
                action = "create"
                valid_rows += 1
            session.add(
                ImportRow(
                    tenant_id=job.tenant_id,
                    import_job_id=job.id,
                    product_id=product.id if product else None,
                    source_sheet=item["source_sheet"],
                    source_row=item["source_row"],
                    source_data=item["source_data"],
                    mapped_data=item["mapped_data"],
                    status=status,
                    action=action,
                    errors=sorted(set(errors)),
                )
            )

        await session.flush()
        await self._match_images(
            session,
            job=job,
            rows=preview_rows,
            mapping=mapping,
            existing_by_sku=existing_by_sku,
        )
        job.mapping_snapshot = mapping.model_dump(mode="json")
        job.status = "preview_ready"
        job.total_rows = len(preview_rows)
        job.valid_rows = valid_rows
        job.conflict_rows = conflict_rows
        job.error_message = None
        await session.flush()
        await session.refresh(job)
        return await self.get_job(session, job.id)

    async def _match_images(
        self,
        session: AsyncSession,
        *,
        job: ImportJob,
        rows: list[dict],
        mapping: ImportMappingConfig,
        existing_by_sku: dict[str, Product],
    ) -> None:
        row_skus = {
            (row["source_sheet"], row["source_row"]): str(row["mapped_data"]["sku"]).strip()
            for row in rows
            if not row["errors"] and row["mapped_data"].get("sku")
        }
        all_skus = sorted(set(row_skus.values()), key=len, reverse=True)
        headers_by_sheet: dict[str, dict[int, str]] = {}
        for sheet in job.analysis.get("sheets", []):
            headers_by_sheet[sheet["name"]] = {
                int(header["column_index"]): str(header.get("value") or "")
                for header in sheet.get("headers", [])
            }
        candidates = list(
            await session.scalars(
                select(ImportImageCandidate).where(
                    ImportImageCandidate.import_job_id == job.id
                )
            )
        )
        for candidate in candidates:
            filename_key = _normalize_sku(Path(candidate.original_filename).stem)
            filename_matches = [
                sku
                for sku in all_skus
                if len(_normalize_sku(sku)) >= 3
                and _normalize_sku(sku) in filename_key
            ]
            sku: str | None = None
            method = "unmatched"
            confidence = Decimal("0.000")
            source = "no_reliable_match"
            if len(filename_matches) == 1:
                sku = filename_matches[0]
                method = "filename_sku"
                confidence = Decimal("1.000")
                source = f"filename:{candidate.original_filename}"
            elif (candidate.source_sheet, candidate.source_row) in row_skus:
                sku = row_skus[(candidate.source_sheet, candidate.source_row)]
                method = "anchor"
                confidence = Decimal("0.990")
                source = (
                    f"anchor:{candidate.source_sheet}!"
                    f"{candidate.source_column},{candidate.source_row}"
                )
            else:
                nearby = [
                    (abs(row_number - candidate.source_row), value, row_number)
                    for (sheet, row_number), value in row_skus.items()
                    if sheet == candidate.source_sheet
                    and 0 < abs(row_number - candidate.source_row) <= 2
                ]
                nearby.sort()
                if nearby and (len(nearby) == 1 or nearby[0][0] < nearby[1][0]):
                    _, sku, matched_row = nearby[0]
                    method = "nearby_sku"
                    confidence = Decimal("0.900")
                    source = f"nearby_row:{candidate.source_sheet}!{matched_row}"
                else:
                    context = [
                        (abs(row_number - candidate.source_row), value, row_number)
                        for (sheet, row_number), value in row_skus.items()
                        if sheet == candidate.source_sheet
                        and 0 < abs(row_number - candidate.source_row) <= 5
                    ]
                    context.sort()
                    if context and (len(context) == 1 or context[0][0] < context[1][0]):
                        _, context_sku, matched_row = context[0]
                        method = "context"
                        confidence = Decimal("0.700")
                        source = (
                            f"low_confidence_context:{context_sku}@"
                            f"{candidate.source_sheet}!{matched_row}"
                        )
            header = headers_by_sheet.get(candidate.source_sheet, {}).get(
                candidate.source_column, ""
            ).lower()
            candidate.image_type = "packaging" if "package" in header else "main"
            if sku is not None and confidence >= AUTO_MATCH_THRESHOLD:
                candidate.matched_sku = sku
                product = existing_by_sku.get(sku.lower())
                candidate.matched_product_id = product.id if product else None
                candidate.status = "matched"
            else:
                candidate.matched_sku = None
                candidate.matched_product_id = None
                candidate.status = "unmatched"
            candidate.match_method = method
            candidate.match_confidence = confidence
            candidate.match_source = source

    async def confirm(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        request: ImportConfirmRequest,
    ) -> ImportJobResponse:
        job = await self._get_job(session, job_id)
        if job.status != "preview_ready" or job.mapping_snapshot is None:
            raise BadRequestError("请先完成字段映射并生成导入预览。")
        mapping = ImportMappingConfig.model_validate(job.mapping_snapshot)
        job.status = "importing"
        job.duplicate_strategy = request.duplicate_strategy.value
        await session.flush()

        rows = list(
            await session.scalars(
                select(ImportRow)
                .where(ImportRow.import_job_id == job.id)
                .order_by(ImportRow.source_sheet, ImportRow.source_row)
            )
        )
        mapped_targets = {field.target for field in mapping.fields}
        imported = 0
        skipped = 0
        conflicts = 0
        products_by_sku: dict[str, Product] = {}
        for row in rows:
            if row.errors:
                row.status = "failed"
                row.action = "conflict"
                conflicts += 1
                continue
            data = dict(row.mapped_data)
            sku = str(data["sku"]).strip()
            existing = await session.scalar(
                select(Product).where(func.lower(Product.sku) == sku.lower())
            )
            try:
                if existing is None:
                    response = await self.products.create_product(
                        session,
                        tenant_id=job.tenant_id,
                        payload=self._create_payload(data),
                    )
                    row.product_id = response.id
                    row.action = "create"
                elif request.duplicate_strategy == DuplicateStrategy.SKIP:
                    row.product_id = existing.id
                    row.status = "skipped"
                    row.action = "skip"
                    products_by_sku[sku.lower()] = existing
                    skipped += 1
                    continue
                else:
                    response = await self.products.update_product(
                        session,
                        product_id=existing.id,
                        payload=self._update_payload(
                            data,
                            mapped_targets=mapped_targets,
                            overwrite=request.duplicate_strategy == DuplicateStrategy.OVERWRITE,
                        ),
                    )
                    row.product_id = response.id
                    row.action = "update"
                row.status = "imported"
                imported += 1
                product = await session.get(Product, row.product_id)
                if product is not None:
                    products_by_sku[sku.lower()] = product
            except BadRequestError as exc:
                row.status = "failed"
                row.action = "conflict"
                row.errors = [exc.message]
                conflicts += 1

        await session.flush()
        await self._import_images(session, job=job, products_by_sku=products_by_sku)
        job.status = "completed"
        job.imported_rows = imported
        job.skipped_rows = skipped
        job.conflict_rows = conflicts
        job.completed_at = datetime.now(UTC)
        await session.flush()
        await session.refresh(job)
        return await self.get_job(session, job.id)

    @staticmethod
    def _create_payload(data: dict) -> ProductCreateRequest:
        custom = {key: value for key, value in data.items() if key not in CORE_FIELD_CODES}
        return ProductCreateRequest(
            sku=str(data["sku"]),
            product_name=str(data["product_name"]),
            description=data.get("description"),
            category=data.get("category"),
            brand=data.get("brand"),
            status=ProductStatus.ACTIVE,
            custom_fields=custom,
        )

    @staticmethod
    def _update_payload(
        data: dict, *, mapped_targets: set[str], overwrite: bool
    ) -> ProductUpdateRequest:
        values: dict[str, object] = {}
        for key in CORE_FIELD_CODES:
            if key in data:
                values[key] = data[key]
            elif overwrite and key in mapped_targets and key not in {"sku", "product_name"}:
                values[key] = None
        custom_targets = mapped_targets - CORE_FIELD_CODES
        values["custom_fields"] = {
            key: data.get(key)
            for key in custom_targets
            if overwrite or data.get(key) not in (None, "")
        }
        return ProductUpdateRequest.model_validate(values)

    async def _import_images(
        self,
        session: AsyncSession,
        *,
        job: ImportJob,
        products_by_sku: dict[str, Product],
    ) -> None:
        candidates = list(
            await session.scalars(
                select(ImportImageCandidate).where(
                    ImportImageCandidate.import_job_id == job.id
                )
            )
        )
        for candidate in candidates:
            if (
                candidate.status != "matched"
                or candidate.match_confidence < AUTO_MATCH_THRESHOLD
                or not candidate.matched_sku
            ):
                continue
            product = products_by_sku.get(candidate.matched_sku.lower())
            if product is None:
                product = await session.scalar(
                    select(Product).where(
                        func.lower(Product.sku) == candidate.matched_sku.lower()
                    )
                )
            if product is None:
                candidate.status = "unmatched"
                candidate.matched_product_id = None
                continue
            candidate.matched_product_id = product.id
            duplicate = await session.scalar(
                select(ProductImage.id).where(
                    ProductImage.product_id == product.id,
                    ProductImage.stored_file_id == candidate.stored_file_id,
                    ProductImage.image_type == candidate.image_type,
                )
            )
            if duplicate is not None:
                candidate.status = "skipped"
                continue
            original_file = await session.get(StoredFile, candidate.stored_file_id)
            if original_file is None:
                candidate.status = "unmatched"
                candidate.matched_product_id = None
                continue
            processed_file, background_removed = (
                await self.products.image_processor.ensure_transparent_variant(
                    session,
                    tenant_id=job.tenant_id,
                    original=original_file,
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
            make_primary = candidate.is_primary or image_count == 0
            if make_primary:
                await session.execute(
                    update(ProductImage)
                    .where(ProductImage.product_id == product.id)
                    .values(is_primary=False)
                )
            session.add(
                ProductImage(
                    tenant_id=job.tenant_id,
                    product_id=product.id,
                    stored_file_id=candidate.stored_file_id,
                    processed_file_id=processed_file.id,
                    background_removed=background_removed,
                    image_type=candidate.image_type,
                    sort_order=image_count,
                    is_primary=make_primary,
                    source_sheet=candidate.source_sheet,
                    source_row=candidate.source_row,
                    source_column=candidate.source_column,
                    match_method=candidate.match_method,
                    match_confidence=candidate.match_confidence,
                    match_source=candidate.match_source,
                )
            )
            candidate.status = "imported"

    async def manual_match_image(
        self,
        session: AsyncSession,
        *,
        candidate_id: UUID,
        request: ImportImageMatchRequest,
    ) -> ImportImageCandidateResponse:
        candidate = await session.get(ImportImageCandidate, candidate_id)
        if candidate is None:
            raise NotFoundError("导入图片候选不存在。")
        job = await self._get_job(session, candidate.import_job_id)
        if job.status != "preview_ready":
            raise BadRequestError("仅预览待确认的导入任务可以调整图片匹配。")
        if request.matched_product_id is None and request.matched_sku is None:
            candidate.matched_product_id = None
            candidate.matched_sku = None
            candidate.match_method = "unmatched"
            candidate.match_confidence = Decimal("0.000")
            candidate.match_source = "manual_unmatch"
            candidate.status = "unmatched"
        elif request.matched_product_id is not None:
            product = await session.get(Product, request.matched_product_id)
            if product is None:
                raise NotFoundError("目标产品不存在。")
            candidate.matched_product_id = product.id
            candidate.matched_sku = product.sku
            candidate.match_method = "manual"
            candidate.match_confidence = Decimal("1.000")
            candidate.match_source = "manual_review"
            candidate.status = "matched"
        else:
            assert request.matched_sku is not None
            rows = list(
                await session.scalars(
                    select(ImportRow).where(ImportRow.import_job_id == candidate.import_job_id)
                )
            )
            matched_row = next(
                (
                    row
                    for row in rows
                    if not row.errors
                    and str(row.mapped_data.get("sku", "")).strip().lower()
                    == request.matched_sku.lower()
                ),
                None,
            )
            if matched_row is None:
                raise NotFoundError("本次导入预览中不存在该 SKU。")
            product = await session.scalar(
                select(Product).where(func.lower(Product.sku) == request.matched_sku.lower())
            )
            candidate.matched_product_id = product.id if product is not None else None
            candidate.matched_sku = str(matched_row.mapped_data["sku"]).strip()
            candidate.match_method = "manual"
            candidate.match_confidence = Decimal("1.000")
            candidate.match_source = "manual_preview_sku"
            candidate.status = "matched"
        candidate.image_type = request.image_type
        candidate.is_primary = request.is_primary
        await session.flush()
        return await self._image_response(session, candidate)

    async def get_candidate_file(
        self, session: AsyncSession, candidate_id: UUID
    ) -> tuple[Path, StoredFile]:
        candidate = await session.get(ImportImageCandidate, candidate_id)
        if candidate is None:
            raise NotFoundError("导入图片候选不存在。")
        stored_file = await session.get(StoredFile, candidate.stored_file_id)
        if stored_file is None:
            raise NotFoundError("导入图片文件不存在。")
        path = self._storage_path(stored_file.storage_key)
        if not path.is_file():
            raise NotFoundError("导入图片文件不存在。")
        return path, stored_file

    async def list_jobs(self, session: AsyncSession) -> list[ImportJobResponse]:
        jobs = list(
            await session.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()))
        )
        return [await self.get_job(session, job.id, include_details=False) for job in jobs]

    async def get_job(
        self, session: AsyncSession, job_id: UUID, *, include_details: bool = True
    ) -> ImportJobResponse:
        job = await self._get_job(session, job_id)
        source_file = await session.get(StoredFile, job.source_file_id)
        if source_file is None:
            raise NotFoundError("导入源文件不存在。")
        rows: list[ImportRowResponse] = []
        images: list[ImportImageCandidateResponse] = []
        if include_details:
            row_models = list(
                await session.scalars(
                    select(ImportRow)
                    .where(ImportRow.import_job_id == job.id)
                    .order_by(ImportRow.source_sheet, ImportRow.source_row)
                )
            )
            rows = [
                ImportRowResponse(
                    id=row.id,
                    source_sheet=row.source_sheet,
                    source_row=row.source_row,
                    source_data=row.source_data,
                    mapped_data=row.mapped_data,
                    status=row.status,
                    action=row.action,
                    errors=row.errors,
                    product_id=row.product_id,
                )
                for row in row_models
            ]
            image_models = list(
                await session.scalars(
                    select(ImportImageCandidate)
                    .where(ImportImageCandidate.import_job_id == job.id)
                    .order_by(
                        ImportImageCandidate.source_sheet,
                        ImportImageCandidate.source_row,
                        ImportImageCandidate.source_column,
                    )
                )
            )
            images = [await self._image_response(session, image) for image in image_models]
        return ImportJobResponse(
            id=job.id,
            tenant_id=job.tenant_id,
            import_template_id=job.import_template_id,
            source_file_id=job.source_file_id,
            source_filename=source_file.original_filename,
            source_sha256=source_file.sha256,
            status=job.status,
            analysis=job.analysis,
            mapping_snapshot=job.mapping_snapshot,
            duplicate_strategy=job.duplicate_strategy,
            total_rows=job.total_rows,
            valid_rows=job.valid_rows,
            imported_rows=job.imported_rows,
            skipped_rows=job.skipped_rows,
            conflict_rows=job.conflict_rows,
            error_message=job.error_message,
            rows=rows,
            images=images,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    @staticmethod
    async def _image_response(
        session: AsyncSession, candidate: ImportImageCandidate
    ) -> ImportImageCandidateResponse:
        stored_file = await session.get(StoredFile, candidate.stored_file_id)
        if stored_file is None:
            raise NotFoundError("导入图片文件不存在。")
        return ImportImageCandidateResponse(
            id=candidate.id,
            stored_file_id=candidate.stored_file_id,
            matched_product_id=candidate.matched_product_id,
            matched_sku=candidate.matched_sku,
            original_filename=candidate.original_filename,
            safe_filename=candidate.safe_filename,
            sha256=stored_file.sha256,
            mime_type=stored_file.mime_type,
            width=stored_file.width,
            height=stored_file.height,
            source_sheet=candidate.source_sheet,
            source_row=candidate.source_row,
            source_column=candidate.source_column,
            image_type=candidate.image_type,
            is_primary=candidate.is_primary,
            match_method=candidate.match_method,
            match_confidence=float(candidate.match_confidence),
            match_source=candidate.match_source,
            status=candidate.status,
            content_url=f"/api/v1/import-image-candidates/{candidate.id}/content",
        )


def template_response(template: ImportTemplate) -> ImportTemplateResponse:
    return ImportTemplateResponse(
        id=template.id,
        tenant_id=template.tenant_id,
        name=template.name,
        description=template.description,
        source_type=template.source_type,
        mapping_config=template.mapping_config,
        status=template.status,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )
