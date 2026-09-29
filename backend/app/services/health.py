import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.infrastructure.redis import get_redis
from app.schemas.health import DependencyHealth, HealthResponse


class HealthService:
    async def _database(self) -> DependencyHealth:
        try:
            async with SessionFactory() as session:
                await session.execute(text("SELECT 1"))
            return DependencyHealth(status="ok")
        except Exception as exc:
            return DependencyHealth(status="error", message=type(exc).__name__)

    async def _redis(self) -> DependencyHealth:
        try:
            await get_redis().ping()
            return DependencyHealth(status="ok")
        except Exception as exc:
            return DependencyHealth(status="error", message=type(exc).__name__)

    async def check(self) -> HealthResponse:
        settings = get_settings()
        try:
            database, redis = await asyncio.wait_for(
                asyncio.gather(self._database(), self._redis()),
                timeout=settings.dependency_timeout_seconds,
            )
        except TimeoutError:
            database = DependencyHealth(status="error", message="timeout")
            redis = DependencyHealth(status="error", message="timeout")

        overall = "ok" if database.status == redis.status == "ok" else "error"
        return HealthResponse(
            status=overall,
            service=settings.app_name,
            version=settings.app_version,
            dependencies={"postgres": database, "redis": redis},
        )

