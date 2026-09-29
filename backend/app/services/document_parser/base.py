from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.imports import ImportMappingConfig


class BaseImporter(ABC):
    @abstractmethod
    def analyze(self, path: Path, *, original_filename: str, sha256: str) -> tuple[dict, list]:
        raise NotImplementedError

    @abstractmethod
    def preview(self, path: Path, mapping: ImportMappingConfig) -> list[dict]:
        raise NotImplementedError
