from pathlib import Path

from markitdown import MarkItDown


class MarkItDownService:
    """Optional workbook content-understanding layer; openpyxl remains authoritative."""

    def __init__(self, *, max_characters: int = 100_000) -> None:
        self.max_characters = max_characters

    def convert_local(self, path: Path) -> dict[str, object]:
        try:
            converter = MarkItDown(enable_plugins=False)
            result = converter.convert_local(str(path))
            markdown = getattr(result, "markdown", None)
            if markdown is None:
                markdown = getattr(result, "text_content", "")
            markdown = str(markdown or "")
            truncated = len(markdown) > self.max_characters
            return {
                "status": "ok",
                "markdown": markdown[: self.max_characters],
                "truncated": truncated,
            }
        except Exception as exc:  # MarkItDown is an enrichment layer, not the parser.
            return {
                "status": "unavailable",
                "markdown": "",
                "truncated": False,
                "error": str(exc)[:500],
            }
