from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import AuthContext, get_auth_context, require_roles
from app.schemas.identity import UserRole
from app.schemas.imports import (
    ImportConfirmRequest,
    ImportImageCandidateResponse,
    ImportImageMatchRequest,
    ImportJobListResponse,
    ImportJobResponse,
    ImportPreviewRequest,
    ImportTemplateCreateRequest,
    ImportTemplateListResponse,
    ImportTemplateResponse,
    ImportTemplateUpdateRequest,
)
from app.services.imports import ImportJobService, ImportTemplateService, template_response

router = APIRouter(tags=["imports"])
import_admin = require_roles(UserRole.OWNER, UserRole.ADMIN)


def get_template_service() -> ImportTemplateService:
    return ImportTemplateService()


def get_job_service() -> ImportJobService:
    return ImportJobService()


@router.get("/import-templates", response_model=ImportTemplateListResponse)
async def list_import_templates(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ImportTemplateService, Depends(get_template_service)],
) -> ImportTemplateListResponse:
    items = await service.list(context.session)
    return ImportTemplateListResponse(
        items=[template_response(template) for template in items], total=len(items)
    )


@router.post(
    "/import-templates",
    response_model=ImportTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_import_template(
    payload: ImportTemplateCreateRequest,
    context: Annotated[AuthContext, Depends(import_admin)],
    service: Annotated[ImportTemplateService, Depends(get_template_service)],
) -> ImportTemplateResponse:
    template = await service.create(
        context.session, tenant_id=context.tenant.id, payload=payload
    )
    return template_response(template)


@router.patch("/import-templates/{template_id}", response_model=ImportTemplateResponse)
async def update_import_template(
    template_id: UUID,
    payload: ImportTemplateUpdateRequest,
    context: Annotated[AuthContext, Depends(import_admin)],
    service: Annotated[ImportTemplateService, Depends(get_template_service)],
) -> ImportTemplateResponse:
    template = await service.update(
        context.session, template_id=template_id, payload=payload
    )
    return template_response(template)


@router.delete("/import-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_import_template(
    template_id: UUID,
    context: Annotated[AuthContext, Depends(import_admin)],
    service: Annotated[ImportTemplateService, Depends(get_template_service)],
) -> None:
    await service.delete(context.session, template_id=template_id)


@router.get("/import-jobs", response_model=ImportJobListResponse)
async def list_import_jobs(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ImportJobService, Depends(get_job_service)],
) -> ImportJobListResponse:
    items = await service.list_jobs(context.session)
    return ImportJobListResponse(items=items, total=len(items))


@router.post(
    "/import-jobs/analyze",
    response_model=ImportJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_import_file(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ImportJobService, Depends(get_job_service)],
    file: Annotated[UploadFile, File()],
) -> ImportJobResponse:
    return await service.analyze_upload(
        context.session,
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        upload=file,
    )


@router.get("/import-jobs/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ImportJobService, Depends(get_job_service)],
) -> ImportJobResponse:
    return await service.get_job(context.session, job_id)


@router.post("/import-jobs/{job_id}/preview", response_model=ImportJobResponse)
async def preview_import_job(
    job_id: UUID,
    payload: ImportPreviewRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ImportJobService, Depends(get_job_service)],
) -> ImportJobResponse:
    return await service.preview(context.session, job_id=job_id, request=payload)


@router.post("/import-jobs/{job_id}/confirm", response_model=ImportJobResponse)
async def confirm_import_job(
    job_id: UUID,
    payload: ImportConfirmRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ImportJobService, Depends(get_job_service)],
) -> ImportJobResponse:
    return await service.confirm(context.session, job_id=job_id, request=payload)


@router.patch(
    "/import-image-candidates/{candidate_id}",
    response_model=ImportImageCandidateResponse,
)
async def manually_match_import_image(
    candidate_id: UUID,
    payload: ImportImageMatchRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ImportJobService, Depends(get_job_service)],
) -> ImportImageCandidateResponse:
    return await service.manual_match_image(
        context.session, candidate_id=candidate_id, request=payload
    )


@router.get(
    "/import-image-candidates/{candidate_id}/content",
    response_class=FileResponse,
)
async def get_import_image_candidate_content(
    candidate_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[ImportJobService, Depends(get_job_service)],
) -> FileResponse:
    path, stored_file = await service.get_candidate_file(context.session, candidate_id)
    return FileResponse(
        path,
        media_type=stored_file.mime_type,
        filename=stored_file.safe_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=300"},
    )
