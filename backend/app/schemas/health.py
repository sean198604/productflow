from typing import Literal

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    status: Literal["ok", "error"]
    message: str | None = None


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class HealthResponse(LiveResponse):
    status: Literal["ok", "error"]
    dependencies: dict[str, DependencyHealth]
