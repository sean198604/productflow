import asyncio
import hashlib
import os
import re
import unicodedata
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    Customer,
    FieldDefinition,
    GenerationTask,
    OutputTemplate,
    OutputTemplateVersion,
    StoredFile,
)
from app.schemas.templates import (
    CUSTOMER_SOURCES,
    IMAGE_SOURCES,
    OutputTemplateDetailResponse,
    OutputTemplateMapping,
    OutputTemplateResponse,
    OutputTemplateUpdateRequest,
    OutputTemplateVersionResponse,
)
from app.services.template_parser import TemplateParser

settings = get_settings()

MIME_TYPES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _safe_filename(original: str, digest: str, extension: str) -> str:
    stem = Path(original).stem
    normalized = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized).strip("-._") or "template"
    return f"{digest[:12]}-{clean[:120]}{extension}"


class OutputTemplateService:
    def __init__(self) -> None:
        self.parser = TemplateParser()

    @staticmethod
    def _storage_path(storage_key: str) -> Path:
        root = settings.storage_root.resolve()
        destination = (root / storage_key).resolve()
        if root not in destination.parents:
            raise BadRequestError("文件存储路径无效。")
        return destination

    async def _read_upload(self, upload: UploadFile, expected_type: str | None = None) -> tuple:
        filename = upload.filename or "template"
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in MIME_TYPES:
            raise BadRequestError("输出模板仅支持 PPTX 和 XLSX 文件。")
        if expected_type is not None and extension != expected_type:
            raise BadRequestError(f"该模板只能上传 {expected_type.upper()} 文件。")
        limit = settings.max_upload_size_mb * 1024 * 1024
        payload = await upload.read(limit + 1)
        if not payload:
            raise BadRequestError("上传文件为空。")
        if len(payload) > limit:
            raise BadRequestError(f"模板文件不能超过 {settings.max_upload_size_mb} MB。")
        return filename, extension, payload, hashlib.sha256(payload).hexdigest()

    async def _store_and_parse(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        filename: str,
        output_type: str,
        payload: bytes,
        digest: str,
    ) -> tuple[StoredFile, dict]:
        existing = await session.scalar(select(StoredFile).where(StoredFile.sha256 == digest))
        created_physical_file = False
        if existing is not None:
            path = self._storage_path(existing.storage_key)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
                temporary.write_bytes(payload)
                os.replace(temporary, path)
        else:
            storage_key = (
                f"{tenant_id}/templates/{output_type}/{digest[:2]}/{digest}.{output_type}"
            )
            path = self._storage_path(storage_key)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
                temporary.write_bytes(payload)
                os.replace(temporary, path)
                created_physical_file = True
        try:
            report = await asyncio.to_thread(self.parser.parse, path, output_type)
        except Exception:
            if created_physical_file and path.is_file():
                path.unlink()
            raise

        if existing is not None:
            return existing, report
        stored_file = StoredFile(
            tenant_id=tenant_id,
            storage_key=storage_key,
            original_filename=filename[:500],
            safe_filename=_safe_filename(filename, digest, f".{output_type}"),
            sha256=digest,
            mime_type=MIME_TYPES[output_type],
            size_bytes=len(payload),
        )
        session.add(stored_file)
        await session.flush()
        return stored_file, report

    async def create(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        description: str | None,
        upload: UploadFile,
    ) -> OutputTemplateDetailResponse:
        clean_name = name.strip()
        if not clean_name:
            raise BadRequestError("模板名称不能为空。")
        duplicate = await session.scalar(
            select(OutputTemplate.id).where(func.lower(OutputTemplate.name) == clean_name.lower())
        )
        if duplicate is not None:
            raise ConflictError("当前租户中已存在同名输出模板。")
        filename, output_type, payload, digest = await self._read_upload(upload)
        stored_file, report = await self._store_and_parse(
            session,
            tenant_id=tenant_id,
            filename=filename,
            output_type=output_type,
            payload=payload,
            digest=digest,
        )
        report["template_changed"] = False
        template = OutputTemplate(
            tenant_id=tenant_id,
            name=clean_name[:200],
            description=description.strip()[:2000] if description and description.strip() else None,
            output_type=output_type,
            current_version_number=1,
        )
        session.add(template)
        await session.flush()
        version = OutputTemplateVersion(
            tenant_id=tenant_id,
            output_template_id=template.id,
            stored_file_id=stored_file.id,
            created_by_user_id=user_id,
            version_number=1,
            template_sha256=digest,
            validation_report=report,
            mapping_config={"version": "1.0", "template_sha256": digest, "bindings": []},
            status="needs_mapping",
        )
        session.add(version)
        await session.flush()
        return await self.get(session, template.id)

    async def create_version(
        self,
        session: AsyncSession,
        *,
        template_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        upload: UploadFile,
    ) -> OutputTemplateDetailResponse:
        template = await session.get(OutputTemplate, template_id)
        if template is None:
            raise NotFoundError("输出模板不存在。")
        if template.status != "active":
            raise BadRequestError("已归档模板不能上传新版本。")
        filename, output_type, payload, digest = await self._read_upload(
            upload, template.output_type
        )
        duplicate = await session.scalar(
            select(OutputTemplateVersion.id).where(
                OutputTemplateVersion.output_template_id == template.id,
                OutputTemplateVersion.template_sha256 == digest,
            )
        )
        if duplicate is not None:
            raise ConflictError("这个模板文件已经上传过，无需创建重复版本。")
        stored_file, report = await self._store_and_parse(
            session,
            tenant_id=tenant_id,
            filename=filename,
            output_type=output_type,
            payload=payload,
            digest=digest,
        )
        report["template_changed"] = True
        report["fingerprint_message"] = "模板文件发生变化，请重新验证字段映射。"
        version_number = template.current_version_number + 1
        session.add(
            OutputTemplateVersion(
                tenant_id=tenant_id,
                output_template_id=template.id,
                stored_file_id=stored_file.id,
                created_by_user_id=user_id,
                version_number=version_number,
                template_sha256=digest,
                validation_report=report,
                mapping_config={"version": "1.0", "template_sha256": digest, "bindings": []},
                status="needs_mapping",
            )
        )
        template.current_version_number = version_number
        await session.flush()
        await session.refresh(template)
        return await self.get(session, template.id)

    async def list(self, session: AsyncSession) -> list[OutputTemplateResponse]:
        templates = list(
            await session.scalars(
                select(OutputTemplate).order_by(
                    OutputTemplate.status, OutputTemplate.updated_at.desc()
                )
            )
        )
        return [await self._template_response(session, template) for template in templates]

    async def get(
        self, session: AsyncSession, template_id: UUID
    ) -> OutputTemplateDetailResponse:
        template = await session.get(OutputTemplate, template_id)
        if template is None:
            raise NotFoundError("输出模板不存在。")
        versions = list(
            await session.scalars(
                select(OutputTemplateVersion)
                .where(OutputTemplateVersion.output_template_id == template.id)
                .order_by(OutputTemplateVersion.version_number.desc())
            )
        )
        version_payloads = [
            await self._version_response(session, version) for version in versions
        ]
        current = next(
            item
            for item in version_payloads
            if item.version_number == template.current_version_number
        )
        return OutputTemplateDetailResponse(
            id=template.id,
            tenant_id=template.tenant_id,
            name=template.name,
            description=template.description,
            output_type=template.output_type,
            status=template.status,
            current_version_number=template.current_version_number,
            current_version=current,
            versions=version_payloads,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    async def update(
        self,
        session: AsyncSession,
        *,
        template_id: UUID,
        request: OutputTemplateUpdateRequest,
    ) -> OutputTemplateDetailResponse:
        template = await session.get(OutputTemplate, template_id)
        if template is None:
            raise NotFoundError("输出模板不存在。")
        values = request.model_dump(exclude_unset=True)
        if "name" in values:
            duplicate = await session.scalar(
                select(OutputTemplate.id).where(
                    func.lower(OutputTemplate.name) == values["name"].lower(),
                    OutputTemplate.id != template.id,
                )
            )
            if duplicate is not None:
                raise ConflictError("当前租户中已存在同名输出模板。")
        if request.status is not None:
            values["status"] = request.status.value
        for key, value in values.items():
            setattr(template, key, value)
        await session.flush()
        await session.refresh(template)
        return await self.get(session, template.id)

    async def delete(self, session: AsyncSession, *, template_id: UUID) -> None:
        template = await session.get(OutputTemplate, template_id)
        if template is None:
            raise NotFoundError("输出模板不存在。")

        version_ids = select(OutputTemplateVersion.id).where(
            OutputTemplateVersion.output_template_id == template.id
        )
        generation_count = int(
            await session.scalar(
                select(func.count())
                .select_from(GenerationTask)
                .where(GenerationTask.output_template_version_id.in_(version_ids))
            )
            or 0
        )
        if generation_count:
            raise ConflictError(
                f"该模板已被 {generation_count} 个历史生成任务使用，不能永久删除。"
                "可以将模板状态改为“已归档”。"
            )

        # 客户默认模板是可选配置；删除模板时安全解除默认绑定。
        await session.execute(
            update(Customer)
            .where(Customer.default_ppt_template_id == template.id)
            .values(default_ppt_template_id=None)
        )
        await session.execute(
            update(Customer)
            .where(Customer.default_xlsx_template_id == template.id)
            .values(default_xlsx_template_id=None)
        )
        await session.delete(template)
        await session.flush()

    async def save_mapping(
        self,
        session: AsyncSession,
        *,
        version_id: UUID,
        mapping: OutputTemplateMapping,
    ) -> OutputTemplateVersionResponse:
        version = await session.get(OutputTemplateVersion, version_id)
        if version is None:
            raise NotFoundError("输出模板版本不存在。")
        if mapping.template_sha256 != version.template_sha256:
            raise ConflictError("模板文件发生变化，请重新验证字段映射。")
        objects = {
            item["object_key"]: item
            for item in version.validation_report.get("objects", [])
        }
        unknown_objects = {
            binding.object_key
            for binding in mapping.bindings
            if binding.object_key not in objects
            or not objects[binding.object_key].get("supported", False)
        }
        if unknown_objects:
            raise BadRequestError(
                f"映射包含不存在或不支持的模板对象：{', '.join(sorted(unknown_objects))}"
            )
        all_sources = {
            source
            for binding in mapping.bindings
            for source in [binding.source, *(run.source for run in binding.text_runs)]
        }
        field_sources = all_sources - CUSTOMER_SOURCES
        fields = list(
            await session.scalars(
                select(FieldDefinition).where(FieldDefinition.code.in_(field_sources))
            )
        ) if field_sources else []
        by_code = {field.code: field for field in fields}
        unknown_fields = field_sources - set(by_code)
        if unknown_fields:
            raise BadRequestError(
                f"映射引用了未知字段：{', '.join(sorted(unknown_fields))}"
            )
        forbidden_fields = {
            code
            for code, field in by_code.items()
            if field.scope == "internal" or field.status != "active"
        }
        if forbidden_fields:
            raise BadRequestError(
                "客户输出模板禁止绑定内部或已停用字段："
                + ", ".join(sorted(forbidden_fields))
            )
        for binding in mapping.bindings:
            object_type = objects[binding.object_key]["object_type"]
            is_image_source = binding.source in IMAGE_SOURCES
            if is_image_source and object_type != "image":
                raise BadRequestError("图片规则只能绑定到图片对象。")
            if not is_image_source and object_type == "image":
                raise BadRequestError("图片对象必须绑定 image.* 图片来源。")
            if binding.text_runs and object_type != "text":
                raise BadRequestError("文本 Run 规则只能绑定到 PPT 文本对象。")
        version.mapping_config = mapping.model_dump(mode="json")
        version.status = "ready" if mapping.bindings else "needs_mapping"
        report = dict(version.validation_report)
        report["mapped_object_count"] = len(mapping.bindings)
        report["mapping_verified"] = bool(mapping.bindings)
        version.validation_report = report
        await session.flush()
        await session.refresh(version)
        return await self._version_response(session, version)

    async def content_path(
        self, session: AsyncSession, version_id: UUID
    ) -> tuple[Path, StoredFile]:
        version = await session.get(OutputTemplateVersion, version_id)
        if version is None:
            raise NotFoundError("输出模板版本不存在。")
        stored_file = await session.get(StoredFile, version.stored_file_id)
        if stored_file is None:
            raise NotFoundError("模板文件不存在。")
        path = self._storage_path(stored_file.storage_key)
        if not path.is_file():
            raise NotFoundError("模板文件不存在。")
        return path, stored_file

    async def _template_response(
        self, session: AsyncSession, template: OutputTemplate
    ) -> OutputTemplateResponse:
        version = await session.scalar(
            select(OutputTemplateVersion).where(
                OutputTemplateVersion.output_template_id == template.id,
                OutputTemplateVersion.version_number == template.current_version_number,
            )
        )
        if version is None:
            raise NotFoundError("输出模板当前版本不存在。")
        return OutputTemplateResponse(
            id=template.id,
            tenant_id=template.tenant_id,
            name=template.name,
            description=template.description,
            output_type=template.output_type,
            status=template.status,
            current_version_number=template.current_version_number,
            current_version=await self._version_response(session, version),
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    async def _version_response(
        self, session: AsyncSession, version: OutputTemplateVersion
    ) -> OutputTemplateVersionResponse:
        stored_file = await session.get(StoredFile, version.stored_file_id)
        if stored_file is None:
            raise NotFoundError("模板文件不存在。")
        return OutputTemplateVersionResponse(
            id=version.id,
            version_number=version.version_number,
            template_sha256=version.template_sha256,
            original_filename=stored_file.original_filename,
            safe_filename=stored_file.safe_filename,
            mime_type=stored_file.mime_type,
            size_bytes=stored_file.size_bytes,
            validation_report=version.validation_report,
            mapping_config=version.mapping_config,
            status=version.status,
            created_at=version.created_at,
            updated_at=version.updated_at,
        )
