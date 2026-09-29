from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import AuthContext, get_auth_context, require_roles
from app.schemas.identity import UserRole
from app.schemas.templates import (
    OutputTemplateDetailResponse,
    OutputTemplateListResponse,
    OutputTemplateMapping,
    OutputTemplateUpdateRequest,
    OutputTemplateVersionResponse,
)
from app.services.output_templates import OutputTemplateService

router = APIRouter(prefix="/output-templates", tags=["output-templates"])
template_admin = require_roles(UserRole.OWNER, UserRole.ADMIN)


def get_service() -> OutputTemplateService:
    return OutputTemplateService()


@router.get("", response_model=OutputTemplateListResponse)
async def list_output_templates(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[OutputTemplateService, Depends(get_service)],
) -> OutputTemplateListResponse:
    items = await service.list(context.session)
    return OutputTemplateListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=OutputTemplateDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_output_template(
    context: Annotated[AuthContext, Depends(template_admin)],
    service: Annotated[OutputTemplateService, Depends(get_service)],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    file: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form(max_length=2000)] = None,
) -> OutputTemplateDetailResponse:
    return await service.create(
        context.session,
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        name=name,
        description=description,
        upload=file,
    )


@router.get("/{template_id}", response_model=OutputTemplateDetailResponse)
async def get_output_template(
    template_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[OutputTemplateService, Depends(get_service)],
) -> OutputTemplateDetailResponse:
    return await service.get(context.session, template_id)


@router.patch("/{template_id}", response_model=OutputTemplateDetailResponse)
async def update_output_template(
    template_id: UUID,
    request: OutputTemplateUpdateRequest,
    context: Annotated[AuthContext, Depends(template_admin)],
    service: Annotated[OutputTemplateService, Depends(get_service)],
) -> OutputTemplateDetailResponse:
    return await service.update(context.session, template_id=template_id, request=request)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_output_template(
    template_id: UUID,
    context: Annotated[AuthContext, Depends(template_admin)],
    service: Annotated[OutputTemplateService, Depends(get_service)],
) -> None:
    await service.delete(context.session, template_id=template_id)


@router.post(
    "/{template_id}/versions",
    response_model=OutputTemplateDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_output_template_version(
    template_id: UUID,
    context: Annotated[AuthContext, Depends(template_admin)],
    service: Annotated[OutputTemplateService, Depends(get_service)],
    file: Annotated[UploadFile, File()],
) -> OutputTemplateDetailResponse:
    return await service.create_version(
        context.session,
        template_id=template_id,
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        upload=file,
    )


@router.put(
    "/versions/{version_id}/mapping",
    response_model=OutputTemplateVersionResponse,
)
async def save_output_template_mapping(
    version_id: UUID,
    mapping: OutputTemplateMapping,
    context: Annotated[AuthContext, Depends(template_admin)],
    service: Annotated[OutputTemplateService, Depends(get_service)],
) -> OutputTemplateVersionResponse:
    return await service.save_mapping(context.session, version_id=version_id, mapping=mapping)


@router.get("/versions/{version_id}/content", response_class=FileResponse)
async def get_output_template_content(
    version_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[OutputTemplateService, Depends(get_service)],
) -> FileResponse:
    path, stored_file = await service.content_path(context.session, version_id)
    return FileResponse(
        path,
        media_type=stored_file.mime_type,
        filename=stored_file.original_filename,
    )
