from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

from app.api.dependencies import AuthContext, get_auth_context
from app.schemas.generation import (
    GenerationTaskCreateRequest,
    GenerationTaskDetailResponse,
    GenerationTaskListResponse,
)
from app.services.generation import GenerationService

router = APIRouter(prefix="/generation-tasks", tags=["generation"])


def get_service() -> GenerationService:
    return GenerationService()


@router.get("", response_model=GenerationTaskListResponse)
async def list_generation_tasks(
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[GenerationService, Depends(get_service)],
) -> GenerationTaskListResponse:
    items = await service.list_tasks(context.session)
    return GenerationTaskListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=GenerationTaskDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_generation_task(
    payload: GenerationTaskCreateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[GenerationService, Depends(get_service)],
) -> GenerationTaskDetailResponse:
    return await service.create_task(
        context.session,
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        payload=payload,
    )


@router.get("/{task_id}", response_model=GenerationTaskDetailResponse)
async def get_generation_task(
    task_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[GenerationService, Depends(get_service)],
) -> GenerationTaskDetailResponse:
    return await service.get_task(context.session, task_id)


@router.get("/{task_id}/download", response_class=FileResponse)
async def download_generation_output(
    task_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context, scope="function")],
    service: Annotated[GenerationService, Depends(get_service)],
) -> FileResponse:
    path, stored_file = await service.output_path(context.session, task_id)
    return FileResponse(
        path,
        media_type=stored_file.mime_type,
        filename=stored_file.original_filename,
    )
