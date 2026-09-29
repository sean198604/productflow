from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.dependencies import get_health_service
from app.core.config import get_settings
from app.schemas.health import HealthResponse, LiveResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    settings = get_settings()
    return LiveResponse(service=settings.app_name, version=settings.app_version)


@router.get("/health", response_model=HealthResponse)
@router.get("/health/ready", response_model=HealthResponse, include_in_schema=False)
async def health(
    health_service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse | JSONResponse:
    result = await health_service.check()
    if result.status != "ok":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=result.model_dump(),
        )
    return result

